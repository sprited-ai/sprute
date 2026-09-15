import { test, expect, vi } from 'vitest';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SPIN_ORDER } from '../src/core/extract.js';
import { inspectWalk } from '../src/node/animation-status.js';
import { runAnimate } from '../src/node/animate.js';
const hash = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
async function snapshot(root: string): Promise<Record<string, string>> {
  const files: Record<string, string> = {};
  async function visit(path: string, prefix = '') {
    for (const entry of await readdir(path, { withFileTypes: true })) {
      if (entry.isDirectory()) await visit(join(path, entry.name), prefix + entry.name + '/');
      else files[prefix + entry.name] = hash(await readFile(join(path, entry.name)));
    }
  }
  await visit(root); return files;
}

test('status observes mixed job states without downloading, submitting, writing or taking the worker lock', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-status-')), requests: string[] = [];
  const server = createServer((req, res) => {
    requests.push(`${req.method} ${req.url}`);
    if (req.url === '/queue') { res.end(JSON.stringify({ queue_running: [[0, 'SE']], queue_pending: [[0, 'E']] })); return; }
    const id = req.url!.split('/').pop()!;
    const entry = id === 'NE' ? { status: { status_str: 'success' }, outputs: { '15': { gifs: [{ filename: 'NE.mp4', type: 'output' }] } } }
      : id === 'NW' ? { status: { status_str: 'error' } } : id === 'W' ? { status: { status_str: 'success' }, outputs: {} } : undefined;
    res.end(JSON.stringify(entry ? { [id]: entry } : {}));
  });
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${(server.address() as any).port}/`;
  try {
    await writeFile(join(root, 'walk.json'), JSON.stringify({ version: 1, profile: 'scail2-walk-v1', server: url }));
    expect((await inspectWalk(root)).views.every(v => v.state === 'unsubmitted')).toBe(true); expect(requests).toEqual([]);
    const run = join(root, 'run'), workflow = '{}';
    await mkdir(join(run, 'results/S'), { recursive: true });
    await mkdir(join(root, 'transparent/S'), { recursive: true });
    await writeFile(join(root, 'transparent/S/cycle.json'), '{}');
    await writeFile(join(root, '.animate.lock'), 'worker owns this lock');
    await writeFile(join(run, 'run.json'), JSON.stringify({ version: 1, server: url, views: SPIN_ORDER.map(direction => ({ direction, workflow: `${direction}.workflow.json`, sha256: hash(workflow) })) }));
    for (const d of SPIN_ORDER) {
      await writeFile(join(run, `${d}.workflow.json`), workflow);
      await writeFile(join(run, `${d}.job.json`), d === 'SW' ? '{' : JSON.stringify({ version: 1, server: url, workflowSha256: hash(workflow), jobId: d }));
    }
    const video = Buffer.from('downloaded test video');
    await writeFile(join(run, 'results/S/animation.mp4'), video);
    await writeFile(join(run, 'results/S/job.json'), JSON.stringify({ version: 1, state: 'complete', jobId: 'S', file: 'animation.mp4', bytes: video.length, sha256: hash(video) }));
    const before = await snapshot(root), status = await inspectWalk(root);
    expect(status.views.map(v => v.state)).toEqual(['downloaded', 'running', 'queued', 'ready-to-download', 'unknown', 'failed', 'ambiguous-output', 'unreadable-journal']);
    expect(status.views[0].transparentFilesPresent).toBe(true);
    expect(status).toMatchObject({ submittedJobs: 0, downloadedFiles: 0, writtenFiles: 0, previewFile: null });
    expect(requests.every(r => r.startsWith('GET /history/') || r === 'GET /queue')).toBe(true);
    expect(requests).not.toContain('GET /history/S');
    expect(await snapshot(root)).toEqual(before);
    const previousExitCode = process.exitCode;
    const output = vi.spyOn(console, 'log').mockImplementation(() => {});
    try {
      await runAnimate(['--status', root]);
      const text = output.mock.calls.map(args => args.join(' ')).join('\n');
      expect(text).toContain('generating (job SE)');
      expect(text).toContain('waiting for the GPU (job E)');
      expect(text).toContain('the server could not confirm this job (job N)');
      expect(text).toContain('generation failed (job NW)');
      expect(text).toContain('video could not be identified (job W)');
      expect(text).toContain('Nothing submitted or downloaded.');
      expect(process.exitCode).toBe(1);
      expect(await snapshot(root)).toEqual(before);
      expect(requests.every(r => r.startsWith('GET /history/') || r === 'GET /queue')).toBe(true);
    } finally { output.mockRestore(); process.exitCode = previousExitCode; }
    const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('test observation outage'));
    try {
      const offline = await inspectWalk(root);
      expect(offline.views[0].state).toBe('downloaded');
      expect(offline.views.slice(1, 7).every(v => v.state === 'server-unavailable')).toBe(true);
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(await snapshot(root)).toEqual(before);
    } finally { fetch.mockRestore(); }
    await writeFile(join(run, 'results/S/animation.mp4'), Buffer.alloc(video.length));
    const count = requests.length;
    await expect(inspectWalk(root)).rejects.toThrow('Downloaded video changed'); expect(requests.length).toBe(count);
  } finally { await new Promise<void>(r => server.close(() => r())); await rm(root, { recursive: true, force: true }); }
});

test('an attempt without a journal is unknown, never unsubmitted', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-status-attempt-'));
  try {
    const server = 'http://localhost:8188/';
    await mkdir(join(root, 'run'));
    await writeFile(join(root, 'walk.json'), JSON.stringify({ version: 1, profile: 'scail2-walk-v1', server }));
    await writeFile(join(root, 'run/run.json'), JSON.stringify({ version: 1, server, views: SPIN_ORDER.map(direction => ({ direction, workflow: `${direction}.workflow.json`, sha256: hash('{}') })) }));
    for (const d of SPIN_ORDER) await writeFile(join(root, 'run', `${d}.workflow.json`), '{}');
    await writeFile(join(root, 'run/S.attempt.json'), '{}');
    const result = await inspectWalk(root);
    expect(result.views[0].state).toBe('unknown-attempt');
    expect(result.views.slice(1).every(v => v.state === 'unsubmitted')).toBe(true);
  } finally { await rm(root, { recursive: true, force: true }); }
});
