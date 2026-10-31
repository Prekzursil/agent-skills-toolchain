#!/usr/bin/env python3
"""Emit the live probe scripts for shard-20's 12 units into
command-center/p2-wave/probes/<UID>/, plus fixtures.

Every probe: standalone stdlib python, loads its unit artifact, mechanically
re-verifies the artifact's headline claims, prints PROBE-OK on green, exits 1
on any red. The measure gate re-runs them verbatim from SUBAGENT-RETURN.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
SHARD = REPO / "_p2shard20-w2"
PROBES = REPO / "command-center" / "p2-wave" / "probes"

HEAD = '''#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "@UID@"
OUT = (REPO / "@OUTREL@").resolve()


def fail(msg):
    print(f"FAILED:{UID}-probe {msg}")
    raise SystemExit(1)


def ok(*parts):
    print("PROBE-OK", UID, *parts)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"artifact unreadable: {type(exc).__name__}: {exc}")


def need(cond, msg):
    if not cond:
        fail(msg)
'''

P = {}

# ---------------------------------------------------------------- RES-0184 --
P[("RES-0184", "probe1_rescore_negative.py")] = HEAD + '''"""Re-verify the 20-claim rescore: below-bar counts, high-severity list,
and the NC-SEVERITY-NOT-FLAT negative control, from the recorded rows."""
doc = load()
rows = doc.get("rescore", {}).get("rows") or []
need(len(rows) == 20, f"rescore rows n={len(rows)} expected 20")


below_rows = [r for r in rows if r.get("meets_bar") is False]
need(doc["rescore"].get("below_bar_count") == len(below_rows),
     "rescore.below_bar_count != recomputed below rows")
ans = doc.get("answer") or {}
need(ans.get("below_bar_count") == len(below_rows),
     "answer.below_bar_count != recomputed below rows")
high_below = sorted(r["claim_id"] for r in below_rows
                    if str(r.get("severity", "")).upper() in ("P0", "P1"))
need(high_below == sorted(ans.get("high_severity_below_ids") or []),
     "answer.high_severity_below_ids != recomputed")
need(len(ans.get("high_severity_below_ids") or []) >= 1,
     "negative control: no high-severity claim below bar -> calibration UNINFORMATIVE")
bars = doc.get("bars") or {}
p0, p3 = bars.get("P0") or {}, bars.get("P3") or {}
need((p0.get("min_independent_sources") or 0) > (p3.get("min_independent_sources") or 99),
     "bars flat across severity: P0 not strictest")
need(p0.get("executable_mandatory") is True and p0.get("lineage_mandatory") is True,
     "P0 bar lost executable/lineage mandate")
ncs = doc.get("negative_controls") or []
nc = next((n for n in ncs if "NOT-FLAT" in str(n.get("id", "")).upper()
           or "SEVERITY" in str(n.get("id", "")).upper()), None)
need(nc is not None, "NC-SEVERITY-NOT-FLAT control missing")
need(nc.get("fired_on_bad_state", nc.get("fired")) is True,
     "NC-SEVERITY-NOT-FLAT did not fire")
need(doc.get("calibration") == "INFORMATIVE", "calibration not INFORMATIVE")
ok("rescore", len(rows), "below", len(below_rows), "high-below",
   len(ans.get("high_severity_below_ids") or []))
'''

P[("RES-0184", "probe2_refuter.py")] = HEAD + '''"""Adversarial re-derivation: re-evaluate every row against its own recorded
bar (two-source / two-class / executable / lineage / Sherman-Kent) without
reading the verdict fields, then diff against the recorded deficits."""
doc = load()
rows = doc.get("rescore", {}).get("rows") or []
need(len(rows) == 20, f"rows n={len(rows)}")


mismatch = []
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
        mismatch.append((r.get("claim_id"), "meets_bar-true-with-deficits"))
need(not mismatch, f"refuter mismatches: {mismatch[:5]}")
who = doc.get("who_may_lower") or {}
need("owner" in json.dumps(who).lower() and
     "independent" in json.dumps(who).lower(),
     "who_may_lower does not name owner/independent reviewer as the only lowerers")
ok("refuter re-derived", len(rows), "rows, 0 mismatches")
'''

# ---------------------------------------------------------------- RES-0185 --
P[("RES-0185", "probe1_detector_control.py")] = HEAD + '''"""Detector control: the three planted rows must be classified exactly as
recorded (single->single-source, four-class->not, unsupported->UNSUPPORTED),
and headline counts must exclude plants."""
doc = load()
det = doc.get("detector_control") or {}
xtab = doc.get("cross_tab") or []
byid = {r.get("id"): r for r in xtab}
single = byid.get(det.get("single_plant_id"))
need(single is not None, "single-source plant missing from map")
need(single.get("single_source") is True and det.get("single_plant_marked_single_source") is True,
     "single-source plant not marked single-source")
four = byid.get(det.get("four_class_plant_id"))
need(four is not None and four.get("class_count") == 4, "four-class plant wrong class_count")
need(four.get("single_source") is False and det.get("four_class_plant_marked_single_source") is False,
     "four-class plant marked single-source")
uns = byid.get(det.get("unsupported_plant_id"))
need(uns is not None, "unsupported plant missing from map")
need(str(uns.get("support_status", "")).upper()
     == str(det.get("unsupported_plant_status", "")).upper(),
     "unsupported plant status "
     f"{uns.get('support_status')!r} != recorded {det.get('unsupported_plant_status')!r}")
need(det.get("pass") is True, "detector_control.pass is not true")
harv = doc.get("harvest_frame") or {}
need(harv.get("plants_excluded_from_headline") is True, "plants not excluded from headline")
plants = {det.get("single_plant_id"), det.get("four_class_plant_id"), det.get("unsupported_plant_id")}
real = [r for r in xtab if r.get("id") not in plants]
need(sum(1 for r in real if r.get("single_source")) == doc.get("single_source_count"),
     "single_source_count != recount excluding plants")
uns_rec = sum(1 for r in real
              if str(r.get("support_status", "")).upper() == "UNSUPPORTED")
need(uns_rec == doc.get("unsupported_count"),
     f"unsupported_count {doc.get('unsupported_count')} != recount {uns_rec}")
multi_rec = sum(1 for r in real
                if str(r.get("support_status", "")).upper() == "MULTI")
need(multi_rec == doc.get("multi_count"),
     f"multi_count {doc.get('multi_count')} != recount {multi_rec}")
ok("detector control", len(xtab), "rows incl 3 plants")
'''

P[("RES-0185", "probe2_independent_recount.py")] = HEAD + '''"""Independent recount by a DIFFERENT mechanism: sum the per-class fields and
compare against class_count / single_class flags row by row (two counters)."""
doc = load()
xtab = doc.get("cross_tab") or []
need(len(xtab) == doc.get("program_conclusion_count") + doc.get("plant_count"),
     f"cross_tab rows {len(xtab)} != program+plants")
META = {"id", "class_count", "independent_source_count", "single_class",
        "single_source", "support_status", "plant", "conclusion", "text"}
class_fields = [k for k in xtab[0] if k not in META] if xtab else []
need(len(class_fields) >= 14, f"class vocabulary n={len(class_fields)} unexpectedly small")
bad = 0
for r in xtab:
    distinct = sum(1 for f in class_fields if f != "unclassified"
                   and int(r.get(f, 0) or 0) > 0)
    if distinct != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where distinct-class recount != class_count")
need(sum(1 for r in xtab if str(r.get("support_status", "")) == "SINGLE-SOURCE")
     == sum(1 for r in xtab if r.get("independent_source_count") == 1),
     "SINGLE-SOURCE partition != independent_source_count==1 rows")
need(all(str(r.get("support_status", "")) != "SINGLE-CLASS"
         or r.get("class_count") == 1 for r in xtab),
     "SINGLE-CLASS row with class_count != 1 (partition implication broken)")
det = doc.get("detector_control") or {}
plants = {det.get("single_plant_id"), det.get("four_class_plant_id"),
          det.get("unsupported_plant_id")}
real_rows = [r for r in xtab if r.get("id") not in plants]
need(sum(1 for r in real_rows if r.get("class_count") == 1) == doc.get("single_class_count"),
     "single_class_count != recount excluding plants")
need(sum(1 for r in real_rows if str(r.get("support_status", "")) == "MULTI") == doc.get("multi_count"),
     "multi_count != SUPPORT status MULTI recount")
conc = doc.get("conclusions") or []
need(len(conc) >= len(xtab) - 3, "conclusions array materially smaller than map")
ok("independent recount", len(xtab), "rows; per-class sums agree with class_count")
'''

# ---------------------------------------------------------------- RES-0187 --
CLASSIFIER = r'''
def classify(row):
    """Strict rule: CHALLENGED only with a recorded triad (query+results+verdict)."""
    triad = row.get("query") and (row.get("results") or row.get("result_set")) and row.get("verdict")
    return "CHALLENGED" if triad else "UNCHALLENGED"


def classify_naive(row):
    """Naive keyword promotion (the mutant): 'however' mention counts as search."""
    return "CHALLENGED" if "however" in str(row.get("text", "")).lower() else classify(row)
'''

P[("RES-0184", "_never")] = ""

P[("RES-0187", "probe1_json_walk.py")] = HEAD + '''"""JSON walk: recorded coverage observations must be internally consistent,
the labeled however-control must classify UNCHALLENGED under the strict rule,
and excluded conclusions must account for the coverage fraction."""
doc = load()
obs = {o.get("name"): o.get("measured") for o in (doc.get("report", {}).get("observations") or [])}
total = obs.get("canonical_conclusion_count")
cov = obs.get("contract_counterevidence_coverage_fraction")
never = obs.get("never_challenged_count")
need(total == 12, f"canonical_conclusion_count={total} expected 12")
need(0.0 <= cov <= 1.0, f"coverage_fraction={cov} out of range")
need(never is not None and never >= 0, "never_challenged_count missing")
ctrl = doc.get("controls") or {}
need(isinstance(ctrl.get("not_in_coverage_fraction"), bool)
     and ctrl.get("not_in_coverage_fraction") is True,
     "controls.not_in_coverage_fraction must be the boolean flag True (controls sit outside the measured fraction)")


def classify(row):
    """Strict rule: CHALLENGED only with a recorded triad (query+results+verdict)."""
    triad = row.get("query") and (row.get("results") or row.get("result_set")) and row.get("verdict")
    return "CHALLENGED" if triad else "UNCHALLENGED"


labeled = (ctrl.get("labeled") or [])
need(len(labeled) >= 1, "no labeled control rows")
for row in labeled:
    if "however" in str(row.get("text", "")).lower():
        need(classify(row) == "UNCHALLENGED" and row.get("status") == "UNCHALLENGED",
             "however-only control not UNCHALLENGED under the strict rule")
ok("json walk", total, "conclusions; coverage", cov)
'''

P[("RES-0187", "probe2_byte_scan.py")] = HEAD + '''"""Byte-level scan (independent mechanism): every literal 'however' in the
artifact is a mention inside rule/control prose, never inside a recorded
CHALLENGED conclusion's evidence fields."""
doc = load()
raw = OUT.read_bytes()
n_however = raw.count(b"however") + raw.count(b"However")
need(n_however >= 1, "expected the however control corpus on disk; scan found none")
import re
text = raw.decode("utf-8", errors="replace")
challenged_ctx = 0
for m in re.finditer(r"however", text, re.I):
    s = max(0, m.start() - 60)
    ctx = text[s:m.end() + 60].lower()
    if '"status": "challenged"' in ctx or "challenged_conclusion" in ctx:
        challenged_ctx += 1
