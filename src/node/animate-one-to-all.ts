import { spawn } from 'node:child_process';
import { parseArgs } from 'node:util';
import { resolve } from 'node:path';

export function oneToAllInvocation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    plan: { type: 'string' }, runtime: { type: 'string' }, python: { type: 'string' },
    runner: { type: 'string' }, output: { type: 'string', short: 'o' },
    check: { type: 'boolean' }, resume: { type: 'boolean' }, resident: { type: 'boolean' },
  } });
  if (positionals.length || !values.plan?.trim() || !values.python?.trim() || !values.runner?.trim()) {
    throw new Error('Provide --plan, --python and --runner (the installed batch.py path). This command requires eight prepared conditioning caches.');
  }
  if (values.check && (values.resume || values.resident || values.output || values.runtime)) {
    throw new Error('--check validates only the plan; omit generation and resume options.');
  }
  if (!values.check && (!values.runtime?.trim() || !values.output?.trim())) {
    throw new Error('Generation requires --runtime and -o. Existing output requires --resume.');
  }
  const command = [resolve(values.runner), '--plan', resolve(values.plan)];
  if (values.check) command.push('--check');
  else {
    command.push('--runtime', resolve(values.runtime!), '--output', resolve(values.output!));
    if (values.resume) command.push('--resume');
    if (values.resident) command.push('--resident');
  }
  return { executable: values.python, args: command };
}

/** Explicit inclusive frame selection; cycle quality remains a human decision. */
export function oneToAllCycleInvocation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    batch: { type: 'string' }, python: { type: 'string' }, runner: { type: 'string' },
    output: { type: 'string', short: 'o' }, start: { type: 'string' }, end: { type: 'string' },
  } });
  if (positionals.length || !values.batch?.trim() || !values.python?.trim() ||
      !values.runner?.trim() || !values.output?.trim()) {
    throw new Error('Provide --batch, --python, --runner (cycles.py), and -o.');
  }
  const start = Number(values.start), end = Number(values.end);
  if (!/^\d+$/.test(values.start ?? '') || !/^\d+$/.test(values.end ?? '') ||
      !Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || start >= end || end >= 65) {
    throw new Error('Select at least two frames with --start and --end: 0 <= start < end < 65 (inclusive).');
  }
  return { executable: values.python, args: [resolve(values.runner), '--batch', resolve(values.batch),
    '--output', resolve(values.output), '--start', String(start), '--end', String(end)] };
}

export async function runOneToAll(args: string[]) {
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log(`Experimental local animation from eight prepared conditioning caches.

sprute animate one-to-all --plan plan.json --python /path/to/venv/bin/python --runner /path/to/batch.py --check
sprute animate one-to-all --plan plan.json --python /path/to/venv/bin/python --runner /path/to/batch.py --runtime /path/to/runtime -o new-batch --resident

sprute animate one-to-all extract --batch new-batch --python /path/to/venv/bin/python --runner /path/to/cycles.py --start 32 --end 63 -o rgb-cycles

Extract copies an explicitly selected inclusive range into eight cycle folders.
It requires Pillow, verifies the completed batch, and does not approve the loop.
Repeat generation arguments with --resume to continue verified completed work.
Ctrl+C asks the runner to finish the current direction, then pause.
Requires a configured Linux CUDA runtime. This does not prepare a new character,
remove backgrounds or export a game atlas. See docs/local-animation.md.`);
    return;
  }
  const invocation = args[0] === 'extract'
    ? oneToAllCycleInvocation(args.slice(1)) : oneToAllInvocation(args);
  const code = await new Promise<number>((resolveExit, reject) => {
    const child = spawn(invocation.executable, invocation.args, {
      stdio: 'inherit', detached: process.platform !== 'win32', shell: false,
    });
    const interrupt = () => { child.kill('SIGINT'); };
    const terminate = () => { child.kill('SIGTERM'); };
    const cleanup = () => {
      process.removeListener('SIGINT', interrupt);
      process.removeListener('SIGTERM', terminate);
    };
    process.on('SIGINT', interrupt);
    process.on('SIGTERM', terminate);
    child.once('error', error => { cleanup(); reject(error); });
    child.once('exit', (status, signal) => {
      cleanup();
      resolveExit(status ?? (signal === 'SIGINT' ? 130 : signal === 'SIGTERM' ? 143 : 1));
    });
  });
  process.exitCode = code;
}
