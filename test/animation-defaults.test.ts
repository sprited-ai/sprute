import {test,expect} from 'vitest';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {loadAnimationDefaults} from '../src/node/animation-defaults.js';
test('unified animation settings override legacy setup and resolve guide paths from project',async()=>{
 const root=await mkdtemp(join(tmpdir(),'sprute-animation-defaults-'));
 try {
  expect(await loadAnimationDefaults(root)).toEqual({});
  await writeFile(join(root,'sprute.animation.json'),JSON.stringify({version:1,server:'http://localhost:8188',drivers:'old.json'}));
  expect((await loadAnimationDefaults(root)).drivers).toBe(join(root,'old.json'));
  await writeFile(join(root,'sprute.config.json'),JSON.stringify({animation:{server:'http://localhost:8190',drivers:'motion/drivers.json'}}));
  expect(await loadAnimationDefaults(root)).toEqual({server:'http://localhost:8190/',drivers:join(root,'motion/drivers.json')});
  await writeFile(join(root,'sprute.config.json'),JSON.stringify({animation:{server:'bad',drivers:'motion/drivers.json'}}));
  await expect(loadAnimationDefaults(root)).rejects.toThrow();
 }finally{await rm(root,{recursive:true,force:true});}
});
