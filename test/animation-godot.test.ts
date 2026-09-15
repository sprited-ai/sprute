import { test, expect } from 'vitest';
import { mkdtemp, mkdir, writeFile, readFile, rm, readdir, symlink } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { packAnimation } from '../src/core/animation.js';
import { createImage } from '../src/core/image.js';
import { SPIN_ORDER } from '../src/core/extract.js';
import { writePng } from '../src/node/io.js';
import { exportGodotAnimation } from '../src/node/animation-godot.js';

test('Godot export preserves PNG bytes, all tracks, explicit duration and portable paths', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-godot-'));
  try {
    const input = join(root, 'input'); await mkdir(input);
    const packed = packAnimation([createImage(2, 16, [25, 60, 220, 90]), createImage(2, 16, [90, 10, 30, 0])], { cellWidth:2, cellHeight:2, columns:1, directions:[...SPIN_ORDER], fps:10, loop:false });
    packed.metadata.animations.S[1].durationMs = 250;
    await writeFile(join(input, 'animation.json'), JSON.stringify(packed.metadata));
    await writePng(join(input, 'animation.png'), packed.atlas);
    const output = join(root, 'result'); await exportGodotAnimation(input, output);
    expect(await readdir(output)).not.toContain('project.godot');
    expect(await readFile(join(output, 'animation.png'))).toEqual(await readFile(join(input, 'animation.png')));
    const text = await readFile(join(output, 'walk.tres'), 'utf8');
    expect(text).toContain('path="animation.png"');
    expect(await readFile(join(output, 'animation.png.import'), 'utf8')).toContain('process/fix_alpha_border=false');
    expect(text).not.toContain(root);
    expect(text.match(/\[sub_resource type="AtlasTexture"/g)).toHaveLength(16);
    for (const d of SPIN_ORDER) expect(text).toContain(`"name": &"${d}"`);
    expect(text).toContain('"duration": 2.5');
    expect(text.match(/"loop": false/g)).toHaveLength(8);
    await expect(exportGodotAnimation(input, output)).rejects.toThrow('already exists');
    const demo = join(root, 'demo');
    await exportGodotAnimation(input, demo, { demo: true });
    expect(await readFile(join(demo, 'animation.png'))).toEqual(await readFile(join(output, 'animation.png')));
    expect(await readFile(join(demo, 'walk.tres'))).toEqual(await readFile(join(output, 'walk.tres')));
    for (const name of ['project.godot', 'main.tscn', 'player.gd']) {
      const source = await readFile(join(demo, name), 'utf8');
      expect(source).not.toContain(root);
    }
    expect(await readFile(join(demo, 'main.tscn'), 'utf8')).toContain('path="res://walk.tres"');
    expect(await readFile(join(demo, 'main.tscn'), 'utf8')).toContain('scale = Vector2(64, 64)');
    expect(JSON.parse(await readFile(join(demo, 'export.json'), 'utf8')).demo).toBe('arrow-key-walk-v1');
    packed.metadata.animations.E[0].x = -1;
    await writeFile(join(input, 'animation.json'), JSON.stringify(packed.metadata));
    await expect(exportGodotAnimation(input, join(root, 'invalid'))).rejects.toThrow('rectangle');
    expect(await readdir(root)).toEqual(expect.arrayContaining(['input', 'result']));
    expect((await readdir(root)).some(p => p.startsWith('.sprute-') || p === 'invalid')).toBe(false);
  } finally { await rm(root, { recursive:true, force:true }); }
});

test('Godot export rejects escaped image and mismatched geometry before output', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-godot-'));
  try {
    const input = join(root, 'input'); await mkdir(input);
    const p = packAnimation([createImage(1,8),createImage(1,8)],{cellWidth:1,cellHeight:1,columns:1,directions:[...SPIN_ORDER],fps:8});
    await writeFile(join(input,'animation.json'),JSON.stringify(p.metadata));
    await writePng(join(root,'outside.png'),p.atlas);
    await symlink(join(root,'outside.png'),join(input,'animation.png'));
    await expect(exportGodotAnimation(input,join(root,'escaped'))).rejects.toThrow('escapes');
    await rm(join(input,'animation.png'));
    await writePng(join(input,'animation.png'),createImage(1,1));
    await expect(exportGodotAnimation(input,join(root,'wrong'))).rejects.toThrow('geometry');
    expect((await readdir(root)).sort()).toEqual(['input','outside.png']);
  } finally { await rm(root,{recursive:true,force:true}); }
});
