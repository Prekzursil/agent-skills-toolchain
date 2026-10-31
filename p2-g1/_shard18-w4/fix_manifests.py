import hashlib, json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")

def digest(p):
    raw = Path(p).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)

def detect_indent(text):
    for line in text.splitlines()[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(' '))
    return 1

NOTE = ("2026-10-26 shard18-w4: re-hashed after restoring the receipt to the reviewer-certified "
        "refute-stage BLOCKED disposition and correcting probe1's state predicate; CRLF-normalized "
        "sha256 per _measure_one_delivered.py")

for uid in ('TST-0129', 'TST-0130'):
    mp = REPO / 'command-center' / 'p2-wave' / 'probes' / uid / 'UNIT-ARTIFACT-MANIFEST.json'
    man = json.loads(mp.read_text(encoding='utf-8'))
    changed = 0
    for row in man.get('artifacts', []):
        rel = str(row.get('path', '')).replace(chr(92), '/')
        if row.get('unit_id') == uid and rel in (
            'command-center/receipts/%s.json' % uid,
            'command-center/p2-wave/probes/%s/probe1_delivery_predicate.py' % uid,
        ):
            f = REPO / rel
            if f.is_file():
                sha, nb = digest(f)
                row['sha256'] = sha
                row['bytes'] = nb
                row['eol'] = 'LF'
                row['present'] = True
                row['exists'] = True
                changed += 1
    man['shard18_w4_rehash'] = NOTE
    out = json.dumps(man, indent=detect_indent(mp.read_text(encoding='utf-8')), ensure_ascii=False) + '\n'
    mp.write_bytes(out.replace('\r\n', '\n').encode('utf-8'))
    print('REHASH-MANIFEST', uid, 'rows_updated=%d' % changed)
