"""Resumable Replicate prediction and local ComfyUI ToonOut adapters."""
import base64
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from PIL import Image
from common import digest, download, file_record, json_request, now, pin, read, token, write

API = 'https://api.replicate.com/v1'


def replicate(folder, model, settings, images, videos, output, allow_paid=False, timeout=1800):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    plan = {'model': model, 'input': settings,
            'images': [file_record(p) for p in images], 'videos': [file_record(p) for p in videos]}
    pin(folder / 'request.json', plan)
    receipt = folder / 'prediction.json'
    marker = folder / 'submission-started.json'
    target = folder / output
    complete = folder / 'output.json'
    if complete.exists():
        if not target.exists() or digest(target) != read(complete)['sha256']:
            raise RuntimeError(f'Saved provider output changed: {target}')
        return target
    headers = {'Authorization': 'Bearer ' + token()}
    if receipt.exists():
        pred = read(receipt)
    else:
        if marker.exists():
            raise RuntimeError(f'Uncertain submission in {folder}; inspect provider dashboard. Do not delete marker and retry blindly.')
        if not allow_paid:
            raise RuntimeError(f'Prepared {folder / "request.json"}. New paid requests require --allow-paid.')
        inp = dict(settings)
        def uri(path, mime):
            return 'data:' + mime + ';base64,' + base64.b64encode(Path(path).read_bytes()).decode()
        if images:
            inp['image_input' if model == 'google/nano-banana-pro' else 'reference_images'] = [uri(p, 'image/png') for p in images]
        if videos:
            inp['reference_videos'] = [uri(p, 'video/mp4') for p in videos]
        # Never auto-resubmit POST, including transport timeout / lost response.
        write(marker, {'at': now(), 'model': model})
        pred = json_request(API + '/models/' + model + '/predictions', {'input': inp}, headers)
        # Whitelist: provider input may echo huge data URIs and output URLs may be temporary.
        pred = {k: pred[k] for k in ('id', 'status', 'output', 'error', 'metrics', 'created_at', 'started_at', 'completed_at', 'version') if k in pred}
        write(receipt, pred)
        print('Submitted:', pred['id'], flush=True)
    deadline = time.monotonic() + timeout
    while pred['status'] not in ('succeeded', 'failed', 'canceled'):
        if time.monotonic() > deadline:
            raise RuntimeError('Polling timed out. Rerun the same command to resume this prediction.')
        time.sleep(5)
        pred = json_request(API + '/predictions/' + urllib.parse.quote(pred['id'], safe=''), headers=headers)
        pred = {k: pred[k] for k in ('id', 'status', 'output', 'error', 'metrics', 'created_at', 'started_at', 'completed_at', 'version') if k in pred}
        write(receipt, pred)
    if pred['status'] != 'succeeded':
        raise RuntimeError(f"Prediction {pred['status']}: {pred.get('error')}. No automatic retry.")
    url = pred['output'][0] if isinstance(pred['output'], list) else pred['output']
    download(url, target)
    write(complete, file_record(target))
    return target


