import { createHash } from 'node:crypto';
import { readFile, realpath, stat, writeFile, lstat } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import sharp from 'sharp';
import { SPIN_ORDER } from '../core/extract.js';
import { baseUrl } from './comfy-animation.js';
import { limitedResponse } from './animation-upload.js';
const hash = (b: Uint8Array) => createHash('sha256').update(b).digest('hex');

/** Install paired motion assets without executing a graph. Remote names are content-derived. */
export async function uploadAnimationDrivers(bundleFolder: string, server: string, serverInput: string) {
  if (!/^(\/|[A-Za-z]:[\\/])/.test(serverInput) || /[\x00-\x1f]/.test(serverInput) || serverInput.split(/[\\/]/).includes('..')) throw new Error('server-input must be an absolute ComfyUI input directory');
  const base = baseUrl(server), root = await realpath(bundleFolder);
  async function local(file: string, limit: number) {
    const path = join(root, file);
    if (await realpath(path) !== path || !(await stat(path)).isFile()) throw new Error(`Aliased or invalid bundle file: ${file}`);
    if ((await stat(path)).size > limit) throw new Error(`Bundle file exceeds limit: ${file}`);
    return readFile(path);
  }
  const bundle = JSON.parse((await local('bundle.json', 1024 * 1024)).toString());
  if (bundle.version !== 1 || bundle.profile !== 'quaternius-standard-walk-8dir-v1' || bundle.pathScope !== 'local-bundle-relative' || !bundle.views || Object.keys(bundle.views).length !== 8) throw new Error('Expected a local walk-driver bundle.json');
  const files: { name: string; bytes: Buffer; mime: string }[] = [];
  const withMasks = SPIN_ORDER.some(d => bundle.views[d]?.maskVideo !== undefined || bundle.views[d]?.maskVideoSha256 !== undefined);
  for (const d of SPIN_ORDER) {
    const v = bundle.views[d];
    if (v?.video !== `${d}/driver.mp4` || v.firstFrame !== `${d}/first.png` || typeof v.caption !== 'string' || !v.caption.trim() || v.caption.length > 4000 || /[\x00-\x1f]/.test(v.caption)) throw new Error(`Invalid driver view: ${d}`);
    const video = await local(v.video, 32 * 1024 * 1024), first = await local(v.firstFrame, 4 * 1024 * 1024);
    if (hash(video) !== v.videoSha256 || hash(first) !== v.firstFrameSha256) throw new Error(`Driver hash mismatch: ${d}`);
    if (video.length < 12 || video.toString('ascii', 4, 8) !== 'ftyp') throw new Error(`Expected MP4 container: ${d}`);
    const info = await sharp(first, { limitInputPixels: 512 * 512 }).metadata();
    if (info.format !== 'png' || info.width !== 512 || info.height !== 512 || (info.pages ?? 1) !== 1) throw new Error(`Invalid first frame: ${d}`);
    files.push({ name: `${d}.mp4`, bytes: video, mime: 'video/mp4' }, { name: `${d}.png`, bytes: first, mime: 'image/png' });
    if (withMasks) {
      if (v.maskVideo !== `${d}/mask.mkv`) throw new Error(`Expected motion mask for every direction: ${d}`);
      const mask = await local(v.maskVideo, 32 * 1024 * 1024);
      if (hash(mask) !== v.maskVideoSha256) throw new Error(`Motion mask hash mismatch: ${d}`);
      if (mask.length < 4 || mask.readUInt32BE(0) !== 0x1a45dfa3) throw new Error(`Expected EBML motion-mask container: ${d}`);
      files.push({ name: `${d}-mask.mkv`, bytes: mask, mime: 'video/x-matroska' });
    }
  }
  const prefix = `sprute-motion-${hash(Buffer.from(files.map(f => hash(f.bytes)).join(''))).slice(0, 24)}`;
  async function inspect(f: typeof files[number]) {
    const url = new URL('view', base); url.search = new URLSearchParams({ filename: f.name, subfolder: prefix, type: 'input' }).toString();
    const response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(30_000) });
    if (response.status === 404) { await response.body?.cancel(); return false; }
    if (!response.ok) throw new Error(`Cannot inspect ${f.name}: HTTP ${response.status}`);
    if (hash(await limitedResponse(response, 32 * 1024 * 1024)) !== hash(f.bytes)) throw new Error(`Remote driver conflict: ${f.name}`);
    return true;
  }
  const existing: boolean[] = [];
  for (const f of files) existing.push(await inspect(f));
  const checked = [];
  for (const [i, f] of files.entries()) {
    if (!existing[i]) {
      const body = new FormData(); body.set('image', new Blob([new Uint8Array(f.bytes)], { type: f.mime }), f.name);
      body.set('type', 'input'); body.set('subfolder', prefix); body.set('overwrite', 'false');
      try {
        const response = await fetch(new URL('upload/image', base), { method: 'POST', body, redirect: 'error', signal: AbortSignal.timeout(60_000) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = JSON.parse((await limitedResponse(response, 65536)).toString());
        if (result.name !== f.name || result.subfolder !== prefix || result.type !== 'input') throw new Error('Server returned a different path');
        if (!await inspect(f)) throw new Error('Uploaded file missing on readback');
      } catch (e) { throw new Error(`Driver upload not verified: ${f.name}. Rerun the same bundle to inspect/reuse files; no job submitted. ${e}`); }
    }
    checked.push({ file: f.name, status: existing[i] ? 'reused' : 'uploaded' });
  }
  return { version: 1, views: Object.fromEntries(SPIN_ORDER.map(d => [d, { video: `${serverInput.replace(/[\\/]+$/, '')}/${prefix}/${d}.mp4`, firstFrame: `${prefix}/${d}.png`, caption: bundle.views[d].caption,
    ...(withMasks ? { maskVideo: `${serverInput.replace(/[\\/]+$/, '')}/${prefix}/${d}-mask.mkv` } : {}) }])),
    installation: { server: base.href, inputPrefix: prefix, files: checked, submittedJobs: 0, note: 'Remote bytes verified. The supplied server input directory is not discoverable/verified via upload API. MP4 header and first-image geometry checked; decode, frame count, motion, pairing and licenses require separate validation.' } };
}

export async function runUploadAnimationDrivers(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { server: { type: 'string', default: 'http://127.0.0.1:8188' }, 'server-input': { type: 'string' }, output: { type: 'string', short: 'o' } } });
  if (positionals.length !== 1 || !values['server-input'] || !values.output) throw new Error('Usage: sprute upload-animation-drivers bundle-folder --server URL --server-input /server/ComfyUI/input -o drivers.json');
  try { await lstat(values.output); throw new Error(`Output already exists: ${values.output}`); } catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  const result = await uploadAnimationDrivers(positionals[0], values.server!, values['server-input']);
  await writeFile(values.output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(`Verified ${result.installation.files.length} motion assets and saved ${values.output}. No generation jobs submitted.`);
}
