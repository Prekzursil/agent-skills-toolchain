#!/usr/bin/env python3
"""Probe 2: independently recomputed reachability from terminal dispositions.

Mechanically different from Probe 1: Kosaraju SCCs + reverse BFS from items
that already carry a terminal disposition. Missing ids are not nodes, so a
unit reachable only through a dangling id cannot enter the closure.

Also cross-checks Probe 1's cycle/dangling counts so a silent Kahn hole
cannot pass as 'reachable'.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

UNIT = "AUD-0039"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    live = E.analyze_items(E.load_json(E.repo_catalog_path()))
    bad = E.analyze_items(E.fixture("control_cycle_and_dangling.json"))
    good = E.analyze_items(E.fixture("control_clean.json"))

    checks = []

    def check(cid: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "ok": ok, "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} {cid} {detail}")

    check(
        "scratch-dangling-id-is-not-a-node",
        "X-MISSING" not in bad["reachable_from_terminals"]
        and "X-MISSING" not in bad["kahn_order"]
        and bad["dangling_ids"] == ["X-MISSING"],
        f"dangling={bad['dangling_ids']} reachable={bad['reachable_from_terminals']}",
    )
    check(
        "scratch-X-C-not-reachable-from-terminals",
        "X-C" not in bad["reachable_from_terminals"]
        and "X-C" in bad["dangling_only_dependents"],
        "X-C's only declared edge targets a missing id; closure must exclude it",
    )
    check(
        "scratch-kahn-would-have-counted-X-C",
        "X-C" in bad["kahn_order"] and "X-C" in bad["naive_kahn_roots_including_dangling_dependents"],
        "independence: Kahn peels X-C; reverse-closure from terminals does not",
    )
    check(
        "scratch-X-OK-reachable-X-cycle-not",
        "X-OK" in bad["reachable_from_terminals"]
        and "X-TERM" in bad["reachable_from_terminals"]
        and "X-A" not in bad["reachable_from_terminals"]
        and "X-B" not in bad["reachable_from_terminals"],
        f"reachable={bad['reachable_from_terminals']}",
    )
    check(
        "scratch-kosaraju-one-cycle",
        bad["cycle_count"] == 1 and set(bad["cycle_nodes"]) == {"X-A", "X-B"},
        f"cycle_count={bad['cycle_count']} nodes={bad['cycle_nodes']}",
    )
    check(
        "clean-both-reachable",
        set(good["reachable_from_terminals"]) == {"G-TERM", "G-CHILD"}
        and good["unreachable_count"] == 0
        and good["cycle_count"] == 0,
        f"reachable={good['reachable_from_terminals']} unreach={good['unreachable_count']}",
    )
    check(
        "live-kahn-vs-kosaraju-cycle-agreement",
        live["cycle_count"] == 0 and not live["kahn_residual"] and live["acyclic"] is True,
        f"cycles={live['cycle_count']} residual={live['kahn_residual']}",
    )
    check(
        "live-closure-subset-of-existing",
        set(live["reachable_from_terminals"]).issubset(set(live["kahn_order"]))
        and live["reachable_count"] + live["unreachable_count"] == live["node_count"],
        f"reachable={live['reachable_count']} unreach={live['unreachable_count']} nodes={live['node_count']}",
    )
    check(
        "live-terminals-are-reachable",
        set(live["terminal_ids"]).issubset(set(live["reachable_from_terminals"])),
        f"terminals={live['terminal_count']} missing_from_closure={sorted(set(live['terminal_ids']) - set(live['reachable_from_terminals']))[:8]}",
    )

    payload = {
        "probe": "probe2-reachability-closure",
        "unit_id": UNIT,
        "pass": all(c["ok"] for c in checks),
        "independent_of": "probe1-Kahn",
        "method": "Kosaraju SCCs + reverse BFS from terminal-disposition items; dangling ids are not nodes",
        "checks": checks,
        "live": {
            "terminal_count": live["terminal_count"],
            "reachable_count": live["reachable_count"],
            "unreachable_count": live["unreachable_count"],
            "all_reachable_from_terminals": live["all_reachable_from_terminals"],
            "unreachable_head": live["unreachable_from_terminals"][:24],
        },
        "scratch_bad": {
            "reachable_from_terminals": bad["reachable_from_terminals"],
            "dangling_only_dependents": bad["dangling_only_dependents"],
            "cycle_nodes": bad["cycle_nodes"],
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not payload["pass"]:
        return fail("reachability closure or independence control failed")
    print(
        f"SUCCESS:{UNIT}-probe2 reverse-closure from terminals; "
        f"scratch X-C excluded; live reachable={live['reachable_count']}/"
        f"{live['node_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
