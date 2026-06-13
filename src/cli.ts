#!/usr/bin/env node
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
import { parseArgs } from "node:util";
import { join, relative } from "node:path";
import { writeFileSync, existsSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import YAML from "yaml";
import { writePng, writeAnimatedWebp, writeBytes } from "./node/io.js";
import { loadConfig, loadProjectConfig, resolveConfig } from "./config.js";
import type { CharacterConfig, ResolvedConfig } from "./config.js";
import { startProgress } from "./node/progress.js";
import { startReport } from "./node/report.js";
import { buildCharacter, nextCharName } from "./node/build.js";
import { writeKey, credentialsPath } from "./node/keystore.js";

// ~417ms per direction — slow enough to actually look at each pose
const TURNTABLE_FPS = 2.4;

function usage(): never {
  console.error("usage:");
  console.error('  sprute "a small forest fairy"      generate from a description');
  console.error('  sprute generate "a goblin archer"  explicit form of the same');
  console.error("  sprute <name>.sprute.yaml          rerun a saved build exactly");
  console.error('  sprute -d "…" [-r ref.png] …       flags-only build');
  console.error("  sprute init                        write ./sprute.config.json");
  console.error("  sprute login                       set up an image-model key");
  console.error("");
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

/** Split leading bare words (the description) from the first flag onward, so
 * both `sprute "a forest fairy"` and `sprute a forest fairy --seed 42` work. */
function splitDesc(args: string[]): { description?: string; rest: string[] } {
  const i = args.findIndex((a) => a.startsWith("-"));
  const words = i === -1 ? args : args.slice(0, i);
  return { description: words.length ? words.join(" ") : undefined, rest: i === -1 ? [] : args.slice(i) };
}

/** Merge precedence: flags > prompt > ./sprute.config.json > builtin. */
function configFromFlags(description: string | undefined, args: string[]): { cfg: ResolvedConfig; template?: string } {
  const { values: b } = parseArgs({
    args,
    options: {
      description: { type: "string", short: "d" },
      reference: { type: "string", short: "r" },
      seed: { type: "string" },
      output: { type: "string", short: "o" },
      sheet: { type: "boolean" },
      template: { type: "string" },
      provider: { type: "string" },
      matting: { type: "string" },
      "no-check": { type: "boolean" },
      "max-fixes": { type: "string" },
      report: { type: "boolean" },
      intermediate: { type: "boolean" },
    },
  });
  if (b.matting !== undefined && b.matting !== "floodfill" && b.matting !== "toonout") {
    throw new Error(`--matting wants "floodfill" or "toonout", got "${b.matting}"`);
  }
  if (b["max-fixes"] !== undefined && !Number.isInteger(Number(b["max-fixes"]))) {
    throw new Error(`--max-fixes wants an integer, got "${b["max-fixes"]}"`);
  }
  if (b.seed !== undefined && b.seed !== "random" && !Number.isInteger(Number(b.seed))) {
    throw new Error(`--seed wants an integer or "random", got "${b.seed}"`);
  }
  const project = loadProjectConfig(process.cwd());
  const template = b.template ?? (typeof project.template === "string" ? project.template : undefined);
  const cfg = resolveConfig(
    {
      name: project.name,
      description: b.description ?? description ?? project.description,
      reference: b.reference ?? project.reference,
      seed: b.seed === undefined ? project.seed : b.seed === "random" ? undefined : Number(b.seed),
      output: b.output ?? project.output ?? "./outputs",
      template: b.template ?? project.template,
      model: b.provider ? { provider: b.provider as NonNullable<CharacterConfig["model"]>["provider"] } : project.model,
      outputs: b.sheet ? { sheet: true } : project.outputs,
      matting: (b.matting as CharacterConfig["matting"]) ?? project.matting,
      check: b["no-check"] ? false : project.check,
      maxFixes: b["max-fixes"] !== undefined ? Number(b["max-fixes"]) : project.maxFixes,
      report: b.report || project.report || undefined,
      intermediate: b.intermediate || project.intermediate || undefined,
    },
    process.cwd(),
  );
  // resolveConfig swaps the template name for its spec — keep the name for the yaml
  return { cfg, template };
}

/** Flag/prompt builds drop a config next to the outputs, with the resolved name
 * and seed baked in — `sprute <name>.sprute.yaml` reruns the exact build.
 * Paths are written relative to the yaml, which is how loadConfig reads them. */
function buildYaml(cfg: ResolvedConfig, templateName: string | undefined, name: string): string {
  return YAML.stringify({
    name,
    ...(cfg.description && { description: cfg.description }),
    ...(cfg.reference && { reference: relative(cfg.output, cfg.reference) }),
    seed: cfg.seed,
    ...(templateName && { template: templateName }),
    ...(cfg.model?.provider && { model: { provider: cfg.model.provider } }),
    ...(cfg.outputs?.sheet && { outputs: { sheet: cfg.outputs.sheet } }),
    ...(cfg.matting && { matting: cfg.matting }),
    ...(cfg.check === false && { check: false }),
    ...(cfg.maxFixes !== undefined && { maxFixes: cfg.maxFixes }),
    ...(cfg.report && { report: true }),
    ...(cfg.intermediate && { intermediate: true }),
  });
}

/** A name from the description ("a small forest fairy" → "a-small-forest-fairy"),
 * de-duped against existing outputs; falls back to the char-NNN counter. */
function deriveName(cfg: ResolvedConfig): string {
  if (!cfg.description) return nextCharName(cfg.output);
  const base =
    cfg.description.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").split("-").slice(0, 4).join("-") ||
    "char";
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

// ------------------------------------------------------------- dispatch --

const argv = process.argv.slice(2);
const first = argv[0];

if (first === "login") {
  await login();
  process.exit(0);
}
if (first === "init") {
  init();
  process.exit(0);
}
if (first === undefined || first === "help" || first === "--help" || first === "-h") {
  // bare invocation → interactive session (M2); until then, usage
  usage();
}

let flags: { cfg: ResolvedConfig; template?: string } | undefined;
let cfg: ResolvedConfig;
if (/\.(ya?ml|json)$/.test(first)) {
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
