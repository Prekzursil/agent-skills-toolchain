import hashlib, json
from pathlib import Path

BS = chr(92)
mine = ['ARC-0055','ARC-0056','ARC-0076','AUD-0003','AUD-0005','AUD-0008',
        'AUD-0010','AUD-0026','AUD-0032','AUD-0033','AUD-0042','AUD-0043']
cat = json.loads(Path('command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}
all_ok = True
for uid in mine:
    unit = byid[uid]
    out_rel = str(unit['output_path']).replace(BS, '/')
    out = Path(out_rel)
    raw = out.read_bytes().replace(b'\r\n', b'\n')
    live_sha = hashlib.sha256(raw).hexdigest()
    doc = json.loads(out.read_text(encoding='utf-8'))
    art_state = doc.get('state', '?')
    man = json.loads(Path(f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json').read_text(encoding='utf-8'))
    rows = [a for a in man.get('artifacts', []) if a.get('unit_id') == uid]
    match = [a for a in rows if str(a.get('path','')).replace(BS,'/') == out_rel
             and a.get('sha256') == live_sha and a.get('present') is True]
    ret = json.loads(Path(f'command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json').read_text(encoding='utf-8'))
    np = ret.get('named_probes') or []
    ok = bool(match) and art_state not in ('BLOCKED','FAILED','SEVERED','TIMEOUT')
    all_ok &= ok
    print(f"{uid}: sha_match={bool(match)} manifest_rows={len(rows)} art_state={art_state} named_probes={len(np)} -> {'OK' if ok else 'FAIL'}")
print('ALL-OK' if all_ok else 'SOME-FAILED')
