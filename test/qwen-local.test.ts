import { test, expect } from 'vitest';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import sharp from 'sharp';
import { runLocalQwenJob } from '../src/node/qwen-local.js';
test('local process logs are retained and failure cannot return a completed result', async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-runner-'));
 try {
  const runner=join(root,'runner.mjs'), job=join(root,'job.json');
  await writeFile(job,'{}');await writeFile(join(root,'state.json'),JSON.stringify({status:'complete',gradEnabled:false}));
  await sharp({create:{width:8,height:8,channels:4,background:'#123456'}}).png().toFile(join(root,'result.png'));
  await writeFile(runner,"console.log('model output'); console.error('diagnostic');");
  const options={python:process.execPath,runner,job,output:root,log:join(root,'success.log')};
  const result=await runLocalQwenJob(options);expect(result.width).toBe(8);
  expect(await readFile(options.log,'utf8')).toContain('diagnostic');
  await writeFile(runner,"console.error('model failed');process.exit(7)");
  await expect(runLocalQwenJob({...options,log:join(root,'failure.log')})).rejects.toThrow('7');
  expect(await readFile(join(root,'failure.log'),'utf8')).toContain('model failed');
 }finally{await rm(root,{recursive:true,force:true});}
});

test('interrupt reaches the model process and waits for its shutdown before rejecting', async () => {
 const root=await mkdtemp(join(tmpdir(),'sprute-interrupt-'));
 const before=process.listenerCount('SIGINT');
 try {
  const runner=join(root,'runner.mjs'),job=join(root,'job.json');
  const ready=join(root,'ready'),stopped=join(root,'stopped');
  await writeFile(job,'{}');
  await writeFile(runner,`import {writeFileSync} from 'node:fs';
process.on('SIGINT',()=>setTimeout(()=>{writeFileSync(${JSON.stringify(stopped)},'shutdown finished');process.exit(0)},80));
writeFileSync(${JSON.stringify(ready)},'ready');setInterval(()=>{},1000);`);
  const pending=runLocalQwenJob({python:process.execPath,runner,job,output:root,log:join(root,'model.log')});
  const rejected=expect(pending).rejects.toThrow('interrupted (SIGINT)');
  const deadline=Date.now()+3000;
  while (true) {
   if (await readFile(ready,'utf8').catch(()=>null)) break;
   if (Date.now()>deadline) { process.emit('SIGTERM'); throw new Error('Fixture did not start'); }
   await new Promise(resolve=>setTimeout(resolve,10));
  }
  process.emit('SIGINT');
  await rejected;
  expect(await readFile(stopped,'utf8')).toBe('shutdown finished');
  expect(process.listenerCount('SIGINT')).toBe(before);
 } finally {await rm(root,{recursive:true,force:true});}
});
