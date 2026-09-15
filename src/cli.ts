#!/usr/bin/env node
import { cachedCharacterBuild } from "./node/character-cache.js";
import { standingPreviewHtml, openPreview } from "./node/standing-preview.js";
import { characterSpecForImage } from "./node/character-input.js";
import { runTerminalDemo } from "./node/terminal-character.js";
import { loadLocalCharacter, buildLocalCharacter } from "./node/local-character.js";
/** sprute CLI — prompt-first.
 *
 *   sprute "a small forest fairy"      generate from a description
 *   sprute generate "a goblin archer"  explicit form of the same
 *   sprute <name>.sprute.yaml          rerun a saved build exactly
 *   sprute -d "…" [-r ref.png] …       flags-only build
 *   sprute init                        write ./sprute.config.json (project defaults)
 *   sprute login                       set up an image-model key
 *
 * Extraction and QC are no longer CLI subcommands — they stay importable from
 * the core library (src/core/extract.ts, src/node/generate.ts).
 */
import { discoverCharacters, loadCharacterSpec } from "./node/character-project.js";
import { runAnimate } from "./node/animate.js";
import { runCollectAnimationRun } from "./node/animation-collect-run.js";
import { runRenderAnimationDrivers } from "./node/animation-driver-render.js";
import { runUploadAnimationDrivers } from "./node/animation-driver-upload.js";
import { runSubmitAnimationPlan } from "./node/animation-batch.js";
import { runUploadAnimationInputs } from "./node/animation-upload.js";
import { runCheckAnimationServer } from "./node/animation-preflight.js";
import { runPlanAnimation } from "./node/animation-plan.js";
import { runPrepareAnimationCharacter } from "./node/animation-character.js";
import { runCollectAnimation } from "./node/comfy-animation.js";
import { runSubmitAnimation } from "./node/comfy-submit.js";
import { runExportGodot } from "./node/animation-godot.js";
import { runPreviewAnimation } from "./node/animation-preview.js";
import { runMatteAnimation } from "./node/animation-matte.js";
import { runExtractCycle } from "./node/animation-cycle.js";
import { runReviewAnimation } from "./node/animation-review.js";
import { runPackAnimation } from "./node/animation.js";
import { join, relative } from "node:path";
import { writeFileSync, existsSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import { writePng, writeAnimatedWebp, writeBytes } from "./node/io.js";
import { loadConfig, loadProjectConfig, resolveConfig } from "./config.js";
import type { ResolvedConfig } from "./config.js";
import { splitDesc, slugify, parseFlags, mergeConfig, buildYaml } from "./args.js";
import { startProgress } from "./node/progress.js";
import { startReport } from "./node/report.js";
import { buildCharacter, nextCharName } from "./node/build.js";
import { writeKey, credentialsPath } from "./node/keystore.js";

// ~417ms per direction — slow enough to actually look at each pose
const TURNTABLE_FPS = 2.4;

function usage(): never {
  console.error("usage:");
  console.error('  sprute demo                       play an 8-direction sample in your terminal');
  console.error('  sprute character.png              generate standing views from your picture');
  console.error('  sprute                            build discovered *.sprute.json files');
  console.error('  sprute "a small forest fairy"      generate from a description');
  console.error('  sprute generate "a goblin archer"  explicit form of the same');
  console.error("  sprute <name>.sprute.yaml          rerun a saved build exactly");
  console.error('  sprute -d "…" [-r ref.png] …       flags-only build');
  console.error("  sprute init                        write ./sprute.config.json");
  console.error("  sprute login                       set up an image-model key");
  console.error("  sprute animate character.spritesheet.png --wait  generate an eight-direction walk");
  console.error("  sprute animate setup --drivers drivers.json --server URL  connect animation server");
  console.error("  sprute animate --resume my-walk --wait  continue a saved walking animation");
  console.error("  sprute animate --status my-walk       check progress without starting work");
  console.error("");
  console.error("  sprute collect-animation-run run-folder  collect/reuse eight job videos (GET only)");
  console.error("  sprute render-animation-drivers [model.glb | --download-template] -o new-folder [--scail-masks]");
  console.error("  sprute submit-animation-plan plan-folder --run run-folder --server URL  submit/resume eight views");
  console.error("  sprute upload-animation plan-folder --server URL  upload verified character inputs");
  console.error("  sprute upload-animation-drivers bundle-folder --server URL --server-input /server/input -o drivers.json");
  console.error("  sprute check-animation-server --server URL [--model scail2]  inspect nodes and models");
  console.error("  sprute plan-animation character-folder --drivers drivers.json --description appearance -o new-folder [--model scail2]");
  console.error("  sprute prepare-animation character.spritesheet.png -o new-folder [--scail-masks]  prepare references offline");
  console.error("  sprute pack-animation frames.json|cycles-folder -o new-folder [--size 128] [--loop] [--hold-frames 2]");
  console.error("  sprute review-animation clip.mp4 -o new-folder   review every video frame (offline)");
  console.error("  sprute preview-animation packed-folder -o preview.html  inspect all eight directions offline");
  console.error("  sprute collect-animation --job ID -o new-folder  recover a ComfyUI video");
  console.error("  sprute submit-animation workflow-api.json --journal job.json  submit once (experimental)");
  console.error("  sprute extract-cycle review-folder --start N --end N -o new-folder");
  console.error("  sprute matte-animation cycle-folder -o new-folder [--all-directions]  remove backgrounds locally");
  console.error("  sprute export-godot packed-folder -o new-folder  create Godot SpriteFrames");
  console.error("build flags: -d <desc>  -r <ref.png>  --seed N  -o <dir>  --sheet");
  console.error("             --template NAME  --provider NAME  --matting floodfill|toonout");
  console.error("             --no-check  --max-fixes N  --report  --intermediate");
  process.exit(1);
}

// ---------------------------------------------------------------- login --

// M1 ships the Replicate provider only — login offers what generation can
// actually use. Fal and Comfy join the menu when their gen.ts branches land
// (docs/006 sequencing: Replicate → Fal → Comfy).
const LOGIN_PROVIDERS: { envKey: string; label: string; url: string; verify?: (key: string) => Promise<boolean> }[] = [
  { envKey: "REPLICATE_API_TOKEN", label: "Replicate API token", url: "replicate.com/account/api-tokens", verify: verifyReplicate },
];

async function verifyReplicate(token: string): Promise<boolean> {
  try {
    const res = await fetch("https://api.replicate.com/v1/account", { headers: { Authorization: `Bearer ${token}` } });
    return res.ok;
  } catch {
    return false;
  }
}

async function login(): Promise<void> {
  if (process.env.REPLICATE_API_TOKEN) {
    console.log("✓ REPLICATE_API_TOKEN is already set in your environment. No need to log in again.");
    return;
  }
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    console.log("sprute needs an image-model key (one-time setup)\n");
    LOGIN_PROVIDERS.forEach((p, i) => console.log(`  ${i + 1}. ${p.label.padEnd(18)} — ${p.url}`));
    const provider = LOGIN_PROVIDERS[Number((await rl.question("\nchoose [1]: ")).trim() || "1") - 1];
    if (!provider) {
      console.error("invalid choice");
      process.exit(1);
    }
    const key = (await rl.question(`paste ${provider.label}: `)).trim();
    if (!key) {
      console.error("no key entered");
      process.exit(1);
    }
    if (provider.verify) {
      process.stdout.write("verifying… ");
      const ok = await provider.verify(key);
      console.log(ok ? "✓" : "✗");
      if (!ok) {
        console.error(`${provider.label} rejected — not saved`);
        process.exit(1);
      }
    } else {
      console.log("(saved without verification)");
    }
    writeKey(provider.envKey, key);
    console.log(`✓ saved to ${credentialsPath()} (0600)`);
  } finally {
    rl.close();
  }
}

