import { test, expect } from 'vitest';
import { mkdtemp, writeFile, readFile, readdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import sharp from 'sharp';
import { SPIN_ORDER } from '../src/core/extract.js';
import { prepareAnimationCharacter } from '../src/node/animation-character.js';
import { planAnimation } from '../src/node/animation-plan.js';

test('plans all direction-matched local workflows with copied, verified references and no overwrites', async () => {
  const root = await mkdtemp(join(tmpdir(),'sprute-plan-test-'));
  try {
    const pixels = Buffer.alloc(32*4*4);
    for (let i=0;i<8;i++) pixels.set([i*30,80,40,255],(32+i*4+1)*4);
    const source=join(root,'source.png');
    await sharp(pixels,{raw:{width:32,height:4,channels:4}}).png().toFile(source);
    const character=join(root,'character'); await prepareAnimationCharacter(source,character,{scailMasks:true});
    const views=Object.fromEntries(SPIN_ORDER.map(d=>[d,{video:`/server/${d}.mp4`,firstFrame:`motion/${d}.png`,caption:`Mannequin faces ${d}`} ]));
    const drivers=join(root,'drivers.json');await writeFile(drivers,JSON.stringify({version:1,views}));
    const out=join(root,'out');const {plan}=await planAnimation(character,drivers,'a wingless robot',out);
    for (const d of SPIN_ORDER) {
      const w=JSON.parse(await readFile(join(out,`${d}.workflow.json`),'utf8'));
      expect(w['8'].inputs.video).toBe(`/server/${d}.mp4`);
      expect(w['19'].inputs.image).toBe(`motion/${d}.png`);
      expect(w['20'].inputs.text).toBe(`Mannequin faces ${d}`);
      expect(w['6'].inputs.image).toBe(`${plan.inputPrefix}/${d}.png`);
      expect(w['9'].inputs.text).toContain('a wingless robot');
      expect(w['11'].class_type).toBe('WanAnimate2ToVideo');
      expect(w['12'].inputs).toMatchObject({steps:10,cfg:1,sampler_name:'euler',seed:42});
      expect(await readFile(join(out,'input',plan.inputPrefix,`${d}.png`))).toEqual(await readFile(join(character,`${d}.png`)));
    }
    expect(plan.status).toBe('unsubmitted');
    const scailDrivers = join(root,'scail-drivers.json');
    await writeFile(scailDrivers,JSON.stringify({version:1,views:Object.fromEntries(SPIN_ORDER.map(d=>[d,{video:`/server/${d}.mp4`,maskVideo:`/server/${d}-mask.mkv`}]))}));
    const scailOut=join(root,'scail');
    const {plan:scail}=await planAnimation(character,scailDrivers,'a wingless robot',scailOut,{model:'scail2'});
    expect(scail.profile).toBe('scail2-unipc40-v1');
    expect(scail.inputPrefix).not.toBe(plan.inputPrefix);
    for(const d of SPIN_ORDER) {
      const w=JSON.parse(await readFile(join(scailOut,`${d}.workflow.json`),'utf8'));
      expect(w['1'].inputs.unet_name).toBe('wan2.1_14B_SCAIL_2_fp8_scaled.safetensors');
      expect(w['11'].class_type).toBe('WanSCAILToVideo');
      expect(w['11'].inputs).toMatchObject({width:512,height:512,length:65,reference_image:['6',0],reference_image_mask:['21',0],pose_video:['8',0],pose_video_mask:['22',0]});
      expect(w['12'].inputs).toMatchObject({seed:7,steps:40,cfg:3,sampler_name:'uni_pc',scheduler:'simple'});
      expect(w['8'].inputs.video).toBe(`/server/${d}.mp4`);
      expect(w['22'].inputs.video).toBe(`/server/${d}-mask.mkv`);
      expect(w['21'].inputs.image).toBe(`${scail.inputPrefix}/${d}-primary.png`);
      expect(await readFile(join(scailOut,'input',scail.inputPrefix,`${d}-primary.png`))).toEqual(await readFile(join(character,`${d}-primary.png`)));
    }
    await expect(planAnimation(character,drivers,'robot',join(root,'missing-motion-mask'),{model:'scail2'})).rejects.toThrow(/motion-mask/);
    await writeFile(join(character,'S-primary.png'),'changed');
    await expect(planAnimation(character,scailDrivers,'robot',join(root,'changed-mask'),{model:'scail2'})).rejects.toThrow();
    expect(await readdir(root)).not.toContain('changed-mask');
    await expect(planAnimation(character,drivers,'robot',out)).rejects.toThrow('already exists');
    await writeFile(join(character,'N.png'),'changed');
    await expect(planAnimation(character,drivers,'robot',join(root,'invalid'))).rejects.toThrow();
    expect((await readdir(root)).some(n=>n==='invalid'||n.startsWith('.sprute-'))).toBe(false);
  } finally {await rm(root,{recursive:true,force:true});}
});
