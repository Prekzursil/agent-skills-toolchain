#!/usr/bin/env python3
"""Probe 1: reconstruct each historical layout, migrate, byte-compare to clean+user data."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_scenario  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0077.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0077-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:TST-0077" not in blob:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = run_scenario()
    t1 = live["tests"]["test_migration_from_each_reconstructed_layout"]
    if not t1["pass"]:
        print(json.dumps(t1, indent=2, default=str)[:4000])
        return fail("migration-from-each-layout")
    if not live.get("current_layout_matches_zero_legacy_fingerprints"):
        return fail("current-layout-still-matches-a-legacy-fingerprint")
    if len(live.get("historical_layouts_with_path") or []) < 4:
        return fail("expected four migratable historical layouts")

    rec_t1 = (doc.get("tests") or {}).get("test_migration_from_each_reconstructed_layout") or {}
    if rec_t1.get("pass") is not True:
        return fail("artifact t1 pass is not true")
    rec_answer = doc.get("answer") or {}
    if rec_answer.get("which_historical_layouts_exist") != live["answer"]["which_historical_layouts_exist"]:
        return fail("artifact layout census drifted from live")

    print(
        json.dumps(
            {
                "probe": "probe1-reconstruct-migrate",
                "pass": True,
                "layouts": t1["layouts"],
                "reconstruction_method": live.get("reconstruction_method"),
                "git_head": (live.get("git") or {}).get("head"),
            },
            sort_keys=True,
        )
    )
    for row in t1["layouts"]:
        print(
            f"layout {row['id']} byte_eq={row['byte_equivalent']} "
            f"current={row['after_is_current']} steps={row['steps_run']}"
        )
    print("SUCCESS:TST-0077-probe1 reconstruct migrate byte-equivalence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
