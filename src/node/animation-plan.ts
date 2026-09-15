import { createHash } from 'node:crypto';
import { lstat, stat, readFile, realpath, mkdir, mkdtemp, writeFile, rename, rmdir, rm } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { parseArgs } from 'node:util';
import sharp from 'sharp';
import graph from './wan-animation-template.json';
import scailGraph from './scail-animation-template.json';
import { SPIN_ORDER } from '../core/extract.js';

const hash = (value: Buffer | string) => createHash('sha256').update(value).digest('hex');
const facing = ['front', 'front-right', 'right side', 'rear-right', 'rear', 'rear-left', 'left side', 'front-left'];
async function readJson(path: string) {
  if ((await stat(path)).size > 1024 * 1024) throw new Error('Manifest exceeds 1 MiB');
  return JSON.parse(await readFile(path, 'utf8'));
}
function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 4000 || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(value)) throw new Error(`Invalid ${label}`);
  return value;
}

/** Build only the known local-node graph, never submit or execute arbitrary graphs. */
export async function planAnimation(characterFolder: string, driversFile: string, description: string, destination: string, options: { model?: 'wan-animate' | 'scail2' } = {}) {
  if (options.model !== undefined && !['wan-animate', 'scail2'].includes(options.model)) throw new Error('Unknown animation model');
  const scail = options.model === 'scail2';
  text(description, 'appearance description');
  const output = resolve(destination), root = await realpath(characterFolder);
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const character = await readJson(join(root, 'character.json')), drivers = await readJson(driversFile);
  if (character.version !== 1 || character.profile !== 'wan-512-gray-reference-v1' || !Array.isArray(character.references) || character.references.length !== 8) throw new Error('Expected prepare-animation character.json');
  if (drivers.version !== 1 || !drivers.views || Object.keys(drivers.views).length !== 8) throw new Error('Expected driver manifest version 1 with all eight views');
  const referenceBytes: Buffer[] = [];
  const maskBytes: Buffer[] = [];
  for (const [i, d] of SPIN_ORDER.entries()) {
    const ref = character.references[i], driver = drivers.views[d];
    if (ref?.direction !== d || ref.file !== `${d}.png`) throw new Error(`Invalid character reference: ${d}`);
    const path = join(root, ref.file);
    if (await realpath(path) !== path) throw new Error(`Reference escapes or aliases its folder: ${d}`);
    if ((await stat(path)).size > 4 * 1024 * 1024) throw new Error(`Reference exceeds 4 MiB: ${d}`);
    const bytes = await readFile(path), info = await sharp(bytes, { limitInputPixels: 512 * 512 }).metadata();
    if (hash(bytes) !== ref.sha256 || info.format !== 'png' || info.width !== 512 || info.height !== 512 || (info.pages ?? 1) !== 1) throw new Error(`Changed or invalid reference: ${d}`);
    if (!driver) throw new Error(`Missing driver: ${d}`);
    text(driver.video, `${d} server video path`);
    if (scail) {
      text(driver.maskVideo, `${d} server motion-mask video path`);
      const mask = ref.primaryMask;
      if (!mask || mask.file !== `${d}-primary.png` || mask.encoding !== 'scail-blue-on-white-source-alpha-ge128-v1') throw new Error(`Missing SCAIL identity mask: ${d}; prepare-animation with --scail-masks`);
      const maskPath = join(root, mask.file);
      if (await realpath(maskPath) !== maskPath || (await stat(maskPath)).size > 4 * 1024 * 1024) throw new Error(`Aliased or oversized identity mask: ${d}`);
      const bytes = await readFile(maskPath), info = await sharp(bytes, { limitInputPixels: 512 * 512 }).metadata();
      if (hash(bytes) !== mask.sha256 || info.format !== 'png' || info.width !== 512 || info.height !== 512 || (info.pages ?? 1) !== 1) throw new Error(`Changed or invalid identity mask: ${d}`);
      const rgb = await sharp(bytes).removeAlpha().raw().toBuffer();
      if (rgb.length !== 512 * 512 * 3 || info.hasAlpha) throw new Error(`Expected RGB identity mask: ${d}`);
      let blue = 0;
      for (let p = 0; p < rgb.length; p += 3) {
        if (rgb[p] === 0 && rgb[p+1] === 0 && rgb[p+2] === 255) blue++;
        else if (rgb[p] !== 255 || rgb[p+1] !== 255 || rgb[p+2] !== 255) throw new Error(`Invalid identity mask colors: ${d}`);
      }
      if (!blue) throw new Error(`Identity mask has no foreground: ${d}`);
      maskBytes.push(bytes);
    } else { text(driver.firstFrame, `${d} server first-frame path`); text(driver.caption, `${d} driver caption`); }
    referenceBytes.push(bytes);
  }
  // Names depend on the actual reference files, not the editable source-hash field.
  const inputPrefix = `sprute-${hash(Buffer.concat([...referenceBytes, ...maskBytes])).slice(0, 24)}`;
  const workflows = SPIN_ORDER.map((d, i) => {
    const w: any = structuredClone(scail ? scailGraph : graph), driver = drivers.views[d];
    w['6'].inputs.image = `${inputPrefix}/${d}.png`;
    w['8'].inputs.video = driver.video;
    if (scail) {
      w['21'].inputs.image = `${inputPrefix}/${d}-primary.png`;
      w['22'].inputs.video = driver.maskVideo;
    } else { w['19'].inputs.image = driver.firstFrame; w['20'].inputs.text = driver.caption; }
    w['9'].inputs.text = `Character appearance: ${description}. Full body, one character, fixed ${facing[i]} view. ${scail ? 'Walk in place with alternating steps and opposing arm swings. Preserve the reference appearance and proportions. Stationary camera. ' : ''}Background: uniform light gray, even lighting, no other objects.`;
    w['15'].inputs.filename_prefix = `${inputPrefix}/${d}`;
    return w;
  });
  const plan = { version: 1, profile: scail ? 'scail2-unipc40-v1' : 'wan-animate2-distill-euler10-v1', status: 'unsubmitted', reviewStatus: 'unreviewed', inputPrefix,
    description, drivers, views: SPIN_ORDER.map((direction, i) => ({ direction, workflow: `${direction}.workflow.json`,
      workflowSha256: hash(JSON.stringify(workflows[i], null, 2) + '\n'), reference: `input/${inputPrefix}/${direction}.png`, referenceSha256: hash(referenceBytes[i]),
      ...(scail ? { mask: `input/${inputPrefix}/${direction}-primary.png`, maskSha256: hash(maskBytes[i]) } : {}) })),
    note: 'Upload the input subfolder contents into ComfyUI input. Driver paths refer to the server. No server files, installed models, node versions, motion quality or licenses were verified by this offline planner.' };
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-plan-'));
  try {
    await mkdir(join(temp, 'input', inputPrefix), { recursive: true });
    for (const [i, d] of SPIN_ORDER.entries()) {
      await writeFile(join(temp, 'input', inputPrefix, `${d}.png`), referenceBytes[i]);
      if (scail) await writeFile(join(temp, 'input', inputPrefix, `${d}-primary.png`), maskBytes[i]);
      await writeFile(join(temp, `${d}.workflow.json`), JSON.stringify(workflows[i], null, 2) + '\n');
    }
    await writeFile(join(temp, 'plan.json'), JSON.stringify(plan, null, 2) + '\n');
    await mkdir(output);
    try { await rename(temp, output); } catch (error) { await rmdir(output).catch(() => {}); throw error; }
  } finally { await rm(temp, { recursive: true, force: true }); }
  return { output, plan };
}

export async function runPlanAnimation(args: string[]) {
  const { positionals, values } = parseArgs({ args, allowPositionals: true, options: { output: { type: 'string', short: 'o' }, drivers: { type: 'string' }, description: { type: 'string' }, model: { type: 'string', default: 'wan-animate' } } });
  if (positionals.length !== 1 || !values.output || !values.drivers || !values.description) throw new Error('Usage: sprute plan-animation character-folder --drivers drivers.json --description "appearance" -o new-folder');
  if (values.model !== 'wan-animate' && values.model !== 'scail2') throw new Error('--model must be wan-animate or scail2');
  const result = await planAnimation(positionals[0], values.drivers, values.description, values.output, { model: values.model });
  console.log(`Prepared eight unsubmitted ${values.model} workflows in ${result.output}. Server setup and input review are still required.`);
}
