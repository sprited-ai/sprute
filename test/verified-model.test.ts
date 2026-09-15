import { test, expect, vi } from 'vitest';
import { mkdtemp, readFile, writeFile, readdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { ensureVerifiedModel } from '../src/node/verified-model.js';

const bytes = Buffer.from('verified fixture');
const expected = { url: 'https://example.test/pinned/model', bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };

test('verified downloads publish once; matching cache avoids network and corrupt cache is preserved', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-model-')), file = join(root, 'model');
  try {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(bytes)));
    await ensureVerifiedModel(file, expected);
    expect(await readFile(file)).toEqual(bytes);
    await ensureVerifiedModel(file, expected);
    expect(fetch).toHaveBeenCalledTimes(1);
    const corrupt = Buffer.alloc(bytes.length, 42); await writeFile(file, corrupt);
    await expect(ensureVerifiedModel(file, expected)).rejects.toThrow('hash mismatch');
    expect(await readFile(file)).toEqual(corrupt);
    expect(fetch).toHaveBeenCalledTimes(1);
  } finally { vi.unstubAllGlobals(); await rm(root, { recursive: true, force: true }); }
});

test('truncated, oversized, wrong-hash and interrupted downloads leave no final or partial file', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-model-')), file = join(root, 'model');
  try {
    for (const value of [bytes.subarray(1), Buffer.concat([bytes, bytes]), Buffer.alloc(bytes.length)]) {
      vi.stubGlobal('fetch', vi.fn(async () => new Response(value)));
      await expect(ensureVerifiedModel(file, expected)).rejects.toThrow();
      expect(await readdir(root)).toEqual([]);
    }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new ReadableStream({ start(c) { c.enqueue(bytes.subarray(0, 2)); c.error(new Error('connection lost')); } }))));
    await expect(ensureVerifiedModel(file, expected)).rejects.toThrow('connection lost');
    expect(await readdir(root)).toEqual([]);
  } finally { vi.unstubAllGlobals(); await rm(root, { recursive: true, force: true }); }
});

test('concurrent downloader reuses verified winner and refuses conflicting winner without overwriting it', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-model-')), file = join(root, 'model');
  try {
    vi.stubGlobal('fetch', vi.fn(async () => { await writeFile(file, bytes); return new Response(bytes); }));
    await ensureVerifiedModel(file, expected);
    expect(await readdir(root)).toEqual(['model']);
    await rm(file);
    const other = Buffer.alloc(bytes.length, 33);
    vi.stubGlobal('fetch', vi.fn(async () => { await writeFile(file, other); return new Response(bytes); }));
    await expect(ensureVerifiedModel(file, expected)).rejects.toThrow('hash mismatch');
    expect(await readFile(file)).toEqual(other);
    expect(await readdir(root)).toEqual(['model']);
  } finally { vi.unstubAllGlobals(); await rm(root, { recursive: true, force: true }); }
});
