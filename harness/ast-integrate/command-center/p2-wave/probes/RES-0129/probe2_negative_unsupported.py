#!/usr/bin/env python3
"""Probe 2: at least one UNSUPPORTED per client; dual rails on measured claims."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from contract import CLIENTS, cell_map, errors_for, load_art, validate_schema  # noqa: E402
import extract as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0129-probe2 {msg}")
    return 1


def main() -> int:
    doc = load_art()
    validate_schema(doc)
    live = E.extract_all()
    errs = errors_for(doc, live)
    cmap = cell_map(doc)
    per_client = {}
    for client in CLIENTS:
        unsupported = [
            concept
            for concept, cell in ((k[1], cmap.get((client, k[1]))) for k in cmap if k[0] == client)
            if cell and cell.get("status") == "UNSUPPORTED"
        ]
        per_client[client] = unsupported
        if not unsupported:
            return fail(f"{client} has no UNSUPPORTED concept (all-green row)")
    print(
        json.dumps(
            {
                "probe": "probe2-negative-unsupported",
                "errors": errs,
                "unsupported_per_client": per_client,
                "common_subset": (doc.get("largest_common_subset") or {}).get("concepts"),
            },
            sort_keys=True,
        )
    )
    if errs:
        return fail(";".join(errs[:10]))
    print("unsupported_ok=True dual_rails_ok=True")
    print("SUCCESS:RES-0129-probe2 each client has UNSUPPORTED; dual rails hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
