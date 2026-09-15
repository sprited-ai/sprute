import { readFile, realpath, stat } from 'node:fs/promises';
import { resolve, join, sep } from 'node:path';
import { SPIN_ORDER } from '../core/extract.js';

/** Expand exported cycles without sorting frames or inventing a shared gait phase. */
export async function readAnimationCycles(value: unknown, base: string, width: number, height: number) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== 8) throw new Error('cycles requires all eight direction folders');
  const folders = value as Record<string, unknown>;
  const views: Record<string, string[]> = {}, durations: Record<string, number[]> = {}, sources: Record<string, unknown> = {};
  const starts: number[] = [];
  const hashes: Record<string, (string | undefined)[]> = {};
  let referenceTotal = 0;
  for (const d of SPIN_ORDER) {
    if (typeof folders[d] !== 'string' || !(folders[d] as string).trim()) throw new Error(`Missing cycle folder: ${d}`);
    const root = await realpath(resolve(base, folders[d] as string));
    const manifest = join(root, 'cycle.json');
    if ((await stat(manifest)).size > 1024 * 1024) throw new Error('Cycle manifest exceeds 1 MiB');
    const cycle = JSON.parse(await readFile(manifest, 'utf8'));
    if (cycle.version !== 1 || cycle.columns !== 1 || cycle.rows !== 1 || cycle.width !== width || cycle.height !== height ||
        !Array.isArray(cycle.frames) || cycle.frameCount !== cycle.frames.length || cycle.frameCount < 2 || cycle.frameCount > 600) throw new Error(`Invalid single-view cycle geometry or frame count: ${d}`);
    let elapsed = 0;
    views[d] = []; durations[d] = []; hashes[d] = [];
    for (const [i, f] of cycle.frames.entries()) {
      if (f.mattingRuntime !== undefined && (!Number.isSafeInteger(f.mattingRuntime) || f.mattingRuntime < 0 ||
          !Array.isArray(cycle.processing?.runtimes) || f.mattingRuntime >= cycle.processing.runtimes.length)) throw new Error(`Invalid matting runtime reference: ${d}`);
      if (typeof f.file !== 'string' || !/^frames\/\d{6}\.png$/.test(f.file) ||
          !Number.isSafeInteger(f.sourceFrame) || f.sourceFrame < 0 || !Number.isFinite(f.time) || Math.abs(f.time - elapsed) > 1e-5 ||
          !Number.isFinite(f.duration) || f.duration <= 0) throw new Error(`Invalid cycle frame or timeline: ${d}`);
      if (d === 'S') starts.push(f.time);
      else if (Math.abs(f.time - starts[i]) > 1e-5) throw new Error(`Cycle timelines differ: ${d}; align timing before packing`);
      elapsed += f.duration;
      const path = await realpath(join(root, f.file));
      if (!path.startsWith(root + sep)) throw new Error(`Cycle frame escapes its folder: ${d}`);
      if (f.sha256 !== undefined && (typeof f.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(f.sha256))) throw new Error(`Invalid cycle frame hash: ${d}`);
      hashes[d].push(f.sha256);
      views[d].push(path); durations[d].push(f.duration * 1000);
    }
    if (!Number.isFinite(elapsed) || !Number.isFinite(cycle.durationSeconds) || Math.abs(elapsed - cycle.durationSeconds) > 1e-5) throw new Error(`Invalid cycle total duration: ${d}`);
    if (d === 'S') referenceTotal = elapsed;
    else if (Math.abs(elapsed - referenceTotal) > 1e-5) throw new Error(`Cycle timelines differ: ${d}; align timing before packing`);
    if (d !== 'S' && (durations[d].length !== durations.S.length || durations[d].some((n, i) => Math.abs(n - durations.S[i]) > .01))) throw new Error(`Cycle timelines differ: ${d}; align timing before packing`);
    sources[d] = { folder: folders[d], ...(cycle.processing === undefined ? {} : { processing: cycle.processing }),
      frames: cycle.frames.map((f: { file: string; sourceFrame: number; time: number; duration: number; mattingRuntime?: number }) => ({ file: f.file, sourceFrame: f.sourceFrame, time: f.time, duration: f.duration,
        ...(f.mattingRuntime === undefined ? {} : { mattingRuntime: f.mattingRuntime }) })) };
  }
  return { views, durations, sources, hashes };
}
