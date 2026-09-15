import { readdir, readFile } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { loadProjectConfig, resolveConfig, type CharacterConfig, type ResolvedConfig } from '../config.js';

/** Discover character specifications, excluding generated/dependency folders. */
export async function discoverCharacters(directory: string): Promise<string[]> {
  const root = resolve(directory), found: string[] = [];
  const excluded = new Set(['node_modules', '.git', '.sprute', 'outputs', 'dist', 'experiments']);
  async function visit(path: string) {
    for (const entry of await readdir(path, { withFileTypes: true })) {
      if (entry.name.startsWith('.') || excluded.has(entry.name)) continue;
      const file = join(path, entry.name);
      if (entry.isDirectory()) await visit(file);
      else if (entry.isFile() && entry.name.endsWith('.sprute.json')) found.push(file);
    }
  }
  await visit(root);
  return found.sort();
}

/** Adapt source-based character specs without silently ignoring future build fields. */
export async function loadCharacterSpec(file: string): Promise<ResolvedConfig> {
  const absolute = resolve(file), base = dirname(absolute);
  const projectBase = process.cwd();
  const project = loadProjectConfig(projectBase) as Record<string, unknown>;
  if (project.backend !== undefined || project.generation !== undefined || project.states !== undefined) {
    throw new Error('Project backend/state orchestration is not connected yet; no generation started');
  }
  const raw = JSON.parse(await readFile(absolute, 'utf8'));
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('Character specification must be an object');
  if (raw.source !== undefined && (typeof raw.source !== 'string' || !raw.source.trim())) throw new Error('source must be an image path');
  if (raw.source !== undefined && raw.reference !== undefined) throw new Error('Use source or reference, not both');
  // Until a backend is actually connected, never fall through to paid generation.
  if (raw.backend !== undefined) throw new Error(`Backend "${raw.backend}" is not connected to character-spec builds yet; no generation started`);
  if (raw.states !== undefined && (!Array.isArray(raw.states) || raw.states.length !== 1 || raw.states[0] !== 'standing')) {
    throw new Error('Character-spec state orchestration is not connected yet; only ["standing"] is supported here. No generation started');
  }
  if (raw.directions !== undefined && raw.directions !== 8) throw new Error('Only 8 directions are supported');
  if (raw.frameSize !== undefined) throw new Error('frameSize is not connected to character-spec builds yet; no generation started');
  const { source, states, directions, ...legacy } = raw;
  const defaults = project as Partial<CharacterConfig>;
  const projectPaths = {
    ...(defaults.fixedDirections ? {fixedDirections: resolveConfig({fixedDirections:defaults.fixedDirections},projectBase).fixedDirections} : {}),
    ...(defaults.output !== undefined ? { output: resolve(projectBase, defaults.output) } : {}),
    ...(defaults.reference !== undefined ? { reference: resolve(projectBase, defaults.reference) } : {}),
    ...(typeof defaults.template === 'object' ? { template: { ...defaults.template, image: resolve(projectBase, defaults.template.image) } } : {}),
  };
  const config: CharacterConfig = { ...defaults, ...projectPaths, ...legacy,
    ...(defaults.model || legacy.model ? { model: { ...defaults.model, ...legacy.model } } : {}),
    name: raw.name ?? basename(absolute, '.sprute.json'),
    preview: { open: true, ...defaults.preview, ...legacy.preview },
    ...(source !== undefined ? { reference: source } : {}),
  };
  return resolveConfig(config, base);
}
