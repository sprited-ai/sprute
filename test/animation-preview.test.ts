import { test, expect } from 'vitest';
import { mkdtemp, readFile, writeFile, rm, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { createImage } from '../src/core/image.js';
import { packAnimation } from '../src/core/animation.js';
import { SPIN_ORDER } from '../src/core/extract.js';
import { writePng } from '../src/node/io.js';
import { previewAnimation } from '../src/node/animation-preview.js';
import { animationPreviewHtml } from '../src/node/animation-preview-html.js';
import { runInNewContext } from 'node:vm';

test('review notes stay attached to the frame being described while navigating', async () => {
  const elements: Record<string, any> = {};
  function element() {
    return { value: '', textContent: '', disabled: true, dataset: {}, style: {}, children: [] as any[],
      append(...items: any[]) { this.children.push(...items); }, setAttribute() {}, click() {},
      replaceChildren(...items: any[]) { this.children = items; },
      draws: [] as any[],
      getContext() { return { clearRect() {}, drawImage: (...args: any[]) => this.draws.push(args) }; } };
  }
  const get = (id: string) => elements[id] ??= element();
  const data = { directions: ['S','NW'], width: 2, height: 2, count: 2, loop: false,
    atlas: 'data:image/png;base64,fixture', atlasSha256: 'atlas', metadataSha256: 'metadata',
    reference: { image: 'data:image/png;base64,source', width: 10, height: 10, sha256: 'reference' },
    tracks: Object.fromEntries(['S','NW'].map(d => [d, [40,160].map(durationMs =>
      ({ x:0, y:0, width:2, height:2, durationMs }))])) };
  get('animation-data').textContent = JSON.stringify(data);
  get('speed').value = '1';
  let tick: (now: number) => void = () => {};
  let exported: Blob | undefined;
  const script = animationPreviewHtml(data).match(/<script>\n([\s\S]*?)<\/script>/)![1];
  runInNewContext(script, {
    document: { getElementById: get, createElement: element, addEventListener() {} },
    Image: class { onload?: () => void; set src(_: string) { this.onload?.(); } },
    performance: { now: () => 0 }, requestAnimationFrame: (fn: typeof tick) => { tick = fn; },
    Blob, URL: { createObjectURL: (blob: Blob) => { exported = blob; return 'blob:notes'; }, revokeObjectURL() {} },
    setTimeout() {},
  });
  expect(get('note').disabled).toBe(false);
  expect(get('referencePanel').hidden).toBe(false);
  expect(get('referenceCanvas').draws.at(-1).slice(1)).toEqual([0,0,10,10,0,0,10,10]);
  get('play').onclick(); tick(60);
  expect(get('status').textContent).toContain('2 / 2');
  get('note').onfocus(); tick(180);
  expect(get('play').textContent).toBe('Play');
  expect(get('status').textContent).toContain('60 ms');
  get('note').value = 'Shoe changes shape'; get('note').oninput();
  get('grid').children[1].onclick(); get('prev').onclick();
  expect(get('heading').textContent).toBe('NW');
  expect(get('referenceCanvas').draws.at(-1).slice(1)).toEqual([10,0,10,10,0,0,10,10]);
  expect(get('noteTarget').textContent).toBe('Note for S, frame 2 (fixed while editing)');
  get('saveNote').onclick(); get('export').onclick();
  expect(JSON.parse(await exported!.text())).toMatchObject({ atlasSha256:'atlas', metadataSha256:'metadata', referenceSha256:'reference',
    notes: [{ direction:'S', frame:1, timeMs:60, text:'Shoe changes shape' }] });
  expect(get('noteTarget').textContent).toBe('Note for NW, frame 1');

  get('note').value = 'discard'; get('note').oninput();
  get('note').value = ''; get('note').oninput();
  get('next').onclick();
  get('note').value = 'Different detail'; get('note').oninput(); get('saveNote').onclick();
  get('export').onclick();
  expect(JSON.parse(await exported!.text()).notes[1]).toEqual({ direction:'NW', frame:1, timeMs:40, text:'Different detail' });

  const saved = JSON.parse(await exported!.text());
  const load = async (value: unknown) => {
    const text = JSON.stringify(value);
    get('importNotes').files = [{ size: text.length, text: async () => text }];
    await get('importNotes').onchange();
  };
  await load(saved); // Loading the same file should not duplicate existing notes.
  expect(get('noteList').children).toHaveLength(2);
  await load({ ...saved, atlasSha256:'other', notes:[] });
  expect(get('notesError').textContent).toContain('different animation');
  expect(get('noteList').children).toHaveLength(2);
  await load({ ...saved, referenceSha256:'other-reference' });
  expect(get('notesError').textContent).toContain('different original reference');
  expect(get('noteList').children).toHaveLength(2);
  await load({ ...saved, notes:[saved.notes[0],{...saved.notes[1],frame:999}] });
  expect(get('notesError').textContent).toContain('Invalid');
  expect(get('noteList').children).toHaveLength(2);
  await load({ ...saved, notes:[{direction:'S',frame:0,timeMs:0,text:'<img onerror=alert(1)>'}] });
  expect(get('noteList').children).toHaveLength(3);
  const button = get('noteList').children[2].children[0];
  expect(button.textContent).toContain('<img onerror=alert(1)>');
  button.onclick();
  expect(get('heading').textContent).toBe('S');
  expect(get('status').textContent).toContain('1 / 2');
  get('export').onclick();
  expect(JSON.parse(await exported!.text()).notes).toHaveLength(3);
});

test('offline preview embeds exact atlas, variable durations and loop preference; rejects damaged inputs', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-preview-'));
  try {
    const input = join(root, 'packed');await mkdir(input);
    const packed = packAnimation([createImage(2,16,[20,30,40,128]),createImage(2,16,[80,90,100,255])],{cellWidth:2,cellHeight:2,columns:1,directions:[...SPIN_ORDER],fps:10,loop:false});
    for(const d of SPIN_ORDER) { packed.metadata.animations[d][0].durationMs=40;packed.metadata.animations[d][1].durationMs=160; }
    await writePng(join(input,'animation.png'),packed.atlas);
    await writeFile(join(input,'animation.json'),JSON.stringify(packed.metadata));
    const output=join(root,'review.html');await previewAnimation(input,output);
    const html=await readFile(output,'utf8');
    const data=JSON.parse(html.match(/<script id="animation-data" type="application\/json">(.*?)<\/script>/s)![1]);
    const png=await readFile(join(input,'animation.png'));
    expect(Buffer.from(data.atlas.split(',')[1],'base64')).toEqual(png);
    expect(data.atlasSha256).toBe(createHash('sha256').update(png).digest('hex'));
    expect(data.loop).toBe(false);expect(data.count).toBe(2);
    expect(data.tracks.NW.map((f:any)=>f.durationMs)).toEqual([40,160]);
    const reference = join(root, 'reference.png');
    await writePng(reference, createImage(24,2,[90,10,20,255]));
    await previewAnimation(input,join(root,'with-source.html'),reference);
    const compared = JSON.parse((await readFile(join(root,'with-source.html'),'utf8')).match(/<script id="animation-data" type="application\/json">(.*?)<\/script>/s)![1]);
    const source = await readFile(reference);
    expect(Buffer.from(compared.reference.image.split(',')[1],'base64')).toEqual(source);
    expect(compared.reference.sha256).toBe(createHash('sha256').update(source).digest('hex'));
    expect(compared.atlasSha256).toBe(data.atlasSha256);
    await writePng(reference,createImage(2,2));
    await expect(previewAnimation(input,join(root,'bad-reference.html'),reference)).rejects.toThrow('eight-view');
    await expect(readFile(join(root,'bad-reference.html'))).rejects.toMatchObject({code:'ENOENT'});
    await expect(previewAnimation(input,output)).rejects.toMatchObject({code:'EEXIST'});
    expect(await readFile(output,'utf8')).toBe(html);
    packed.metadata.animations.S[0].x=1;
    await writeFile(join(input,'animation.json'),JSON.stringify(packed.metadata));
    await expect(previewAnimation(input,join(root,'invalid.html'))).rejects.toThrow('rectangle');
    await expect(readFile(join(root,'invalid.html'))).rejects.toMatchObject({code:'ENOENT'});
    packed.metadata.animations.S[0].x=0;
    await writeFile(join(input,'animation.json'),JSON.stringify(packed.metadata));
    await writePng(join(input,'animation.png'),createImage(1,1));
    await expect(previewAnimation(input,join(root,'wrong-size.html'))).rejects.toThrow('geometry');
  } finally { await rm(root,{recursive:true,force:true}); }
});
