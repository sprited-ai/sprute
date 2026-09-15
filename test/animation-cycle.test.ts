import { test, expect } from 'vitest';
import { mkdtemp, mkdir, readFile, writeFile, rm, readdir, symlink } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import sharp from 'sharp';
import { createHash } from 'node:crypto';
import { extractCycle } from '../src/node/animation-cycle.js';

test('cycle selection preserves inclusive last frame, exact PNG alpha bytes and variable frame durations', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-cycle-test-'));
  try {
    const review = join(root, 'review'); await mkdir(join(review, 'frames'), { recursive: true });
    const durations = [0.1, 0.2, 0.35];
    const frames = [];
    for (let i = 0; i < 3; i++) {
      const file = `frames/${String(i + 1).padStart(6, '0')}.png`;
      await sharp({ create: { width: 4, height: 4, channels: 4, background: { r: i * 100, g: 20, b: 40, alpha: 0.5 } } }).png().toFile(join(review, file));
      frames.push({ file, time: i === 0 ? 0 : i === 1 ? 0.1 : 0.3, duration: durations[i] });
    }
    const metadata = { version: 1, width: 4, height: 4, rows: 1, columns: 1, frameCount: 3, source: 'clip.mp4', frames };
    await writeFile(join(review, 'review.json'), JSON.stringify(metadata));
    const out = join(root, 'cycle'), result = await extractCycle(review, 1, 2, out);
    expect(result.metadata.frames.map(f => [f.sourceFrame, f.time, f.duration])).toEqual([[1, 0, 0.2], [2, 0.2, 0.35]]);
    expect(result.metadata.reviewStatus).toBe('unreviewed');
    expect(result.metadata.frames[1].sha256).toBe(createHash('sha256').update(await readFile(join(out, 'frames/000002.png'))).digest('hex'));
    expect(await readFile(join(out, 'frames/000002.png'))).toEqual(await readFile(join(review, 'frames/000003.png')));
    expect(await readdir(join(out, 'frames'))).toHaveLength(2);
    await expect(extractCycle(review, 0, 2, out)).rejects.toThrow('already exists');
    await expect(extractCycle(review, 2, 2, join(root, 'bad'))).rejects.toThrow('at least two');
    await expect(extractCycle(review, 0, 3, join(root, 'bad'))).rejects.toThrow('at least two');
    frames[2].file = '../outside.png';
    await writeFile(join(review, 'review.json'), JSON.stringify(metadata));
    await expect(extractCycle(review, 1, 2, join(root, 'bad'))).rejects.toThrow('path or timing');
    frames[2].file = 'frames/000003.png';
    await writeFile(join(review, 'review.json'), JSON.stringify(metadata));
    await writeFile(join(root, 'outside.png'), await readFile(join(review, frames[2].file)));
    await rm(join(review, frames[2].file)); await symlink(join(root, 'outside.png'), join(review, frames[2].file));
    await expect(extractCycle(review, 1, 2, join(root, 'bad'))).rejects.toThrow('escapes');
    expect(await readdir(root)).not.toContain('bad');
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('cycle extraction rejects a valid PNG changed since review and preserves verified provenance', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-cycle-provenance-'));
  try {
    const review = join(root, 'review'); await mkdir(join(review, 'frames'), { recursive: true });
    const original = await sharp({ create: { width: 4, height: 4, channels: 4, background: '#123456' } }).png().toBuffer();
    const changed = await sharp({ create: { width: 4, height: 4, channels: 4, background: '#abcdef' } }).png().toBuffer();
    const digest = createHash('sha256').update(original).digest('hex');
    const frames = [1,2].map(i => ({ file: `frames/${String(i).padStart(6,'0')}.png`, sha256: digest, time: (i-1)/24, duration: 1/24 }));
    for (const f of frames) await writeFile(join(review, f.file), original);
    const metadata = { version: 1, width: 4, height: 4, rows: 1, columns: 1, frameCount: 2, sourceSha256: 'a'.repeat(64), frames };
    const bytes = Buffer.from(JSON.stringify(metadata));
    await writeFile(join(review, 'review.json'), bytes);
    await writeFile(join(review, frames[1].file), changed);
    await expect(extractCycle(review, 0, 1, join(root, 'bad'))).rejects.toThrow('differs from review hash');
    expect(await readdir(root)).not.toContain('bad');
    await writeFile(join(review, frames[1].file), original);
    const result = await extractCycle(review, 0, 1, join(root, 'good'));
    expect(result.metadata.source.videoSha256).toBe(metadata.sourceSha256);
    expect(result.metadata.source.reviewSha256).toBe(createHash('sha256').update(bytes).digest('hex'));
    expect(result.metadata.frames.map(f => f.sha256)).toEqual([digest, digest]);
  } finally { await rm(root, { recursive: true, force: true }); }
});
