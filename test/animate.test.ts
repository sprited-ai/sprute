import { test, expect, vi } from 'vitest';
import { createServer } from 'node:http';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, writeFile, rm, access, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import { SPIN_ORDER } from '../src/core/extract.js';
import { advanceWalk, createWalk, runAnimate } from '../src/node/animate.js';

const matting = vi.hoisted(() => ({ calls: 0, failAt: 0 }));

// GPU setup and neural matting have their own tests. Exercise real planning,
// HTTP submission/recovery, video decoding, cycle timing, packing and preview here.
vi.mock('../src/node/animation-preflight.js', () => ({ checkAnimationServer: vi.fn(async () => ({ compatibleNamesAndInputs: true, issues: [] })) }));
vi.mock('../src/node/animation-upload.js', () => ({ uploadAnimationInputs: vi.fn(async () => ({})) }));
vi.mock('../src/node/toonout.js', () => ({ hasLocalToonout: vi.fn(async () => true), toonoutMattingWithProvenance: vi.fn(async (images: any[]) => {
  matting.calls++;
  if (matting.calls === matting.failAt) throw new Error('Interrupted local matting');
  for (const image of images) for (let i = 0; i < image.data.length; i += 4) if (image.data[i] > 200 && image.data[i + 1] > 200 && image.data[i + 2] > 200) image.data[i + 3] = 0;
  return { images, provenance: null };
}) }));

async function inputs(root: string) {
  const sheet = join(root, 'sheet.png'), drivers = join(root, 'drivers.json');
  const pixels = Buffer.alloc(32 * 4 * 4);
  for (let d = 0; d < 8; d++) for (let y = 1; y <= 2; y++) for (let x = 1; x <= 2; x++) pixels.set([50, 80, 100, 255], (y * 32 + d * 4 + x) * 4);
  await sharp(pixels, { raw: { width: 32, height: 4, channels: 4 } }).png().toFile(sheet);
  await writeFile(drivers, JSON.stringify({ version: 1, views: Object.fromEntries(SPIN_ORDER.map(d => [d, { video: `/input/${d}.mp4`, maskVideo: `/input/${d}.mkv` }])) }));
  return { sheet, drivers };
}

test.each([undefined, 2])('one character becomes eight transparent tracks; offline resume with holdFrames=%s avoids duplicate GPU requests', async (holdFrames) => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-walk-test-'));
  matting.calls = 0; matting.failAt = 5;
  let complete = false, posts = 0, downloads = 0, failDownload = true;
  const jobs: string[] = [];
  execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=white:s=16x16:r=24', '-vf', 'drawbox=x=6:y=4:w=4:h=10:color=red:t=fill', '-frames:v', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', join(root, 'video.mp4')]);
  const video = await readFile(join(root, 'video.mp4'));
  const server = createServer(async (req, res) => {
    const path = new URL(req.url!, 'http://local').pathname;
    if (path === '/prompt') {
      posts++; let body = ''; for await (const chunk of req) body += chunk;
      const data = JSON.parse(body); jobs.push(data.prompt_id); res.end(JSON.stringify({ prompt_id: data.prompt_id })); return;
    }
    if (path === '/queue') { res.end(JSON.stringify({ queue_running: [], queue_pending: jobs.map(id => [0, id]) })); return; }
    if (path.startsWith('/history/')) {
      const id = path.split('/').pop()!;
      res.end(JSON.stringify(complete ? { [id]: { status: { status_str: 'success' }, outputs: { '15': { gifs: [{ filename: id + '.mp4', type: 'output' }] } } } } : {})); return;
    }
    if (path === '/view') {
      downloads++;
      if (failDownload && downloads === 3) { failDownload = false; res.writeHead(503); res.end(); return; }
      res.end(video); return;
    }
    res.writeHead(404); res.end();
  });
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  try {
    const { sheet, drivers } = await inputs(root);
    const walk = await createWalk(sheet, drivers, join(root, 'my-walk'), { server: `http://127.0.0.1:${(server.address() as any).port}`, start: 0, end: holdFrames ? 2 : 1, size: 16, holdFrames });
    expect(posts).toBe(0);
    expect((await advanceWalk(walk, () => {})).state).toBe('pending');
    expect(posts).toBe(8);
    expect((await advanceWalk(walk, () => {})).state).toBe('pending'); expect(posts).toBe(8);
    complete = true;
    await expect(advanceWalk(walk, () => {})).rejects.toThrow('Video download failed');
    expect(posts).toBe(8);
    await expect(advanceWalk(walk, () => {})).rejects.toThrow('Interrupted local matting');
    await access(join(walk, 'transparent/S/cycle.json'));
    await expect(access(join(walk, 'transparent/E'))).rejects.toThrow();
    const result = await advanceWalk(walk, () => {});
    expect(result.state).toBe('complete'); expect(downloads).toBe(9); expect(posts).toBe(8);
    const metadata = JSON.parse(await readFile(join(walk, 'walk/animation.json'), 'utf8'));
    expect(metadata.frameCount).toBe(2); expect(metadata.loop).toBe(true);
    expect(Object.keys(metadata.animations)).toEqual([...SPIN_ORDER]);
    for (const direction of SPIN_ORDER) {
      expect(metadata.animations[direction][0].durationMs).toBeCloseTo((holdFrames ?? 1) * 1000 / 24, 1);
      expect(metadata.animations[direction][1].durationMs).toBeCloseTo(1000 / 24, 1);
    }
    expect(metadata.durationMs).toBeCloseTo((holdFrames ? 3 : 2) * 1000 / 24, 1);
    expect((await sharp(join(walk, 'walk/animation.png')).metadata()).hasAlpha).toBe(true);
    expect(await readFile(join(walk, 'walk/preview.html'), 'utf8')).toContain('data:image/png;base64,');
    await new Promise<void>(r => server.close(() => r()));
    expect(matting.calls).toBe(holdFrames ? 26 : 17);
    expect((await advanceWalk(walk, () => {})).state).toBe('complete'); expect(posts).toBe(8); expect(matting.calls).toBe(holdFrames ? 26 : 17);
    // Editing a completed asset must not silently authorize its reuse.
    await writeFile(join(walk, 'transparent/S/frames/000001.png'), 'changed');
    await expect(advanceWalk(walk, () => {})).rejects.toThrow('Saved animation stage changed');
  } finally { server.close(); await rm(root, { recursive: true, force: true }); }
}, 60_000);

