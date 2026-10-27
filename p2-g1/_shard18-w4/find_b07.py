import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
cat = json.load(open(REPO/'command-center'/'WORK-UNIT-CATALOG.json', encoding='utf-8'))
for u in cat['work_units']:
    if isinstance(u, dict) and u.get('id') in ('B06','B07','B06.1','B07.1'):
        print('='*15, u.get('id'))
        print(json.dumps({k: u.get(k) for k in ('id','title','question_or_target','output_path','dependencies','phase')}, indent=1, ensure_ascii=False)[:1200])