def upload(server, path):
    boundary = 'sprute-' + uuid.uuid4().hex
    name = digest(path) + '.webp'
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            'Content-Type: image/webp\r\n\r\n').encode() + Path(path).read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(server + '/upload/image', data=body,
                                 headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(req, timeout=180) as res:
        info = json.load(res)
    return (info.get('subfolder', '').strip('/') + '/' + info['name']).lstrip('/')


def encoded_spans(path, source_count):
    spans = []
    with Image.open(path) as im:
        for n in range(im.n_frames):
            im.seek(n); im.load()
            duration = source_count * 100 if im.n_frames == 1 else im.info['duration']
            if duration <= 0 or duration % 100:
                raise RuntimeError('Unexpected intermediate WebP timing')
            spans.append(duration // 100)
    if sum(spans) != source_count:
        raise RuntimeError('Intermediate WebP lost frame timing')
    return spans


def check_comfy(server):
    schema = json_request(server.rstrip('/') + '/object_info/BiRefNetRMBG')
    node = schema.get('BiRefNetRMBG')
    if not node or 'BiRefNet_toonout' not in node['input']['required']['model'][0]:
        raise RuntimeError('ComfyUI-RMBG with BiRefNet_toonout is required before generating.')


def matte(server, sources, folder, timeout=1800):
    """Sources are ALREADY cropped per-direction PNG sequences; never matte a whole grid."""
    server = server.rstrip('/')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    settings = {'model': 'BiRefNet_toonout', 'process_resolution': 1024, 'mask_blur': 0,
                'mask_offset': 0, 'invert_output': False, 'refine_foreground': True,
                'background': 'Alpha', 'background_color': '#808080'}
    plan = {'server': server, 'settings': settings,
            'sources': {d: [file_record(p) for p in paths] for d, paths in sources.items()}}
    pin(folder / 'inputs.json', plan)
    done = folder / 'complete.json'
    if done.exists():
        saved = read(done)
        for group in saved.values():
            for item in group:
                if not Path(item['path']).exists() or digest(item['path']) != item['sha256']:
                    raise RuntimeError('Matte frames changed; use a fresh output folder.')
        return {d: [Path(item['path']) for item in group] for d, group in saved.items()}
    jobfile = folder / 'job.json'
    if not jobfile.exists():
        if (folder / 'submission-started.json').exists():
            raise RuntimeError('Uncertain ComfyUI submission; inspect queue/history before resubmitting.')
        schema = json_request(server + '/object_info/BiRefNetRMBG')
        if 'BiRefNetRMBG' not in schema:
            raise RuntimeError('ComfyUI-RMBG BiRefNetRMBG node is required.')
        graph = {}
        for i, (direction, paths) in enumerate(sources.items()):
            frames = [Image.open(p).convert('RGBA') for p in paths]
            # Preserve every frame even when the encoder merges identical idle frames:
            # store run lengths and expand the returned mattes below.
            encoded = folder / f'{direction}-input.webp'
            frames[0].save(encoded, save_all=True, append_images=frames[1:], lossless=True,
                           duration=[100] * len(frames), loop=0, method=1)
            spans = encoded_spans(encoded, len(paths))
            write(folder / f'{direction}-spans.json', spans)
            name = upload(server, encoded)
            load, node, save = map(str, (i * 3 + 1, i * 3 + 2, i * 3 + 3))
            graph[load] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
            graph[node] = {'class_type': 'BiRefNetRMBG', 'inputs': {'image': [load, 0], **settings}}
            graph[save] = {'class_type': 'SaveImage', 'inputs': {'images': [node, 0], 'filename_prefix': f'sprute-script/{folder.name}/{direction}'}}
        write(folder / 'workflow.json', graph)
        write(folder / 'submission-started.json', {'at': now()})
        job = json_request(server + '/prompt', {'prompt': graph})
        write(jobfile, job)
    job = read(jobfile)
    if job.get('node_errors') or 'prompt_id' not in job:
        raise RuntimeError(f'ComfyUI rejected graph: {job}')
    deadline = time.monotonic() + timeout
    while True:
        result = json_request(server + '/history/' + job['prompt_id']).get(job['prompt_id'])
        if result:
            break
        if time.monotonic() > deadline:
            raise RuntimeError('ComfyUI wait timed out; rerun to resume. If history was cleared, inspect server manually.')
        time.sleep(3)
    write(folder / 'history.json', result)
    if result['status']['status_str'] != 'success':
        raise RuntimeError(f'ComfyUI failed; inspect {folder / "history.json"}')
    outputs = {}
    for i, direction in enumerate(sources):
        images = result['outputs'][str(i * 3 + 3)]['images']
        spans = read(folder / f'{direction}-spans.json')
        if len(images) != len(spans):
            raise RuntimeError('ComfyUI returned unexpected frame count')
        dest = folder / 'frames' / direction
        dest.mkdir(parents=True, exist_ok=True)
        paths = []
        for idx, (info, span) in enumerate(zip(images, spans)):
            raw = folder / f'{direction}-download.png'
            download(server + '/view?' + urllib.parse.urlencode({k: info[k] for k in ('filename', 'subfolder', 'type') if k in info}), raw)
            with Image.open(raw) as im:
                im = im.convert('RGBA')
                with Image.open(sources[direction][0]) as original:
                    if im.size != original.size:
                        raise RuntimeError('Matting changed frame dimensions')
                if im.getchannel('A').getbbox() is None:
                    raise RuntimeError(f'Empty matte: {direction} {idx}')
                for _ in range(span):
                    path = dest / f'{len(paths):04}.png'; im.save(path); paths.append(path)
            raw.unlink()
        outputs[direction] = paths
        print('Matted', direction, len(paths), flush=True)
    write(done, {d: [file_record(p) for p in paths] for d, paths in outputs.items()})
    return outputs
