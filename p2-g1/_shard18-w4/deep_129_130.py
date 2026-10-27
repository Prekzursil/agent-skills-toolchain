import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
for uid, keys in [('TST-0129', ['residual_unknowns','success_withheld_while_condition11_red','condition11_live_check_exit_code','refutation_outcome','fresh_probe_rerun']),
                  ('TST-0130', ['residual_unknowns','condition11_live_red','answer','state_policy_applied','refute_stage'])]:
    p = REPO / 'command-center' / 'receipts' / (uid + '.json')
    doc = json.load(open(p, encoding='utf-8'))
    print('='*25, uid)
    for k in keys:
        if k in doc:
            print('--', k, ':', json.dumps(doc[k], ensure_ascii=False)[:800])
