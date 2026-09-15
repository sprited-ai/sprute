import { test, expect } from 'vitest';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { discoverCharacters, loadCharacterSpec } from '../src/node/character-project.js';

test('discovers nested character specs, ignores outputs, and resolves source relative to each file', async () => {
 const root = await mkdtemp(join(tmpdir(), 'sprute-project-'));
 try {
  for (const folder of ['characters', 'outputs', 'node_modules']) await mkdir(join(root,folder));
  for (const folder of ['characters','outputs','node_modules']) await writeFile(join(root,folder,'hero.sprute.json'),JSON.stringify({source:'hero.png',seed:42,states:['standing'],directions:8}));
  const files=await discoverCharacters(root);
  expect(files).toEqual([join(root,'characters/hero.sprute.json')]);
  const config=await loadCharacterSpec(files[0]);
  expect(config.reference).toBe(join(root,'characters/hero.png'));
  expect(config.name).toBe('hero');expect(config.seed).toBe(42);
  await writeFile(files[0],JSON.stringify({source:'hero.png',backend:'local'}));
  await expect(loadCharacterSpec(files[0])).rejects.toThrow('no generation started');
  await writeFile(files[0],JSON.stringify({source:'hero.png',states:['standing','run']}));
  await expect(loadCharacterSpec(files[0])).rejects.toThrow('No generation started');
 } finally {await rm(root,{recursive:true,force:true});}
});

test('nested characters inherit provider and project-relative output while character overrides stay relative to their file', async () => {
 const root=await mkdtemp(join(tmpdir(),'sprute-defaults-'));
 const old=process.cwd();
 try {
  process.chdir(root);await mkdir(join(root,'characters'));
  await writeFile(join(root,'sprute.config.json'),JSON.stringify({output:'exports',seed:7,preview:{open:false},model:{provider:'replicate',id:'configured-model',envKey:'CUSTOM_KEY'}}));
  const file=join(root,'characters','hero.sprute.json');
  await writeFile(file,JSON.stringify({source:'hero.png',model:{id:'character-model'}}));
  const inherited=await loadCharacterSpec(file);
  expect(inherited.output).toBe(join(process.cwd(),'exports'));
  expect(inherited.reference).toBe(join(root,'characters','hero.png'));
  expect(inherited.model).toEqual({provider:'replicate',id:'character-model',envKey:'CUSTOM_KEY'});
  expect(inherited.seed).toBe(7);expect(inherited.preview?.open).toBe(false);
  await writeFile(file,JSON.stringify({source:'hero.png',output:'own-output',seed:42,preview:{open:true}}));
  const overridden=await loadCharacterSpec(file);
  expect(overridden.output).toBe(join(root,'characters','own-output'));expect(overridden.seed).toBe(42);expect(overridden.preview?.open).toBe(true);
 } finally {process.chdir(old);await rm(root,{recursive:true,force:true});}
});
