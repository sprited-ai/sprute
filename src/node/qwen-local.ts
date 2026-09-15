import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { readFile, open } from 'node:fs/promises';
import sharp from 'sharp';

/** Execute a local Qwen job; never falls back to a remote provider. */
export async function runLocalQwenJob(options: { python: string; runner: string; job: string; output: string; log?: string }) {
  if (![options.python, options.runner, options.job, options.output].every(x => typeof x === 'string' && x.trim())) {
    throw new Error('Local Qwen requires python, runner, job and output paths');
  }
  const log = options.log ? await open(resolve(options.log), 'wx') : undefined;
  try {
  await new Promise<void>((done, reject) => {
    const child = spawn(options.python, [resolve(options.runner), '--job', resolve(options.job)], {
      shell: false, detached: process.platform !== 'win32',
      stdio: log ? ['ignore', log.fd, log.fd] : 'inherit', env: { ...process.env, HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1' },
    });
    let interrupted: NodeJS.Signals | undefined;
    const forward = (signal: NodeJS.Signals) => {
      interrupted = signal;
      if (!child.pid) return;
      try {
        // Include any model subprocesses, while leaving other GPU jobs alone.
        if (process.platform === 'win32') child.kill(signal);
        else process.kill(-child.pid, signal);
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error;
      }
    };
    const interrupt = () => forward('SIGINT');
    const terminate = () => forward('SIGTERM');
    const cleanup = () => {
      process.off('SIGINT', interrupt); process.off('SIGTERM', terminate);
    };
    process.on('SIGINT', interrupt); process.on('SIGTERM', terminate);
    child.once('error', error => { cleanup(); reject(error); });
    // Wait for the child and its stdio to close before releasing the build lock.
    child.once('close', (code, signal) => {
      cleanup();
      if (interrupted) reject(new Error(`Local Qwen interrupted (${interrupted}); rerun the same command to resume completed directions`));
      else if (code === 0) done();
      else reject(new Error(`Local Qwen stopped (${signal ?? code}); inspect its output before retrying`));
    });
  });
  } finally { await log?.close(); }
  const output = resolve(options.output);
  const state = JSON.parse(await readFile(`${output}/state.json`, 'utf8'));
  if (state.status !== 'complete' || state.gradEnabled !== false) throw new Error('Local Qwen did not complete an inference-only job');
  const png = await readFile(`${output}/result.png`);
  const image = await sharp(png).metadata();
  if (image.format !== 'png' || !image.width || !image.height) throw new Error('Local Qwen output is not a valid PNG');
  return { png, state, width: image.width, height: image.height };
}
