import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ['TST-0092','TST-0094','TST-0100','TST-0109','TST-0113','TST-0116','TST-0124','TST-0129','TST-0130','TST-0136','TST-0137','TST-0138']
for uid in UNITS:
    p = REPO / 'command-center' / 'receipts' / (uid + '.json')
    doc = json.load(open(p, encoding='utf-8'))
    flags = {}
    for k in ['success_withheld_while_condition11_red','condition11_live_red','state_policy_applied','answer','condition11_live_check_exit_code']:
        if k in doc:
            flags[k] = doc[k]
    rs = doc.get('refute_stage') or {}
    if rs:
        flags['refute_stage.disposition'] = rs.get('measured_disposition')
        flags['refute_stage.condition11'] = rs.get('condition11_live_check')
    ans = doc.get('answer')
    if isinstance(ans, str) and ('BLOCKED' in ans or 'NOT-REFUTED' in ans):
        flags['answer_has_blocked'] = True
    print(uid, 'state=', doc.get('state'), json.dumps(flags, ensure_ascii=False)[:500])
