from PIL import Image
from pathlib import Path
import json
r=Path(__file__).resolve().parent;order=['S','SE','E','NE','N','NW','W','SW'];layout={'NW':(0,0),'N':(1,0),'NE':(2,0),'W':(0,1),'E':(2,1),'SW':(0,2),'S':(1,2),'SE':(2,2)};edge=[0,213,427,640];frames=[];ds=[];clipped=0
for n in range(23,42):
 grid=Image.new('RGBA',(640,640))
 for d,(x,y) in layout.items():grid.alpha_composite(Image.open(r/'frames'/d/f'{n:04}.png').convert('RGBA'),(edge[x],edge[y]))
 full=grid.resize((1536,1536),Image.Resampling.LANCZOS);row=Image.new('RGBA',(2560,512))
 for i,d in enumerate(order):
  x,y=layout[d];cell=full.crop((x*512,y*512,(x+1)*512,(y+1)*512));box=cell.getchannel('A').point(lambda a:255 if a>16 else 0).getbbox()
  if box and (box[0]<96 or box[2]>416):clipped+=1
  row.alpha_composite(cell.crop((96,0,416,512)),(320*i,0))
 frames.append(row);ds.append(round((n+1)*1000/24)-round(n*1000/24))
p=r/'elise-run-still-sized-loop-q65.webp';frames[0].save(p,save_all=True,append_images=frames[1:],duration=ds,loop=0,lossless=False,quality=65,method=4)
check=Image.open(p);assert check.size==(2560,512) and check.n_frames==19
print('potential clipped cells:',clipped,'bytes:',p.stat().st_size)
(r/'still-sizing.json').write_text(json.dumps({'output':[2560,512],'cell':[320,512],'order':order,'extra_gap':0,'mapping':'restore 640 grid to 1536 (2x reference grid); crop each 512 square at x=96 width=320 to undo reference padding; fixed transform for every frame','source_frames':[23,41],'alpha_bounds_crossing_crop':clipped},indent=2))
