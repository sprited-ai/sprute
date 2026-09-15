import { test, expect } from 'vitest';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { characterSpecForImage } from '../src/node/character-input.js';
test('image input creates a reusable provider-neutral spec and preserves edits on subsequent runs',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-image-'));
 try {
  const image=join(root,'my hero.jpg');await writeFile(image,'fixture');
  const first=await characterSpecForImage(image);expect(first.created).toBe(true);
  const spec=JSON.parse(await readFile(first.file,'utf8'));expect(spec.backend).toBeUndefined();expect(spec.frameSize).toBeUndefined();expect(spec.source).toBe('my hero.jpg');
  spec.frameSize=256;await writeFile(first.file,JSON.stringify(spec));
  expect((await characterSpecForImage(image)).created).toBe(false);
  expect(JSON.parse(await readFile(first.file,'utf8')).frameSize).toBe(256);
  await writeFile(first.file,JSON.stringify({...spec,source:'other.jpg'}));
  await expect(characterSpecForImage(image)).rejects.toThrow('another source');
 }finally{await rm(root,{recursive:true,force:true});}
});

test('explicit local project selection is retained in image-first specs',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-local-choice-'));
 const old=process.cwd();
 try {
  process.chdir(root);
  await writeFile(join(root,'sprute.config.json'),JSON.stringify({backend:'local'}));
  await writeFile(join(root,'hero.png'),'fixture');
  const result=await characterSpecForImage(join(root,'hero.png'));
  const saved=JSON.parse(await readFile(result.file,'utf8'));
  expect(saved.backend).toBe('local');expect(saved.frameSize).toBe(128);
 }finally{process.chdir(old);await rm(root,{recursive:true,force:true});}
});
