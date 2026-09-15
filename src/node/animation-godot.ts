import { readFile, writeFile, stat, lstat, realpath, mkdir, mkdtemp, rename, rm, rmdir } from 'node:fs/promises';
import { dirname, join, resolve, sep } from 'node:path';
import { parseArgs } from 'node:util';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { godotDemoFiles } from './animation-godot-demo.js';
import { SPIN_ORDER } from '../core/extract.js';
import { validateAnimationLayout } from '../core/animation.js';

/** Export a packed Sprute atlas as a portable Godot 4 SpriteFrames resource. */
export async function exportGodotAnimation(input: string, destination: string, options: { demo?: boolean } = {}) {
  const root = await realpath(input), output = resolve(destination);
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const metadataPath = join(root, 'animation.json');
  if ((await stat(metadataPath)).size > 8 * 1024 * 1024) throw new Error('Animation metadata exceeds 8 MiB');
  const metadataBytes = await readFile(metadataPath);
  const m = JSON.parse(metadataBytes.toString('utf8'));
  if (m.version !== 1 || m.image !== 'animation.png' || typeof m.loop !== 'boolean') throw new Error('Expected packed Sprute animation.json version 1');
  validateAnimationLayout({ cellWidth: m.cellWidth, cellHeight: m.cellHeight, columns: 1, directions: m.directions, fps: m.fps, loop: m.loop }, m.frameCount);
  if (!m.animations || Object.keys(m.animations).length !== 8) throw new Error('Expected all eight animation tracks');
  const frameBlocks: string[] = [], animations: string[] = [];
  let id = 0;
  for (const [row, direction] of SPIN_ORDER.entries()) {
    const frames = m.animations[direction];
    if (!Array.isArray(frames) || frames.length !== m.frameCount) throw new Error(`Wrong frame count for ${direction}`);
    const entries: string[] = [];
    for (const [i, frame] of frames.entries()) {
      if (!frame || frame.x !== i * m.cellWidth || frame.y !== row * m.cellHeight || frame.width !== m.cellWidth || frame.height !== m.cellHeight ||
          !Number.isFinite(frame.durationMs) || frame.durationMs <= 0 || !Number.isFinite(frame.durationMs * m.fps / 1000)) throw new Error(`Invalid frame rectangle or duration: ${direction} ${i}`);
      const key = `Atlas_${++id}`;
      frameBlocks.push(`[sub_resource type="AtlasTexture" id="${key}"]\natlas = ExtResource("1")\nregion = Rect2(${frame.x}, ${frame.y}, ${frame.width}, ${frame.height})\n`);
      entries.push(`{\n"duration": ${frame.durationMs * m.fps / 1000},\n"texture": SubResource("${key}")\n}`);
    }
    animations.push(`{\n"frames": [${entries.join(',\n')}],\n"loop": ${m.loop},\n"name": &"${direction}",\n"speed": ${m.fps}\n}`);
  }
  const imagePath = await realpath(join(root, 'animation.png'));
  if (!imagePath.startsWith(root + sep)) throw new Error('Atlas escapes source directory');
  if ((await stat(imagePath)).size > 128 * 1024 * 1024) throw new Error('Atlas file exceeds 128 MiB');
  const image = await readFile(imagePath), info = await sharp(image).metadata();
  if (info.format !== 'png' || (info.pages ?? 1) !== 1 || info.width !== m.cellWidth * m.frameCount || info.height !== m.cellHeight * 8) throw new Error('Atlas PNG geometry does not match metadata');
  const resource = `[gd_resource type="SpriteFrames" load_steps=${id + 2} format=3]\n\n[ext_resource type="Texture2D" path="animation.png" id="1"]\n\n${frameBlocks.join('\n')}\n[resource]\nanimations = [${animations.join(',\n')}]\n`;
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-godot-'));
  try {
    await writeFile(join(temp, 'animation.png'), image);
    await writeFile(join(temp, 'animation.png.import'), '[remap]\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\ncompress/mode=0\nmipmaps/generate=false\nprocess/fix_alpha_border=false\nprocess/premult_alpha=false\n');
    await writeFile(join(temp, 'animation.json'), metadataBytes);
    await writeFile(join(temp, 'walk.tres'), resource);
    if (options.demo) {
      for (const [name, text] of Object.entries(godotDemoFiles(m.cellWidth, m.cellHeight))) await writeFile(join(temp, name), text);
    }
    await writeFile(join(temp, 'README.txt'), (options.demo ? 'Open project.godot in Godot 4 and press F5. Use arrow keys; hold two for diagonal movement. Releasing the keys pauses the pose. This demo does not create an idle animation.\n\n' : '') + 'Godot 4: copy this whole folder into your project. Add AnimatedSprite2D, then drag walk.tres onto its Sprite Frames property. Choose S, SE, E, NE, N, NW, W or SW and play. Set Texture Filter to Nearest for pixel art. Keep animation.png and its .import settings beside walk.tres. The settings disable Godot alpha-border color modification to preserve source RGBA.\n\nThis export preserves frame order and durations. It does not approve anatomy, direction, foot contact or loop quality.\n');
    await writeFile(join(temp, 'export.json'), JSON.stringify({ version: 1, format: 'godot4-spriteframes', ...(options.demo ? { demo: 'arrow-key-walk-v1' } : {}), sourceMetadataSha256: createHash('sha256').update(metadataBytes).digest('hex'), atlasSha256: createHash('sha256').update(image).digest('hex'), reviewStatus: 'unreviewed' }, null, 2) + '\n');
    await mkdir(output);
    try { await rename(temp, output); } catch (error) { await rmdir(output).catch(() => {}); throw error; }
  } finally { await rm(temp, { recursive: true, force: true }); }
  return { output, frameCount: m.frameCount };
}

export async function runExportGodot(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { output: { type: 'string', short: 'o' }, demo: { type: 'boolean', default: false } } });
  if (positionals.length !== 1 || !values.output) throw new Error('Usage: sprute export-godot packed-folder -o new-folder [--demo]');
  const result = await exportGodotAnimation(positionals[0], values.output, { demo: values.demo });
  if (values.demo) console.log(`Open ${result.output}/project.godot in Godot 4, press F5, and use the arrow keys.`);
  console.log(`Exported ${result.frameCount} frames per direction to ${result.output}/walk.tres. Visual review still required.`);
}
