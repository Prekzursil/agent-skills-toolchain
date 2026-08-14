"""Round 6 -- a gate for the defect class this lane keeps shipping: the RECEIPT is right
and the SENTENCE is wrong.

Across rounds 1-5 every adversarial finding against this lane was the same shape. The
audit of round 4 put it plainly: "the code was correct and the sentence was wider than
the evidence". Round 6 found two more by hand, both in SLOP-BUILD-R5.md:

  * line 33 published `histogram b=179 / c=3 / d-census=100 / d-zero=18` while the
    committed receipt says d-zero=23. The published parts sum to 300 against the
    "305 rows == 305 untracked" asserted in the SAME sentence, which also cites
    `partition_total: true`. The classifier was right; the transcription was not.
  * line 102 said "four of its SIX declared inputs" while the receipt says
    n_inputs_resolved: 12 and the doc's own table 20 lines earlier says "4 of 12".

Nothing mechanical was checking any of it. This probe is that check.

WHAT IT DOES
  Extracts two claim shapes from every SLOP-*.md in this directory and compares each one
  against the committed `_*.out.json` receipts in the same directory:

    KV        a backticked `key: value`      -> the leaf key must carry that value in a
                                                receipt (the one named on the line, if any)
    HISTOGRAM a line saying `histogram k=n / k=n ...` -> (a) the parts must SUM to the total
                                                asserted on the same line, and (b) each part
                                                must match the named receipt's histogram

USE-vs-MENTION IS THE HARD PART, and this lane has paid for it three times. A document that
QUOTES a superseded number is not asserting it -- SLOP-BUILD-R5.md:196 deliberately prints
`lint_rc: 1` and `lint_files_n: 0` as the output of a detector it is in the act of
declaring BROKEN. A naive comparator flags those as defects. They are the opposite: they
are the disclosure working. So a disagreement is a CANDIDATE, adjudicated in
`_r6_transcript_baseline.json` with a written reason -- the same baseline convention this
lane already ships in `published-commands-baseline.json`. An unbaselined disagreement is a
violation and exits non-zero.

CONTROLS -- both states, on fixtures held IN THIS FILE so they survive the doc being fixed.
A control that reads the live document would go silent the moment the defect is repaired,
and could no longer prove the gate can fire at all.

  T1 KNOWN-BROKEN. The verbatim pre-fix text of SLOP-BUILD-R5.md:33 must produce a
     histogram SUM-MISMATCH *and* a receipt DISAGREE. If T1 is silent the gate is inert
     and every clean result below is meaningless.
  T2 KNOWN-GOOD. The corrected text of the same line must produce neither.
  T3 NEGATIVE / liveness. A fresh uuid4 key must come back UNCHECKABLE, never a silent
     AGREE -- otherwise "no violations" could just mean "found nothing to look up". And a
     REAL key carrying a WRONG value must come back DISAGREE.
  T4 FAIL CLOSED. Zero claims extracted is a shape change, not a pass.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import uuid

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SR = "command-center/slop-report"
OUT = os.path.join(REPO, SR, "_r6_transcript.out.json")
BASELINE = os.path.join(REPO, SR, "_r6_transcript_baseline.json")

KV = re.compile(r"`(\"?)([A-Za-z_][A-Za-z0-9_-]*)\1:[ ]([^`]+)`")
# This lane's standing rule is that refuted wording is KEPT, struck through and annotated,
# never deleted. A preserved wrong number is a MENTION, not an assertion -- but it is still
# the wrong number sitting in the file, so the extractor would flag it forever. A claim on a
# line carrying this marker is recorded as PRESERVED-REFUTATION instead of a violation, and
# every one is counted in the receipt so the suppression can never be silent. Consequence
# for authors: the CORRECTED value must live on a line WITHOUT the marker, or it stops
# being checked. T5 proves the marker only works when it is actually present.
REFUTED_MARK = re.compile(r"\bREFUTED\b")
RECEIPT_REF = re.compile(r"`(_[A-Za-z0-9_.-]+\.out\.json)`")
HIST_LINE = re.compile(r"histogram\s+((?:[A-Za-z][A-Za-z0-9_-]*=\d+\s*/?\s*){3,})")
HIST_PAIR = re.compile(r"([A-Za-z][A-Za-z0-9_-]*)=(\d+)")
TOTAL = re.compile(r"(\d+)\s+rows\s*==\s*(\d+)")

# The verbatim pre-fix text of SLOP-BUILD-R5.md:33 and its corrected form. Held here on
# purpose: after the doc is repaired the live line can no longer demonstrate a firing gate.
T1_BROKEN = (
    "`_r5_reclassify.out.json` @ `5423de0f`: 305 rows == 305 untracked, "
    "`partition_total: true`, classifier's own 5 controls PASS, histogram "
    "b=179 / c=3 / d-census=100 / d-zero=18"
)
T2_FIXED = T1_BROKEN.replace("d-zero=18", "d-zero=23")


def norm(text: str):
    """Normalize a doc-side value into something comparable with JSON."""
    s = text.strip().strip("`").strip()
    s = s.split("(")[0].strip().rstrip(",.;")
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if s in ("[]", "[ ]"):
        return []
    try:
        return int(s)
    except ValueError:
        pass
    return s.strip('"')


def leaf_index(obj, into: dict) -> None:
    """Collect every leaf key -> set of values seen anywhere in one receipt."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and not (isinstance(v, list) and not v):
                leaf_index(v, into)
            into.setdefault(k, []).append(v)
    elif isinstance(obj, list):
        for v in obj:
            leaf_index(v, into)


