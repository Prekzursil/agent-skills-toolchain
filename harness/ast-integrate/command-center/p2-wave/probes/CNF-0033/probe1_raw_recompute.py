#!/usr/bin/env python3
"""Named probe 1: recompute from raw files; never from the summary table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import recompute as R  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0033-metric-recompute.json"
SCHEMA = REPO / "command-center/schema/benchmark-report.schema.json"
SUMMARY_REL = (
    "command-center/p2-wave/probes/CNF-0033/fixtures/summary/implementer_table.json"
)
RECOMPUTE_PY = HERE / "recompute.py"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0033-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0033":
        print("FAILED:CNF-0033-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0033-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:CNF-0033" not in text:
        print("FAILED:CNF-0033-probe1 sentinel absent")
        return 1

    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0033-probe1 schema", errs[0].message)
        return 1
    cat_errs = S.catalog_iter_errors(doc)
    if cat_errs:
        print("FAILED:CNF-0033-probe1 catalog-schema", cat_errs[0].message)
        return 1

    src = RECOMPUTE_PY.read_text(encoding="utf-8")
    if SUMMARY_REL in src:
        print("FAILED:CNF-0033-probe1 recompute.py names the summary table")
        return 1
    if "implementer_table" in src:
        print("FAILED:CNF-0033-probe1 recompute.py mentions implementer_table")
        return 1

    summary = json.loads((REPO / SUMMARY_REL).read_text(encoding="utf-8"))
    claims = S.claims_of(doc)
    if not isinstance(claims, list) or len(claims) < 4:
        print("FAILED:CNF-0033-probe1 too few claims", len(claims) if isinstance(claims, list) else None)
        return 1

    by_id = {c["id"]: c for c in claims if isinstance(c, dict) and c.get("id")}
    for cid, row in by_id.items():
        verdict = row.get("verdict")
        if verdict == "NOT-CHECKED":
            missing = str(row.get("missing_raw_file") or "")
            if not missing:
                print("FAILED:CNF-0033-probe1 NOT-CHECKED unnamed", cid)
                return 1
            path = REPO / missing
            if path.is_file() and path.stat().st_size > 0:
                print("FAILED:CNF-0033-probe1 NOT-CHECKED but present", missing)
                return 1
            if row.get("recomputed_value") is not None:
                print("FAILED:CNF-0033-probe1 NOT-CHECKED has value", cid)
                return 1
        else:
            if row.get("recomputed_value") is None:
                print("FAILED:CNF-0033-probe1 missing recomputed_value", cid)
                return 1

        if verdict == "MATCH" and not (REPO / str(row.get("raw_file") or "")).is_file():
            print("FAILED:CNF-0033-probe1 MATCH without raw file", cid)
            return 1

    # Independent recompute of detector-control rows.
    match_spec = next(s for s in I.control_specs() if s["id"] == "control.match")
    claimed_v, _claimed_d = I.claimed_from_table(summary, "control.match")
    live = R.evaluate(
        claim_id="control.match",
        source="detector-control",
        raw_rel=str(match_spec["raw_file"]),
        claimed_value=claimed_v,
        claimed_delta=None,
        precision_decimals=1,
        noise_floor=None,
        noise_floor_file="command-center/confirmation/CNF-0027-baseline-variance.json",
    )
    art_match = by_id["control.match"]
    if live["verdict"] != "MATCH" or art_match["verdict"] != "MATCH":
        print("FAILED:CNF-0033-probe1 match verdict", live["verdict"], art_match["verdict"])
        return 1
    if abs(float(live["recomputed_value"]) - float(art_match["recomputed_value"])) > 1e-12:
        print("FAILED:CNF-0033-probe1 match value drift")
        return 1
    if abs(float(live["recomputed_value"]) - 10.0) > 1e-9:
        print("FAILED:CNF-0033-probe1 expected median 10.0", live["recomputed_value"])
        return 1

    poison_spec = next(s for s in I.control_specs() if s["id"] == "control.summary-poison")
    claimed_p, _d = I.claimed_from_table(summary, "control.summary-poison")
    if claimed_p != 999.0:
        print("FAILED:CNF-0033-probe1 poison table changed", claimed_p)
        return 1
    poison = R.evaluate(
        claim_id="control.summary-poison",
        source="detector-control",
        raw_rel=str(poison_spec["raw_file"]),
        claimed_value=claimed_p,
        claimed_delta=None,
        precision_decimals=1,
        noise_floor=None,
        noise_floor_file="command-center/confirmation/CNF-0027-baseline-variance.json",
    )
    if poison["verdict"] != "MISMATCH":
        print("FAILED:CNF-0033-probe1 poison not overclaim", poison["verdict"])
        return 1
    if abs(float(poison["recomputed_value"]) - 999.0) < 0.1:
        print("FAILED:CNF-0033-probe1 used summary as input")
        return 1
    if by_id["control.summary-poison"]["verdict"] != "MISMATCH":
        print("FAILED:CNF-0033-probe1 artifact poison verdict")
        return 1

    missing = by_id["control.missing-raw"]
    if missing["verdict"] != "NOT-CHECKED":
        print("FAILED:CNF-0033-probe1 missing-raw", missing)
        return 1
    miss_path = str(missing["missing_raw_file"])
    if "control_missing.json" not in miss_path:
        print("FAILED:CNF-0033-probe1 missing file not named", miss_path)
        return 1

    live_rows = [c for c in claims if c.get("source") == "live-census"]
    if not live_rows:
        print("FAILED:CNF-0033-probe1 no live census rows")
        return 1
    for row in live_rows:
        if row.get("verdict") != "NOT-CHECKED":
            print("FAILED:CNF-0033-probe1 live row not NOT-CHECKED", row)
            return 1

    print(
        f"match={art_match['recomputed_value']} poison={poison['recomputed_value']} "
        f"poison_verdict=MISMATCH missing={miss_path}"
    )
    print("SUCCESS:CNF-0033-probe1 raw recompute; summary not used as input")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
