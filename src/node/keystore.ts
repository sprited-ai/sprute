/** Minimal credential store: ~/.sprute/credentials.json, 0600. `sprute login`
 * writes here; key resolution (src/node/generate.ts) reads here after env and
 * ./.env. Keys are filed under their env-style name (REPLICATE_API_TOKEN,
 * FAL_KEY, …) so one store serves every provider. Plain local JSON — a provider
 * token is a spending bearer; it never leaves this machine and is never sent
 * anywhere but the provider it belongs to. */
import { readFileSync, writeFileSync, mkdirSync, existsSync, chmodSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

// computed lazily (not at module load) so it tracks the environment.
// SPRUTE_CONFIG_DIR relocates the store (CI, sandboxes, tests).
function dir(): string {
  return process.env.SPRUTE_CONFIG_DIR ?? join(homedir(), ".sprute");
}

export function credentialsPath(): string {
  return join(dir(), "credentials.json");
}

type Store = Record<string, string>;

function read(): Store {
  const file = credentialsPath();
  if (!existsSync(file)) return {};
  try {
    return JSON.parse(readFileSync(file, "utf8")) as Store;
  } catch {
    return {};
  }
}

export function readKey(envKey: string): string | undefined {
  return read()[envKey];
}

export function writeKey(envKey: string, value: string): void {
  mkdirSync(dir(), { recursive: true });
  const store = read();
  store[envKey] = value;
  const file = credentialsPath();
  writeFileSync(file, JSON.stringify(store, null, 2) + "\n", { mode: 0o600 });
  // enforce 0600 even if the file pre-existed with looser permissions
  chmodSync(file, 0o600);
}
