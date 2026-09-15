import { loadAnimationDefaults } from './animation-defaults.js';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { execFile } from 'node:child_process';
import { lstat, mkdir, mkdtemp, open, readFile, readdir, realpath, rename, rm, rmdir, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { hostname } from 'node:os';
import { parseArgs, promisify } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';
import YAML from 'yaml';
import { SPIN_ORDER } from '../core/extract.js';
import { baseUrl } from './comfy-animation.js';
import { prepareAnimationCharacter } from './animation-character.js';
import { planAnimation } from './animation-plan.js';
import { checkAnimationServer } from './animation-preflight.js';
import { uploadAnimationInputs } from './animation-upload.js';
import { submitAnimationPlan } from './animation-batch.js';
import { collectAnimationRun } from './animation-collect-run.js';
import { reviewAnimation } from './animation-review.js';
import { extractCycle } from './animation-cycle.js';
import { matteAnimationCycle } from './animation-matte.js';
import { packAnimationFile } from './animation.js';
import { previewAnimation } from './animation-preview.js';
import { hasLocalToonout } from './toonout.js';
import { inspectWalk } from './animation-status.js';
import { runOneToAll } from './animate-one-to-all.js';

const hash = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
const shellArg = (value: string) => "'" + value.replaceAll("'", "'\\''") + "'";
const receiptName = '.sprute-stage.json';
const exec = promisify(execFile);
type WalkConfig = {
  version: 1; profile: 'scail2-walk-v1'; server: string; description: string;
  start: number; end: number; size: number; holdFrames?: number; sheetSha256: string; driversSha256: string;
};
export type AnimateOptions = { server?: string; description?: string; start?: number; end?: number; size?: number; holdFrames?: number };

async function exists(path: string) {
  try { await lstat(path); return true; }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false; throw error; }
}
async function json(path: string) {
  if ((await lstat(path)).size > 8 * 1024 * 1024) throw new Error(`Metadata too large: ${path}`);
  return JSON.parse(await readFile(path, 'utf8'));
}
async function tree(path: string): Promise<Record<string, string>> {
  const files: Record<string, string> = {};
  async function visit(folder: string, prefix: string) {
    for (const entry of (await readdir(folder, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      if (!prefix && entry.name === receiptName) continue;
      const name = prefix + entry.name, file = join(folder, entry.name);
      if (entry.isDirectory()) await visit(file, name + '/');
      else if (entry.isFile()) {
        const digest = createHash('sha256');
        for await (const chunk of createReadStream(file)) digest.update(chunk);
        files[name] = digest.digest('hex');
      } else throw new Error(`Unexpected alias or special file: ${file}`);
    }
  }
  await visit(path, '');
  return files;
}

/** Commit local stages together with their receipts; an interrupted stage can be rebuilt. */
async function stage(output: string, inputKey: string, build: (destination: string) => Promise<unknown>) {
  if (await exists(output)) {
    if (!(await lstat(output)).isDirectory()) throw new Error(`Invalid stage directory: ${output}`);
    const receipt = await json(join(output, receiptName));
    if (receipt.version !== 1 || receipt.inputKey !== inputKey ||
        JSON.stringify(receipt.files) !== JSON.stringify(await tree(output))) throw new Error(`Saved animation stage changed: ${output}`);
    return;
  }
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-walk-'));
  try {
    const data = join(temp, 'data');
    await build(data);
    await writeFile(join(data, receiptName), JSON.stringify({ version: 1, inputKey, files: await tree(data) }) + '\n');
    await rename(data, output);
  } finally { await rm(temp, { recursive: true, force: true }); }
}

function validate(config: WalkConfig) {
  if (config.version !== 1 || config.profile !== 'scail2-walk-v1' ||
      typeof config.description !== 'string' || !config.description.trim() || config.description.length > 4000 ||
      !Number.isSafeInteger(config.start) || !Number.isSafeInteger(config.end) || config.start < 0 || config.end <= config.start || config.end > 599 ||
      !Number.isSafeInteger(config.size) || config.size < 4 || config.size > 2048 ||
      !/^[a-f0-9]{64}$/.test(config.sheetSha256) || !/^[a-f0-9]{64}$/.test(config.driversSha256)) throw new Error('Invalid saved walk settings');
  if (config.holdFrames !== undefined && (!Number.isSafeInteger(config.holdFrames) || config.holdFrames < 1 ||
      Math.ceil((config.end - config.start + 1) / config.holdFrames) < 2)) throw new Error('Invalid frame hold: use a positive integer that leaves at least two drawings');
  baseUrl(config.server);
}

/** Snapshot one character and installed motion guides. Initialization never submits a job. */
export async function createWalk(sheet: string, drivers: string, output: string, options: AnimateOptions = {}) {
  const root = resolve(output);
  if (await exists(root)) throw new Error(`Output already exists. Continue with: sprute animate --resume ${shellArg(root)}`);
  if ((await lstat(sheet)).size > 32 * 1024 * 1024 || (await lstat(drivers)).size > 1024 * 1024) throw new Error('Character or driver input exceeds size limit');
  const sheetBytes = await readFile(sheet), driverBytes = await readFile(drivers);
  let description = options.description;
  const sidecar = sheet.replace(/\.spritesheet\.png$/i, '.sprute.yaml');
  if (description === undefined && sidecar !== sheet && await exists(sidecar)) {
    if ((await lstat(sidecar)).size > 1024 * 1024) throw new Error('Saved character description exceeds 1 MiB');
    const saved = YAML.parse(await readFile(sidecar, 'utf8'));
    if (typeof saved?.description === 'string' && saved.description.trim()) description = saved.description;
  }
  const config: WalkConfig = { version: 1, profile: 'scail2-walk-v1', server: baseUrl(options.server ?? 'http://127.0.0.1:8188').href,
    description: description ?? 'A stylized game character matching the reference image',
    start: options.start ?? 32, end: options.end ?? 63, size: options.size ?? 128,
    ...(options.holdFrames === undefined ? {} : { holdFrames: options.holdFrames }),
    sheetSha256: hash(sheetBytes), driversSha256: hash(driverBytes) };
  validate(config);
  // Validate the PNG and all guide fields before creating a persistent project.
  await mkdir(dirname(root), { recursive: true });
  const temp = await mkdtemp(join(dirname(root), '.sprute-walk-init-'));
  try {
    await writeFile(join(temp, 'character.png'), sheetBytes);
    await writeFile(join(temp, 'drivers.json'), driverBytes);
    await prepareAnimationCharacter(join(temp, 'character.png'), join(temp, 'check-character'), { scailMasks: true });
    await planAnimation(join(temp, 'check-character'), join(temp, 'drivers.json'), config.description, join(temp, 'check-plan'), { model: 'scail2' });
    await rm(join(temp, 'check-character'), { recursive: true });
    await rm(join(temp, 'check-plan'), { recursive: true });
    await writeFile(join(temp, 'walk.json'), JSON.stringify(config, null, 2) + '\n');
    await mkdir(root);
    try { await rename(temp, root); } catch (error) { await rmdir(root).catch(() => {}); throw error; }
  } finally { await rm(temp, { recursive: true, force: true }); }
  return root;
}

/** A single invocation advances the saved project; GPU attempts remain journaled exactly once. */
export async function advanceWalk(folder: string, log: (message: string) => void = console.error) {
  const root = await realpath(folder), lockPath = join(root, '.animate.lock');
  let lock;
  try { lock = await open(lockPath, 'wx', 0o600); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
    throw new Error(`Another animate process owns ${lockPath}. If it stopped unexpectedly, check the PID in that file and remove only the lock after confirming the process has stopped.`);
  }
  try {
    await lock.writeFile(JSON.stringify({ pid: process.pid, host: hostname() }));
    const config: WalkConfig = await json(join(root, 'walk.json')); validate(config);
    const sheet = join(root, 'character.png'), drivers = join(root, 'drivers.json');
    if (hash(await readFile(sheet)) !== config.sheetSha256 || hash(await readFile(drivers)) !== config.driversSha256) throw new Error('Saved character or motion guides changed; use a new output folder for a different animation.');
    const key = hash(JSON.stringify(config));
    const character = join(root, 'references'), plan = join(root, 'plan'), run = join(root, 'run');
    await stage(character, key, out => prepareAnimationCharacter(sheet, out, { scailMasks: true }));
    await stage(plan, key, out => planAnimation(character, drivers, config.description, out, { model: 'scail2' }));

    // Completed local downloads let export resume even when the GPU server is offline.
    const hasRun = await exists(join(run, 'run.json'));
    if (hasRun) {
      const saved = await json(join(run, 'run.json')), expected = await json(join(plan, 'plan.json'));
      if (saved.server !== config.server || !Array.isArray(saved.views) || saved.views.length !== 8) throw new Error('Saved run does not match this walk');
      for (const [i, d] of SPIN_ORDER.entries()) {
        const v = saved.views[i];
        if (v.direction !== d || v.workflow !== `${d}.workflow.json` || v.sha256 !== expected.views[i].workflowSha256 ||
            hash(await readFile(join(run, v.workflow))) !== v.sha256) throw new Error(`Saved run differs from the walk plan: ${d}`);
      }
    }
    let collected = hasRun ? await collectAnimationRun(run) : undefined;
    if (collected?.views.some(v => v.state === 'failed' || v.state === 'unknown')) return { state: 'needs-attention' as const, views: collected.views, output: root };
    if (!collected?.allComplete) {
      if (!hasRun) {
        for (const program of ['ffmpeg', 'ffprobe']) {
          try { await exec(program, ['-version'], { timeout: 10_000, maxBuffer: 1024 * 1024 }); }
          catch { throw new Error(`Install a working ${program} on this computer before generating a walk. No job submitted.`); }
        }
        if (!await hasLocalToonout()) throw new Error('Install the optional onnxruntime-node dependency for local background removal. No job submitted.');
      }
      log('Checking the animation server…');
      const preflight = await checkAnimationServer(config.server, 'scail2');
      if (!preflight.compatibleNamesAndInputs) throw new Error(`Animation server needs setup:\n${preflight.issues.map(i => i.detail).join('\n')}`);
      await uploadAnimationInputs(plan, config.server);
      log('Submitting new directions and recovering existing jobs…');
      const submitted = await submitAnimationPlan(plan, run, config.server);
      if (submitted.views.some(v => v.state === 'unknown' || v.state === 'failed')) {
        return { state: 'needs-attention' as const, views: submitted.views, output: root };
      }
      collected = await collectAnimationRun(run);
    }
    log(collected.views.map(v => `${v.direction}: ${v.state}`).join(' · '));
    // Process completed views while other directions are still rendering.
    for (const view of collected.views) {
      if (view.state !== 'complete' || !('file' in view) || !view.file) continue;
      const d = view.direction, review = join(root, 'reviews', d), cycle = join(root, 'cycles', d), matte = join(root, 'transparent', d);
      const video = await json(join(run, 'results', d, 'job.json'));
      const viewKey = hash(key + video.sha256);
      log(`${d}: extracting the walk and removing its background…`);
      await stage(review, viewKey, out => reviewAnimation(view.file!, out));
      await stage(cycle, viewKey, out => extractCycle(review, config.start, config.end, out));
      await stage(matte, viewKey, out => matteAnimationCycle(cycle, out));
    }
    if (!collected.allComplete) return { state: collected.views.some(v => ['failed', 'unknown'].includes(v.state)) ? 'needs-attention' as const : 'pending' as const, views: collected.views, output: root };
    const packed = join(root, 'walk');
    await stage(packed, key, async out => {
      const first = await json(join(root, 'transparent', 'S', 'cycle.json'));
      const temp = await mkdtemp(join(root, '.sprute-pack-'));
      try {
        const manifest = join(temp, 'frames.json');
        await writeFile(manifest, JSON.stringify({ version: 1, cellWidth: config.size, cellHeight: config.size,
          fps: first.frameCount / first.durationSeconds, loop: true,
          ...(config.holdFrames === undefined ? {} : { holdFrames: config.holdFrames }),
          cycles: Object.fromEntries(SPIN_ORDER.map(d => [d, join(root, 'transparent', d)])),
          registration: { sourceWidth: first.width, sourceHeight: first.height, targetHeight: Math.round(config.size * .7), baseline: Math.round(config.size * .85), centerX: config.size / 2, alphaThreshold: 128 } }));
        await packAnimationFile(manifest, out);
      await previewAnimation(out, join(out, 'preview.html'), sheet);
      } finally { await rm(temp, { recursive: true, force: true }); }
    });
    return { state: 'complete' as const, output: packed, preview: join(packed, 'preview.html'), reviewStatus: 'unreviewed' as const };
  } finally { await lock.close(); await rm(lockPath, { force: true }); }
}

export async function runAnimate(args: string[]) {
  if (args[0] === 'one-to-all') return runOneToAll(args.slice(1));
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log(`Make your character walk in eight directions (experimental).

Connect your ComfyUI SCAIL-2 server once:
  sprute animate setup --drivers drivers.json --server http://localhost:8188

Make a walk from a character you generated:
  sprute animate outputs/my-character.spritesheet.png --wait

Continue a saved animation after closing the terminal:
  sprute animate --resume outputs/my-character.walk --wait

To stop: press Ctrl+C once and wait for the resume command before closing.
The current processing pass finishes first; submitted GPU jobs keep running.

Check progress without submitting or downloading anything:
  sprute animate --status outputs/my-character.walk

The result includes a transparent sprite sheet, animation.json and preview.html.
Default: 32 frames per direction, 128px cells, repeating playback.
Review character details, foot contact and the loop seam before using it in a game.

Options for a new walk:
  -o FOLDER           Choose a new output folder
  --description TEXT Override the saved character description
  --drivers FILE     Use an installed motion-guide manifest
  --server URL       Override the saved animation server
  --size N           Game frame size (default 128)
  --start N --end N  Select an inclusive video frame range (default 32–63)
  --hold-frames N    Hold every Nth drawing without changing the cycle length
  --wait             Keep checking until export finishes

Local requirements: FFmpeg, ffprobe and onnxruntime-node.
Server requirements: ComfyUI, SCAIL-2 models/nodes and installed walking guides.
Without --wait, exit code 2 means generation is still pending.`);
    return;
  }
  if (args[0] === 'setup') {
    const { values, positionals } = parseArgs({ args: args.slice(1), allowPositionals: true, options: { drivers: { type: 'string' }, server: { type: 'string', default: 'http://127.0.0.1:8188' } } });
    if (positionals.length || !values.drivers) throw new Error('Usage: sprute animate setup --drivers drivers.json [--server URL]');
    const path = resolve('sprute.animation.json');
    if (await exists(path)) throw new Error(`Settings already exist: ${path}. Edit that file to change your animation server.`);
    const drivers = await realpath(values.drivers), manifest = await json(drivers);
    if (manifest.version !== 1 || SPIN_ORDER.some(d => typeof manifest.views?.[d]?.video !== 'string' || typeof manifest.views?.[d]?.maskVideo !== 'string')) throw new Error('Expected installed SCAIL walk guides with eight RGB and mask video paths');
    const server = baseUrl(values.server!).href, check = await checkAnimationServer(server, 'scail2');
    if (!check.compatibleNamesAndInputs) throw new Error(`Animation server needs setup:\n${check.issues.map(i => i.detail).join('\n')}`);
    await writeFile(path, JSON.stringify({ version: 1, server, drivers }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    console.log(`Saved ${path}. Next: sprute animate character.spritesheet.png --wait`); return;
  }
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    output: { type: 'string', short: 'o' }, drivers: { type: 'string' }, server: { type: 'string' }, description: { type: 'string' },
    resume: { type: 'string' }, status: { type: 'string' }, wait: { type: 'boolean' }, start: { type: 'string' }, end: { type: 'string' }, size: { type: 'string' }, 'hold-frames': { type: 'string' },
  } });
  if (values.status !== undefined) {
    if (!values.status.trim()) throw new Error('--status requires a saved animation folder.');
    if (positionals.length || Object.entries(values).some(([key, value]) => key !== 'status' && value !== undefined)) throw new Error('--status cannot be combined with generation or resume options.');
    const result = await inspectWalk(values.status);
    const labels: Record<string, string> = {
      unsubmitted: 'not started', running: 'generating', queued: 'waiting for the GPU',
      'ready-to-download': 'generated; ready to download', downloaded: 'video downloaded',
      failed: 'generation failed', unknown: 'the server could not confirm this job',
      'unknown-attempt': 'a submission was started but not confirmed',
      'unreadable-journal': 'saved job information is not readable yet',
      'server-unavailable': 'cannot reach the server; job state is unknown',
      'ambiguous-output': 'generation finished, but its video could not be identified',
    };
    for (const view of result.views) console.log(`${view.direction.padEnd(3)} ${labels[view.state] ?? view.state}${view.jobId ? ` (job ${view.jobId})` : ''}${view.transparentFilesPresent ? ' · transparent files present' : ''}`);
    console.log(result.previewFile ? `Preview file: ${result.previewFile}` : 'Preview has not been exported yet.');
    if (result.serverObservationError) console.error(`Could not observe the server: ${result.serverObservationError}`);
    console.log('Status only. Nothing submitted or downloaded.');
    if (result.views.some(v => ['failed', 'unknown', 'unknown-attempt', 'unreadable-journal', 'server-unavailable', 'ambiguous-output'].includes(v.state))) process.exitCode = 1;
    return;
  }
  let root: string;
  if (values.resume) {
    if (positionals.length || ['output', 'drivers', 'server', 'description', 'start', 'end', 'size', 'hold-frames'].some(k => values[k as keyof typeof values] !== undefined)) throw new Error('--resume uses saved settings; only --wait can be added.');
    root = resolve(values.resume);
  } else {
    if (positionals.length !== 1) throw new Error('Usage: sprute animate character.spritesheet.png [--wait]\nSetup: sprute animate setup --drivers drivers.json --server URL\nContinue: sprute animate --resume my-walk [--wait]');
    const defaults = await loadAnimationDefaults();
    const drivers = values.drivers ?? defaults.drivers;
    if (!drivers) throw new Error('Connect your animation server first: sprute animate setup --drivers drivers.json --server URL\nSee docs/walking.md for server and motion-guide setup.');
    for (const name of ['start', 'end', 'size', 'hold-frames'] as const) if (values[name] !== undefined && !/^\d+$/.test(values[name]!)) throw new Error(`--${name} must be an integer`);
    const input = resolve(positionals[0]), output = values.output ?? join(dirname(input), basename(input).replace(/(?:\.spritesheet)?\.png$/i, '') + '.walk');
    root = await createWalk(input, drivers, output, { server: values.server ?? defaults.server, description: values.description,
      start: values.start === undefined ? undefined : Number(values.start), end: values.end === undefined ? undefined : Number(values.end), size: values.size === undefined ? undefined : Number(values.size),
      holdFrames: values['hold-frames'] === undefined ? undefined : Number(values['hold-frames']) });
  }
  // Let the in-flight stage settle before releasing its lock. Killing a POST
  // halfway through can leave an uncertain job, so cancellation is cooperative.
  const stopped = new AbortController();
  let stopCode = 130;
  const requestStop = (code: number) => {
    if (stopped.signal.aborted) return;
    stopCode = code;
    stopped.abort();
    console.error('Stopping after the current processing step finishes. Keep this terminal open until the resume command appears.');
  };
  const onInterrupt = () => requestStop(130), onTerminate = () => requestStop(143);
  process.on('SIGINT', onInterrupt);
  process.on('SIGTERM', onTerminate);
  try {
    do {
      const result = await advanceWalk(root);
      if (result.state === 'complete') {
        console.log(`Walk generated: ${result.output}\nOpen ${result.preview}\nReview the feet, character details and loop seam before using it in your game.`); return;
      }
      if (result.state === 'needs-attention') {
        console.error('Walking needs attention. Your saved work is still in this folder:');
        console.error(root);
        for (const view of result.views) {
          const label = view.state === 'failed' ? 'generation failed'
            : view.state === 'unknown' ? 'the server could not confirm this job'
            : view.state === 'unsubmitted' ? 'not submitted'
            : view.state === 'complete' ? 'generation complete'
            : view.state;
          console.error(`  ${view.direction}: ${label}${'jobId' in view && view.jobId ? ` (job ${view.jobId})` : ''}`);
        }
        console.error(`Check the saved jobs without starting new ones:\nsprute animate --status ${shellArg(root)}`);
        console.error('Keep this folder. No automatic retry was submitted.'); process.exitCode = 1; return;
      }
      if (stopped.signal.aborted) break;
      if (!values.wait) {
        console.log(`Generation is still running. Continue with: sprute animate --resume ${shellArg(root)} --wait`); process.exitCode = 2; return;
      }
      console.error('Waiting 30 seconds for the remaining directions…');
      try { await delay(30_000, undefined, { signal: stopped.signal }); }
      catch (error) { if (!stopped.signal.aborted) throw error; }
      if (stopped.signal.aborted) break;
    } while (true);
    console.log(`Stopped locally. Submitted GPU jobs may still be running.\nContinue with: sprute animate --resume ${shellArg(root)} --wait`);
    process.exitCode = stopCode;
  } finally {
    process.removeListener('SIGINT', onInterrupt);
    process.removeListener('SIGTERM', onTerminate);
  }
}
