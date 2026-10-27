import json
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:\Users\Prekzursil' + BS + 'p2-g1')
def dump(uid, keys, limit=2200):
    doc = json.loads((REPO/'command-center'/'receipts'/(uid+'.json')).read_text(encoding='utf-8'))
    print('#'*16, uid)
    for k in keys:
        if k in doc:
            print(f'--{k}--')
            print(json.dumps(doc[k], indent=1)[:limit])
dump('IMP-0423', ['tests','implementation','evidence'], 1500)
dump('IMP-0430', ['answer','report','evidence','notes'])
dump('IMP-0435', ['ci_runs','evidence','notes','implementation'])
dump('IMP-0442', ['named_probes','dry_run','time_series','implementation','serial_lock','routing','peaks'], 1200)
dump('IMP-0448', ['report','evidence','tests'], 1600)
dump('IMP-0450', ['named_probes','census','pane_capture','answer'])
dump('IMP-0460', ['declared_vs_observed','both_states','named_probes','answer'], 1400)
dump('IMP-0466', ['corpus','resolution_table','per_argument_shape','evidence'], 1400)
dump('IMP-0467', ['library','host','evidence','tests','answer','question_or_target','notes'], 1800)
dump('IMP-0468', ['report','evidence','tests','answer'], 1600)
