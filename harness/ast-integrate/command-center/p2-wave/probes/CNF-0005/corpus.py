#!/usr/bin/env python3
"""Implementation-receipt corpus for CNF-0005.

Live receipt directories are empty on this worktree. The 100-brief scan uses
a seeded synthetic corpus so the empty live set cannot be read as a pass.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SEED = 20260824
N_BRIEFS = 100
INJECT_INDEX = 37

LIVE_ROOTS = (
    REPO / "command-center" / "receipts",
    REPO / "command-center" / "events",
    REPO / "command-center" / "confirmation",
)

BANDS = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)


def synthetic_receipt(i: int) -> dict[str, Any]:
    """One implementation receipt with distinctive denied-field needles."""
    cid = f"CLM-CNF0005-{i:04d}"
    src_path = f"fixtures/synthetic/widget_{i:04d}.py"
    src_text = (
        f"# widget_{i:04d}\n"
        f"def hash_bytes(payload: bytes) -> str:\n"
        f"    import hashlib\n"
        f"    return hashlib.sha256(payload).hexdigest()\n"
        f"# public API only; no implementer verdict in this file\n"
    )
    tests = [
        {
            "id": f"T-{i:04d}-a",
            "command": f"python3 -c \"from widget_{i:04d} import hash_bytes; print(hash_bytes(b'x'))\"",
            "recorded_output": "placeholder-sha-not-a-verdict",
        },
        {
            "id": f"T-{i:04d}-b",
            "command": f"python3 -c \"from widget_{i:04d} import hash_bytes; print(len(hash_bytes(b'y')))\"",
            "recorded_output": "64",
        },
    ]
    needle = f"NEEDLE-CNF0005-IMPL-{i:04d}"
    prose_needle = f"NEEDLE-CNF0005-PROSE-{i:04d}"
    table_needle = f"NEEDLE-CNF0005-TABLE-{i:04d}"
    return {
        "claim_id": cid,
        "claim_statement": (
            f"Widget {i:04d} hashes an input payload with SHA-256 and returns "
            f"the lowercase hex digest of that payload and no other bytes."
        ),
        "raw_source": {
            "path": src_path,
            "text": src_text,
        },
        "tests": tests,
        "implementer_conclusion": (
            f"{needle} CONFIRMED production-ready; ship widget {i:04d} without "
            f"further confirmer work."
        ),
        "receipt_prose": (
            f"We observed a clean local run and therefore recommend ship. "
            f"{prose_needle} This paragraph is implementer narrative, not source."
        ),
        "confidence_band": BANDS[i % len(BANDS)],
        "summary_table": [
            {
                "metric": "pass_rate",
                "value": "100%",
                "note": table_needle,
            }
        ],
        "verdict": "DONE",
        "agent_id": f"impl-agent-{i:04d}",
        "prior_confirmation": None,
    }


def live_receipts() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for root in LIVE_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            if path.name.startswith("CNF-0005"):
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(doc, dict) and "claim_id" in doc and "claim_statement" in doc:
                found.append(doc)
    return found


def load_corpus() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    live = live_receipts()
    syn = [synthetic_receipt(i) for i in range(N_BRIEFS)]
    meta = {
        "seed": SEED,
        "live_receipt_count": len(live),
        "synthetic_receipt_count": len(syn),
        "used_for_scan": len(syn),
        "inject_index": INJECT_INDEX,
        "empty_live_corpus_stated": len(live) == 0,
        "live_roots": [str(p.relative_to(REPO).as_posix()) if p.exists() else str(p) for p in LIVE_ROOTS],
    }
    return syn, meta