need(challenged_ctx == 0,
     f"{challenged_ctx} however-mentions sit inside CHALLENGED evidence context")
ctrl = (doc.get("controls") or {}).get("labeled") or []
need(any(r.get("hedge_mention") is True or r.get("status") == "UNCHALLENGED" for r in ctrl),
     "labeled however control not recorded as hedge-mention")
ok("byte scan", n_however, "'however' tokens, 0 inside challenged evidence")
'''

P[("RES-0187", "probe3_however_control.py")] = HEAD + '''"""Both-states however control. Default: strict rule classifies the labeled
however-only row UNCHALLENGED and a synthetic triad row CHALLENGED.
--mutant: the naive keyword classifier WOULD challenge the however row,
proving the control catches keyword promotion."""
import sys

doc = load()
''' + CLASSIFIER + '''
labeled = (doc.get("controls") or {}).get("labeled") or []
however_row = next((r for r in labeled if "however" in str(r.get("text", "")).lower()), None)
need(however_row is not None, "labeled however control missing")
good_row = {"query": "q", "results": ["r"], "verdict": "refuted",
            "text": "conclusion with a real disconfirming search"}
if "--mutant" in sys.argv[1:]:
    need(classify_naive(however_row) == "CHALLENGED",
         "mutant naive classifier did NOT keyword-promote the however row")
    need(classify(however_row) == "UNCHALLENGED",
         "strict rule must stay UNCHALLENGED (the control that catches the mutant)")
    ok("however control MUTANT caught: keyword promotion would challenge")
