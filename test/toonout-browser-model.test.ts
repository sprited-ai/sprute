import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { createHash, webcrypto } from 'node:crypto';
const fixture = Buffer.from('browser model fixture');
const state = vi.hoisted(() => ({ creates: 0 }));
vi.mock('../src/core/toonout.js', async (original) => ({
  ...await original<typeof import('../src/core/toonout.js')>(),
  TOONOUT_MODEL_BYTES: Buffer.byteLength('browser model fixture'),
  TOONOUT_MODEL_SHA256: createHash('sha256').update('browser model fixture').digest('hex'),
}));
vi.mock('onnxruntime-web', () => {
  const ort = { InferenceSession: { create: async () => { state.creates++; return {}; } } };
  return { default: ort, ...ort };
});
beforeEach(() => { vi.resetModules(); state.creates = 0; vi.stubGlobal('crypto', webcrypto); });
afterEach(() => vi.unstubAllGlobals());

test('browser verifies before caching and revalidates cached bytes without downloading', async () => {
  let saved: Response | undefined;
  const cache = { match: vi.fn(async () => saved?.clone()), put: vi.fn(async (_url: string, response: Response) => { saved = response; }) };
  vi.stubGlobal('caches', { open: async () => cache });
  vi.stubGlobal('fetch', vi.fn(async () => new Response(fixture)));
  await (await import('../src/web/toonout.js')).toonoutMatting([]);
  expect(cache.put).toHaveBeenCalledTimes(1);
  expect(state.creates).toBe(1);
  vi.resetModules();
  await (await import('../src/web/toonout.js')).toonoutMatting([]);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(state.creates).toBe(2);
});

test('browser rejects corrupt download before cache or inference session creation', async () => {
  const cache = { match: async () => undefined, put: vi.fn() };
  vi.stubGlobal('caches', { open: async () => cache });
  vi.stubGlobal('fetch', vi.fn(async () => new Response(Buffer.alloc(fixture.length))));
  await expect((await import('../src/web/toonout.js')).toonoutMatting([])).rejects.toThrow('hash mismatch');
  expect(cache.put).not.toHaveBeenCalled(); expect(state.creates).toBe(0);
});

test('browser rejects truncated cached model without overwriting it or creating a session', async () => {
  const cache = { match: async () => new Response('short'), put: vi.fn() };
  vi.stubGlobal('caches', { open: async () => cache });
  vi.stubGlobal('fetch', vi.fn());
  await expect((await import('../src/web/toonout.js')).toonoutMatting([])).rejects.toThrow('size mismatch');
  expect(fetch).not.toHaveBeenCalled(); expect(cache.put).not.toHaveBeenCalled(); expect(state.creates).toBe(0);
});

test('browser can retry after a failed download without reloading the module', async () => {
  vi.stubGlobal('caches', undefined);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('unavailable', { status: 503 })).mockResolvedValueOnce(new Response(fixture)));
  const api = await import('../src/web/toonout.js');
  await expect(api.toonoutMatting([])).rejects.toThrow('503');
  await expect(api.toonoutMatting([])).resolves.toEqual([]);
  expect(state.creates).toBe(1);
  expect(fetch).toHaveBeenCalledTimes(2);
});
