/** Show actual stages and elapsed time; never invent percentage/ETA. */
export function buildProgress(stream: NodeJS.WriteStream = process.stderr) {
  let timer: ReturnType<typeof setInterval> | undefined;
  let active = '', started = 0;
  const clear = () => {
    if (timer) clearInterval(timer);
    timer = undefined;
    if (active && stream.isTTY) stream.write('\r\x1b[2K');
  };
  const draw = () => stream.write(`\r\x1b[2K  ◉ ${active} · ${Math.floor((Date.now() - started) / 1000)}s`);
  return {
    start(label: string) {
      clear(); active = label; started = Date.now();
      if (stream.isTTY) { draw(); timer = setInterval(draw, 1000); timer.unref(); }
      else stream.write(`  … ${label}\n`);
    },
    done(label: string) { clear(); active = ''; stream.write(`  ✓ ${label}\n`); },
    fail(label: string) { clear(); active = ''; stream.write(`  ✗ ${label}\n`); },
    close() { clear(); active = ''; },
  };
}
