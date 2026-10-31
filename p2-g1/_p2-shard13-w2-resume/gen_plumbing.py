import importlib.util, json, io, sys
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO = Path(r'C:/Users/Prekzursil/p2-g1')
spec = importlib.util.spec_from_file_location('m1d', REPO/'command-center'/'p2-wave'/'_measure_one_delivered.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
HASH_RULE = 'sha256 over CRLF-normalized bytes (matches _measure_one_delivered.digest_file)'

ids = ['IMP-0261','IMP-0264','IMP-0269','IMP-0270','IMP-0271','IMP-0272','IMP-0273','IMP-0274','IMP-0275','IMP-0279','IMP-0303']
NOTE_0261 = ('shard13-w2 resume 2026-10-25: receipt + reviewer closure pre-existing and still verify live. '
 'Repair: probe2 inner `python -m jsonschema` CLI exited nonzero under the measure harness env because '
 'PYTHONPATH puts REPO first and repo platform/ shadows stdlib platform inside the attrs import chain; '
 'fixed by adding -I to the inner CLI subprocess (isolated from PYTHONPATH, upstream jsonschema CLI unchanged). '
 'Probe re-verified live rc=0; manifest hashes refreshed. Receipt bytes untouched.')
NOTE_10 = ('shard13-w2 resume 2026-10-25: prior builder receipt + probes + raws verified complete and live '
 '(probe1+probe2 re-run exit 0, raw pass=true); SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST written to close '
 'delivery plumbing. Receipt and reviewer closure kept unmodified.')

for uid in ids:
    pdir = REPO/'command-center'/'p2-wave'/'probes'/uid
    out_rel = 'command-center/receipts/%s.json' % uid
    receipt = json.loads((REPO/out_rel).read_text(encoding='utf-8'))
    cmds = m.probe_commands(uid, None, pdir)
    assert len(cmds) >= 1, (uid, 'no probes')
    rows = []
    def add(path_rel, role):
        p = REPO/path_rel
        if p.is_file() and p.stat().st_size > 0:
            sha, nb = m.digest_file(p)
            rows.append({'unit_id': uid, 'path': path_rel, 'bytes': nb, 'sha256': sha,
                         'present': True, 'role': role})
        else:
            rows.append({'unit_id': uid, 'path': path_rel, 'bytes': 0, 'sha256': '',
                         'present': False, 'role': role})
    add(out_rel, 'primary')
    for i, a in enumerate(receipt.get('artifacts') or []):
        ap = a.get('path') or a.get('artifact') or ''
        if not ap: continue
        add(ap, a.get('role') or ('implementation' if i == 0 else 'supporting'))
    for c in cmds:
        add(c.split()[-1], 'named-probe')
    man = {'unit_id': uid, 'generated': NOW, 'hash_rule': HASH_RULE, 'artifacts': rows}
    (pdir/'UNIT-ARTIFACT-MANIFEST.json').write_text(json.dumps(man, indent=1, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    ret = {
        'id': uid, 'unit_id': uid, 'status': 'DELIVERED', 'state': 'SUCCESS',
        'sentinel': receipt.get('sentinel') or ('SUCCESS:%s' % uid),
        'output_path': out_rel,
        'output_schema': 'command-center/schema/receipt.schema.json',
        'registered': True,
        'manifest_path': 'command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid,
        'reviewer': receipt.get('reviewer'),
        'cloud_ok': False, 'ts': NOW,
        'named_probes': [{'id': 'probe%d' % j, 'command': c} for j, c in enumerate(cmds, 1)],
        'resume_note': NOTE_0261 if uid == 'IMP-0261' else NOTE_10,
        'artifacts': [{'path': r['path'], 'bytes': r['bytes'], 'sha256': r['sha256'],
                       'exists': r['present'], 'role': r['role']} for r in rows],
    }
    (pdir/'SUBAGENT-RETURN.json').write_text(json.dumps(ret, indent=1, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    print('%s: %d manifest rows, %d probes, primary sha=%s' % (uid, len(rows), len(cmds), rows[0]['sha256'][:12]))
print('PLUMBING DONE')
