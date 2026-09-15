import { test, expect } from 'vitest';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { inspectComfyJob, collectComfyAnimation } from '../src/node/comfy-animation.js';

test('recovery is GET-only, distinguishes live/unknown/failed, and sanitizes saved metadata', async () => {
  const requests: string[] = [];
  let mode = 'running';
  const server = createServer((req, res) => {
    requests.push(`${req.method} ${req.url}`);
    res.setHeader('Content-Type', 'application/json');
    if (req.url?.startsWith('/view?')) { res.end(Buffer.from([0,1,2,3])); return; }
    if (req.url === '/queue') { res.end(JSON.stringify({ queue_running: mode === 'running' ? [[0,'job']] : [], queue_pending: mode === 'queued' ? [[0,'job']] : [] })); return; }
    if (mode === 'complete' || mode === 'ambiguous') res.end(JSON.stringify({ job: { prompt: ['SECRET'], status: { status_str: 'success', completed: true }, outputs: {
      '15': { gifs: [{ filename: 'clip.mp4', subfolder: 'nested', type: 'output', fullpath: '/private/SECRET' }] },
      ...(mode === 'ambiguous' ? { '16': { images: [{ filename: 'other.mp4', type: 'output' }] } } : {}),
    } } }));
    else res.end(JSON.stringify(mode === 'failed' ? { job: { status: { status_str: 'error' } } } : {}));
  });
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${(server.address() as any).port}`;
  const root = await mkdtemp(join(tmpdir(), 'sprute-comfy-test-'));
  try {
    for (const state of ['running','queued','unknown','failed']) { mode=state; expect(await collectComfyAnimation(url,'job',join(root,state))).toEqual({state}); }
    expect(await readdir(root)).toEqual([]);
    mode='ambiguous'; await expect(collectComfyAnimation(url,'job',join(root,'result'))).rejects.toThrow('found 2');
    const result = await collectComfyAnimation(url,'job',join(root,'result'),'15');
    expect(result.state).toBe('complete');
    expect([...await readFile(join(root,'result','animation.mp4'))]).toEqual([0,1,2,3]);
    const saved = await readFile(join(root,'result','job.json'),'utf8');
    expect(saved).not.toContain('SECRET'); expect(JSON.parse(saved).reviewStatus).toBe('unreviewed');
    await expect(collectComfyAnimation(url,'job',join(root,'result'),'15')).rejects.toThrow('already exists');
    expect(requests.every(r=>r.startsWith('GET '))).toBe(true);
    expect(requests.some(r=>r.includes('type=output'))).toBe(true);
    await expect(inspectComfyJob(url,'../prompt')).rejects.toThrow('Invalid');
  } finally { await new Promise<void>(r=>server.close(()=>r())); await rm(root,{recursive:true,force:true}); }
});

test('a failed download leaves no output and can be retried with the same job ID', async()=>{
  let fail=true;
  const server=createServer((req,res)=>{
    if(req.url?.startsWith('/view?')) { res.statusCode=fail?503:200;res.end(fail?'unavailable':'video bytes');return; }
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify({job:{status:{status_str:'success'},outputs:{'1':{images:[{filename:'x.mp4',type:'output'}]}}}}));
  });
  await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));
  const url=`http://127.0.0.1:${(server.address() as any).port}`,root=await mkdtemp(join(tmpdir(),'sprute-retry-'));
  try {
    await expect(collectComfyAnimation(url,'job',join(root,'result'))).rejects.toThrow('download failed');
    expect(await readdir(root)).toEqual([]);fail=false;
    expect((await collectComfyAnimation(url,'job',join(root,'result'))).state).toBe('complete');
  } finally { await new Promise<void>(r=>server.close(()=>r()));await rm(root,{recursive:true,force:true}); }
});
