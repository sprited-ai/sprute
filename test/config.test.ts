import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, isAbsolute } from "node:path";
import { loadProjectConfig, resolveConfig, DEFAULT_TEMPLATE } from "../src/config.js";

let base: string;
beforeEach(() => {
  base = mkdtempSync(join(tmpdir(), "sprute-cfg-"));
});
afterEach(() => {
  rmSync(base, { recursive: true, force: true });
});

describe("loadProjectConfig", () => {
  it("returns {} when no project config is present", () => {
    expect(loadProjectConfig(base)).toEqual({});
  });
  it("reads sprute.config.json", () => {
    writeFileSync(join(base, "sprute.config.json"), JSON.stringify({ output: "./o", model: { provider: "replicate" } }));
    expect(loadProjectConfig(base)).toMatchObject({ output: "./o", model: { provider: "replicate" } });
  });
  it("reads sprute.config.yaml", () => {
    writeFileSync(join(base, "sprute.config.yaml"), "matting: floodfill\n");
    expect(loadProjectConfig(base)).toMatchObject({ matting: "floodfill" });
  });
});

describe("resolveConfig", () => {
  it("keeps a pinned numeric seed (seedRolled false)", () => {
    const r = resolveConfig({ seed: 123 }, base);
    expect(r.seed).toBe(123);
    expect(r.seedRolled).toBe(false);
  });
  it("rolls a seed when omitted or 'random' (seedRolled true)", () => {
    expect(resolveConfig({}, base).seedRolled).toBe(true);
    expect(typeof resolveConfig({}, base).seed).toBe("number");
    expect(resolveConfig({ seed: "random" }, base).seedRolled).toBe(true);
  });
  it("swaps a builtin template name for its absolute-path spec", () => {
    const r = resolveConfig({ template: DEFAULT_TEMPLATE }, base);
    expect(typeof r.template).toBe("object");
    expect(isAbsolute(r.template.image)).toBe(true);
  });
  it("throws on an unknown template", () => {
    expect(() => resolveConfig({ template: "nope-9000" }, base)).toThrow(/unknown template/);
  });
  it("resolves a relative reference against the base dir", () => {
    const r = resolveConfig({ reference: "ref.png" }, base);
    expect(r.reference).toBe(join(base, "ref.png"));
  });
  it("defaults output to the base dir", () => {
    expect(resolveConfig({}, base).output).toBe(base);
  });
});
