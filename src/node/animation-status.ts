import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { lstat, readFile, realpath } from 'node:fs/promises';
import { join } from 'node:path';
import { SPIN_ORDER } from '../core/extract.js';
import { baseUrl, inspectComfyJob } from './comfy-animation.js';

async function exists(path: string) {
  try { await lstat(path); return true; }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false; throw error; }
}
async function readJson(path: string) {
  const info = await lstat(path);
  if (!info.isFile() || info.size > 1024 * 1024 || await realpath(path) !== path) throw new Error(`Invalid status metadata: ${path}`);
  return JSON.parse(await readFile(path, 'utf8'));
}
async function hashFile(path: string) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest('hex');
}

/** Observe a walk without locking, submitting, downloading, or creating files. */
export async function inspectWalk(folder: string) {
  const root = await realpath(folder), config = await readJson(join(root, 'walk.json'));
  if (config.version !== 1 || config.profile !== 'scail2-walk-v1') throw new Error('Expected an animate project containing walk.json');
  const server = baseUrl(config.server).href, run = join(root, 'run');
  const manifest = await exists(join(run, 'run.json')) ? await readJson(join(run, 'run.json')) : undefined;
  if (manifest && (manifest.version !== 1 || manifest.server !== server || !Array.isArray(manifest.views) || manifest.views.length !== 8)) throw new Error('Run does not match the saved animation server');
  const views: { direction: string; state: string; jobId?: string; transparentFilesPresent: boolean }[] = [];
  // Verify saved identities before making any server observations.
  for (const [i, direction] of SPIN_ORDER.entries()) {
    const transparentFilesPresent = await exists(join(root, 'transparent', direction, 'cycle.json'));
    if (!manifest) { views.push({ direction, state: 'unsubmitted', transparentFilesPresent }); continue; }
    const view = manifest.views[i], workflow = join(run, `${direction}.workflow.json`);
    const workflowInfo = await lstat(workflow);
    if (view?.direction !== direction || view.workflow !== `${direction}.workflow.json` || typeof view.sha256 !== 'string' ||
        !/^[a-f0-9]{64}$/.test(view.sha256) || !workflowInfo.isFile() || workflowInfo.size > 1024 * 1024 ||
        await realpath(workflow) !== workflow || await hashFile(workflow) !== view.sha256) throw new Error(`Saved workflow changed: ${direction}`);
    const journal = join(run, `${direction}.job.json`);
    if (!await exists(journal)) {
      views.push({ direction, state: await exists(join(run, `${direction}.attempt.json`)) ? 'unknown-attempt' : 'unsubmitted', transparentFilesPresent }); continue;
    }
    let job;
    try { job = await readJson(journal); }
    catch (error) {
      // A submitting process writes this journal in place. A partial observation
      // must never imply that no attempt was made or that a retry is authorized.
      if (!(error instanceof SyntaxError)) throw error;
      views.push({ direction, state: 'unreadable-journal', transparentFilesPresent }); continue;
    }
    if (job.version !== 1 || job.server !== server || job.workflowSha256 !== view.sha256 ||
        typeof job.jobId !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(job.jobId)) throw new Error(`Invalid saved job: ${direction}`);
    const result = join(run, 'results', direction), metadata = join(result, 'job.json');
    if (await exists(metadata)) {
      const saved = await readJson(metadata);
      if (saved.version !== 1 || saved.state !== 'complete' || saved.jobId !== job.jobId ||
          !['animation.mp4', 'animation.webm'].includes(saved.file) || !Number.isSafeInteger(saved.bytes) || saved.bytes <= 0 || saved.bytes > 512 * 1024 * 1024 ||
          typeof saved.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(saved.sha256)) throw new Error(`Invalid downloaded video metadata: ${direction}`);
      const file = join(result, saved.file), info = await lstat(file);
      if (!info.isFile() || await realpath(file) !== file || info.size !== saved.bytes || await hashFile(file) !== saved.sha256) throw new Error(`Downloaded video changed: ${direction}`);
      views.push({ direction, jobId: job.jobId, state: 'downloaded', transparentFilesPresent });
    } else views.push({ direction, jobId: job.jobId, state: 'check-server', transparentFilesPresent });
  }
  let serverObservationError: string | undefined;
  for (const view of views) {
    if (view.state !== 'check-server') continue;
    if (serverObservationError) { view.state = 'server-unavailable'; continue; }
    try {
      const job = await inspectComfyJob(server, view.jobId!);
      view.state = job.state === 'complete' ? job.videos.length === 1 ? 'ready-to-download' : 'ambiguous-output' : job.state;
    } catch (error) {
      view.state = 'server-unavailable';
      serverObservationError = error instanceof Error ? error.message : String(error);
    }
  }
  const previewPath = join(root, 'walk', 'preview.html');
  return { project: root, views, previewFile: await exists(previewPath) ? previewPath : null, serverObservationError,
    submittedJobs: 0, downloadedFiles: 0, writtenFiles: 0,
    note: 'Read-only snapshot. Downloaded video hashes were verified. Transparent and preview paths report presence only; use resume to verify/reuse all processing stages. Missing server observations never authorize resubmission.' };
}
