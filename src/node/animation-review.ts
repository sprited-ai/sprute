import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { promisify, parseArgs } from 'node:util';
import { lstat, mkdir, mkdtemp, rename, rm, rmdir, writeFile, readdir } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';

const exec = promisify(execFile);
const MAX_FRAMES = 600;
const MAX_PIXELS = 128_000_000;

async function fileHash(path: string) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest('hex');
}

export async function reviewAnimation(videoPath: string, outputPath: string, grid = '1x1') {
  const match = /^(\d+)x(\d+)$/.exec(grid);
  const [columns, rows] = match ? match.slice(1).map(Number) : [0, 0];
  if (!columns || !rows || columns * rows > 8) throw new Error('Grid must be columns x rows, with 1–8 cells (for example 4x2).');
  const input = resolve(videoPath), output = resolve(outputPath);
  if (!(await lstat(input)).isFile()) throw new Error('Input must be a local video file.');
  try { await lstat(output); throw new Error(`Output already exists: ${output}`); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  const sourceSha256 = await fileHash(input);
  let probe: any;
  try {
    const { stdout } = await exec('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_frames',
      '-show_entries', 'stream=width,height,avg_frame_rate:stream_side_data=rotation:frame=best_effort_timestamp_time,pkt_duration_time', '-of', 'json', input],
      { maxBuffer: 16 * 1024 * 1024, timeout: 120_000 });
    probe = JSON.parse(stdout);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === 'ENOENT') throw new Error('Install FFmpeg (ffmpeg and ffprobe) to review videos.');
    throw e;
  }
  const stream = probe.streams?.[0], frames = probe.frames;
  const width = stream?.width, height = stream?.height;
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0 || !frames?.length) throw new Error('No decodable video frames.');
  if (frames.length > MAX_FRAMES || width * height * frames.length > MAX_PIXELS) throw new Error('Review limit: 600 frames and 128 million decoded pixels. Trim or resize the video first.');
  if (width % columns || height % rows) throw new Error('Video dimensions must divide evenly into the grid.');
  if (stream.side_data_list?.some((x: any) => x.rotation && x.rotation % 360)) throw new Error('Normalize video rotation before reviewing.');
  const [num, den] = String(stream.avg_frame_rate).split('/').map(Number);
  const fallback = num > 0 && den > 0 ? den / num : 1 / 24;
  const times = frames.map((f: any) => Number(f.best_effort_timestamp_time));
  if (times.some((t: number, i: number) => !Number.isFinite(t) || (i && t < times[i - 1]))) throw new Error('Video needs monotonic frame timestamps.');
  const metadata = { version: 1, source: basename(input), sourceSha256, width, height, columns, rows, frameCount: frames.length,
    reviewStatus: 'unreviewed', frames: times.map((t: number, i: number) => ({ file: `frames/${String(i + 1).padStart(6, '0')}.png`,
      sha256: '',
      time: t - times[0], duration: i + 1 < times.length && times[i + 1] > t ? times[i + 1] - t : Number(frames[i].pkt_duration_time) > 0 ? Number(frames[i].pkt_duration_time) : fallback })) };
  await mkdir(dirname(output), { recursive: true });
  const temp = await mkdtemp(join(dirname(output), '.sprute-review-'));
  try {
    await mkdir(join(temp, 'frames'));
    await exec('ffmpeg', ['-v', 'error', '-noautorotate', '-i', input, '-map', '0:v:0', '-fps_mode', 'passthrough', '-frames:v', String(MAX_FRAMES + 1), join(temp, 'frames', '%06d.png')], { maxBuffer: 1024 * 1024, timeout: 300_000 });
    if ((await readdir(join(temp, 'frames'))).length !== frames.length) throw new Error('Decoded frame count differs from probe; review was not created.');
    if (await fileHash(input) !== sourceSha256) throw new Error('Input video changed during decoding; review was not created.');
    for (const frame of metadata.frames) frame.sha256 = await fileHash(join(temp, frame.file));
    await writeFile(join(temp, 'review.json'), JSON.stringify(metadata, null, 2));
    await writeFile(join(temp, 'index.html'), reviewHtml(metadata));
    await mkdir(output);
    try { await rename(temp, output); } catch (e) { await rmdir(output).catch(() => {}); throw e; }
  } finally { await rm(temp, { recursive: true, force: true }); }
  return { output, metadata };
}

