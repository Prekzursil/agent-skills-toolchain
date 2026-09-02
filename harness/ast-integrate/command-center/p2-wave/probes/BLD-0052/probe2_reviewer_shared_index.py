#!/usr/bin/env python3
"""Probe 2: independent reviewer reproduces two ARMED shipped guards + shared-index."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0052.json"
SHIPPED = (
    REPO / "tools" / "command-center" / "seed.py",
    REPO / "tools" / "command-center" / "close.py",
)


def main() -> int:
    for path in SHIPPED:
        if not path.is_file():
            print(f"FAILED:BLD-0052-probe2 shipped missing {path}")
            return 1
        # Reviewer uses the shipped path, not a copied fixture of the guard.
        if "fixtures" in path.parts:
            print(f"FAILED:BLD-0052-probe2 refused to use a fixture copy {path}")
            return 1
    live = M.run_campaign()
    view = M.comparison_view(live)
    print(json.dumps({"shared_index": view["shared_index"], "armed": view["armed_guards"]}, sort_keys=True))
    if not ART.is_file():
        print("FAILED:BLD-0052-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0052-probe2 self-declared {doc.get('state')}")
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        print(f"FAILED:BLD-0052-probe2 reviewer {rev}")
        return 1
    reproduced = list(rev.get("reproduced_guards") or [])
    need = ["seed-force-overwrite", "close-blank-evidence"]
    if reproduced != need and set(reproduced) != set(need):
        print(f"FAILED:BLD-0052-probe2 reproduced_guards {reproduced}")
        return 1
    for gid in need:
        g = view["armed_guards"].get(gid) or {}
        if g.get("status") != "ARMED" or not g.get("refused_on_bad"):
            print(f"FAILED:BLD-0052-probe2 shipped reproduction {gid} {g}")
            return 1
        # Confirm the live campaign invoked the shipped file, not a copy.
        live_g = live["guards"][gid]
        shipped_path = str(live_g.get("shipped_path") or "")
        if shipped_path not in {
            "tools/command-center/seed.py",
            "tools/command-center/close.py",
        }:
            print(f"FAILED:BLD-0052-probe2 not shipped path {gid} {shipped_path}")
            return 1
    shared = view["shared_index"]
    if not (
        shared["same_tree_broad_add_contaminates"]
        and shared["scoped_add_isolates"]
        and shared["worktree_isolates"]
        and shared["planted_contamination_detected"]
    ):
        print(f"FAILED:BLD-0052-probe2 shared-index {shared}")
        return 1
    art_shared = doc.get("shared_index") or {}
    for key in (
        "same_tree_broad_add_contaminates",
        "scoped_add_isolates",
        "worktree_isolates",
        "planted_contamination_detected",
    ):
        if art_shared.get(key) != shared[key]:
            print(f"FAILED:BLD-0052-probe2 shared drift {key}")
            return 1
    print(
        "reviewer reproduced seed.py --force and close.py --evidence from shipped "
        f"tools/; shared_index contaminates={shared['same_tree_broad_add_contaminates']} "
        f"worktree_isolates={shared['worktree_isolates']}"
    )
    print("SUCCESS:BLD-0052-probe2 shipped-guard reproduction shared-index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