test('rejects invalid setup, changed snapshots and concurrent work before GPU access', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-walk-errors-'));
  try {
    const { sheet, drivers } = await inputs(root), output = join(root, 'walk');
    await expect(createWalk(sheet, drivers, output, { start: 3, end: 1 })).rejects.toThrow('settings');
    await expect(access(output)).rejects.toThrow();
    for (const holdFrames of [0, -1, 1.5, 32]) {
      await expect(createWalk(sheet, drivers, output, { holdFrames })).rejects.toThrow('frame hold');
      await expect(access(output)).rejects.toThrow();
    }
    await createWalk(sheet, drivers, output);
    await expect(createWalk(sheet, drivers, output)).rejects.toThrow('--resume');
    await writeFile(join(output, '.animate.lock'), JSON.stringify({ pid: process.pid }));
    await expect(advanceWalk(output)).rejects.toThrow('Another animate process');
    await rm(join(output, '.animate.lock'));
    const savedPath = process.env.PATH;
    try {
      process.env.PATH = '';
      await expect(advanceWalk(output, () => {})).rejects.toThrow('Install a working ffmpeg');
      await expect(access(join(output, 'run'))).rejects.toThrow();
    } finally { process.env.PATH = savedPath; }
    await writeFile(join(output, 'drivers.json'), '{}');
    await expect(advanceWalk(output)).rejects.toThrow('guides changed');
    await expect(access(join(output, '.animate.lock'))).rejects.toThrow();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('one-time CLI setup saves local defaults, never overwrites them, and resume rejects changed settings', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-walk-setup-')), cwd = process.cwd();
  try {
    const { drivers } = await inputs(root); process.chdir(root);
    await runAnimate(['setup', '--drivers', drivers, '--server', 'http://localhost:8188']);
    const settings = JSON.parse(await readFile(join(root, 'sprute.animation.json'), 'utf8'));
    expect(settings).toMatchObject({ version: 1, drivers: await realpath(drivers), server: 'http://localhost:8188/' });
    await expect(runAnimate(['setup', '--drivers', drivers])).rejects.toThrow('Settings already exist');
    await expect(runAnimate(['--resume', 'saved-walk', '--size', '32'])).rejects.toThrow('saved settings');
  } finally { process.chdir(cwd); await rm(root, { recursive: true, force: true }); }
});

test('an uncertain submission never resubmits or starts the remaining seven directions', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-walk-uncertain-')); let posts = 0;
  const server = createServer(async (req, res) => {
    if (req.method === 'POST') { posts++; for await (const _ of req) { /* consume request */ } res.writeHead(503); res.end(); return; }
    res.end(JSON.stringify(req.url === '/queue' ? { queue_running: [], queue_pending: [] } : {}));
  });
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  try {
    const { sheet, drivers } = await inputs(root);
    const walk = await createWalk(sheet, drivers, join(root, 'walk'), { server: `http://127.0.0.1:${(server.address() as any).port}` });
    await expect(advanceWalk(walk, () => {})).rejects.toThrow('Submission not confirmed');
    const resumed = await advanceWalk(walk, () => {});
    expect(resumed.state).toBe('needs-attention'); expect(posts).toBe(1);
    await expect(access(join(walk, 'run/SE.job.json'))).rejects.toThrow();
    const previousExitCode = process.exitCode;
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      await runAnimate(['--resume', walk]);
      const output = errors.mock.calls.map(args => args.join(' ')).join('\n');
      expect(output).toContain('S: the server could not confirm this job');
      expect(output).toContain(`sprute animate --status '${walk}'`);
      expect(output).toContain('No automatic retry was submitted.');
      expect(process.exitCode).toBe(1);
      expect(posts).toBe(1);
      await expect(access(join(walk, '.animate.lock'))).rejects.toThrow();
    } finally { errors.mockRestore(); process.exitCode = previousExitCode; }
  } finally { await new Promise<void>(r => server.close(() => r())); await rm(root, { recursive: true, force: true }); }
});

