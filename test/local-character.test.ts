import { test, expect, vi } from 'vitest';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import sharp from 'sharp';
vi.mock('../src/node/qwen-local.js',()=>({runLocalQwenJob:vi.fn()}));
vi.mock('../src/node/toonout.js',()=>({toonoutMatting:async (images:unknown[])=>images}));
import { runLocalQwenJob } from '../src/node/qwen-local.js';
import { loadLocalCharacter, buildLocalCharacter } from '../src/node/local-character.js';

test('local spec builds eight jobs and a real sheet/preview without invoking cloud',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-local-'));
 try {
  const png=await sharp({create:{width:32,height:32,channels:4,background:'#123456'}}).png().toBuffer();
  await writeFile(join(root,'source.png'),png);
  const file=join(root,'hero.sprute.json');await writeFile(join(root,'runner.py'),'fixture');
  await writeFile(file,JSON.stringify({backend:'local',source:'source.png',states:['standing'],frameSize:32,output:'result',preview:{open:false},local:{python:'/python',runner:join(root,'runner.py'),comfyRoot:'/comfy',diffusionModels:'/models'}}));
  const config=await loadLocalCharacter(file);expect(config!.source).toBe(join(root,'source.png'));
  vi.mocked(runLocalQwenJob).mockImplementation(async options=>{
   const {mkdir}=await import('node:fs/promises');await mkdir(options.output);
   return {png,state:{status:'complete'},width:32,height:32};
  });
  await buildLocalCharacter(config!);
  expect(runLocalQwenJob).toHaveBeenCalledTimes(8);
  const state=JSON.parse(await readFile(join(root,'result/build.json'),'utf8'));
  expect(state.completed).toEqual(['S','SE','E','NE','N','NW','W','SW']);expect(state.status).toBe('complete');
  const sheet=await sharp(join(root,'result/standing.png')).metadata();expect(sheet.width).toBe(256);
  expect(await readFile(join(root,'result/preview.html'),'utf8')).toContain('standing.png');
  await buildLocalCharacter(config!);
  await writeFile(join(root,'result/standing.png'),'changed');
  await expect(buildLocalCharacter(config!)).rejects.toThrow('Saved output changed');
  expect(runLocalQwenJob).toHaveBeenCalledTimes(8);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('failed third direction resumes without regenerating two verified cutouts', async () => {
 const root = await mkdtemp(join(tmpdir(), 'sprute-resume-'));
 vi.mocked(runLocalQwenJob).mockClear();
 try {
  const png = await sharp({create:{width:32,height:32,channels:4,background:'#123456'}}).png().toBuffer();
  await writeFile(join(root,'source.png'),png);
  await writeFile(join(root,'runner.py'),'fixture');
  const file = join(root,'hero.sprute.json');
  await writeFile(file,JSON.stringify({backend:'local',source:'source.png',states:['standing'],frameSize:32,output:'result',preview:{open:false},local:{python:'/python',runner:join(root,'runner.py'),comfyRoot:'/comfy',diffusionModels:'/models'}}));
  const config = (await loadLocalCharacter(file))!;
  let attempts = 0;
  vi.mocked(runLocalQwenJob).mockImplementation(async options => {
   const {mkdir} = await import('node:fs/promises'); await mkdir(options.output);
   if (++attempts === 3) throw new Error('simulated model failure');
   return {png,state:{status:'complete'},width:32,height:32};
  });
  await expect(buildLocalCharacter(config)).rejects.toThrow('simulated model failure');
  const failed = JSON.parse(await readFile(join(root,'result/build.json'),'utf8'));
  expect(failed.status).toBe('failed'); expect(failed.completed).toEqual(['S','SE']);
  const saved = await readFile(join(root,'result',failed.cutouts.S.path));
  await buildLocalCharacter(config);
  expect(attempts).toBe(9); // Eight successes and one failure; S/SE were not regenerated.
  expect(await readFile(join(root,'result',failed.cutouts.S.path))).toEqual(saved);
  const complete = JSON.parse(await readFile(join(root,'result/build.json'),'utf8'));
  expect(complete.status).toBe('complete'); expect(complete.completed).toHaveLength(8);
  expect(complete.cutouts.E.path).not.toContain('..');
 } finally { await rm(root,{recursive:true,force:true}); }
});

test('approved south bypasses local inference and survives packing and cache reuse',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-local-fixed-'));vi.mocked(runLocalQwenJob).mockClear();
 try {
  const generated=await sharp({create:{width:32,height:32,channels:4,background:'#123456'}}).png().toBuffer();
  const south=await sharp({create:{width:32,height:32,channels:4,background:{r:250,g:60,b:20,alpha:0.5}}}).png().toBuffer();
  await writeFile(join(root,'source.png'),generated);await writeFile(join(root,'south.png'),south);await writeFile(join(root,'runner.py'),'fixture');
  const file=join(root,'hero.sprute.json');
  await writeFile(file,JSON.stringify({backend:'local',source:'source.png',frameSize:32,fixedDirections:{S:'south.png'},output:'result',preview:{open:false},local:{python:'/python',runner:join(root,'runner.py'),comfyRoot:'/comfy',diffusionModels:'/models'}}));
  const config=(await loadLocalCharacter(file))!;
  vi.mocked(runLocalQwenJob).mockImplementation(async options=>{
   const {mkdir}=await import('node:fs/promises');await mkdir(options.output);return {png:generated,state:{status:'complete'},width:32,height:32};
  });
  await buildLocalCharacter(config);expect(runLocalQwenJob).toHaveBeenCalledTimes(7);
  const actual=await sharp(join(root,'result/standing.png')).extract({left:0,top:0,width:32,height:32}).raw().toBuffer();
  expect(actual).toEqual(await sharp(south).raw().toBuffer());
  await buildLocalCharacter(config);expect(runLocalQwenJob).toHaveBeenCalledTimes(7);
  await writeFile(join(root,'south.png'),generated);
  await expect(buildLocalCharacter(config)).rejects.toThrow('changed');expect(runLocalQwenJob).toHaveBeenCalledTimes(7);
 }finally{await rm(root,{recursive:true,force:true});}
});
