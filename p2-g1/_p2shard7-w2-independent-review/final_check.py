import hashlib, json
from pathlib import Path
REPO = Path.cwd()
rep = json.load(open('_p2shard7-w2-independent-review/review-phaseA.json', encoding='utf-8'))
by = {u['unit_id']: u for u in rep['units']}
ok = True
for uid in ('BLD-0044', 'BLD-0045'):
    u = by[uid]
    op = u['catalog']['output_path']
    raw = (REPO / op).read_bytes()
    live = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
    same = live == u['manifest_primary_sha_live']
    state = json.loads(raw.decode('utf-8'))['state']
    print(uid, 'receipt-unchanged-since-phaseA:', same, '| state:', state)
    ok = ok and same
for uid, op in [('BLD-0043', 'command-center/receipts/BLD-0043.json'),
                ('CNF-0070', 'command-center/confirmation/CNF-0070-archival-corroboration.json'),
                ('CC-0003', 'command-center/receipts/CC-0003.json'),
                ('CC-0019', 'command-center/receipts/CC-0019.json')]:
    d = json.loads((REPO / op).read_text(encoding='utf-8'))
    m = json.loads((REPO / ('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid)).read_text(encoding='utf-8'))
    rows = [r for r in m['artifacts'] if str(r['path']).replace(chr(92), '/') == op]
    live = hashlib.sha256((REPO / op).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    match = bool(rows) and rows[0]['sha256'] == live
    rev = d.get('reviewer', {})
    print(uid, 'reviewer:', rev.get('reviewer_id'), '| manifest-row-matches-live:', match,
          '| all-rows-match-disk:', all(
              (REPO / str(r['path'])).is_file() and
              hashlib.sha256((REPO / str(r['path'])).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == r['sha256']
              for r in m['artifacts']))
    ok = ok and match
print('FINAL-CHECK:', 'PASS' if ok else 'FAIL')
