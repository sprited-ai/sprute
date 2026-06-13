/** Minimal credential store: ~/.sprute/credentials.json, 0600. `sprute login`
 * writes here; key resolution (src/node/generate.ts) reads here after env and
 * ./.env. Keys are filed under their env-style name (REPLICATE_API_TOKEN,
 * FAL_KEY, …) so one store serves every provider. Plain local JSON — a provider
 * token is a spending bearer; it never leaves this machine and is never sent
 * anywhere but the provider it belongs to. */
import { readFileSync, writeFileSync, mkdirSync, existsSync, chmodSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const DIR = join(homedir(), ".sprute");
const FILE = join(DIR, "credentials.json");

export function credentialsPath(): string {
  return FILE;
}

type Store = Record<string, string>;

function read(): Store {
  if (!existsSync(FILE)) return {};
  try {
    return JSON.parse(readFileSync(FILE, "utf8")) as Store;
  } catch {
    return {};
  }
}

export function readKey(envKey: string): string | undefined {
  return read()[envKey];
}

export function writeKey(envKey: string, value: string): void {
  mkdirSync(DIR, { recursive: true });
  const store = read();
  store[envKey] = value;
  writeFileSync(FILE, JSON.stringify(store, null, 2) + "\n", { mode: 0o600 });
  // enforce 0600 even if the file pre-existed with looser permissions
  chmodSync(FILE, 0o600);
}