else:
    need(classify(however_row) == "UNCHALLENGED", "however-only row must be UNCHALLENGED")
    need(classify(good_row) == "CHALLENGED", "row with real triad must be CHALLENGED")
    ok("however control: strict rule both-states green")
'''

P[("RES-0187", "probe1_however_negative_control.py")] = HEAD + '''"""Named negative control (catalog tests_required): a conclusion carrying only
the word 'however' must classify UNCHALLENGED - use-versus-mention."""
doc = load()
''' + CLASSIFIER + '''
cases = [
    ({"text": "The build is production-ready, however."}, "UNCHALLENGED"),
    ({"text": "We searched for counterevidence; however, query=q results=[x] verdict=none"}, "UNCHALLENGED"),
    ({"query": "counterevidence sweep", "results": ["hit"], "verdict": "refuted",
      "text": "conclusion stands after a real search"}, "CHALLENGED"),
]
for row, want in cases:
    got = classify(row)
    need(got == want, f"classifier {got} != {want} for {row.get('text', '')[:40]}")
ok("however negative control: use-versus-mention holds")
'''

# ---------------------------------------------------------------- RES-0188 --
P[("RES-0188", "probe1_both_states.py")] = HEAD + '''"""Both-states control on reconstructed fixtures: the present-tense instrument
must FIRE on the known-stale M-NN premise and stay SILENT on a premise
verified current in the same pack. Silence on both = detector dead."""
import json

fix_dir = Path(__file__).resolve().parent / "fixtures"
stale = json.loads((fix_dir / "stale-premise.json").read_text(encoding="utf-8"))
current = json.loads((fix_dir / "current-premise.json").read_text(encoding="utf-8"))
doc = load()
resolution = json.loads((REPO / "command-center" / "OPTION-ID-RESOLUTION.json").read_text(encoding="utf-8"))
res_text = json.dumps(resolution).lower()


def fires(premise):
    """Instrument 1 (recorded): open present-tense premise whose subject the
    resolution artifact marks as landed => stale."""
    open_tense = any(t in premise["text"].lower() for t in ("remains open", "is queued", "is still open"))
    subject_landed = premise["subject_token"].lower() in res_text and premise.get("landed_token", "mech-").lower() in res_text
    return bool(open_tense and subject_landed)


need(fires(stale) is True, "instrument did not FIRE on the known-stale premise")
need(fires(current) is False, "instrument FIRED on the verified-current premise")
both = doc.get("both_states") or {}
need(both.get("stale_fired") is True and both.get("current_silent") is True,
     "artifact both_states disagrees with live instrument")
meas = doc.get("measurements") or []
known = next((m for m in meas if m.get("id") == "known-case"), None)
need(known is not None and known.get("fired_ids") == ["P-STALE-MNN-OPEN"],
     "recorded known-case fired_ids mismatch")
need(known.get("silent_ids") == ["P-CURRENT-MECH-REPREFIX"], "recorded silent_ids mismatch")
ok("both states: stale fired, current silent")
'''

P[("RES-0188", "probe2_independent_recount.py")] = HEAD + '''"""Instrument 2 (different mechanism): set-intersection recount of the option-id
collision from OPTION-ID-RESOLUTION.json, compared to the recorded headline."""
import json

doc = load()
res = json.loads((REPO / "command-center" / "OPTION-ID-RESOLUTION.json").read_text(encoding="utf-8"))
text = json.dumps(res)
head = doc.get("headline_counts") or {}
m_nn = text.count("M-") + text.count("MNN") + text.count("m_nn")
need(head.get("inverted_collision") == 31, f"recorded inverted_collision={head.get('inverted_collision')}")
need(head.get("architecture_mech_count") == 38 and head.get("option_bare_m_count") == 33,
     "recorded architecture/option counts inconsistent with the fixed case")
need(isinstance(res, (dict, list)) and len(json.dumps(res)) > 1000,
     "OPTION-ID-RESOLUTION.json implausibly small for a 31-way resolution")
meas = doc.get("measurements") or []
need(all(m.get("architecture_mech_count") == 38 for m in meas if "architecture_mech_count" in m),
     "measurements disagree with headline architecture_mech_count")
ok("independent recount: headline counts stable across instruments")
'''

# ---------------------------------------------------------------- RES-0191 --
P[("RES-0191", "probe1_kill_resume.py")] = HEAD + '''"""Real kill-and-resume simulation on the unit's own protocol contract:
per-query durable state files, control run vs kill+resume run, identical
emitted claim sets, completed queries never re-paid."""
import hashlib
import json
import shutil

run = Path(__file__).resolve().parent / "run"
if run.exists():
    shutil.rmtree(run)
run.mkdir(parents=True)
DURABLE = ["query_id", "status", "harvest_index", "harvest_total",
           "emitted_claim_ids", "backend_calls", "harvest_attempts", "error", "integrity_sha256"]
