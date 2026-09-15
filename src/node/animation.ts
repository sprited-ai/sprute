import { readFile, mkdir, mkdtemp, rename, rm, rmdir, lstat, stat } from 'node:fs/promises';
import { dirname, resolve, join } from 'node:path';
import { parseArgs } from 'node:util';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { packAnimation, validateAnimationLayout, MAX_ANIMATION_PIXELS, type AnimationLayout } from '../core/animation.js';
import { planFrameHolds } from '../core/animation-timing.js';
import { registerAnimationView } from '../core/animation-registration.js';
import { readImage, decodeImage, writePng, writeBytes } from './io.js';
import { SPIN_ORDER } from '../core/extract.js';
import { createImage, type RawImage } from '../core/image.js';
import { readAnimationCycles } from './animation-cycle-input.js';

/** Explicit frame order prevents filename sorting from silently changing gait. */
export async function packAnimationFile(manifestPath: string, outputPath: string) {
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  return packAnimationManifest(manifest, dirname(resolve(manifestPath)), outputPath);
}

/** Conventional direction folders remove the need to hand-write a packing manifest. */
export async function packAnimationDirectory(inputPath: string, outputPath: string, options: { size?: number; loop?: boolean; holdFrames?: number } = {}) {
  const base = resolve(inputPath);
  const firstPath = join(base, 'S', 'cycle.json');
  if ((await stat(firstPath)).size > 1024 * 1024) throw new Error('Cycle manifest exceeds 1 MiB');
  const first = JSON.parse(await readFile(firstPath, 'utf8'));
  if (![first.width, first.height, first.frameCount].every(n => Number.isSafeInteger(n) && n > 0) ||
      !Number.isFinite(first.durationSeconds) || first.durationSeconds <= 0) throw new Error('Invalid S cycle geometry or duration');
  const size = options.size;
  if (size !== undefined && (!Number.isSafeInteger(size) || size < 4 || size > 2048)) throw new Error('--size must be an integer from 4 to 2048');
  return packAnimationManifest({
    version: 1, cellWidth: size ?? first.width, cellHeight: size ?? first.height,
    fps: first.frameCount / first.durationSeconds, loop: options.loop ?? false,
    cycles: Object.fromEntries(SPIN_ORDER.map(d => [d, d])),
    holdFrames: options.holdFrames,
    ...(size === undefined ? {} : { registration: {
      sourceWidth: first.width, sourceHeight: first.height,
      targetHeight: Math.round(size * .7), baseline: Math.round(size * .85), centerX: size / 2,
      alphaThreshold: 128,
    } }),
  }, base, outputPath);
}

