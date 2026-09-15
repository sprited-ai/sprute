/** Sprite sheet assembly — pack cells into a single horizontal strip.
 * All cells must share dimensions; order is the caller's contract
 * (build uses SPIN_ORDER: S SE E NE N NW W SW). */
import { createImage, type RawImage } from "./image.js";

export function makeSpriteSheet(cells: RawImage[]): RawImage {
  const { width: cw, height: ch } = cells[0];
  const sheet = createImage(cw * cells.length, ch, [0, 0, 0, 0]);
  cells.forEach((c, i) => {
    if (c.width !== cw || c.height !== ch) throw new Error('Sprite cells must share dimensions');
    // Packing is a byte copy, not alpha blending onto transparent black.
    for (let row = 0; row < ch; row++) {
      sheet.data.set(c.data.subarray(row * cw * 4, (row + 1) * cw * 4), (row * sheet.width + i * cw) * 4);
    }
  });
  return sheet;
}
