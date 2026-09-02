#!/usr/bin/env python3
"""Named probe 1: two independent rails per claim, live sha256, control table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    SENTINEL,
    UNIT,
    artifact_errors,
    artifact_path,
    load_artifact,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0026-probe1 {msg}")
    return 1


def main() -> int:
    path = artifact_path()
    if not path.is_file() or path.stat().st_size <= 0:
        return fail("artifact missing")
    doc = load_artifact()
    errs = artifact_errors(doc, require_live_hash=True)
    if errs:
        return fail("; ".join(errs[:12]))
    table = doc["control_table"]
    server = [
        r for r in table if r.get("client_vs_server_enforcement") == "SERVER-ENFORCED"
    ]
    if SENTINEL not in path.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    out = {
        "probe": "probe1-two-rails-and-table",
        "unit_id": UNIT,
        "claims": len(doc["claims"]),
        "control_rows": len(table),
        "server_enforced_rows": len(server),
        "each_claim_two_hosts": True,
        "live_sha256_matched": True,
        "quotes_in_captures": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"SUCCESS:RES-0026-probe1 claims={out['claims']} "
        f"server_enforced={out['server_enforced_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
