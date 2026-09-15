import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, mkdtemp, open, unlink, rename } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import sharp from 'sharp';
import { SPIN_ORDER } from '../core/extract.js';
import { makeSpriteSheet } from '../core/sheet.js';
import { decodeImage, writePng } from './io.js';
import { toonoutMatting } from './toonout.js';
import { showStandingInTerminal } from './terminal-character.js';
import { buildProgress } from './build-progress.js';
import {validateFixedDirections, type FixedDirections} from './fixed-directions.js';
import { runLocalQwenJob } from './qwen-local.js';

const facing = ['front, facing the viewer', 'three-quarter front, nose pointing screen-right',
  'strict side profile, nose pointing screen-right', 'three-quarter rear, facing away toward screen-right',
  'back view, facing directly away, no visible face', 'three-quarter rear, facing away toward screen-left',
  'strict side profile, nose pointing screen-left', 'three-quarter front, nose pointing screen-left'];

export async function loadLocalCharacter(file: string) {
  const base = dirname(resolve(file));
  const projectFile = join(process.cwd(), 'sprute.config.json');
  const project = await readFile(projectFile, 'utf8').then(JSON.parse, (e: NodeJS.ErrnoException) => {
    if (e.code === 'ENOENT') return {}; throw e;
  });
  const raw = JSON.parse(await readFile(file, 'utf8'));
  const config = { ...project, ...raw, local: { ...project.local, ...raw.local } };
  if (config.backend !== 'local') return null;
  if (config.fixedDirections !== undefined) validateFixedDirections(config.fixedDirections);
  if (typeof config.source !== 'string' || !config.source.trim()) throw new Error('Local character requires source image');
  if (config.states !== undefined && JSON.stringify(config.states) !== '["standing"]') throw new Error('Local idle/walk/run orchestration is not connected yet. No generation started.');
  if (config.directions !== undefined && config.directions !== 8) throw new Error('Local character requires 8 directions');
  const size = config.frameSize ?? 128;
  if (!Number.isInteger(size) || size < 32 || size > 512) throw new Error('frameSize must be32..512');
  const local = config.local;
  for (const key of ['python', 'runner', 'comfyRoot', 'diffusionModels']) {
    if (typeof local[key] !== 'string' || !local[key].trim()) throw new Error(`Missing local.${key}`);
    // Project paths are relative to project cwd; character overrides to its file.
    local[key] = resolve(raw.local?.[key] !== undefined ? base : process.cwd(), local[key]);
  }
  const source = resolve(base, config.source);
  await readFile(source); // Fail before claiming output or launching a model.
  const seed = config.seed ?? 42;
  if (!Number.isInteger(seed) || seed < 0 || seed >= 2 ** 32) throw new Error('Invalid seed');
  const fixedDirections: FixedDirections = Object.fromEntries(Object.entries(config.fixedDirections ?? {}).map(([d,p])=>[d,resolve(raw.fixedDirections !== undefined ? base : process.cwd(),p as string)]));
  return { source, local, size, seed, fixedDirections,
    output: resolve(raw.output !== undefined ? base : process.cwd(), config.output ?? `outputs/${basename(file, '.sprute.json')}`),
    open: config.preview?.open ?? true };
}

type LocalCharacter = NonNullable<Awaited<ReturnType<typeof loadLocalCharacter>>>;
type BuildState = { status: string; completed: string[]; active?: string; error?: string; key: string; files?: Record<string, string>; cutouts: Record<string, {path: string; hash: string}> };

export async function buildLocalCharacter(config: LocalCharacter) {
  await mkdir(dirname(config.output), {recursive: true});
  const lockPath = `${config.output}.sprute-lock`;
  const lock = await open(lockPath, 'wx').catch((error: NodeJS.ErrnoException) => {
    if (error.code === 'EEXIST') throw new Error(`Build is locked: ${lockPath}. Check the owning process before removing a stale lock.`);
    throw error;
  });
  try {
    await lock.writeFile(JSON.stringify({pid: process.pid, started: new Date().toISOString()}));
    return await buildLocked(config);
  } finally { await lock.close(); await unlink(lockPath); }
}

