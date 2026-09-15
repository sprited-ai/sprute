import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { readFile, realpath, stat, lstat } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { SPIN_ORDER } from '../core/extract.js';
import { baseUrl, collectComfyAnimation } from './comfy-animation.js';

/** GET-only collection of a saved batch, with verified local video reuse. */
export async function collectAnimationRun(runFolder: string) {
  const root=await realpath(runFolder);
  async function json(file:string) {
    const path=join(root,file);
    if(await realpath(path)!==path)throw new Error(`Aliased run file: ${file}`);
    if((await stat(path)).size>1024*1024)throw new Error(`Run metadata exceeds 1 MiB: ${file}`);
    return JSON.parse(await readFile(path,'utf8'));
  }
  const manifest=await json('run.json');
  if(manifest.version!==1||typeof manifest.server!=='string'||!Array.isArray(manifest.views)||manifest.views.length!==8)throw new Error('Expected submit-animation-plan run folder');
  const server=baseUrl(manifest.server).href;
  const jobs: ({jobId:string}|{state:string})[]=[];
  for(const [i,d] of SPIN_ORDER.entries()) {
    const view=manifest.views[i];if(view?.direction!==d||view.workflow!==`${d}.workflow.json`)throw new Error(`Invalid run direction: ${d}`);
    let job:any;
    try {job=await json(`${d}.job.json`);}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
    if(!job){
      let attempted=false;try{await lstat(join(root,`${d}.attempt.json`));attempted=true;}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
      jobs.push({state:attempted?'unknown':'unattempted'});continue;
    }
    if(job.version!==1||job.server!==server||job.workflowSha256!==view.sha256||typeof job.jobId!=='string'||!/^[a-zA-Z0-9_-]{1,128}$/.test(job.jobId))throw new Error(`Invalid job journal: ${d}`);
    jobs.push({jobId:job.jobId});
  }
  const resultsRoot=join(root,'results');
  try {if(await realpath(resultsRoot)!==resultsRoot)throw new Error('Results directory is aliased');}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
  const views=[];
  for(const [i,d] of SPIN_ORDER.entries()) {
    const job=jobs[i];if('state' in job){views.push({direction:d,state:job.state});continue;}
    const folder=join(resultsRoot,d);
    let saved:any;
    try {saved=await json(`results/${d}/job.json`);}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
    if(saved){
      if(saved.version!==1||saved.state!=='complete'||saved.jobId!==job.jobId||!['animation.mp4','animation.webm'].includes(saved.file)||!Number.isSafeInteger(saved.bytes)||saved.bytes<=0||saved.bytes>512*1024*1024||typeof saved.sha256!=='string'||!/^[a-f0-9]{64}$/.test(saved.sha256))throw new Error(`Invalid collected metadata: ${d}`);
      const file=join(folder,saved.file);
      if(await realpath(file)!==file||(await stat(file)).size!==saved.bytes)throw new Error(`Collected video changed: ${d}`);
      const digest=createHash('sha256');for await(const chunk of createReadStream(file))digest.update(chunk);
      if(digest.digest('hex')!==saved.sha256)throw new Error(`Collected video hash mismatch: ${d}`);
      views.push({direction:d,jobId:job.jobId,state:'complete',reused:true,file});continue;
    }
    const result=await collectComfyAnimation(server,job.jobId,folder);
    views.push({direction:d,jobId:job.jobId,...result,reused:false});
  }
  return {run:root,views,allComplete:views.every(v=>v.state==='complete'),submittedJobs:0,reviewStatus:'unreviewed'};
}

export async function runCollectAnimationRun(args:string[]) {
  const {positionals}=parseArgs({args,allowPositionals:true,options:{}});
  if(positionals.length!==1)throw new Error('Usage: sprute collect-animation-run run-folder');
  const result=await collectAnimationRun(positionals[0]);console.log(JSON.stringify(result,null,2));
  if(!result.allComplete)process.exitCode=result.views.some(v=>v.state==='failed')?1:2;
}
