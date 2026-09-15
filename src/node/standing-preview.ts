import sharp from 'sharp';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { SPIN_ORDER } from '../core/extract.js';
import type { RawImage } from '../core/image.js';

/** Offline compass preview of the actual generated pixels; no inference. */
export async function standingPreviewHtml(name: string, cells: RawImage[]) {
  if (cells.length !== 8) throw new Error('Standing preview requires eight direction cells');
  const images = await Promise.all(cells.map(async cell => {
    const png = await sharp(cell.data, { raw: { width: cell.width, height: cell.height, channels: 4 } }).png().toBuffer();
    return `data:image/png;base64,${png.toString('base64')}`;
  }));
  const escape = (s: string) => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
  const facing: Record<string, string> = {
    N: '↑ Back', NE: '↗ Back-right', E: '→ Right side', SE: '↘ Front-right',
    S: '↓ Front', SW: '↙ Front-left', W: '← Left side', NW: '↖ Back-left',
  };
  const slots = ['NW','N','NE','W',null,'E','SW','S','SE'];
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(name)} · Sprute</title>
<style>body{font:16px system-ui;background:#181b24;color:#eee;margin:24px auto;padding:0 16px;max-width:900px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0;padding:12px;background:#252b38;border-radius:12px;text-align:center}img{width:100%;height:clamp(90px,22vw,230px);object-fit:contain;image-rendering:pixelated}figcaption{padding:8px}figcaption small{display:block;margin-top:4px;color:#b8c3d9;background:#252b38;border-radius:4px;padding:4px}aside{display:grid;place-content:center;text-align:center}select{font:inherit;padding:8px}</style>
<h1>${escape(name)}</h1><p>Eight standing views. Labels show the expected direction, not a verified result. Compare each image with its arrow: up means facing away, down means facing you. Check clothes and accessories too. This is not a walking animation.</p>
<label>Background <select onchange="document.querySelectorAll('figure').forEach(f=>f.style.background=this.value)"><option value="#252b38">Dark</option><option value="#eee">Light</option><option value="#487451">Green</option></select></label>
<main>${slots.map(d=>d ? `<figure><img alt="Generated standing view; expected ${d}: ${facing[d]}" src="${images[SPIN_ORDER.indexOf(d as typeof SPIN_ORDER[number])]}"><figcaption>Expected ${d}<small>${facing[d]}</small></figcaption></figure>` : '<aside>Sprute<br>Standing poses</aside>').join('')}</main></html>`;
}

export async function openPreview(file: string): Promise<void> {
  const url = pathToFileURL(resolve(file)).href;
  const command = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'rundll32' : 'xdg-open';
  const args = process.platform === 'win32' ? ['url.dll,FileProtocolHandler',url] : [url];
  await new Promise<void>((done, reject) => {
    const child=spawn(command,args,{stdio:'ignore'});
    child.once('error',reject);child.once('close',code=>code===0?done():reject(new Error(`Browser opener exited ${code}`)));
  });
}
