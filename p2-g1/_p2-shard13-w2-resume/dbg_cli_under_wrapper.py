import json, subprocess, sys, tempfile
from pathlib import Path
SCHEMA = Path('tools/council/schema/councilspec.schema.json').resolve()
spec13 = {'kind':'councilspec','stopping':{'rule':'quorum'},'charter':{'title':'13-section'},'participants':{'n':3},'roles':{'chair':'alice'},'engagement':{'mode':'round-robin'},'budgets':{'max_turns':6},'evidence':{'required':True},'voting':{'mode':'majority'},'outcomes':{'artifact':'decision'},'integrity':{'dupes':'audit'},'artifacts':{'transcript':True},'execution':{'substrate':'local'},'meta':{'id':'CS-13'}}
td = tempfile.mkdtemp(); p13 = Path(td)/'g.json'; p13.write_text(json.dumps(spec13), encoding='utf-8')
r = subprocess.run([sys.executable, '-m', 'jsonschema', '--instance', str(p13), str(SCHEMA)], capture_output=True, text=True)
print('INNER rc=', r.returncode)
print('INNER stdout:', (r.stdout or '')[:300])
print('INNER stderr:', (r.stderr or '')[:800])
import p2_jsonschema_hook
print('hook file:', getattr(p2_jsonschema_hook, '__file__', '?'), 'version:', getattr(p2_jsonschema_hook, 'HOOK_VERSION', '?'))
