import { open, readFile } from 'node:fs/promises';
import { randomUUID, createHash } from 'node:crypto';
import { parseArgs } from 'node:util';
import { baseUrl, inspectComfyJob } from './comfy-animation.js';

/** Persist the ID before POST. An existing journal is exclusively a recovery path. */
export async function submitComfyAnimation(server: string, workflowPath: string, journalPath: string) {
  const base = baseUrl(server);
  let existing: string | undefined;
  try { existing = await readFile(journalPath, 'utf8'); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  if (existing !== undefined) {
    const saved = JSON.parse(existing);
    if (saved.version !== 1 || saved.server !== base.href || typeof saved.jobId !== 'string') throw new Error('Journal does not match this server or format. No job submitted.');
    return { jobId: saved.jobId as string, submitted: false, state: (await inspectComfyJob(server, saved.jobId)).state };
  }
  const bytes = await readFile(workflowPath);
  if (bytes.length > 8 * 1024 * 1024) throw new Error('Workflow exceeds 8 MiB.');
  const prompt = JSON.parse(bytes.toString('utf8'));
  if (!prompt || Array.isArray(prompt) || typeof prompt !== 'object' || !Object.keys(prompt).length ||
      Object.values(prompt).some((node: any) => !node || typeof node.class_type !== 'string' || !node.inputs || typeof node.inputs !== 'object' || Array.isArray(node.inputs))) {
    throw new Error('Expected a ComfyUI API workflow: node IDs mapped to class_type and inputs.');
  }
  const jobId = randomUUID();
  // Exclusive creation also prevents concurrent invocations from posting twice.
  // Leave this record intact on every failure, including uncertain network errors.
  const handle = await open(journalPath, 'wx', 0o600);
  try {
    await handle.writeFile(JSON.stringify({ version: 1, server: base.href, jobId, workflowSha256: createHash('sha256').update(bytes).digest('hex'), createdAt: new Date().toISOString() }, null, 2) + '\n');
    await handle.sync();
  } finally { await handle.close(); }
  let response: Response;
  try {
    response = await fetch(new URL('prompt', base), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt, prompt_id: jobId }), redirect: 'error', signal: AbortSignal.timeout(30_000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json() as any;
    if (result.prompt_id !== jobId) throw new Error('Server did not honor the saved prompt ID. Check ComfyUI history manually; this server is unsupported.');
  } catch (error) {
    throw new Error(`Submission not confirmed for ${jobId}. Keep ${journalPath}; rerunning only checks this ID and never resubmits. ${error instanceof Error ? error.message : 'Request failed'}`);
  }
  return { jobId, submitted: true, state: 'submitted' as const };
}

export async function runSubmitAnimation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    server: { type: 'string', default: 'http://127.0.0.1:8188' }, journal: { type: 'string' },
  } });
  if (positionals.length !== 1 || !values.journal) throw new Error('Usage: sprute submit-animation workflow-api.json --journal job.json [--server URL]');
  const result = await submitComfyAnimation(values.server!, positionals[0], values.journal);
  console.log(`Job ${result.jobId}: ${result.state}. ${result.submitted ? 'Submitted once.' : 'Recovery only; no new job submitted.'}`);
  console.log(`Collect with: sprute collect-animation --job ${result.jobId} --server ${JSON.stringify(values.server)} -o new-folder`);
  if (!result.submitted && result.state !== 'complete') process.exitCode = result.state === 'failed' ? 1 : 2;
}
