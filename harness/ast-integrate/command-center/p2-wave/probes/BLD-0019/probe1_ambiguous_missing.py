#!/usr/bin/env python3
"""Probe 1: dual disposition -> AMBIGUOUS; planted absent id -> MISSING."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from closer import close  # noqa: E402
from sources import CTRL_DUAL, CTRL_MISSING  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0019.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0019-probe1 {msg}")
    return 1


def main() -> int:
    result = close()
    by_id = {r["id"]: r for r in result["rows"]}
    if len(by_id) != len(result["rows"]):
        return fail("closer silently collapsed duplicate ids")

    dual = by_id.get(CTRL_DUAL)
    if dual is None:
        return fail(f"{CTRL_DUAL} missing from table")
    print(
        f"dual id={CTRL_DUAL} disposition={dual['disposition']} "
        f"candidates={dual['candidate_dispositions']}"
    )
    if dual["disposition"] != "AMBIGUOUS":
        return fail("dual-disposition id was not AMBIGUOUS")
    if len(dual.get("candidate_dispositions") or []) < 2:
        return fail("AMBIGUOUS row did not keep both candidate dispositions")
    if "IMPLEMENTED" not in dual["candidate_dispositions"]:
        return fail("expected IMPLEMENTED among dual candidates")
    if "REJECTED-WITH-OWNER-REASONING" not in dual["candidate_dispositions"]:
        return fail("expected REJECTED-WITH-OWNER-REASONING among dual candidates")

    # Negative: silently keeping only the first candidate must not be how
    # the closer behaves. Re-check the raw candidate list length.
    if len(set(dual["candidate_dispositions"])) < 2:
        return fail("candidates were silently deduplicated to one meaning")

    missing = by_id.get(CTRL_MISSING)
    if missing is None:
        return fail(f"{CTRL_MISSING} missing from table")
    print(
        f"planted id={CTRL_MISSING} disposition={missing['disposition']} "
        f"in_universe={missing['in_option_universe']} in_doc13={missing['in_doc13']}"
    )
    if missing["disposition"] != "MISSING":
        return fail("planted absent id was not MISSING")
    if missing["in_option_universe"] or missing["in_doc13"]:
        return fail("planted missing id was declared in an artifact")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        art_rows = {r["id"]: r for r in doc.get("rows") or []}
        if art_rows.get(CTRL_DUAL, {}).get("disposition") != "AMBIGUOUS":
            return fail("artifact dual row not AMBIGUOUS")
        if art_rows.get(CTRL_MISSING, {}).get("disposition") != "MISSING":
            return fail("artifact planted row not MISSING")
        print("artifact_rows_agree=True")
    else:
        print("artifact_rows_agree=NOT-YET (engine-only)")

    print("SUCCESS:BLD-0019-probe1 ambiguous-and-missing controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
