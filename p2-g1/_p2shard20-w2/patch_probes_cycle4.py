"""Cycle-4 fixes: RES-0185 partition semantics, RES-0187 classifier, SYN-0007 sort_key."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\_p2shard20-w2\write_probes.py")
src = p.read_text(encoding="utf-8")

# --- RES-0185 probe1: multi = support_status MULTI partition
old = '''multi_rec = sum(1 for r in real
                if not r.get("single_source")
                and str(r.get("support_status", "")).upper() != "UNSUPPORTED"
                and (r.get("class_count") or 0) >= 2)
need(multi_rec == doc.get("multi_count"),
     f"multi_count {doc.get('multi_count')} != recount {multi_rec}")'''
new = '''multi_rec = sum(1 for r in real
                if str(r.get("support_status", "")).upper() == "MULTI")
need(multi_rec == doc.get("multi_count"),
     f"multi_count {doc.get('multi_count')} != recount {multi_rec}")'''
assert old in src, "R0185 probe1 multi anchor missing"
src = src.replace(old, new)

# --- RES-0185 probe2: distinct-class recount + support_status partition identities
old = '''bad = 0
for r in xtab:
    distinct = sum(1 for f in class_fields if int(r.get(f, 0) or 0) > 0)
    if distinct != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where distinct-class recount != class_count")'''
new = '''bad = 0
for r in xtab:
    distinct = sum(1 for f in class_fields if f != "unclassified"
                   and int(r.get(f, 0) or 0) > 0)
    if distinct != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where distinct-class recount != class_count")
need(sum(1 for r in xtab if str(r.get("support_status", "")) == "SINGLE-SOURCE")
     == sum(1 for r in xtab if r.get("independent_source_count") == 1),
     "SINGLE-SOURCE partition != independent_source_count==1 rows")
need(all((r.get("class_count") == 1) == (str(r.get("support_status", "")) == "SINGLE-CLASS")
         for r in xtab), "SINGLE-CLASS partition != class_count==1 rows")'''
assert old in src, "R0185 probe2 anchor missing"
src = src.replace(old, new)

# --- RES-0187 probe1: the rewrite dropped the classifier; put it back
old = '''need(isinstance(ctrl.get("not_in_coverage_fraction"), bool)
     and ctrl.get("not_in_coverage_fraction") is True,
     "controls.not_in_coverage_fraction must be the boolean flag True (controls sit outside the measured fraction)")
labeled = (ctrl.get("labeled") or [])'''
new = '''need(isinstance(ctrl.get("not_in_coverage_fraction"), bool)
     and ctrl.get("not_in_coverage_fraction") is True,
     "controls.not_in_coverage_fraction must be the boolean flag True (controls sit outside the measured fraction)")


def classify(row):
    """Strict rule: CHALLENGED only with a recorded triad (query+results+verdict)."""
    triad = row.get("query") and (row.get("results") or row.get("result_set")) and row.get("verdict")
    return "CHALLENGED" if triad else "UNCHALLENGED"


labeled = (ctrl.get("labeled") or [])'''
assert old in src, "R0187 classifier anchor missing"
src = src.replace(old, new)

# --- SYN-0007 probe2: resort by the recorded deterministic sort_key
old = '''recomputed = sorted(ranking,
                    key=lambda r: (-float(r.get("score_micro") or 0.0),
                                   str(r.get("intervention_id"))))
need([r.get("intervention_id") for r in recomputed]
     == [r.get("intervention_id") for r in ranking],
     "recorded order != deterministic re-sort by (-score_micro, intervention_id)")
need(all(r.get("score_micro") is not None for r in ranking),
     "a ranking row lacks its score_micro")'''
new = '''recomputed = sorted(ranking, key=lambda r: r.get("sort_key"))
need([r.get("intervention_id") for r in recomputed]
     == [r.get("intervention_id") for r in ranking],
     "recorded order != re-sort by the recorded deterministic sort_key")
need(all(r.get("sort_key") is not None for r in ranking),
     "a ranking row lacks its deterministic sort_key")'''
assert old in src, "S0007 probe2 anchor missing"
src = src.replace(old, new)

p.write_text(src, encoding="utf-8")
print("SUCCESS:cycle4 patches applied")
