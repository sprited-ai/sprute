import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, writeFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readKey, writeKey, credentialsPath } from "../src/node/keystore.js";

let configDir: string;
const prev = process.env.SPRUTE_CONFIG_DIR;

beforeEach(() => {
  configDir = mkdtempSync(join(tmpdir(), "sprute-ks-"));
  process.env.SPRUTE_CONFIG_DIR = configDir;
});
afterEach(() => {
  rmSync(configDir, { recursive: true, force: true });
  if (prev === undefined) delete process.env.SPRUTE_CONFIG_DIR;
  else process.env.SPRUTE_CONFIG_DIR = prev;
});

describe("keystore", () => {
  it("honors SPRUTE_CONFIG_DIR for the path", () => {
    expect(credentialsPath()).toBe(join(configDir, "credentials.json"));
  });
  it("returns undefined when nothing is stored", () => {
    expect(readKey("REPLICATE_API_TOKEN")).toBeUndefined();
  });
  it("round-trips a key", () => {
    writeKey("REPLICATE_API_TOKEN", "r8_abc");
    expect(readKey("REPLICATE_API_TOKEN")).toBe("r8_abc");
  });
  it("keeps multiple keys side by side", () => {
    writeKey("REPLICATE_API_TOKEN", "r8_abc");
    writeKey("FAL_KEY", "fal_xyz");
    expect(readKey("REPLICATE_API_TOKEN")).toBe("r8_abc");
    expect(readKey("FAL_KEY")).toBe("fal_xyz");
  });
  it("overwrites an existing key", () => {
    writeKey("REPLICATE_API_TOKEN", "old");
    writeKey("REPLICATE_API_TOKEN", "new");
    expect(readKey("REPLICATE_API_TOKEN")).toBe("new");
  });
  it("writes the file 0600", () => {
    writeKey("REPLICATE_API_TOKEN", "r8_abc");
    expect(statSync(credentialsPath()).mode & 0o777).toBe(0o600);
  });
  it("treats a corrupt store as empty", () => {
    writeKey("REPLICATE_API_TOKEN", "r8_abc");
    writeFileSync(credentialsPath(), "{ not json");
    expect(readKey("REPLICATE_API_TOKEN")).toBeUndefined();
  });
});
