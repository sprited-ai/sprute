import { SPIN_ORDER, type Direction } from './extract.js';
import { createImage, type RawImage } from './image.js';

export interface AnimationLayout {
  cellWidth: number;
  cellHeight: number;
  columns: number;
  /** Direction of each source cell, in reading order. All eight are required. */
  directions: Direction[];
  fps: number;
  /** Playback preference, not a claim that the seam was validated. */
  loop?: boolean;
}

export const MAX_ANIMATION_PIXELS = 16_777_216;

export function validateAnimationLayout(layout: AnimationLayout, count: number): void {
  for (const key of ['cellWidth', 'cellHeight', 'columns'] as const) {
    if (!Number.isSafeInteger(layout[key]) || layout[key] <= 0) throw new Error(`${key} must be a positive integer`);
  }
  if (!Number.isSafeInteger(count) || count < 2) throw new Error('An animation needs at least two frames');
  if (![1, 2, 4, 8].includes(layout.columns)) throw new Error('columns must be 1, 2, 4, or 8');
  if (!Array.isArray(layout.directions) || layout.directions.length !== 8 ||
      new Set(layout.directions).size !== 8 || layout.directions.some(d => !SPIN_ORDER.includes(d))) {
    throw new Error('directions must contain each of S, SE, E, NE, N, NW, W, SW exactly once');
  }
  if (!Number.isFinite(layout.fps) || layout.fps <= 0 || layout.fps > 120) throw new Error('fps must be greater than 0 and at most 120');
  if (layout.loop !== undefined && typeof layout.loop !== 'boolean') throw new Error('loop must be a boolean');
  const pixels = layout.cellWidth * layout.cellHeight * 8 * count;
  if (!Number.isSafeInteger(pixels) || pixels > MAX_ANIMATION_PIXELS || layout.cellWidth * count > 16384 || layout.cellHeight * 8 > 16384) {
    throw new Error('Animation atlas exceeds the supported size; use fewer frames or smaller cells');
  }
}

/** Packs time across columns and canonical facing down rows. Copies RGBA bytes
 * exactly: compositing semi-transparent wings here would corrupt their colors. */
export function packAnimation(frames: RawImage[], layout: AnimationLayout) {
  validateAnimationLayout(layout, frames.length);
  const { cellWidth: cw, cellHeight: ch, columns, fps } = layout;
  const width = columns * cw, height = 8 / columns * ch;
  for (const [i, frame] of frames.entries()) {
    if (frame.width !== width || frame.height !== height || frame.data.length !== width * height * 4) {
      throw new Error(`Frame ${i} must be an exact ${width}x${height} RGBA grid`);
    }
  }
  const atlas = createImage(cw * frames.length, ch * 8);
  for (const [row, direction] of SPIN_ORDER.entries()) {
    const source = layout.directions.indexOf(direction);
    const x = source % columns * cw, y = Math.floor(source / columns) * ch;
    for (const [time, frame] of frames.entries()) {
      for (let line = 0; line < ch; line++) {
        const start = ((y + line) * width + x) * 4;
        atlas.data.set(frame.data.subarray(start, start + cw * 4), ((row * ch + line) * atlas.width + time * cw) * 4);
      }
    }
  }
  const metadata = {
    version: 1,
    image: 'animation.png',
    cellWidth: cw, cellHeight: ch,
    fps, frameCount: frames.length, durationMs: frames.length * 1000 / fps,
    loop: layout.loop ?? false,
    review: { status: 'unreviewed', note: 'Packing does not validate anatomy, facing, foot contact, or loop quality.' },
    directions: [...SPIN_ORDER],
    animations: Object.fromEntries(SPIN_ORDER.map((d, row) => [d, frames.map((_, i) => ({
      x: i * cw, y: row * ch, width: cw, height: ch, durationMs: 1000 / fps,
    }))])),
  };
  return { atlas, metadata };
}
