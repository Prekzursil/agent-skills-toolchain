"""Shared IMP-0156 scenario: materialise fixtures and score the live extractor."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.license_extract import (  # noqa: E402
    UNKNOWN,
    extract_licence,
    normalize_to_spdx,
    redistribution_gate,
)
from control_set import CONTROL, silent_default_traps  # noqa: E402


def materialize(dest: Path, spec: dict[str, Any]) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for rel, content in spec["files"].items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return dest


def evaluate_control_set(tmp: Path) -> dict[str, Any]:
    if len(CONTROL) != 20:
        return {
            "pass": False,
            "matched": 0,
            "total": len(CONTROL),
            "error": f"control set size {len(CONTROL)} want=20",
            "rows": [],
        }
    rows: list[dict[str, Any]] = []
    matched = 0
    for spec in CONTROL:
        root = materialize(tmp / spec["id"], spec)
        rec = extract_licence(root)
        hit = rec["spdx_id"] == spec["expected"]
        matched += int(hit)
        rows.append(
            {
                "id": spec["id"],
                "expected": spec["expected"],
                "got": rec["spdx_id"],
                "method": rec["method"],
                "source_path": rec["source_path"],
                "match": hit,
            }
        )
    return {
        "pass": matched == 20,
        "matched": matched,
        "total": 20,
        "rows": rows,
    }


def evaluate_silent_default(tmp: Path) -> dict[str, Any]:
    traps = silent_default_traps()
    rows: list[dict[str, Any]] = []
    ok = True
    for spec in traps:
        rec = extract_licence(materialize(tmp / spec["id"], spec))
        coerced = rec["spdx_id"] in {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"}
        hit = rec["spdx_id"] == UNKNOWN and not coerced
        ok = ok and hit
        rows.append(
            {
                "id": spec["id"],
                "expected": UNKNOWN,
                "got": rec["spdx_id"],
                "method": rec["method"],
                "coerced_to_permissive": coerced,
                "match": hit,
            }
        )
    word = normalize_to_spdx("permissive")
    empty = normalize_to_spdx("")
    ok = ok and word == UNKNOWN and empty == UNKNOWN
    rows.append(
        {
            "id": "normalize-permissive-word",
            "expected": UNKNOWN,
            "got": word,
            "match": word == UNKNOWN,
        }
    )
    rows.append(
        {
            "id": "normalize-empty",
            "expected": UNKNOWN,
            "got": empty,
            "match": empty == UNKNOWN,
        }
    )
    return {"pass": ok, "rows": rows}


def evaluate_redistribution_gate(tmp: Path) -> dict[str, Any]:
    none_spec = {
        "id": "licence-less",
        "files": {"README.md": "# workflow candidate with no licence\n"},
    }
    twin_spec = {
        "id": "permissive-twin",
        "files": {
            "README.md": "# workflow candidate with no licence\n",
            "LICENSE": CONTROL[0]["files"]["LICENSE"],
        },
    }
    unknown_rec = extract_licence(materialize(tmp / "licence-less", none_spec))
    twin_rec = extract_licence(materialize(tmp / "permissive-twin", twin_spec))
    unknown_gate = redistribution_gate(unknown_rec)
    twin_gate = redistribution_gate(twin_rec)
    # Direct API call, not a reimplementation.
    unknown_gate2 = redistribution_gate(UNKNOWN)
    ok = (
        unknown_rec["spdx_id"] == UNKNOWN
        and unknown_rec["blocked_from_redistribution"] is True
        and unknown_gate["allowed"] is False
        and unknown_gate["reason"] == "UNKNOWN-LICENCE-BLOCKS-REDISTRIBUTION"
        and unknown_gate2["allowed"] is False
        and twin_rec["spdx_id"] == "MIT"
        and twin_rec["blocked_from_redistribution"] is False
        and twin_gate["allowed"] is True
        and twin_gate["reason"] == "LICENCE-TERMS-KNOWN"
    )
    return {
        "pass": ok,
        "unknown": {
            "record": unknown_rec,
            "gate": unknown_gate,
        },
        "permissive_twin": {
            "record": twin_rec,
            "gate": twin_gate,
        },
    }
