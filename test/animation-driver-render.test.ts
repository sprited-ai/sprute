import {mkdtemp, writeFile, readFile, rm, access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {afterEach, expect, test} from 'vitest';
import {renderAnimationDrivers, runRenderAnimationDrivers} from '../src/node/animation-driver-render.js';

const roots: string[] = [];
async function fixture(code: number) {
  const root = await mkdtemp(join(tmpdir(), 'sprute render ')); roots.push(root);
  const executable = join(root, 'fake blender');
  const record = join(root, 'arguments.json');
  await writeFile(executable, `#!/usr/bin/env node\nimport fs from 'node:fs';\nfs.writeFileSync(${JSON.stringify(record)}, JSON.stringify(process.argv.slice(2)));\nprocess.exit(${code});\n`, {mode: 0o755});
  // Make the fake executable's module type independent of the user's working directory.
  await writeFile(join(root, 'package.json'), '{"type":"module"}');
  return {root, executable, record};
}
afterEach(async () => { await Promise.all(roots.splice(0).map(p => rm(p, {recursive: true, force: true}))); });

test('launches a separate executable without shell interpretation and preserves spaced paths', async () => {
  const f = await fixture(0);
  const model = join(f.root, 'model $(touch SHOULD_NOT_EXIST).glb');
  const output = join(f.root, 'new output');
  await runRenderAnimationDrivers([model, '-o', output, '--blender', f.executable, '--ffmpeg', '/tools/ffmpeg with spaces', '--scail-masks']);
  const args = JSON.parse(await readFile(f.record, 'utf8')) as string[];
  expect(args.slice(0, 5)).toEqual(['--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1']);
  await expect(access(args[6])).resolves.toBeUndefined();
  expect(args.slice(7)).toEqual(['--', '--model', resolve(model), '--output', resolve(output), '--ffmpeg', '/tools/ffmpeg with spaces', '--scail-masks']);
  await expect(access(output)).rejects.toThrow(); // The wrapper leaves output ownership to Blender.
});

test('reports render failure and missing executable instead of claiming completion', async () => {
  const f = await fixture(9);
  await expect(renderAnimationDrivers('model.glb', join(f.root, 'out'), {blender: f.executable})).rejects.toThrow('exit 9');
  const args = JSON.parse(await readFile(f.record, 'utf8'));
  expect(args).not.toContain('--scail-masks');
  await expect(renderAnimationDrivers(undefined, join(f.root, 'out'), {blender: f.executable, downloadTemplate: true})).rejects.toThrow('exit 9');
  const failedDownload = JSON.parse(await readFile(f.record, 'utf8')) as string[];
  expect(failedDownload[6]).toMatch(/download-template\.py$/);
  await expect(access(resolve(failedDownload.at(-1)!, '..'))).rejects.toThrow();
  await expect(renderAnimationDrivers('model.glb', join(f.root, 'out'), {blender: join(f.root, 'missing')})).rejects.toThrow('Cannot start Blender');
});

test('automatic template uses Blender for download and render, cleans its temporary file, and rejects conflicting arguments', async () => {
  const f = await fixture(0);
  await writeFile(f.executable, `#!/usr/bin/env node\nimport fs from 'node:fs';\nconst path=${JSON.stringify(f.record)}; const calls=fs.existsSync(path)?JSON.parse(fs.readFileSync(path,'utf8')):[]; calls.push(process.argv.slice(2)); fs.writeFileSync(path,JSON.stringify(calls));\n`, {mode:0o755});
  await runRenderAnimationDrivers(['--download-template', '--scail-masks', '-o', join(f.root, 'out'), '--blender', f.executable]);
  const calls = JSON.parse(await readFile(f.record, 'utf8')) as string[][];
  expect(calls).toHaveLength(2);
  expect(calls[0][6]).toMatch(/download-template\.py$/);
  expect(calls[1][6]).toMatch(/render-walk-drivers\.py$/);
  const model = calls[0].at(-1)!;
  expect(calls[1][calls[1].indexOf('--model')+1]).toBe(model);
  expect(calls[1]).toContain('--scail-masks');
  await expect(access(model)).rejects.toThrow();
  await expect(access(resolve(model, '..'))).rejects.toThrow();
  await expect(runRenderAnimationDrivers(['model.glb','--download-template','-o','out'])).rejects.toThrow('Usage');
  await expect(runRenderAnimationDrivers(['--download-template','-o',f.root,'--blender',f.executable])).rejects.toThrow('already exists');
  expect(JSON.parse(await readFile(f.record,'utf8'))).toHaveLength(2);
});
