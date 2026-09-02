#!/usr/bin/env python3
"""Probe 1: id-existence and Kahn topological sort on declared edges.

Control (scratch copy): a two-item cycle plus one dangling id must report
exactly one cycle and exactly one dangling id. A clean copy must be silent.
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
    print(f"FAILED:{UNIT}-probe1 {msg}")
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
        "scratch-exactly-one-dangling-id",
        bad["dangling_ids"] == ["X-MISSING"] and bad["dangling_edge_count"] == 1,
        f"dangling_ids={bad['dangling_ids']} edges={bad['dangling_edge_count']}",
    )
    check(
        "scratch-exactly-one-cycle",
        bad["cycle_count"] == 1 and set(bad["cycle_nodes"]) == {"X-A", "X-B"},
        f"cycle_count={bad['cycle_count']} nodes={bad['cycle_nodes']}",
    )
    check(
        "scratch-kahn-residual-is-the-cycle",
        set(bad["kahn_residual"]) == {"X-A", "X-B"},
        f"kahn_residual={bad['kahn_residual']}",
    )
    check(
        "scratch-dangling-dependent-looks-like-a-kahn-root",
        "X-C" in bad["naive_kahn_roots_including_dangling_dependents"]
        and "X-C" in bad["kahn_order"],
        "Kahn drops X-MISSING so X-C peels as a root — the hole Probe 2 closes",
    )
    check(
        "clean-silent",
        good["dangling_edge_count"] == 0
        and good["cycle_count"] == 0
        and good["acyclic"] is True,
        f"dangling={good['dangling_edge_count']} cycles={good['cycle_count']}",
    )
    check(
        "live-items-ids-exist",
        live["all_existing_ids_named"] is True and live["dangling_edge_count"] == 0,
        f"items nodes={live['node_count']} edges={live['edge_count']} dangling={live['dangling_edge_count']}",
    )
    check(
        "live-items-acyclic",
        live["acyclic"] is True and live["cycle_count"] == 0 and not live["kahn_residual"],
        f"acyclic={live['acyclic']} residual={live['kahn_residual']}",
    )
    check(
        "live-kahn-orders-every-item",
        len(live["kahn_order"]) == live["node_count"],
        f"order={len(live['kahn_order'])} nodes={live['node_count']}",
    )

    payload = {
        "probe": "probe1-id-existence-topo",
        "unit_id": UNIT,
        "pass": all(c["ok"] for c in checks),
        "checks": checks,
        "live": {
            "node_count": live["node_count"],
            "edge_count": live["edge_count"],
            "dangling_ids": live["dangling_ids"],
            "cycle_count": live["cycle_count"],
            "kahn_order_len": len(live["kahn_order"]),
        },
        "scratch_bad": {
            "dangling_ids": bad["dangling_ids"],
            "cycle_count": bad["cycle_count"],
            "cycle_nodes": bad["cycle_nodes"],
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not payload["pass"]:
        return fail("control or live Kahn/existence check failed")
    print(
        f"SUCCESS:{UNIT}-probe1 id-existence + Kahn; "
        f"scratch cycle=1 dangling=1; live items dangling=0 cycles=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
