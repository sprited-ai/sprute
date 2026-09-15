import { readFile, copyFile, lstat, mkdir, mkdtemp, realpath, rename, rm, rmdir, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve, sep } from 'node:path';
import { parseArgs } from 'node:util';
import sharp from 'sharp';
import { createHash } from 'node:crypto';

const sha256 = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

/** Copy an explicitly selected inclusive range without changing pixels or timing. */
export async function extractCycle(reviewPath: string, start: number, end: number, outputPath: string) {
  const root = await realpath(reviewPath), output = resolve(outputPath);
  const reviewBytes = await readFile(join(root, 'review.json'));
  const data = JSON.parse(reviewBytes.toString('utf8'));
  if (data.sourceSha256 !== undefined && !/^[a-f0-9]{64}$/.test(data.sourceSha256)) throw new Error('Invalid review source hash.');
  if (data.version !== 1 || !Array.isArray(data.frames) || data.frameCount !== data.frames.length ||
      !Number.isInteger(data.frameCount) || data.frameCount < 2 || data.frameCount > 600 ||
      !Number.isInteger(data.width) || !Number.isInteger(data.height) || data.width <= 0 || data.height <= 0 ||
      data.width * data.height * data.frameCount > 128_000_000 ||
      !Number.isInteger(data.columns) || !Number.isInteger(data.rows) || data.columns < 1 || data.rows < 1 ||
      data.columns * data.rows > 8 || data.width % data.columns || data.height % data.rows) {
    throw new Error('Invalid animation review metadata.');
  }
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end >= data.frameCount) {
    throw new Error('Select at least two frames: 0 <= start < end < frameCount (end is inclusive).');
  }
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  const selected = data.frames.slice(start, end + 1);
  const files: string[] = [];
  const hashes: string[] = [];
  for (const frame of selected) {
    if (typeof frame.file !== 'string' || !/^frames\/\d{6}\.png$/.test(frame.file) ||
        !Number.isFinite(frame.time) || frame.time < 0 || !Number.isFinite(frame.duration) || frame.duration <= 0) {
      throw new Error('Invalid selected frame path or timing.');
    }
    const file = await realpath(join(root, frame.file));
    if (!file.startsWith(root + sep)) throw new Error('Selected frame escapes the review directory.');
    const bytes = await readFile(file), digest = sha256(bytes);
    if (frame.sha256 !== undefined && frame.sha256 !== digest) {
      throw new Error(`Selected frame differs from review hash: ${frame.file}`);
    }
    const info = await sharp(bytes).metadata();
    if (info.format !== 'png' || (info.pages ?? 1) !== 1 || info.width !== data.width || info.height !== data.height) {
      throw new Error('Selected PNG dimensions do not match the review.');
    }
    files.push(file);
    hashes.push(digest);
  }
  let elapsed = 0;
  const frames = selected.map((f: { duration: number }, i: number) => {
    const frame = { file: `frames/${String(i + 1).padStart(6, '0')}.png`, sha256: hashes[i], sourceFrame: start + i, time: elapsed, duration: f.duration };
    elapsed += f.duration;
    return frame;
  });
  if (!Number.isFinite(elapsed)) throw new Error('Selected duration is too large.');
  const metadata = { version: 1, source: { review: basename(root), video: typeof data.source === 'string' ? basename(data.source) : undefined,
    reviewSha256: sha256(reviewBytes), videoSha256: data.sourceSha256,
    startFrame: start, endFrameInclusive: end }, width: data.width, height: data.height, columns: data.columns, rows: data.rows,
    frameCount: frames.length, durationSeconds: elapsed, reviewStatus: 'unreviewed', frames };
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-cycle-'));
  try {
    await mkdir(join(temp, 'frames'));
    for (let i = 0; i < files.length; i++) {
      const target = join(temp, frames[i].file);
      await copyFile(files[i], target);
      if (sha256(await readFile(target)) !== hashes[i]) throw new Error('Selected frame changed during extraction.');
    }
    await writeFile(join(temp, 'cycle.json'), JSON.stringify(metadata, null, 2) + '\n');
    await mkdir(output);
    try { await rename(temp, output); } catch (e) { await rmdir(output).catch(() => {}); throw e; }
  } finally { await rm(temp, { recursive: true, force: true }); }
  return { output, metadata };
}

export async function runExtractCycle(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    start: { type: 'string' }, end: { type: 'string' }, output: { type: 'string', short: 'o' },
  } });
  if (positionals.length !== 1 || !values.output || !/^\d+$/.test(values.start ?? '') || !/^\d+$/.test(values.end ?? '')) {
    throw new Error('Usage: sprute extract-cycle review-folder --start 27 --end 39 -o new-folder');
  }
  const result = await extractCycle(positionals[0], Number(values.start), Number(values.end), values.output);
  console.log(`Copied ${result.metadata.frameCount} original frames to ${result.output}. Loop quality remains unreviewed.`);
}
