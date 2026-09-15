import { test, expect } from 'vitest';
import { mkdtemp, rm, readdir, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import { prepareAnimationCharacter } from '../src/node/animation-character.js';

test('prepares all supplied directions independently, with partial alpha on gray and fixed placement', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-character-test-'));
  try {
    const pixels = Buffer.alloc(32 * 4 * 4);
    for (let i = 0; i < 8; i++) {
      for (let y = 1; y <= 2; y++) for (let x = 1; x <= 2; x++) {
        const p = (y * 32 + i * 4 + x) * 4;
        pixels.set([i * 30, x === 1 ? 20 : 180, 50, x === 1 ? 128 : 255], p);
      }
    }
    const source = join(root, 'source.png');
    await sharp(pixels, { raw: { width: 32, height: 4, channels: 4 } }).png().toFile(source);
    const out = join(root, 'out');
    const result = await prepareAnimationCharacter(source, out);
    expect(result.metadata.references.map(r => r.direction)).toEqual(['S','SE','E','NE','N','NW','W','SW']);
    for (const [i, ref] of result.metadata.references.entries()) {
      const { data, info } = await sharp(join(out, ref.file)).raw().toBuffer({ resolveWithObject: true });
      expect(info).toMatchObject({ width: 512, height: 512, channels: 3 });
      const rgb = (x: number, y: number) => [...data.subarray((y * 512 + x) * 3, (y * 512 + x) * 3 + 3)];
      expect(rgb(0,0)).toEqual([232,232,232]);
      expect(rgb(76,76)).toEqual([Math.round((i*30*128+232*127)/255),126,141]);
      expect(rgb(435,435)).toEqual([i*30,180,50]);
      expect(rgb(435,436)).toEqual([232,232,232]);
    }
    await expect(prepareAnimationCharacter(source,out)).rejects.toThrow('already exists');
    expect((await readdir(out)).filter(f => f.endsWith('-primary.png'))).toEqual([]);
    // Preserve the 127/128 threshold distinction even though both pixels were
    // partially composited onto gray in the appearance references.
    for (let i=0;i<8;i++) pixels[(32+i*4+1)*4+3]=127;
    await sharp(pixels, { raw: { width:32,height:4,channels:4 } }).png().toFile(source);
    const masked = await prepareAnimationCharacter(source,join(root,'masked'),{scailMasks:true});
    for (const ref of masked.metadata.references) {
      expect(ref.primaryMask?.encoding).toBe('scail-blue-on-white-source-alpha-ge128-v1');
      const bytes = await readFile(join(root,'masked',ref.primaryMask!.file));
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(ref.primaryMask!.sha256);
      const {data,info}=await sharp(bytes).raw().toBuffer({resolveWithObject:true});
      expect(info).toMatchObject({width:512,height:512,channels:3});
      const expected=Buffer.alloc(512*512*3,255);
      for(let y=76;y<436;y++)for(let x=76;x<436;x++)if(x>=256||y>=256) {
        const p=(y*512+x)*3;expected[p]=expected[p+1]=0;
      }
      expect(data.equals(expected)).toBe(true);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('rejects empty or opaque cells before leaving output', async () => {
  const root = await mkdtemp(join(tmpdir(), 'sprute-character-test-'));
  try {
    for (const [name, alpha, error] of [['empty',0,'Empty'],['opaque',255,'transparent']] as const) {
      const source = join(root, `${name}.png`);
      await sharp({ create: { width: 16, height: 2, channels: 4, background: { r: 50, g: 50, b: 50, alpha: alpha/255 } } }).png().toFile(source);
      await expect(prepareAnimationCharacter(source,join(root,'out'))).rejects.toThrow(error);
    }
    expect((await readdir(root)).sort()).toEqual(['empty.png','opaque.png']);
  } finally { await rm(root, { recursive: true, force: true }); }
});
