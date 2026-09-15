import { createHash } from 'node:crypto';
import { readFile, realpath, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import sharp from 'sharp';
import { SPIN_ORDER } from '../core/extract.js';
import { baseUrl } from './comfy-animation.js';
const hash = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex');

export async function limitedResponse(response: Response, limit: number) {
  if (!response.body) throw new Error('Server returned an empty body');
  const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.length;
      if (size > limit) { await reader.cancel(); throw new Error('Server response exceeds size limit'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks);
}

/** Upload only verified character PNGs. Retry by inspecting the same remote names. */
export async function uploadAnimationInputs(planFolder: string, server: string) {
  const base = baseUrl(server), root = await realpath(planFolder);
  async function local(file: string, limit: number) {
    const path = join(root, file);
    if (await realpath(path) !== path) throw new Error(`Aliased or escaped plan file: ${file}`);
    if ((await stat(path)).size > limit) throw new Error(`Plan file exceeds limit: ${file}`);
    return readFile(path);
  }
  const plan = JSON.parse((await local('plan.json', 1024 * 1024)).toString('utf8'));
  if (plan.version !== 1 || !['wan-animate2-distill-euler10-v1', 'scail2-unipc40-v1'].includes(plan.profile) || !/^sprute-[a-f0-9]{24}$/.test(plan.inputPrefix) || !Array.isArray(plan.views) || plan.views.length !== 8) throw new Error('Expected plan-animation plan.json');
  const scail = plan.profile === 'scail2-unipc40-v1';
  const images: Buffer[] = [];
  const masks: Buffer[] = [];
  // Validate every local asset before making any network request.
  for (const [i, d] of SPIN_ORDER.entries()) {
    const view = plan.views[i];
    if (view?.direction !== d || view.reference !== `input/${plan.inputPrefix}/${d}.png` || view.workflow !== `${d}.workflow.json`) throw new Error(`Invalid plan view: ${d}`);
    const image = await local(view.reference, 4 * 1024 * 1024), workflow = await local(view.workflow, 1024 * 1024);
    if (hash(image) !== view.referenceSha256 || hash(workflow) !== view.workflowSha256) throw new Error(`Plan files changed: ${d}`);
    const w = JSON.parse(workflow.toString('utf8'));
    if (w['6']?.class_type !== 'LoadImage' || w['6'].inputs?.image !== `${plan.inputPrefix}/${d}.png`) throw new Error(`Reference does not match workflow: ${d}`);
    const info = await sharp(image, { limitInputPixels: 512 * 512 }).metadata();
    if (info.format !== 'png' || info.width !== 512 || info.height !== 512 || (info.pages ?? 1) !== 1) throw new Error(`Invalid reference geometry: ${d}`);
    images.push(image);
    if (scail) {
      if (view.mask !== `input/${plan.inputPrefix}/${d}-primary.png` || w['21']?.class_type !== 'LoadImage' || w['21'].inputs?.image !== `${plan.inputPrefix}/${d}-primary.png`) throw new Error(`Identity mask does not match workflow: ${d}`);
      const mask = await local(view.mask, 4 * 1024 * 1024);
      if (hash(mask) !== view.maskSha256) throw new Error(`Plan mask changed: ${d}`);
      const info = await sharp(mask, { limitInputPixels: 512 * 512 }).metadata();
      if (info.format !== 'png' || info.width !== 512 || info.height !== 512 || info.hasAlpha || (info.pages ?? 1) !== 1) throw new Error(`Invalid identity mask geometry: ${d}`);
      masks.push(mask);
    }
  }
  images.push(...masks);
  const names = [...SPIN_ORDER.map(d => `${d}.png`), ...(scail ? SPIN_ORDER.map(d => `${d}-primary.png`) : [])];
  if (`sprute-${hash(Buffer.concat(images)).slice(0,24)}` !== plan.inputPrefix) throw new Error('Reference files do not match plan input prefix');
  const checked: { direction: string; file: string; status: string }[] = [];
  async function inspect(i: number) {
    const url = new URL('view', base);
    url.search = new URLSearchParams({ filename: names[i], subfolder: plan.inputPrefix, type: 'input' }).toString();
    const response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(30_000) });
    if (response.status === 404) { await response.body?.cancel(); return false; }
    if (!response.ok) throw new Error(`Cannot inspect ${names[i]}: HTTP ${response.status}`);
    if (hash(await limitedResponse(response, 4 * 1024 * 1024)) !== hash(images[i])) throw new Error(`Remote input conflict: ${names[i]}. No overwrite requested.`);
    return true;
  }
  // Detect known conflicts across all views before uploading any missing view.
  const existing: boolean[] = [];
  for (let i = 0; i < images.length; i++) existing.push(await inspect(i));
  for (const [i, file] of names.entries()) {
    const d = SPIN_ORDER[i % 8];
    if (existing[i]) { checked.push({ direction: d, file, status: 'reused' }); continue; }
    const body = new FormData();
    body.set('image', new Blob([new Uint8Array(images[i])], { type: 'image/png' }), file);
    body.set('type', 'input'); body.set('subfolder', plan.inputPrefix); body.set('overwrite', 'false');
    try {
      const response = await fetch(new URL('upload/image', base), { method: 'POST', body, redirect: 'error', signal: AbortSignal.timeout(30_000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = JSON.parse((await limitedResponse(response, 64 * 1024)).toString('utf8'));
      if (result.name !== file || result.subfolder !== plan.inputPrefix || result.type !== 'input') throw new Error('Server returned a different input path; inspect it before continuing');
      if (!await inspect(i)) throw new Error('Uploaded file could not be read back');
    } catch (error) {
      throw new Error(`Upload not verified for ${file}. Rerun this same plan to inspect/reuse existing inputs. No job was submitted. ${error instanceof Error ? error.message : String(error)}`);
    }
    checked.push({ direction: d, file, status: 'uploaded' });
  }
  return { version: 1, server: base.href, inputPrefix: plan.inputPrefix, views: checked, submittedJobs: 0 };
}

export async function runUploadAnimationInputs(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { server: { type: 'string', default: 'http://127.0.0.1:8188' } } });
  if (positionals.length !== 1) throw new Error('Usage: sprute upload-animation plan-folder --server http://127.0.0.1:8188');
  console.log(JSON.stringify(await uploadAnimationInputs(positionals[0], values.server!), null, 2));
}