def load_receipts() -> dict:
    out = {}
    for path in sorted(glob.glob(os.path.join(REPO, SR, "_*.out.json"))):
        # NEVER index this probe's own output. It records every claim it found, including
        # the `key` and `doc_value` of each one, so indexing it lets a document be
        # "confirmed" by the gate's own previous reading of that same document. That is a
        # false NEGATIVE -- the dangerous direction -- and it is self-referential besides.
        # Caught live: `key: value` in the round-6 report matched this file's own records.
        if os.path.basename(path) == os.path.basename(OUT):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        idx: dict = {}
        leaf_index(data, idx)
        out[os.path.basename(path)] = {"index": idx, "raw": data}
    return out


def match_equal(doc_val, receipt_vals: list) -> bool:
    for rv in receipt_vals:
        if rv == doc_val:
            return True
        if isinstance(rv, list) and doc_val == [] and not rv:
            return True
        if isinstance(rv, str) and isinstance(doc_val, str) and rv.strip() == doc_val:
            return True
    return False


def analyze_text(
    text: str, receipts: dict, doc: str = "<fixture>", base: int = 0
) -> list:
    """Return one verdict record per claim found in `text`."""
    claims = []
    for i, line in enumerate(text.splitlines(), start=1):
        refs = [r for r in RECEIPT_REF.findall(line) if r in receipts]
        preserved = bool(REFUTED_MARK.search(line))

        for _q, key, raw in KV.findall(line):
            doc_val = norm(raw)
            holders = [n for n, r in receipts.items() if key in r["index"]]
            scoped = [n for n in holders if n in refs] or holders
            if not holders:
                verdict = "UNCHECKABLE"
                seen = None
            else:
                agree = any(
                    match_equal(doc_val, receipts[n]["index"][key]) for n in scoped
                )
                verdict = "AGREE" if agree else "DISAGREE"
                seen = {n: receipts[n]["index"][key][:3] for n in scoped[:3]}
            claims.append(
                {
                    "doc": doc,
                    "line": base + i,
                    "kind": "KV",
                    "key": key,
                    "doc_value": doc_val,
                    "receipts_consulted": scoped[:3],
                    "receipt_values": seen,
                    "preserved_refutation": preserved,
                    "verdict": verdict,
                }
            )

        hm = HIST_LINE.search(line)
        if hm:
            parts = {k: int(v) for k, v in HIST_PAIR.findall(hm.group(1))}
            tm = TOTAL.search(line)
            total = int(tm.group(2)) if tm else None
            rec = {
                "doc": doc,
                "line": base + i,
                "kind": "HISTOGRAM",
                "parts": parts,
                "sum": sum(parts.values()),
                "asserted_total": total,
                "receipts_consulted": refs[:1],
                "preserved_refutation": preserved,
            }
            if total is not None and sum(parts.values()) != total:
                rec["verdict"] = "SUM-MISMATCH"
            else:
                rec["verdict"] = "SUM-OK"
            mism = {}
            for name in refs:
                hist = receipts[name]["raw"].get("histogram")
                if isinstance(hist, dict):
                    for k, v in parts.items():
                        if k in hist and hist[k] != v:
                            mism[k] = {"doc": v, "receipt": hist[k]}
            if mism:
                rec["receipt_mismatch"] = mism
                rec["verdict"] = (
                    "DISAGREE" if rec["verdict"] == "SUM-OK" else rec["verdict"]
                )
            claims.append(rec)
    return claims


