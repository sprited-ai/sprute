// Render an episode's stage to 60 fps JPEG frames, one screenshot per frame on a clock set by this script.
// usage: node shoot.mjs eps/<episode>.json <framesDir>
import { chromium } from '/Users/jin/.npm/_npx/9833c18b2d85bc59/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const [, , EP, OUT] = process.argv;
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const ep = JSON.parse(fs.readFileSync(EP, 'utf8'));
const FPS = 60;
const types = { '.html': 'text/html', '.json': 'application/json', '.cast': 'text/plain', '.webp': 'image/webp', '.png': 'image/png' };

// The stage fetches its files, which a file:// page can't.
const server = http.createServer((request, response) => {
  const file = path.join(ROOT, decodeURIComponent(new URL(request.url, 'http://x').pathname));
  if (!file.startsWith(ROOT) || !fs.existsSync(file)) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, { 'Content-Type': types[path.extname(file)] ?? 'application/octet-stream' });
  fs.createReadStream(file).pipe(response);
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()); });
page.on('pageerror', (e) => console.error('page:', e.message));
await page.goto(`http://localhost:${port}/stage.html?ep=${encodeURIComponent(path.relative(ROOT, path.resolve(EP)))}`);
await page.waitForFunction(() => window.__ready, null, { timeout: 60000 });

const total = Math.round(ep.minSeconds * FPS);
fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) fs.unlinkSync(path.join(OUT, f));
for (let f = 0; f < total; f++) {
  await page.evaluate((t) => window.__frame(t), f / FPS);
  // Let the terminal paint what was just written.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await page.screenshot({ path: path.join(OUT, `${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92 });
}
console.log(`${EP}: ${total} frames`);
await browser.close();
server.close();
