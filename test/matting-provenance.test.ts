import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { mkdtemp, rm, appendFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { createImage } from '../src/core/image.js';
vi.mock('../src/core/toonout.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/core/toonout.js')>();
  const fixture = Buffer.from('synthetic-model-for-provenance-test');
  return { ...actual, TOONOUT_MODEL_BYTES: fixture.length, TOONOUT_MODEL_SHA256: createHash('sha256').update(fixture).digest('hex') };
});
const state = vi.hoisted(() => ({ mutate: false, creates: [] as string[], runs: [] as string[] }));
vi.mock('onnxruntime-node', () => {
  const ort = {
    env: { versions: { node: 'test-runtime-1' } },
    Tensor: class {},
    InferenceSession: { create: async (path: string, options: { executionProviders: string[] }) => {
      const ep = options.executionProviders[0]; state.creates.push(ep);
      if (state.mutate) await appendFile(path, 'changed');
      return { run: async () => {
        state.runs.push(ep);
        if (ep === 'webgpu') throw new Error('test WebGPU run failure');
        return { mask: { data: new Float32Array(1024 * 1024).fill(.8) } };
      } };
    } },
  };
  return { default: ort, ...ort };
});
const bytes = Buffer.from('synthetic-model-for-provenance-test');
let root: string;
beforeEach(async () => {
  vi.resetModules(); state.mutate = false; state.creates = []; state.runs = [];
  root = await mkdtemp(join(tmpdir(), 'sprute-provenance-'));
  vi.stubEnv('SPRUTE_CACHE_DIR', root);
  vi.stubGlobal('fetch', vi.fn(async () => new Response(bytes)));
});
afterEach(async () => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); await rm(root, { recursive: true, force: true }); });

test('records the successful fallback session and exact model hash; cached reuse retains independent provenance', async () => {
  const { localToonoutMattingWithProvenance } = await import('../src/node/matting-local.js');
  const input = createImage(2, 2, [80, 90, 100, 255]);
  const first = await localToonoutMattingWithProvenance([input]);
  expect(first.images[0]).toMatchObject({ width: 2, height: 2 });
  expect(first.provenance.model).toEqual({ file: 'birefnet-toonout-fp16.onnx', bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
  expect(first.provenance.runtime).toMatchObject({ onnxruntime: 'test-runtime-1', executionProvider: 'cpu' });
  expect(JSON.stringify(first.provenance)).not.toContain(root);
  first.provenance.runtime.executionProvider = 'altered-by-caller';
  const second = await localToonoutMattingWithProvenance([input]);
  expect(second.provenance.runtime.executionProvider).toBe('cpu');
  expect(state.creates).toEqual(['webgpu', 'cpu']);
  expect(state.runs).toEqual(['webgpu', 'cpu', 'cpu']);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('does not assign a model digest when the file changes during session loading', async () => {
  state.mutate = true;
  const { localToonoutMattingWithProvenance } = await import('../src/node/matting-local.js');
  await expect(localToonoutMattingWithProvenance([createImage(2, 2)])).rejects.toThrow('model changed while loading');
  expect(state.runs).toEqual([]);
});
