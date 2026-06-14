import { describe, it, expect } from "vitest";
import YAML from "yaml";
import { splitDesc, slugify, parseFlags, mergeConfig, buildYaml } from "../src/args.js";
import type { ResolvedConfig } from "../src/config.js";

describe("splitDesc", () => {
  it("treats a single quoted arg as the description", () => {
    expect(splitDesc(["a forest fairy"])).toEqual({ description: "a forest fairy", rest: [] });
  });
  it("joins leading bare words (unquoted)", () => {
    expect(splitDesc(["a", "forest", "fairy"])).toEqual({ description: "a forest fairy", rest: [] });
  });
  it("splits description from the first flag onward", () => {
    expect(splitDesc(["a", "fairy", "--seed", "42"])).toEqual({ description: "a fairy", rest: ["--seed", "42"] });
  });
  it("is all-flags when the first arg is a flag", () => {
    expect(splitDesc(["--seed", "42"])).toEqual({ description: undefined, rest: ["--seed", "42"] });
  });
  it("is empty for no args", () => {
    expect(splitDesc([])).toEqual({ description: undefined, rest: [] });
  });
});

describe("slugify", () => {
  it("kebab-cases the first four words", () => {
    expect(slugify("a small forest fairy")).toBe("a-small-forest-fairy");
    expect(slugify("a really long five word description")).toBe("a-really-long-five");
  });
  it("drops punctuation", () => {
    expect(slugify("Goblin Archer!!")).toBe("goblin-archer");
  });
  it("falls back to char for empty/punctuation-only", () => {
    expect(slugify("")).toBe("char");
    expect(slugify("!!! ???")).toBe("char");
  });
});

describe("parseFlags", () => {
  it("parses short and long flags", () => {
    expect(parseFlags(["-d", "x", "-o", "out", "--sheet"])).toMatchObject({ description: "x", output: "out", sheet: true });
  });
  it("accepts valid matting / seed / max-fixes", () => {
    expect(() => parseFlags(["--matting", "toonout", "--seed", "42", "--max-fixes", "3"])).not.toThrow();
    expect(() => parseFlags(["--seed", "random"])).not.toThrow();
  });
  it("rejects a bad --matting", () => {
    expect(() => parseFlags(["--matting", "nope"])).toThrow(/matting/);
  });
  it("rejects a non-integer --seed", () => {
    expect(() => parseFlags(["--seed", "abc"])).toThrow(/seed/);
  });
  it("rejects a non-integer --max-fixes", () => {
    expect(() => parseFlags(["--max-fixes", "x"])).toThrow(/max-fixes/);
  });
});

describe("mergeConfig precedence (flags > prompt > project > builtin)", () => {
  it("flag description beats prompt beats project", () => {
    expect(mergeConfig({ description: "flag" }, "prompt", { description: "proj" }).cfg.description).toBe("flag");
    expect(mergeConfig({}, "prompt", { description: "proj" }).cfg.description).toBe("prompt");
    expect(mergeConfig({}, undefined, { description: "proj" }).cfg.description).toBe("proj");
  });
  it("defaults output to ./outputs, project can set it, flag overrides", () => {
    expect(mergeConfig({}, undefined, {}).cfg.output).toBe("./outputs");
    expect(mergeConfig({}, undefined, { output: "proj" }).cfg.output).toBe("proj");
    expect(mergeConfig({ output: "flag" }, undefined, { output: "proj" }).cfg.output).toBe("flag");
  });
  it("provider: flag wins, else project model", () => {
    expect(mergeConfig({ provider: "fal" }, undefined, { model: { provider: "gemini" } }).cfg.model?.provider).toBe("fal");
    expect(mergeConfig({}, undefined, { model: { provider: "gemini" } }).cfg.model?.provider).toBe("gemini");
    expect(mergeConfig({}, undefined, {}).cfg.model).toBeUndefined();
  });
  it("seed: number from flag, undefined for random, project fallback", () => {
    expect(mergeConfig({ seed: "42" }, undefined, {}).cfg.seed).toBe(42);
    expect(mergeConfig({ seed: "random" }, undefined, { seed: 7 }).cfg.seed).toBeUndefined();
    expect(mergeConfig({}, undefined, { seed: 7 }).cfg.seed).toBe(7);
  });
  it("--no-check forces check:false, else project", () => {
    expect(mergeConfig({ "no-check": true }, undefined, { check: true }).cfg.check).toBe(false);
    expect(mergeConfig({}, undefined, { check: false }).cfg.check).toBe(false);
  });
  it("reports the template name (flag, or project when a string)", () => {
    expect(mergeConfig({ template: "8dir-v2" }, undefined, {}).template).toBe("8dir-v2");
    expect(mergeConfig({}, undefined, { template: "8dir-v1" }).template).toBe("8dir-v1");
    expect(mergeConfig({}, undefined, {}).template).toBeUndefined();
  });
});

describe("buildYaml", () => {
  const base = {
    name: "fairy",
    description: "a fairy",
    seed: 99,
    output: "/a/b",
    reference: "/a/b/ref.png",
    template: {} as ResolvedConfig["template"],
    seedRolled: false,
    matting: "toonout",
    model: { provider: "replicate" },
  } as ResolvedConfig;

  it("round-trips the reproducible fields, reference relative to output", () => {
    const parsed = YAML.parse(buildYaml(base, "8dir-v1", "fairy"));
    expect(parsed).toMatchObject({
      name: "fairy",
      description: "a fairy",
      seed: 99,
      template: "8dir-v1",
      reference: "ref.png",
      matting: "toonout",
      model: { provider: "replicate" },
    });
  });
  it("omits absent optionals", () => {
    const parsed = YAML.parse(buildYaml({ name: "x", seed: 1, output: ".", template: {} } as ResolvedConfig, undefined, "x"));
    expect(parsed.reference).toBeUndefined();
    expect(parsed.template).toBeUndefined();
    expect(parsed.report).toBeUndefined();
  });
});
