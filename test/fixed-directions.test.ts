import {test,expect} from 'vitest';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createImage,crop} from '../src/core/image.js';
import {applyFixedDirections} from '../src/node/fixed-directions.js';
import {resolveConfig} from '../src/config.js';
import {cachedCharacterBuild} from '../src/node/character-cache.js';
import {buildCharacter} from '../src/node/build.js';
test('fixed sprite keeps exact RGBA including invisible RGB; other directions stay intact',()=>{
 const cells=Array.from({length:8},(_,i)=>createImage(2,3,[i,20,30,255]));
 const south=createImage(4,2,[91,81,71,0]);south.data.set([250,100,0,127]);
 const result=applyFixedDirections(cells,{S:south});
 expect(result.map(c=>[c.width,c.height])).toEqual(Array(8).fill([4,3]));
 expect(crop(result[0],0,1,4,2).data).toEqual(south.data);
 for(let i=1;i<8;i++)expect(crop(result[i],1,0,2,3).data).toEqual(cells[i].data);
 expect(result[0].data.slice(0,16)).toEqual(new Uint8ClampedArray(16));
 expect(cells[0].width).toBe(2);
});
test('bad fixed direction and missing images fail before generation',async()=>{
 expect(()=>resolveConfig({fixedDirections:{BAD:'x'} as any},'/tmp')).toThrow('Invalid fixedDirections');
 const cfg=resolveConfig({fixedDirections:{S:'missing-fixed-sprute.png'}},'/tmp');
 expect(cfg.fixedDirections?.S).toBe('/tmp/missing-fixed-sprute.png');
 await expect(buildCharacter(cfg)).rejects.toThrow(/missing-fixed-sprute/);
});
test('editing fixed image invalidates completed build even when its filename is unchanged',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-fixed-'));let calls=0;
 try{
  const fixed=join(root,'south.png');await writeFile(fixed,'original');
  const cfg=resolveConfig({name:'hero',output:root,fixedDirections:{S:fixed}},root);
  const build=async()=>{calls++;for(const suffix of ['spritesheet.png','turntable.webp','entity.json','preview.html'])await writeFile(join(root,'hero.'+suffix),suffix);};
  await cachedCharacterBuild(cfg,build);await writeFile(fixed,'edited');
  await expect(cachedCharacterBuild(cfg,build)).rejects.toThrow('changed');expect(calls).toBe(1);
 }finally{await rm(root,{recursive:true,force:true});}
});
