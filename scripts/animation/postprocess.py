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
    p.add_argument('--loop',choices=['full','auto'],default='auto')
    p.add_argument('--preset',choices=['idle','walk','run'],help='Loop period hints; inferred from parent animation job when available')
    p.add_argument('--period-min',type=int)
    p.add_argument('--period-max',type=int)
    p.add_argument('--start',type=int,help='Explicit inclusive frame, with --end')
    p.add_argument('--end',type=int,help='Explicit exclusive frame, with --start')
    p.add_argument('--register',action='store_true',help='Fixed per-direction median height/foot registration to standing sheet; visually review')
    args=p.parse_args()
    if not 0<=args.quality<=100:p.error('quality must be 0..100')
    if (args.start is None)!=(args.end is None):p.error('--start and --end are required together')
    if args.start is not None:args.loop='full'
    if args.loop=='auto':
        preset=args.preset
        parent_job=args.out.parent/'inputs.json'
        if preset is None and parent_job.exists():preset=read(parent_job).get('state')
        if preset:
            hints=read(Path(__file__).with_name('presets.json'))[preset]
            if args.period_min is None:args.period_min=hints['period_min']
            if args.period_max is None:args.period_max=hints['period_max']
    if args.loop=='auto' and (args.period_min is None or args.period_max is None):p.error('Specify --preset, --period-min/--period-max, or --loop full')
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
        label=f'{start}-{end}-q{args.quality}-optimized'+('-registered' if args.register else '')
        out=args.out/'exports'/label;out.mkdir(parents=True,exist_ok=True)
        strips,registration=horizontal(selected,args.standing,args.register)
        save_webp(out/'horizontal.webp',strips,dur,args.quality)
        save_webp(out/'grid.webp',selected,dur,args.quality)
        # A web-sized companion avoids inflating 480p cells to the standing sheet resolution.
        cw,ch=registration['cell'];h=min(ch,round(meta['width']/3));w=max(1,round(cw*h/ch))
        compact=[]
        for strip in strips:
            row=Image.new('RGBA',(w*8,h))
            for i in range(8):
                row.alpha_composite(strip.crop((i*cw,0,(i+1)*cw,ch)).resize((w,h),Image.Resampling.LANCZOS),(i*w,0))
            compact.append(row)
        save_webp(out/'horizontal-compact.webp',compact,dur,args.quality)
        edge=bounds(meta['width']);files=['horizontal.webp','horizontal-compact.webp','grid.webp']
        for d,(x,y) in GRID.items():
            frames=[g.crop((edge[x],edge[y],edge[x+1],edge[y+1])) for g in selected]
            save_webp(out/f'{d}.webp',frames,dur,args.quality);files.append(f'{d}.webp')
        report={'source':meta,'selection':selection,'layout':registration,'quality':args.quality,
                'duration_ms':sum(dur),'compact_cell':[w,h], 'encoding':{'method':6,'minimize_size':True,'alpha_quality':80},'outputs':[file_record(out/f) for f in files]}
        write(out/'export.json',report)
        with zipfile.ZipFile(out/'animations.zip','w',zipfile.ZIP_DEFLATED) as z:
            for f in files+['export.json']:z.write(out/f,f)
        write(args.out/'latest.json',{'directory':str(out.resolve()),'horizontal':str((out/'horizontal.webp').resolve()),'compact':str((out/'horizontal-compact.webp').resolve()),'selection':selection})
        print(f'Loop: frames {start}..{end-1} ({end-start}/{len(grid)} frames), {sum(dur)} ms',flush=True)
        for name in ['horizontal.webp','horizontal-compact.webp']:
            print(f'{out/name} ({(out/name).stat().st_size:,} bytes)',flush=True)


if __name__=='__main__':main()
