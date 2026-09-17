from pathlib import Path
from PIL import Image
import subprocess,json,sys
r=Path(__file__).resolve().parent;layout=[('NW',0,0),('N',1,0),('NE',2,0),('W',0,1),('E',2,1),('SW',0,2),('S',1,2),('SE',2,2)]
for state in (sys.argv[1:] or ['idle','walk']):
 p=r/state;m=json.loads((p/'metadata.json').read_text());count=m['frames'];fs=[]
 for n in range(count):
  out=Image.new('RGB',(768,768),'#808080')
  for d,x,y in layout:
   im=Image.open(p/'cells'/d/f'{n:06}.png').convert('RGBA');out.paste(im,(x*256,y*256),im)
  fs.append(out)
 proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','768x768','-r','24','-i','-','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',str(p/'driving.mp4')],stdin=subprocess.PIPE)
 for n in range(120):proc.stdin.write(fs[n%count].tobytes())
 proc.stdin.close();assert proc.wait()==0
 ds=[round((n+1)*1000/24)-round(n*1000/24) for n in range(count)]
 fs[0].save(p/'driving.webp',save_all=True,append_images=fs[1:],duration=ds,loop=0,quality=80,method=4)
 fs[0].save(p/'first-frame.png')
 print(state,count,'frames loop; MP4 5 seconds',flush=True)
