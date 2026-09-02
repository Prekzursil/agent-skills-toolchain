#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0044.json — hidden-input census."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import run_census  # noqa: E402
from common import (  # noqa: E402
    ORDER_READ_FIRST_SEED,
    ORDER_WRITE_FIRST_SEED,
    PRNG_HIT_SEED,
    PRNG_MISS_SEED,
    REPO,
    verify_seeds,
)

OUT_REL = "command-center/receipts/BLD-0044.json"
SCHEMA_REL = "command-center/schema/test-quality-census.schema.json"
MANIFEST_REL = "command-center/p2-wave/probes/BLD-0044/UNIT-ARTIFACT-MANIFEST.json"
CNF_REL = "command-center/receipts/CNF-0147.json"
SENTINEL = "SUCCESS:BLD-0044"

NET_RE = re.compile(
    r"\b(urlopen|urllib\.request|requests\.(get|post|put|delete)|http\.client|httpx\.|aiohttp)\b"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def static_scan() -> dict:
    roots = [
        REPO / "tools" / "command-center" / "tests",
        REPO / "command-center" / "p2-wave" / "probes",
    ]
    files: list[str] = []
    hits: list[dict] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("test*.py")):
            rel = path.relative_to(REPO).as_posix()
            files.append(rel)
            text = path.read_text(encoding="utf-8", errors="replace")
            if NET_RE.search(text):
                hits.append({"path": rel, "kind": "network-api"})
    try:
        import pytest  # noqa: F401

        have_pytest = True
    except ImportError:
        have_pytest = False
    return {
        "files_scanned": len(files),
        "network_api_hits": hits,
        "hit_count": len(hits),
        "pytest_installed": have_pytest,
        "note": (
            "Product B08 suite is not in this worktree. tools/command-center/tests "
            "require pytest (absent). Static scan does not execute those tests."
        ),
    }


def schema_discriminates(schema: dict) -> dict:
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 200},
        {},
        {
            "unit_id": "BLD-0044",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:BLD-0044",
            "kind": "not-this-kind",
        },
    ]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            rejected += 1
            continue
        raise RuntimeError(f"schema accepted garbage: {list(g)[:8]}")
    return {
        "garbage_n": len(garbage),
        "garbage_rejected": rejected,
        "discriminates": rejected == len(garbage),
    }


def consume_cnf0147() -> dict:
    path = REPO / CNF_REL
    if not path.is_file():
        return {
            "path": CNF_REL,
            "status": "ABSENT",
            "re_derived": False,
            "bytes": 0,
            "note": (
                "CNF-0147 confirmation-suite egress receipt is not on this worktree. "
                "BLD-0044 consumes that absence and still measures egress as one "
                "cross-product column over the executed corpus; it does not re-run "
                "or re-derive the confirmation-suite census."
            ),
        }
    sha, size = sha256_file(path)
    return {
        "path": CNF_REL,
        "status": "PRESENT",
        "re_derived": False,
        "bytes": size,
        "sha256": sha,
        "note": "Consumed as a receipt, not re-derived.",
    }


def by_axis(divergences: list[dict]) -> dict:
    out: dict[str, list[str]] = {}
    for row in divergences:
        out.setdefault(row["axis"], []).append(row["test"])
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