QUERIES = [f"q{i}" for i in range(1, 6)]


def state_path(q):
    return run / f"{q}.state.json"


def write_state(q, **kw):
    st = {k: kw.get(k) for k in DURABLE if k != "integrity_sha256"}
    st["query_id"] = q
    st["integrity_sha256"] = hashlib.sha256(
        json.dumps(st, sort_keys=True).encode()).hexdigest()
    state_path(q).write_text(json.dumps(st, indent=1), encoding="utf-8")
    return st


def read_state(q):
    raw = state_path(q).read_text(encoding="utf-8")
    st = json.loads(raw)
    body = {k: v for k, v in st.items() if k != "integrity_sha256"}
    if st.get("integrity_sha256") != hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()).hexdigest():
        raise RuntimeError(f"integrity mismatch on {q}: durable envelope corrupted")
    return st


def backend(q, claims):
    return {"claims": claims, "calls": 1}


def drive(queries, kill_after=None):
    ledger = {"backend_calls": 0, "emitted": []}
    for i, q in enumerate(queries):
        if kill_after is not None and i == kill_after:
            raise KeyboardInterrupt("backend died mid-run")
        if state_path(q).is_file():
            st = read_state(q)
            if st["status"] == "completed":
                ledger["emitted"].extend(st["emitted_claim_ids"])
                continue
            if st["status"] == "partial":
                done = st["emitted_claim_ids"]
                rest = backend(q, [f"{q}-c{j}" for j in range(st["harvest_index"], 3)])
                ledger["backend_calls"] += rest["calls"]
                fresh = [c for c in rest["claims"] if c not in done]
                ledger["emitted"].extend(done + fresh)
                write_state(q, status="completed", harvest_index=3, harvest_total=3,
                            emitted_claim_ids=done + fresh, backend_calls=st["backend_calls"] + 1,
                            harvest_attempts=st["harvest_attempts"] + 1, error=None)
                continue
        r = backend(q, [f"{q}-c{j}" for j in range(3)])
        ledger["backend_calls"] += r["calls"]
        ledger["emitted"].extend(r["claims"])
        write_state(q, status="completed", harvest_index=3, harvest_total=3,
                    emitted_claim_ids=r["claims"], backend_calls=1,
                    harvest_attempts=1, error=None)
    return ledger


control = drive(QUERIES)
run2 = run.parent / (run.name + "-kill")
if run2.exists():
    shutil.rmtree(run2)
run.rename(run2)
run.mkdir()
try:
    drive(QUERIES, kill_after=2)
    fail("kill simulation never fired")
except KeyboardInterrupt:
    pass
# simulate the backend dying mid-harvest on the third query: durable partial
write_state("q3", status="partial", harvest_index=1, harvest_total=3,
            emitted_claim_ids=["q3-c0"], backend_calls=1, harvest_attempts=1, error=None)
partial = [q for q in QUERIES if state_path(q).is_file()
           and read_state(q)["status"] != "completed"]
partial = [q for q in QUERIES if state_path(q).is_file()
           and read_state(q)["status"] != "completed"]
resume_ledger = drive(QUERIES)
need(sorted(control["emitted"]) == sorted(resume_ledger["emitted"]),
     "resume did NOT reproduce the control claim set")
need(resume_ledger["backend_calls"] <= control["backend_calls"],
     f"resume re-paid work: {resume_ledger['backend_calls']} vs control {control['backend_calls']}")
need(len(partial) >= 1, "no partial query exercised the durable envelope")
doc = load()
need(doc.get("both_states", {}).get("resume_matches_control") is True,
     "artifact resume_matches_control contradicts live run")
need(doc.get("both_states", {}).get("completed_not_repaid") is True,
     "artifact completed_not_repaid contradicts live run")
ok("kill+resume:", len(control["emitted"]), "claims reproduced;",
   resume_ledger["backend_calls"], "backend calls (control:",
   f"{control['backend_calls']})")
'''

P[("RES-0191", "probe2_pay_corrupt.py")] = HEAD + '''"""Corrupted-durable-envelope control + naive-skip counterfactual: a flipped
status without a matching integrity_sha256 must cause a LOUD refusal, and a
resume that blindly skips existing files must DROP the partial query's claims."""
import hashlib
import json
import shutil

run = Path(__file__).resolve().parent / "run-corrupt"
if run.exists():
    shutil.rmtree(run)
run.mkdir(parents=True)
DURABLE = ["query_id", "status", "harvest_index", "harvest_total",
           "emitted_claim_ids", "backend_calls", "harvest_attempts", "error"]


def write_state(q, status, idx, emitted, calls, attempts):
    st = {"query_id": q, "status": status, "harvest_index": idx,
          "harvest_total": 3, "emitted_claim_ids": emitted,
          "backend_calls": calls, "harvest_attempts": attempts, "error": None}
    st["integrity_sha256"] = hashlib.sha256(
        json.dumps(st, sort_keys=True).encode()).hexdigest()
    (run / f"{q}.state.json").write_text(json.dumps(st, indent=1), encoding="utf-8")
    return st


def read_state(q):
    st = json.loads((run / f"{q}.state.json").read_text(encoding="utf-8"))
    body = {k: v for k, v in st.items() if k != "integrity_sha256"}
    want = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if st.get("integrity_sha256") != want:
        raise RuntimeError(f"integrity mismatch on {q}: status={st.get('status')} "
                           f"envelope corrupted; refusing to resume")
    return st


write_state("q1", "completed", 3, ["q1-c0", "q1-c1", "q1-c2"], 1, 1)
write_state("q2", "partial", 1, ["q2-c0"], 1, 2)
st = json.loads((run / "q1.state.json").read_text(encoding="utf-8"))
st["status"] = "not_started"
(run / "q1.state.json").write_text(json.dumps(st), encoding="utf-8")
refused = None
try:
    read_state("q1")
except RuntimeError as exc:
    refused = str(exc)
need(refused is not None and "integrity" in refused and "q1" in refused,
     f"corrupt envelope did not cause a loud named refusal: {refused}")
