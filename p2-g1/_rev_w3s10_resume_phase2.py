"""w3s10 resume review - Phase 2: close the verified-PASS units with an independent reviewer closure.

For each unit in PHASE2_UNITS (verified PASS in phase1b):
  1. backup receipt + manifest row to _rev_w3s10_resume_backup/
  2. set reviewer = w3s10 independent closure (prior block preserved verbatim under
     extensions.w3s10_closure.prior_reviewer)
  3. update UNIT-ARTIFACT-MANIFEST.json primary row sha256+bytes to the new receipt bytes
  4. post-edit re-verify: parse + I2 resolver + I3 admission + I4 gate layer-1 + I1 measure rc=0
  5. any failure -> restore both files byte-exact from backup, re-verify restoration, report FAIL-closure
"""
import json, hashlib, subprocess, sys, os, shutil, time, datetime
from pathlib import Path

R = Path(r'C:\Users\Prekzursil\p2-g1')
PHASE2_UNITS = ["IMP-0084", "IMP-0090", "IMP-0093", "IMP-0097", "IMP-0098", "IMP-0103",
                "IMP-0134", "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168"]
REVIEWER_ID = 'claude-opus-5-5-ind-reviewer-w3-shard10-2026-10-26'
NOW = '2026-10-26T07:40:00Z'
PY = sys.executable
MEASURE = R / 'command-center/p2-wave/_measure_one_delivered.py'
ADMIT = R / 'command-center/receipt_validate.py'
GATE = R / 'platform/lib/receipt_schema_gate.py'
BACKUP = R / '_rev_w3s10_resume_backup'
BACKUP.mkdir(exist_ok=True)

sys.path.insert(0, str(R / 'platform' / 'lib'))
from schema_resolver import validate_artifact  # noqa: E402

