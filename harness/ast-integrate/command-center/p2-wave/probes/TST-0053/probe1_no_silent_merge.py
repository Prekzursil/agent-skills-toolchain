#!/usr/bin/env python3
"""Probe 1: case-distinct keys do not silently merge (live consumer table).

Re-runs the same fixture through every consumer. PASS requires:
  * object_pairs_hook still sees both Name and name with distinct values
  * the unit pipeline reader errors (does not merge)
  * a casefold downstream last-wins (the seeded silent-loss path is live)
  * CPython json.loads keeps both (divergence, not a single expected value)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from case_keys import NAME_LOWER_VALUE, NAME_UPPER_VALUE  # noqa: E402
from consumers import run_matrix, write_fixture  # noqa: E402

ART = REPO / "command-center/receipts/TST-0053.json"
FIX = HERE / "fixtures" / "name-and-Name.json"
REQUIRED = {
    "cpython-json.loads": "kept-both",
    "ci-downstream-of-cs-producer": "last-wins",
    "tst-0053-pipeline-reader": "error",
}


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0053-probe1 {msg}")
    return 1


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["consumer_id"]: r for r in rows}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return _fail(f"receipt self-declared {doc.get('state')}")
    if "SUCCESS:TST-0053" not in text:
        return _fail("sentinel absent")

    write_fixture(FIX)
    matrix = run_matrix(FIX)
    plant = matrix["plant"]
    print(
        "plant both_present="
        f"{plant['both_present']} name_keys={plant['name_keys']} "
        f"name_values={plant['name_values']} distinct={plant['distinct_values']}"
    )
    if not plant["both_present"] or not plant["distinct_values"]:
        return _fail("pairs-hook plant dead: both keys were not in the source")
    if NAME_UPPER_VALUE not in plant["name_values"] or NAME_LOWER_VALUE not in plant["name_values"]:
        return _fail("plant values were not the two distinct Name/name payloads")

    rows = matrix["consumers"]
    by_id = _by_id(rows)
    for cid, expected in REQUIRED.items():
        row = by_id.get(cid)
        if row is None:
            return _fail(f"consumer {cid} missing from live matrix")
        print(
            f"consumer[{cid}] outcome={row['outcome']} errored={row['errored']} "
            f"resolved={row.get('resolved')}"
        )
        if row.get("error_text"):
            print(f"  error={row['error_text']}")
        if row["outcome"] != expected:
            return _fail(f"{cid} outcome {row['outcome']!r} != {expected!r}")

    pipe = by_id["tst-0053-pipeline-reader"]
    if not pipe["errored"] or pipe.get("resolved") is not None:
        return _fail("pipeline reader silently merged or returned values")
    ci = by_id["ci-downstream-of-cs-producer"]
    resolved = ci.get("resolved") or {}
    if resolved.get("Name") != NAME_LOWER_VALUE or resolved.get("name") != NAME_LOWER_VALUE:
        return _fail("casefold downstream did not last-win to lowercase-n")

    cs = by_id["cpython-json.loads"]
    cs_r = cs.get("resolved") or {}
    if cs_r.get("Name") != NAME_UPPER_VALUE or cs_r.get("name") != NAME_LOWER_VALUE:
        return _fail("json.loads did not keep both distinct values")

    if matrix["outcome_count"] < 2:
        return _fail("no divergence: every consumer reported the same outcome")

    cnf = by_id.get("cnf-0035-strict-reader")
    if cnf and cnf.get("available") is not False and cnf["outcome"] != "error":
        return _fail("CNF-0035 strict reader did not error on Name/name")

    recorded = doc.get("resolution_table") or {}
    rec_rows = _by_id(recorded.get("consumers") or [])
    for cid, expected in REQUIRED.items():
        rec = rec_rows.get(cid) or {}
        if rec.get("outcome") != expected:
            return _fail(
                f"receipt table {cid} outcome {rec.get('outcome')!r} != live {expected!r}"
            )

    summary = {
        "probe": "probe1-no-silent-merge",
        "unit_id": "TST-0053",
        "pass": True,
        "plant_both_present": plant["both_present"],
        "distinct_outcomes": matrix["distinct_outcomes"],
        "pipeline_errored": pipe["errored"],
        "cpython_kept_both": cs["outcome"] == "kept-both",
        "ci_last_wins": ci["outcome"] == "last-wins",
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:TST-0053-probe1 case-distinct keys do not silently merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
