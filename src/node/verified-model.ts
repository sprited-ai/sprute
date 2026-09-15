import { createReadStream, createWriteStream } from 'node:fs';
import { mkdir, stat, link, rm } from 'node:fs/promises';
import { dirname } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { Readable, Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';

/** Never publish partial weights or overwrite an existing model. */
export async function ensureVerifiedModel(file: string, expected: { url: string; bytes: number; sha256: string }): Promise<string> {
  async function verify() {
    const before = await stat(file), hash = createHash('sha256');
    if (before.size !== expected.bytes) throw new Error(`Model size mismatch; existing file left unchanged: ${file}`);
    for await (const chunk of createReadStream(file)) hash.update(chunk);
    const after = await stat(file);
    if (before.ino !== after.ino || before.dev !== after.dev || before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ctimeMs !== after.ctimeMs || hash.digest('hex') !== expected.sha256) throw new Error(`Model hash mismatch or file changed; existing file left unchanged: ${file}`);
  }
  try { await verify(); return file; } catch (error: any) { if (error.code !== 'ENOENT') throw error; }
  await mkdir(dirname(file), { recursive: true });
  const temporary = `${file}.${randomUUID()}.part`;
  try {
    console.error(`Downloading verified model (${expected.bytes} bytes) to ${file}`);
    const response = await fetch(expected.url);
    if (!response.ok || !response.body) throw new Error(`Model download failed: ${response.status}`);
    let bytes = 0;
    const hash = createHash('sha256');
    const check = new Transform({ transform(chunk, _encoding, done) {
      bytes += chunk.length;
      if (bytes > expected.bytes) return done(new Error('Model download exceeds expected size'));
      hash.update(chunk); done(null, chunk);
    } });
    await pipeline(Readable.fromWeb(response.body as any), check, createWriteStream(temporary, { flags: 'wx' }));
    if (bytes !== expected.bytes || hash.digest('hex') !== expected.sha256) throw new Error('Model download failed size/SHA256 verification');
    try { await link(temporary, file); }
    catch (error: any) { if (error.code !== 'EEXIST') throw error; await verify(); }
    return file;
  } finally { await rm(temporary, { force: true }); }
}
