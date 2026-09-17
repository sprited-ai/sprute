#!/usr/bin/env python3
"""Reference/prompt -> NBP template -> crop -> ToonOut -> eight-view sheet.

Standalone lab script, not the sprute CLI. Five actual views + three mirrored.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageOps
from common import file_record, lock, pin, write
from media import ORDER, compose_reference
from providers import matte, replicate, check_comfy

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', type=Path)
    p.add_argument('--prompt', default='')
    p.add_argument('--template', type=Path, default=ROOT/'templates/sprute-8dir-v1.png')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--comfy', default='http://127.0.0.1:18188')
    p.add_argument('--allow-paid', action='store_true')
    args = p.parse_args()
    check_comfy(args.comfy)
    with lock(args.out):
        pin(args.out/'inputs.json', {'reference': file_record(args.image) if args.image else None,
            'template': file_record(args.template), 'prompt': args.prompt, 'comfy': args.comfy})
        template = Image.open(args.template).convert('RGB')
        if template.size != (1584,672):
            raise ValueError('This helper supports only the bundled 8dir-v1/v2 geometry (1584x672)')
        if args.image:
            ref = Image.open(args.image).convert('RGBA')
            ref = ImageOps.contain(ref,(160,256),Image.Resampling.LANCZOS)
            template.paste(ref,(32+(160-ref.width)//2,352+(256-ref.height)//2),ref)
        composed = args.out/'template.png'; template.save(composed)
        prompt = ('Complete the lower Inference Results row of this template. Keep the entire template layout and dimensions. '
                  'Draw a full-body pixel-art RPG character, standing neutrally, consistently in South, South East, East, '
                  'North East and North views, matching the example row positions and proportions. Keep backgrounds plain gray. '
                  + ('Use the lower-left reference image for identity, colors, hair and outfit. ' if args.image else 'Invent a new original character. ')
                  + args.prompt)
        output = replicate(args.out/'generation','google/nano-banana-pro',
            {'prompt':prompt,'output_format':'png','resolution':'2K'},[composed],[], 'sheet.png',args.allow_paid)
        generated = Image.open(output).convert('RGBA')
        sx,sy = generated.width/1584,generated.height/672
        if abs(sx-sy)>0.02:
            raise ValueError('Generated template aspect ratio changed; inspect instead of guessing crop coordinates')
        sources = {}; dims = {}
        for i,d in enumerate(['S','SE','E','NE','N']):
            rect=(round((192+i*160)*sx),round(352*sy),round((352+i*160)*sx),round(608*sy))
            cell=generated.crop(rect);dims[d]=cell.size
            dest=args.out/'cropped'/d;dest.mkdir(parents=True,exist_ok=True)
            path=dest/'0000.png';cell.crop((4,4,cell.width-4,cell.height-4)).save(path);sources[d]=[path]
        matted=matte(args.comfy,sources,args.out/'toonout')
        cells={}
        for d,paths in matted.items():
            cell=Image.new('RGBA',dims[d]);cell.alpha_composite(Image.open(paths[0]).convert('RGBA'),(4,4));cells[d]=cell
        for dst,src in {'SW':'SE','W':'E','NW':'NE'}.items():cells[dst]=ImageOps.mirror(cells[src])
        cw=max(im.width for im in cells.values());ch=max(im.height for im in cells.values())
        sheet=Image.new('RGBA',(cw*8,ch))
        for i,d in enumerate(ORDER):
            dest=args.out/'directions';dest.mkdir(exist_ok=True)
            cell=Image.new('RGBA',(cw,ch));cell.alpha_composite(cells[d]);cell.save(dest/f'{d}.png');sheet.alpha_composite(cell,(cw*i,0))
        sheet.save(args.out/'standing.png')
        layout=compose_reference(args.out/'standing.png',args.out/'reference-grid.png')
        write(args.out/'character.json',{'standing':file_record(args.out/'standing.png'),'layout':layout,
            'mirrored':['SW','W','NW'],'matting':'BiRefNet_toonout after cropping','review_required':True})
        print(args.out/'standing.png')


if __name__=='__main__':main()