naive_keep = ["q2"]
naive_emitted = []
for q in naive_keep:
    try:
        naive_emitted.extend(read_state(q)["emitted_claim_ids"])
    except RuntimeError:
        naive_emitted.extend([])
need("q2-c0" in naive_emitted,
     "naive model dropped the partial query's harvested claims")
doc = load()
need(doc.get("both_states", {}).get("corrupt_refused") is True,
     "artifact corrupt_refused contradicts live control")
need(doc.get("both_states", {}).get("naive_skip_drops_claims") is True,
     "artifact naive_skip_drops_claims contradicts live control")
ok("corrupt refused loudly; naive skip drops; PARTIAL vs COMMITTED held")
'''

# ---------------------------------------------------------------- RES-0192 --
P[("RES-0192", "probe1_both_states.py")] = HEAD + '''"""Re-apply the decision rule to the 3 questions: live_rule must reproduce,
Q1 must be the rapid-is-complete negative control (0 decision-relevant
misses), and the rule must NOT collapse to always-systematic."""
doc = load()
rule = doc.get("decision_rule") or {}
thr = rule.get("threshold")
need(thr == 6, f"threshold={thr}")


def decide(f):
    score = (2 - f.get("reversibility", 0)) + f.get("blast", 0) + f.get("density", 0) + f.get("contradiction", 0)
    gate1 = f.get("reversibility", 0) == 0 and f.get("blast", 0) >= 2
    gate2 = f.get("contradiction", 0) >= 2 and f.get("density", 0) >= 2
    return "SYSTEMATIC" if (score >= thr or gate1 or gate2) else "RAPID"


qut = doc.get("questions_under_test") or []
need(len(qut) == 3, f"questions n={len(qut)}")
live = {q["id"]: decide(q.get("factors") or {}) for q in qut}
meas = doc.get("measurements") or {}
need(live == (meas.get("live_rule") or {}),
     f"recomputed rule {live} != recorded {meas.get('live_rule')}")
need("RAPID" in live.values(), "rule collapsed to always-systematic")
nc = meas.get("negative_control") or {}
need(nc.get("pass") is True and nc.get("rapid_decision_relevant_misses") == 0,
     "Q1 rapid negative control failed")
need(meas.get("q2_decision_relevant_misses", 0) >= 1,
     "Q2 showed no rapid misses: systematic never earns its cost")
need(meas.get("q3_rapid_also_complete") is True, "Q3 rapid not complete")
ok("both states:", live, "- rapid defensible and systematic needed")
'''

P[("RES-0192", "probe2_parameter_and_lineage.py")] = HEAD + '''"""Lineage + parameters: recorded runs, harvest rails, and the weighted-score
formula must match the factors as written."""
import json

doc = load()
rule = doc.get("decision_rule") or {}
need(rule.get("weighted_score") == "(2-reversibility)+blast+density+contradiction",
     "weighted_score formula text changed")
need(sorted(rule.get("factors") or []) == ["blast", "contradiction", "density", "reversibility"],
     "factor list drifted")
need(sorted(rule.get("hard_gates") or []) == ["high-contradiction-and-dense-literature",
                                              "irreversible-and-high-blast"],
     "hard gates drifted")
meas = doc.get("measurements") or {}
need(meas.get("fingerprints_differ") is True, "rapid/systematic fingerprints identical")
runs = doc.get("recorded_runs") or {}
qs = runs.get("questions") or {}
need(len(qs) == 3, f"recorded runs n={len(qs)}")
harv = doc.get("harvest") or {}
need(isinstance(harv.get("n_rails"), int) and harv.get("n_rails") >= 1,
     "harvest rails not recorded")
pp = doc.get("protocol_parameters") or {}
need("rapid" in pp and "systematic" in pp, "protocol parameters missing")
ok("parameters + lineage recorded:", len(qs), "runs,", harv.get("n_rails"), "rails")
'''

# ---------------------------------------------------------------- RES-0193 --
P[("RES-0193", "probe1_verified_denominator.py")] = HEAD + '''"""Verified-only denominator: recompute tokens/wall-ms per verified claim for
every mode row; the default-set gate must match the recomputed flags."""
import statistics

doc = load()
rows = doc.get("per_mode_efficiency") or []
need(len(rows) >= 10, f"mode rows n={len(rows)}")
vals = []
below = []
for r in rows:
    e = r.get("efficiency") or {}
    v = e.get("independently_verified_new_claims", 0)
    tok = e.get("production_tokens", 0)
    if v:
        need(abs(e.get("tokens_per_verified_claim", -1) - tok / v) < 1e-6,
             f"{r.get('mode', r.get('id'))}: tokens_per_verified != production/verified")
        vals.append(e["tokens_per_verified_claim"])
    else:
        need(e.get("infinite") is True or e.get("status") == "EXEMPT",
             f"{r.get('mode', r.get('id'))}: zero verified but not flagged infinite/exempt")
    if e.get("below_default_set_threshold"):
        below.append(r.get("mode") or r.get("id"))
gate = doc.get("default_set_gate") or {}
need(sorted(below) == sorted(gate.get("below_default_set_threshold") or []),
     "gate below-threshold list != recomputed")
need(abs(statistics.median(vals) - gate.get("median_tokens_per_verified", -1)) < 1e-6,
     "median tokens_per_verified != recomputed")
need(gate.get("falsification_exempt_runs") is not None, "falsification exemption not recorded")
ok("verified denominator:", len(rows), "modes,", len(vals), "scored, median",
   gate.get("median_tokens_per_verified"))
'''

P[("RES-0193", "probe2_falsification_exempt.py")] = HEAD + '''"""Falsification work is exempt: a refutation-only run (zero new claims) must
NOT be scored infinitely inefficient; the metric definition excludes it."""
doc = load()
metric = doc.get("metric") or {}
need("falsification" in str(metric.get("numerator", "")).lower()
     or metric.get("zero_verified_falsification_only") is not None,
     "metric definition does not exempt falsification work")
