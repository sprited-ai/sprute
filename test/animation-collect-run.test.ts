import { test, expect } from 'vitest';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { SPIN_ORDER } from '../src/core/extract.js';
import { collectAnimationRun } from '../src/node/animation-collect-run.js';

test('collects completed directions, resumes remaining downloads, verifies reused bytes and never posts',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-collect-run-'));let all=false,downloads=0;const requests:string[]=[];
 const server=createServer((req,res)=>{
  requests.push(req.method!);const url=new URL(req.url!,'http://local');
  if(url.pathname==='/view'){downloads++;res.end('video-'+url.searchParams.get('filename'));return;}
  if(url.pathname==='/queue'){res.end(JSON.stringify({queue_running:[],queue_pending:SPIN_ORDER.slice(1).map(d=>[0,d])}));return;}
  const d=url.pathname.split('/').pop();res.end(JSON.stringify(all||d==='S'?{[d!]:{status:{status_str:'success',completed:true},outputs:{'15':{gifs:[{filename:d+'.mp4',type:'output',subfolder:''}]}}}}:{}));
 });await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));const url=`http://127.0.0.1:${(server.address() as any).port}/`;
 try{
  await writeFile(join(root,'run.json'),JSON.stringify({version:1,server:url,views:SPIN_ORDER.map(direction=>({direction,workflow:`${direction}.workflow.json`,sha256:'a'.repeat(64)}))}));
  for(const d of SPIN_ORDER)await writeFile(join(root,`${d}.job.json`),JSON.stringify({version:1,server:url,jobId:d,workflowSha256:'a'.repeat(64)}));
  const partial=await collectAnimationRun(root);expect(partial.allComplete).toBe(false);expect(downloads).toBe(1);expect(partial.views[1].state).toBe('queued');
  all=true;expect((await collectAnimationRun(root)).allComplete).toBe(true);expect(downloads).toBe(8);
  const count=requests.length;const reused=await collectAnimationRun(root);expect(reused.allComplete).toBe(true);expect(requests.length).toBe(count);
  const file=join(root,'results/S/animation.mp4');const bytes=await readFile(file);bytes[0]^=255;await writeFile(file,bytes);
  await expect(collectAnimationRun(root)).rejects.toThrow('hash mismatch');expect(requests.length).toBe(count);
  expect(new Set(requests)).toEqual(new Set(['GET']));
 }finally{await new Promise<void>(r=>server.close(()=>r()));await rm(root,{recursive:true,force:true});}
});
