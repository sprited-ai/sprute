"""Emit Linux/Python3.12 wheel URLs with mandatory hashes from the observed inventory."""
from pathlib import Path
import json,re
from urllib.parse import urlsplit
root=Path(__file__).resolve().parent
packages=json.loads((root/'python-artifacts.json').read_text())['packages']
lines=['# Linux x86_64 / CPython3.12 only; exact wheels observed and compared in083.', '# Install with pip --require-hashes --no-index -r this-file.', '# Other platforms require separately validated wheels.']
seen=set()
for p in sorted(packages,key=lambda p:p['name'].lower()):
 name=p['name'];url=p['url'];h=p['hashes']['sha256'];u=urlsplit(url)
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',name) or not re.fullmatch(r'[a-f0-9]{64}',h):raise ValueError('Invalid package/hash')
 if u.scheme!='https' or u.username or u.password or not u.path.endswith('.whl') or any(c.isspace() for c in url):raise ValueError('Invalid wheel URL')
 key=re.sub(r'[-_.]+','-',name).lower()
 if key in seen:raise ValueError('Duplicate package')
 seen.add(key)
 lines.append(f'{name} @ {url} --hash=sha256:{h}')
(root/'requirements-linux-cu128-hashed.txt').write_text('\n'.join(lines)+'\n')
print(f'Wrote{len(seen)} exact wheel entries')
