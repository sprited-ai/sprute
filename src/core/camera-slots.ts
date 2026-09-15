/** Camera positions, not verified character-facing labels. */
export const CAMERA_AZIMUTHS = [0, 45, 90, 135, 180, 225, 270, 315] as const;
const views = ['front view', 'front-right quarter view', 'right side view',
  'back-right quarter view', 'back view', 'back-left quarter view',
  'left side view', 'front-left quarter view'] as const;

/** Nearest 45 degrees; exact halfway ties advance clockwise. */
export function snapCameraAzimuth(degrees: number) {
  if (!Number.isFinite(degrees)) throw new Error('Camera azimuth must be finite');
  const wrapped = ((degrees % 360) + 360) % 360;
  return CAMERA_AZIMUTHS[Math.floor((wrapped + 22.5) / 45) % 8];
}

/** fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA's documented prompt format.
 * Every slot must use the same original source, not the previous slot's output.
 * Camera position and actual sprite facing must be compared after generation.
 */
export function cameraSlotPlan(source: string) {
  if (!source.trim()) throw new Error('Camera plan requires a source image');
  return CAMERA_AZIMUTHS.map((azimuth, i) => ({
    source, azimuth, elevation: 0, distance: 'medium shot' as const,
    prompt: `<sks> ${views[i]} eye-level shot medium shot`,
    reviewStatus: 'unreviewed' as const,
  }));
}
