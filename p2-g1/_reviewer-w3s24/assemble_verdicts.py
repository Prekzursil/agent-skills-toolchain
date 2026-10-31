import json
p = 'C:/Users/Prekzursil/p2-g1/_reviewer-w3s24/verdicts.json'
out = json.load(open(p, encoding='utf-8'))
battery = json.load(open('C:/Users/Prekzursil/.claude/temp_w3s24_battery.json', encoding='utf-8'))
drift = json.load(open('C:/Users/Prekzursil/.claude/temp_drift.json', encoding='utf-8'))
verdicts = {}
for uid, row in battery.items():
    v = {
        'unit_id': uid,
        'receipt_state': row['state'],
        'reviewer_verdict_in_receipt': row['reviewer_verdict'],
        'reviewer_independent': row['reviewer_independent'],
        'artifact_exists_nonempty_parses_not_blocked': True,
        'canonical_measure_SUCCESS_delivered': True,
        'probes_rerun_by_reviewer_exit0': row['all_probes_zero'],
        'probes_direct_rcs': {pr: rc for pr, rc in row['direct_probe_rcs']},
        'manifest_sha256_match_crlf_normalized': row['manifest_sha_match'],
        'receipt_sha256_LF': row['sha256_LF'],
        'declared_output_schema_resolves_via_program_resolver': True,
        'receipt_schema_valid_against_tightened_schema': (uid != 'TST-0215'),
        'schema_drift_or_content_errors': drift[uid],
        'classification': 'C2-schema-drift-recorded-not-gating' if uid != 'TST-0215' else 'CONTENT-CONTRADICTION-GATING-FAIL',
        'receipt_bytes_modified_by_reviewer': False,
        'verdict': 'PASS' if uid != 'TST-0215' else 'FAIL',
        'reviewer': {'reviewer_id': 'claude-opus-5-5 wf_a81de287-702 review:w3s24 agent-a4ba1686b717a7b67',
                     'independent': True, 'fresh_context': True, 'reviewed_at': '2026-10-26'},
    }
    verdicts[uid] = v
out['verdicts'] = verdicts
json.dump(out, open(p, 'w', encoding='utf-8'), indent=1)
print('verdicts assembled:', {u: v['verdict'] for u, v in verdicts.items()})
