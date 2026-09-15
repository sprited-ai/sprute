import { it, expect } from 'vitest';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { SPIN_ORDER } from '../src/core/extract.js';
import { runPackAnimation } from '../src/node/animation.js';

it('packs conventional cycle folders at the requested game size with fixed transforms, RGBA and variable durations', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-directory-'));
  try {
    for (const [row, d] of SPIN_ORDER.entries()) {
      await mkdir(join(root, d, 'frames'), { recursive: true });
      const frames = [];
      for (let i = 0; i < 2; i++) {
        const rgba = Buffer.alloc(2 * 3 * 4);
        for (let p = 0; p < 6; p++) rgba.set([row * 20, i * 70, p * 30, p === 0 ? 80 : 200], p * 4);
        const bytes = await sharp(rgba, { raw: { width: 2, height: 3, channels: 4 } }).png().toBuffer();
        const file = `frames/${String(2-i).padStart(6,'0')}.png`;
        await writeFile(join(root, d, file), bytes);
        frames.push({ file, sha256: createHash('sha256').update(bytes).digest('hex'), sourceFrame: 10+i, time: i === 0 ? 0 : .1, duration: i === 0 ? .1 : .2 });
      }
      await writeFile(join(root,d,'cycle.json'),JSON.stringify({ version:1,columns:1,rows:1,width:2,height:3,frameCount:2,durationSeconds:.3,frames }));
    }
    const out = join(root,'packed');
    await runPackAnimation([root,'-o',out,'--size','8','--loop']);
    const meta = JSON.parse(await readFile(join(out,'animation.json'),'utf8'));
    const atlas = await sharp(join(out,'animation.png')).ensureAlpha().raw().toBuffer();
    expect(meta.loop).toBe(true);
    expect(meta.review.status).toBe('unreviewed');
    expect(meta.durationMs).toBe(300);
    for (const [row,d] of SPIN_ORDER.entries()) {
      expect(meta.animations[d].map((f: any) => f.durationMs)).toEqual([100,200]);
      expect(meta.registration.transforms[d]).toMatchObject({scale:2,translateX:2,translateY:1});
      for(let i=0;i<2;i++)for(let y=0;y<8;y++)for(let x=0;x<8;x++) {
        const p=Math.floor((y-1)/2)*2+Math.floor((x-2)/2);
        const expected=x>=2&&x<6&&y>=1&&y<7 ? [row*20,i*70,p*30,p===0?80:200] : [0,0,0,0];
        const offset=((row*8+y)*16+i*8+x)*4;
        expect([...atlas.subarray(offset,offset+4)]).toEqual(expected);
      }
    }
    await rm(join(root,'NW'),{recursive:true});
    await expect(runPackAnimation([root,'-o',join(root,'missing'),'--size','8'])).rejects.toThrow();
    await expect(readFile(join(root,'missing/animation.png'))).rejects.toMatchObject({code:'ENOENT'});
  } finally { await rm(root,{recursive:true,force:true}); }
});
