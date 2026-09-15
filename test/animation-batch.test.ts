import { test, expect } from 'vitest';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { SPIN_ORDER } from '../src/core/extract.js';
import { submitAnimationPlan } from '../src/node/animation-batch.js';

test.each(['wan-animate2-distill-euler10-v1','scail2-unipc40-v1'])('%s batch recovers a lost response then submits only unattempted directions, independent of source plan', async(profile)=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-batch-')), plan=join(root,'plan'),run=join(root,'run');await mkdir(plan);
 const views=[];for(const direction of SPIN_ORDER){const bytes=JSON.stringify({'1':{class_type:'Test',inputs:{direction}}});await writeFile(join(plan,`${direction}.workflow.json`),bytes);views.push({direction,workflow:`${direction}.workflow.json`,workflowSha256:createHash('sha256').update(bytes).digest('hex')});}
 await writeFile(join(plan,'plan.json'),JSON.stringify({version:1,profile,views}));
 const ids:string[]=[];let lost=true,claimsAtPost=true;
 const server=createServer(async(req,res)=>{
  if(req.method==='POST'){
   const chunks=[];for await(const c of req)chunks.push(c);const payload=JSON.parse(Buffer.concat(chunks).toString());ids.push(payload.prompt_id);
   const d=payload.prompt['1'].inputs.direction;
   claimsAtPost &&= !!JSON.parse(await readFile(join(run,`${d}.attempt.json`),'utf8')) && JSON.parse(await readFile(join(run,`${d}.job.json`),'utf8')).jobId===payload.prompt_id;
   if(lost){lost=false;req.socket.destroy();return;}res.end(JSON.stringify({prompt_id:payload.prompt_id}));return;
  }
  if(req.url==='/queue')res.end(JSON.stringify({queue_running:ids.map(id=>[0,id]),queue_pending:[]}));else res.end('{}');
 });await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));const url=`http://127.0.0.1:${(server.address() as any).port}`;
 try{
  await expect(submitAnimationPlan(plan,run,url)).rejects.toThrow('Submission not confirmed');expect(ids).toHaveLength(1);
  await rm(plan,{recursive:true});
  const result=await submitAnimationPlan(plan,run,url);expect(result.views).toHaveLength(8);expect(ids).toHaveLength(8);expect(new Set(ids).size).toBe(8);expect(claimsAtPost).toBe(true);
  expect(result.views[0].submitted).toBe(false);
  await submitAnimationPlan(plan,run,url);expect(ids).toHaveLength(8);
  await rm(join(run,'N.job.json'));
  const missing=await submitAnimationPlan(plan,run,url);expect(missing.views.at(-1)?.state).toBe('unknown');expect(ids).toHaveLength(8);
  await expect(submitAnimationPlan(plan,run,url+'/other')).rejects.toThrow('does not match');expect(ids).toHaveLength(8);
 }finally{await new Promise<void>(r=>server.close(()=>r()));await rm(root,{recursive:true,force:true});}
});