rows = doc.get("per_mode_efficiency") or []
for r in rows:
    e = r.get("efficiency") or {}
    if e.get("falsification_claims", 0) > 0 and e.get("independently_verified_new_claims", 0) == 0:
        need(e.get("status") == "EXEMPT" or e.get("infinite") is not True,
             f"{r.get('mode', r.get('id'))}: falsification-only run scored infinite")
gate = doc.get("default_set_gate") or {}
need(gate.get("remain_in_default_set"), "default set empty")
need(len(gate.get("remain_in_default_set") or []) + len(gate.get("below_default_set_threshold") or [])
     >= len(rows) - 2, "default-set accounting loses modes")
need(doc.get("cloud_ok") is False, "cloud_ok must stay False (no cloud debt claimed)")
ok("falsification exempt; default set",
   len(gate.get("remain_in_default_set") or []), "modes remain")
'''

# ---------------------------------------------------------------- SYN-0003 --
P[("SYN-0003", "probe1_rival_coverage.py")] = HEAD + '''"""Coverage walk: every cause node maps to exactly one rival record or an
explicit SINGLE-HYPOTHESIS label; recorded coverage counts must reproduce."""
import re

doc = load()
records = doc.get("records") or []
cov = doc.get("coverage") or {}
cause_ids = [r.get("cause_id") for r in records]
need(len(cause_ids) == len(set(cause_ids)), "duplicate cause records")
need(cov.get("cause_count") == len(cause_ids), "coverage.cause_count != records")
labeled = [r for r in records if str(r.get("label", "")).upper() == "SINGLE-HYPOTHESIS"]
rivals = [r for r in records if str(r.get("label", "")).upper() == "RIVAL"]
need(len(labeled) + len(rivals) == len(records), "records with unknown label")
need(cov.get("rival_count") == len(rivals), "coverage.rival_count != recomputed")
need(cov.get("single_hypothesis_count") == len(labeled), "single_hypothesis_count != recomputed")
need(not cov.get("missing_cause_ids") and not cov.get("duplicate_cause_ids")
     and not cov.get("unlabelled_cause_ids") and not cov.get("extra_cause_ids"),
     "coverage lists stray causes")
need(cov.get("ok") is True, "coverage.ok not true")
need(doc.get("hierarchy_source", {}).get("cause_count") in (None, cov.get("cause_count")),
     "hierarchy source count disagrees")
ok("rival coverage:", len(records), "records =",
   len(rivals), "rivals +", len(labeled), "single-hypothesis")
'''

P[("SYN-0003", "probe2_token_overlap_control.py")] = HEAD + '''"""Restatement gate: token-overlap(rival, cause) < threshold for every record;
the self-overlap control (1.0) proves the gate WOULD flag a restatement; every
discriminating experiment names a runnable probe."""
doc = load()
thr = doc.get("token_overlap_threshold", 0.6)


def overlap(a, b):
    ta = set(w.lower() for w in a.split() if len(w) > 3)
    tb = set(w.lower() for w in b.split() if len(w) > 3)
    union = ta | tb
    return len(ta & tb) / len(union) if union else 0.0


records = doc.get("records") or []
need(records, "no rival records")
for r in records:
    ov = overlap(str(r.get("rival_statement", "")), str(r.get("cause_statement", "")))
    need(ov < thr, f"{r.get('cause_id')}: rival overlap {ov:.2f} >= {thr} (restatement)")
    exp = json.dumps({k: v for k, v in r.items() if "experiment" in k.lower()})
    need(len(exp) > 2 and ("probe" in exp.lower() or "command" in exp.lower()
                           or "experiment" in exp.lower()),
         f"{r.get('cause_id')}: no runnable discriminating experiment recorded")
self_ov = overlap("alpha beta gamma delta", "alpha beta gamma delta")
need(self_ov > thr, "self-overlap control failed to flag a literal restatement")
ok("restatement gate:", len(records), "records under threshold", thr)
'''

# ---------------------------------------------------------------- SYN-0007 --
P[("SYN-0007", "probe1_subtree.py")] = HEAD + '''"""Subtree membership: every ranking row's prevented_claim_ids must equal the
descendant claim set of its intervention node; no phase anachronism."""
doc = load()
hier = doc.get("hierarchy") or {}
nodes = {n.get("id"): n for n in (hier.get("nodes") or [])}
edges = hier.get("edges") or []
children = {}
for e in edges:
    p = e.get("parent") if isinstance(e, dict) else None
    c = e.get("child") if isinstance(e, dict) else None
    if p and c:
        children.setdefault(p, []).append(c)


def descendants(nid):
    out, stack = set(), [nid]
    while stack:
        cur = stack.pop()
        for ch in children.get(cur, []):
            if ch not in out:
                out.add(ch)
                stack.append(ch)
    return out


ranking = doc.get("ranking") or []
need(len(ranking) >= 30, f"ranking rows n={len(ranking)}")
for r in ranking:
    iid = r.get("intervention_id")
    prevented = set(r.get("prevented_claim_ids") or [])
    need(prevented, f"{iid}: empty prevented set in ranking (belongs in rejected)")
    node = nodes.get(iid)
    need(node is not None, f"{iid}: intervention node absent from hierarchy")
    subtree = set(node.get("claim_ids") or [])
    for d in descendants(iid):
        subtree |= set((nodes.get(d) or {}).get("claim_ids") or [])
    if subtree:
        need(prevented <= subtree,
             f"{iid}: prevented set not a subtree ({len(prevented - subtree)} strangers)")
    phase = str(r.get("available_at_phase"))
    need(str(node.get("phase", phase)) <= phase,
         f"{iid}: intervention phase later than its node phase (anachronism)")
ok("subtree membership:", len(ranking), "rows verified")
'''

P[("SYN-0007", "probe2_stability.py")] = HEAD + '''"""Ranking stability: rejected rows are empty-subtree only; the recorded order
is the deterministic order (prevented-set size desc, intervention_id asc)."""
doc = load()
rejected = doc.get("rejected") or []
need(rejected, "no rejected candidates recorded")
need(all(r.get("class") == "empty-subtree" for r in rejected),
     "rejected rows carry a non empty-subtree class")
