import { test, expect } from 'vitest';
import { createImage } from '../src/core/image.js';
import { registerAnimationView } from '../src/core/animation-registration.js';

function movingFrame(dy: number) {
  const im = createImage(6, 6);
  for (let y = 1; y < 3; y++) for (let x = 2; x < 4; x++) im.data.set([20 + x, 30 + y, 70, 200], ((y + dy) * 6 + x) * 4);
  im.data.set([90, 110, 130, 10], ((2 + dy) * 6 + 1) * 4);
  return im;
}
const options = { width: 8, height: 8, targetHeight: 2, baseline: 4.5, centerX: 4 };

test('one fixed transform preserves motion, source bytes and translucent RGB', () => {
  const input = [movingFrame(0), movingFrame(1)], originals = input.map(im => im.data.slice());
  const result = registerAnimationView(input, options);
  expect(result.transform).toMatchObject({ scale: 1, translateX: 1, translateY: 1 });
  for (let t = 0; t < 2; t++) {
    const expected = createImage(8, 8);
    for (let y = 0; y < 6; y++) for (let x = 0; x < 6; x++) expected.data.set(input[t].data.subarray((y * 6 + x) * 4, (y * 6 + x + 1) * 4), ((y + 1) * 8 + x + 1) * 4);
    expect(result.frames[t].data).toEqual(expected.data);
    expect(input[t].data).toEqual(originals[t]);
  }
  expect(result.frames[0].data).not.toEqual(result.frames[1].data);
});

test('rejects clipping even for alpha below the measurement threshold', () => {
  const im = movingFrame(0);
  im.data.set([100, 120, 130, 1], 0);
  expect(() => registerAnimationView([im, movingFrame(1)], { ...options, centerX: 2 })).toThrow('clip');
});

test('rejects absent silhouettes, invalid geometry, mismatched sizes and oversized input', () => {
  expect(() => registerAnimationView([createImage(6,6), movingFrame(0)], options)).toThrow('no silhouette');
  expect(() => registerAnimationView([movingFrame(0), movingFrame(1)], { ...options, targetHeight: NaN })).toThrow('Invalid');
  expect(() => registerAnimationView([movingFrame(0), movingFrame(1)], { ...options, alphaThreshold: 0 })).toThrow('Invalid');
  expect(() => registerAnimationView([movingFrame(0), createImage(5,6)], options)).toThrow('matching');
  expect(() => registerAnimationView([movingFrame(0)], options)).toThrow('two');
  expect(() => registerAnimationView([movingFrame(0), movingFrame(1)], { ...options, width: 16000, height: 16000 })).toThrow('pixel limit');
});
