from PIL import Image
from pathlib import Path
import zipfile,json
r=Path(__file__).resolve().parent
layout=[('NW',0,0),('N',1,0),('NE',2,0),('W',0,1),('E',2,1),('SW',0,2),('S',1,2),('SE',2,2)];edges=[0,213,427,640]
ds=[round((i+1)*1000/24)-round(i*1000/24) for i in range(121)]
grid=[Image.new('RGBA',(640,640)) for _ in ds]
for d,x,y in layout:
 fs=[];paths=sorted((r/'frames'/d).glob('*.png'));assert len(paths)==121
 for i,p in enumerate(paths):
  im=Image.open(p).convert('RGBA');assert im.getchannel('A').getextrema()[0]==0
  grid[i].alpha_composite(im,(edges[x],edges[y]))
  cell=Image.new('RGBA',(214,214));cell.alpha_composite(im);fs.append(cell)
 fs[0].save(r/f'{d}.webp',save_all=True,append_images=fs[1:],duration=ds,loop=0,quality=90,method=4)
 print(d,flush=True)
grid[0].save(r/'elise-run-transparent.webp',save_all=True,append_images=grid[1:],duration=ds,loop=0,quality=90,method=4)
review=Image.new('RGB',(1280,640))
for i,(n,bg) in enumerate([(0,'white'),(60,'#202030')]):
 c=Image.new('RGBA',(640,640),bg);c.alpha_composite(grid[n]);review.paste(c,(i*640,0))
review.save(r/'review.png')
with zipfile.ZipFile(r/'elise-run-toonout.zip','w',zipfile.ZIP_DEFLATED) as z:
 for d,_,_ in layout:z.write(r/f'{d}.webp',f'{d}.webp')
 z.write(r/'elise-run-transparent.webp','elise-run-transparent.webp')
for p in r.glob('*.webp'):
 im=Image.open(p);total=0
 for n in range(im.n_frames):im.seek(n);im.load();total+=im.info['duration']
 assert total==sum(ds)
 print(p.name,im.n_frames,total)