async function packAnimationManifest(manifest: any, base: string, outputPath: string) {
  if (manifest?.version !== 1) throw new Error('Animation manifest requires version: 1');
  let cycles: Awaited<ReturnType<typeof readAnimationCycles>> | undefined;
  if (manifest.cycles !== undefined) {
    if (['views', 'frames', 'columns', 'directions'].some(key => manifest[key] !== undefined)) throw new Error('cycles cannot be combined with views, frames, columns or directions');
    cycles = await readAnimationCycles(manifest.cycles, base, manifest.registration?.sourceWidth ?? manifest.cellWidth, manifest.registration?.sourceHeight ?? manifest.cellHeight);
    manifest.views = cycles.views;
  }
  const separate = manifest.views !== undefined;
  const registration = manifest.registration;
  if (registration !== undefined && (!separate || !registration || typeof registration !== 'object' || Array.isArray(registration))) throw new Error('registration requires separate views and an options object');
  const pathsValid = (paths: unknown): paths is string[] => Array.isArray(paths) && paths.every(p => typeof p === 'string' && !!p.trim());
  let layout: AnimationLayout, count: number;
  let paths: string[], source: object;
  if (separate) {
    if (manifest.frames !== undefined || manifest.columns !== undefined || manifest.directions !== undefined) throw new Error('views cannot be combined with frames, columns or directions');
    if (!manifest.views || typeof manifest.views !== 'object' || Array.isArray(manifest.views) ||
        Object.keys(manifest.views).length !== 8 || SPIN_ORDER.some(d => !pathsValid(manifest.views[d]))) {
      throw new Error('views must contain ordered PNG paths for each of S, SE, E, NE, N, NW, W, SW');
    }
    count = manifest.views.S.length;
    if (SPIN_ORDER.some(d => manifest.views[d].length !== count)) throw new Error('Every direction must have the same frame count; align timing explicitly before packing');
    layout = { cellWidth: manifest.cellWidth, cellHeight: manifest.cellHeight, fps: manifest.fps, loop: manifest.loop, columns: 1, directions: [...SPIN_ORDER] };
    paths = SPIN_ORDER.flatMap(d => manifest.views[d]);
    source = cycles ? { cycles: cycles.sources } : { views: manifest.views };
  } else {
    if (!pathsValid(manifest.frames)) throw new Error('frames must be an ordered array of image file paths');
    layout = manifest; count = manifest.frames.length; paths = manifest.frames;
    source = { frames: manifest.frames, directions: layout.directions, columns: layout.columns };
  }
  validateAnimationLayout(layout, count);
  const holds = Object.fromEntries(SPIN_ORDER.map(d => [d, planFrameHolds(
    cycles?.durations[d] ?? Array(count).fill(1000 / layout.fps), manifest.holdFrames ?? 1,
  )]));
  const selectedCount = holds.S.length;
  validateAnimationLayout(layout, selectedCount);
  if (registration && (![registration.sourceWidth, registration.sourceHeight].every(n => Number.isSafeInteger(n) && n > 0) ||
      registration.sourceWidth * registration.sourceHeight * count > MAX_ANIMATION_PIXELS)) throw new Error('Registration requires valid sourceWidth/sourceHeight within the per-view pixel limit');
  const output = resolve(outputPath);
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const files = paths.map(p => resolve(base, p));
  const expectedHashes = cycles ? SPIN_ORDER.flatMap(d => cycles.hashes[d]) : undefined;
  const readFrame = async (index: number): Promise<RawImage> => {
    if (!cycles) return readImage(files[index]);
    // Hash the exact buffer decoded, rather than verifying a path then reopening it.
    const bytes = await readFile(files[index]);
    const expected = expectedHashes![index];
    if (expected !== undefined && createHash('sha256').update(bytes).digest('hex') !== expected) throw new Error(`Cycle frame hash mismatch: ${files[index]}`);
    const image = await decodeImage(bytes);
    const width = registration ? registration.sourceWidth : layout.cellWidth;
    const height = registration ? registration.sourceHeight : layout.cellHeight;
    if (image.width !== width || image.height !== height) throw new Error(`Cycle frame dimensions changed: ${files[index]}`);
    return image;
  };
  // Validate dimensions before decoding the entire clip or creating any output.
  for (const file of files) {
    const info = await sharp(file).metadata();
    const width = registration ? registration.sourceWidth : separate ? layout.cellWidth : layout.cellWidth * layout.columns;
    const height = registration ? registration.sourceHeight : separate ? layout.cellHeight : layout.cellHeight * 8 / layout.columns;
    if ((info.pages ?? 1) !== 1 || info.width !== width || info.height !== height || (separate && info.format !== 'png')) {
      throw new Error(`Expected a single ${width}x${height}${separate ? ' PNG direction frame' : ' eight-cell grid'} in ${file}`);
    }
  }
  const frames: RawImage[] = [];
  const transforms: Record<string, unknown> = {};
  if (registration) {
    for (let t = 0; t < count; t++) frames.push(createImage(layout.cellWidth, layout.cellHeight * 8));
    for (const [row, direction] of SPIN_ORDER.entries()) {
      const inputs: RawImage[] = [];
      for (let t = 0; t < count; t++) inputs.push(await readFrame(row * count + t));
      const registered = registerAnimationView(inputs, { width: layout.cellWidth, height: layout.cellHeight, targetHeight: registration.targetHeight, baseline: registration.baseline, centerX: registration.centerX, alphaThreshold: registration.alphaThreshold });
      transforms[direction] = registered.transform;
      for (let t = 0; t < count; t++) frames[t].data.set(registered.frames[t].data, row * layout.cellWidth * layout.cellHeight * 4);
    }
  } else if (separate) {
    for (let t = 0; t < count; t++) {
      const grid = createImage(layout.cellWidth, layout.cellHeight * 8);
      for (let row = 0; row < 8; row++) {
        const image = await readFrame(row * count + t);
        grid.data.set(image.data, row * layout.cellWidth * layout.cellHeight * 4);
      }
      frames.push(grid);
    }
  } else for (const file of files) frames.push(await readImage(file));
  const { atlas, metadata } = packAnimation(holds.S.map(f => frames[f.sourceFrame]), layout);
  for (const d of SPIN_ORDER) for (let i = 0; i < selectedCount; i++) metadata.animations[d][i].durationMs = holds[d][i].durationMs;
  metadata.durationMs = holds.S.reduce((sum, f) => sum + f.durationMs, 0);
  if (manifest.holdFrames !== undefined) source = { ...source, frameHolds: holds };
  await mkdir(dirname(output), { recursive: true });
  const temporary = await mkdtemp(join(dirname(output), '.sprute-animation-'));
  try {
    await writePng(join(temporary, 'animation.png'), atlas);
    writeBytes(join(temporary, 'animation.json'), Buffer.from(JSON.stringify({ ...metadata,
      source,
      ...(registration ? { registration: { options: registration, transforms, note: 'Silhouette framing only; does not align anatomical gait phase or detect ground contact.' } } : {}),
    }, null, 2) + '\n'));
    // mkdir reserves the destination without overwriting an existing directory.
    await mkdir(output);
    try { await rename(temporary, output); }
    catch (error) { await rmdir(output).catch(() => {}); throw error; }
  } finally { await rm(temporary, { recursive: true, force: true }); }
  return { output, metadata };
}

export async function runPackAnimation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    output: { type: 'string', short: 'o' }, size: { type: 'string' }, loop: { type: 'boolean' }, 'hold-frames': { type: 'string' },
  } });
  if (positionals.length !== 1 || !values.output) throw new Error('Usage: sprute pack-animation frames.json|cycles-folder --output new-folder [--size 128] [--loop] [--hold-frames 2]');
  const input = resolve(positionals[0]), directory = (await stat(input)).isDirectory();
  if (!directory && (values.size !== undefined || values.loop !== undefined || values['hold-frames'] !== undefined)) throw new Error('--size, --loop and --hold-frames apply only to cycle-folder input; edit the JSON manifest for file input');
  if (values.size !== undefined && !/^\d+$/.test(values.size)) throw new Error('--size must be an integer from 4 to 2048');
  if (values['hold-frames'] !== undefined && !/^[1-9]\d*$/.test(values['hold-frames'])) throw new Error('--hold-frames must be a positive integer');
  const result = directory
    ? await packAnimationDirectory(input, values.output, { size: values.size === undefined ? undefined : Number(values.size), loop: values.loop, holdFrames: values['hold-frames'] === undefined ? undefined : Number(values['hold-frames']) })
    : await packAnimationFile(input, values.output);
  console.log(`Packed ${result.metadata.frameCount} frames for each of 8 directions into ${result.output}`);
  console.log('Visual review still required: anatomy, facing, foot contact, and loop seam.');
}
