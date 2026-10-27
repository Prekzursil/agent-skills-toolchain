import json
REPO = r'C:/Users/Prekzursil/p2-g1'
# ARC-0021 probe outputs (both-directions preservation)
sr = json.load(open(REPO + '/command-center/p2-wave/probes/ARC-0021/SUBAGENT-RETURN.json', encoding='utf-8'))
for np in sr.get('named_probes', []):
    print('== ARC-0021', np.get('id'), 'exit', np.get('exit_code'))
    print((np.get('raw_output') or '')[:1200])
    print()
# ARC-0048 classification discipline
d = json.load(open(REPO + '/command-center/phase3/A7/SECURITY.json', encoding='utf-8'))
eps = d.get('escalation_paths', [])
from collections import Counter
cls = Counter()
missing_mech = []
for e in eps:
    c = e.get('classification')
    cls[str(c)] += 1
    if c == 'STRUCTURALLY-IMPOSSIBLE' and not (e.get('mechanism') or e.get('forbidden_by') or e.get('mechanism_that_forbids')):
        missing_mech.append(e.get('id'))
print('ARC-0048 classifications:', dict(cls))
print('structurally-impossible rows missing mechanism:', missing_mech)
for e in eps[:3]:
    print(' sample path:', json.dumps(e)[:350])
