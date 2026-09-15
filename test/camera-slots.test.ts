import { test, expect } from 'vitest';
import { cameraSlotPlan, snapCameraAzimuth } from '../src/core/camera-slots.js';

test('camera snapping wraps negative/full rotations and has deterministic ties', () => {
  expect([-45, 360, 721, 22.49, 22.5, 337.5].map(snapCameraAzimuth)).toEqual([315, 0, 0, 0, 45, 0]);
  expect(() => snapCameraAzimuth(NaN)).toThrow('finite');
});

test('eight distinct camera prompts retain one source and await facing review', () => {
  const plan = cameraSlotPlan('hero.png');
  expect(plan.map(x => x.azimuth)).toEqual([0,45,90,135,180,225,270,315]);
  expect(new Set(plan.map(x => x.prompt)).size).toBe(8);
  expect(plan.every(x => x.source === 'hero.png' && x.reviewStatus === 'unreviewed')).toBe(true);
  expect(plan[4].prompt).toBe('<sks> back view eye-level shot medium shot');
});
