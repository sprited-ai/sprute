import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdir,open,unlink,rename} from 'node:fs/promises';
import {join} from 'node:path';
import type {ResolvedConfig} from '../config.js';
const digest=(b:Buffer|string)=>createHash('sha256').update(b).digest('hex');

/** Completed standing outputs only. A failed/uncertain attempt is never retried implicitly. */
export async function cachedCharacterBuild(config:ResolvedConfig, build:()=>Promise<void>) {
 if (!config.name) throw new Error('Cached character requires a stable name');
 const {preview,animation,seed,seedRolled,...settings}=config;
 const inputKey=async()=>digest(JSON.stringify({version:1,settings,seed:seedRolled?'random':seed,
  ...(config.fixedDirections ? {fixedDirections:await Promise.all(Object.entries(config.fixedDirections).sort(([a],[b])=>a.localeCompare(b)).map(async([d,p])=>[d,digest(await readFile(p))]))} : {}),
  reference:config.reference?digest(await readFile(config.reference)):null,
  template:digest(await readFile(config.template.image))}));
 const key=await inputKey();
 await mkdir(config.output,{recursive:true});
 const receipt=join(config.output,`${config.name}.build.json`),lockPath=receipt+'.lock';
 const lock=await open(lockPath,'wx').catch((error:NodeJS.ErrnoException)=>{
  if(error.code==='EEXIST')throw new Error(`Character build is locked: ${lockPath}. Check its owning process before removing a stale lock.`);
  throw error;
 });
 try {
  await lock.writeFile(JSON.stringify({pid:process.pid}));
  let saved;
  try{saved=JSON.parse(await readFile(receipt,'utf8'));}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
  if(saved){
   if(saved.version!==1||saved.key!==key||saved.status!=='complete')throw new Error(`Saved character is changed or unfinished: ${receipt}. Choose a new output folder; no generation started.`);
   if(!saved.files||typeof saved.files!=='object')throw new Error('Invalid character receipt');
   for(const suffix of ['spritesheet.png','turntable.webp','entity.json','preview.html']){
    const name=`${config.name}.${suffix}`;
    if(typeof saved.files[name]!=='string'||digest(await readFile(join(config.output,name)))!==saved.files[name])throw new Error(`Saved character output changed: ${name}; no generation started.`);
   }
   return {reused:true};
  }
  // Preserve existing unjournaled characters rather than overwriting them.
  for(const suffix of ['spritesheet.png','turntable.webp','entity.json','preview.html']){
   try{await readFile(join(config.output,`${config.name}.${suffix}`));throw new Error('Existing character has no build receipt; choose a new output folder.');}
   catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
  }
  await writeFile(receipt,JSON.stringify({version:1,key,status:'started'}),{flag:'wx'});
  await build();
  if(await inputKey()!==key)throw new Error('Character inputs changed during generation; outputs are preserved but not marked reusable.');
  const files:Record<string,string>={};
  for(const suffix of ['spritesheet.png','turntable.webp','entity.json','preview.html']){
   const name=`${config.name}.${suffix}`;files[name]=digest(await readFile(join(config.output,name)));
  }
  const temp=receipt+'.tmp';
  await writeFile(temp,JSON.stringify({version:1,key,status:'complete',files},null,2)+'\n',{flag:'wx'});
  await rename(temp,receipt);
  return {reused:false};
 }finally{await lock.close();await unlink(lockPath);}
}
