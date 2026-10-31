import json, os
ids = ['TST-0284','TST-0288','TST-0297','TST-0303']
for uid in ids:
    doc = json.load(open(f'command-center/receipts/{uid}.json', encoding='utf-8'))
    print('='*70)
    print(uid, 'state=', doc.get('state'))
    tests = doc.get('tests') or []
    for t in tests:
        if isinstance(t, dict):
            print('  TEST', t.get('id'), t.get('result'))
            print('    cmd:', t.get('command'))
        else:
            print('  TEST-STR:', str(t)[:120])
    ext = doc.get('extensions') or {}
    np = ext.get('named_probes') or doc.get('named_probes') or []
    for n in np:
        if isinstance(n, dict) and n.get('command'):
            print('  NAMED-PROBE cmd:', n.get('command'))
        elif isinstance(n, dict):
            print('  NAMED-PROBE raw:', n.get('raw_path'), str(n.get('raw_sha256',''))[:12])
    for a in (doc.get('artifacts') or []):
        p = str(a.get('path','')).replace('\\','/')
        if f'probes/{uid}' in p:
            print('  PROBE-ARTIFACT:', p, 'exists=', os.path.exists(p))
