import { readFile, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, join, resolve } from 'node:path';
import { loadProjectConfig } from '../config.js';

/** Image-first authoring: preserve a reusable spec next to the user's source. */
export async function characterSpecForImage(input: string) {
  const source = resolve(input);
  await readFile(source);
  const file = join(dirname(source), `${basename(source, extname(source))}.sprute.json`);
  const project = loadProjectConfig(process.cwd()) as Record<string, unknown>;
  const spec = { source: basename(source), states: ['standing'], directions: 8,
    ...(project.backend === 'local' ? { backend: 'local', frameSize: 128 } : {}) };
  try {
    await writeFile(file, JSON.stringify(spec, null, 2) + '\n', { flag: 'wx' });
    return { file, created: true };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
    const saved = JSON.parse(await readFile(file, 'utf8'));
    if (typeof saved.source !== 'string' || resolve(dirname(file), saved.source) !== source) {
      throw new Error(`${file} already describes another source; choose its specification explicitly`);
    }
    return { file, created: false };
  }
}