test('carries the original character description into the walk and snapshots explicit overrides', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-walk-description-'));
  try {
    const { sheet, drivers } = await inputs(root), hero = join(root, 'hero.spritesheet.png');
    await writeFile(hero, await readFile(sheet));
    await writeFile(join(root, 'hero.sprute.yaml'), 'description: a little robot with red boots\n');
    const first = await createWalk(hero, drivers, join(root, 'first'));
    expect(JSON.parse(await readFile(join(first, 'walk.json'), 'utf8')).description).toBe('a little robot with red boots');
    await writeFile(join(root, 'hero.sprute.yaml'), 'description: a changed description\n');
    expect(JSON.parse(await readFile(join(first, 'walk.json'), 'utf8')).description).toBe('a little robot with red boots');
    const second = await createWalk(hero, drivers, join(root, 'second'), { description: 'a robot with blue boots' });
    expect(JSON.parse(await readFile(join(second, 'walk.json'), 'utf8')).description).toBe('a robot with blue boots');
  } finally { await rm(root, { recursive: true, force: true }); }
});

test.each([
  { signal: 'SIGINT' as const, during: 'submission', code: 130 },
  { signal: 'SIGTERM' as const, during: 'waiting', code: 143 },
])('gracefully stops $signal during $during and resumes without duplicate jobs', async ({ signal, during, code }) => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-walk-stop-'));
  const oldExitCode = process.exitCode;
  const listeners = { SIGINT: process.listenerCount('SIGINT'), SIGTERM: process.listenerCount('SIGTERM') };
  const jobs: string[] = [];
  let sentSignal = false;
  const signalOnce = () => { if (!sentSignal) { sentSignal = true; process.emit(signal); } };
  const output = vi.spyOn(console, 'log').mockImplementation(() => {});
  const errors = vi.spyOn(console, 'error').mockImplementation(message => {
    if (during === 'waiting' && String(message).startsWith('Waiting 30 seconds')) signalOnce();
  });
  const server = createServer(async (req, res) => {
    if (req.url === '/prompt') {
      let body = ''; for await (const chunk of req) body += chunk;
      const id = JSON.parse(body).prompt_id; jobs.push(id);
      // Deliver the signal before confirming the POST, exercising an in-flight request.
      if (during === 'submission') signalOnce();
      res.end(JSON.stringify({ prompt_id: id })); return;
    }
    res.end(JSON.stringify(req.url === '/queue' ? { queue_running: [], queue_pending: jobs.map(id => [0, id]) } : {}));
  });
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  try {
    const { sheet, drivers } = await inputs(root);
    const walk = await createWalk(sheet, drivers, join(root, "hero's walk"), { server: `http://127.0.0.1:${(server.address() as any).port}` });
    await runAnimate(['--resume', walk, '--wait']);
    expect(sentSignal).toBe(true); expect(process.exitCode).toBe(code);
    expect(jobs).toHaveLength(8);
    await expect(access(join(walk, '.animate.lock'))).rejects.toThrow();
    expect(output.mock.calls.flat().join('\n')).toContain("hero'\\''s walk' --wait");
    expect(process.listenerCount('SIGINT')).toBe(listeners.SIGINT);
    expect(process.listenerCount('SIGTERM')).toBe(listeners.SIGTERM);
    expect((await advanceWalk(walk, () => {})).state).toBe('pending');
    expect(jobs).toHaveLength(8);
  } finally {
    process.exitCode = oldExitCode; output.mockRestore(); errors.mockRestore();
    await new Promise<void>(r => server.close(() => r()));
    await rm(root, { recursive: true, force: true });
  }
}, 60_000);
