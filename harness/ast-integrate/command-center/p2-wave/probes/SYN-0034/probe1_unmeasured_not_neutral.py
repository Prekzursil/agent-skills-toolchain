#!/usr/bin/env python3
"""Named probe 1: missing baseline is UNMEASURED, not NEUTRAL; live net recomputes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ledger import (  # noqa: E402
    FIXTURES,
    assert_table_internally_consistent,
    evaluate,
    recompute_net_from_published,
    recompute_row_verdict_from_published,
)

ART = REPO / "command-center/synthesis/SYN-0034.improvement-ledger.json"
SENTINEL = (
    "SUCCESS:SYN-0034 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every change row carries "
    "a verdict and the net verdict recomputes from the published rows. Any "
    "other terminal state is FAILED:SYN-0034 <classification> with the "
    "diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0034-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if doc.get("unit_id") != "SYN-0034":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if SENTINEL not in text:
        return fail("completion sentinel absent")

    missing = evaluate(FIXTURES["missing_baseline"])
    assert_table_internally_consistent(missing)
    row = missing["changes"][0]
    if row["verdict"] != "UNMEASURED":
        return fail(f"missing baseline classified {row['verdict']}")
    if row["verdict"] == "NEUTRAL":
        return fail("unmeasured-counted-as-neutral")
    if row["baseline"]["captured"] is True:
        return fail("fixture baseline marked captured")

    changes = doc.get("changes")
    if not isinstance(changes, list) or not changes:
        return fail("live changes missing")
    for live_row in changes:
        if not isinstance(live_row, dict) or not live_row.get("verdict"):
            return fail(f"row without verdict {live_row}")
        recomputed_row = recompute_row_verdict_from_published(live_row)
        if recomputed_row != live_row.get("verdict"):
            return fail(
                f"{live_row.get('change_id')} published "
                f"{live_row.get('verdict')} recomputes {recomputed_row}"
            )
        baseline = live_row.get("baseline") or {}
        if baseline.get("captured") is False and live_row.get("verdict") == "NEUTRAL":
            return fail(
                f"{live_row.get('change_id')} unmeasured-counted-as-neutral"
            )

    live_net = (doc.get("net") or {}).get("verdict")
    recomputed_net = recompute_net_from_published(changes)
    if recomputed_net != live_net:
        return fail(f"net {live_net} recomputes to {recomputed_net}")

    payload = {
        "pass": True,
        "probe": "probe1-unmeasured-not-neutral",
        "unit_id": "SYN-0034",
        "missing_baseline_verdict": row["verdict"],
        "live_rows": len(changes),
        "live_net": live_net,
        "recomputed_net": recomputed_net,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:SYN-0034-probe1 missing baseline is UNMEASURED; "
        f"live net {live_net} recomputes from {len(changes)} rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
