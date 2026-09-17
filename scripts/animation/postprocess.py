#!/usr/bin/env python3
"""Existing video -> cropped direction frames -> ToonOut -> loop / WebP exports.

No hosted image/video generation. Requires a running ComfyUI-RMBG installation.
"""
import argparse
from pathlib import Path
import zipfile
from PIL import Image
from common import file_record, lock, pin, read, write
from media import ORDER, GRID, bounds, choose_loop, decode_and_crop, grids, horizontal, save_webp
from providers import matte


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--standing',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--comfy',default='http://127.0.0.1:18188')
    p.add_argument('--quality',type=int,default=65)
    p.add_argument('--loop',choices=['full','auto'],default='full')
    p.add_argument('--period-min',type=int)
    p.add_argument('--period-max',type=int)
    p.add_argument('--start',type=int,help='Explicit inclusive frame, with --end')
    p.add_argument('--end',type=int,help='Explicit exclusive frame, with --start')
    p.add_argument('--register',action='store_true',help='Fixed per-direction median height/foot registration to standing sheet; visually review')
    args=p.parse_args()
    if not 0<=args.quality<=100:p.error('quality must be 0..100')
    if (args.start is None)!=(args.end is None):p.error('--start and --end are required together')
    if args.loop=='auto' and (args.period_min is None or args.period_max is None):p.error('auto loop requires --period-min/--period-max')
    if args.loop=='auto' and args.start is not None:p.error('Choose auto loop OR explicit frame range')
    with lock(args.out):
        pin(args.out/'inputs.json',{'video':file_record(args.video),'standing':file_record(args.standing),'comfy':args.comfy})
        # Deterministic decode/crops can be regenerated; matte input hashes protect cache reuse.
        sources,meta=decode_and_crop(args.video,args.out/'source')
        matted=matte(args.comfy,sources,args.out/'toonout')
        grid=grids(matted,meta['width'])
        selection={'start':0,'end':len(grid),'review_required':True}
        if args.loop=='auto':selection=choose_loop(grid,args.period_min,args.period_max)
        elif args.start is not None:selection={'start':args.start,'end':args.end,'review_required':True}
        start,end=selection['start'],selection['end']
        if not 0<=start<end<=len(grid):raise ValueError('Invalid frame selection')
        selected=grid[start:end];dur=meta['durations_ms'][start:end]
        label=f'{start}-{end}-q{args.quality}'+('-registered' if args.register else '')
        out=args.out/'exports'/label;out.mkdir(parents=True,exist_ok=True)
        strips,registration=horizontal(selected,args.standing,args.register)
        save_webp(out/'horizontal.webp',strips,dur,args.quality)
        save_webp(out/'grid.webp',selected,dur,args.quality)
        edge=bounds(meta['width']);files=['horizontal.webp','grid.webp']
        for d,(x,y) in GRID.items():
            frames=[g.crop((edge[x],edge[y],edge[x+1],edge[y+1])) for g in selected]
            save_webp(out/f'{d}.webp',frames,dur,args.quality);files.append(f'{d}.webp')
        report={'source':meta,'selection':selection,'layout':registration,'quality':args.quality,
                'duration_ms':sum(dur),'outputs':[file_record(out/f) for f in files]}
        write(out/'export.json',report)
        with zipfile.ZipFile(out/'animations.zip','w',zipfile.ZIP_DEFLATED) as z:
            for f in files+['export.json']:z.write(out/f,f)
        print(out,flush=True)


if __name__=='__main__':main()