async function buildLocked(config: LocalCharacter) {
  const { output, source, local, seed, size } = config;
  await mkdir(dirname(output), { recursive: true });
  const digest = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
  const sourceHash = digest(await readFile(source));
  const fixed = new Map<string,{png:Buffer;hash:string}>();
  for (const [direction,path] of Object.entries(config.fixedDirections).sort(([a],[b])=>a.localeCompare(b))) {
    const png=await readFile(path),image=await decodeImage(png);
    if(image.width!==size || image.height!==size) throw new Error(`Fixed ${direction} must be ${size}x${size}; no generation started. Prepare the sprite canvas without rescaling its pixels.`);
    fixed.set(direction,{png,hash:digest(png)});
  }
  const fixedUnchanged=async()=>{
    for(const [d,p] of Object.entries(config.fixedDirections))if(digest(await readFile(p))!==fixed.get(d)!.hash)throw new Error(`Fixed direction changed: ${d}`);
  };
  const key = digest(JSON.stringify({ version: 2, sourceHash,
    ...(fixed.size ? {fixedDirections:[...fixed].map(([d,v])=>[d,v.hash])} : {}),
    runnerHash: digest(await readFile(local.runner)), local, seed, size, facing }));
  let previous: BuildState | undefined;
  try { await mkdir(output); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
    const receipt = JSON.parse(await readFile(join(output, 'build.json'), 'utf8'));
    if (receipt.key !== key || !receipt.cutouts || !['complete', 'failed'].includes(receipt.status)) {
      throw new Error('Output is unrecognized, still running, or inputs/settings changed; choose a new output directory. No generation started.');
    }
    if (receipt.status === 'complete') {
    for (const file of ['standing.png', 'standing.json', 'preview.html']) {
      if (digest(await readFile(join(output, file))) !== receipt.files[file]) throw new Error(`Saved output changed: ${file}`);
    }
    console.log(`  ✓ Standing is already built · reused 8 directions\n\n  Preview: ${join(output, 'preview.html')}\n`);
    await showStandingInTerminal(join(output, 'standing.png'), size);
    openPreview(config.open, join(output, 'preview.html'));
    return output;
    }
    previous = receipt;
    for (const direction of previous!.completed) {
      const saved = previous!.cutouts[direction];
      if (!saved || digest(await readFile(join(output, saved.path))) !== saved.hash) throw new Error(`Saved direction changed: ${direction}`);
    }
    console.log(`  ↻ Continuing · ${previous!.completed.length}/8 directions already built`);
  }
  const state: BuildState = previous ?? { status: 'running', completed: [], key, cutouts: {} };
  state.status = 'running'; delete state.error;
  const progress = buildProgress();
  const save = async () => {
    const temp = join(output, 'build.json.tmp');
    await writeFile(temp, JSON.stringify(state, null, 2));
    await rename(temp, join(output, 'build.json'));
  };
  try {
    await save();
    const cells = [];
    await fixedUnchanged();
    for (const [i, direction] of SPIN_ORDER.entries()) {
      if (state.completed.includes(direction)) {
        const cutout = await readFile(join(output, state.cutouts[direction].path));
        cells.push(await decodeImage(await sharp(cutout).resize(size, size, {kernel: 'nearest'}).png().toBuffer()));
        progress.done(`Standing ${direction} · reused`);
        continue;
      }
      if(fixed.has(direction)) {
        const supplied=fixed.get(direction)!;
        const path=`fixed-${direction}.png`;
        // Snapshot approved pixels; these directions do not enter inference or matting.
        await writePng(join(output,path),await decodeImage(supplied.png));
        cells.push(await decodeImage(supplied.png));
        state.cutouts[direction]={path,hash:digest(await readFile(join(output,path)))};
        state.completed.push(direction);await save();
        progress.done(`Standing ${direction} · supplied image preserved`);
        continue;
      }
      if (digest(await readFile(source)) !== sourceHash) throw new Error('Source changed');
      state.active = direction; await save();
      // Keep previous failed attempts for diagnosis; never overwrite them.
      const attempt = await mkdtemp(join(output, `${direction}-`));
      const jobOutput = join(attempt, 'result'), job = join(attempt, 'job.json');
      await writeFile(job, JSON.stringify({ reference: source, comfyRoot: local.comfyRoot,
        diffusionModels: local.diffusionModels, output: jobOutput, seed, width: 1024, height: 1024,
        prompt: `Draw the exact character from the reference in ${facing[i]}. Standing still, full body centered with margin above head and below feet. Preserve original proportions, face, hairstyle, clothing, colors and art style. Plain light gray background. One character only.` }, null, 2));
      progress.start(`Standing ${direction} · ${i + 1}/8`);
      const generated = await runLocalQwenJob({ python: local.python, runner: local.runner, job, output: jobOutput, log: join(attempt, 'generation.log') });
      progress.start(`Background removal ${direction} · ${i + 1}/8`);
      const [cutout] = await toonoutMatting([await decodeImage(generated.png)]);
      await writePng(join(jobOutput, 'transparent.png'), cutout);
      // Fixed canvas preserves registration; no per-frame bounding-box scaling.
      const png = await sharp(Buffer.from(cutout.data), { raw: { width: cutout.width, height: cutout.height, channels: 4 } })
        .resize(size, size, { kernel: 'nearest' }).png().toBuffer();
      cells.push(await decodeImage(png));
      state.cutouts[direction] = {path: `${basename(attempt)}/result/transparent.png`, hash: digest(await readFile(join(jobOutput, 'transparent.png')))};
      state.completed.push(direction); await save();
      progress.done(`Standing ${direction} · ${i + 1}/8`);
    }
    progress.start('Packing sprite sheet');
    await writePng(join(output, 'standing.png'), makeSpriteSheet(cells));
    await writeFile(join(output, 'standing.json'), JSON.stringify({ version: 1, directions: SPIN_ORDER, frameSize: size, states: ['standing'], reviewStatus: 'unreviewed' }, null, 2));
    const html = `<!doctype html><meta charset="utf-8"><title>Sprute preview</title><style>body{background:#202630;color:white;font:18px system-ui;text-align:center}canvas{image-rendering:pixelated;width:384px;height:384px}button{padding:12px;margin:4px}</style><h1>Your character</h1><p>Standing · AI-generated preview; check all directions.</p><canvas width="${size}" height="${size}"></canvas><div></div><script>const c=document.querySelector('canvas'),x=c.getContext('2d'),im=new Image();let d=0;function draw(){x.clearRect(0,0,c.width,c.height);x.drawImage(im,d*c.width,0,c.width,c.height,0,0,c.width,c.height)}im.onload=draw;im.src='standing.png';${JSON.stringify(SPIN_ORDER)}.forEach((n,i)=>{let b=document.createElement('button');b.textContent=n;b.onclick=()=>{d=i;draw()};document.querySelector('div').append(b)})</script>`;
    const preview = join(output, 'preview.html'); await writeFile(preview, html);
    state.files = {};
    for (const file of ['standing.png', 'standing.json', 'preview.html']) state.files[file] = digest(await readFile(join(output, file)));
    if (digest(await readFile(source)) !== sourceHash) throw new Error('Source changed');
    await fixedUnchanged();
    state.status = 'complete'; delete state.active; await save();
    progress.done('Sprite sheet and preview ready');
    console.log(`\n  Preview: ${preview}\n`);
    await showStandingInTerminal(join(output, 'standing.png'), size);
    openPreview(config.open, preview);
    return output;
  } catch (error) { progress.fail(`Build stopped at ${state.active ?? 'packing'}; logs: ${output}`); state.status = 'failed'; state.error = String(error); await save(); throw error; } finally { progress.close(); }
}

function openPreview(enabled: boolean, preview: string) {
  if (!enabled) return;
  const command = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? null : 'xdg-open';
  if (command) { const child = spawn(command, [preview], { stdio: 'ignore' }); child.on('error', () => {}); child.unref(); }
}
