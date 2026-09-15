import { describe, it, expect } from 'vitest';
import { planFrameHolds } from '../src/core/animation-timing.js';

describe('drawing holds preserve source time', () => {
  it('keeps variable source durations instead of assuming a nominal FPS', () => {
    const source = Object.freeze([2000, 42, 42, 125, 80]);
    expect(planFrameHolds(source, 2)).toEqual([
      {sourceFrame: 0, durationMs: 2042}, {sourceFrame: 2, durationMs: 167}, {sourceFrame: 4, durationMs: 80},
    ]);
  });
  it('retains the final two ticks of a 32-frame cycle held on threes', () => {
    const out = planFrameHolds(Array(32).fill(1000 / 24), 3);
    expect(out).toHaveLength(11);
    expect(out.at(-1)).toEqual({sourceFrame: 30, durationMs: 2000 / 24});
    expect(out.reduce((s, f) => s + f.durationMs, 0)).toBeCloseTo(32000 / 24, 9);
  });
  it('supports authored holds while preserving coverage and time', () => {
    expect(planFrameHolds([10, 20, 30, 40, 50], [1, 3, 1])).toEqual([
      {sourceFrame: 0, durationMs: 10}, {sourceFrame: 1, durationMs: 90}, {sourceFrame: 4, durationMs: 50},
    ]);
  });
  it('rejects invalid or incomplete schedules and overflow', () => {
    for (const groups of [0, -1, 1.5, Infinity, [], [1], [3], [1, 0, 1]]) {
      expect(() => planFrameHolds([10, 20], groups)).toThrow();
    }
    for (const durations of [Array(2), [], [0], [-1], [NaN], [Infinity], [Number.MAX_VALUE, Number.MAX_VALUE]]) {
      expect(() => planFrameHolds(durations, 1)).toThrow();
    }
  });
});
