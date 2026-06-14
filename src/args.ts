/** Pure CLI argument logic — no process, fs, or network. Extracted from cli.ts
 * so the dispatch parsing and the config-merge precedence are unit-testable;
 * cli.ts keeps the process/IO/network wiring. */
import { parseArgs } from "node:util";
import { relative } from "node:path";
import YAML from "yaml";
import type { CharacterConfig, ResolvedConfig } from "./config.js";

/** Split leading bare words (the description) from the first flag onward, so
 * both `sprute "a forest fairy"` and `sprute a forest fairy --seed 42` work. */
export function splitDesc(args: string[]): { description?: string; rest: string[] } {
  const i = args.findIndex((a) => a.startsWith("-"));
  const words = i === -1 ? args : args.slice(0, i);
  return { description: words.length ? words.join(" ") : undefined, rest: i === -1 ? [] : args.slice(i) };
}

/** A name from a description: "a small forest fairy" → "a-small-forest-fairy"
 * (first four words, kebab-cased). Empty/punctuation-only falls back to "char". */
export function slugify(description: string): string {
  return (
    description
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .split("-")
      .filter(Boolean)
      .slice(0, 4)
      .join("-") || "char"
  );
}

export interface BuildFlags {
  description?: string;
  reference?: string;
  seed?: string;
  output?: string;
  sheet?: boolean;
  template?: string;
  provider?: string;
  matting?: string;
  "no-check"?: boolean;
  "max-fixes"?: string;
  report?: boolean;
  intermediate?: boolean;
}

/** parseArgs + validation for the build flags. Throws on a bad --matting,
 * --seed, or --max-fixes. */
export function parseFlags(args: string[]): BuildFlags {
  const { values } = parseArgs({
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
  if (values.matting !== undefined && values.matting !== "floodfill" && values.matting !== "toonout") {
    throw new Error(`--matting wants "floodfill" or "toonout", got "${values.matting}"`);
  }
  if (values["max-fixes"] !== undefined && !Number.isInteger(Number(values["max-fixes"]))) {
    throw new Error(`--max-fixes wants an integer, got "${values["max-fixes"]}"`);
  }
  if (values.seed !== undefined && values.seed !== "random" && !Number.isInteger(Number(values.seed))) {
    throw new Error(`--seed wants an integer or "random", got "${values.seed}"`);
  }
  return values as BuildFlags;
}

/** Merge precedence: flags > prompt > project config > builtin. Returns the
 * CharacterConfig to hand to resolveConfig, plus the template name kept aside
 * for the reproducible yaml (resolveConfig swaps the name for its spec). */
export function mergeConfig(
  flags: BuildFlags,
  description: string | undefined,
  project: Partial<CharacterConfig>,
): { cfg: CharacterConfig; template?: string } {
  const cfg: CharacterConfig = {
    name: project.name,
    description: flags.description ?? description ?? project.description,
    reference: flags.reference ?? project.reference,
    seed: flags.seed === undefined ? project.seed : flags.seed === "random" ? undefined : Number(flags.seed),
    output: flags.output ?? project.output ?? "./outputs",
    template: flags.template ?? project.template,
    model: flags.provider ? { provider: flags.provider as NonNullable<CharacterConfig["model"]>["provider"] } : project.model,
    outputs: flags.sheet ? { sheet: true } : project.outputs,
    matting: (flags.matting as CharacterConfig["matting"]) ?? project.matting,
    check: flags["no-check"] ? false : project.check,
    maxFixes: flags["max-fixes"] !== undefined ? Number(flags["max-fixes"]) : project.maxFixes,
    report: flags.report || project.report || undefined,
    intermediate: flags.intermediate || project.intermediate || undefined,
  };
  const template = flags.template ?? (typeof project.template === "string" ? project.template : undefined);
  return { cfg, template };
}

/** A build's reproducible config, dropped next to the outputs with the resolved
 * name and seed baked in — `sprute <name>.sprute.yaml` reruns it exactly. Paths
 * are written relative to the yaml, which is how loadConfig reads them back. */
export function buildYaml(cfg: ResolvedConfig, templateName: string | undefined, name: string): string {
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
