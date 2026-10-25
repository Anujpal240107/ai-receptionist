from pathlib import Path
import json
import importlib.metadata as md
from packaging.requirements import Requirement
p=Path('migrations/001_receptionist.sql')
s=p.read_text(encoding='utf-8-sig')
s=s.replace(" if action='bootstrap' then", " perform pg_advisory_xact_lock(hashtextextended(u::text,21));\n if action='bootstrap' then")
p.write_text(s,encoding='utf-8')
roots=['streamlit','groq','sentry-sdk']
seen={}
def visit(name):
    d=md.distribution(name)
    key=d.metadata['Name'].lower().replace('_','-')
    if key in seen:return
    seen[key]=d.version
    for entry in d.requires or []:
        req=Requirement(entry)
        if req.marker is None or req.marker.evaluate({'extra':''}): visit(req.name)
for root in roots:visit(root)
Path('requirements.txt').write_text('# Resolved runtime graph, Python 3.12; refresh with an audit and regression checks.\n'+''.join(f'{k}=={v}\n' for k,v in sorted(seen.items())),encoding='utf-8')
Path('requirements-dev.txt').write_text('-r requirements.txt\npip-audit==2.10.1\n',encoding='utf-8')
print('Pinned',len(seen),'runtime distributions')
