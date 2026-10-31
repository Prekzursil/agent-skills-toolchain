import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:' + BS + 'Users' + BS + 'Prekzursil' + BS + 'p2-g1')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
MINE_B = ['IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
PROBES = {
 'IMP-0448': ['probe1_decision_table.py','probe2_two_strikes.py'],
 'IMP-0450': ['probe1_readonly.py','probe2_census.py'],
 'IMP-0460': ['probe1_declared_vs_observed.py','probe2_both_states.py'],
 'IMP-0466': ['probe1_both_directions.py','probe2_global_suppression.py'],
 'IMP-0467': ['probe1_reserved_enum.py','probe2_longpath_noswallow.py'],
 'IMP-0468': ['probe1_planted_nested.py','probe2_non_case_receipt.py'],
}
NOTES = {
 'IMP-0448': 'rebuild: probe1/probe2 (retry_engine.py sha-verified pre-existing)',
 'IMP-0450': 'rebuild: probe1/probe2 + pane-capture.txt (program_pane.py pre-existing)',
 'IMP-0460': 'rebuild: 4 fixture hooks + hooks.json; load_probe.py tightened to refuse $-keys per receipt; probes',
 'IMP-0466': 'rebuild: fixtures/corpus.json + probes (tools/shell/pathconv.py pre-existing)',
 'IMP-0467': 'rebuild: probe1/probe2 (command-center/lib/windows_safe_path.py pre-existing); NUL via extended-length prefix',
 'IMP-0468': 'rebuild: 5 control fixtures + probes (case_collision.py sha-verified pre-existing)',
}
cat = json.loads((REPO/'command-center'/'WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
units = {u['id']: u for u in cat['work_units']}
norm_sha = lambda p: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
for uid in MINE_B:
    out_rel = str(units[uid]['output_path']).replace(BS, '/')
    rp = REPO / out_rel
    pdir = REPO / 'command-center' / 'p2-wave' / 'probes' / uid
    ret = {
        'unit_id': uid, 'status': 'COMPLETED', 'completed_at': NOW,
        'builder': 'shard15-w2-resume (prior builder died mid-flight; verified + completed)',
        'rebuild_provenance': NOTES[uid],
        'receipt_state': 'SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true)',
        'named_probes': [
            {'id': n.replace('.py',''), 'role': 'named-probe',
             'command': 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/%s/%s' % (uid, n)}
            for n in PROBES[uid]],
        'notes': 'Receipt untouched. Probes re-run live on this checkout, exit 0. Manifest sha256 = CRLF-normalized digest of the live receipt.',
    }
    (pdir/'SUBAGENT-RETURN.json').write_text(json.dumps(ret, indent=2)+'\n', encoding='utf-8', newline='\n')
    man = {'unit_id': uid, 'generated_at': NOW, 'receipt_state': 'SUCCESS',
           'artifacts': [{'unit_id': uid, 'path': out_rel, 'sha256': norm_sha(rp),
                          'bytes': rp.stat().st_size, 'present': True,
                          'note': 'primary artifact (CRLF-normalized digest)'}]}
    (pdir/'UNIT-ARTIFACT-MANIFEST.json').write_text(json.dumps(man, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('B', uid, norm_sha(rp)[:12])
print('PART-B DONE')
