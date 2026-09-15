import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { loadProjectConfig } from '../config.js';
import { baseUrl } from './comfy-animation.js';

/** Prefer the project's single configuration file; retain existing setup files. */
export async function loadAnimationDefaults(base = process.cwd()) {
  const project = loadProjectConfig(base) as Record<string, unknown>;
  let raw = project.animation;
  if (raw === undefined) {
    try {
      raw = JSON.parse(await readFile(resolve(base,'sprute.animation.json'),'utf8'));
      if ((raw as {version?:number})?.version !== 1) throw new Error('Invalid sprute.animation.json version');
    } catch(error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
      throw error;
    }
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('animation must contain server and drivers');
  const config=raw as Record<string,unknown>;
  if (typeof config.server !== 'string' || typeof config.drivers !== 'string' || !config.drivers.trim()) throw new Error('animation requires server and drivers');
  return {server:baseUrl(config.server).href,drivers:resolve(base,config.drivers)};
}
