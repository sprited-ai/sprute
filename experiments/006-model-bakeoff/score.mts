/** Aesthetic eval scorer — the moat's "best = measured, not vibes" tool.
 *
 * A VLM (gemini-2.5-flash, the same judge sprute uses for QC) scores character
 * images on the axes that separate "striking" from the "stale/generic" default
 * (the Nano Banana Pro complaint). Point it at a directory; subdirectories are
 * treated as one model/config each, so a bake-off lays out as:
 *
 *   bakeoff/
 *     zanime/      *.png
 *     illustrious/ *.png
 *     nbp/         *.png        # baseline to beat
 *
 *   GEMINI_API_KEY=... npx tsx experiments/006-model-bakeoff/score.mts ./bakeoff
 *
 * Prints per-image scores + a per-model ranking. Same image set across models
 * → repeatable, comparable. This does NOT generate anything; feed it the
 * outputs of each model (bake-off images come from gin+ComfyUI).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, extname, basename, dirname, relative } from "node:path";

const KEY = process.env.GEMINI_API_KEY;
if (!KEY) {
  console.error("set GEMINI_API_KEY");
  process.exit(1);
}
const root = process.argv[2];
if (!root) {
  console.error("usage: tsx score.mts <dir>   (subdirs = one model each, or a flat dir of pngs)");
  process.exit(1);
}

// Rubric — each 1-10. The axes are the ones the workflow research flagged as
// the pretty-vs-stale differentiators (docs/007).
const AXES = ["aesthetic", "illustration", "anatomy", "detail", "appeal"] as const;
type Axis = (typeof AXES)[number];
type Score = Record<Axis, number> & { verdict: "striking" | "solid" | "generic"; note: string };

const RUBRIC =
  "You are judging a single AI-generated anime/illustration game character image. " +
  "Score each axis 1-10 (10 best), strictly and comparably:\n" +
  "- aesthetic: striking, beautiful composition and color vs flat/boring\n" +
  "- illustration: clean linework, intentional shading, craft (not muddy/AI-soup)\n" +
  "- anatomy: correct proportions, hands, face, no deformities\n" +
  "- detail: rich, finished detail vs undercooked/blurry\n" +
  "- appeal: would a game art director call this striking and on-style, or generic stock-AI?\n" +
  'Also give "verdict": one of "striking" | "solid" | "generic", and a one-line "note". ' +
  'Reply as JSON: {"aesthetic":n,"illustration":n,"anatomy":n,"detail":n,"appeal":n,"verdict":"...","note":"..."}';

async function scoreImage(path: string): Promise<Score> {
  const b64 = readFileSync(path).toString("base64");
  for (let attempt = 0; ; attempt++) {
    const res = await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": KEY! },
      body: JSON.stringify({
        contents: [{ parts: [{ inline_data: { mime_type: "image/png", data: b64 } }, { text: RUBRIC }] }],
        generationConfig: { responseMimeType: "application/json", temperature: 0 },
      }),
    });
    if (!res.ok) throw new Error(`score ${res.status}: ${(await res.text()).slice(0, 200)}`);
    const json = (await res.json()) as any;
    const text = (json.candidates?.[0]?.content?.parts ?? []).map((p: any) => p.text ?? "").join("");
    try {
      return JSON.parse(text.replace(/^```(json)?|```$/g, "").trim());
    } catch {
      if (attempt >= 1) throw new Error(`unparseable VLM reply for ${path}: ${text.slice(0, 120)}`);
    }
  }
}

function pngsUnder(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) out.push(...pngsUnder(p));
    else if (extname(p).toLowerCase() === ".png") out.push(p);
  }
  return out;
}

const total = (s: Score) => AXES.reduce((a, k) => a + (s[k] ?? 0), 0) / AXES.length;
// model = immediate parent dir relative to root ("." when images sit in root)
const modelOf = (path: string) => {
  const rel = relative(root, dirname(path)) || ".";
  return rel;
};

const images = pngsUnder(root);
if (!images.length) {
  console.error(`no .png under ${root}`);
  process.exit(1);
}
console.error(`scoring ${images.length} image(s) under ${root} …`);

const rows: { model: string; file: string; s: Score; avg: number }[] = [];
for (const path of images) {
  const s = await scoreImage(path);
  rows.push({ model: modelOf(path), file: basename(path), s, avg: total(s) });
  process.stderr.write(".");
}
process.stderr.write("\n");

// per-image detail
rows.sort((a, b) => b.avg - a.avg);
console.log("\n# per-image");
for (const r of rows) {
  console.log(
    `${r.avg.toFixed(1)}  [${r.s.verdict.padEnd(8)}] ${r.model}/${r.file}  ` +
      `(aes ${r.s.aesthetic} ill ${r.s.illustration} ana ${r.s.anatomy} det ${r.s.detail} app ${r.s.appeal})  ${r.s.note}`,
  );
}

// per-model ranking
const byModel = new Map<string, number[]>();
for (const r of rows) (byModel.get(r.model) ?? byModel.set(r.model, []).get(r.model)!).push(r.avg);
console.log("\n# model ranking (mean avg, n)");
[...byModel.entries()]
  .map(([m, xs]) => ({ m, mean: xs.reduce((a, b) => a + b, 0) / xs.length, n: xs.length }))
  .sort((a, b) => b.mean - a.mean)
  .forEach((x) => console.log(`${x.mean.toFixed(2)}  ${x.m}  (n=${x.n})`));
