export interface FrameHold {
  sourceFrame: number;
  durationMs: number;
}

/** Hold the first drawing in each consecutive group for the group's total time.
 * Does not resample pixels, change cycle length, or select anatomical key poses.
 * A short final group is retained. Explicit groups must cover the entire input.
 */
export function planFrameHolds(durationsMs: readonly number[], groups: number | readonly number[]): FrameHold[] {
  if (!Array.isArray(durationsMs) || durationsMs.length === 0 ||
      Array.from(durationsMs).some(d => !Number.isFinite(d) || d <= 0) ||
      !Number.isFinite(durationsMs.reduce((sum, d) => sum + d, 0))) {
    throw new Error('Expected nonempty finite positive frame durations');
  }
  const validCount = (n: number) => Number.isSafeInteger(n) && n > 0;
  let counts: readonly number[];
  if (typeof groups === 'number') {
    if (!validCount(groups)) throw new Error('Frame hold size must be a positive integer');
    const generated: number[] = [];
    for (let i = 0; i < durationsMs.length; i += groups) generated.push(Math.min(groups, durationsMs.length - i));
    counts = generated;
  } else {
    if (!Array.isArray(groups) || groups.length === 0 || Array.from(groups).some(n => !validCount(n)) ||
        groups.reduce((sum, n) => sum + n, 0) !== durationsMs.length) {
      throw new Error('Explicit frame holds must cover every source frame exactly');
    }
    counts = groups;
  }
  let cursor = 0;
  return counts.map(count => {
    const sourceFrame = cursor;
    let durationMs = 0;
    for (let i = 0; i < count; i++) durationMs += durationsMs[cursor++];
    return { sourceFrame, durationMs };
  });
}
