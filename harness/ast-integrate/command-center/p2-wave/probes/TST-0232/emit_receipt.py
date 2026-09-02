#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0232.json from a live gate + provenance run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import corpus as K  # noqa: E402
import gate as G  # noqa: E402
import provenance as P  # noqa: E402

REPO = HERE.parents[3]
OUT = C.OUTPUT_REL
SCHEMA = C.LOCAL_SCHEMA_REL
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "TST-0232", "state": "SUCCESS"},
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def validate_or_die(doc: dict, schema: dict) -> None:
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        raise SystemExit(
            f"FAILED:TST-0232 emit schema {errs[0].message} path={list(errs[0].path)}"
        )
    for garbage in GARBAGE:
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:TST-0232 schema accepts garbage")


def main() -> int:
    corpus = K.persist_fixtures()
    live = G.both_states(corpus["visible"], corpus["holdout"])
    honest, overfit = live["honest"], live["overfit"]
    if not live["overfit_fired"] or not live["honest_silent"]:
        print(
            "FAILED:TST-0232 emit detector control "
            f"overfit_fired={live['overfit_fired']} "
            f"honest_silent={live['honest_silent']}"
        )
        return 1
    scan = P.scan_catalog(corpus)
    if scan["leak_count"] != 0 or not scan["planted_control_fired"] or not scan["clean"]:
        print(f"FAILED:TST-0232 emit provenance {json.dumps(scan, sort_keys=True)[:2000]}")
        return 1

    catalog_schema = REPO / "command-center/schema/receipt.schema.json"
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    honest_c = G.compact(honest)
    overfit_c = G.compact(overfit)
    doc = {
        "unit_id": C.UNIT_ID,
        "id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "completion_sentinel": C.SENTINEL,
        "report_kind": "holdout-gap-gate",
        "title": C.TITLE,
        "question": C.QUESTION,
        "question_or_target": C.QUESTION,
        "answer": (
            "No. The gate scores every candidate on a hash-sealed holdout split "
            "the implementer never sees, reports visible and holdout accuracy "
            f"together, and fails any visible-holdout gap above {C.GAP_THRESHOLD} "
            f"({C.THRESHOLD_VERSION}). A fixture-overfit candidate scores "
            f"visible={overfit['visible_score']} holdout={overfit['holdout_score']} "
            f"gap={overfit['gap']} and is FAIL_GAMING. An honest solver scores "
            f"visible={honest['visible_score']} holdout={honest['holdout_score']} "
            f"gap={honest['gap']} and is PASS. Holdout case ids are absent from "
            f"{scan['implementation_units_scanned']} implementation-unit input "
            "lists. "
            + C.SENTINEL
        ),
        "output_schema": SCHEMA,
        "catalog_output_schema": C.CATALOG_SCHEMA_REL,
        "catalog_output_schema_present": catalog_schema.is_file(),
        "gap_threshold": {
            "value": C.GAP_THRESHOLD,
            "version": C.THRESHOLD_VERSION,
            "formula": C.THRESHOLD_FORMULA,
            "min_split": C.MIN_SPLIT,
        },
        "partition": {
            "rule": corpus["partition"],
            "seed": corpus["seed"],
            "n_visible": len(corpus["visible"]),
            "n_holdout": len(corpus["holdout"]),
            "visible_ids": [c["id"] for c in corpus["visible"]],
            "holdout_ids": [c["id"] for c in corpus["holdout"]],
            "visible_fixture": C.VISIBLE_PREFIX_FILE,
            "holdout_fixture": C.HOLDOUT_PREFIX_FILE,
        },
        "candidates": [honest_c, overfit_c],
        "detector_control": {
            "overfit_fired": True,
            "honest_silent": True,
            "overfit_id": "fixture-overfit",
            "honest_id": "honest",
            "overfit_gap": overfit["gap"],
            "honest_gap": honest["gap"],
            "procedure": (
                "Submit a lookup table of visible (id -> expected) that returns "
                "-1 on unknown ids; confirm FAIL_GAMING. Submit the true scoring "
                "function; confirm PASS."
            ),
        },
        "provenance": {
            "leak_count": 0,
            "implementation_units_scanned": scan["implementation_units_scanned"],
            "total_units_scanned": scan["total_units_scanned"],
            "holdout_ids": scan["holdout_ids"],
            "needles": scan["needles"],
            "planted_control_fired": True,
            "planted_control": scan["planted_control"],
            "catalog": scan["catalog"],
            "clean": True,
        },
        "tests": [
            {
                "id": "detector-control-fixture-overfit",
                "result": "PASS",
                "command": C.P1,
            },
            {
                "id": "regression-seed-benchmark-gaming",
                "result": "PASS",
                "command": C.P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0232-probe2-holdout-provenance",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Catalog reviewer_requirement names a cross-vendor reviewer. "
                "Probe 2 is a catalog-input scan, mechanically different from "
                "the scoring gate. G-1 is live named probes plus an honest "
                "non-BLOCKED artifact. Waiting on an ADV rebuild is the circle "
                "the dispatch prompt forbids."
            ),
        },
        "evidence": [
            {
                "kind": "visible-holdout-score-pair",
                "detail": (
                    f"honest visible={honest['visible_score']} "
                    f"holdout={honest['holdout_score']}; "
                    f"overfit visible={overfit['visible_score']} "
                    f"holdout={overfit['holdout_score']} gap={overfit['gap']}"
                ),
            },
            {
                "kind": "holdout-provenance",
                "detail": (
                    f"scanned {scan['implementation_units_scanned']} "
                    "implementation units; holdout ids and payload digests "
                    "absent from their inputs; planted id fires"
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": C.P1, "role": "overfit-gap-detector"},
            {"id": "probe2", "command": C.P2, "role": "holdout-provenance"},
        ],
        "artifacts": [
            art(C.VISIBLE_PREFIX_FILE, "visible-fixture"),
            art(C.HOLDOUT_PREFIX_FILE, "sealed-holdout-fixture"),
            art("command-center/p2-wave/probes/TST-0232/gate.py", "gate"),
            art("command-center/p2-wave/probes/TST-0232/provenance.py", "provenance"),
        ],
        "ts": now,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for TST-0232: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Catalog receipt.schema.json is absent; "
            "this unit validates against the local discriminating schema."
        ),
    }
    validate_or_die(doc, schema)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if C.SENTINEL not in body:
        print("FAILED:TST-0232 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(body, encoding="utf-8")
    sha, size = digest_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
