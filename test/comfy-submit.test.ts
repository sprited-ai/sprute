import { test, expect } from 'vitest';
import { createServer } from 'node:http';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { submitComfyAnimation } from '../src/node/comfy-submit.js';

for (const mode of ['success', 'disconnect', 'rejected', 'different-id']) {
  test(`submission journal survives ${mode} and recovery never posts again`, async () => {
    const root = await mkdtemp(join(tmpdir(), 'sprute-submit-'));
    const workflow = join(root, 'workflow.json'), journal = join(root, 'job.json');
    await writeFile(workflow, JSON.stringify({ '1': { class_type: 'Test', inputs: { caption: 'PRIVATE CAPTION' } } }));
    let posts = 0, acceptedId = '', journalExistsAtPost = false;
    const server = createServer(async (req, res) => {
      if (req.method === 'POST') {
        posts++;
        const chunks = []; for await (const chunk of req) chunks.push(chunk);
        const payload = JSON.parse(Buffer.concat(chunks).toString());
        acceptedId = payload.prompt_id;
        journalExistsAtPost = JSON.parse(await readFile(journal, 'utf8')).jobId === acceptedId;
        if (mode === 'disconnect') { req.socket.destroy(); return; }
        if (mode === 'rejected') { res.writeHead(400); res.end('{"error":"PRIVATE CAPTION"}'); return; }
        res.end(JSON.stringify({ prompt_id: mode === 'different-id' ? 'other' : acceptedId })); return;
      }
      if (req.url === '/queue') res.end(JSON.stringify({ queue_running: mode === 'rejected' ? [] : [[0, acceptedId]], queue_pending: [] }));
      else res.end('{}');
    });
    await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
    const url = `http://127.0.0.1:${(server.address() as any).port}`;
    try {
      if (mode === 'success') expect((await submitComfyAnimation(url, workflow, journal)).submitted).toBe(true);
      else await expect(submitComfyAnimation(url, workflow, journal)).rejects.toThrow('Submission not confirmed');
      expect(journalExistsAtPost).toBe(true);
      expect(await readFile(journal, 'utf8')).not.toContain('PRIVATE');
      // Recovery does not depend on the original workflow still being present.
      await rm(workflow);
      const result = await submitComfyAnimation(url, workflow, journal);
      expect(result.submitted).toBe(false);
      expect(result.jobId).toBe(acceptedId);
      expect(result.state).toBe(mode === 'rejected' ? 'unknown' : 'running');
      expect(posts).toBe(1);
      await expect(submitComfyAnimation(url + '/different', workflow, journal)).rejects.toThrow('does not match');
      expect(posts).toBe(1);
    } finally {
      await new Promise<void>(r => server.close(() => r()));
      await rm(root, { recursive: true, force: true });
    }
  });
}

test('malformed journals and UI workflows do not submit', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-invalid-submit-'));
  try {
    const workflow = join(root, 'workflow.json'), journal = join(root, 'job.json');
    await writeFile(workflow, JSON.stringify({ nodes: [] }));
    await expect(submitComfyAnimation('http://127.0.0.1:1', workflow, journal)).rejects.toThrow('API workflow');
    await writeFile(journal, '{');
    await expect(submitComfyAnimation('http://127.0.0.1:1', workflow, journal)).rejects.toThrow();
    expect(await readFile(journal, 'utf8')).toBe('{');
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('two simultaneous invocations sharing one journal submit at most once', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-race-'));
  const workflow = join(root, 'workflow.json'), journal = join(root, 'job.json');
  await writeFile(workflow, JSON.stringify({ '1': { class_type: 'Test', inputs: {} } }));
  let posts = 0;
  const server = createServer(async (req, res) => {
    if (req.method === 'POST') {
      posts++;
      const chunks = []; for await (const chunk of req) chunks.push(chunk);
      res.end(JSON.stringify({ prompt_id: JSON.parse(Buffer.concat(chunks).toString()).prompt_id }));
    } else res.end('{}');
  });
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${(server.address() as any).port}`;
  try {
    const results = await Promise.allSettled([submitComfyAnimation(url, workflow, journal), submitComfyAnimation(url, workflow, journal)]);
    expect(posts).toBe(1);
    expect(results.some(r => r.status === 'fulfilled' && r.value.submitted)).toBe(true);
    expect(JSON.parse(await readFile(journal, 'utf8')).jobId).toMatch(/^[a-f0-9-]{36}$/);
  } finally {
    await new Promise<void>(r => server.close(() => r()));
    await rm(root, { recursive: true, force: true });
  }
});
