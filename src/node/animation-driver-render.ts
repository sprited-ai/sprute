import { access, mkdtemp, rm, lstat } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { tmpdir } from 'node:os';

async function rendererPath() {
  const here = dirname(fileURLToPath(import.meta.url));
  // Bundled CLI lives in dist; development source lives in src/node.
  for (const relative of ['../motion/render-walk-drivers.py', '../../motion/render-walk-drivers.py']) {
    const candidate = resolve(here, relative);
    try { await access(candidate); return candidate; }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  }
  throw new Error('Bundled motion renderer is missing. Reinstall Sprute or use a complete development checkout.');
}

export async function renderAnimationDrivers(model: string | undefined, output: string, options: {
  blender?: string; ffmpeg?: string; scailMasks?: boolean; downloadTemplate?: boolean;
} = {}) {
  if (Boolean(model) === Boolean(options.downloadTemplate)) throw new Error('Choose a model.glb or --download-template, not both.');
  try { await lstat(resolve(output)); throw new Error(`Output already exists: ${output}`); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const script = await rendererPath();
  let blender = options.blender;
  if (!blender && process.platform === 'darwin') {
    const app = '/Applications/Blender.app/Contents/MacOS/Blender';
    try { await access(app); blender = app; } catch { /* Fall back to PATH. */ }
  }
  blender ??= 'blender';
  const prefix = ['--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1'];
  async function invoke(args: string[]) {
    await new Promise<void>((accept, reject) => {
      const child = spawn(blender!, args, {stdio: 'inherit', shell: false});
      child.once('error', error => reject(new Error(`Cannot start Blender (${blender}). Install Blender or pass --blender /path/to/blender. ${error.message}`)));
      child.once('close', (code, signal) => {
        if (code === 0) accept();
        else reject(new Error(`Motion preparation failed (${signal ? `signal ${signal}` : `exit ${code}`}). See the output above.`));
      });
    });
  }
  let temporary: string | undefined;
  try {
    if (options.downloadTemplate) {
      const downloader = join(dirname(script), 'download-template.py');
      await access(downloader);
      temporary = await mkdtemp(join(tmpdir(), 'sprute-template-'));
      model = join(temporary, 'walk-template.glb');
      await invoke([...prefix, '--python', downloader, '--', model]);
    }
    const args = [...prefix, '--python', script, '--', '--model', resolve(model!), '--output', resolve(output)];
    if (options.ffmpeg) args.push('--ffmpeg', options.ffmpeg);
    if (options.scailMasks) args.push('--scail-masks');
    await invoke(args);
  } finally { if (temporary) await rm(temporary, {recursive: true, force: true}); }

}

export async function runRenderAnimationDrivers(args: string[]) {
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log(`Make reusable walking guides for your animation server.

Download the supported template and render all eight SCAIL-2 guides:
  sprute render-animation-drivers --download-template --scail-masks -o my-walk-drivers

Or use the supported template you already downloaded:
  sprute render-animation-drivers walk-template.glb --scail-masks -o my-walk-drivers

Requires Blender and FFmpeg. The download is a verified Quaternius CC0 template.
Choose a new output folder. This renders guides; it submits no animation jobs.

Options:
  --download-template  Download the supported model instead of providing a GLB
  --scail-masks        Include the masks required by SCAIL-2
  -o, --output FOLDER  New folder for the eight guides
  --blender PATH      Blender executable (otherwise standard macOS app or PATH)
  --ffmpeg PATH       FFmpeg executable (otherwise PATH)

Next: upload-animation-drivers, then animate setup.
See docs/walking-setup.md in the source checkout for the complete setup.`);
    return;
  }
  const {values, positionals} = parseArgs({args, allowPositionals: true, options: {
    output: {type: 'string', short: 'o'}, blender: {type: 'string'}, ffmpeg: {type: 'string'},
    'scail-masks': {type: 'boolean', default: false},
    'download-template': {type: 'boolean', default: false},
  }});
  if (positionals.length !== (values['download-template'] ? 0 : 1) || !values.output) {
    throw new Error('Usage: sprute render-animation-drivers [model.glb | --download-template] -o new-folder [--scail-masks] [--blender PATH] [--ffmpeg PATH]');
  }
  await renderAnimationDrivers(positionals[0], values.output, {
    blender: values.blender, ffmpeg: values.ffmpeg, scailMasks: values['scail-masks'], downloadTemplate: values['download-template'],
  });
}
