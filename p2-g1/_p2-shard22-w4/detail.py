import json, sys
uid = sys.argv[1]
doc = json.load(open(f'command-center/receipts/{uid}.json', encoding='utf-8'))
print('UID:', uid, '| profile:', doc.get('profile'), '| kind:', (doc.get('report') or {}).get('kind'))
print('SENTINEL:', doc.get('sentinel'))
print('ANSWER:', str((doc.get('report') or {}).get('answer'))[:900])
print()
for ev in (doc.get('evidence') or []):
    print('EVIDENCE:', ev.get('verdict'), '|', str(ev.get('claim'))[:250])
    for pr in (ev.get('probes') or []):
        print('   probe:', json.dumps(pr)[:220])
print()
for t in (doc.get('tests') or []):
    if isinstance(t, dict):
        print('TEST:', t.get('id'), t.get('result'), '| assertions:', t.get('assertions'))
        print('   cmd:', t.get('command'))
        print('   tail:', str(t.get('output_tail'))[:300])
print()
for nc in (doc.get('negative_controls') or []):
    print('NC:', nc.get('id'), '|', str(nc.get('description'))[:150])
    print('   bad:', str(nc.get('bad_state_output'))[:200])
    print('   good:', str(nc.get('good_state_output'))[:200])
rep = doc.get('report') or {}
for k, v in rep.items():
    if k in ('answer','observations','plain_field_set','tui_field_set','only_plain','only_tui'): continue
    s = json.dumps(v)
    print(f'REPORT.{k}: {s[:280]}')
for k, v in (doc.get('extensions') or {}).items():
    if k in ('named_probes','tests_required','question_or_target','evidence_requirement','title'): continue
    s = json.dumps(v)
    print(f'EXT.{k}: {s[:280]}')