// ----------------------------------------------------------------- init --

function init(): void {
  const path = join(process.cwd(), "sprute.config.json");
  if (existsSync(path)) {
    console.error(`${relative(process.cwd(), path)} already exists`);
    process.exit(1);
  }
  const defaults = { output: "./outputs", model: { provider: "replicate" }, matting: "toonout" };
  writeFileSync(path, JSON.stringify(defaults, null, 2) + "\n");
  console.log(`wrote ${relative(process.cwd(), path)} — project defaults for sprute builds`);
}

// ------------------------------------------------------------- generate --

/** Build a resolved config from the prompt, flags, and project defaults.
 * Merge precedence (in src/args.ts): flags > prompt > ./sprute.config.json >
 * builtin. The template name is kept aside for the reproducible yaml. */
function configFromFlags(description: string | undefined, args: string[]): { cfg: ResolvedConfig; template?: string } {
  const { cfg, template } = mergeConfig(parseFlags(args), description, loadProjectConfig(process.cwd()));
  return { cfg: resolveConfig(cfg, process.cwd()), template };
}

/** A name from the description ("a small forest fairy" → "a-small-forest-fairy"),
 * de-duped against existing outputs; falls back to the char-NNN counter. */
function deriveName(cfg: ResolvedConfig): string {
  if (!cfg.description) return nextCharName(cfg.output);
  const base = slugify(cfg.description);
  let name = base;
  for (let n = 2; existsSync(join(cfg.output, `${name}.spritesheet.png`)); n++) name = `${base}-${n}`;
  return name;
}

