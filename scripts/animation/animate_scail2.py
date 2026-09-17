#!/usr/bin/env python3
"""Standing strip + preset -> local SCAIL2 -> the shared ToonOut/loop/WebP pipeline."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from common import digest, file_record, lock, pin, read, write
from media import compose_reference
from providers import check_comfy
from scail2 import build_graph, execute, upload_asset, validate_server


def normalize_video(source, target, frames, mask=False, cycle=None):
    """Repeat a known complete cycle; custom videos must already be long enough."""
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height','-of','json',str(source)]))['streams'][0]
    if probe['width']!=probe['height']:raise ValueError('Driver must be a square 3x3 grid')
    codec=['-c:v','ffv1','-pix_fmt','bgr0'] if mask else ['-c:v','libx264','-crf','16','-pix_fmt','yuv420p']
    filters='fps=24'
    if cycle:filters+=f',trim=end_frame={cycle},loop=loop=-1:size={cycle}:start=0,setpts=N/(24*TB)'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),
        '-an','-vf',filters,'-frames:v',str(frames),*codec,str(target)],check=True)
    count=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','json',str(target)]))['streams'][0]['nb_read_frames']
    if int(count)!=frames:raise ValueError('Driver is too short; provide enough frames at 24fps')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--standing',type=Path,required=True)
    p.add_argument('--preset',choices=['idle','walk','run'],required=True)
    p.add_argument('--driver',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--comfy',default='http://127.0.0.1:18188')
    p.add_argument('--recipe',choices=['lightx2v','baseline'],default='lightx2v')
    p.add_argument('--size',type=int,default=768,help='Square grid resolution, multiple of 48')
    p.add_argument('--frames',type=int,default=81,help='4n+1; 81 supports all preset loop-search windows')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--prompt',default='8 directional character sprite animation')
    p.add_argument('--negative',default='')
    p.add_argument('--reference-mask',type=Path,help='SCAIL identity-color grid PNG, not alpha/grayscale')
    p.add_argument('--driver-mask',type=Path,help='Identity-color video aligned with the driver')
    p.add_argument('--loop',choices=['auto','full'],default='auto')
    p.add_argument('--quality',type=int,default=65)
    p.add_argument('--register',action='store_true')
    p.add_argument('--prepare-only',action='store_true',help='Prepare local inputs/graph; no network or GPU execution')
    args=p.parse_args();args.comfy=args.comfy.rstrip('/')
    if args.size<48 or args.size%48:p.error('--size must be a positive multiple of 48')
    if not 5<=args.frames<=601 or args.frames%4!=1:p.error('--frames must be 4n+1, 5..601')
    if not 0<=args.seed<2**64 or not 0<=args.quality<=100:p.error('Invalid seed or quality')
    if bool(args.reference_mask)!=bool(args.driver_mask):p.error('Provide both identity masks, or neither')
    preset=read(Path(__file__).with_name('presets.json'))[args.preset]
    if args.loop=='auto' and args.frames<=preset['period_max']+6:p.error('Too few frames for preset loop search; increase --frames or use --loop full')
    cycle=None
    if args.driver is None:
        cycle=round(preset['source_period_frames']*24/preset['source_fps'])
        root=Path(__file__).parent/'drivers';entry=read(root/'manifest.json')[args.preset]
        args.driver=root/entry['file']
        if digest(args.driver)!=entry['sha256']:raise RuntimeError('Preset driver hash mismatch')
    settings={k:getattr(args,k) for k in ('recipe','size','frames','seed','prompt','negative')}
    with lock(args.out):
        inputs={'standing':file_record(args.standing),'driver':file_record(args.driver),'state':args.preset,
                'backend':'scail2','server':args.comfy,'settings':settings,'driver_cycle_frames_24fps':cycle,
                'masks':{k:file_record(getattr(args,k)) for k in ('reference_mask','driver_mask') if getattr(args,k)}}
        pin(args.out/'inputs.json',inputs)
        reference=args.out/'reference-grid.png'
        write(args.out/'layout.json',compose_reference(args.standing,reference))
        driver=args.out/'driver.mp4';normalize_video(args.driver,driver,args.frames,cycle=cycle)
        assets={'reference':reference,'driver':driver}
        if args.reference_mask:
            from PIL import Image
            with Image.open(args.reference_mask) as mask,Image.open(reference) as ref:
                if mask.size!=ref.size:p.error('Reference mask must match the composed reference-grid.png dimensions')
            mask_video=args.out/'driver-mask.mkv';normalize_video(args.driver_mask,mask_video,args.frames,True,cycle=cycle)
            assets.update(reference_mask=args.reference_mask,driver_mask=mask_video)
        graph=build_graph(**{k:str(v.resolve()) for k,v in assets.items()},**settings)
        write(args.out/'workflow-local.json',graph)
        if args.prepare_only:
            print(f'Prepared {args.out}. workflow-local.json is a plan, not a server-ready graph. No inference submitted.');return
        prediction=args.out/'prediction'
        if (prediction/'workflow.json').exists():
            graph=read(prediction/'workflow.json')
        else:
            validate_server(args.comfy,graph);check_comfy(args.comfy)
            names={k:upload_asset(args.comfy,v) for k,v in assets.items()}
            graph=build_graph(**names,**settings)
        video=execute(args.comfy,graph,prediction)
        command=[sys.executable,str(Path(__file__).with_name('postprocess.py')),
            '--video',str(video),'--standing',str(args.standing),'--out',str(args.out/'postprocess'),
            '--comfy',args.comfy,'--preset',args.preset,'--loop',args.loop,'--quality',str(args.quality)]
        if args.register:command+=['--register']
        subprocess.run(command,check=True)


if __name__=='__main__':main()
