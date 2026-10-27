import json
ids = ['TST-0255','TST-0256','TST-0261','TST-0265','TST-0282','TST-0283','TST-0284','TST-0288','TST-0297','TST-0303']
for uid in ids:
    doc = json.load(open(f'command-center/receipts/{uid}.json', encoding='utf-8'))
    print('='*72)
    print(uid, '| answer:', str(doc.get('answer'))[:400])
    np = doc.get('named_probes') or []
    for n in np:
        if isinstance(n, dict):
            print('  NP:', n.get('id'), n.get('role'), '|', n.get('command'))
    for k in ('both_states','controls','cp1252_console'):
        if doc.get(k): print(f'  {k}:', json.dumps(doc[k])[:250])
    bs = doc.get('both_states_check') or doc.get('both-states')
    if bs: print('  bs:', json.dumps(bs)[:250])