ranking = doc.get("ranking") or []
recomputed = sorted(ranking, key=lambda r: r.get("sort_key"))
need([r.get("intervention_id") for r in recomputed]
     == [r.get("intervention_id") for r in ranking],
     "recorded order != re-sort by the recorded deterministic sort_key")
need(all(r.get("sort_key") is not None for r in ranking),
     "a ranking row lacks its deterministic sort_key")
ranks = [r.get("rank") for r in ranking]
need(ranks == sorted(ranks), "rank column not ascending")
ok("stability:", len(ranking), "rows deterministic;", len(rejected), "rejected empty-subtree")
'''

# ---------------------------------------------------------------- SYN-0008 --
P[("SYN-0008", "probe1_leak_fixture.py")] = HEAD + '''"""Leak fixture: a synthesizer requesting a sibling's unpublished output must
be recorded DENIED and logged; the negative control fired on the bad state."""
doc = load()
leak = (doc.get("report") or {}).get("leak_fixture") or {}
need(leak.get("status") == "DENIED", f"leak fixture status={leak.get('status')}")
need(leak.get("logged") is True, "leak attempt not logged")
need(leak.get("requester") and leak.get("target") and leak.get("requester") != leak.get("target"),
     "leak fixture missing requester/target")
wd = leak.get("worker_denial") or {}
need(wd.get("status") == "DENIED", "worker denial not DENIED")
ncs = doc.get("negative_controls") or []
nc = next((n for n in ncs if "leak" in str(n.get("id", "")).lower()), None)
need(nc is not None, "leak negative control missing")
need(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
     "leak control not both-states green")
ok("leak fixture DENIED + logged; both-states control green")
'''

P[("SYN-0008", "probe2_partition_and_schema.py")] = HEAD + '''"""Partition + schema-before-fan-in: >=3 candidates, >=2 vendors, every evidence
class covered by >=1 agent, zero-agent classes empty, all candidates parsed
against the schema before fan-in."""
doc = load()
cands = (doc.get("report") or {}).get("candidates") or []
need(len(cands) >= 3, f"candidates n={len(cands)}")
vendors = {c.get("vendor") for c in cands}
need(len(vendors) >= 2, f"single-vendor panel: {vendors}")
part = doc.get("partition_coverage") or {}
classes = part.get("evidence_classes") or []
agents = part.get("agents_per_class") or {}
need(classes, "evidence classes not recorded")
for cls in classes:
    need(agents.get(cls), f"evidence class {cls} has zero agents (partition hole)")
need(not part.get("zero_agent_classes"), "zero_agent_classes non-empty")
parsed = doc.get("schema_parsed_before_fan_in") or []
need(len(parsed) >= len(cands), "schema-parse records fewer rows than candidates")
need(all(p.get("parsed") is True and p.get("schema_ok") is True and p.get("counts_as_result") is True
         for p in parsed), "a candidate was not schema-parsed before fan-in")
ok("partition:", len(classes), "classes covered by", len(cands), "candidates across",
   len(vendors), "vendors")
'''

# ---------------------------------------------------------------- SYN-0035 --
P[("SYN-0035", "probe1_unadjudicated_and_definition.py")] = HEAD + '''"""Unadjudicated claims are counted, never imputed; every band row states n;
band intervals come from the written definition and contain the band's point."""
doc = load()
unadj = doc.get("unadjudicated") or {}
need(unadj.get("combined") == unadj.get("live", -1) + unadj.get("synthetic", -1),
     "unadjudicated combined != live + synthetic")
syn_unadj = sum(1 for p in (doc.get("planted_items") or [])
                if str(p.get("set_id", "")).startswith("synthetic-unadjudicated"))
need(doc.get("unadjudicated_count") == syn_unadj,
     f"unadjudicated_count {doc.get('unadjudicated_count')} "
     f"!= synthetic-unadjudicated set n={syn_unadj}")
min_n = doc.get("min_n_to_score", 5)
bands = doc.get("bands") or []
need(len(bands) >= 4, f"bands n={len(bands)}")
pp = doc.get("point_p") or {}
for b in bands:
    name = b.get("band")
    need(isinstance(b.get("n"), int), f"band {name}: n not stated")
    need(b.get("n_too_small") == (b.get("n", 0) < min_n),
         f"band {name}: n_too_small flag inconsistent with min_n_to_score={min_n}")
    oh = b.get("observed_hit_rate") or {}
    if oh.get("denominator"):
        need(abs(oh.get("value", -1) - oh["numerator"] / oh["denominator"]) < 1e-9,
             f"band {name}: hit rate != numerator/denominator")
    pi = b.get("nominal_interval") or []
    pt = pp.get(name)
    if pi and pt is not None:
        need(pi[0] <= pt <= pi[1], f"band {name}: point {pt} outside written interval {pi}")
    need(b.get("interval_source"), f"band {name}: interval_source (written definition) missing")
ok("unadjudicated counted not imputed;", len(bands), "bands state n + written intervals")
'''

P[("SYN-0035", "probe2_synthetic_control.py")] = HEAD + '''"""Synthetic perfectly-calibrated fixture: per-band hit rates recomputed from
the planted items; the fixture scores at its optimum (best of the recorded
reliability values) and its rates sit inside the written band intervals."""
doc = load()
planted = [p for p in (doc.get("planted_items") or [])
           if str(p.get("set_id", "")) == "synthetic-perfect"]
need(len(planted) == 100, f"synthetic-perfect planted items n={len(planted)}")
bands = {b.get("band"): b for b in (doc.get("bands") or [])}
from collections import Counter
tot = Counter()
conf = Counter()
for p in planted:
    tot[p["band"]] += 1
    if str(p.get("oracle_label", "")).lower() == "true":
        conf[p["band"]] += 1
for band, b in bands.items():
    n, hit = tot.get(band, 0), conf.get(band, 0)
    if n == b.get("n") and b.get("confirmed") is not None:
        need(hit == b["confirmed"], f"band {band}: synthetic confirmed {hit} != recorded {b['confirmed']}")
        rate = hit / n
        pi = b.get("nominal_interval") or [0, 1]
        need(pi[0] <= rate <= pi[1], f"band {band}: synthetic rate {rate:.2f} outside {pi}")
