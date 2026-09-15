import { readFile, lstat, realpath, mkdir, mkdtemp, rename, rmdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve, sep } from 'node:path';
import { createHash } from 'node:crypto';
import { parseArgs } from 'node:util';
import sharp from 'sharp';
import { decodeImage, encodePng } from './io.js';
import { toonoutMattingWithProvenance } from './toonout.js';
import { SPIN_ORDER } from '../core/extract.js';
import type { ToonoutProvenance } from './matting-local.js';

/** Matte each original frame independently, retaining its explicit source index and timing. */
export async function matteAnimationCycle(cyclePath: string, outputPath: string) {
  const root = await realpath(cyclePath), output = resolve(outputPath);
  const data = JSON.parse(await readFile(join(root, 'cycle.json'), 'utf8'));
  if (data.version !== 1 || data.columns !== 1 || data.rows !== 1 || !Array.isArray(data.frames) ||
      data.frameCount !== data.frames.length || data.frameCount < 2 || data.frameCount > 600 ||
      !Number.isSafeInteger(data.width) || !Number.isSafeInteger(data.height) || data.width < 1 || data.height < 1 ||
      data.width * data.height * data.frameCount > 128_000_000) throw new Error('Expected a single-view cycle.json within the 600-frame / 128-million-pixel limits');
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  const files: string[] = [], frames: { file: string; sourceFrame: number; time: number; duration: number; sourceSha256: string; sha256: string; mattingRuntime?: number }[] = [];
  const runtimes: ToonoutProvenance[] = [];
  let elapsed = 0;
  for (const [i, f] of data.frames.entries()) {
    if (typeof f.file !== 'string' || !/^frames\/\d{6}\.png$/.test(f.file) ||
        !Number.isSafeInteger(f.sourceFrame) || f.sourceFrame < 0 || !Number.isFinite(f.time) || f.time < 0 ||
        Math.abs(f.time - elapsed) > .00001 || !Number.isFinite(f.duration) || f.duration <= 0) throw new Error('Invalid cycle frame path, source index or timeline');
    elapsed += f.duration;
    if (!Number.isFinite(elapsed)) throw new Error('Invalid cycle duration');
    const file = await realpath(join(root, f.file));
    if (!file.startsWith(root + sep)) throw new Error('Cycle frame escapes its source directory');
    const bytes = await readFile(file);
    const digest = createHash('sha256').update(bytes).digest('hex');
    if (f.sha256 !== undefined && f.sha256 !== digest) throw new Error(`Cycle frame hash mismatch: ${f.file}`);
    const info = await sharp(bytes).metadata();
    if (info.format !== 'png' || (info.pages ?? 1) !== 1 || info.width !== data.width || info.height !== data.height) throw new Error('Cycle PNG geometry mismatch');
    files.push(file);
    frames.push({ file: `frames/${String(i + 1).padStart(6, '0')}.png`, sourceFrame: f.sourceFrame, time: f.time, duration: f.duration, sourceSha256: digest, sha256: '' });
  }
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-matte-'));
  try {
    await mkdir(join(temp, 'frames'));
    for (let i = 0; i < files.length; i++) {
      const bytes = await readFile(files[i]);
      if (createHash('sha256').update(bytes).digest('hex') !== frames[i].sourceSha256) throw new Error('Cycle frame changed during matting');
      const { images: [image], provenance } = await toonoutMattingWithProvenance([await decodeImage(bytes)]);
      if (provenance) {
        let index = runtimes.findIndex(p => JSON.stringify(p) === JSON.stringify(provenance));
        if (index < 0) { index = runtimes.length; runtimes.push(provenance); }
        frames[i].mattingRuntime = index;
      }
      if (!image || image.width !== data.width || image.height !== data.height || image.data.length !== data.width * data.height * 4) throw new Error('Matting returned invalid frame geometry');
      const png = await encodePng(image);
      await writeFile(join(temp, frames[i].file), png);
      frames[i].sha256 = createHash('sha256').update(png).digest('hex');
      console.log(`Matted ${i + 1}/${files.length}`);
    }
    const metadata = { version: 1, width: data.width, height: data.height, columns: 1, rows: 1, frameCount: frames.length, durationSeconds: elapsed, reviewStatus: 'unreviewed', processing: { method: 'toonout', runtimes,
      imageRuntime: { sharp: sharp.versions.sharp, vips: sharp.versions.vips },
      note: 'Independent local frame matting; temporal edge stability and character details require visual review. Runtime provenance identifies execution, not cross-platform numerical equivalence.' }, frames };
    await writeFile(join(temp, 'cycle.json'), JSON.stringify(metadata, null, 2) + '\n');
    await mkdir(output);
    try { await rename(temp, output); } catch (e) { await rmdir(output).catch(() => {}); throw e; }
    return { output, metadata };
  } finally { await rm(temp, { recursive: true, force: true }); }
}

/** Preserve completed directions and a failure receipt; never silently rerun output. */
export async function matteAnimationDirectory(inputPath: string, outputPath: string) {
  const input = await realpath(inputPath), output = resolve(outputPath);
  // Catch absent directions before starting model work.
  for (const direction of SPIN_ORDER) {
    const metadata = JSON.parse(await readFile(join(input, direction, 'cycle.json'), 'utf8'));
    if (metadata.version !== 1 || !Array.isArray(metadata.frames) || metadata.frames.length < 2) {
      throw new Error(`Invalid cycle for ${direction}`);
    }
  }
  await mkdir(dirname(output), { recursive: true });
  await mkdir(output); // Exclusive: existing or interrupted output requires inspection.
  const state: { status: string; input: string; completed: string[]; active: string | null; error?: string } = {
    status: 'running', input, completed: [], active: null,
  };
  const save = async () => {
    await writeFile(join(output, 'matting-state.json.tmp'), JSON.stringify(state, null, 2) + '\n');
    await rename(join(output, 'matting-state.json.tmp'), join(output, 'matting-state.json'));
  };
  try {
    await save();
    for (const direction of SPIN_ORDER) {
      state.active = direction; await save();
      await matteAnimationCycle(join(input, direction), join(output, direction));
      state.completed.push(direction); state.active = null; await save();
    }
    state.status = 'complete'; await save();
    return { output, state };
  } catch (error) {
    state.status = 'failed'; state.error = error instanceof Error ? error.message : String(error);
    await save().catch(() => {});
    throw error;
  }
}

export async function runMatteAnimation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { output: { type: 'string', short: 'o' }, 'all-directions': { type: 'boolean' } } });
  if (positionals.length !== 1 || !values.output) throw new Error('Usage: sprute matte-animation cycle-folder -o new-folder');
  if (values['all-directions']) {
    const result = await matteAnimationDirectory(positionals[0], values.output);
    console.log(`Saved eight transparent candidate cycles to ${result.output}. Visual review required.`);
    return;
  }
  const result = await matteAnimationCycle(positionals[0], values.output);
  console.log(`Saved ${result.metadata.frameCount} transparent candidate frames to ${result.output}. Visual review required.`);
}
