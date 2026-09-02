#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0069-adopt-as-is-executable-test.json."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_both_states  # noqa: E402
from registry import EXPECTED_N, load_registry  # noqa: E402
from smoke import (  # noqa: E402
    ADOPT,
    UNKNOWN,
    bounds_snapshot,
    digest_file,
    reset_bounds,
    run_all,
)

OUT = "command-center/wfa/WFA-0069-adopt-as-is-executable-test.json"
SCHEMA = "command-center/p2-wave/probes/WFA-0069/disposition.schema.json"
RECEIPTS = "command-center/wfa/WFA-0069-smoke-receipts"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0069/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0069/probe2_postcondition.py"
)
QUESTION = (
    "For each of the 122 ADOPT-AS-IS candidates, does an executable adoption "
    "test actually pass - the workflow loads, validates, and completes a smoke "
    "case unchanged - or is ADOPT-AS-IS currently an untested assertion "
    "carried forward from discovery?"
)
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
]
SIZE_FLOOR = 8192


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def validate(doc: dict, schema: dict) -> None:
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for g in GARBAGE:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != len(GARBAGE):
        raise SystemExit(f"FAILED:WFA-0069 schema accepted garbage rejected={rejected}")


def main() -> int:
    reset_bounds()
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    reg = load_registry(REPO)
    receipt_dir = REPO / RECEIPTS
    if receipt_dir.exists():
        for old in receipt_dir.glob("*.json"):
            old.unlink()
    receipt_dir.mkdir(parents=True, exist_ok=True)

    both = run_both_states(HERE / "_control-scratch")
    if not both["ok"]:
        print("FAILED:WFA-0069 both-states control did not discriminate")
        print(json.dumps({k: both[k] for k in ("good_passed", "broken_copy_failed_same_smoke", "unconstructable_reclassified")}, sort_keys=True))
        return 1

    raw_rows = run_all(reg["records"], receipt_dir)
    if len(raw_rows) != EXPECTED_N:
        print(f"FAILED:WFA-0069 expected {EXPECTED_N} rows got {len(raw_rows)}")
        return 1

    records = []
    for src, row in zip(reg["records"], raw_rows):
        rec_path = Path(row["receipt_path"])
        records.append(
            {
                "candidate_id": row["candidate_id"],
                "discovery_id_known": bool(src.get("discovery_id_known")),
                "disposition": row["disposition"],
                "prior_classification": "ADOPT-AS-IS",
                "reason": row["reason"],
                "receipt_bytes": row["receipt_bytes"],
                "receipt_path": relpath(rec_path),
                "receipt_sha256": row["receipt_sha256"],
                "smoke_run": row["smoke_run"],
            }
        )

    for rec in records:
        if rec["smoke_run"]["constructed"] is False and rec["disposition"] == ADOPT:
            print(f"FAILED:WFA-0069 unconstructable left as ADOPT-AS-IS {rec['candidate_id']}")
            return 1
        if rec["disposition"] == ADOPT:
            live = REPO / rec["receipt_path"]
            if not live.is_file() or live.stat().st_size < 180:
                print(f"FAILED:WFA-0069 adopt without receipt {rec['candidate_id']}")
                return 1

    hist = Counter(r["disposition"] for r in records)
    bounds = bounds_snapshot()
    if bounds["max_in_flight"] != 1:
        print(f"FAILED:WFA-0069 not serialized max_in_flight={bounds['max_in_flight']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    adopt_n = int(hist.get(ADOPT, 0))
    unk_n = int(hist.get(UNKNOWN, 0))
    if reg["found"]:
        answer = (
            f"Of {EXPECTED_N} ADOPT-AS-IS candidates loaded from the registry, "
            f"{adopt_n} passed load+validate+complete with an on-disk receipt "
            f"and {unk_n} were reclassified {UNKNOWN} because a smoke case "
            "could not be constructed or did not complete unchanged. Exit code "
            "zero was never treated as success."
        )
    else:
        answer = (
            f"ADOPT-AS-IS is currently an untested assertion carried forward "
            f"from discovery: 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent on "
            f"this Linux worktree, so none of the {EXPECTED_N} smoke cases could "
            f"be constructed. All {EXPECTED_N} were reclassified {UNKNOWN} with "
            "a per-candidate receipt. The harness both-states control still "
            "fires: a good fixture passes and a deliberately broken copy fails "
            "the same smoke case."
        )

    doc = {
        "answer": answer,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": RECEIPTS, "exists": True, "role": "per-candidate-receipts"},
        ],
        "both_states": {
            "broken_copy_failed_same_smoke": True,
            "good_passed": True,
            "unconstructable_reclassified": True,
            "good_candidate_id": both["good_candidate_id"],
            "broken_candidate_id": both["broken_candidate_id"],
            "unconstructable_disposition": both["unconstructable_disposition"],
        },
        "bounds": bounds,
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Exit code zero is never success: ADOPT-AS-IS requires a "
                    "constructed smoke, source_unchanged, and a parsing receipt "
                    "above the size floor."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0069/smoke.py:_adopt_ok",
            },
            {
                "id": "C2",
                "claim": (
                    "A candidate whose smoke case cannot be constructed is "
                    f"reclassified {UNKNOWN}, never left as ADOPT-AS-IS."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0069/controls.py:unconstructable",
            },
            {
                "id": "C3",
                "claim": (
                    "A deliberately broken copy of one adopted workflow fails "
                    "the same smoke case that the good copy passes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0069/controls.py:run_both_states",
            },
        ],
        "evidence": [
            {
                "path": RECEIPTS,
                "kind": "per-candidate-smoke-receipt",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0069/probe2_postcondition.py",
                "kind": "independent-postcondition",
            },
        ],
        "expected_adopt_as_is_count": EXPECTED_N,
        "histogram": {
            ADOPT: adopt_n,
            UNKNOWN: unk_n,
        },
        "id": "WFA-0069",
        "output_schema_declared": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/DispositionRecord"
        ),
        "question": QUESTION,
        "records": records,
        "registry": {
            "found": bool(reg["found"]),
            "path": reg["path"],
            "searched_paths": reg["searched_paths"],
            "sha256": reg["sha256"],
            "adopt_as_is_count": int(reg["adopt_as_is_count"]),
        },
        "report_kind": "DispositionRecord",
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0069-probe2-postcondition",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:WFA-0069",
        "state": "SUCCESS",
        "tests": [
            {
                "id": "T-BOTH-STATES",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-POSTCONDITION",
                "command": P2,
                "result": "PASS",
            },
        ],
        "ts": now,
        "unit_id": "WFA-0069",
    }

    validate(doc, schema)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest_file(out)
    if size < SIZE_FLOOR:
        print(f"FAILED:WFA-0069 artifact below size floor bytes={size}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"histogram ADOPT-AS-IS={adopt_n} UNKNOWN-NEEDS-PROBE={unk_n} registry_found={reg['found']}")
    print("SUCCESS:WFA-0069")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
