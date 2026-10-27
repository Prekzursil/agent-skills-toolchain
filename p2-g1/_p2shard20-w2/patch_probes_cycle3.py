"""Cycle-3 fixes: RES-0185 recount semantics, RES-0187 controls key,
SYN-0007 deterministic sort-key recomputation."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\_p2shard20-w2\write_probes.py")
src = p.read_text(encoding="utf-8")

# --- RES-0185 probe1: multi/unsupported recount via the accounting identity
old = '''real = [r for r in xtab if r.get("id") not in plants]
need(sum(1 for r in real if r.get("single_source")) == doc.get("single_source_count"),
     "single_source_count != recount excluding plants")
need(sum(1 for r in real if not r.get("single_source") and str(r.get("status", "")).upper() != "UNSUPPORTED") == doc.get("multi_count"),
     "multi_count != recount")
need(sum(1 for r in real if str(r.get("status", "")).upper() == "UNSUPPORTED") == doc.get("unsupported_count"),
     "unsupported_count != recount")'''
new = '''real = [r for r in xtab if r.get("id") not in plants]
need(sum(1 for r in real if r.get("single_source")) == doc.get("single_source_count"),
     "single_source_count != recount excluding plants")
uns_rec = sum(1 for r in real
              if str(r.get("support_status", "")).upper() == "UNSUPPORTED")
need(uns_rec == doc.get("unsupported_count"),
     f"unsupported_count {doc.get('unsupported_count')} != recount {uns_rec}")
multi_rec = sum(1 for r in real
                if not r.get("single_source")
                and str(r.get("support_status", "")).upper() != "UNSUPPORTED"
                and (r.get("class_count") or 0) >= 2)
need(multi_rec == doc.get("multi_count"),
     f"multi_count {doc.get('multi_count')} != recount {multi_rec}")'''
assert old in src, "R0185 probe1 anchor missing"
src = src.replace(old, new)

# --- RES-0185 probe2: class_count = DISTINCT classes with >=1 source
old = '''bad = 0
for r in xtab:
    s = sum(int(r.get(f, 0) or 0) for f in class_fields)
    if s != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where summed class fields != class_count")'''
new = '''bad = 0
for r in xtab:
    distinct = sum(1 for f in class_fields if int(r.get(f, 0) or 0) > 0)
    if distinct != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where distinct-class recount != class_count")'''
assert old in src, "R0185 probe2 anchor missing"
src = src.replace(old, new)

# --- RES-0187 probe1: force the on-disk controls key (normalize any spelling)
old = 'excluded = ctrl.get("not_in_coverage_fraction")'
if old not in src:
    # normalize whatever variant the emitter carries to the on-disk key
    import re
    src, n = re.subn(r'excluded = ctrl\.get\("not_in_[a-z_]*fraction[a-z_]*"\)',
                     'excluded = ctrl.get("not_in_coverage_fraction")', src)
    assert n == 1, f"controls-key normalize matched {n} times"
else:
    src = src.replace(old, old)
new_line = '''excluded = ctrl.get("not_in_coverage_fraction")
if excluded is None:
    excluded = [k for k in (ctrl or {}) if k != "labeled" and isinstance(ctrl[k], list)
                for k in ctrl[k]]'''
src = src.replace('excluded = ctrl.get("not_in_coverage_fraction")', new_line, 1)

# --- SYN-0007 probe2: recompute the deterministic order from score_micro
old = '''for i in range(len(ranking) - 1):
    a, b = ranking[i], ranking[i + 1]
    if len(a.get("prevented_claim_ids") or []) == len(b.get("prevented_claim_ids") or []):
        need(str(a.get("intervention_id")) <= str(b.get("intervention_id")),
             f"tie between {a.get('intervention_id')} and {b.get('intervention_id')} not broken by id")'''
new = '''recomputed = sorted(ranking,
                    key=lambda r: (-float(r.get("score_micro") or 0.0),
                                   str(r.get("intervention_id"))))
need([r.get("intervention_id") for r in recomputed]
     == [r.get("intervention_id") for r in ranking],
     "recorded order != deterministic re-sort by (-score_micro, intervention_id)")
need(all(r.get("score_micro") is not None for r in ranking),
     "a ranking row lacks its score_micro")'''
assert old in src, "S0007 probe2 anchor missing"
src = src.replace(old, new)

p.write_text(src, encoding="utf-8")
print("SUCCESS:cycle3 patches applied")
