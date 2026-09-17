/** Platform seam for the generation pipeline: PNG bytes <-> RawImage and
 * small text labels. Node backs this with sharp, the browser with Canvas —
 * everything else in the pipeline is pure and shared. */
import type { RawImage } from "./image.js";

export interface Codec {
  encodePng(img: RawImage): Promise<Uint8Array>;
  decodeImage(bytes: Uint8Array): Promise<RawImage>;
  /** Black centered `text` on a transparent w x h strip (fix-grid labels). */
  drawLabel(text: string, width: number, height: number): Promise<RawImage>;
}

const B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/** Pure base64 — Buffer-free and btoa-free so core stays runtime-neutral. */
export function toBase64(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i], b = bytes[i + 1], c = bytes[i + 2];
    out += B64[a >> 2] + B64[((a & 3) << 4) | (b ?? 0) >> 4];
    out += i + 1 < bytes.length ? B64[((b & 15) << 2) | (c ?? 0) >> 6] : "=";
    out += i + 2 < bytes.length ? B64[c & 63] : "=";
  }
  return out;
}

export function fromBase64(s: string): Uint8Array {
  const clean = s.replace(/[^A-Za-z0-9+/]/g, "");
  const out = new Uint8Array(Math.floor(clean.length * 3 / 4));
  let o = 0;
  for (let i = 0; i + 1 < clean.length; i += 4) {
    const n = (B64.indexOf(clean[i]) << 18) | (B64.indexOf(clean[i + 1]) << 12)
      | ((B64.indexOf(clean[i + 2]) & 63) << 6) | (B64.indexOf(clean[i + 3]) & 63);
    out[o++] = n >> 16;
    if (i + 2 < clean.length) out[o++] = (n >> 8) & 255;
    if (i + 3 < clean.length) out[o++] = n & 255;
  }
  return out;
}
