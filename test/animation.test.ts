import { describe, it, expect } from 'vitest';
import { mkdtemp, readFile, rm, writeFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { packAnimation, type AnimationLayout } from '../src/core/animation.js';
import { SPIN_ORDER } from '../src/core/extract.js';
import { createImage } from '../src/core/image.js';
import { packAnimationFile } from '../src/node/animation.js';
import { writePng, readImage } from '../src/node/io.js';

const layout: AnimationLayout = { cellWidth: 2, cellHeight: 3, columns: 4, directions: [...SPIN_ORDER].reverse(), fps: 12 };
function frame(time: number) {
  const im = createImage(8, 6);
  for (let i = 0; i < 8; i++) for (let y = 0; y < 3; y++) for (let x = 0; x < 2; x++) {
    im.data.set([i * 20, time * 30, x + y, 80 + i], (((Math.floor(i / 4) * 3 + y) * 8) + (i % 4) * 2 + x) * 4);
  }
  return im;
}

describe('animation atlas', () => {
  it('preserves all RGBA pixels in every direction and time, including translucent colors', () => {
    const inputs = [frame(0), frame(1), frame(2)];
    const { atlas, metadata } = packAnimation(inputs, layout);
    expect([atlas.width, atlas.height]).toEqual([6, 24]);
    for (const [row, direction] of SPIN_ORDER.entries()) {
      const source = layout.directions.indexOf(direction);
      for (let t = 0; t < 3; t++) for (let y = 0; y < 3; y++) for (let x = 0; x < 2; x++) {
        const offset = ((row * 3 + y) * atlas.width + t * 2 + x) * 4;
        expect([...atlas.data.slice(offset, offset + 4)]).toEqual([source * 20, t * 30, x + y, 80 + source]);
      }
      expect(metadata.animations[direction][2]).toEqual({ x: 4, y: row * 3, width: 2, height: 3, durationMs: 1000 / 12 });
    }
    expect(metadata.loop).toBe(false);
    expect(metadata.review.status).toBe('unreviewed');
  });
  it('rejects missing views, invalid time bases and mismatched geometry', () => {
    expect(() => packAnimation([frame(0), frame(1)], { ...layout, directions: Array(8).fill('S') })).toThrow(/each/);
    expect(() => packAnimation([frame(0), frame(1)], { ...layout, fps: 0 })).toThrow(/fps/);
    expect(() => packAnimation([frame(0), createImage(7, 6)], layout)).toThrow(/Frame 1/);
    expect(() => packAnimation([frame(0)], layout)).toThrow(/two/);
    expect(() => packAnimation([frame(0), frame(1)], { ...layout, cellWidth: 100000 })).toThrow(/size/);
  });
});

describe('offline animation packaging', () => {
  it('packs independent direction PNGs in explicit time order without mirroring or changing RGBA', async () => {
    const root = await mkdtemp(join(tmpdir(), 'sprute-views-test-'));
    try {
      const views: Record<string, string[]> = {};
      for (const [d, direction] of [...SPIN_ORDER].reverse().entries()) {
        views[direction] = [];
        for (let t = 0; t < 2; t++) {
          const file = `${direction}-${10 - t}.png`, image = createImage(2, 2);
          for (let pixel = 0; pixel < 4; pixel++) image.data.set([d * 25, t * 80, pixel * 20, 30 + pixel * 50], pixel * 4);
          await writePng(join(root, file), image); views[direction].push(file);
        }
      }
      const manifest = join(root, 'views.json'), output = join(root, 'packed');
      const data = { version: 1, cellWidth: 2, cellHeight: 2, fps: 24, views };
      await writeFile(manifest, JSON.stringify(data));
      await packAnimationFile(manifest, output);
      const atlas = await readImage(join(output, 'animation.png'));
      expect([atlas.width, atlas.height]).toEqual([4, 16]);
      for (const [row, direction] of SPIN_ORDER.entries()) for (let t = 0; t < 2; t++) {
        const original = await readImage(join(root, views[direction][t]));
        for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) {
          const i = ((row * 2 + y) * atlas.width + t * 2 + x) * 4, j = (y * 2 + x) * 4;
          expect(atlas.data.slice(i, i + 4)).toEqual(original.data.slice(j, j + 4));
        }
      }
      const metadata = JSON.parse(await readFile(join(output, 'animation.json'), 'utf8'));
      expect(metadata.source).toEqual({ views });
      expect(metadata.animations.NW[1].durationMs).toBe(1000 / 24);
      const registration = { sourceWidth: 2, sourceHeight: 2, targetHeight: 2, baseline: 3, centerX: 2, alphaThreshold: 1 };
      await writeFile(manifest, JSON.stringify({ ...data, cellWidth: 4, cellHeight: 4, registration }));
      const registeredPath = join(root, 'registered');
      await packAnimationFile(manifest, registeredPath);
      const registered = await readImage(join(registeredPath, 'animation.png'));
      const registeredMeta = JSON.parse(await readFile(join(registeredPath, 'animation.json'), 'utf8'));
      expect(Object.keys(registeredMeta.registration.transforms)).toEqual([...SPIN_ORDER]);
      for (const [row, direction] of SPIN_ORDER.entries()) for (let t = 0; t < 2; t++) {
        const original = await readImage(join(root, views[direction][t]));
        expect(registeredMeta.registration.transforms[direction]).toMatchObject({ scale: 1, translateX: 1, translateY: 1 });
        for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) {
          const i = ((row * 4 + y) * registered.width + t * 4 + x) * 4;
          const expected = x >= 1 && x < 3 && y >= 1 && y < 3 ? [...original.data.slice(((y-1)*2+x-1)*4, ((y-1)*2+x)*4)] : [0,0,0,0];
          expect([...registered.data.slice(i, i + 4)]).toEqual(expected);
        }
      }
      for (const invalid of [
        { ...data, views: { ...views, S: views.S.slice(1) } },
        { ...data, views: { ...views, N: undefined } },
        { ...data, frames: [] },
        { ...data, columns: 4 },
        { ...data, cellWidth: 3 },
        { ...data, registration: { ...registration, centerX: 0 } },
        { ...data, registration: { ...registration, sourceWidth: 300000 } },
      ]) {
        await writeFile(manifest, JSON.stringify(invalid));
        await expect(packAnimationFile(manifest, join(root, 'invalid'))).rejects.toThrow();
        expect(await readdir(root)).not.toContain('invalid');
      }
    } finally { await rm(root, { recursive: true, force: true }); }
  });
  it('resolves explicit frame order relative to the manifest, preserves alpha and never overwrites output', async () => {
    const root = await mkdtemp(join(tmpdir(), 'sprute-animation-test-'));
    try {
      await writePng(join(root, '10.png'), frame(1));
      await writePng(join(root, '2.png'), frame(0));
      const manifest = join(root, 'clip.json'), output = join(root, 'packed');
      await writeFile(manifest, JSON.stringify({ version: 1, ...layout, frames: ['10.png', '2.png'], loop: true }));
      await packAnimationFile(manifest, output);
      const atlas = await readImage(join(output, 'animation.png'));
      expect([...atlas.data.slice(0, 4)]).toEqual([140, 30, 0, 87]);
      const metadata = JSON.parse(await readFile(join(output, 'animation.json'), 'utf8'));
      expect(metadata.frameCount).toBe(2);
      expect(metadata.source.frames).toEqual(['10.png', '2.png']);
      expect(metadata.loop).toBe(true);
      expect(metadata.review.status).toBe('unreviewed');
      const before = await readFile(join(output, 'animation.png'));
      await expect(packAnimationFile(manifest, output)).rejects.toThrow(/already exists/);
      expect(await readFile(join(output, 'animation.png'))).toEqual(before);
      await writeFile(manifest, JSON.stringify({ version: 1, ...layout, frames: ['10.png', 'missing.png'] }));
      await expect(packAnimationFile(manifest, join(root, 'invalid'))).rejects.toThrow();
      expect(await readdir(root)).not.toContain('invalid');
    } finally { await rm(root, { recursive: true, force: true }); }
  });
});
