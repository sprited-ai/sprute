import {test,expect} from 'vitest';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {resolveConfig} from '../src/config.js';
import {cachedCharacterBuild} from '../src/node/character-cache.js';
test('completed outputs are reused across rolled seeds; tampering never calls generation',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-cache-'));let calls=0;
 try{
  const cfg=resolveConfig({name:'hero',output:root},root);
  const build=async()=>{calls++;for(const suffix of ['spritesheet.png','turntable.webp','entity.json','preview.html'])await writeFile(join(root,'hero.'+suffix),suffix);};
  expect(await cachedCharacterBuild(cfg,build)).toEqual({reused:false});
  expect(await cachedCharacterBuild({...cfg,seed:cfg.seed+1,preview:{open:false}},build)).toEqual({reused:true});
  await writeFile(join(root,'hero.spritesheet.png'),'changed');
  await expect(cachedCharacterBuild(cfg,build)).rejects.toThrow('changed');expect(calls).toBe(1);
 }finally{await rm(root,{recursive:true,force:true});}
});
test('uncertain failed build is preserved and not silently resubmitted',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-failed-'));let calls=0;
 try{
  const cfg=resolveConfig({name:'hero',output:root,seed:42},root);
  const build=async()=>{calls++;throw new Error('provider disconnected');};
  await expect(cachedCharacterBuild(cfg,build)).rejects.toThrow('disconnected');
  await expect(cachedCharacterBuild(cfg,build)).rejects.toThrow('unfinished');expect(calls).toBe(1);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('changing reference during generation never publishes a reusable receipt',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-input-race-'));let calls=0;
 try{
  const reference=join(root,'source.png');await writeFile(reference,'original');
  const cfg=resolveConfig({name:'hero',output:root,seed:42,reference},root);
  await expect(cachedCharacterBuild(cfg,async()=>{
   calls++;await writeFile(reference,'edited while building');
   for(const suffix of ['spritesheet.png','turntable.webp','entity.json','preview.html'])await writeFile(join(root,'hero.'+suffix),suffix);
  })).rejects.toThrow('changed during generation');
  await writeFile(reference,'original');
  await expect(cachedCharacterBuild(cfg,async()=>{calls++;})).rejects.toThrow('unfinished');
  expect(calls).toBe(1);
 }finally{await rm(root,{recursive:true,force:true});}
});
