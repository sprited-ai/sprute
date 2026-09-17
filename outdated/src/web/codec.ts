/** Canvas-backed codec — the browser's half of the GenContext seam. */
import type { RawImage } from "../core/image.js";
import type { Codec } from "../core/codec.js";

function canvas2d(width: number, height: number): [OffscreenCanvas, OffscreenCanvasRenderingContext2D] {
  const canvas = new OffscreenCanvas(width, height);
  return [canvas, canvas.getContext("2d")!];
}

export const canvasCodec: Codec = {
  async encodePng(img: RawImage): Promise<Uint8Array> {
    const [canvas, ctx] = canvas2d(img.width, img.height);
    ctx.putImageData(new ImageData(img.data as Uint8ClampedArray<ArrayBuffer>, img.width, img.height), 0, 0);
    const blob = await canvas.convertToBlob({ type: "image/png" });
    return new Uint8Array(await blob.arrayBuffer());
  },

  async decodeImage(bytes: Uint8Array): Promise<RawImage> {
    const bitmap = await createImageBitmap(new Blob([bytes as BlobPart]));
    const [, ctx] = canvas2d(bitmap.width, bitmap.height);
    ctx.drawImage(bitmap, 0, 0);
    const d = ctx.getImageData(0, 0, bitmap.width, bitmap.height);
    return { width: d.width, height: d.height, data: d.data };
  },

  async drawLabel(text: string, width: number, height: number): Promise<RawImage> {
    const [, ctx] = canvas2d(width, height);
    ctx.fillStyle = "black";
    ctx.font = `${Math.round(height * 0.5)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(text, width / 2, Math.round(height * 0.7));
    const d = ctx.getImageData(0, 0, width, height);
    return { width, height, data: d.data };
  },
};
