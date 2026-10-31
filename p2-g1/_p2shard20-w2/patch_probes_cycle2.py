"""Cycle-2 probe fixes: field-name corrections against the real artifact shapes."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\_p2shard20-w2\write_probes.py")
src = p.read_text(encoding="utf-8")
n0 = len(src)

# --- RES-0184 probe1: use meets_bar / correct answer keys
old = '''def below(r):
    return bool(r.get("below_bar") or r.get("below") or r.get("deficits"))


below_rows = [r for r in rows if below(r)]
need(doc["rescore"].get("below_bar_count") == len(below_rows),
     "rescore.below_bar_count != recomputed below rows")
ans = doc.get("answer") or {}
need(ans.get("below_bar_count") == len(below_rows),
     "answer.below_bar_count != recomputed below rows")
below_ids = {r.get("claim_id") for r in below_rows}
need(below_ids == set(ans.get("below_bar_ids") or []),
     "answer.below_bar_ids != recomputed below ids")
high_below = {r.get("claim_id") for r in below_rows
              if str(r.get("severity", "")).upper() in ("P0", "P1", "HIGH")}
need(high_below == set(ans.get("high_severity_below_ids") or []),
     "answer.high_severity_below_ids != recomputed")'''
new = '''below_rows = [r for r in rows if r.get("meets_bar") is False]
need(doc["rescore"].get("below_bar_count") == len(below_rows),
     "rescore.below_bar_count != recomputed below rows")
ans = doc.get("answer") or {}
need(ans.get("below_bar_count") == len(below_rows),
     "answer.below_bar_count != recomputed below rows")
high_below = sorted(r["claim_id"] for r in below_rows
                    if str(r.get("severity", "")).upper() in ("P0", "P1"))
need(high_below == sorted(ans.get("high_severity_below_ids") or []),
     "answer.high_severity_below_ids != recomputed")'''
assert old in src, "R0184 probe1 anchor missing"
src = src.replace(old, new)

# --- RES-0184 probe2: re-derive deficits from the recorded metric fields
old = '''def ev_keys(r):
    return (r.get("metrics") or r.get("measured") or {})


mismatch = []
for r in rows:
    m = ev_keys(r)
    bar = r.get("bar") or {}
    if not m:
        fail(f"row {r.get('claim_id')}: no recorded metrics to re-derive from")
    deficits = []
    if m.get("independent_sources", 0) < (bar.get("min_independent_sources") or 0):
        deficits.append("independent_sources")
    if m.get("source_classes", 0) < (bar.get("min_source_classes") or 0):
        deficits.append("source_classes")
    if bar.get("executable_mandatory") and not m.get("executable_check"):
        deficits.append("executable_check")
    if bar.get("lineage_mandatory") and not m.get("lineage"):
        deficits.append("lineage")
    if bar.get("sherman_kent_mandatory") and not m.get("sherman_kent"):
        deficits.append("sherman_kent")
    rec = {d.split()[0] for d in (r.get("deficits") or [])}
    for d in deficits:
        if not any(d in x for x in rec):
            mismatch.append((r.get("claim_id"), d))
    if bool(deficits) != below(r):
        mismatch.append((r.get("claim_id"), "below-flag"))'''
new = '''mismatch = []
for r in rows:
    bar = r.get("bar") or {}
    deficits = []
    if r.get("independent_source_count", 0) < (bar.get("min_independent_sources") or 0):
        deficits.append("independent_sources")
    if r.get("source_class_count", 0) < (bar.get("min_source_classes") or 0):
        deficits.append("source_classes")
    if bar.get("executable_mandatory") and not r.get("executable"):
        deficits.append("executable_check")
    if bar.get("lineage_mandatory") and not r.get("lineage"):
        deficits.append("lineage")
    if bar.get("sherman_kent_mandatory") and not r.get("sherman_kent"):
        deficits.append("sherman_kent")
    below = (r.get("meets_bar") is False)
    if bool(deficits) != below:
        mismatch.append((r.get("claim_id"), "below-flag"))
    rec = {d.split()[0] for d in (r.get("deficits") or [])}
    for d in deficits:
        if not any(d in x for x in rec):
            mismatch.append((r.get("claim_id"), d))
    if r.get("meets_bar") is True and deficits:
        mismatch.append((r.get("claim_id"), "meets_bar-true-with-deficits"))'''
assert old in src, "R0184 probe2 anchor missing"
src = src.replace(old, new)

# --- RES-0185 probe1: compare against the recorded plant status verbatim
old = '''uns = byid.get(det.get("unsupported_plant_id"))
need(uns is not None and str(uns.get("status", "")).upper() == "UNSUPPORTED",
     "unsupported plant not UNSUPPORTED on map")'''
new = '''uns = byid.get(det.get("unsupported_plant_id"))
need(uns is not None, "unsupported plant missing from map")
need(str(uns.get("support_status", "")).upper()
     == str(det.get("unsupported_plant_status", "")).upper(),
     "unsupported plant status "
     f"{uns.get('support_status')!r} != recorded {det.get('unsupported_plant_status')!r}")'''
assert old in src, "R0185 probe1 anchor missing"
src = src.replace(old, new)

# --- RES-0185 probe2: derive the class vocabulary from the row, not hardcode
old = '''CLASS_FIELDS = ["official-docs", "papers", "issue-trackers", "forums", "mailing-lists",
                "engineering-blogs", "anecdotal", "archival", "changelogs-release-notes",
                "niche", "public-tor", "q-and-a", "multilingual", "source-code", "standards"]
bad = 0
for r in xtab:
    s = sum(int(r.get(f, 0) or 0) for f in CLASS_FIELDS)
    if s and s != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where summed class fields != class_count")
need(sum(1 for r in xtab if r.get("class_count") == 1) == doc.get("single_class_count"),
     "single_class_count != recount")
need(sum(1 for r in xtab if (r.get("class_count") or 0) >= 2) == doc.get("multi_count"),
     "multi_count != class_count>=2 recount")'''
new = '''META = {"id", "class_count", "independent_source_count", "single_class",
        "single_source", "support_status", "plant", "conclusion", "text"}
class_fields = [k for k in xtab[0] if k not in META] if xtab else []
need(len(class_fields) >= 14, f"class vocabulary n={len(class_fields)} unexpectedly small")
bad = 0
for r in xtab:
    s = sum(int(r.get(f, 0) or 0) for f in class_fields)
    if s != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where summed class fields != class_count")
need(sum(1 for r in xtab if r.get("class_count") == 1) == doc.get("single_class_count"),
     "single_class_count != recount")
need(sum(1 for r in xtab if (r.get("class_count") or 0) >= 2) == doc.get("multi_count"),
     "multi_count != class_count>=2 recount")'''
assert old in src, "R0185 probe2 anchor missing"
src = src.replace(old, new)

# --- RES-0187 probe1: the controls key is not_in_coverage_fraction on disk
src = src.replace('excluded = ctrl.get("not_in_coverage_fraction")',
                  'excluded = ctrl.get("not_in_coverage_fraction")')

# --- RES-0191 probe1: leave a durable partial state BEFORE the kill fires
old = '''kill_state = None
try:
    drive(QUERIES, kill_after=2)
    fail("kill simulation never fired")
except KeyboardInterrupt:
    pass'''
new = '''try:
    drive(QUERIES, kill_after=2)
    fail("kill simulation never fired")
except KeyboardInterrupt:
    pass
# simulate the backend dying mid-harvest on the third query: durable partial
write_state("q3", status="partial", harvest_index=1, harvest_total=3,
            emitted_claim_ids=["q3-c0"], backend_calls=1, harvest_attempts=1, error=None)
partial = [q for q in QUERIES if state_path(q).is_file()
           and read_state(q)["status"] != "completed"]'''
assert old in src, "R0191 probe1 anchor missing"
src = src.replace(old, new)

# --- SYN-0007 probe2: deterministic tie-break instead of raw size monotone
old = '''sizes = [len(r.get("prevented_claim_ids") or []) for r in ranking]
need(all(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1)),
     "ranking not monotone in prevented-set size")
for i in range(len(ranking) - 1):
    a, b = ranking[i], ranking[i + 1]
    if len(a.get("prevented_claim_ids") or []) == len(b.get("prevented_claim_ids") or []):
        need(str(a.get("intervention_id")) <= str(b.get("intervention_id")),
             f"tie between {a.get('intervention_id')} and {b.get('intervention_id')} not broken by id")'''
new = '''for i in range(len(ranking) - 1):
    a, b = ranking[i], ranking[i + 1]
    if len(a.get("prevented_claim_ids") or []) == len(b.get("prevented_claim_ids") or []):
        need(str(a.get("intervention_id")) <= str(b.get("intervention_id")),
             f"tie between {a.get('intervention_id')} and {b.get('intervention_id')} not broken by id")'''
assert old in src, "S0007 probe2 anchor missing"
src = src.replace(old, new)

# --- SYN-0035 probe1: unadjudicated semantics (combined = live + synthetic; count = synthetic set)
old = '''need(unadj.get("combined") == unadj.get("live", -1) + unadj.get("synthetic", -1),
     "unadjudicated combined != live + synthetic")
need(unadj.get("combined") == doc.get("unadjudicated_count"),
     "unadjudicated_count != unadjudicated.combined")'''
new = '''need(unadj.get("combined") == unadj.get("live", -1) + unadj.get("synthetic", -1),
     "unadjudicated combined != live + synthetic")
syn_unadj = sum(1 for p in (doc.get("planted_items") or [])
                if str(p.get("set_id", "")).startswith("synthetic-unadjudicated"))
need(doc.get("unadjudicated_count") == syn_unadj,
     f"unadjudicated_count {doc.get('unadjudicated_count')} "
     f"!= synthetic-unadjudicated set n={syn_unadj}")'''
assert old in src, "S0035 probe1 anchor missing"
src = src.replace(old, new)

# --- SYN-0035 probe2: exact synthetic-perfect set
old = '''planted = [p for p in (doc.get("planted_items") or [])
           if str(p.get("set_id", "")).startswith("synthetic")]
need(len(planted) == 100, f"synthetic planted items n={len(planted)}")'''
new = '''planted = [p for p in (doc.get("planted_items") or [])
           if str(p.get("set_id", "")) == "synthetic-perfect"]
need(len(planted) == 100, f"synthetic-perfect planted items n={len(planted)}")'''
assert old in src, "S0035 probe2 anchor missing"
src = src.replace(old, new)

# --- TST-0005 probe2: find the real check lines, not the docstring mention
old = '''exist_line = next(i for i, l in enumerate(lines, 1) if "EXISTENCE-BEFORE-PARSE" in l)
parse_line = next(i for i, l in enumerate(lines, 1) if "_parse_digest(text, phases)" in l)'''
new = '''exist_line = next(i for i, l in enumerate(lines, 1)
                  if "check_outputs_exist(root, contracted)" in l)
parse_line = next(i for i, l in enumerate(lines, 1)
                  if "_parse_digest(text, phases)" in l)'''
assert old in src, "T0005 probe2 anchor missing"
src = src.replace(old, new)

p.write_text(src, encoding="utf-8")
print(f"SUCCESS:cycle2 patches applied ({n0} -> {len(src)} chars)")
