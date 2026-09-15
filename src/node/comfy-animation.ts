import { mkdir, mkdtemp, lstat, rename, rm, rmdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { parseArgs } from 'node:util';
import { Readable, Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';

interface Video { node: string; filename: string; subfolder: string; type: 'output'; }
export type ComfyJob = { state: 'running' | 'queued' | 'unknown' | 'failed' } | { state: 'complete'; videos: Video[] };
export function baseUrl(server: string) {
  const url = new URL(server);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Use an HTTP(S) ComfyUI URL without credentials, query or fragment.');
  if (!url.pathname.endsWith('/')) url.pathname += '/';
  return url;
}
function validateJob(job: string) { if (!/^[a-zA-Z0-9_-]{1,128}$/.test(job)) throw new Error('Invalid ComfyUI job ID.'); }
async function json(url: URL) {
  const response = await fetch(url, { signal: AbortSignal.timeout(30_000), redirect: 'error' });
  if (!response.ok) throw new Error(`ComfyUI returned HTTP ${response.status}. The job was not restarted.`);
  return response.json() as Promise<any>;
}

/** Read-only: neither missing history nor an observation failure authorizes a new job. */
export async function inspectComfyJob(server: string, job: string): Promise<ComfyJob> {
  validateJob(job); const base = baseUrl(server);
  const history = await json(new URL(`history/${encodeURIComponent(job)}`, base));
  const entry = history[job];
  if (entry) {
    if (entry.status?.status_str === 'error') return { state: 'failed' };
    if (entry.status?.status_str === 'success' && entry.status?.completed !== false) {
      const videos: Video[] = [];
      for (const [node, raw] of Object.entries(entry.outputs ?? {})) {
        const output = raw as any;
        for (const file of [...(output.gifs ?? []), ...(output.images ?? [])]) {
          if (file?.type !== 'output' || typeof file.filename !== 'string' || !/\.(mp4|webm)$/i.test(file.filename)) continue;
          if (typeof (file.subfolder ?? '') !== 'string') continue;
          const video: Video = { node, filename: file.filename, subfolder: file.subfolder ?? '', type: 'output' };
          if (!videos.some(v => v.node === node && v.filename === video.filename && v.subfolder === video.subfolder)) videos.push(video);
        }
      }
      return { state: 'complete', videos };
    }
  }
  const queue = await json(new URL('queue', base));
  if (queue.queue_running?.some((x: any[]) => x[1] === job)) return { state: 'running' };
  if (queue.queue_pending?.some((x: any[]) => x[1] === job)) return { state: 'queued' };
  // Queue/history can change between reads or be cleared. Absence is not failure.
  return { state: 'unknown' };
}

export async function collectComfyAnimation(server: string, job: string, outputPath: string, node?: string) {
  const status = await inspectComfyJob(server, job);
  if (status.state !== 'complete') return { state: status.state };
  const videos = status.videos.filter(v => node === undefined || v.node === node);
  if (videos.length !== 1) throw new Error(`Expected one video, found ${videos.length}. Use --node with the output node ID if several nodes saved videos.`);
  const video = videos[0], output = resolve(outputPath);
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  const url = new URL('view', baseUrl(server));
  url.search = new URLSearchParams({ filename: video.filename, subfolder: video.subfolder, type: video.type }).toString();
  const response = await fetch(url, { signal: AbortSignal.timeout(120_000), redirect: 'error' });
  if (!response.ok || !response.body) throw new Error(`Video download failed (HTTP ${response.status}). Retry this job ID; do not submit another job.`);
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-comfy-'));
  try {
    const filename = /\.webm$/i.test(video.filename) ? 'animation.webm' : 'animation.mp4';
    let bytes = 0;
    const digest = createHash('sha256');
    const limit = new Transform({ transform(chunk, _encoding, callback) {
      bytes += chunk.length;
      digest.update(chunk);
      callback(bytes > 512 * 1024 * 1024 ? new Error('Video exceeds the 512 MiB download limit.') : null, chunk);
    } });
    await pipeline(Readable.fromWeb(response.body as any), limit, createWriteStream(join(temp, filename), { flags: 'wx' }));
    if (!bytes) throw new Error('ComfyUI returned an empty video.');
    // History may contain provider credentials, prompts and absolute server paths.
    // Persist only explicitly selected, non-secret fields, never the raw response.
    await writeFile(join(temp, 'job.json'), JSON.stringify({ version: 1, jobId: job, state: 'complete', reviewStatus: 'unreviewed', file: filename, bytes, sha256: digest.digest('hex'), outputNode: video.node }, null, 2));
    await mkdir(output);
    try { await rename(temp, output); } catch (e) { await rmdir(output).catch(() => {}); throw e; }
    return { state: 'complete' as const, output, file: join(output, filename) };
  } finally { await rm(temp, { recursive: true, force: true }); }
}

export async function runCollectAnimation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    server: { type: 'string', default: 'http://127.0.0.1:8188' }, job: { type: 'string' }, node: { type: 'string' }, output: { type: 'string', short: 'o' },
  } });
  if (positionals.length || !values.job || !values.output) throw new Error('Usage: sprute collect-animation --job ID -o new-folder [--server URL] [--node ID]');
  const result = await collectComfyAnimation(values.server!, values.job, values.output, values.node);
  if (result.state === 'complete') console.log(`Saved ${result.file}. Visual review is still required.`);
  else {
    console.log(`Job ${values.job}: ${result.state}. No job was submitted or restarted.`);
    if (result.state === 'unknown') console.log('History may be cleared or changing. Check ComfyUI and retry the same job ID.');
    process.exitCode = result.state === 'failed' ? 1 : 2;
  }
}
