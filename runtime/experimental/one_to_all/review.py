"""Build an RGB comparison page for a completed experimental batch."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image
from batch import DIRECTIONS, verify_result


def build(batch, output, ffmpeg='ffmpeg'):
    batch, output = Path(batch).resolve(), Path(output).absolute()
    state = json.loads((batch / 'state.json').read_text())
    if state['status'] != 'complete' or state['completed'] != DIRECTIONS:
        raise ValueError('Review requires all eight completed directions')
    plan = json.loads((batch / 'plan.json').read_text())
    sources = {}
    for direction in DIRECTIONS:
        folder = batch / direction
        verify_result(folder)
        run = json.loads((folder / 'run.json').read_text())
        if run['inputFiles'] != plan[direction]['inputFiles']:
            raise ValueError(f'Input provenance differs: {direction}')
        ref = Path(plan[direction]['conditioning']) / 'cache/image_input.png'
        if hashlib.sha256(ref.read_bytes()).hexdigest() != run['inputFiles']['image_input.png']:
            raise ValueError(f'Reference image changed: {direction}')
        frames = sorted((folder / 'output').rglob('frame_*.png'))
        for frame in frames:
            with Image.open(frame) as image:
                if image.size != (384, 384):
                    raise ValueError(f'Unexpected frame size: {direction}')
        sources[direction] = (ref, frames)
    subprocess.run([ffmpeg, '-version'], check=True, stdout=subprocess.DEVNULL)
    output.mkdir(exist_ok=False)
    cards, items = [], []
    for direction, (ref, frames) in sources.items():
        Image.open(ref).convert('RGB').save(output / f'{direction}-reference.png')
        # Copy the selected frames into a temporary numbered sequence within this new output.
        sequence = output / f'{direction}-frames';sequence.mkdir()
        for i, frame in enumerate(frames[32:64]):
            (sequence / f'{i:06d}.png').write_bytes(frame.read_bytes())
        video = output / f'{direction}.mp4'
        subprocess.run([ffmpeg, '-v', 'error', '-n', '-framerate', '24', '-i', str(sequence / '%06d.png'),
                        '-frames:v', '32', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', str(video)], check=True)
        for p in sequence.iterdir():p.unlink()
        sequence.rmdir()
        items.append({'direction': direction, 'video': video.name, 'videoSha256': hashlib.sha256(video.read_bytes()).hexdigest(),
                      'referenceSha256': hashlib.sha256(ref.read_bytes()).hexdigest(),
                      'selectedFrameHashes': [hashlib.sha256(p.read_bytes()).hexdigest() for p in frames[32:64]]})
        cards.append(f'<article><h2>{direction}</h2><div><img src="{direction}-reference.png" alt="{direction} original"><video src="{direction}.mp4" muted loop playsinline controls preload="auto"></video></div></article>')
    (output / 'manifest.json').write_text(json.dumps({'batch': str(batch), 'scope': 'RGB review only; no alpha, contact, loop or visual-quality approval', 'frames': '32..63 at24fps', 'items': items}, indent=2))
    (output / 'preview.html').write_text('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Sprute batch review</title><style>body{font:16px system-ui;background:#171a20;color:#eee;margin:24px}header{position:sticky;top:0;background:#171a20;padding:12px 0;z-index:1}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}article{padding:12px;background:#262b34;border-radius:8px}article div{display:flex}img,video{width:50%;object-fit:contain;image-rendering:pixelated}button,select{font:inherit;padding:8px}p{max-width:900px}</style><header><h1>Eight-direction batch review</h1><p>Original left; experimental RGB animation right. Generation completed, but appearance, facing, gait, foot contact and loops still require review. Equal timestamps do not prove matching foot phases. These videos have no transparency.</p><button id="play">Play all</button> <button id="restart">Restart all</button> <label>Speed <select id="speed"><option value="1">1×</option><option value="0.5">0.5×</option><option value="0.25">0.25×</option></select></label><p id="state" role="status">Paused</p></header><main>'''+''.join(cards)+'''</main><script>const vs=[...document.querySelectorAll('video')],play=document.querySelector('#play'),state=document.querySelector('#state');play.onclick=async()=>{if(vs.some(v=>!v.paused)){vs.forEach(v=>v.pause());play.textContent='Play all';state.textContent='Paused';}else{const results=await Promise.allSettled(vs.map(v=>v.play()));play.textContent='Pause all';state.textContent=results.every(x=>x.status==='fulfilled')?'Playing all':'Some videos could not play';}};document.querySelector('#restart').onclick=()=>vs.forEach(v=>v.currentTime=0);document.querySelector('#speed').onchange=e=>vs.forEach(v=>v.playbackRate=Number(e.target.value));</script>''')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ffmpeg', default='ffmpeg')
    a = p.parse_args()
    try:build(a.batch, a.output, a.ffmpeg)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:p.exit(2, f'Review failed: {exc}\n')
    print(a.output / 'preview.html')

if __name__ == '__main__':main()
