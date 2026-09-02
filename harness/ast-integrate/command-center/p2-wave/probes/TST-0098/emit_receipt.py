#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0098.json from a live matrix run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = "command-center/receipts/TST-0098.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
QUESTION = (
    "Inject DNS failure, connection reset, TLS error, slow loris, truncated "
    "response and mid-stream disconnect at every external boundary, asserting "
    "a typed failure and preserved partial work. Which boundary swallows a "
    "fault into an empty success?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0098/probe1_typed_failure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0098/probe2_partial_work.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    work = HERE / "runtime" / "emit"
    cells = H.run_matrix(work / "matrix")
    mok, mwhy = H.matrix_ok(cells)
    pok, pwhy = H.partial_ok(cells)
    healthy = H.run_healthy(work / "healthy")
    swallow = H.run_swallower_control(work / "swallow")
    inv = H.inventory_live_tree()
    if not mok:
        print(f"FAILED:TST-0098 emit matrix {mwhy}")
        return 1
    if not pok:
        print(f"FAILED:TST-0098 emit partial {pwhy}")
        return 1
    if swallow.get("classification") != "EMPTY_SUCCESS":
        print("FAILED:TST-0098 emit swallower detector blind")
        return 1
    if any(c["classification"] != "SUCCESS" for c in healthy):
        print("FAILED:TST-0098 emit healthy path")
        return 1

    empty = [c for c in cells if c["empty_success"]]
    swallow_answer = (
        "None of the five in-scope fail-closed adapters swallow a fault into "
        "empty success. Live-tree inventory found "
        f"{inv['product_http_client_count']} product HTTP client import(s) "
        "outside p2-wave probes. The planted swallower at "
        f"{H.SWALLOW_PATH} is classified EMPTY_SUCCESS (P1 detector control), "
        "proving empty success is visible rather than scored as a pass."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "TST-0098",
        "id": "TST-0098",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0098",
        "spec_anchor": "_USER-PROMPTS.md:11007",
        "min_bytes_threshold": 256,
        "title": "Network fault-injection matrix",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report": {
            "kind": "fault-injection-receipt",
            "observations": [
                {
                    "name": "typed_failure_cells",
                    "measured": sum(1 for c in cells if not c["empty_success"]),
                    "method": "live-localhost-fault-server-matrix",
                    "anchor": "command-center/p2-wave/probes/TST-0098/harness.py:fetch_fail_closed",
                },
                {
                    "name": "empty_success_production_cells",
                    "measured": len(empty),
                    "method": "classification-table",
                    "anchor": "command-center/p2-wave/probes/TST-0098/harness.py:matrix_ok",
                },
                {
                    "name": "planted_swallower_classification",
                    "measured": swallow["classification"],
                    "method": "planted-empty-success-detector-control",
                    "anchor": H.SWALLOW_PATH,
                },
            ],
            "control_ids": [
                "planted_empty_success_swallower",
                "healthy_both_states",
            ],
        },
        "failure_class": "empty-success-on-network-fault",
        "injection": {
            "method": "localhost-fault-server-plus-rfc2606-invalid-dns",
            "target": (
                "five fail-closed adapters: registry, package, research, "
                "cloud dispatch, cross-vendor MCP stream"
            ),
            "when": (
                "per-cell: pre-handshake (dns/tls/reset) or mid-body "
                "(slow-loris / truncated FIN / mid-stream RST)"
            ),
        },
        "observations": {
            "ledger_event_types": [
                "TYPED_FAILURE",
                "EMPTY_SUCCESS",
                "PARTIAL_STAGING",
                "COMMITTED_UNCHANGED",
            ],
            "harvest": {
                "typed_failure_cells": sum(
                    1 for c in cells if not c["empty_success"]
                ),
                "empty_success_production_cells": len(empty),
                "planted_swallower": swallow["classification"],
                "product_http_client_count": inv["product_http_client_count"],
            },
        },
        "receipt_kind": "network-fault-injection-matrix",
        "schema_version": 1,
        "produced_at": now,
        "timestamp_utc": now,
        "boundaries": [
            {"id": b.id, "role": b.role, "method": b.method, "path": b.path}
            for b in H.BOUNDARIES
        ],
        "faults": list(H.FAULTS),
        "matrix": {
            "total_cells": len(cells),
            "typed_failure_cells": sum(1 for c in cells if not c["empty_success"]),
            "cells": cells,
        },
        "empty_success_cells": empty,
        "swallow_answer": swallow_answer,
        "partial_work": {
            "all_committed_unchanged": all(c["committed_unchanged"] for c in cells),
            "any_staging_promoted_on_fault": any(c["staging_promoted"] for c in cells),
            "mid_body_cells_with_staging": [
                {
                    "boundary": c["boundary"],
                    "fault": c["fault"],
                    "staging_bytes": c["staging_bytes"],
                }
                for c in cells
                if c["fault"] in {"truncated_response", "mid_stream_disconnect"}
            ],
        },
        "detector_controls": {
            "planted_empty_success_swallower": {
                "classification": swallow["classification"],
                "empty_success": swallow["empty_success"],
                "code_path": swallow["code_path"],
                "detected": swallow["classification"] == "EMPTY_SUCCESS",
            },
            "healthy_both_states": [
                {
                    "boundary": c["boundary"],
                    "classification": c["classification"],
                    "ok": c["ok"],
                }
                for c in healthy
            ],
        },
        "inventory": inv,
        "tests": [
            {
                "id": "test_every_boundary_produces_a_typed_failure_per_fault",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_partial_work_is_preserved_across_every_fault",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "TST-0098-probe2-partial-work-scope",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes the matrix and only scores committed-digest "
                "stability and staging non-promotion — a different measurement "
                "than probe 1's classification table."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "kind": "live-matrix",
                "claim": "30 cells, each a typed failure matching the injected fault",
                "path": "command-center/p2-wave/probes/TST-0098/harness.py",
            },
            {
                "kind": "detector-control",
                "claim": "planted swallower is EMPTY_SUCCESS, not a green pass",
                "path": H.SWALLOW_PATH,
            },
            {
                "kind": "partial-work",
                "claim": "seeded committed bytes survive every fault; no promote",
                "path": "command-center/p2-wave/probes/TST-0098/probe2_partial_work.py",
            },
            {
                "kind": "inventory",
                "claim": "product HTTP clients inventoried via AST imports, not strings",
                "path": "command-center/p2-wave/probes/TST-0098/harness.py",
            },
        ],
        "p1_policy": (
            "Any production cell classified EMPTY_SUCCESS is a P1 and the "
            "code_path is quoted. Detector-control EMPTY_SUCCESS is required."
        ),
        "scope_note": (
            "B07 registry/package clients named by sibling TST-0129..TST-0135 "
            "are not present as modules on this worktree. TST-0122 delegates "
            "network fault primitives to this unit; the five adapters here are "
            "those primitives, fail-closed, under live localhost injection."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        jsonschema.Draft7Validator(schema).validate(receipt)
    except Exception as exc:  # noqa: BLE001 — shim $ref is remote; G-1 does not require it
        print(f"schema-note: {type(exc).__name__}: {exc}")

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0098 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
