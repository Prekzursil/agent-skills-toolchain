#!/usr/bin/env python3
"""Probe 1: recorded owner answer classifies ANSWERED; agent inference does not.

Both-states: stripping owner quotes from the control decisions file must flip
CTL-ANS-1 from ANSWERED to UNANSWERED. Live artifact must carry SUCCESS:BLD-0017
and every catalog owner_question exactly once.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import closure as C  # noqa: E402
import scenario as S  # noqa: E402
import validate_doc as V  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0017.json"
SCHEMA = REPO / "command-center/schema/owner-question-closure.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0017-probe1 {msg}")
    return 1


def main() -> int:
    fix = S.build_fixtures()
    result = C.analyze_controls(REPO, fix)
    verdicts = C.control_verdicts(result)
    print("control_verdicts", json.dumps(verdicts, sort_keys=True))
    for qid in ("CTL-ANS-1", "CTL-ANS-2", "CTL-ANS-3", "CTL-ANS-4", "CTL-ANS-5"):
        if verdicts.get(qid) != "ANSWERED":
            return fail(f"{qid} expected ANSWERED got {verdicts.get(qid)}")
        row = next(r for r in result["closure_table"] if r["id"] == qid)
        if not row.get("answer_anchor") or ":" not in str(row["answer_anchor"]):
            return fail(f"{qid} missing path:line owner anchor")
        if C.is_mere_ack(str(row.get("answer_quote") or "")):
            return fail(f"{qid} owner quote is mere acknowledgement")
    if verdicts.get("CTL-INF-1") != "UNANSWERED":
        return fail(f"CTL-INF-1 expected UNANSWERED got {verdicts.get('CTL-INF-1')}")
    inf = next(r for r in result["closure_table"] if r["id"] == "CTL-INF-1")
    if inf.get("reason") != "answered-only-by-agent-inference":
        return fail(f"CTL-INF-1 reason {inf.get('reason')}")
    if verdicts.get("CTL-ACK-1") != "UNANSWERED":
        return fail(f"CTL-ACK-1 expected UNANSWERED got {verdicts.get('CTL-ACK-1')}")
    if verdicts.get("CTL-OPEN-1") != "UNANSWERED":
        return fail(f"CTL-OPEN-1 expected UNANSWERED got {verdicts.get('CTL-OPEN-1')}")

    with tempfile.TemporaryDirectory(prefix="bld0017-p1-") as tmp:
        mutant = Path(tmp) / "controls"
        shutil.copytree(fix, mutant)
        md = (mutant / "OWNER-DECISIONS.md").read_text(encoding="utf-8")
        md = md.replace("Owner:", "Noted-by-scribe:")
        (mutant / "OWNER-DECISIONS.md").write_text(md, encoding="utf-8")
        flipped = C.analyze_controls(REPO, mutant)
        v2 = C.control_verdicts(flipped)
        print("stripped_owner_verdicts", json.dumps(v2, sort_keys=True))
        if v2.get("CTL-ANS-1") == "ANSWERED":
            return fail("CTL-ANS-1 still ANSWERED after owner quotes stripped (both-states silent)")
        if v2.get("CTL-INF-1") != "UNANSWERED":
            return fail("inference control flipped when only owner lines were stripped")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    raw = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0017" not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if not V.catalog_shim_present():
        return fail("catalog output_schema shim missing")
    try:
        V.validate_doc(doc)
    except Exception as exc:
        return fail(f"local schema {type(exc).__name__}: {exc}")

    live = C.analyze(REPO)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_ids = [str(q["id"]) for q in catalog.get("owner_questions") or [] if q.get("id")]
    table_ids = [r["id"] for r in doc.get("closure_table") or []]
    if sorted(table_ids) != sorted(catalog_ids + [i for i in live["packet_ids"] if i not in catalog_ids]):
        return fail("live closure_table ids != catalog+packet join")
    if len(table_ids) != len(set(table_ids)):
        return fail("duplicate rows in live closure_table")
    if len(catalog_ids) != live["catalog_count"]:
        return fail("catalog count drift between probe re-measure and analyzer")
    print(
        "live_catalog_count="
        + str(len(catalog_ids))
        + " table="
        + str(len(table_ids))
        + " answered="
        + str(live["answered_count"])
        + " unanswered="
        + str(live["unanswered_count"])
        + " packet_present="
        + str(live["sources"]["packet"]["present"])
        + " decisions_present="
        + str(live["sources"]["owner_decisions"]["present"])
    )
    print("SUCCESS:BLD-0017-probe1 owner-answer vs agent-inference both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
