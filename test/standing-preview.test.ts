import {test,expect} from 'vitest';
import sharp from 'sharp';
import {standingPreviewHtml} from '../src/node/standing-preview.js';
import {createImage} from '../src/core/image.js';
test('compass retains actual directional pixels and escapes character names',async()=>{
 const cells=Array.from({length:8},(_,i)=>{const c=createImage(1,1);c.data.set([i*30,10,20,255]);return c;});
 const html=await standingPreviewHtml('<script>alert(1)</script>',cells);
 expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>');
 const images=[...html.matchAll(/src="data:image\/png;base64,([^"]+)"/g)];
 expect(images).toHaveLength(8);
 const red=await Promise.all(images.map(async m=>(await sharp(Buffer.from(m[1],'base64')).raw().toBuffer())[0]));
 // SPIN_ORDER S,SE,E,NE,N,NW,W,SW -> compass NW,N,NE,W,E,SW,S,SE.
 expect(red).toEqual([150,120,90,180,60,210,0,30]);
});
