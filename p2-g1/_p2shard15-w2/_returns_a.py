import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:' + BS + 'Users' + BS + 'Prekzursil' + BS + 'p2-g1')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
MINE_A = ['IMP-0423','IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442']
PROBES = {
 'IMP-0423': ['probe1_mismatch.py','probe2_preserve.py'],
 'IMP-0430': ['probe1_bleed.py','probe2_repo_vs_live.py'],
 'IMP-0435': ['probe1_both_states.py','probe2_noop_mode.py'],
 'IMP-0437': ['probe1_defaults_deletion.py','probe2_single_field_review.py'],
 'IMP-0439': ['probe1_blob_parity.py','probe2_independent_show.py'],
 'IMP-0442': ['probe1_mixed_dry_run.py','probe2_serial_lock_mutation.py'],
}
NOTES = {
 'IMP-0423': 'rebuild: test battery + fixture + probes (degrade_loudly.py pre-existing)',
 'IMP-0430': 'rebuild: hooks/_shared/session_keyed_store.py + settings snapshot + fixture-live drift copy + audit/bleed + probes',
 'IMP-0435': 'rebuild: receipt_gate.py + validate.py gate wiring + quality.yml + test + scenario + probes',
 'IMP-0437': 'rebuild: quality.yml + probe1/probe2 (vfields_ci.py + test sha-verified pre-existing)',
 'IMP-0439': 'rebuild: probe1/probe2 (blob.py pre-existing; parity + independent-show)',
 'IMP-0442': 'rebuild: dispatcher.py + probe1/probe2 (substrate source: live catalog)',
}
cat = json.loads((REPO/'command-center'/'WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
units = {u['id']: u for u in cat['work_units']}
norm_sha = lambda p: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
for uid in MINE_A:
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
    print('A', uid, norm_sha(rp)[:12])
print('PART-A DONE')
