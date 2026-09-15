import {SPIN_ORDER, type Direction} from '../core/extract.js';
import {createImage, type RawImage} from '../core/image.js';
import {readImage} from './io.js';
export type FixedDirections = Partial<Record<Direction, string>>;
export function validateFixedDirections(value: unknown): asserts value is FixedDirections {
 if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('fixedDirections must map directions to image paths');
 for(const [direction,path] of Object.entries(value)) {
  if (!(SPIN_ORDER as readonly string[]).includes(direction) || typeof path !== 'string' || !path.trim()) throw new Error(`Invalid fixedDirections entry: ${direction}`);
 }
}
export async function loadFixedDirections(paths: FixedDirections = {}) {
 validateFixedDirections(paths);
 const images: Partial<Record<Direction, RawImage>> = {};
 for(const [direction,path] of Object.entries(paths)) images[direction as Direction]=await readImage(path);
 return images;
}
/** Keep original RGBA pixels, including transparency. Align canvas bottoms and centers; never resize. */
export function applyFixedDirections(cells: RawImage[], fixed: Partial<Record<Direction, RawImage>>) {
 if(cells.length!==8)throw new Error('Expected eight direction cells');
 if(!Object.keys(fixed).length)return cells;
 const chosen=SPIN_ORDER.map((direction,i)=>fixed[direction]??cells[i]);
 const width=Math.max(...chosen.map(c=>c.width)),height=Math.max(...chosen.map(c=>c.height));
 return chosen.map(cell=>{
  const out=createImage(width,height),x=Math.floor((width-cell.width)/2),y=height-cell.height;
  for(let row=0;row<cell.height;row++)out.data.set(cell.data.subarray(row*cell.width*4,(row+1)*cell.width*4),((row+y)*width+x)*4);
  return out;
 });
}
