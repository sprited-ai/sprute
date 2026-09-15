import { test, expect } from 'vitest';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createServer } from 'node:http';
import { once } from 'node:events';
import sharp from 'sharp';
import { SPIN_ORDER } from '../src/core/extract.js';
import { prepareAnimationCharacter } from '../src/node/animation-character.js';
import { planAnimation } from '../src/node/animation-plan.js';
import { uploadAnimationInputs } from '../src/node/animation-upload.js';

test.each(['wan-animate','scail2'] as const)('%s uploads exact PNGs, recovers a lost response without duplicate upload, and refuses conflicts', async (model) => {
  const root=await mkdtemp(join(tmpdir(),'sprute-upload-test-'));
  const stored=new Map<string,Buffer>();let posts=0,lost=true;const paths:string[]=[];
  const server=createServer(async(req,res)=>{
    try {
      const url=new URL(req.url!,'http://local');paths.push(url.pathname);
      if(req.method==='GET'&&url.pathname==='/view'){
        const value=stored.get(url.searchParams.get('filename')!);res.statusCode=value?200:404;res.end(value);return;
      }
      if(req.method==='POST'&&url.pathname==='/upload/image'){
        posts++;const chunks:Buffer[]=[];for await(const chunk of req)chunks.push(Buffer.from(chunk));
        const form=await new Request('http://local/upload/image',{method:'POST',headers:{'content-type':req.headers['content-type']!},body:Buffer.concat(chunks)}).formData();
        expect(form.get('overwrite')).toBe('false');expect(form.get('type')).toBe('input');
        const image=form.get('image') as File;stored.set(image.name,Buffer.from(await image.arrayBuffer()));
        if(lost&&(model==='wan-animate'||image.name.endsWith('-primary.png'))){lost=false;res.destroy();return;}
        res.setHeader('content-type','application/json');res.end(JSON.stringify({name:image.name,subfolder:form.get('subfolder'),type:'input'}));return;
      }
      res.statusCode=400;res.end();
    }catch(e){res.statusCode=500;res.end(String(e));}
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');const url=`http://127.0.0.1:${(server.address() as any).port}`;
  try{
    const pixels=Buffer.alloc(32*4*4);for(let i=0;i<8;i++)pixels.set([i*30,80,40,255],(32+i*4+1)*4);
    const source=join(root,'source.png');await sharp(pixels,{raw:{width:32,height:4,channels:4}}).png().toFile(source);
    await prepareAnimationCharacter(source,join(root,'character'),{scailMasks:model==='scail2'});
    const drivers=join(root,'drivers.json');await writeFile(drivers,JSON.stringify({version:1,views:Object.fromEntries(SPIN_ORDER.map(d=>[d,{video:`/${d}.mp4`,firstFrame:`${d}.png`,caption:d,maskVideo:`/${d}-mask.mkv`}]))}));
    const folder=join(root,'plan');const {plan}=await planAnimation(join(root,'character'),drivers,'a robot',folder,{model});
    const count=model==='scail2'?16:8;
    await expect(uploadAnimationInputs(folder,url)).rejects.toThrow('Upload not verified');expect(posts).toBe(model==='scail2'?9:1);
    const recovered=await uploadAnimationInputs(folder,url);expect(posts).toBe(count);expect(recovered.views[0].status).toBe('reused');
    expect((await uploadAnimationInputs(folder,url)).views.every(v=>v.status==='reused')).toBe(true);expect(posts).toBe(count);
    for(const [file,bytes] of stored)expect(bytes).toEqual(await readFile(join(folder,'input',plan.inputPrefix,file)));
    stored.delete('S.png');
    stored.set(model==='scail2'?'SW-primary.png':'N.png',Buffer.from('conflicting remote image'));
    await expect(uploadAnimationInputs(folder,url)).rejects.toThrow('Remote input conflict');expect(posts).toBe(count);
    if(model==='scail2') {
      await writeFile(join(folder,'input',plan.inputPrefix,'W-primary.png'),'changed');const reads=paths.length;
      await expect(uploadAnimationInputs(folder,url)).rejects.toThrow('Plan mask changed');expect(paths.length).toBe(reads);
      await writeFile(join(folder,'input',plan.inputPrefix,'W-primary.png'),await readFile(join(root,'character','W-primary.png')));
    }
    await writeFile(join(folder,'W.workflow.json'),'changed');const reads=paths.length;
    await expect(uploadAnimationInputs(folder,url)).rejects.toThrow('Plan files changed');expect(paths.length).toBe(reads);
    expect(paths.every(p=>p==='/view'||p==='/upload/image')).toBe(true);
  }finally{server.close();await once(server,'close');await rm(root,{recursive:true,force:true});}
});
