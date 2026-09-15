import { createHash } from 'node:crypto';
import { open, readFile, realpath, stat, mkdir, mkdtemp, rename, rmdir, rm } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { parseArgs } from 'node:util';
import { SPIN_ORDER } from '../core/extract.js';
import { baseUrl } from './comfy-animation.js';
import { submitComfyAnimation } from './comfy-submit.js';
const hash = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
async function durable(path: string, bytes: string | Buffer) {
  const file = await open(path, 'wx', 0o600);
  try { await file.writeFile(bytes); await file.sync(); } finally { await file.close(); }
}
async function bounded(path: string) {
  if ((await stat(path)).size > 1024 * 1024) throw new Error('Run file exceeds 1 MiB');
  return readFile(path);
}

/** Resume unattempted directions; an attempt claim can never authorize a second POST. */
export async function submitAnimationPlan(planFolder: string, runFolder: string, server: string) {
  const base = baseUrl(server), run = resolve(runFolder);
  let manifest: any;
  try { manifest = JSON.parse((await bounded(join(run, 'run.json'))).toString('utf8')); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  if (!manifest) {
    const root = await realpath(planFolder);
    const plan = JSON.parse((await bounded(join(root,'plan.json'))).toString('utf8'));
    if (plan.version !== 1 || !['wan-animate2-distill-euler10-v1', 'scail2-unipc40-v1'].includes(plan.profile) || !Array.isArray(plan.views) || plan.views.length !== 8) throw new Error('Expected an eight-view plan-animation plan');
    const workflows: Buffer[] = [];
    for (const [i,d] of SPIN_ORDER.entries()) {
      const view=plan.views[i];
      if (view?.direction!==d || view.workflow!==`${d}.workflow.json`) throw new Error(`Invalid plan direction: ${d}`);
      const path=join(root,view.workflow);
      if (await realpath(path)!==path) throw new Error(`Aliased workflow: ${d}`);
      const bytes=await bounded(path), w=JSON.parse(bytes.toString('utf8'));
      if (hash(bytes)!==view.workflowSha256 || !w || Array.isArray(w) || !Object.keys(w).length || Object.values(w).some((node:any)=>!node||typeof node.class_type!=='string'||!node.inputs||typeof node.inputs!=='object'||Array.isArray(node.inputs))) throw new Error(`Changed or invalid workflow: ${d}`);
      workflows.push(bytes);
    }
    manifest={version:1,server:base.href,createdAt:new Date().toISOString(),views:SPIN_ORDER.map((direction,i)=>({direction,workflow:`${direction}.workflow.json`,sha256:hash(workflows[i])}))};
    await mkdir(dirname(run),{recursive:true});const temp=await mkdtemp(join(dirname(run),'.sprute-run-'));
    try {
      for (let i=0;i<8;i++) await durable(join(temp,manifest.views[i].workflow),workflows[i]);
      await durable(join(temp,'run.json'),JSON.stringify(manifest,null,2)+'\n');
      await mkdir(run);
      try { await rename(temp,run); } catch(error) { await rmdir(run).catch(()=>{});throw error; }
    } finally {await rm(temp,{recursive:true,force:true});}
  }
  if (manifest.version!==1 || manifest.server!==base.href || !Array.isArray(manifest.views)||manifest.views.length!==8) throw new Error('Run does not match server or format. No new job submitted.');
  const canonicalRun = await realpath(run);
  // Check every saved workflow before attempting any remaining direction.
  for(const [i,d] of SPIN_ORDER.entries()) {
    const view=manifest.views[i];if(view?.direction!==d||view.workflow!==`${d}.workflow.json`)throw new Error('Invalid saved run direction');
    const path=join(canonicalRun,view.workflow);
    if(await realpath(path)!==path || hash(await bounded(path))!==view.sha256)throw new Error(`Saved workflow changed: ${d}`);
  }
  const results=[];
  for(const d of SPIN_ORDER) {
    const claim=join(run,`${d}.attempt.json`),journal=join(run,`${d}.job.json`);
    let owner=false;
    try {await durable(claim,JSON.stringify({version:1,direction:d,createdAt:new Date().toISOString()})+'\n');owner=true;}
    catch(error){if((error as NodeJS.ErrnoException).code!=='EEXIST')throw error;}
    if(!owner) {
      try {await stat(journal);}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;results.push({direction:d,state:'unknown',submitted:false,note:'Attempt exists without job journal. Inspect this run; no automatic resubmission.'});break;}
    }
    const result=await submitComfyAnimation(base.href,join(run,`${d}.workflow.json`),journal);
    results.push({direction:d,...result});
    if(result.state==='unknown'||result.state==='failed')break;
  }
  return {run,views:results,allDirectionsVisited:results.length===8,note:'Existing attempts are recovery-only. Keep this run folder; deleting it loses duplicate-submission protection.'};
}

export async function runSubmitAnimationPlan(args:string[]) {
  const {values,positionals}=parseArgs({args,allowPositionals:true,options:{run:{type:'string'},server:{type:'string',default:'http://127.0.0.1:8188'}}});
  if(positionals.length!==1||!values.run)throw new Error('Usage: sprute submit-animation-plan plan-folder --run run-folder --server URL');
  const result=await submitAnimationPlan(positionals[0],values.run,values.server!);console.log(JSON.stringify(result,null,2));
  if(result.views.some(v=>v.state==='unknown'||v.state==='failed'))process.exitCode=2;
}
