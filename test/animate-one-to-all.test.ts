import { test, expect } from 'vitest';
import { mkdtemp, mkdir, writeFile, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync, spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { oneToAllInvocation, oneToAllCycleInvocation } from '../src/node/animate-one-to-all.js';

test.each(['SIGINT', 'SIGTERM'] as const)('CLI forwards %s and waits for the Python runner to finish saving', async signal => {
  const root = await mkdtemp(join(tmpdir(), 'sprute signal bridge '));
  const runner = join(root, 'runner.py');
  await writeFile(runner, `import signal, time, sys
from pathlib import Path
root = Path(__file__).parent
received = []
def stop(number, frame):
    received.append(number)
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
(root / 'ready').write_text('ready')
deadline = time.monotonic() + 8
while not received and time.monotonic() < deadline:
    time.sleep(0.01)
if not received:
    sys.exit(99)
time.sleep(0.2)
(root / 'saved').write_text(str(received[0]))
sys.exit(128 + received[0])
`);
  const child = spawn(process.execPath, ['--import', 'tsx', 'src/cli.ts', 'animate', 'one-to-all',
    '--plan', join(root, 'plan.json'), '--python', 'python3', '--runner', runner, '--check'],
    { stdio: 'ignore' });
  const exit = new Promise<number | null>((done, reject) => {
    child.once('error', reject);
    child.once('exit', done);
  });
  try {
    let ready = false;
    for (let i = 0; i < 200; i++) {
      ready = await readFile(join(root, 'ready'), 'utf8').then(() => true, () => false);
      if (ready || child.exitCode !== null) break;
      await delay(25);
    }
    expect(ready).toBe(true);
    child.kill(signal);
    expect(await exit).toBe(signal === 'SIGINT' ? 130 : 143);
    expect(await readFile(join(root, 'saved'), 'utf8')).toBe(signal === 'SIGINT' ? '2' : '15');
  } finally {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
    await exit;
    await rm(root, { recursive: true, force: true });
  }
}, 15_000);

test('rejects ambiguous inputs before invoking Python', () => {
  const base = ['--plan', 'plan.json', '--python', 'python3', '--runner', 'batch.py'];
  expect(() => oneToAllInvocation(base)).toThrow('--runtime');
  expect(() => oneToAllInvocation([...base, '--check', '--resume'])).toThrow('omit');
  expect(() => oneToAllInvocation([...base, 'character.png', '--check'])).toThrow('prepared');
  const invocation = oneToAllInvocation([...base, '--runtime', 'runtime', '-o', 'path with spaces', '--resident', '--resume']);
  expect(invocation.args).toContain(resolve('path with spaces'));
  expect(invocation.args.slice(-2)).toEqual(['--resume', '--resident']);
});

test('actual CLI dispatch validates a prepared plan without creating generation output', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute prepared plan '));
  try {
    await mkdir(join(root, 'cache/frames'), { recursive: true });
    const names = ['image_input.png', 'pose_input.png', 'mask_input.png', 'pose.mp4',
      ...Array.from({ length: 65 }, (_, i) => `frames/${String(i + 1).padStart(6, '0')}.png`)];
    const files: Record<string, string> = {};
    for (const name of names) {
      // Check mode validates input identity, not image decoding or inference.
      const bytes = Buffer.from(name);
      await writeFile(join(root, 'cache', name), bytes);
      files[name] = createHash('sha256').update(bytes).digest('hex');
    }
    await writeFile(join(root, 'conditioning.json'), JSON.stringify({ files, frames: 65, fps: 24 }));
    const plan = join(root, 'plan.json');
    await writeFile(plan, JSON.stringify({ directions: Object.fromEntries(
      ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW'].map(d => [d, { conditioning: root }])) }));
    const result = execFileSync(resolve('node_modules/.bin/tsx'), ['src/cli.ts', 'animate', 'one-to-all',
      '--plan', plan, '--python', 'python3', '--runner', resolve('runtime/experimental/one_to_all/batch.py'), '--check'],
      { encoding: 'utf8', timeout: 15_000 });
    expect(result).toContain('Validated all 8 direction caches; no generation started');
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('extract command preserves inclusive source indices and rejects changed batch frames', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute extract '));
  try {
    const sharp = (await import('sharp')).default;
    const png = await sharp({ create: { width: 384, height: 384, channels: 3, background: '#123456' } }).png().toBuffer();
    const digest = createHash('sha256').update(png).digest('hex');
    const directions = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW'];
    for (const d of directions) {
      const folder = join(root, 'batch', d);
      await mkdir(join(folder, 'output'), { recursive: true });
      const hashes: Record<string, string> = {};
      for (let i = 0; i < 65; i++) {
        const name = `frame_${String(i).padStart(6, '0')}.png`;
        await writeFile(join(folder, 'output', name), png); hashes[name] = digest;
      }
      await writeFile(join(folder, 'output-hashes.json'), JSON.stringify(hashes));
      await writeFile(join(folder, 'state.json'), JSON.stringify({ status: 'complete', frames: 65 }));
      await writeFile(join(folder, 'run.json'), '{}');
    }
    await writeFile(join(root, 'batch/state.json'), JSON.stringify({ status: 'complete', completed: directions }));
    const args = ['src/cli.ts', 'animate', 'one-to-all', 'extract', '--batch', join(root, 'batch'),
      '--python', 'python3', '--runner', resolve('runtime/experimental/one_to_all/cycles.py'), '--start', '32', '--end', '63'];
    const invoke = (output: string) => execFileSync(resolve('node_modules/.bin/tsx'), [...args, '-o', output],
      { encoding: 'utf8', timeout: 15_000, stdio: 'pipe' });
    expect(invoke(join(root, 'cycles'))).toContain('Extracted frames 32..63');
    for (const d of directions) {
      const meta = JSON.parse(await readFile(join(root, 'cycles', d, 'cycle.json'), 'utf8'));
      expect(meta.frames.map((f: any) => f.sourceFrame)).toEqual(Array.from({ length: 32 }, (_, i) => i + 32));
      expect(meta.durationSeconds).toBeCloseTo(32 / 24);
      expect(await readFile(join(root, 'cycles', d, 'frames/000001.png'))).toEqual(png);
    }
    expect(() => invoke(join(root, 'cycles'))).toThrow();
    await writeFile(join(root, 'batch/N/output/frame_000032.png'), 'changed');
    expect(() => invoke(join(root, 'corrupt'))).toThrow();
    expect(await readFile(join(root, 'corrupt/extraction.json')).then(() => true, () => false)).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 20_000);


test('extract requires an explicit valid inclusive range before launching Python', () => {
  const base = ['--batch', 'batch', '--python', 'python3', '--runner', 'cycles.py', '-o', 'cycles'];
  for (const range of [[], ['--start', '3', '--end', '3'], ['--start=-1', '--end', '5'],
    ['--start', '1', '--end', '65'], ['--start', '1.5', '--end', '5']]) {
    expect(() => oneToAllCycleInvocation([...base, ...range])).toThrow('at least two');
  }
  expect(oneToAllCycleInvocation([...base, '--start', '0', '--end', '64']).args.slice(-4))
    .toEqual(['--start', '0', '--end', '64']);
});