catalog = json.load(open(R / 'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
idx = {u['id']: u for u in catalog['work_units']}

results = {}
for uid in PHASE2_UNITS:
    unit = idx[uid]
    rpath = R / unit['output_path']
    mpath = R / ('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid)
    out = {'id': uid}

    # -- 1. backups --
    orig_receipt_bytes = rpath.read_bytes()
    orig_manifest_bytes = mpath.read_bytes()
    (BACKUP / ('%s.receipt.json' % uid)).write_bytes(orig_receipt_bytes)
    (BACKUP / ('%s.manifest.json' % uid)).write_bytes(orig_manifest_bytes)

    # -- 2. receipt edit --
    doc = json.loads(orig_receipt_bytes.decode('utf-8'))
    prior_rev = doc.get('reviewer')
    ext = doc.get('extensions') if isinstance(doc.get('extensions'), dict) else {}
    ext['w3s10_closure'] = {
        'prior_reviewer': prior_rev,
        'review_basis': {
            'instruments': 'I1 _measure_one_delivered rc=0 (predicate+live probes+manifest sha+sentinel); '
                           'I2 schema_resolver.validate_artifact []; I3 receipt_validate ACCEPT; '
                           'I4 receipt_schema_gate schema_errors=[]; I5 reviewer sha256 CRLF->LF match',
            'artifact_sha256_at_review': hashlib.sha256(
                orig_receipt_bytes.replace(b'\r\n', b'\n')).hexdigest(),
            'reviewed_by_wave': 'wave3-shard10-resume',
            'note': 'Reviewer did not build this unit. All four contract checks re-derived live on the '
                    'current bytes in a fresh context. Prior reviewer block preserved verbatim; '
                    'receipt re-serialized (indent=2) with manifest primary row sha/bytes refreshed to match.',
        },
    }
    doc['extensions'] = ext
    doc['reviewer'] = {
        'reviewer_id': REVIEWER_ID,
        'verdict': 'PASS',
        'independent': True,
        'fresh_context': True,
        'reviewed_at': NOW,
        'notes': 'Wave-3 shard-10 independent reviewer closure (resume run). Reviewer did not build this '
                 'unit; re-derived all four contract checks live in a fresh context on the CURRENT bytes: '
                 'artifact predicate (exists/non-empty/parses/not-self-blocked), both named probes re-run '
                 'live (rc=0), reviewer-recomputed sha256 (CRLF-normalized) matched against '
                 'UNIT-ARTIFACT-MANIFEST.json primary row, catalog output_schema validated under three '
                 'independent instruments (repo schema_resolver, receipt_validate admission gate, '
                 'receipt_schema_gate layer-1). Prior document preserved verbatim under '
                 'extensions.w3s10_closure.',
    }
    new_receipt_text = json.dumps(doc, indent=2, ensure_ascii=False) + '\n'
    rpath.write_text(new_receipt_text, encoding='utf-8', newline='\n')

    # -- 3. manifest row update --
    man = json.loads(orig_manifest_bytes.decode('utf-8'))
    live_sha = hashlib.sha256(new_receipt_text.encode('utf-8').replace(b'\r\n', b'\n')).hexdigest()
    live_len = len(new_receipt_text.encode('utf-8'))
    touched = 0
    for row in man.get('artifacts', []):
        if str(row.get('path', '')).endswith('receipts/%s.json' % uid):
            row['sha256'] = live_sha
            row['bytes'] = live_len
            touched += 1
    new_manifest_text = json.dumps(man, indent=2, ensure_ascii=False) + '\n'
    mpath.write_text(new_manifest_text, encoding='utf-8', newline='\n')
    out['manifest_rows_updated'] = touched

    # -- 4. post-edit re-verify --
    ok = True
    reasons = []
    try:
        doc2 = json.loads(rpath.read_text(encoding='utf-8'))
        errs = validate_artifact(doc2, unit.get('output_schema'))
        if errs:
            ok = False
            reasons.append('I2 post-edit: %s' % errs[:3])
        p = subprocess.run([PY, '-I', str(ADMIT), str(rpath)], cwd=str(R),
                           capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            ok = False
            reasons.append('I3 post-edit rc=%d %s' % (p.returncode, ((p.stdout or '') + (p.stderr or ''))[-200:]))
        p = subprocess.run([PY, '-I', str(GATE), str(rpath), '--json'], cwd=str(R),
                           capture_output=True, text=True, timeout=300)
        try:
            j = json.loads(p.stdout or '[]')
            row0 = j[0] if isinstance(j, list) and j else {}
            if row0.get('schema_errors'):
                ok = False
                reasons.append('I4 post-edit schema_errors: %s' % str(row0.get('schema_errors'))[:200])
        except Exception:
            ok = False
            reasons.append('I4 post-edit unparseable')
        p = subprocess.run([PY, '-I', '-B', str(MEASURE), uid], cwd=str(R),
                           capture_output=True, text=True, timeout=2900)
        out['post_measure_rc'] = p.returncode
        if p.returncode != 0:
            ok = False
            reasons.append('I1 post-edit measure rc=%d: %s' % (p.returncode, ((p.stdout or '') + (p.stderr or ''))[-250:]))
        out['post_sha'] = live_sha[:16]
    except Exception as e:
        ok = False
        reasons.append('post-edit exception: ' + repr(e))

    # -- 5. restore on failure --
    if not ok:
        rpath.write_bytes(orig_receipt_bytes)
        mpath.write_bytes(orig_manifest_bytes)
        d1 = hashlib.sha256(rpath.read_bytes()).hexdigest() == hashlib.sha256(orig_receipt_bytes).hexdigest()
        d2 = hashlib.sha256(mpath.read_bytes()).hexdigest() == hashlib.sha256(orig_manifest_bytes).hexdigest()
        out['restored'] = bool(d1 and d2)
        out['verdict'] = 'FAIL-CLOSURE-ERROR'
        out['reasons'] = reasons
    else:
        out['verdict'] = 'CLOSED-PASS'
        out['reasons'] = []
    print('%s %s %s' % (uid, out['verdict'], '; '.join(reasons)[:200] if reasons else
                        'measure rc=%s rows=%d sha=%s...' % (out.get('post_measure_rc'), touched, out.get('post_sha'))),
          flush=True)
    results[uid] = out
    time.sleep(0.2)

json.dump(results, open(R / '_rev_w3s10_resume_phase2_results.json', 'w', encoding='utf-8'),
          indent=1, default=str)
print('WROTE phase2 results')
