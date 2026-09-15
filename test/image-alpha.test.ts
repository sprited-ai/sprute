import {test,expect} from 'vitest';
import {createImage,paste,crop} from '../src/core/image.js';
import {makeSpriteSheet} from '../src/core/sheet.js';
test('padding a translucent cutout preserves its straight RGBA colors',()=>{
 const src=createImage(1,1,[240,100,60,128]),dst=createImage(3,3);
 paste(dst,src,1,1);expect([...crop(dst,1,1,1,1).data]).toEqual([240,100,60,128]);
});
test('source-over combines translucent alpha and normalizes color',()=>{
 const dst=createImage(1,1,[0,0,255,128]);paste(dst,createImage(1,1,[255,0,0,128]),0,0);
 expect([...dst.data]).toEqual([170,0,85,192]);
});
test('transparent source does not alter destination, and clipping is preserved',()=>{
 const dst=createImage(1,1,[10,20,30,40]);paste(dst,createImage(2,2,[255,0,0,0]),-1,-1);
 expect([...dst.data]).toEqual([10,20,30,40]);
});
test('sheet packing preserves all alpha levels and RGB in each slot',()=>{
 const cells=[0,1,127,128,254,255].map(a=>createImage(2,2,[200,80,10,a]));
 const sheet=makeSpriteSheet(cells);
 cells.forEach((c,i)=>expect(crop(sheet,i*2,0,2,2).data).toEqual(c.data));
});
