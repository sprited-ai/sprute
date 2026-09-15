import sharp from 'sharp';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { emitKeypressEvents } from 'node:readline';

const directions = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW'];
const arrows = ['↓', '↘', '→', '↗', '↑', '↖', '←', '↙'];

/** Two square pixels per terminal cell; alpha composited on the stage. */
export function terminalPixels(data: Uint8Array, width: number, height: number) {
  const color = (x: number, y: number) => {
    const p = (y * width + x) * 4, a = (data[p + 3] ?? 0) / 255;
    return [0, 1, 2].map(c => Math.round((data[p + c] ?? 0) * a + 22 * (1 - a))).join(';');
  };
  const rows: string[] = [];
  for (let y = 0; y < height; y += 2) {
    let row = '  ';
    for (let x = 0; x < width; x++) row += `\x1b[38;2;${color(x, y)}m\x1b[48;2;${color(x, y + 1)}m▀`;
    rows.push(row + '\x1b[0m');
  }
  return rows.join('\n');
}

export async function showStandingInTerminal(file: string, cellSize: number) {
  if (!process.stdout.isTTY || process.env.TERM === 'dumb') return;
  const size = Math.max(8, Math.min(48, (process.stdout.rows - 8) * 2, process.stdout.columns - 4)) & ~1;
  const data = await sharp(file).extract({left: 0, top: 0, width: cellSize, height: cellSize})
    .resize(size, size, {kernel: 'nearest'}).ensureAlpha().raw().toBuffer();
  console.log(terminalPixels(data, size, size));
}

export async function runTerminalDemo() {
  const file = ['../assets/demo/walk.png', '../../assets/demo/walk.png']
    .map(p => fileURLToPath(new URL(p, import.meta.url))).find(existsSync);
  if (!file) throw new Error('Bundled demo sprite is missing.');
  if (!process.stdout.isTTY || !process.stdin.isTTY || process.env.TERM === 'dumb') {
    console.log('sprute demo — run in an interactive color terminal.\nPre-generated sample · 8 directions · 16 drawings per direction · no GPU or API needed.');
    return;
  }
  const size = Math.max(8, Math.min(64, (process.stdout.rows - 10) * 2, process.stdout.columns - 6)) & ~1;
  const frames: string[][] = [];
  for (let d = 0; d < 8; d++) {
    frames[d] = await Promise.all(Array.from({length: 16}, async (_, f) => {
      const data = await sharp(file).extract({left: f * 64, top: d * 64, width: 64, height: 64})
        .resize(size, size, {kernel: 'nearest'}).ensureAlpha().raw().toBuffer();
      return terminalPixels(data, size, size);
    }));
  }
  let direction = 0, frame = 0, paused = false;
  const draw = () => process.stdout.write('\x1b[H' +
    '  \x1b[1;38;2;173;238;154msprute\x1b[0m  /  first steps\x1b[K\n\n' + frames[direction][frame] +
    `\n\n  ${arrows[direction]} ${directions[direction]}  ·  ${paused ? 'paused ' : 'walking'}  ·  8 directions\x1b[K\n` +
    '  Arrows / QWE ASD ZXC: face   Space: pause   Esc: leave\x1b[K\n' +
    '  Pre-generated sample · local playback · no API calls\x1b[K\n');
  const wasRaw = process.stdin.isRaw;
  emitKeypressEvents(process.stdin);
  process.stdin.setRawMode(true); process.stdin.resume();
  process.stdout.write('\x1b[?1049h\x1b[?25l\x1b[2J');
  await new Promise<void>(resolve => {
    const timer = setInterval(() => { if (!paused) frame = (frame + 1) % 16; draw(); }, 1000 / 12);
    const finish = () => {
      clearInterval(timer); process.stdin.off('keypress', keypress);
      process.off('SIGTERM', finish); process.off('SIGINT', finish);
      process.stdin.setRawMode(wasRaw); process.stdin.pause();
      process.stdout.write('\x1b[0m\x1b[?25h\x1b[?1049l'); resolve();
    };
    const keypress = (text: string, key: {name?: string; ctrl?: boolean}) => {
      if (key.name === 'escape' || (key.ctrl && key.name === 'c')) return finish();
      if (key.name === 'space') paused = !paused;
      const mapping: Record<string, number> = {down:0, x:0, c:1, right:2, d:2, e:3, up:4, w:4, q:5, left:6, a:6, z:7, s:0};
      const next = mapping[key.name ?? text];
      if (next !== undefined) direction = next;
      draw();
    };
    process.stdin.on('keypress', keypress);
    process.on('SIGTERM', finish); process.on('SIGINT', finish); draw();
  });
  console.log('\n  Your turn: sprute character.png\n  Local generation requires sprute.config.json and installed models.\n');
}
