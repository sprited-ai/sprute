import { createHash } from 'node:crypto';
import { lstat, stat, readFile, mkdir, mkdtemp, writeFile, rename, rmdir, rm } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { parseArgs } from 'node:util';
import sharp from 'sharp';
import { SPIN_ORDER } from '../core/extract.js';

/** Local character references for the tested 512px WAN pipeline. No generation. */
export async function prepareAnimationCharacter(input: string, destination: string, options: { scailMasks?: boolean } = {}) {
  const output = resolve(destination);
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  if ((await stat(input)).size > 128 * 1024 * 1024) throw new Error('Source exceeds 128 MiB');
  const bytes = await readFile(input);
  const decoder = sharp(bytes, { limitInputPixels: 16_777_216 });
  const info = await decoder.metadata();
  if (info.format !== 'png' || (info.pages ?? 1) !== 1 || !info.width || !info.height || info.width % 8 !== 0) {
    throw new Error('Expected a single PNG with eight equal cells in one row: S SE E NE N NW W SW');
  }
  const { data, info: raw } = await decoder.toColourspace('srgb').ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const cellWidth = raw.width / 8;
  const references = [];
  const pngs: Buffer[] = [];
  const masks: Buffer[] = [];
  for (const [index, direction] of SPIN_ORDER.entries()) {
    let left = cellWidth, right = -1, top = raw.height, bottom = -1, hasTransparent = false;
    for (let y = 0; y < raw.height; y++) for (let x = 0; x < cellWidth; x++) {
      const alpha = data[(y * raw.width + index * cellWidth + x) * 4 + 3];
      if (alpha === 0) hasTransparent = true;
      if (alpha > 0) { left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y); }
    }
    if (right < left) throw new Error(`Empty character cell: ${direction}`);
    if (!hasTransparent) throw new Error(`Cell ${direction} needs a transparent background`);
    const cropWidth = right - left + 1, cropHeight = bottom - top + 1;
    const width = Math.max(1, Math.round(cropWidth * 360 / cropHeight)), height = 360;
    if (width > 512) throw new Error(`Cell ${direction} is too wide for the 512px reference canvas`);
    const xOffset = Math.floor((512 - width) / 2), yOffset = 436 - height;
    const rgb = Buffer.alloc(512 * 512 * 3, 232);
    const mask = options.scailMasks ? Buffer.alloc(512 * 512 * 3, 255) : undefined;
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const sx = left + Math.floor((x + 0.5) * cropWidth / width);
      const sy = top + Math.floor((y + 0.5) * cropHeight / height);
      const source = (sy * raw.width + index * cellWidth + sx) * 4;
      const target = ((yOffset + y) * 512 + xOffset + x) * 3, alpha = data[source + 3];
      for (let c = 0; c < 3; c++) rgb[target + c] = Math.round((data[source + c] * alpha + 232 * (255 - alpha)) / 255);
      // SCAIL primary identity map: blue foreground, white background. Use the
      // source alpha and the exact RGB sampling map, not the flattened gray RGB.
      if (mask && alpha >= 128) { mask[target] = 0; mask[target + 1] = 0; }
    }
    const png = await sharp(rgb, { raw: { width: 512, height: 512, channels: 3 } }).png().toBuffer();
    pngs.push(png);
    let primaryMask: { file: string; sha256: string; encoding: string } | undefined;
    if (mask) {
      const encoded = await sharp(mask, { raw: { width: 512, height: 512, channels: 3 } }).png().toBuffer();
      masks.push(encoded);
      primaryMask = { file: `${direction}-primary.png`, sha256: createHash('sha256').update(encoded).digest('hex'), encoding: 'scail-blue-on-white-source-alpha-ge128-v1' };
    }
    references.push({ direction, file: `${direction}.png`, sourceCell: index,
      crop: { x: index * cellWidth + left, y: top, width: cropWidth, height: cropHeight },
      placement: { x: xOffset, y: yOffset, width, height }, sha256: createHash('sha256').update(png).digest('hex'), ...(primaryMask ? { primaryMask } : {}) });
  }
  const metadata = { version: 1, profile: 'wan-512-gray-reference-v1', reviewStatus: 'unreviewed',
    sourceSha256: createHash('sha256').update(bytes).digest('hex'),
    sourceWidth: raw.width, sourceHeight: raw.height, directions: [...SPIN_ORDER],
    canvas: { width: 512, height: 512, background: [232, 232, 232], baseline: 436 },
    references, note: 'Each supplied cell is used independently. No new views, mirroring, motion or appearance captions are generated. Inspect facing and silhouette before submission.' };
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-character-'));
  try {
    for (let i = 0; i < references.length; i++) {
      await writeFile(join(temp, references[i].file), pngs[i]);
      const mask = references[i].primaryMask;
      if (mask) await writeFile(join(temp, mask.file), masks[i]);
    }
    await writeFile(join(temp, 'character.json'), JSON.stringify(metadata, null, 2) + '\n');
    await mkdir(output);
    try { await rename(temp, output); } catch (error) { await rmdir(output).catch(() => {}); throw error; }
  } finally { await rm(temp, { recursive: true, force: true }); }
  return { output, metadata };
}

export async function runPrepareAnimationCharacter(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { output: { type: 'string', short: 'o' }, 'scail-masks': { type: 'boolean' } } });
  if (positionals.length !== 1 || !values.output) throw new Error('Usage: sprute prepare-animation character.spritesheet.png -o new-folder [--scail-masks]');
  const result = await prepareAnimationCharacter(positionals[0], values.output, { scailMasks: values['scail-masks'] });
  console.log(`Prepared eight character references${values['scail-masks'] ? ' and SCAIL identity masks' : ''} in ${result.output}. Review facing before using a matching workflow.`);
}