def is_violation(c: dict) -> bool:
    if c.get("preserved_refutation"):
        return False
    return c["verdict"] in ("DISAGREE", "SUM-MISMATCH") or bool(
        c.get("receipt_mismatch")
    )


def main() -> int:
    receipts = load_receipts()
    baseline = {}
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as fh:
            for row in json.load(fh).get("adjudicated", []):
                baseline[(row["doc"], row["key"])] = row["reason"]

    live: list = []
    for path in sorted(glob.glob(os.path.join(REPO, SR, "SLOP-*.md"))):
        with open(path, encoding="utf-8") as fh:
            live += analyze_text(fh.read(), receipts, doc=os.path.basename(path))

    violations, baselined = [], []
    for c in live:
        if not is_violation(c):
            continue
        reason = baseline.get((c["doc"], c.get("key", "histogram")))
        if reason:
            c["baselined_reason"] = reason
            baselined.append(c)
        else:
            violations.append(c)

    # ---- controls -------------------------------------------------------
    t1 = analyze_text(T1_BROKEN, receipts, doc="<T1-known-broken>")
    t2 = analyze_text(T2_FIXED, receipts, doc="<T2-known-good>")
    nonce = "k" + uuid.uuid4().hex
    t3 = analyze_text(
        f"`{nonce}: true` and `partition_total: false` in `_r5_reclassify.out.json`",
        receipts,
        doc="<T3-negative>",
    )
    t3_map = {c["key"]: c["verdict"] for c in t3 if c["kind"] == "KV"}
    t5_marked = analyze_text(
        "~~" + T1_BROKEN + "~~ **REFUTED in round 6**", receipts, doc="<T5-marked>"
    )

    controls = {
        "T1_known_broken_fires_sum": any(c["verdict"] == "SUM-MISMATCH" for c in t1),
        "T1_known_broken_fires_receipt": any(c.get("receipt_mismatch") for c in t1),
        "T2_known_good_silent": not any(is_violation(c) for c in t2),
        "T3_uuid4_key_is_uncheckable": t3_map.get(nonce) == "UNCHECKABLE",
        "T3_real_key_wrong_value_disagrees": t3_map.get("partition_total")
        == "DISAGREE",
        "T4_fail_closed_claims_found": len(live) > 0,
        # T5 both-states on the suppression itself: the SAME broken text must violate
        # without the marker (T1, above) and stop violating with it. A marker that
        # suppressed unconditionally, or not at all, fails one of the two halves.
        "T5_refuted_marker_suppresses": not any(is_violation(c) for c in t5_marked),
        "T5_refuted_marker_needed": any(is_violation(c) for c in t1),
    }
    controls["PASS"] = all(controls.values())

    res = {
        "head": os.popen(f'git -C "{REPO}" rev-parse --short HEAD').read().strip(),
        "receipts_indexed": len(receipts),
        "docs_scanned": len(glob.glob(os.path.join(REPO, SR, "SLOP-*.md"))),
        "claims_found": len(live),
        "claims_by_verdict": {
            v: sum(1 for c in live if c["verdict"] == v)
            for v in {c["verdict"] for c in live}
        },
        "controls": controls,
        # Suppression is never silent: every claim excluded by the REFUTED marker is
        # counted here, so a reader can see how much the marker is carrying.
        "preserved_refutations": [
            {"doc": c["doc"], "line": c["line"], "key": c.get("key", "histogram")}
            for c in live
            if c.get("preserved_refutation")
        ],
        "violations": violations,
        "baselined": baselined,
        "all_claims": live,
    }
    ok = controls["PASS"] and not violations
    res["verdict"] = "TRANSCRIPTION-CLEAN" if ok else "TRANSCRIPTION-VIOLATIONS"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)

    summary = {k: v for k, v in res.items() if k != "all_claims"}
    json.dump(summary, sys.stdout, indent=1, sort_keys=True)
    print()
    print("SUCCESS:r6-transcript" if ok else "FAILED:r6-transcript see-violations")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
