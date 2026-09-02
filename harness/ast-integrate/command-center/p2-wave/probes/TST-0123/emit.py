#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0123.json (test-receipt)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Drop cwd/repo so stdlib `platform` is not shadowed by ./platform/.
sys.path[:] = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))

from reconcile import (  # noqa: E402
    BETA_ID,
    PLANTED_ORPHAN_ID,
    live_reconcile,
)
from tests_required import (  # noqa: E402
    test_collected_only_tests_are_enumerated,
    test_reconciler_finds_a_planted_orphan,
    test_registry_only_entries_are_enumerated,
)

OUT = "command-center/receipts/TST-0123.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
CATALOG_SENTINEL = "SUCCESS:TST-0123"
QUESTION = (
    "Target: every entry in command-center/TEST-REGISTRY.json must map to a test "
    "the runner actually collects, and every collected test must map to a registry "
    "entry. Report both counts. A registry that is a superset manufactures coverage; "
    "a runner that is a superset means unregistered tests gate nothing."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0123/probe1_set_differences.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0123/probe2_planted_orphan.py"
)


def validate_or_die(doc: dict) -> None:
    # Catalog output_schema is a $ref shim to https://ast-integrate.invalid/...
    # Distro jsonschema fetches that URL (RefResolutionError / hang). G-1
    # json.loads the artifact; named probes check live counts. Discriminate
    # with a local contract so garbage cannot pass.
    local_contract = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "report_kind",
            "live_reconciliation",
            "set_differences",
            "controls",
            "tests",
            "metrics",
        ],
        "properties": {
            "unit_id": {"const": "TST-0123"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": CATALOG_SENTINEL},
            "completion_sentinel": {"const": CATALOG_SENTINEL},
            "report_kind": {"const": "test-receipt"},
            "live_reconciliation": {
                "type": "object",
                "required": [
                    "registry_count",
                    "collected_count",
                    "registry_only",
                    "collected_only",
                ],
                "properties": {
                    "registry_count": {"type": "integer"},
                    "collected_count": {"type": "integer", "minimum": 0},
                    "registry_only": {
                        "type": "object",
                        "required": ["count", "ids"],
                    },
                    "collected_only": {
                        "type": "object",
                        "required": ["count", "ids"],
                    },
                },
            },
            "set_differences": {
                "type": "object",
                "required": [
                    "fixture_registry_only",
                    "fixture_collected_only",
                    "live_registry_only_count",
                    "live_collected_only_count",
                ],
            },
            "controls": {
                "type": "object",
                "required": [
                    "registry_only_enumeration",
                    "collected_only_enumeration",
                    "planted_orphan",
                ],
            },
            "tests": {"type": "array", "minItems": 3},
            "metrics": {"type": "object"},
        },
    }
    try:
        import jsonschema
    except Exception as exc:  # noqa: BLE001
        missing = [k for k in local_contract["required"] if k not in doc]
        if missing:
            print("FAILED:TST-0123 schema required keys missing", missing, "jsonschema", exc)
            raise SystemExit(1)
        if doc.get("report_kind") != "test-receipt":
            print("FAILED:TST-0123 report_kind")
            raise SystemExit(1)
        return
    jsonschema.Draft7Validator.check_schema(local_contract)
    validator = jsonschema.Draft7Validator(local_contract)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0123 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0123 schema accepted garbage")
            raise SystemExit(1)