async function runBuild(cfgIn: ResolvedConfig, flags?: { cfg: ResolvedConfig; template?: string }): Promise<void> {
  // resolve the name up front — the report and intermediate paths carry it
  const name = cfgIn.name ?? deriveName(cfgIn);
  const cfg = { ...cfgIn, name };
  const report = cfg.report ? startReport(join(cfg.output, `${name}.report.md`), `${name} — build report`) : undefined;
  let stepN = 0;
  const { seed, sheet, concept, cells, spritesheet, entity } = await buildCharacter(cfg, {
    log: (line) => console.error(line),
    progress: (label, expectedMs) => {
      const p = startProgress(label, expectedMs);
      return (finalLabel) => p.done(finalLabel);
    },
    reporter: report,
    // --intermediate: every pipeline image also lands as a numbered PNG
    stage: cfg.intermediate
      ? async (label, img) => {
          const file = join(cfg.output, `${name}.intermediate`, `${String(++stepN).padStart(2, "0")}-${label}.png`);
          if (Buffer.isBuffer(img)) writeBytes(file, img);
          else await writePng(file, img);
        }
      : undefined,
  });
  if (cfg.outputs?.sheet) await writePng(join(cfg.output, cfg.outputs.sheet === true ? `${name}.sheet.png` : cfg.outputs.sheet), sheet);
  if (concept) await writePng(join(cfg.output, `${name}.concept.png`), concept);
  await writePng(join(cfg.output, `${name}.spritesheet.png`), spritesheet);
  await writeAnimatedWebp(join(cfg.output, `${name}.turntable.webp`), cells, TURNTABLE_FPS);
  writeFileSync(join(cfg.output, `${name}.entity.json`), JSON.stringify(entity, null, 2) + "\n");
  const preview = join(cfg.output, `${name}.preview.html`);
  writeFileSync(preview, await standingPreviewHtml(name, cells));
  console.log(`Preview: ${preview}`);
  if (cfg.preview?.open) await openPreview(preview).catch(error => console.error(`Open the preview file in your browser: ${error.message}`));
  // the seed that actually produced the kept sheet, not the one we started with
  if (flags) writeFileSync(join(cfg.output, `${name}.sprute.yaml`), buildYaml({ ...cfg, seed }, flags.template, name));
  const exts = [
    ...(concept ? ["concept.png"] : []),
    "spritesheet.png",
    "turntable.webp",
    "entity.json",
    ...(flags ? ["sprute.yaml"] : []),
    ...(cfg.report ? ["report.md"] : []),
  ];
  console.log(`"${name}" -> ${cfg.output}/${name}.{${exts.join(",")}}`);
}

