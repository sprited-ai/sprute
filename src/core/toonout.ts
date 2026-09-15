/** Runtime-agnostic halves of BiRefNet-ToonOut matting: preprocessing and
 * mask application, pure TS on RawImage. The ONNX runtime itself is injected
 * by the environment glue — onnxruntime-node (src/node/toonout.ts) or
 * onnxruntime-web (src/web/toonout.ts, picked by the exports "browser"
 * condition) — so both run the exact same pixel path. */
import { compositeOn, createImage, resizeBilinear, type RawImage } from "./image.js";

export const TOONOUT_SIZE = 1024;
export const TOONOUT_MODEL_URL =
  "https://huggingface.co/sprited/birefnet-toonout-onnx/resolve/2ded6fe6063fe146b7b30d8b4cfc5636df322525/birefnet-toonout-fp16.onnx";
export const TOONOUT_MODEL_BYTES = 492381880;
export const TOONOUT_MODEL_SHA256 = '213a8a98ee426ef8f02d247eb5a5a9889359e37c2e1e7e31e282d61034d08a83';

// ImageNet normalization — BiRefNet's training preprocessing
const MEAN = [0.485, 0.456, 0.406];
const STD = [0.229, 0.224, 0.225];

/** Cell → normalized CHW float tensor data ([1,3,1024,1024]). Transparency
 * is flattened onto neutral gray first — the model wants a filled image. */
export function toonoutPreprocess(cell: RawImage): Float32Array {
  const flat = resizeBilinear(compositeOn(cell, [128, 128, 128]), TOONOUT_SIZE, TOONOUT_SIZE);
  const n = TOONOUT_SIZE * TOONOUT_SIZE;
  const chw = new Float32Array(3 * n);
  for (let p = 0; p < n; p++) {
    for (let c = 0; c < 3; c++) {
      chw[c * n + p] = (flat.data[p * 4 + c] / 255 - MEAN[c]) / STD[c];
    }
  }
  return chw;
}

/** Sigmoid mask ([1,1,1024,1024] data) → cell with the mask as alpha,
 * resized back to the cell's size. Existing transparency is kept. */
export function toonoutApplyMask(cell: RawImage, mask: Float32Array): RawImage {
  const m = createImage(TOONOUT_SIZE, TOONOUT_SIZE);
  for (let p = 0; p < TOONOUT_SIZE * TOONOUT_SIZE; p++) {
    m.data[p * 4] = Math.min(1, Math.max(0, mask[p])) * 255;
  }
  const resized = resizeBilinear(m, cell.width, cell.height);
  const out: RawImage = { width: cell.width, height: cell.height, data: new Uint8ClampedArray(cell.data) };
  for (let p = 0; p < cell.width * cell.height; p++) {
    out.data[p * 4 + 3] = Math.min(out.data[p * 4 + 3], resized.data[p * 4]);
  }
  return out;
}
