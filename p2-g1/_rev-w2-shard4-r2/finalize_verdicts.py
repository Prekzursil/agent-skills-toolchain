import json, os, sys, glob, datetime
R=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.abspath(os.path.join(R,'..')))
IDS=['AUD-0043','AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075']
static=json.load(open('_rev-w2-shard4-r2/static_sha_results.json',encoding='utf-8'))
schema=json.load(open('_rev-w2-shard4-r2/schema_results.json',encoding='utf-8'))
summ=open('_rev-w2-shard4-r2/probe_rerun/SUMMARY.txt',encoding='utf-8').read()
probe_rc={}
for line in summ.splitlines():
    m=line.strip()
    if m.startswith('AUD-') and ' rc=' in m:
        u,n,rc=m.split()[:3]
        probe_rc[f'{u}::{n}']=int(rc.split('=')[1])
cat=json.load(open('command-center/WORK-UNIT-CATALOG.json',encoding='utf-8'))
wu={u.get('id'):u for u in cat['work_units'] if isinstance(u,dict)}
units_verdicts={}; all_pass=True
for uid in IDS:
    c=static[uid]; sc=schema[uid]
    probes={k:v for k,v in probe_rc.items() if k.startswith(uid+'::')}
    probes_ok=len(probes)>=2 and all(v==0 for v in probes.values())
    static_ok=c['exists'] and c.get('nonempty') and c.get('parses') and c.get('not_self_blocked') and c.get('sha_match_manifest_norm') and c.get('receipt_sha')==c.get('manifest_sha')
    schema_ok=sc.get('error_count')==0
    checks={'artifact_exists_nonempty_parses':static_ok and c.get('parses'),
            'not_self_blocked':c.get('not_self_blocked'),
            'artifact_self_state':c.get('artifact_state'),
            'probes_live_exit0':probes_ok,'probe_rcs':probes,
            'manifest_sha256_match_crlf_normalized':c.get('sha_match_manifest_norm'),
            'receipt_sha_matches_manifest':c.get('receipt_sha')==c.get('manifest_sha'),
            'output_schema_error_count':sc.get('error_count'),
            'output_schema_errors_sample':(sc.get('errors_first5') or [])[:5]}
    ok=bool(checks['artifact_exists_nonempty_parses'] and checks['not_self_blocked'] and probes_ok and checks['manifest_sha256_match_crlf_normalized'] and checks['receipt_sha_matches_manifest'] and schema_ok)
    if not ok: all_pass=False
    fail=None
    if not schema_ok:
        fail=f"output_schema validation via canonical platform/lib/schema_resolver.validate_artifact against catalog {c['schema']}: {sc.get('error_count')} errors"
    elif not probes_ok:
        fail=f"live probe rerun non-zero exit: {probes}"
    elif not static_ok:
        fail=f"static/sha check failed: { {k:c.get(k) for k in ['exists','nonempty','parses','not_self_blocked','sha_match_manifest_norm']} }"
    units_verdicts[uid]={'verdict':'PASS' if ok else 'FAIL','failing_check':fail,'checks':checks}
out={'reviewer':'claude-opus-5-5 wave2-shard4-independent-reviewer (re-verification r2)',
 'reviewed_at':datetime.date.today().isoformat(),
 'shard':'wave2-shard4',
 'units':IDS,
 'method':{
  'artifact_checks':'exists/non-empty/JSON-parse/self-block scan (top-level state/verdict + body marker scan) at catalog output_path',
  'probes':'both named probes per unit re-executed live by reviewer transport (PYTHONDONTWRITEBYTECODE=1 python3 -B from repo root), exit 0 required',
  'sha':'recompute sha256 of live artifact after CRLF->LF normalization, compare to probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row + receipt-claimed sha',
  'schema':'canonical instrument platform/lib/schema_resolver.py validate_artifact (repo-local _root=p2-g1, AST_INTEGRATE_ROOT unset, no network); reachability control: AUD-0006 (audit-inventory class, same class as AUD-0066) and SYN-0027 (self-audit-report) validate ZERO errors through the same instrument in this re-verification; artifact-class-profiles.schema.json byte-identical (sha f89a4209...) between p2-g1 and source/ast-integrate so instrument ambiguity is moot'},
 'units_verdicts':units_verdicts,
 'receipts_unchanged':True,
 'notes':[
  'ALL 12 units FAIL on exactly one check: output_schema validation against the catalog class profile (platform/schema/artifact-class-profiles.schema.json via the repo shim chain). Error counts: AUD-0043=40, AUD-0044=26, AUD-0047=27, AUD-0053=14, AUD-0055=17, AUD-0057=26, AUD-0064=1, AUD-0066=32, AUD-0069=33, AUD-0071=17, AUD-0072=38, AUD-0075=30. Dominant shapes: missing required root keys (downstream_consumers, negative_controls, min_bytes_threshold, manifest_registration, report, retry, residual_unknowns, schema_version, spec_anchor, timestamps), artifacts rows missing bytes/sha256, evidence probes rows not matching the profile probe shape, defects items missing required fields.',
  'Reachability control re-proven in this run: AUD-0006 (audit-inventory, same class as AUD-0066) and SYN-0027 (self-audit-report) validate ZERO errors through the identical canonical instrument, so the schema bar is operative, reachable, and not instrument drift. artifact-class-profiles.schema.json is byte-identical (sha256 f89a4209d2fbb01331db87194c22be6976c0de5786fae5cdb47c3666a6e558d3) between ~/p2-g1 and ~/source/ast-integrate; resolver _root()=p2-g1, AST_INTEGRATE_ROOT unset.',
  'Everything except schema HOLDS and was re-proven live: all 12 artifacts exist/non-empty/parse at catalog output_path with no self-block markers (top-level or body); AUD-0057 self-state PARTIAL and AUD-0072 self-state BUILT are neither BLOCKED nor FAILED; manifest primary sha256 (CRLF->LF normalized) matches live artifacts and receipt-claimed shas for all 12; named probes re-executed by reviewer transport (see per-unit probe_rcs).',
  'SECONDARY closure barrier independent of schema (surfacing for the fix wave): catalog reviewer_requirement for AUD-0053, AUD-0057, AUD-0069, AUD-0071 demands a cross-vendor Codex reviewer, and AUD-0075 demands TWO reviewers (fresh-context Claude AND Codex, escalate disagreement to owner). A Claude-only PASS cannot satisfy those five even after a schema fix.',
  'AUD-0072 artifact self-declares failure.blocked_on=catalog reviewer_requirement with classification [reviewer-absent] while state=BUILT; honest but means the artifact itself records the review gate as open.',
  'Per fail-closed instruction, receipts AUD-0043/0044/0047/0053/0055/0057/0064/0066/0069/0071/0072/0075 are UNCHANGED (state=BLOCKED, reviewer.verdict=NOT-REVIEWED, failure.classification=[reviewer-absent]).'
 ]}
json.dump(out,open('_rev-w2-shard4-r2/verdicts.json','w',encoding='utf-8'),indent=1)
print('ALL_PASS' if all_pass else 'NOT_ALL_PASS')
for uid in IDS: print(uid, units_verdicts[uid]['verdict'], units_verdicts[uid]['failing_check'] or '')
