import { readFile, writeFile, realpath, stat } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { parseArgs } from 'node:util';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { SPIN_ORDER } from '../core/extract.js';
import { validateAnimationLayout } from '../core/animation.js';
import { animationPreviewHtml } from './animation-preview-html.js';

/** A portable offline viewer for a packed atlas, without modifying its pixels. */
export async function previewAnimation(input: string, output: string, referenceSheet?: string) {
  const root = await realpath(input), metadataPath = join(root, 'animation.json');
  if ((await stat(metadataPath)).size > 8 * 1024 * 1024) throw new Error('Animation metadata exceeds 8 MiB');
  const metadataBytes = await readFile(metadataPath), m = JSON.parse(metadataBytes.toString('utf8'));
  if (m.version !== 1 || m.image !== 'animation.png' || typeof m.loop !== 'boolean') throw new Error('Expected packed Sprute animation.json version 1');
  validateAnimationLayout({ cellWidth: m.cellWidth, cellHeight: m.cellHeight, columns: 1, directions: m.directions, fps: m.fps, loop: m.loop }, m.frameCount);
  if (!m.animations || Object.keys(m.animations).length !== 8) throw new Error('Expected all eight animation tracks');
  for (const [row, d] of SPIN_ORDER.entries()) {
    const frames = m.animations[d];
    if (!Array.isArray(frames) || frames.length !== m.frameCount) throw new Error(`Wrong frame count for ${d}`);
    let total = 0;
    for (const [i, f] of frames.entries()) {
      if (!f || f.x !== i * m.cellWidth || f.y !== row * m.cellHeight || f.width !== m.cellWidth || f.height !== m.cellHeight || !Number.isFinite(f.durationMs) || f.durationMs <= 0) throw new Error(`Invalid frame rectangle or duration: ${d} ${i}`);
      total += f.durationMs;
    }
    if (!Number.isFinite(total)) throw new Error(`Invalid total duration: ${d}`);
  }
  const imagePath = await realpath(join(root, 'animation.png'));
  if (!imagePath.startsWith(root + sep)) throw new Error('Atlas escapes source directory');
  if ((await stat(imagePath)).size > 128 * 1024 * 1024) throw new Error('Atlas file exceeds 128 MiB');
  const bytes = await readFile(imagePath), info = await sharp(bytes).metadata();
  if (info.format !== 'png' || (info.pages ?? 1) !== 1 || info.width !== m.cellWidth * m.frameCount || info.height !== m.cellHeight * 8) throw new Error('Atlas PNG geometry does not match metadata');
  const sha = (b: Buffer) => createHash('sha256').update(b).digest('hex');
  let reference;
  if (referenceSheet !== undefined) {
    if ((await stat(referenceSheet)).size > 32 * 1024 * 1024) throw new Error('Reference sheet exceeds 32 MiB');
    const source = await readFile(referenceSheet), info = await sharp(source, { limitInputPixels: 16_777_216 }).metadata();
    if (info.format !== 'png' || (info.pages ?? 1) !== 1 || !info.height || !info.width || info.width % 8 !== 0) throw new Error('Reference must be an eight-view horizontal PNG sprite sheet with equal cells');
    reference = { image: `data:image/png;base64,${source.toString('base64')}`, width: info.width / 8, height: info.height, sha256: sha(source) };
  }
  const data = { width: m.cellWidth, height: m.cellHeight, count: m.frameCount, loop: m.loop,
    directions: SPIN_ORDER, tracks: m.animations, atlas: `data:image/png;base64,${bytes.toString('base64')}`,
    atlasSha256: sha(bytes), metadataSha256: sha(metadataBytes), reference };
  await writeFile(output, animationPreviewHtml(data), { flag: 'wx' });
  return { output, frameCount: m.frameCount };
}

export async function runPreviewAnimation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { output: { type: 'string', short: 'o' }, reference: { type: 'string' } } });
  if (positionals.length !== 1 || !values.output) throw new Error('Usage: sprute preview-animation packed-folder -o new-preview.html [--reference character.spritesheet.png]');
  const result = await previewAnimation(positionals[0], values.output, values.reference);
  console.log(`Open ${result.output} in a browser to review all eight directions. No server needed.`);
}
