"""w3s10 resume review - Phase 1: verify all 12 units, NO edits.

Instruments per unit:
  I1  command-center/p2-wave/_measure_one_delivered.py <uid>   (predicate + live probes + manifest sha + sentinel)
  I2  platform/lib/schema_resolver.validate_artifact          (repo-blessed schema resolver)
  I3  command-center/receipt_validate.py                      (admission gate: parse+schema+catalog xref)
  I4  platform/lib/receipt_schema_gate.py --json              (layer-1 schema + layer-2 completion, informational)
  I5  reviewer-recomputed sha256 (CRLF->LF) vs manifest primary row
"""
import json, hashlib, subprocess, sys, os, time
from pathlib import Path

R = Path(r'C:\Users\Prekzursil\p2-g1')
UNITS = ["IMP-0084", "IMP-0090", "IMP-0093", "IMP-0097", "IMP-0098", "IMP-0103",
         "IMP-0134", "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168", "IMP-0189"]
PY = sys.executable
MEASURE = R / 'command-center/p2-wave/_measure_one_delivered.py'
ADMIT = R / 'command-center/receipt_validate.py'
GATE = R / 'platform/lib/receipt_schema_gate.py'
OUT = R / '_rev_w3s10_resume_phase1_results.json'

sys.path.insert(0, str(R / 'platform' / 'lib'))
from schema_resolver import validate_artifact  # noqa: E402

catalog = json.load(open(R / 'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
idx = {u['id']: u for u in catalog['work_units']}


def lfsha(p):
    raw = Path(p).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw), raw


results = {}
for uid in UNITS:
    t0 = time.time()
    rec = {'id': uid}
    unit = idx[uid]
    declared_schema = unit.get('output_schema')
    rec['declared_schema'] = declared_schema
    rpath = R / unit['output_path']
    rec['output_path'] = str(unit['output_path'])

    # ---- I1: measure (predicate + probes + manifest sha + sentinel) ----
    try:
        p = subprocess.run([PY, '-I', '-B', str(MEASURE), uid], cwd=str(R),
                           capture_output=True, text=True, timeout=2900)
        rec['I1_rc'] = p.returncode
        rec['I1_tail'] = ((p.stdout or '') + (p.stderr or ''))[-500:]
    except subprocess.TimeoutExpired:
        rec['I1_rc'] = 124
        rec['I1_tail'] = 'TIMEOUT'

    # ---- artifact predicate (direct) ----
    try:
        doc = json.loads(rpath.read_text(encoding='utf-8'))
        rec['parses'] = True
        st = str(doc.get('state', '')).upper()
        rec['self_state'] = st
        rec['self_blocked'] = st in {'BLOCKED', 'FAILED', 'SEVERED', 'TIMEOUT'}
    except Exception as e:
        doc = None
        rec['parses'] = False
        rec['parse_err'] = repr(e)
    rec['exists_nonempty'] = bool(rpath.is_file() and rpath.stat().st_size > 0)
    rev = (doc or {}).get('reviewer') or {}
    rec['prior_reviewer'] = {k: rev.get(k) for k in ('reviewer_id', 'verdict', 'independent', 'fresh_context')}

    # ---- I2: schema_resolver ----
    if doc is not None:
        try:
            errs = validate_artifact(doc, declared_schema)
            rec['I2_errors'] = errs[:12]
            rec['I2_ok'] = not errs
        except Exception as e:
            rec['I2_ok'] = False
            rec['I2_errors'] = ['resolver-exception: ' + repr(e)]
    else:
        rec['I2_ok'] = False

    # ---- I3: admission gate ----
    try:
        p = subprocess.run([PY, '-I', str(ADMIT), str(rpath)], cwd=str(R),
                           capture_output=True, text=True, timeout=300)
        rec['I3_rc'] = p.returncode
        rec['I3_out'] = ((p.stdout or '') + (p.stderr or ''))[-300:]
    except subprocess.TimeoutExpired:
        rec['I3_rc'] = 124
        rec['I3_out'] = 'TIMEOUT'

    # ---- I4: receipt_schema_gate (layer1 + layer2 informational) ----
    try:
        p = subprocess.run([PY, '-I', str(GATE), str(rpath), '--json'], cwd=str(R),
                           capture_output=True, text=True, timeout=300)
        txt = p.stdout or ''
        rec['I4_rc'] = p.returncode
        try:
            j = json.loads(txt)
            rec['I4_layer1_valid'] = j.get('schema_valid', j.get('layer1_valid'))
            rec['I4_complete'] = j.get('complete')
            conds = j.get('conditions') or []
            rec['I4_blocking'] = [c.get('condition') or c.get('name') for c in conds
                                  if isinstance(c, dict) and c.get('blocking')]
            rec['I4_blocking_details'] = [
                (c.get('condition') or c.get('name'), str(c.get('basis', ''))[:120])
                for c in conds if isinstance(c, dict) and c.get('blocking')][:8]
        except Exception:
            rec['I4_raw'] = txt[-400:]
    except subprocess.TimeoutExpired:
        rec['I4_rc'] = 124

    # ---- I5: my own sha vs manifest ----
    mp = R / ('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid)
    try:
        man = json.load(open(mp, encoding='utf-8'))
        rows = [a for a in man.get('artifacts', [])
                if str(a.get('path', '')).endswith('receipts/%s.json' % uid)]
        live, nbytes, _ = lfsha(rpath)
        rec['I5_live_sha'] = live
        rec['I5_live_bytes'] = nbytes
        rec['I5_rows'] = [{'sha256': r.get('sha256'), 'bytes': r.get('bytes'), 'role': r.get('role')}
                          for r in rows]
        rec['I5_match'] = any(r.get('sha256') == live for r in rows)
    except Exception as e:
        rec['I5_match'] = False
        rec['I5_err'] = repr(e)

    checks = {
        'artifact_ok': bool(rec['exists_nonempty'] and rec['parses'] and not rec.get('self_blocked')),
        'probes_live_exit0': rec['I1_rc'] == 0,
        'manifest_sha_match': bool(rec.get('I5_match')) and rec['I1_rc'] == 0,
        'output_schema_valid': bool(rec.get('I2_ok')) and rec['I3_rc'] == 0,
    }
    rec['checks'] = checks
    rec['verdict'] = 'PASS' if all(checks.values()) else 'FAIL'
    rec['fail_reasons'] = []
    if not checks['artifact_ok']:
        rec['fail_reasons'].append('artifact predicate fails (exists/non-empty/parse/not-self-blocked)')
    if not checks['probes_live_exit0']:
        rec['fail_reasons'].append('I1 measure rc=%s (probes/predicate/sentinel/manifest)' % rec.get('I1_rc'))
    if not checks['manifest_sha_match'] and rec['I1_rc'] == 0:
        rec['fail_reasons'].append('I5 sha mismatch vs manifest')
    if not checks['output_schema_valid']:
        rec['fail_reasons'].append('schema: I2 %s / I3 rc=%s' % (
            'ok' if rec.get('I2_ok') else (rec.get('I2_errors') or ['?'])[:3], rec.get('I3_rc')))
    rec['secs'] = round(time.time() - t0, 1)
    print('%s %s %.1fs | I1=%s I2=%s I3=%s I4_l1=%s I5=%s' % (
        uid, rec['verdict'], rec['secs'], rec['I1_rc'], rec.get('I2_ok'), rec.get('I3_rc'),
        rec.get('I4_layer1_valid'), rec.get('I5_match')), flush=True)

json.dump(results, open(OUT, 'w', encoding='utf-8'), indent=1, default=str)
print('WROTE', OUT)
