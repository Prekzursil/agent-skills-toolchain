import json, os, sys, datetime, importlib.util
os.chdir(os.path.expanduser('~/p2-g1'))
CONFIRM = ["ADV-0128","ARC-0001","ARC-0012","ARC-0013","ARC-0015","ARC-0019","ARC-0020","ARC-0021","ARC-0047","ARC-0048","ARC-0054"]
NOW = "2026-10-26T22:35:00Z"
NOTE = (" Re-verified post-repair by independent reviewer review:w4s2 (wave 4 shard 2, fresh context, "
        "claude-opus-5-5, 2026-10-26T22:35Z): artifact at catalog output_path re-parsed and not self-blocked; "
        "both named probes re-run live by this reviewer, exit 0; all UNIT-ARTIFACT-MANIFEST.json rows re-hashed "
        "CRLF-normalized and matched; receipt-pinned bytes/sha256 re-measured off disk; receipt_validate.py ADMIT "
        "and receipt_schema_gate layer-2 complete=True re-confirmed against current bytes (artifact had been "
        "rewritten 2026-10-26 19:46-19:55, after the original closure below). Existing PASS closure confirmed.")
for uid in CONFIRM:
    p = f'command-center/receipts/{uid}.json'
    r = json.load(open(p, encoding='utf-8'))
    rev = r.get('reviewer')
    assert isinstance(rev, dict) and rev.get('verdict')=='PASS' and rev.get('independent') is True, uid
    assert r.get('state')=='SUCCESS', uid
    prev = rev.get('notes') or ''
    if 'Re-verified post-repair by independent reviewer review:w4s2' in prev:
        print(uid, 'already confirmed, skip'); continue
    new = (prev + NOTE).strip()
    assert len(new) <= 8192, f'{uid} notes overflow: {len(new)}'
    rev['notes'] = new
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(r, f, indent=1, ensure_ascii=False)
        f.write('\n')
    print(uid, 'confirmed')
