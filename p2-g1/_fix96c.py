import json, hashlib, subprocess, sys, os
from pathlib import Path
REPO = Path('.').resolve()
ART = REPO/'command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json'
env = os.environ.copy(); env['PYTHONDONTWRITEBYTECODE'] = '1'
r = subprocess.run([sys.executable, '-B', 'command-center/p2-wave/_measure_one_delivered.py', 'ADV-0096'],
                   capture_output=True, text=True, env=env)
tail = ((r.stdout or '') + (r.stderr or '')).strip()[-3000:]
assert r.returncode == 0 and 'SUCCESS:delivered ADV-0096' in tail, tail[-300:]
doc = json.loads(ART.read_text(encoding='utf-8'))
rows = doc['downstream_consumers']
mrow = next(x for x in rows if '_measure_one_delivered' in x['consumer'])
mrow['probe']['raw_output'] = tail
mrow['exit_code'] = 0
jrow = next(x for x in rows if x['consumer'].startswith('json.loads'))
code = ("import json;d=json.load(open(r'%s',encoding='utf-8'));"
        "print('consumer=json.loads; unit_id=%%s; state=%%s; evidence=%%d; targets=%%d' %% (d['unit_id'], d['state'], len(d['evidence']), len(d.get('targets') or [])))" % ART.as_posix())
r2 = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
assert r2.returncode == 0, r2.stderr
jrow['probe']['raw_output'] = (r2.stdout or '').strip()
ART.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
print('consumer rows recorded, bytes:', ART.stat().st_size)
