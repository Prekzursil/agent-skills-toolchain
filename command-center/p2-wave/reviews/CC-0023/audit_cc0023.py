#!/usr/bin/env python3
"""CC-0023 independent reviewer audit: all-58 option-id ref disposition falsification.

Checks (independent re-derivation, does not trust the implementer's control script):
  1. Census refs (CC-0023-UNRESOLVED-REFS.json): every ref DEFERRED/PENDING or
     OWNER_ANSWERED with provenance=owner + timestamp + recorded answer.
  2. Ledger ref_states (OWNER-ADJUDICATION-LEDGER.json): same classification,
     cross-checked one-to-one against census ref_ids.
  3. OWNER-DECISIONS.md + ledger.answers: no recorded owner answers for OQ-CC23-*,
     and nothing that could be an agent-invented answer.
  4. Smuggling grep for non-owner resolution phrasing across disposition docs.
  5. Bucket composition vs upstream OPTION-ID-RESOLUTION.json census.
Writes raw evidence as it goes (write-as-you-go mandate).
"""

import io
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"C:/Users/Prekzursil/source/agent-skills-toolchain")
EVDIR = ROOT / "command-center/p2-wave/reviews/CC-0023"
EVDIR.mkdir(parents=True, exist_ok=True)
RAW = io.StringIO()


def log(s=""):
    print(s)
    RAW.write(s + "\n")


census = json.loads(
    (ROOT / "command-center/option-id/CC-0023-UNRESOLVED-REFS.json").read_text(
        encoding="utf-8"
    )
)
ledger = json.loads(
    (ROOT / "command-center/option-id/OWNER-ADJUDICATION-LEDGER.json").read_text(
        encoding="utf-8"
    )
)
upstream = json.loads(
    (ROOT / "command-center/OPTION-ID-RESOLUTION.json").read_text(encoding="utf-8")
)

