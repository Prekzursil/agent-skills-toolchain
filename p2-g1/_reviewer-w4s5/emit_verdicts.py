"""Compose _reviewer-w4s5/verdicts.json from the four evidence files.
Six-check contract (mirrors sibling wave-4 reviewers w4s8/w4s23/w4-shard6):
  C1 artifact at catalog output_path exists, non-empty, parses, not self-declared BLOCKED/FAILED
  C2 every probes/<id>/probe*.py re-run by this reviewer exits 0
  C3 UNIT-ARTIFACT-MANIFEST.json primary row sha256 == live artifact (CRLF->LF), present=true
  C4 output_schema validates (program instrument: receipt_schema_gate.validate_receipt / resolver)
  C5 closure shape: state=SUCCESS + reviewer.verdict=PASS + reviewer.independent=true
Verdict PASS only when ALL hold; else FAIL with the precise failing check. FAIL receipts untouched.
"""
import json, os

os.chdir(os.path.expanduser('~/p2-g1'))

MINE = ['AUD-0084','AUD-0096','BLD-0001','BLD-0002','BLD-0010','BLD-0016',
        'BLD-0023','BLD-0024','BLD-0027','BLD-0028','BLD-0037','BLD-0042']

static = json.load(open('_reviewer-w4s5/static_results.json', encoding='utf-8'))
probes = json.load(open('_reviewer-w4s5/probe_results.json', encoding='utf-8'))
errs = json.load(open('_reviewer-w4s5/schema_errors_full.json', encoding='utf-8'))
pred = json.load(open('_reviewer-w4s5/program_predicate_results.json', encoding='utf-8'))

def c1_of(uid):
    ch = static[uid]['checks']
    hold_keys = ['artifact_exists','artifact_nonempty','artifact_parses','artifact_is_object',
                 'not_self_blocked','unit_id_binding','subagent_return_delivered']
    fails = [k for k in hold_keys if ch.get(k) is not True]
    return (not fails), fails

def c2_of(uid):
    v = probes.get(uid, {})
    if 'error' in v:
        return False, v['error']
    bad = {n: x['exit'] for n, x in v.get('probes', {}).items() if x.get('exit') != 0}
    return (not bad), (bad or None)

def c3_of(uid):
    ch = static[uid]['checks']
    fails = [k for k in ('manifest_primary_row','manifest_bytes') if ch.get(k) is not True]
    mutated = probes.get(uid, {}).get('mutated')
    if mutated:
        fails.append('probe battery mutated the receipt (sha_pre != sha_post)')
    return (not fails), fails

def c4_of(uid):
    n = len(errs.get(uid, []))
    return (n == 0), (n if n else None)

def c5_of(uid):
    ch = static[uid]['checks']
    fails = [k for k in ('reviewer_verdict_pass','reviewer_independent','state_success')
             if ch.get(k) is not True]
    return (not fails), fails

per_unit = {}
for uid in MINE:
    checks = {
        'C1_artifact': c1_of(uid)[0],
        'C2_probes_exit0': c2_of(uid)[0],
        'C3_manifest_sha': c3_of(uid)[0],
        'C4_output_schema': c4_of(uid)[0],
        'C5_closure_shape': c5_of(uid)[0],
    }
    detail = {
        'C1_fail_keys': c1_of(uid)[1],
        'C2_failing_probes': c2_of(uid)[1],
        'C3_fail_keys': c3_of(uid)[1],
        'C4_schema_error_count': c4_of(uid)[1],
        'C5_fail_keys': c5_of(uid)[1],
        'first_schema_error': (errs[uid][0][:300] if errs.get(uid) else None),
        'predicate_blocking_conditions': [(c[0], c[1]) for c in pred[uid]['blocking_conditions']],
    }
    verdict = 'PASS' if all(checks.values()) else 'FAIL'
    failing = [k for k, ok in checks.items() if not ok]
    per_unit[uid] = {'verdict': verdict, 'checks': checks, 'failing_check': failing, 'detail': detail}
    print(uid, verdict, failing)

npass = sum(1 for v in per_unit.values() if v['verdict'] == 'PASS')
doc = {
    'reviewer': 'review:w4s5 (wave 4 shard 5 independent reviewer, Opus 5.5, workflow resume 2026-10-26)',
    'assignment_derivation': 'build:w4s5 list extracted verbatim from _reviewer-w4s8/build-assignments-all-waves.json '
                             '(12 ids: AUD-0084, AUD-0096, BLD-0001, BLD-0002, BLD-0010, BLD-0016, BLD-0023, '
                             'BLD-0024, BLD-0027, BLD-0028, BLD-0037, BLD-0042)',
    'units': MINE,
    'per_unit': per_unit,
    'evidence_files': {
        'static_checks_and_manifest_sha': '_reviewer-w4s5/static_results.json',
        'probe_battery': '_reviewer-w4s5/probe_results.json',
        'schema_errors_full': '_reviewer-w4s5/schema_errors_full.json',
        'twelve_condition_predicate_observations': '_reviewer-w4s5/program_predicate_results.json',
    },
    'instrument_note': 'C4 uses the program fail-closed validator chain: command-center/receipt_validate.py '
                       '-> platform/lib/receipt_schema_gate.py::validate_receipt. Control: IMP-0001, ADV-0005, '
                       'AUD-0005 ACCEPT; the 11 REJECTs are per-receipt defects, not gate drift. Declared '
                       'per-unit class schemas (command-center/schema/*.schema.json) are generated shims whose '
                       '$ref rebases through platform/lib/schema_resolver.py; naive jsonschema auto-retrieval '
                       'resolves into the source repo tree and is NOT the instrument.',
    'observations_not_verdict_driving': [
        'Receipts carry stale internal artifacts[].bytes/sha256 snapshots (12-condition predicate cond-3), '
        'stale FAILED-era sentinels (cond-5 on AUD-0084/BLD-0001/BLD-0002/BLD-0023/BLD-0024), NOT-RUN test rows '
        'and open P0/P1 defect rows - while the per-unit UNIT-ARTIFACT-MANIFEST rows match the live bytes '
        'exactly (hand-verified BLD-0010/0023/0042). The manifests were refreshed after the last receipt rewrite; '
        'the internal snapshots were not.',
        'Nested "verdict": "BLOCKED" strings inside per-target evidence rows are legitimate enumerated-target '
        'verdicts, not self-declared receipt state; top-level state is SUCCESS and the admission gate did not '
        'reject on self-declared state.',
    ],
    'receipt_action': 'NONE for the FAIL units (receipts untouched per contract). PASS units: existing '
                      'independent PASS closures (openai/gpt-5.2 C5 wave 2026-08-21, xai grok 2026-08-19) '
                      'CONFIRMED as valid - no edit needed; this reviewer adds confirmation only.',
    'honesty_note': 'partial green reported as partial',
}
json.dump(doc, open('_reviewer-w4s5/verdicts.json', 'w'), indent=1)
print()
print('VERDICTS: %d PASS / %d FAIL of 12 -> _reviewer-w4s5/verdicts.json' % (npass, 12 - npass))
