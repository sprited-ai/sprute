import { createImage, type RawImage } from './image.js';
import { MAX_ANIMATION_PIXELS } from './animation.js';

export interface RegistrationOptions {
  width: number;
  height: number;
  targetHeight: number;
  baseline: number;
  centerX: number;
  alphaThreshold?: number;
}

function median(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b), mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** One transform for the entire view. Never aligns individual frames or gait phase. */
export function registerAnimationView(frames: RawImage[], options: RegistrationOptions) {
  const { width, height, targetHeight, baseline, centerX } = options;
  const alphaThreshold = options.alphaThreshold ?? 128;
  if (![width, height].every(n => Number.isSafeInteger(n) && n > 0 && n <= 16384) ||
      !Number.isFinite(targetHeight) || targetHeight <= 0 || targetHeight > height ||
      !Number.isFinite(baseline) || baseline < targetHeight || baseline > height ||
      !Number.isFinite(centerX) || centerX < 0 || centerX > width ||
      !Number.isInteger(alphaThreshold) || alphaThreshold < 1 || alphaThreshold > 255) throw new Error('Invalid animation registration geometry or alpha threshold');
  if (frames.length < 2 || width * height * frames.length > MAX_ANIMATION_PIXELS) throw new Error('Registration requires at least two frames within the pixel limit');
  let pixels = 0;
  const bounds = frames.map((im, index) => {
    if (!Number.isSafeInteger(im.width) || !Number.isSafeInteger(im.height) || im.width <= 0 || im.height <= 0 || im.data.length !== im.width * im.height * 4 ||
        im.width !== frames[0].width || im.height !== frames[0].height) throw new Error('Registration source frames must have matching RGBA dimensions');
    pixels += im.width * im.height;
    if (pixels > MAX_ANIMATION_PIXELS) throw new Error('Registration source view exceeds the pixel limit');
    let left = im.width, top = im.height, right = 0, bottom = 0;
    let fullLeft = im.width, fullTop = im.height, fullRight = 0, fullBottom = 0;
    for (let y = 0; y < im.height; y++) for (let x = 0; x < im.width; x++) {
      const a = im.data[(y * im.width + x) * 4 + 3];
      if (a > 0) { fullLeft = Math.min(fullLeft, x); fullTop = Math.min(fullTop, y); fullRight = Math.max(fullRight, x + 1); fullBottom = Math.max(fullBottom, y + 1); }
      if (a >= alphaThreshold) { left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x + 1); bottom = Math.max(bottom, y + 1); }
    }
    if (!right || !bottom) throw new Error(`Frame ${index} has no silhouette at the registration alpha threshold`);
    return { left, top, right, bottom, fullLeft, fullTop, fullRight, fullBottom };
  });
  const sourceMedian = { height: median(bounds.map(b => b.bottom - b.top)), bottom: median(bounds.map(b => b.bottom)), centerX: median(bounds.map(b => (b.left + b.right) / 2)) };
  const scale = targetHeight / sourceMedian.height, translateX = centerX - scale * sourceMedian.centerX, translateY = baseline - scale * sourceMedian.bottom;
  for (const [i, b] of bounds.entries()) {
    if (b.fullLeft * scale + translateX < -1e-7 || b.fullRight * scale + translateX > width + 1e-7 ||
        b.fullTop * scale + translateY < -1e-7 || b.fullBottom * scale + translateY > height + 1e-7) throw new Error(`Registration would clip nontransparent pixels in frame ${i}; use more canvas space or a smaller targetHeight`);
  }
  const output = frames.map(im => {
    const out = createImage(width, height);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      // Inverse pixel-center mapping, copying RGBA without alpha compositing.
      const sx = Math.floor((x + .5 - translateX) / scale), sy = Math.floor((y + .5 - translateY) / scale);
      if (sx < 0 || sx >= im.width || sy < 0 || sy >= im.height) continue;
      const start = (sy * im.width + sx) * 4;
      out.data.set(im.data.subarray(start, start + 4), (y * width + x) * 4);
    }
    return out;
  });
  return { frames: output, transform: { scale, translateX, translateY, sourceMedian, alphaThreshold, method: 'fixed-cycle-median-nearest' as const } };
}
