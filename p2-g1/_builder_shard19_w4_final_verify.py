import importlib.util, json, subprocess, sys, hashlib
from pathlib import Path
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
ok = True
for uid in mine:
    rp = Path('command-center/receipts/%s.json' % uid)
    # 1. admission validator
    p = subprocess.run([sys.executable, 'command-center/receipt_validate.py', str(rp)], capture_output=True, text=True)
    line = (p.stdout or '').strip().splitlines()[0] if (p.stdout or '').strip() else 'NO-OUTPUT'
    # 2. reviewer closure survived
    doc = json.loads(rp.read_text(encoding='utf-8'))
    rv = doc.get('reviewer') or {}
    closure = rv.get('verdict') == 'PASS' and rv.get('independent') is True
    # 3. manifest row matches live (LF-normalized)
    man = json.loads(Path('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid).read_text(encoding='utf-8'))
    live = hashlib.sha256(rp.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    rows = [a for a in (man.get('artifacts') or []) if isinstance(a, dict) and a.get('unit_id') == uid
            and str(a.get('path','')).replace(chr(92), '/') == 'command-center/receipts/%s.json' % uid
            and a.get('sha256') == live and a.get('present') is True]
    # 4. required core fields present for SUCCESS
    missing = [k for k in ['schema_version','unit_id','state','sentinel','spec_anchor','min_bytes_threshold','artifacts','evidence','timestamps','retry','tests','negative_controls','reviewer','manifest_registration','downstream_consumers','residual_unknowns'] if k not in doc]
    good = line.startswith('ACCEPT') and closure and bool(rows) and not missing and doc.get('state') == 'SUCCESS'
    ok = ok and good
    print('%s: %s | reviewer=%s/%s manifest-match=%s core-missing=%s state=%s' % (uid, line[:60], rv.get('verdict'), rv.get('independent'), bool(rows), missing or 'none', doc.get('state')))
print('ALL-GREEN' if ok else 'NOT-GREEN')
