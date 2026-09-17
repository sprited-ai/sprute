"""Local ComfyUI SCAIL2 graph and resumable execution (no hosted provider)."""
from pathlib import Path
import json
import mimetypes
import time
import urllib.parse
import urllib.request
import uuid
from common import digest, download, file_record, json_request, now, pin, read, write


def build_graph(reference, driver, *, size=768, frames=81, seed=42,
                recipe='lightx2v', prompt='8 directional character sprite animation',
                negative='', reference_mask=None, driver_mask=None):
    if bool(reference_mask) != bool(driver_mask):
        raise ValueError('Supply both identity masks, or neither')
    g=read(Path(__file__).with_name('scail2.template.json'))
    g['6']['inputs']['image']=reference
    g['8']['class_type']='VHS_LoadVideo'
    g['8']['inputs'].update(video=driver,custom_width=size,custom_height=size,frame_load_cap=frames)
    g['9']['inputs']['text']=prompt;g['10']['inputs']['text']=negative
    g['11']['inputs'].update(width=size,height=size,length=frames)
    g['12']['inputs']['seed']=seed
    g['15']['inputs']['filename_prefix']='sprute-script/scail2/result'
    if recipe=='baseline':
        del g['16']
        g['2']['inputs'].update(model=['1',0],shift=3.0)
        g['12']['inputs'].update(steps=20,cfg=3.0)
    if reference_mask:
        g['17']={'class_type':'LoadImage','inputs':{'image':reference_mask}}
        g['18']={'class_type':'VHS_LoadVideo','inputs':dict(g['8']['inputs'],video=driver_mask)}
        g['11']['inputs'].update(reference_image_mask=['17',0],pose_video_mask=['18',0])
    return g


def validate_server(server, graph):
    schema=json_request(server+'/object_info')
    for node in graph.values():
        kind=node['class_type']
        if kind not in schema:raise RuntimeError(f'Missing ComfyUI node: {kind}')
        # Verify required model weights before uploading/submitting.
        required=schema[kind]['input']['required']
        for key in ('unet_name','clip_name','vae_name','lora_name'):
            if key in node['inputs'] and node['inputs'][key] not in required[key][0]:
                raise RuntimeError(f'Missing model: {node["inputs"][key]}')


def upload_asset(server, path):
    path=Path(path);name=digest(path)+path.suffix.lower();boundary='sprute-'+uuid.uuid4().hex
    mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request(server+'/upload/image',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(req,timeout=180) as res:info=json.load(res)
    # Read back to verify the upload, including an existing same-named file.
    query=urllib.parse.urlencode({'filename':info['name'],'subfolder':info.get('subfolder',''),'type':'input'})
    import hashlib
    with urllib.request.urlopen(server+'/view?'+query,timeout=180) as res:
        h=hashlib.sha256()
        for chunk in iter(lambda:res.read(1024*1024),b''):h.update(chunk)
    if h.hexdigest()!=digest(path):raise RuntimeError('Uploaded asset hash mismatch')
    return '/'.join(filter(None,[info.get('subfolder','').strip('/'),info['name']]))


def execute(server, graph, folder, timeout=3600):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    pin(folder/'workflow.json',graph)
    target=folder/'animation.mp4';done=folder/'output.json';receipt=folder/'job.json'
    if done.exists():
        if not target.exists() or digest(target)!=read(done)['sha256']:raise RuntimeError('Cached SCAIL2 video changed')
        return target
    if receipt.exists():job=read(receipt)
    else:
        marker=folder/'submission-started.json'
        if marker.exists():raise RuntimeError('Uncertain ComfyUI submission; inspect queue/history. No automatic resubmission.')
        write(marker,{'at':now()})
        job=json_request(server+'/prompt',{'prompt':graph});write(receipt,job)
    if job.get('node_errors') or 'prompt_id' not in job:raise RuntimeError(f'ComfyUI rejected graph; inspect {receipt}')
    print('SCAIL2 job:',job['prompt_id'],flush=True)
    deadline=time.monotonic()+timeout
    while True:
        result=json_request(server+'/history/'+job['prompt_id']).get(job['prompt_id'])
        if result:break
        if time.monotonic()>deadline:raise RuntimeError('Wait timed out. Rerun the same command to resume; no resubmission.')
        time.sleep(3)
    write(folder/'history.json',result)
    if result['status']['status_str']!='success':raise RuntimeError(f'SCAIL2 failed; inspect {folder / "history.json"}')
    outputs=result['outputs'].get('15',{})
    videos=[f for group in ('gifs','videos','images') for f in outputs.get(group,[]) if f.get('filename','').endswith('.mp4')]
    if len(videos)!=1:raise RuntimeError('Expected exactly one SCAIL2 MP4 output from node 15')
    info=videos[0];query=urllib.parse.urlencode({k:info[k] for k in ('filename','subfolder','type') if k in info})
    download(server+'/view?'+query,target);write(done,file_record(target))
    return target
