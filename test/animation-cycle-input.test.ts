import { it, expect } from 'vitest';
import { mkdtemp, mkdir, writeFile, readFile, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import { createHash } from 'node:crypto';
import { SPIN_ORDER } from '../src/core/extract.js';
import { packAnimationFile, packAnimationDirectory, runPackAnimation } from '../src/node/animation.js';

it('packs cycle folders in recorded order with exact RGBA and variable timing; rejects conflicting inputs and timelines', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-cycle-pack-'));
  try {
    const cycles: Record<string, string> = {};
    const durations = [.1, .25, .15];
    for (const [row, d] of SPIN_ORDER.entries()) {
      cycles[d] = d;
      await mkdir(join(root, d, 'frames'), { recursive: true });
      let time = 0;
      const frames = [];
      for (let i = 0; i < 3; i++) {
        const file = `frames/${String(3 - i).padStart(6, '0')}.png`;
        await sharp(Buffer.from([row * 20, i * 40, 79, 120]), { raw: { width: 1, height: 1, channels: 4 } }).png().toFile(join(root, d, file));
        frames.push({ file, sourceFrame: i + 7, time, duration: durations[i] }); time += durations[i];
      }
      await writeFile(join(root, d, 'cycle.json'), JSON.stringify({ version: 1, columns: 1, rows: 1, width: 1, height: 1, frameCount: 3, durationSeconds: .5, frames }));
    }
    const manifest = join(root, 'pack.json');
    const config = { version: 1, cellWidth: 1, cellHeight: 1, fps: 24, loop: false, cycles };
    await writeFile(manifest, JSON.stringify(config));
    await packAnimationFile(manifest, join(root, 'packed'));
    const pixels = await sharp(join(root, 'packed/animation.png')).raw().toBuffer();
    const meta = JSON.parse(await readFile(join(root, 'packed/animation.json'), 'utf8'));
    await runPackAnimation([root, '-o', join(root, 'direct')]);
    expect(await readFile(join(root, 'direct/animation.png'))).toEqual(await readFile(join(root, 'packed/animation.png')));
    const direct = JSON.parse(await readFile(join(root, 'direct/animation.json'), 'utf8'));
    expect(direct.animations).toEqual(meta.animations);
    expect(direct.fps).toBe(6); // Nominal average; individual durations remain authoritative.
    expect(direct.loop).toBe(false);
    await expect(runPackAnimation([manifest, '-o', join(root, 'ambiguous'), '--loop'])).rejects.toThrow(/only to cycle-folder/);
    await expect(runPackAnimation([root, '-o', join(root, 'invalid-size'), '--size', '1e2'])).rejects.toThrow(/integer/);
    await expect(packAnimationDirectory(root, join(root, 'direct'))).rejects.toThrow(/already exists/);
    expect(meta.durationMs).toBe(500);
    expect(meta.loop).toBe(false);
    expect(meta.review.status).toBe('unreviewed');
    for (const [row, d] of SPIN_ORDER.entries()) {
      expect(meta.animations[d].map((f: any) => f.durationMs)).toEqual([100, 250, 150]);
      expect(meta.source.cycles[d].frames.map((f: any) => f.sourceFrame)).toEqual([7, 8, 9]);
      for (let i = 0; i < 3; i++) expect([...pixels.subarray((row * 3 + i) * 4, (row * 3 + i + 1) * 4)]).toEqual([row * 20, i * 40, 79, 120]);
    }
    await runPackAnimation([root, '-o', join(root, 'held'), '--hold-frames', '2']);
    const held = JSON.parse(await readFile(join(root, 'held/animation.json'), 'utf8'));
    const heldPixels = await sharp(join(root, 'held/animation.png')).raw().toBuffer();
    expect(held.frameCount).toBe(2);
    expect(held.durationMs).toBe(500);
    for (const [row, d] of SPIN_ORDER.entries()) {
      expect(held.animations[d].map((f: any) => f.durationMs)).toEqual([350, 150]);
      expect(held.source.frameHolds[d].map((f: any) => f.sourceFrame)).toEqual([0, 2]);
      for (const [i, source] of [0, 2].entries()) expect([...heldPixels.subarray((row * 2 + i) * 4, (row * 2 + i + 1) * 4)]).toEqual([row * 20, source * 40, 79, 120]);
    }
    await expect(runPackAnimation([root, '-o', join(root, 'invalid-hold'), '--hold-frames', '0'])).rejects.toThrow(/positive integer/);
    await expect(packAnimationDirectory(root, join(root, 'single-hold'), { holdFrames: 3 })).rejects.toThrow(/at least two frames/);
    await expect(readFile(join(root, 'single-hold/animation.png'))).rejects.toMatchObject({ code: 'ENOENT' });
    await writeFile(manifest, JSON.stringify({ ...config, views: {} }));
    await expect(packAnimationFile(manifest, join(root, 'mixed'))).rejects.toThrow(/cannot be combined/);
    await writeFile(manifest, JSON.stringify(config));
    const swFile = join(root, 'SW/cycle.json'), sw = JSON.parse(await readFile(swFile, 'utf8'));
    sw.frames[0].duration = .2; sw.frames[1].duration = .15; sw.frames[1].time = .2;
    await writeFile(swFile, JSON.stringify(sw));
    await expect(packAnimationFile(manifest, join(root, 'timing'))).rejects.toThrow(/timelines differ/);
    await expect(packAnimationDirectory(root, join(root, 'direct-timing'))).rejects.toThrow(/timelines differ/);
    sw.frames[0].duration = .1; sw.frames[1].duration = .25; sw.frames[1].time = .1;
    const original = await readFile(join(root, 'SW/frames/000003.png'));
    sw.frames[0].sha256 = createHash('sha256').update(original).digest('hex');
    await writeFile(swFile, JSON.stringify(sw));
    await sharp(Buffer.from([1, 2, 3, 255]), { raw: { width: 1, height: 1, channels: 4 } }).png().toFile(join(root, 'SW/frames/000003.png'));
    await expect(packAnimationFile(manifest, join(root, 'changed'))).rejects.toThrow(/hash mismatch/i);
    await expect(packAnimationDirectory(root, join(root, 'direct-changed'))).rejects.toThrow(/hash mismatch/i);
    await expect(readFile(join(root, 'changed/animation.png'))).rejects.toMatchObject({ code: 'ENOENT' });
    await writeFile(join(root, 'SW/frames/000003.png'), original);
    await packAnimationFile(manifest, join(root, 'verified'));
    await rm(join(root, 'SW/frames/000003.png'));
    await symlink(join(root, 'S/frames/000003.png'), join(root, 'SW/frames/000003.png'));
    await expect(packAnimationFile(manifest, join(root, 'escape'))).rejects.toThrow(/escapes/);
  } finally { await rm(root, { recursive: true, force: true }); }
});