function reviewHtml(metadata: object) {
  const data = JSON.stringify(metadata).replace(/</g, '\\u003c');
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Sprute animation review</title>
<style>body{font:16px system-ui;background:#171b20;color:#eee;max-width:1000px;margin:24px auto;padding:0 20px}h1{font-size:24px}button,select,textarea{font:inherit;padding:8px;background:#2b333b;color:white;border:1px solid #697888;border-radius:6px}button{cursor:pointer}#controls{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}canvas{display:block;max-width:100%;max-height:65vh;margin:auto;image-rendering:pixelated;background:repeating-conic-gradient(#eee 0% 25%,#bbb 0% 50%) 0/20px 20px}input{width:100%}textarea{box-sizing:border-box;width:100%;height:75px}#error{color:#ffb5ad}small{color:#b6c3cf}</style>
<h1>Review your animation</h1><p id="source"></p><small>Inspect the whole clip, including the last frame and loop join. Look for changed facing, extra objects, sliding feet and changing clothes. This page does not certify quality.</small>
<div id="controls"><button id="first">First</button><button id="prev">← Frame</button><button id="play">Play</button><button id="next">Frame →</button><button id="last">Last</button><select id="cell" aria-label="View"><option value="-1">Whole frame</option></select><select id="speed" aria-label="Playback speed"><option value="1">1× speed</option><option value="0.5">½ speed</option><option value="0.25">¼ speed</option></select></div>
<div id="loop-controls"><button id="mark-start">Set loop start here</button> <button id="mark-end">Set loop end here</button> <button id="jump-start">Loop start</button> <button id="jump-end">Loop end</button> <button id="reset-loop">Use whole clip</button></div><p id="loop-range" aria-live="polite"></p><p id="range-error" role="alert"></p>
<p id="position" aria-live="polite"></p><input id="seek" aria-label="Frame" type="range" min="0" step="1"><canvas id="canvas"></canvas><p id="error"></p>
<details id="foot-review"><summary>Mark foot positions (optional)</summary>
<p>Use the character's own left and right. If you cannot identify a foot or see its joint, record it as unclear or not visible. These marks do not measure ground contact.</p>
<label>Point <select id="landmark"><option value="leftAnkle">Left ankle</option><option value="rightAnkle">Right ankle</option><option value="leftToe">Left toe tip</option><option value="rightToe">Right toe tip</option></select></label>
<label>Certainty <select id="certainty"><option value="uncertain">Uncertain</option><option value="clear">Clear</option></select></label>
<p>Select a point, then click it on the paused image. For a grid, choose one cell first.</p>
<button id="hidden-point">Not visible</button> <button id="clear-point">Clear this mark</button><p id="point-status" aria-live="polite"></p></details>
<p><label for="note">Notes for this frame</label></p><textarea id="note" placeholder="For example: an extra object appears beside the left foot."></textarea><p><button id="save">Download review notes</button> <small>Notes stay in this page until downloaded. Arrow keys step; Home/End jump to the first/last frame.</small></p>
<script>const data=${data};
const $=id=>document.getElementById(id), canvas=$('canvas'), ctx=canvas.getContext('2d');let frame=0,playing=false,timer,request=0,loopStart=0,loopEnd=data.frameCount-1;const notes={},landmarks={};let displayedFrame=-1,displayedCell=-1;
$('source').textContent=data.source+' · '+data.frameCount+' frames · '+data.width+' × '+data.height;
$('seek').max=data.frameCount-1;
for(let i=0;i<data.columns*data.rows;i++){if(data.columns*data.rows===1)break;const o=document.createElement('option');o.value=i;o.textContent='Cell '+(i+1);$('cell').append(o)}
function stop(){playing=false;clearTimeout(timer);$('play').textContent='Play'}
async function show(index){clearTimeout(timer);frame=Math.max(0,Math.min(data.frameCount-1,index));const current=frame,token=++request;displayedFrame=-1;canvas.style.visibility='hidden';$('note').disabled=true;const f=data.frames[current];$('seek').value=current;$('note').value=notes[current]||'';$('position').textContent='Frame '+current+' / '+(data.frameCount-1)+' · '+f.time.toFixed(3)+' s';
const im=new Image();im.src=f.file;try{await im.decode();if(token!==request)return;const cell=Number($('cell').value),w=cell<0?data.width:data.width/data.columns,h=cell<0?data.height:data.height/data.rows;canvas.width=w;canvas.height=h;ctx.drawImage(im,cell<0?0:(cell%data.columns)*w,cell<0?0:Math.floor(cell/data.columns)*h,w,h,0,0,w,h);displayedFrame=current;displayedCell=cell;drawMarks();canvas.style.visibility='visible';$('note').disabled=false;$('error').textContent='';if(playing)timer=setTimeout(()=>show(current>=loopEnd?loopStart:current+1),f.duration*1000/Number($('speed').value));}catch(e){if(token!==request)return;stop();$('error').textContent='Could not load frame '+current+'. Keep the frames folder beside this page.'}}
function pointCell(){return data.columns*data.rows===1?0:Number($('cell').value)}
function pointKey(){return frame+':'+pointCell()+':'+$('landmark').value}
function pointStatus(){const p=landmarks[pointKey()];$('point-status').textContent=p?(p.visibility==='not-visible'?'Not visible':p.certainty+' · x '+p.x.toFixed(1)+', y '+p.y.toFixed(1)+' (original image pixels)'):'No mark for this point in this frame'}
function drawMarks(){const cell=pointCell(),ox=cell<0?0:cell%data.columns*(data.width/data.columns),oy=cell<0?0:Math.floor(cell/data.columns)*(data.height/data.rows);for(const p of Object.values(landmarks)){if(p.frame!==frame||p.cell!==cell||p.visibility!=='visible')continue;ctx.save();ctx.strokeStyle=p.certainty==='clear'?'#00ffff':'#ffbb33';ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.x-ox,p.y-oy,4,0,Math.PI*2);ctx.stroke();ctx.restore()}pointStatus()}
function recordPoint(visibility,x=null,y=null){const cell=pointCell();if(cell<0){$('point-status').textContent='Choose a single grid cell first.';return}stop();landmarks[pointKey()]={frame,sourceFile:data.frames[frame].file,time:data.frames[frame].time,cell,landmark:$('landmark').value,visibility,certainty:visibility==='visible'?$('certainty').value:null,x,y};show(frame)}
canvas.onclick=e=>{if(!$('foot-review').open||displayedFrame!==frame||playing)return;const cell=pointCell();if(cell!==displayedCell&&!(cell===0&&displayedCell===-1))return;const r=canvas.getBoundingClientRect();if(!r.width||!r.height)return;const px=(e.clientX-r.left)*canvas.width/r.width,py=(e.clientY-r.top)*canvas.height/r.height;if(px<0||py<0||px>=canvas.width||py>=canvas.height)return;const ox=cell<0?0:cell%data.columns*(data.width/data.columns),oy=cell<0?0:Math.floor(cell/data.columns)*(data.height/data.rows);recordPoint('visible',px+ox,py+oy)};
$('hidden-point').onclick=()=>recordPoint('not-visible');$('clear-point').onclick=()=>{stop();delete landmarks[pointKey()];show(frame)};$('landmark').onchange=pointStatus;$('certainty').onchange=pointStatus;$('foot-review').ontoggle=()=>{if($('foot-review').open)stop()};
function step(i){stop();show(i)}
function selectedRange(){return {startFrame:loopStart,endFrameInclusive:loopEnd,frameCount:loopEnd-loopStart+1,durationSeconds:data.frames.slice(loopStart,loopEnd+1).reduce((sum,f)=>sum+f.duration,0),frames:data.frames.slice(loopStart,loopEnd+1)}}
function rangeChanged(){const r=selectedRange();$('loop-range').textContent='Repeat frames '+loopStart+'–'+loopEnd+' · '+r.frameCount+' frames · '+r.durationSeconds.toFixed(3)+' s. Full clip remains available through First, Last and the slider.';$('range-error').textContent=''}
$('mark-start').onclick=()=>{stop();if(frame>=loopEnd){$('range-error').textContent='Choose a start before the loop end (at least two frames).';return}loopStart=frame;rangeChanged()};
$('mark-end').onclick=()=>{stop();if(frame<=loopStart){$('range-error').textContent='Choose an end after the loop start (at least two frames).';return}loopEnd=frame;rangeChanged()};
$('jump-start').onclick=()=>step(loopStart);$('jump-end').onclick=()=>step(loopEnd);$('reset-loop').onclick=()=>{stop();loopStart=0;loopEnd=data.frameCount-1;rangeChanged()};rangeChanged();
$('first').onclick=()=>step(0);$('last').onclick=()=>step(data.frameCount-1);$('prev').onclick=()=>step(frame-1);$('next').onclick=()=>step(frame+1);$('seek').oninput=e=>step(Number(e.target.value));$('cell').onchange=()=>show(frame);$('speed').onchange=()=>show(frame);$('play').onclick=()=>{if(playing)stop();else{playing=true;$('play').textContent='Pause';show(frame<loopStart||frame>loopEnd?loopStart:frame)}};
$('note').onfocus=stop;$('note').oninput=e=>{notes[frame]=e.target.value};
document.onkeydown=e=>{if(['TEXTAREA','INPUT','SELECT'].includes(e.target.tagName))return;if(e.key==='ArrowLeft'){e.preventDefault();step(frame-1)}if(e.key==='ArrowRight'){e.preventDefault();step(frame+1)}if(e.key==='Home'){e.preventDefault();step(0)}if(e.key==='End'){e.preventDefault();step(data.frameCount-1)}};
$('save').onclick=()=>{const blob=new Blob([JSON.stringify({source:data.source,sourceSha256:data.sourceSha256,frameCount:data.frameCount,status:'unreviewed',selectedRange:selectedRange(),notes,landmarkCoordinates:'Original decoded image pixels; cell is zero-based, anatomical identity is reviewer-supplied',landmarks:Object.values(landmarks)},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='review-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};show(0);
</script></html>`;
}

export async function runReviewAnimation(args: string[]) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: { output: { type: 'string', short: 'o' }, grid: { type: 'string', default: '1x1' } } });
  if (positionals.length !== 1 || !values.output) throw new Error('Usage: sprute review-animation video.mp4 -o new-folder [--grid 4x2]');
  const { output, metadata } = await reviewAnimation(positionals[0], values.output, values.grid);
  console.log(`Saved all ${metadata.frameCount} frames. Open ${join(output, 'index.html')} to review. No model key required.`);
}