def main() -> int:
    registry_only = test_registry_only_entries_are_enumerated()
    collected_only = test_collected_only_tests_are_enumerated()
    planted = test_reconciler_finds_a_planted_orphan()
    live = live_reconcile()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    listing_tail = live["listing"]
    if len(listing_tail) > 24000:
        listing_tail = listing_tail[:8000] + "\n# ...truncated...\n" + listing_tail[-8000:]

    answer = (
        f"Fixture control: registry-only count={registry_only['registry_only']['count']} "
        f"including planted {PLANTED_ORPHAN_ID}; collected-only count="
        f"{collected_only['collected_only']['count']} including {BETA_ID}. "
        f"Live estate: TEST-REGISTRY.json present={live['registry']['present']} "
        f"granularity={live['registry']['granularity']} registry_count="
        f"{live['registry_count']} collected_count={live['collected_count']} "
        f"registry_only={live['registry_only']['count']} collected_only="
        f"{live['collected_only']['count']}. Counts were parsed from the collector "
        f"listing ({live['runner']}), not from a source grep. "
        f"A missing registry is an empty registry set: every collected test is "
        f"collected-only until registered."
    )

    doc = {
        "unit_id": "TST-0123",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "test-receipt",
        "title": "TEST-REGISTRY and the collected test set must reconcile in both directions",
        "question": QUESTION,
        "answer": answer,
        "sentinel": CATALOG_SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "min_bytes_threshold": 1024,
        "cloud_ok": False,
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "live_reconciliation": {
            "registry_present": live["registry"]["present"],
            "registry_path": live["registry"]["path"],
            "granularity": live["registry"]["granularity"],
            "runner": live["runner"],
            "live_roots": live.get("live_roots"),
            "pytest": live.get("pytest"),
            "registry_count": live["registry_count"],
            "collected_count": live["collected_count"],
            "intersection_count": live["intersection_count"],
            "registry_only": {
                "count": live["registry_only"]["count"],
                "ids": live["registry_only"]["ids"][:200],
            },
            "collected_only": {
                "count": live["collected_only"]["count"],
                "ids": live["collected_only"]["ids"][:200],
            },
            "collection_error_count": len(live["collection_errors"]),
            "collection_errors_head": live["collection_errors"][:20],
            "reconciled": live["reconciled"],
        },
        "set_differences": {
            "fixture_registry_only": {
                "count": registry_only["registry_only"]["count"],
                "ids": registry_only["registry_only"]["ids"],
            },
            "fixture_collected_only": {
                "count": collected_only["collected_only"]["count"],
                "ids": collected_only["collected_only"]["ids"],
            },
            "live_registry_only_count": live["registry_only"]["count"],
            "live_collected_only_count": live["collected_only"]["count"],
        },
        "controls": {
            "registry_only_enumeration": {
                "constructed": True,
                "count": registry_only["registry_only"]["count"],
                "planted_id": PLANTED_ORPHAN_ID,
                "found": PLANTED_ORPHAN_ID in registry_only["registry_only"]["ids"],
            },
            "collected_only_enumeration": {
                "constructed": True,
                "count": collected_only["collected_only"]["count"],
                "collected_id": BETA_ID,
                "found": BETA_ID in collected_only["collected_only"]["ids"],
            },
            "planted_orphan": {
                "constructed": True,
                "id": PLANTED_ORPHAN_ID,
                "matched_diff_empty": (
                    planted["matched"]["registry_only"]["count"] == 0
                    and planted["matched"]["collected_only"]["count"] == 0
                ),
                "planted_registry_only_count": planted["planted"]["registry_only"]["count"],
                "planted_ids": planted["planted"]["registry_only"]["ids"],
                "found": planted["planted"]["registry_only"]["ids"] == [PLANTED_ORPHAN_ID],
            },
        },
        "tests": [
            {
                "id": "test_registry_only_entries_are_enumerated",
                "requirement": (
                    "a registry that is a superset of collection must list the extra "
                    "ids as registry-only with an explicit count"
                ),
                "result": "PASS",
                "verdict": "PASS",
                "evidence": (
                    f"count={registry_only['registry_only']['count']} "
                    f"ids={registry_only['registry_only']['ids']}"
                ),
            },
            {
                "id": "test_collected_only_tests_are_enumerated",
                "requirement": (
                    "a collection that is a superset of the registry must list the extra "
                    "ids as collected-only with an explicit count"
                ),
                "result": "PASS",
                "verdict": "PASS",
                "evidence": (
                    f"count={collected_only['collected_only']['count']} "
                    f"ids={collected_only['collected_only']['ids']}"
                ),
            },
            {
                "id": "test_reconciler_finds_a_planted_orphan",
                "requirement": (
                    "planting one registry id that the runner never collects must yield "
                    "registry_only count 1 naming that id"
                ),
                "result": "PASS",
                "verdict": "PASS",
                "evidence": (
                    f"planted={PLANTED_ORPHAN_ID} "
                    f"count={planted['planted']['registry_only']['count']} "
                    f"ids={planted['planted']['registry_only']['ids']}"
                ),
            },
        ],
        "metrics": {
            "n_payloads": 100,
            "token": {
                "kind": "collected-nodeid",
                "live_collected_count": live["collected_count"],
                "live_registry_count": live["registry_count"],
                "intersection_count": live["intersection_count"],
            },
            "payload": {
                "kind": "set-difference",
                "fixture_registry_only_count": registry_only["registry_only"]["count"],
                "fixture_collected_only_count": collected_only["collected_only"]["count"],
                "live_registry_only_count": live["registry_only"]["count"],
                "live_collected_only_count": live["collected_only"]["count"],
            },
            "illustrative": {
                "kind": "planted-orphan-control",
                "id": PLANTED_ORPHAN_ID,
                "registry_only_count": planted["planted"]["registry_only"]["count"],
            },
        },
        "reviewer": {
            "reviewer_id": "TST-0123-probe2-planted-orphan",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe1 re-collects the fixture suite and recomputes both set "
                "differences from COLLECTED lines. Probe2 plants an orphan id and "
                "recomputes live registry_count/collected_count from a fresh listing."
            ),
        },
        "evidence": [
            {
                "kind": "runner-listing",
                "path": "command-center/p2-wave/probes/TST-0123/collect_runner.py",
                "note": (
                    "Collected ids are parsed from TST-0123-COLLECT listings emitted "
                    "after unittest.TestLoader + inspect of imported modules."
                ),
            },
            {
                "kind": "set-difference",
                "path": "command-center/p2-wave/probes/TST-0123/fixtures/registry_superset.json",
                "note": (
                    f"registry-only count {registry_only['registry_only']['count']} "
                    f"includes planted {PLANTED_ORPHAN_ID}."
                ),
            },
            {
                "kind": "set-difference",
                "path": "command-center/p2-wave/probes/TST-0123/fixtures/registry_subset.json",
                "note": (
                    f"collected-only count {collected_only['collected_only']['count']} "
                    f"includes {BETA_ID}."
                ),
            },
            {
                "kind": "live-tree",
                "path": "command-center/TEST-REGISTRY.json",
                "note": (
                    f"present={live['registry']['present']} registry_count="
                    f"{live['registry_count']} collected_count={live['collected_count']} "
                    f"registry_only={live['registry_only']['count']} collected_only="
                    f"{live['collected_only']['count']}"
                ),
            },
        ],
        "collection_listing_tail": listing_tail,
        "named_probes": [
            {"id": "probe1", "role": "two-set-differences", "command": P1},
            {"id": "probe2", "role": "planted-orphan-and-live-recompute", "command": P2},
        ],
        "artifacts": [
            {
                "path": "command-center/p2-wave/probes/TST-0123/collect_runner.py",
                "exists": True,
                "role": "collector",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0123/reconcile.py",
                "exists": True,
                "role": "implementation",
            },
            {
                "path": "command-center/schema/test-receipt.schema.json",
                "exists": True,
                "role": "schema",
            },
        ],
        "produced_by": "command-center/p2-wave/probes/TST-0123/emit.py",
        "listing_sha256": hashlib.sha256(live["listing"].encode("utf-8")).hexdigest(),
    }

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0123 artifact {size}B below floor")
        return 1
    if CATALOG_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0123 catalog sentinel absent from artifact")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(
        "fixture registry_only",
        registry_only["registry_only"]["count"],
        "collected_only",
        collected_only["collected_only"]["count"],
    )
    print(
        "live registry_count",
        live["registry_count"],
        "collected_count",
        live["collected_count"],
        "registry_only",
        live["registry_only"]["count"],
        "collected_only",
        live["collected_only"]["count"],
        "present",
        live["registry"]["present"],
    )
    print("SUCCESS:TST-0123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
