import importlib.util, json, sys, io, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO = Path(r'C:/Users/Prekzursil/p2-g1')
spec = importlib.util.spec_from_file_location('m1d', REPO/'command-center'/'p2-wave'/'_measure_one_delivered.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ids = ['IMP-0264','IMP-0269','IMP-0270','IMP-0271','IMP-0272','IMP-0273','IMP-0274','IMP-0275','IMP-0279','IMP-0303']
results = {}
for uid in ids:
    pdir = REPO/'command-center'/'p2-wave'/'probes'/uid
    cmds = m.probe_commands(uid, None, pdir)
    rows = []
    for c in cmds:
        code, tail = m.run_cmd(c)
        rows.append({'cmd': c, 'rc': code, 'tail': tail[-800:]})
        print(f'{uid} rc={code} :: {c}')
        if code != 0:
            print('   TAIL:', tail[-400:].replace(chr(10), ' | ')[:400])
    results[uid] = rows
out = REPO/'_p2-shard13-w2-resume'/'probe-run1.json'
json.dump(results, open(out, 'w', encoding='utf-8'), indent=1)
print('WROTE', out)
print('SUMMARY:', {u: [r["rc"] for r in v] for u, v in results.items()})
