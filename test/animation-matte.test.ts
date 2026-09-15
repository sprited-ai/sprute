import { test, expect, vi } from 'vitest';
import { mkdtemp, readFile, writeFile, mkdir, rm, readdir, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { createImage } from '../src/core/image.js';
import { readImage, writePng } from '../src/node/io.js';
import { toonoutMatting } from '../src/node/toonout.js';
import { matteAnimationCycle, matteAnimationDirectory } from '../src/node/animation-matte.js';
import { packAnimationFile } from '../src/node/animation.js';
import { SPIN_ORDER } from '../src/core/extract.js';
vi.mock('../src/node/toonout.js', () => {
  const toonoutMatting = vi.fn();
  return { toonoutMatting, toonoutMattingWithProvenance: async (images: unknown[]) => ({ images: await toonoutMatting(images),
    provenance: { model: { file: 'fixture.onnx', bytes: 4, sha256: 'a'.repeat(64) }, runtime: { onnxruntime: 'test', executionProvider: 'cpu', platform: 'test', arch: 'test' } } }) };
});

test('packing rejects a modified matte output without manually adding hashes', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-matte-pack-'));
  try {
    const source = join(root, 'source');
    await mkdir(join(source, 'frames'), { recursive: true });
    const frames = [];
    for (let i = 0; i < 2; i++) {
      const file = `frames/${String(i + 1).padStart(6, '0')}.png`;
      await writePng(join(source, file), createImage(2, 2, [20 + i, 30, 40, 255]));
      frames.push({ file, sourceFrame: i, time: i * .04, duration: .04 });
    }
    await writeFile(join(source, 'cycle.json'), JSON.stringify({ version: 1, width: 2, height: 2, columns: 1, rows: 1, frameCount: 2, frames }));
    vi.mocked(toonoutMatting).mockImplementation(async images => images);
    await matteAnimationCycle(source, join(root, 'matted'));
    const manifest = join(root, 'walk.json');
    await writeFile(manifest, JSON.stringify({ version: 1, cellWidth: 2, cellHeight: 2, fps: 25, loop: false,
      cycles: Object.fromEntries(SPIN_ORDER.map(d => [d, 'matted'])) }));
    await packAnimationFile(manifest, join(root, 'valid'));
    const packed = JSON.parse(await readFile(join(root, 'valid/animation.json'), 'utf8'));
    expect(packed.source.cycles.S.processing.runtimes[0].model.sha256).toBe('a'.repeat(64));
    expect(packed.source.cycles.S.frames.map((f: any) => f.mattingRuntime)).toEqual([0, 0]);
    const cyclePath = join(root, 'matted/cycle.json'), savedCycle = await readFile(cyclePath);
    const invalidCycle = JSON.parse(savedCycle.toString()); invalidCycle.frames[0].mattingRuntime = 9;
    await writeFile(cyclePath, JSON.stringify(invalidCycle));
    await expect(packAnimationFile(manifest, join(root, 'invalid-runtime'))).rejects.toThrow('Invalid matting runtime reference');
    await writeFile(cyclePath, savedCycle);
    await writePng(join(root, 'matted/frames/000002.png'), createImage(2, 2, [99, 30, 40, 255]));
    await expect(packAnimationFile(manifest, join(root, 'changed'))).rejects.toThrow(/hash mismatch/i);
    expect(await readdir(root)).not.toContain('changed');
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('matting retains explicit order and variable timing; rejects invalid inputs and cleans failures', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-matte-test-'));
  const source = join(root, 'source'); await mkdir(join(source, 'frames'), { recursive: true });
  const frames = [ {file:'frames/000010.png',sourceFrame:9,time:0,duration:.04}, {file:'frames/000002.png',sourceFrame:10,time:.04,duration:.06} ];
  const metadata = {version:1,width:2,height:2,columns:1,rows:1,frameCount:2,frames};
  const seen: number[] = [];
  try {
    for (let i=0;i<2;i++) await writePng(join(source,frames[i].file),createImage(2,2,[20+i,30,40,255]));
    await writeFile(join(source,'cycle.json'),JSON.stringify(metadata));
    vi.mocked(toonoutMatting).mockImplementation(async images=>{seen.push(images[0].data[0]);const result={...images[0],data:images[0].data.slice()};result.data[3]=0;return[result];});
    const output=join(root,'result'); const result=await matteAnimationCycle(source,output);
    expect(seen).toEqual([20,21]);expect(result.metadata.durationSeconds).toBe(.1);
    expect(result.metadata.frames.map(f=>[f.sourceFrame,f.time,f.duration])).toEqual([[9,0,.04],[10,.04,.06]]);
    expect(result.metadata.frames.every(f=>/^[a-f0-9]{64}$/.test(f.sourceSha256))).toBe(true);
    expect((await readImage(join(output,'frames/000001.png'))).data.slice(0,4)).toEqual(new Uint8ClampedArray([20,30,40,0]));
    expect((await readImage(join(source,frames[0].file))).data[3]).toBe(255);
    await expect(matteAnimationCycle(source,output)).rejects.toThrow('already exists');
    let calls=0;vi.mocked(toonoutMatting).mockImplementation(async images=>{if(++calls===2)throw new Error('inference failed');return images;});
    await expect(matteAnimationCycle(source,join(root,'failed'))).rejects.toThrow('inference failed');
    expect(await readdir(root)).toEqual(expect.arrayContaining(['source','result']));
    expect((await readdir(root)).some(p=>p==='failed'||p.startsWith('.sprute-matte'))).toBe(false);
    vi.mocked(toonoutMatting).mockClear();
    await writeFile(join(source,'cycle.json'),JSON.stringify({...metadata,frames:[frames[0],{...frames[1],time:.5}]}));
    await expect(matteAnimationCycle(source,join(root,'invalid'))).rejects.toThrow('timeline');
    await writeFile(join(source,'cycle.json'),JSON.stringify(metadata));
    const external=join(root,'outside.png');await writePng(external,createImage(2,2));await rm(join(source,frames[1].file));await symlink(external,join(source,frames[1].file));
    await expect(matteAnimationCycle(source,join(root,'escape'))).rejects.toThrow('escapes');
    expect(toonoutMatting).not.toHaveBeenCalled();
  } finally { await rm(root,{recursive:true,force:true}); }
});

test('rejects a changed hashed cycle before inference or output creation', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-matte-hash-'));
  try {
    await mkdir(join(root, 'source/frames'), { recursive: true });
    const frames = [];
    for (let i = 0; i < 2; i++) {
      const file = `frames/${String(i + 1).padStart(6, '0')}.png`;
      await writePng(join(root, 'source', file), createImage(2, 2, [20, 30, 40, 255]));
      frames.push({ file, sourceFrame: i, time: i * .04, duration: .04,
        sha256: createHash('sha256').update(await readFile(join(root, 'source', file))).digest('hex') });
    }
    await writeFile(join(root, 'source/cycle.json'), JSON.stringify({ version: 1, width: 2, height: 2, columns: 1, rows: 1, frameCount: 2, frames }));
    await writePng(join(root, 'source', frames[1].file), createImage(2, 2, [99, 30, 40, 255]));
    vi.mocked(toonoutMatting).mockClear().mockImplementation(async images => images);
    await expect(matteAnimationCycle(join(root, 'source'), join(root, 'result'))).rejects.toThrow('hash mismatch');
    expect(toonoutMatting).not.toHaveBeenCalled();
    expect(await readdir(root)).toEqual(['source']);
    await writePng(join(root, 'source', frames[1].file), createImage(2, 2, [20, 30, 40, 255]));
    const valid = await matteAnimationCycle(join(root, 'source'), join(root, 'valid'));
    expect(valid.metadata.frames.map(f => f.sourceSha256)).toEqual(frames.map(f => f.sha256));
    vi.mocked(toonoutMatting).mockClear().mockImplementation(async images => {
      await writePng(join(root, 'source', frames[1].file), createImage(2, 2, [99, 30, 40, 255]));
      return images;
    });
    await expect(matteAnimationCycle(join(root, 'source'), join(root, 'changed'))).rejects.toThrow('changed during matting');
    expect(toonoutMatting).toHaveBeenCalledTimes(1);
    expect((await readdir(root)).sort()).toEqual(['source', 'valid']);
  } finally { await rm(root, { recursive: true, force: true }); }
});


test('eight-direction matting packs directly and journals a stopped batch without overwriting it', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-matte-eight-'));
  try {
    const input = join(root, 'input');
    for (const d of SPIN_ORDER) {
      await mkdir(join(input, d, 'frames'), { recursive: true });
      const frames = [];
      for (let i = 0; i < 2; i++) {
        const file = `frames/${String(i + 1).padStart(6, '0')}.png`;
        await writePng(join(input, d, file), createImage(2, 2, [20, 30, 40, 255]));
        frames.push({ file, sourceFrame: i + 32, time: i / 24, duration: 1 / 24 });
      }
      await writeFile(join(input, d, 'cycle.json'), JSON.stringify({ version: 1, width: 2, height: 2,
        columns: 1, rows: 1, frameCount: 2, durationSeconds: 2 / 24, frames }));
    }
    vi.mocked(toonoutMatting).mockImplementation(async images => images);
    const output = join(root, 'complete');
    await matteAnimationDirectory(input, output);
    const receipt = JSON.parse(await readFile(join(output, 'matting-state.json'), 'utf8'));
    expect(receipt.status).toBe('complete'); expect(receipt.completed).toEqual(SPIN_ORDER);
    const { packAnimationDirectory } = await import('../src/node/animation.js');
    await packAnimationDirectory(output, join(root, 'packed'));
    expect(await readdir(join(root, 'packed'))).toContain('animation.png');
    let calls = 0;
    vi.mocked(toonoutMatting).mockImplementation(async images => {
      if (++calls === 3) throw new Error('model failed');
      return images;
    });
    const failed = join(root, 'failed');
    await expect(matteAnimationDirectory(input, failed)).rejects.toThrow('model failed');
    const state = JSON.parse(await readFile(join(failed, 'matting-state.json'), 'utf8'));
    expect(state).toMatchObject({ status: 'failed', completed: ['S'], active: 'SE', error: 'model failed' });
    expect((await readdir(failed)).sort()).toEqual(['S', 'matting-state.json']);
    await expect(matteAnimationDirectory(input, failed)).rejects.toThrow();
    expect(calls).toBe(3);
  } finally { await rm(root, { recursive: true, force: true }); }
});
