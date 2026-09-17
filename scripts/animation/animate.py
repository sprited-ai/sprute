#!/usr/bin/env python3
"""Standing strip + an explicit driver MP4 -> one resumable Seedance prediction."""
import argparse
import subprocess
import sys
from pathlib import Path
from common import file_record, lock, pin, write, read, digest
from media import compose_reference
from providers import replicate, check_comfy


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--standing',type=Path,required=True)
    p.add_argument('--driver',type=Path,help='Override preset driver MP4')
    p.add_argument('--preset',choices=['idle','walk','run'],required=True)
    p.add_argument('--comfy',default='http://127.0.0.1:18188')
    p.add_argument('--quality',type=int,default=65)
    p.add_argument('--loop',choices=['auto','full'],default='auto')
    p.add_argument('--register',action='store_true')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--allow-paid',action='store_true')
    args=p.parse_args()
    if not 0 <= args.quality <= 100:p.error('quality must be 0..100')
    presets=read(Path(__file__).with_name('presets.json'))
    preset=presets[args.preset]
    if args.driver is None:
        root=Path(__file__).parent/'drivers'
        if not (root/'manifest.json').exists():p.error('Run configure_drivers.py once to install your local preset videos')
        entry=read(root/'manifest.json')[args.preset]
        args.driver=root/entry['file']
        if digest(args.driver)!=entry['sha256']:raise RuntimeError('Preset driver hash mismatch')
    motions={'idle':'Stand still with feet planted and arms relaxed. Very subtle breathing and hair movement. No stepping or turning.',
             'walk':'Walk in place with relaxed alternating steps and natural arm swing.',
             'run':'Run in place with coordinated alternating strides and arm swing.'}
    check_comfy(args.comfy)
    with lock(args.out):
        pin(args.out/'inputs.json',{'standing':file_record(args.standing),'driver':file_record(args.driver),'state':args.preset,'seed':args.seed})
        layout=compose_reference(args.standing,args.out/'reference-grid.png');write(args.out/'layout.json',layout)
        prompt=('8 directional character sprite animation. Use [Image1] for appearance, pixel-art style and proportions. '
                'Use [Video1] for motion, timing, eight viewing directions and 3x3 layout. '+motions[args.preset]+
                ' Keep the center empty, camera fixed, each character in its own cell, original direction and size. '
                'Continue the same cycle for the full duration. Plain gray background.')
        result=replicate(args.out/'prediction','bytedance/seedance-2.0',
            {'prompt':prompt,'resolution':'480p','aspect_ratio':'1:1','duration':5,'seed':args.seed,'generate_audio':False},
            [args.out/'reference-grid.png'],[args.driver],'animation.mp4',args.allow_paid)
        print(result)
        command=[sys.executable,str(Path(__file__).with_name('postprocess.py')),
            '--video',str(result),'--standing',str(args.standing),'--out',str(args.out/'postprocess'),
            '--comfy',args.comfy,'--quality',str(args.quality),'--loop',args.loop]
        if args.loop=='auto':command+=['--period-min',str(preset['period_min']),'--period-max',str(preset['period_max'])]
        if args.register:command+=['--register']
        subprocess.run(command,check=True)


if __name__=='__main__':main()
