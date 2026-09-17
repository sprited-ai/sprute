#!/usr/bin/env python3
"""Install your local idle/walk/run driver MP4s. Replaces the bundled presets and their hash manifest."""
import argparse
from pathlib import Path
import shutil
import subprocess
import json
from common import file_record, write

p=argparse.ArgumentParser(description=__doc__)
for state in ['idle','walk','run']:p.add_argument('--'+state,type=Path,required=True)
a=p.parse_args();root=Path(__file__).parent/'drivers';root.mkdir(exist_ok=True);result={}
for state in ['idle','walk','run']:
    source=getattr(a,state).resolve(strict=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,avg_frame_rate','-of','json',str(source)]))['streams'][0]
    if probe['width']!=probe['height']:raise ValueError('Driver must be a square 3x3 grid')
    target=root/(state+'.mp4')
    if source!=target.resolve():shutil.copy2(source,target)
    result[state]={'file':target.name,'sha256':file_record(target)['sha256'],'source':str(source),'video':probe}
write(root/'manifest.json',result)
print(root/'manifest.json')
