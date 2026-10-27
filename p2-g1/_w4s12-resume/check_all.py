"""W4 shard-12 resume: strict per-unit receipt validation.

(a) generic receipt_schema_gate full evaluate (12-condition predicate + Draft2020-12)
(b) declared-output_schema validation via schema_resolver (the C5-reviewer instrument)
(c) receipt_core SUCCESS conditionals (manifest_registration.registered etc.)
"""
import importlib.util, json, subprocess, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MINE = ['IMP-0461','IMP-0465','IMP-0476','IMP-0478','IMP-0480',
        'REL-0001','REL-0006','REL-0014','REL-0017','REL-0020','REL-0021','REL-0022']

cat = json.loads((REPO/'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}

rspec = importlib.util.spec_from_file_location("sr", REPO/"platform/lib/schema_resolver.py")
sr = importlib.util.module_from_spec(rspec); sys.modules["sr"] = rspec; rspec.loader.exec_module(sr)

results = {}
for uid in MINE:
    u = byid[uid]
    rp = REPO/u['output_path']
    rec = json.loads(rp.read_text(encoding='utf-8'))
    row = {"state": rec.get("state")}
    # (a) generic gate
    p = subprocess.run([sys.executable, 'platform/lib/receipt_schema_gate.py', u['output_path'], '--json'],
                       capture_output=True, text=True, cwd=str(REPO))
    try:
        d = json.loads(p.stdout)
        r0 = d[0] if isinstance(d, list) else d
        row['gate_marker'] = r0.get('marker')
        row['gate_complete'] = r0.get('complete')
        conds = r0.get('conditions') or {}
        row['gate_unsat'] = sorted(k for k,v in conds.items() if v == 'UNSATISFIED')
        row['gate_notchecked'] = sorted(k for k,v in conds.items() if v == 'NOT-CHECKED')
        row['gate_schema_errors'] = len(r0.get('schema_errors') or [])
    except Exception as e:
        row['gate_err'] = f"{type(e).__name__}: {e}; raw={p.stdout[:200]}"
    # (b) declared output_schema
    try:
        errs = sr.validate_artifact(rec, u.get('output_schema'))
        row['declared_schema'] = u.get('output_schema')
        row['declared_errors'] = errs[:8]
        row['declared_error_count'] = len(errs)
    except Exception as e:
        row['declared_err'] = f"{type(e).__name__}: {e}"
    # (c) receipt_core SUCCESS conditionals
    mr = rec.get('manifest_registration')
    row['manifest_registered'] = (mr or {}).get('registered') if isinstance(mr, dict) else mr
    rev = rec.get('reviewer') or {}
    row['reviewer_ok_literal'] = rev.get('verdict') == 'PASS' and rev.get('independent') is True
    dc = rec.get('downstream_consumers') or []
    row['consumers'] = len(dc)
    results[uid] = row

(REPO/'_w4s12-resume/check_results.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
for uid, row in results.items():
    print(f"== {uid} state={row['state']}")
    print(f"   gate_complete={row.get('gate_complete')} marker={str(row.get('gate_marker'))[:80]}")
    print(f"   unsat={row.get('gate_unsat')} not_checked={row.get('gate_notchecked')} schema_errs={row.get('gate_schema_errors')}")
    print(f"   declared_errs={row.get('declared_error_count')} {row.get('declared_schema')}")
    if row.get('declared_errors'):
        for e in row['declared_errors'][:5]:
            print(f"     - {e[:150]}")
    print(f"   manifest_registered={row['manifest_registered']} reviewer_ok={row['reviewer_ok_literal']} consumers={row['consumers']}")
