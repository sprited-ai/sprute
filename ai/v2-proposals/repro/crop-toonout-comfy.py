import json,urllib.request,urllib.parse,time,sys,concurrent.futures
from pathlib import Path
R=Path(__file__).resolve().parent;BASE='http://127.0.0.1:18188'
dirs=[('NW',0,0),('N',1,0),('NE',2,0),('W',0,1),('E',2,1),('SW',0,2),('S',1,2),('SE',2,2)]
edges=[0,213,427,640]
sample='--sample' in sys.argv
name='sample.png' if sample else json.loads((R/'upload.json').read_text())['name']
w={'1':{'class_type':'LoadImage','inputs':{'image':name}}}
for i,(d,x,y) in enumerate(dirs):
 c,m,s=map(str,[10+i,20+i,30+i])
 w[c]={'class_type':'ImageCrop','inputs':{'image':['1',0],'width':edges[x+1]-edges[x],'height':edges[y+1]-edges[y],'x':edges[x],'y':edges[y]}}
 w[m]={'class_type':'BiRefNetRMBG','inputs':{'image':[c,0],'model':'BiRefNet_toonout','process_resolution':1024,'mask_blur':0,'mask_offset':0,'invert_output':False,'refine_foreground':True,'background':'Alpha','background_color':'#808080'}}
 w[s]={'class_type':'SaveImage','inputs':{'images':[m,0],'filename_prefix':f'elise-run-toonout/{"sample" if sample else "full"}/{d}'}}
tag='sample' if sample else 'full';(R/f'{tag}-workflow.json').write_text(json.dumps(w,indent=2))
req=urllib.request.Request(BASE+'/prompt',data=json.dumps({'prompt':w}).encode(),headers={'Content-Type':'application/json'})
try:j=json.load(urllib.request.urlopen(req))
except urllib.error.HTTPError as e: print(e.read().decode());raise
(R/f'{tag}-job.json').write_text(json.dumps(j));print(j,flush=True)
while True:
 h=json.load(urllib.request.urlopen(BASE+'/history/'+j['prompt_id']))
 if j['prompt_id'] in h:break
 time.sleep(3)
h=h[j['prompt_id']];(R/f'{tag}-history.json').write_text(json.dumps(h,indent=2))
if h['status']['status_str']!='success':print(h['status']);sys.exit(1)
tasks=[]
for i,(d,_,_) in enumerate(dirs):
 imgs=h['outputs'][str(30+i)]['images'];out=R/('samples' if sample else 'frames')/d;out.mkdir(parents=True,exist_ok=True)
 print(d,len(imgs),flush=True)
 for n,im in enumerate(imgs):tasks.append((BASE+'/view?'+urllib.parse.urlencode(im),out/f'{n:04}.png'))
def get(t):u,p=t;p.write_bytes(urllib.request.urlopen(u).read())
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(get,tasks))
print('collected',len(tasks),flush=True)
