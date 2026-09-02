#!/usr/bin/env python3
"""Probe 1: live identical-input replay, timestamp normalisation, cause attribution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0074-workflow-replay-determinism.json"
SENTINEL = (
    "SUCCESS:CNF-0074 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the change-one-input control "
    "produced a different artifact, ruling out cache-driven false identity. Any "
    "other terminal state is FAILED:CNF-0074 <classification> with the diagnostic "
    "tail attached."
)


def main() -> int:
    rows = B.replay_all()
    by_id = {r["id"]: r for r in rows}
    print(json.dumps({k: {
        "verdict": v["verdict"],
        "byte_identical_raw": v["byte_identical_raw"],
        "byte_identical_normalized": v["byte_identical_normalized"],
        "n_diffs": len(v["field_diffs"]),
    } for k, v in by_id.items()}, indent=2, sort_keys=True))

    seeded = by_id["wf.seeded-stable"]
    if not seeded["byte_identical_raw"] or seeded["verdict"] != "DETERMINISTIC":
        print("FAILED:CNF-0074-probe1 seeded-stable was not byte-identical")
        return 1

    catalog = by_id["wf.catalog-class.discovery-only"]
    if not catalog["byte_identical_raw"] or catalog["verdict"] != "DETERMINISTIC":
        print("FAILED:CNF-0074-probe1 catalog-class discovery workflow was not deterministic")
        return 1

    ts = by_id["wf.timestamp-wallclock"]
    if ts["byte_identical_raw"]:
        print("FAILED:CNF-0074-probe1 timestamp workflow was raw-identical (stamp did not fire)")
        return 1
    if not ts["byte_identical_normalized"]:
        print("FAILED:CNF-0074-probe1 timestamp workflow still differed after normalisation")
        return 1
    if ts["verdict"] != "TIMESTAMP-ONLY":
        print(f"FAILED:CNF-0074-probe1 timestamp verdict={ts['verdict']}")
        return 1
    if not ts["timestamp_fields"]:
        print("FAILED:CNF-0074-probe1 timestamp fields were not reported separately")
        return 1
    if any(d["cause"] != "timestamp" for d in ts["field_diffs"]):
        print("FAILED:CNF-0074-probe1 timestamp workflow had a non-timestamp diff")
        return 1

    path = by_id["wf.path-leaking"]
    if path["byte_identical_normalized"]:
        print("FAILED:CNF-0074-probe1 path-leaking fixture was identical across run dirs")
        return 1
    if path["verdict"] != "NONDETERMINISTIC":
        print(f"FAILED:CNF-0074-probe1 path-leaking verdict={path['verdict']}")
        return 1
    if not any(d["cause"] == "path" for d in path["field_diffs"]):
        print("FAILED:CNF-0074-probe1 path cause was not attributed")
        return 1

    oc = by_id["wf.overclaim-unseeded-sample"]
    if oc["verdict"] != "OVERCLAIM":
        print(f"FAILED:CNF-0074-probe1 overclaim fixture verdict={oc['verdict']}")
        return 1
    if oc["byte_identical_normalized"]:
        print("FAILED:CNF-0074-probe1 overclaim fixture collapsed after timestamp normalisation")
        return 1

    for row in rows:
        if row["field_diffs"] and not row["cause_attribution_complete"]:
            print(f"FAILED:CNF-0074-probe1 incomplete cause attribution for {row['id']}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0074-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0074-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0074":
        print("FAILED:CNF-0074-probe1 unit_id mismatch")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0074-probe1 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:CNF-0074-probe1 replay identity timestamp-normalise cause-attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