log("=== CC-0023 independent all-58 disposition audit ===")
log("run_at=" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
log()

# ---- 1+2: per-ref classification over census and ledger ---------------------
DEFER_STATES = {"PENDING", "DEFERRED"}
OWNER_STATES = {"OWNER_ANSWERED", "ANSWERED"}


def classify(disposition, owner_answer, answered_at, provenance, source):
    d = (disposition or "").upper()
    if d in DEFER_STATES:
        ok = owner_answer is None and answered_at is None
        return (
            "DEFERRED" if ok else "IMPROPER",
            ""
            if ok
            else f"{source}: deferred-state but owner_answer={owner_answer!r} answered_at={answered_at!r}",
        )
    if d in OWNER_STATES:
        problems = []
        if owner_answer is None:
            problems.append("no owner_answer")
        if not answered_at:
            problems.append("no answered_at timestamp")
        if (provenance or "") != "owner":
            problems.append(f"provenance={provenance!r} != 'owner'")
        return ("OWNER_ANSWERED" if not problems else "IMPROPER", "; ".join(problems))
    return ("IMPROPER", f"{source}: unrecognized disposition {disposition!r}")


improper = []
counts = {"DEFERRED": 0, "OWNER_ANSWERED": 0, "IMPROPER": 0}
log("--- census refs (command-center/option-id/CC-0023-UNRESOLVED-REFS.json) ---")
census_ids = []
for r in census["refs"]:
    rid = r["ref_id"]
    census_ids.append(rid)
    cls, why = classify(
        r.get("disposition"),
        r.get("owner_answer"),
        r.get("answered_at"),
        "(census)",
        f"census {rid}",
    )
    counts[cls] += 1
    if cls == "IMPROPER":
        improper.append((rid, why))
    if cls != "DEFERRED" or rid in ("REF-001", "REF-058"):
        log(
            f"{rid} bucket={r.get('bucket_id')} q={r.get('question_id')} disp={r.get('disposition')!r} cls={cls} {why}"
        )
log(f"census: n={len(census_ids)} unique={len(set(census_ids))}")

log()
log(
    "--- ledger ref_states (command-center/option-id/OWNER-ADJUDICATION-LEDGER.json) ---"
)
ledger_states = ledger["ref_states"]
ledger_ids = []
for rid, st in sorted(ledger_states.items()):
    ledger_ids.append(rid)
    cls, why = classify(
        st.get("state"),
        st.get("owner_answer"),
        st.get("answered_at"),
        st.get("provenance"),
        f"ledger {rid}",
    )
    if cls == "IMPROPER":
        improper.append((rid, why))
    # deferred refs must carry impact + timestamp of deferral
    if cls == "DEFERRED" and (
        not st.get("impact") or not st.get("deferred_recorded_at")
    ):
        improper.append(
            (rid, f"ledger {rid}: DEFERRED without impact/deferred_recorded_at")
        )
    if rid in ("REF-001", "REF-058"):
        log(
            f"{rid} state={st.get('state')} provenance={st.get('provenance')!r} impact={'yes' if st.get('impact') else 'NO'}"
        )
log(f"ledger: n={len(ledger_ids)} unique={len(set(ledger_ids))}")
log(
    f"ledger declared counts: {json.dumps(ledger.get('counts'))} honesty: {json.dumps(ledger.get('honesty'))}"
)

# cross-set equality
expected_ids = {f"REF-{i:03d}" for i in range(1, 59)}
if set(census_ids) != expected_ids:
    improper.append(
        (
            "CENSUS-IDS",
            f"census ids != REF-001..058: symdiff={sorted(set(census_ids) ^ expected_ids)}",
        )
    )
if set(ledger_ids) != expected_ids:
    improper.append(
        (
            "LEDGER-IDS",
            f"ledger ids != REF-001..058: symdiff={sorted(set(ledger_ids) ^ expected_ids)}",
        )
    )
# per-id state consistency census vs ledger
for rid in sorted(expected_ids):
    cs = next(r for r in census["refs"] if r["ref_id"] == rid)
    ls = ledger_states.get(rid, {})
    c_cls, _ = classify(
        cs.get("disposition"),
        cs.get("owner_answer"),
        cs.get("answered_at"),
        "(census)",
        rid,
    )
    l_cls, _ = classify(
        ls.get("state"),
        ls.get("owner_answer"),
        ls.get("answered_at"),
        ls.get("provenance"),
        rid,
    )
    if c_cls != l_cls:
        improper.append((rid, f"census cls {c_cls} != ledger cls {l_cls}"))
    if cs.get("question_id") != ls.get("question_id"):
        improper.append(
            (
                rid,
                f"question_id mismatch census={cs.get('question_id')} ledger={ls.get('question_id')}",
            )
        )

# ---- 3: recorded owner answers must be zero; OWNER-DECISIONS.md inspection ---
log()
log("--- recorded owner answers ---")
roa = ledger.get("recorded_owner_answers", [])
answers = ledger.get("answers", {})
log(
    f"ledger.recorded_owner_answers: {len(roa)} entries; ledger.answers keys: {len(answers)}"
)
if roa or answers:
    improper.append(
        (
            "LEDGER-ANSWERS",
            f"non-empty recorded answers: {roa[:3]} / {list(answers)[:3]}",
        )
    )
dec_path = ROOT / "command-center/OWNER-DECISIONS.md"
dec_text = dec_path.read_text(encoding="utf-8")
oq_hits = [
    (i + 1, m.group(0))
    for i, line in enumerate(dec_text.splitlines())
    for m in [re.search(r"OQ-CC23-\d+", line)]
    if m
]
log(
    f"OWNER-DECISIONS.md: {len(dec_text.splitlines())} lines, OQ-CC23-* mentions: {len(oq_hits)} {oq_hits[:5]}"
)
ans_rows = [
    (i + 1, row)
    for i, row in enumerate(dec_text.splitlines())
    if re.search(r"OQ-CC23-\d+", row)
    and re.search(r"\bANSWERED\b", row)
    and "DEFERRED" not in row
]
log(
    f"OWNER-DECISIONS.md OQ-CC23 rows containing 'ANSWERED' (not DEFERRED): {len(ans_rows)}"
)
for a in ans_rows[:5]:
    log("  " + a[1].strip()[:160])
if ans_rows:
    improper.append(
        ("OWNER-DECISIONS", f"OQ-CC23 rows mentioning ANSWERED: {len(ans_rows)}")
    )
legacy_answered = [
    (i + 1, row)
    for i, row in enumerate(dec_text.splitlines())
    if re.match(r"^\s*\|\s*OQ-\d+\s*\|\s*ANSWERED", row)
]
log(
    f"OWNER-DECISIONS.md legacy OQ-1..N ANSWERED rows (pre-CC-0023 table): {len(legacy_answered)} — inert for CC-0023 unless cited"
)
bare_oq_cited = []
for t in [
    "command-center/option-id/CC-0023-UNRESOLVED-REFS.json",
    "command-center/option-id/OWNER-ADJUDICATION-LEDGER.json",
    "command-center/option-id/OWNER-ADJUDICATION-PACKET.md",
]:
    txt = (ROOT / t).read_text(encoding="utf-8")
    if re.search(r"OQ-(?!CC23-)\d+", txt):
        bare_oq_cited.append(t)
if bare_oq_cited:
    improper.append(
        (
            "LEGACY-OQ-CITED",
            f"disposition docs cite legacy OQ-N answers: {bare_oq_cited}",
        )
    )
else:
    log(
        "disposition docs (census/ledger/packet): zero bare OQ-N citations -> legacy answers never used as CC-0023 evidence"
    )
qpacket = (ROOT / "command-center/OWNER-QUESTION-PACKET.md").read_text(encoding="utf-8")
qp_oq = re.findall(r"OQ-CC23-\d+", qpacket)
log(
    f"OWNER-QUESTION-PACKET.md: {len(qpacket.splitlines())} lines, OQ-CC23 tokens: {len(qp_oq)} unique={len(set(qp_oq))}"
)

# ---- 4: smuggling grep ------------------------------------------------------
log()
log("--- smuggling grep (non-owner resolution phrasing) ---")
PATTERNS = [
    r"inferred",
    r"inferr",
    r"majority",
    r"consensus",
    r"likely\s+mean",
    r"most[- ]likely",
    r"we\s+interpret",
    r"interpret(?:ed|ing)?\s+as",
    r"llm[- ]judg",
    r"agent[- ]judg",
    r"agent[- ]majority",
    r"best[- ]guess",
    r"presum",
    r"assum",
    r"agent[- ]decid",
    r"resolved\s+as\s+(?:meaning|intended)",
    r"settled\s+by\s+(?:agent|llm|claude|gpt)",
]
targets = [
    "command-center/option-id/CC-0023-UNRESOLVED-REFS.json",
    "command-center/option-id/OWNER-ADJUDICATION-LEDGER.json",
    "command-center/option-id/OWNER-ADJUDICATION-PACKET.md",
    "command-center/OWNER-DECISIONS.md",
    "command-center/OWNER-QUESTION-PACKET.md",
]
grep_hits = 0
for t in targets:
    text = (ROOT / t).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        for p in PATTERNS:
            for m in re.finditer(p, line, re.I):
                grep_hits += 1
                log(f"{t}:{i}: [{m.group(0)}] {line.strip()[:150]}")
                break  # one hit per line per file is enough context
log(f"total grep hits: {grep_hits} (adjudicated below in review notes)")

# ---- 5: bucket composition vs upstream --------------------------------------
log()
log("--- bucket composition vs upstream OPTION-ID-RESOLUTION.json ---")
strict = upstream["9_residual_reference_census"]["strict_adjudication"]


def unsettled(f):
    return strict[f]["verdict"].get("UNSETTLED", 0)


expect = {
    "doc17-mentions": 10,  # loose classifier: 17-DECISION-LOG.md total=10 all MENTION-OF-FINDING; still_to_do refs=10
    "doc16-unsettled": unsettled("16-GRILL-QUEUE-PHASE2.md"),
    "doc18-blocks-unsettled": unsettled("18-OPEN-UNKNOWNS-AND-PROBES.md"),
    "doc19-unsettled": unsettled("19-SUBSTANCE-AUDIT-OPTIONS.md"),
    "diagrams-unsettled": unsettled(r"diagrams\07-option-dependency-map.md"),
    "wave1-unsettled": unsettled(r"wave1\REGISTER.md"),
}
# actual bucket ids may differ; match by source_file normalized to forward slashes
# (v1 of this detector compared backslash keys against forward-slash census values
#  -> false MISMATCH on diagrams/ and wave1/; fixed here)
actual = {}
for b in census["buckets"]:
    k = b["source_file"].replace("\\", "/")
    actual[k] = actual.get(k, 0) + b["count"]
src_expect = {
    "17-DECISION-LOG.md": 10,
    "16-GRILL-QUEUE-PHASE2.md": expect["doc16-unsettled"],
    "18-OPEN-UNKNOWNS-AND-PROBES.md": expect["doc18-blocks-unsettled"],
    "19-SUBSTANCE-AUDIT-OPTIONS.md": expect["doc19-unsettled"],
    "diagrams\\07-option-dependency-map.md": expect["diagrams-unsettled"],
    "wave1\\REGISTER.md": expect["wave1-unsettled"],
}
for sf, exp in src_expect.items():
    act = actual.get(sf.replace("\\", "/"))
    log(
        f"{sf}: upstream_expected={exp} census_bucket={act} {'OK' if act == exp else 'MISMATCH'}"
    )
    if act != exp:
        improper.append(("BUCKETS", f"{sf}: upstream {exp} != census {act}"))
# scratch bucket = 12 probe-script AMBIGUOUS refs (still_to_do 'assorted ... refs 12')
scratch_files = [
    "_p1floor_count.py",
    "_sa_conf2.py",
    "_sa_dump.py",
    "_sa_graph.json",
    "_sa_universe_recheck.py",
    "_verify_layerb.py",
    "_verify_layerb2.py",
    "_wfcat_exec.json",
]
loose = upstream["9_residual_reference_census"]["per_file_loose_classifier"]
scratch_sum = sum(
    loose[f]["by_class"].get("AMBIGUOUS", 0) for f in scratch_files if f in loose
)
scratch_bucket = next(
    (
        b["count"]
        for b in census["buckets"]
        if "scratch" in b["bucket_id"] or "probe" in b["bucket_id"]
    ),
    None,
)
log(
    f"scratch: upstream AMBIGUOUS sum={scratch_sum} census_bucket={scratch_bucket} {'OK' if scratch_bucket == scratch_sum == 12 else 'MISMATCH'}"
)
if scratch_bucket != scratch_sum or scratch_sum != 12:
    improper.append(
        ("BUCKETS", f"scratch: upstream {scratch_sum} vs census {scratch_bucket}")
    )
bsum = sum(b["count"] for b in census["buckets"])
log(
    f"bucket_sum={bsum} len(refs)={len(census['refs'])} declared requires_author_adjudication={census['requires_author_adjudication']}"
)
if not (bsum == len(census["refs"]) == census["requires_author_adjudication"] == 58):
    improper.append(
        (
            "ARITHMETIC",
            f"bucket_sum={bsum} refs={len(census['refs'])} declared={census['requires_author_adjudication']}",
        )
    )

# ---- verdict ----------------------------------------------------------------
log()
log("=== VERDICT ===")
log(
    f"census classified: DEFERRED={counts['DEFERRED']} OWNER_ANSWERED={counts['OWNER_ANSWERED']} IMPROPER={counts['IMPROPER']}"
)
log(
    f"ledger n={len(ledger_ids)}; recorded owner answers={len(roa)}; answers dict={len(answers)}"
)
log(f"improper entries ({len(improper)}):")
for rid, why in improper:
    log(f"  {rid}: {why}")
verdict = "PASS" if not improper else "FAIL"
log(
    f"VERDICT={verdict} (deferred={counts['DEFERRED'] + sum(1 for _ in range(0))} owner_answered={counts['OWNER_ANSWERED']} improper={len(improper)})"
)

out = EVDIR / "all58-disposition-audit.raw.txt"
out.write_text(RAW.getvalue(), encoding="utf-8")
print(f"\nwrote {out} ({out.stat().st_size} bytes)")
sys.exit(0 if verdict == "PASS" else 1)
