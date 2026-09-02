#!/usr/bin/env python3
"""Named probe 1: suite is green on the repaired tree (evidence A)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    ARTIFACT_REL,
    REPO,
    SENTINEL,
    load_artifact,
    repaired_tree,
    run_suite,
)


def main() -> int:
    art = REPO / ARTIFACT_REL
    if not art.is_file() or art.stat().st_size < 200:
        print("FAILED:WFA-0092-probe1 artifact missing")
        return 1
    doc = load_artifact(REPO)
    if doc.get("unit_id") != "WFA-0092":
        print("FAILED:WFA-0092-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in art.read_text(encoding="utf-8"):
        print("FAILED:WFA-0092-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0092-probe1 self-declared {st}")
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0092-p1-") as td:
        live = run_suite(repaired_tree(), Path(td))

    if live.scanner.get("ok") is not True:
        print("FAILED:WFA-0092-probe1 scanner both-states dead")
        print(json.dumps(live.scanner, indent=2))
        return 1
    red = [r.id for r in live.rows if not r.ok]
    if not live.green or red:
        print(f"FAILED:WFA-0092-probe1 suite not green red={red}")
        return 1
    if not doc.get("suite", {}).get("green_on_repaired_tree"):
        print("FAILED:WFA-0092-probe1 artifact baseline not green")
        return 1
    recorded = {r["defect_id"]: r["ok"] for r in doc["suite"]["rows"]}
    live_map = {r.id: r.ok for r in live.rows}
    if recorded != live_map:
        print("FAILED:WFA-0092-probe1 artifact rows != live recompute")
        print(json.dumps({"recorded": recorded, "live": live_map}, indent=2))
        return 1

    print(json.dumps({
        "probe": "probe1-suite-green",
        "unit_id": "WFA-0092",
        "green": True,
        "defect_count": len(live.rows),
        "scanner_ok": True,
        "pass": True,
    }, sort_keys=True))
    print(f"green={live.green} defects={len(live.rows)} scanner_ok={live.scanner['ok']}")
    print("SUCCESS:WFA-0092-probe1 repaired-tree suite green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
