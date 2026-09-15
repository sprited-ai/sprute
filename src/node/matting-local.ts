/** Local BiRefNet-ToonOut matting in Node — onnxruntime-node, no Python, no
 * network after the first run. The fp16 ONNX lives on HF under
 * sprited/birefnet-toonout-onnx and is downloaded once to ~/.cache/sprute.
 * onnxruntime-node is an optionalDependency; when it (or the download) is
 * unavailable the caller falls back to the Replicate endpoint / floodfill.
 * Pixel pre/post processing is shared with the browser glue via
 * core/toonout. */
import { createReadStream, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { homedir } from "node:os";
import type { RawImage } from "../core/image.js";
import { TOONOUT_SIZE, TOONOUT_MODEL_URL, TOONOUT_MODEL_BYTES, TOONOUT_MODEL_SHA256, toonoutPreprocess, toonoutApplyMask } from "../core/toonout.js";
import { ensureVerifiedModel } from './verified-model.js';

const MODEL_FILE = "birefnet-toonout-fp16.onnx";

function cacheDir(): string {
  return process.env.SPRUTE_CACHE_DIR ?? join(homedir(), ".cache", "sprute");
}

let ortPromise: Promise<any> | undefined;
function loadOrt(): Promise<any> {
  // dynamic import so the CLI works without the optional native dep
  return (ortPromise ??= import("onnxruntime-node").then((m: any) => m.default ?? m));
}

export async function hasLocalToonout(): Promise<boolean> {
  try {
    await loadOrt();
    return true;
  } catch {
    return false;
  }
}

async function modelPath(): Promise<string> {
  return ensureVerifiedModel(join(cacheDir(), MODEL_FILE), { url: TOONOUT_MODEL_URL, bytes: TOONOUT_MODEL_BYTES, sha256: TOONOUT_MODEL_SHA256 });
}

async function matteAll(ort: any, sess: any, cells: RawImage[]): Promise<RawImage[]> {
  const out: RawImage[] = [];
  // sequential — the session saturates the device on its own
  for (const cell of cells) {
    const chw = toonoutPreprocess(cell);
    const res = await sess.run({ image: new ort.Tensor("float32", chw, [1, 3, TOONOUT_SIZE, TOONOUT_SIZE]) });
    out.push(toonoutApplyMask(cell, res.mask.data as Float32Array));
  }
  return out;
}

// cached after a successful run — a session that matted one batch will
// handle the next
export interface ToonoutProvenance {
  model: { file: string; sha256: string; bytes: number };
  /** The successful session's provider option, not per-operator hardware placement. */
  runtime: { onnxruntime: string | null; executionProvider: string; platform: string; arch: string };
}
let cached: { ort: any; sess: any; provenance: ToonoutProvenance } | undefined;

/** Matte cells through the local model. WebGPU first (~5x faster than the
 * CPU EP on Apple Silicon), CPU fallback — and since an EP can accept the
 * graph at create time yet still fail at run time (CoreML does exactly
 * that), the fallback wraps the run, not just session creation. */
export async function localToonoutMatting(cells: RawImage[]): Promise<RawImage[]> {
  return (await localToonoutMattingWithProvenance(cells)).images;
}

/** Return the provenance of the session that actually produced these images. */
export async function localToonoutMattingWithProvenance(cells: RawImage[]) {
  const ort = await loadOrt();
  if (cached) {
    const session = cached;
    try {
      return { images: await matteAll(session.ort, session.sess, cells), provenance: structuredClone(session.provenance) };
    } catch {
      cached = undefined;
    }
  }
  const path = await modelPath(), before = statSync(path);
  const unchanged = () => {
    const after = statSync(path);
    if (after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs || after.ino !== before.ino) throw new Error('ToonOut model changed while loading; no provenance can be assigned');
  };
  const digest = createHash('sha256');
  for await (const chunk of createReadStream(path)) digest.update(chunk);
  unchanged();
  const model = { file: MODEL_FILE, sha256: digest.digest('hex'), bytes: before.size };
  if (model.sha256 !== TOONOUT_MODEL_SHA256 || model.bytes !== TOONOUT_MODEL_BYTES) throw new Error('ToonOut model changed after verification');
  for (const ep of ["webgpu", "cpu"]) {
    try {
      const sess = await ort.InferenceSession.create(path, { executionProviders: [ep], logSeverityLevel: 3 });
      unchanged();
      const out = await matteAll(ort, sess, cells);
      const provenance: ToonoutProvenance = { model, runtime: { onnxruntime: typeof ort.env?.versions?.node === 'string' ? ort.env.versions.node : null,
        executionProvider: ep, platform: process.platform, arch: process.arch } };
      cached = { ort, sess, provenance };
      return { images: out, provenance: structuredClone(provenance) };
    } catch (e) {
      if (ep === "cpu") throw e;
      console.error(`webgpu matting failed — retrying on cpu (${String(e).slice(0, 120)})`);
    }
  }
  throw new Error("unreachable");
}