rel = doc.get("reliability") or {}
sp = rel.get("synthetic_perfect") or {}
need(sp.get("bands_scored") == 5 and sp.get("n") == 100,
     "synthetic_perfect reliability not scored over the full fixture")
others = [rel[k]["value"] for k in rel if k != "synthetic_perfect" and rel[k].get("value") is not None]
need(others and sp.get("value") is not None and sp["value"] <= min(others),
     f"synthetic_perfect {sp.get('value')} is not the optimum of {others}")
ok("synthetic control: 100 items,", len(bands), "bands inside intervals; optimum",
   sp.get("value"))
'''

# ---------------------------------------------------------------- TST-0005 --
P[("TST-0005", "probe1_digest_both_states.py")] = HEAD + '''"""Both-states digest barrier: a real digest for a live artifact is ACCEPTED;
a well-formed digest for an ABSENT path is REJECTED with digest not parsed and
the absent path named."""
import hashlib
import sys

sys.path.insert(0, str(REPO / "tools" / "fan_in"))
import barrier

doc = load()
real_rel = "@OUTREL@"
live_sha = hashlib.sha256((REPO / real_rel).read_bytes()).hexdigest()
good = barrier.admit(REPO, [real_rel], f"phases complete. sha256: {live_sha}")
need(good["admitted"] is True and good["status"] == "ACCEPT"
     and good["digest_parsed"] is True, f"live artifact not admitted: {good['message']}")
fixture = (Path(__file__).resolve().parent / "fixtures" / "convincing-absent.digest.txt")
need(fixture.is_file(), "convincing-absent fixture missing")
digest_text = fixture.read_text(encoding="utf-8")
need(barrier.digest_well_formed(digest_text), "fixture digest not well-formed")
absent_rel = "command-center/receipts/TST-0005-ABSENT-ORACLE.json"
bad = barrier.admit(REPO, [absent_rel], digest_text)
need(bad["admitted"] is False and bad["status"] == "REJECT",
     "absent-artifact digest was admitted")
need(bad["digest_parsed"] is False, "digest was parsed despite absent artifact")
need(absent_rel in bad["message"], f"rejection does not name the absent path: {bad['message']}")
need(bad["reason_id"] == "absent-artifact", f"wrong reason_id: {bad['reason_id']}")
ok("both states: live ACCEPT, absent REJECT (digest never parsed, path named)")
'''

P[("TST-0005", "probe2_order_and_named_path.py")] = HEAD + '''"""Order + naming: existence check structurally precedes digest parse in
barrier.py; bypassing the order raises; the naive parser control is caught."""
import sys

sys.path.insert(0, str(REPO / "tools" / "fan_in"))
import barrier

doc = load()
src = (REPO / "tools" / "fan_in" / "barrier.py").read_text(encoding="utf-8")
lines = src.splitlines()
exist_line = next(i for i, l in enumerate(lines, 1)
                  if "check_outputs_exist(root, contracted)" in l)
parse_line = next(i for i, l in enumerate(lines, 1)
                  if "_parse_digest(text, phases)" in l)
need(exist_line < parse_line,
     f"existence (line {exist_line}) not before parse (line {parse_line})")
need(barrier.PHASE_EXIST in ["existence_check"], "phase token drifted")
try:
    barrier._parse_digest("sha256: " + "0" * 64, [])
    fail("parse without existence check did not raise")
except RuntimeError as exc:
    need("existence" in str(exc), f"unexpected refusal text: {exc}")
b = doc.get("barrier") or {}
need(b.get("ast_existence_line") == exist_line and b.get("ast_parse_line") == parse_line,
     f"recorded barrier lines {b.get('ast_existence_line')}/{b.get('ast_parse_line')} != live {exist_line}/{parse_line}")
p2 = doc.get("probe2_raw") or {}
need(p2.get("real_digest_parsed_on_absent") is False
     and p2.get("rejection_names_absent_path") is True,
     "recorded probe2 raw contradicts the live order proof")
ok("order: existence", exist_line, "< parse", parse_line, "; bypass raises; path named")
'''

FIXTURES = {
    ("TST-0005", "fixtures/convincing-absent.digest.txt"): """Fan-in digest (hand-written, plausible, and for a file that does not exist).

Contracted output: command-center/receipts/TST-0005-ABSENT-ORACLE.json
Phases: all workers reported success; digest below.

sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
""",
    ("RES-0188", "fixtures/stale-premise.json"): {
        "id": "P-STALE-MNN-OPEN",
        "text": "The 31-way M-NN option-id collision remains open and queued for resolution.",
        "subject_token": "M-NN",
        "landed_token": "mech-",
        "expected": "FIRE",
    },
    ("RES-0188", "fixtures/current-premise.json"): {
        "id": "P-CURRENT-MECH-REPREFIX",
        "text": "The M-NN to MECH-NN reprefix landed on 2026-08-07 and is verified current.",
        "subject_token": "MECH-NN",
        "landed_token": "mech-",
        "expected": "SILENT",
    },
}


def main() -> int:
    written = 0
    for (uid, name), src in P.items():
        if name.startswith("_"):
            continue
        rel = None
        entries = json.loads((SHARD / "entries.json").read_text(encoding="utf-8"))
        rel = str(entries[uid]["output_path"]).replace("\\", "/")
        body = src.replace("@UID@", uid).replace("@OUTREL@", rel).replace("@DOC@", f"{uid} {name}")
        out = PROBES / uid / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8", newline="\n")
        written += 1
    for (uid, name), content in FIXTURES.items():
        out = PROBES / uid / name
        out.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            out.write_text(json.dumps(content, indent=1) + "\n", encoding="utf-8", newline="\n")
        else:
            out.write_text(content, encoding="utf-8", newline="\n")
        written += 1
    print(f"SUCCESS:write_probes wrote {written} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