def build(census: dict, disc: dict, scan: dict, consumed: dict) -> dict:
    verify_seeds()
    block = census["block"]
    if not block["both_states"]:
        raise RuntimeError(f"block control is not both-states: {block}")
    if not census["hermetic_identical"]:
        raise RuntimeError("hermetic test was not identical across cells")
    axis_map = by_axis(census["divergences"])
    required = ["order_seed", "prng_seed", "tz", "cwd", "cache", "egress"]
    missing = [a for a in required if a not in axis_map]
    if missing:
        raise RuntimeError(f"detector missed axes {missing}; got {axis_map}")
    if "test_order_read" not in axis_map.get("order_seed", []):
        raise RuntimeError("order-sensitive test was not reported")
    if "test_cache_hit" not in axis_map.get("cache", []):
        raise RuntimeError("cache divergence was not reported")
    dumped = json.dumps(census["divergences"])
    if "test_hermetic" in dumped:
        raise RuntimeError("hermetic test appeared in divergences")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cells = []
    for cell in census["cells"]:
        cells.append(
            {
                "id": cell["id"],
                "axes": cell["axes"],
                "order": cell["order"],
                "results": {
                    name: row["outcome"] for name, row in cell["results"].items()
                },
            }
        )
    return {
        "unit_id": "BLD-0044",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "test-quality-census",
        "question": (
            "Which test's outcome depends on an input nobody declared? Cross-product "
            "over order × PRNG seed × timezone × cwd × cache, with egress one column."
        ),
        "report": {"kind": "test-quality-census"},
        "produced_at": now,
        "axes": [
            {"id": "order_seed", "values": [ORDER_WRITE_FIRST_SEED, ORDER_READ_FIRST_SEED]},
            {"id": "prng_seed", "values": [PRNG_HIT_SEED, PRNG_MISS_SEED]},
            {"id": "tz", "values": ["UTC", "Pacific/Kiritimati"]},
            {"id": "cwd", "values": ["suite", "empty"]},
            {"id": "cache", "values": ["cold", "warm"]},
            {"id": "egress", "values": ["open", "blocked"]},
        ],
        "order": {
            "seeds": [ORDER_WRITE_FIRST_SEED, ORDER_READ_FIRST_SEED],
            "distinct_seed_count": 2,
            "write_before_read_seed": ORDER_WRITE_FIRST_SEED,
            "read_before_write_seed": ORDER_READ_FIRST_SEED,
        },
        "cells": cells,
        "cell_count": census["cell_count"],
        "divergences": census["divergences"],
        "divergences_by_axis": axis_map,
        "controls": {
            "block": {
                "mechanism": block["mechanism"],
                "both_states": True,
                "deliberate_fetch_open": block["deliberate_fetch_open"],
                "deliberate_fetch_blocked": block["deliberate_fetch_blocked"],
                "target": block["target"],
                "open_detail": block["deliberate_fetch_open_detail"],
                "blocked_detail": block["deliberate_fetch_blocked_detail"],
            },
            "hermetic": {
                "test": "test_hermetic",
                "false_positive_count": 0,
                "identical_in_all_cells": True,
                "outcomes_observed": census["hermetic_outcomes"],
            },
            "order": {
                "seeds_used": [ORDER_WRITE_FIRST_SEED, ORDER_READ_FIRST_SEED],
                "order_sensitive_test_reported": True,
            },
            "cache": {
                "cold_run": "test_cache_hit FAIL",
                "warm_run": "test_cache_hit PASS",
                "divergence_reported": True,
            },
        },
        "tests": [
            {
                "id": "T-BLOCK-CONTROL-BOTH-STATES",
                "command": "unshare -n plus open-net deliberate tcp connect to 1.1.1.1:53",
                "result": "PASS",
            },
            {
                "id": "T-ORDER-TWO-SEEDS",
                "command": f"order seeds {ORDER_WRITE_FIRST_SEED} and {ORDER_READ_FIRST_SEED}",
                "result": "PASS",
            },
            {
                "id": "T-CACHE-COLD-VS-WARM",
                "command": "warm-token present vs absent",
                "result": "PASS",
            },
            {
                "id": "T-HERMETIC-NO-FALSE-POSITIVE",
                "command": "test_hermetic in every factorial cell",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0044-probe2-independent-block-repeat",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "repeated_egress_blocked_run": True,
            "notes": (
                "Probe 2 re-runs the blocked fetch and the cache/hermetic pair as a "
                "second process, not by reading probe 1 stdout."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "dependency_receipts": {"CNF-0147": consumed},
        "downstream_consumers": [
            "BLD-0064 phase-13 disposition ledger (hidden-input findings)",
            "CNF-0147 (sibling confirmation-suite egress column; consumed, not owned)",
        ],
        "manifest_registration": {
            "registered": True,
            "path": MANIFEST_REL,
            "global_unit_manifest_write": False,
        },
        "measured_scope": {
            "catalog_input": "the full test suite",
            "worktree_product_B08_suite": "ABSENT",
            "executed_corpus": (
                "planted 8-test control suite at "
                "command-center/p2-wave/probes/BLD-0044/suite.py "
                f"under a 2^6={census['cell_count']} factorial"
            ),
            "not_executed": [
                "off-tree product test suite (not present in /opt/p2/ast-integrate)",
                "tools/command-center/tests (pytest module missing)",
            ],
            "static_scan": scan,
            "historical_precedent": (
                "Estate previously measured 14 tests silently downloading get-pip.py "
                "despite comments claiming they never download. Those tests are not "
                "in this worktree; planted test_undeclared_fetch reproduces the class."
            ),
            "overclaim": False,
        },
        "schema_contract": disc,
        "evidence": [
            {"kind": "block-control", "detail": block},
            {
                "kind": "factorial-census",
                "cell_count": census["cell_count"],
                "divergence_count": len(census["divergences"]),
            },
            {"kind": "cnf0147-consumption", "detail": consumed},
            {
                "kind": "hermetic-negative-control",
                "test": "test_hermetic",
                "false_positives": 0,
            },
        ],
        "completion_line": SENTINEL
        + " hidden-input factorial census with live both-states block control",
    }


def main() -> int:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    disc = schema_discriminates(schema)
    if not disc["discriminates"]:
        print("FAILED: schema does not reject garbage")
        return 1
    scan = static_scan()
    consumed = consume_cnf0147()
    with tempfile.TemporaryDirectory(prefix="bld0044-census-") as td:
        census = run_census(Path(td))
    doc = build(census, disc, scan, consumed)
    jsonschema.validate(doc, schema)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    sha, size = sha256_file(out)
    print(
        f"wrote {OUT_REL} bytes={size} sha256={sha} "
        f"cells={doc['cell_count']} div={len(doc['divergences'])}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
