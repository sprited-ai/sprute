import { test, expect } from 'vitest';
import { createHash } from 'node:crypto';
import { runInNewContext } from 'node:vm';
import { mkdtemp, rm, readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import sharp from 'sharp';
import { reviewAnimation } from '../src/node/animation-review.js';

test('review keeps every decoded frame including a late artifact, and never replaces output', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-review-test-'));
  try {
    for (let i = 0; i < 3; i++) await sharp({ create: { width: 32, height: 32, channels: 3, background: i === 2 ? '#ff0000' : '#000000' } }).png().toFile(join(root, `${i + 1}.png`));
    const video = join(root, 'clip.mkv');
    execFileSync('ffmpeg', ['-v', 'error', '-framerate', '2', '-i', join(root, '%d.png'), '-c:v', 'ffv1', video]);
    const output = join(root, 'review');
    const result = await reviewAnimation(video, output, '2x2');
    expect(result.metadata.frameCount).toBe(3);
    const sourceHash = createHash('sha256').update(await readFile(video)).digest('hex');
    expect(result.metadata.sourceSha256).toBe(sourceHash);
    for (const frame of result.metadata.frames) {
      expect(frame.sha256).toBe(createHash('sha256').update(await readFile(join(output, frame.file))).digest('hex'));
    }
    expect(result.metadata.frames[0].sha256).not.toBe(result.metadata.frames[2].sha256);
    expect(result.metadata.frames.map(f => f.time)).toEqual([0, 0.5, 1]);
    expect((await readdir(join(output, 'frames'))).length).toBe(3);
    const last = await sharp(join(output, 'frames/000003.png')).removeAlpha().raw().toBuffer();
    expect([...last.subarray(0, 3)]).toEqual([255, 0, 0]);
    // Exercise the actual emitted page script, including downloaded range metadata.
    const html = await readFile(join(output, 'index.html'), 'utf8');
    const elements: Record<string, any> = {};
    const element = (id: string) => elements[id] ??= { value: id === 'cell' ? '-1' : '1', style: {}, append() {}, getBoundingClientRect: () => ({ left: 10, top: 20, width: 160, height: 160 }), getContext: () => ({ drawImage() {}, save() {}, restore() {}, beginPath() {}, arc() {}, stroke() {} }) };
    let exported: Blob | undefined;
    const timers: (() => void)[] = [];
    runInNewContext(html.match(/<script>([\s\S]+)<\/script>/)![1], {
      document: { getElementById: element, createElement: () => ({ click() {} }) },
      Image: class { async decode() {} }, Blob,
      URL: { createObjectURL: (blob: Blob) => { exported = blob; return 'blob:test'; }, revokeObjectURL() {} },
      setTimeout: (fn: () => void) => { timers.push(fn); return timers.length; }, clearTimeout() {},
    });
    element('last').onclick(); element('prev').onclick(); element('mark-end').onclick();
    element('mark-start').onclick(); // End and start cannot be the same.
    expect(element('range-error').textContent).toContain('at least two frames');
    element('save').onclick();
    const exportedData = JSON.parse(await exported!.text());
    expect(exportedData.sourceSha256).toBe(sourceHash);
    expect(exportedData.selectedRange).toMatchObject({ startFrame: 0, endFrameInclusive: 1, frameCount: 2, durationSeconds: 1 });
    expect(exportedData.selectedRange.frames.map((f: any) => f.file)).toEqual(['frames/000001.png', 'frames/000002.png']);
    expect(exportedData.status).toBe('unreviewed');
    element('last').onclick(); element('play').onclick(); // Outside range starts at loop start.
    expect(element('seek').value).toBe(0);
    element('reset-loop').onclick(); element('save').onclick();
    expect(JSON.parse(await exported!.text()).selectedRange.frameCount).toBe(3);
    element('foot-review').open = true;
    element('landmark').value = 'leftToe'; element('certainty').value = 'uncertain';
    element('first').onclick(); await new Promise(resolve => setImmediate(resolve));
    element('canvas').onclick({ clientX: 90, clientY: 60 }); // Grid overview must not assign a foot.
    expect(element('point-status').textContent).toContain('single grid cell');
    element('cell').value = '3'; element('cell').onchange(); await new Promise(resolve => setImmediate(resolve));
    element('canvas').onclick({ clientX: 90, clientY: 60 });
    await new Promise(resolve => setImmediate(resolve));
    element('save').onclick();
    expect(JSON.parse(await exported!.text()).landmarks).toEqual([{
      frame: 0, sourceFile: 'frames/000001.png', time: 0, cell: 3,
      landmark: 'leftToe', visibility: 'visible', certainty: 'uncertain', x: 24, y: 20,
    }]);
    element('landmark').value = 'rightAnkle'; element('hidden-point').onclick();
    await new Promise(resolve => setImmediate(resolve)); element('save').onclick();
    expect(JSON.parse(await exported!.text()).landmarks[1]).toMatchObject({ visibility: 'not-visible', certainty: null, x: null, y: null });
    element('next').onclick(); await new Promise(resolve => setImmediate(resolve)); element('hidden-point').onclick();
    await new Promise(resolve => setImmediate(resolve)); element('clear-point').onclick();
    await new Promise(resolve => setImmediate(resolve)); element('save').onclick();
    expect(JSON.parse(await exported!.text()).landmarks).toHaveLength(2); // Other-frame marks survive clearing.
    const before = await readFile(join(output, 'review.json'), 'utf8');
    await expect(reviewAnimation(video, output)).rejects.toThrow('already exists');
    expect(await readFile(join(output, 'review.json'), 'utf8')).toBe(before);
    await expect(reviewAnimation(video, join(root, 'bad'), '3x1')).rejects.toThrow('divide evenly');
    await expect(reviewAnimation(video, join(root, 'bad'), '0x1')).rejects.toThrow('Grid');
  } finally { await rm(root, { recursive: true, force: true }); }
});