async function runSavedCharacter(cfg: ResolvedConfig) {
  const result = await cachedCharacterBuild(cfg, () => runBuild(cfg));
  if (result.reused) {
    const preview = join(cfg.output, `${cfg.name}.preview.html`);
    console.log(`Using saved character: ${cfg.name}\nPreview: ${preview}`);
    if (cfg.preview?.open) await openPreview(preview).catch(error => console.error(error.message));
  }
}

// ------------------------------------------------------------- dispatch --

const argv = process.argv.slice(2);
let first = argv[0];
if (first === 'demo') {
  try { await runTerminalDemo(); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}
if (first && /\.(png|jpe?g|webp)$/i.test(first)) {
  if (argv.length !== 1) throw new Error('For image-first builds, put options in sprute.config.json or the character specification.');
  const spec = await characterSpecForImage(first);
  console.log(`\n  sprute · ${first}\n`);
  console.log(`  ${spec.created ? 'Created' : 'Using'} ${spec.file}`);
  first = spec.file;
}

if (first === "animate") {
  try { await runAnimate(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "render-animation-drivers") {
  try { await runRenderAnimationDrivers(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "collect-animation-run") {
  try { await runCollectAnimationRun(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "submit-animation-plan") {
  try { await runSubmitAnimationPlan(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "upload-animation") {
  try { await runUploadAnimationInputs(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "check-animation-server") {
  try { await runCheckAnimationServer(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "plan-animation") {
  try { await runPlanAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "prepare-animation") {
  try { await runPrepareAnimationCharacter(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "export-godot") {
  try { await runExportGodot(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "upload-animation-drivers") {
  try { await runUploadAnimationDrivers(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "preview-animation") {
  try { await runPreviewAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "matte-animation") {
  try { await runMatteAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "submit-animation") {
  try { await runSubmitAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "extract-cycle") {
  try { await runExtractCycle(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "collect-animation") {
  try { await runCollectAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
  process.exit(process.exitCode ?? 0);
}

if (first === "review-animation") {
  try { await runReviewAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1); }
  process.exit(0);
}

if (first === "pack-animation") {
  try { await runPackAnimation(argv.slice(1)); }
  catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1); }
  process.exit(0);
}

if (first === "login") {
  await login();
  process.exit(0);
}
if (first === "init") {
  init();
  process.exit(0);
}
if (first === undefined) {
  const files = await discoverCharacters(process.cwd());
  if (!files.length) {
    console.error('No *.sprute.json character files found in this project.');
    process.exit(1);
  }
  // Validate the entire batch before the first possible paid generation call.
  const configs = await Promise.all(files.map(async file => {
    const local = await loadLocalCharacter(file);
    return local ? { local } : { legacy: await loadCharacterSpec(file) };
  }));
  for (let i = 0; i < configs.length; i++) {
    console.log(`Building ${files[i]}`);
    const entry = configs[i];
    if (entry.local) await buildLocalCharacter(entry.local);
    else await runSavedCharacter(entry.legacy!);
  }
  process.exit(0);
}
if (first === "help" || first === "--help" || first === "-h") {
  // bare invocation → interactive session (M2); until then, usage
  usage();
}

let flags: { cfg: ResolvedConfig; template?: string } | undefined;
let cfg: ResolvedConfig;
if (first.endsWith(".sprute.json")) {
  const local = await loadLocalCharacter(first);
  if (local) { await buildLocalCharacter(local); process.exit(0); }
  cfg = await loadCharacterSpec(first);
  await runSavedCharacter(cfg); process.exit(0);
} else if (/\.(ya?ml|json)$/.test(first)) {
  // rerun a saved build exactly — no project-config merge
  cfg = loadConfig(first);
} else if (first === "generate") {
  const { description, rest } = splitDesc(argv.slice(1));
  flags = configFromFlags(description, rest);
  cfg = flags.cfg;
} else if (first.startsWith("-")) {
  flags = configFromFlags(undefined, argv);
  cfg = flags.cfg;
} else {
  const { description, rest } = splitDesc(argv);
  flags = configFromFlags(description, rest);
  cfg = flags.cfg;
}

await runBuild(cfg, flags);
process.exit(0);
