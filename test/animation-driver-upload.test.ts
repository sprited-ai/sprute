import { test, expect } from 'vitest';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { SPIN_ORDER } from '../src/core/extract.js';
import { uploadAnimationDrivers } from '../src/node/animation-driver-upload.js';

test.each([false,true])('installs drivers (masks=%s) with recovery and usable paths; refuses conflicts and tampering', async (withMasks) => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-driver-upload-'));
  const stored = new Map<string, Buffer>(); let posts = 0, reads = 0, lose = true;
  const paths: string[] = [];
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url!, 'http://local'); paths.push(url.pathname);
      if (req.method === 'GET' && url.pathname === '/view') {
        reads++; const value = stored.get(url.searchParams.get('filename')!); res.statusCode = value ? 200 : 404; res.end(value); return;
      }
      if (req.method === 'POST' && url.pathname === '/upload/image') {
        posts++; const chunks: Buffer[] = []; for await (const chunk of req) chunks.push(Buffer.from(chunk));
        const form = await new Request('http://local', { method: 'POST', headers: { 'content-type': req.headers['content-type']! }, body: Buffer.concat(chunks) }).formData();
        expect(form.get('overwrite')).toBe('false'); expect(form.get('type')).toBe('input');
        const file = form.get('image') as File; stored.set(file.name, Buffer.from(await file.arrayBuffer()));
        if (lose && (!withMasks || file.name.endsWith('-mask.mkv'))) { lose = false; res.destroy(); return; }
        res.end(JSON.stringify({ name: file.name, subfolder: form.get('subfolder'), type: 'input' })); return;
      }
      res.statusCode = 400; res.end();
    } catch (e) { res.statusCode = 500; res.end(String(e)); }
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening'); const url = `http://127.0.0.1:${(server.address() as any).port}`;
  try {
    const views: Record<string, unknown> = {}; const hash = (b: Buffer) => createHash('sha256').update(b).digest('hex');
    // This unit fixture only tests the advertised MP4 header check, not decoding.
    const video = Buffer.from('0000ftypisom0000');
    const mask = Buffer.from([0x1a,0x45,0xdf,0xa3,0]); // Header fixture, not a decodable video.
    const count = withMasks ? 24 : 16;
    for (const [i, d] of SPIN_ORDER.entries()) {
      await mkdir(join(root, d));
      const png = await sharp({ create: { width: 512, height: 512, channels: 3, background: { r: i * 20, g: 30, b: 90 } } }).png().toBuffer();
      await writeFile(join(root, d, 'driver.mp4'), video); await writeFile(join(root, d, 'first.png'), png);
      if (withMasks) await writeFile(join(root,d,'mask.mkv'),mask);
      views[d] = { ...(withMasks ? {maskVideo:`${d}/mask.mkv`,maskVideoSha256:hash(mask)} : {}), video: `${d}/driver.mp4`, firstFrame: `${d}/first.png`, videoSha256: hash(video), firstFrameSha256: hash(png), caption: `${d} mannequin` };
    }
    await writeFile(join(root, 'bundle.json'), JSON.stringify({ version: 1, profile: 'quaternius-standard-walk-8dir-v1', pathScope: 'local-bundle-relative', views }));
    await expect(uploadAnimationDrivers(root, url, '/ComfyUI/input')).rejects.toThrow(/not verified/); expect(posts).toBe(withMasks ? 3 : 1);
    const result = await uploadAnimationDrivers(root, url, '/ComfyUI/input/'); expect(posts).toBe(count);
    expect(result.installation.files[0].status).toBe('reused');
    for (const d of SPIN_ORDER) {
      expect(result.views[d].video).toBe(`/ComfyUI/input/${result.installation.inputPrefix}/${d}.mp4`);
      if(withMasks) expect(result.views[d].maskVideo).toBe(`/ComfyUI/input/${result.installation.inputPrefix}/${d}-mask.mkv`);
      expect(result.views[d].firstFrame).toBe(`${result.installation.inputPrefix}/${d}.png`);
    }
    expect((await uploadAnimationDrivers(root, url, '/ComfyUI/input')).installation.files.every(f => f.status === 'reused')).toBe(true); expect(posts).toBe(count);
    stored.delete('S.mp4');
    stored.set(withMasks ? 'SW-mask.mkv' : 'SW.mp4', Buffer.from('conflict'));
    await expect(uploadAnimationDrivers(root, url, '/ComfyUI/input')).rejects.toThrow(/Remote driver conflict/); expect(posts).toBe(count);
    await writeFile(join(root, withMasks ? 'W/mask.mkv' : 'W/driver.mp4'), 'changed'); const before = reads;
    await expect(uploadAnimationDrivers(root, url, '/ComfyUI/input')).rejects.toThrow(/hash mismatch/); expect(reads).toBe(before);
    expect(paths.every(p => p === '/view' || p === '/upload/image')).toBe(true);
  } finally { server.close(); await once(server, 'close'); await rm(root, { recursive: true, force: true }); }
});
