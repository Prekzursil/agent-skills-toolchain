#!/usr/bin/env python3
"""Probe 2: independent reviewer queries on surfaces the author's set
does not obviously cover, plus live-estate honesty (no GENUINELY-NEW
when a required surface was not enumerated).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import git_fixture as G  # noqa: E402
import mechanism as M  # noqa: E402
import surfaces as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0033.json"
AUTHOR_QUERIES = {
    "identifier-normalized w-shingles (w=5) Jaccard",
    "export-name token search (strike-1; not load-bearing)",
}


def main() -> int:
    git_repo = G.build_history_repo()
    try:
        # Reviewer query 1: pickaxe on the deleted-only symbol (git history),
        # not shingle comparison of rebuilds vs tools/lib.
        hist = S.git_history_deleted(git_repo, M.DELETED_SYMBOL)
        q1 = (
            hist.get("found_in_deleted") is True
            and hist.get("found_in_head") is False
            and hist.get("status") == "enumerated"
        )
        print(
            f"reviewer_q1_git_pickaxe ok={q1} path={hist.get('deleted_path')} "
            f"head={hist.get('found_in_head')}"
        )
        if not q1:
            print("FAILED:BLD-0033-probe2 git pickaxe did not isolate deleted symbol")
            return 1

        # Reviewer query 2: inventory glob for SKILL.md / plugin.json, which
        # the author's classifier does not treat as a mechanism subject.
        inv = S.inventory_surface(
            [
                HERE / "fixtures/estate/live-claude",
                HERE / "fixtures/estate/live-agents",
                HERE / "fixtures/estate/inventory",
            ]
        )
        q2 = inv.get("status") == "enumerated" and inv.get("count", 0) >= 2
        print(f"reviewer_q2_inventory ok={q2} count={inv.get('count')} paths={inv.get('paths')}")
        if not q2:
            print("FAILED:BLD-0033-probe2 inventory surface empty")
            return 1

        # Reviewer query 3: host live trees as actually present or honestly absent.
        # Author compared fixture live-claude; reviewer probes ~/.claude and ~/.agents.
        host = S.host_surfaces(REPO)
        live_c = host["live_claude"]["status"]
        live_a = host["live_agents"]["status"]
        q3 = live_c in {"enumerated", "absent"} and live_a in {"enumerated", "absent"}
        print(
            f"reviewer_q3_host_live claude={live_c} agents={live_a} "
            f"claude_files={host['live_claude'].get('file_count')} "
            f"agents_files={host['live_agents'].get('file_count')}"
        )
        if not q3:
            print("FAILED:BLD-0033-probe2 host live surface status invalid")
            return 1
    finally:
        shutil.rmtree(git_repo, ignore_errors=True)

    live = C.live_census(REPO)
    missing = live.get("surfaces_missing") or []
    print(
        f"live_b07={live['b07_input']['status']} "
        f"surfaces_complete={live['surfaces_complete']} missing={missing}"
    )
    if not live["surfaces_complete"]:
        illegal = [
            e
            for e in live["entries"]
            if e.get("verdict") == "GENUINELY-NEW"
        ]
        if illegal:
            print("FAILED:BLD-0033-probe2 GENUINELY-NEW despite missing surfaces")
            print(json.dumps(illegal[:3], indent=2, default=str)[:1500])
            return 1
        print("live_genuinely_new_forbidden_ok=True")

    if ART.is_file():
        rec = json.loads(ART.read_text(encoding="utf-8"))
        reviewer = rec.get("reviewer") or {}
        if not reviewer.get("independent"):
            print("FAILED:BLD-0033-probe2 reviewer not independent")
            return 1
        queries = [str(q) for q in (reviewer.get("queries") or [])]
        if len(queries) < 3:
            print("FAILED:BLD-0033-probe2 reviewer query set too small")
            return 1
        if AUTHOR_QUERIES.issuperset(set(queries)):
            print("FAILED:BLD-0033-probe2 reviewer queries are a subset of the author's")
            return 1
        live_art = rec.get("live_estate") or {}
        if live_art.get("surfaces_complete") is False:
            gnew = [
                e
                for e in (live_art.get("entries") or [])
                if (e.get("verdict") == "GENUINELY-NEW")
            ]
            if gnew:
                print("FAILED:BLD-0033-probe2 artifact overclaimed GENUINELY-NEW")
                return 1
        wfa = rec.get("wfa_0120") or {}
        if wfa.get("status") not in {"consumed", "absent", "error"}:
            print("FAILED:BLD-0033-probe2 wfa_0120 status missing")
            return 1
        if rec.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:BLD-0033-probe2 artifact {rec.get('state')}")
            return 1

    print("SUCCESS:BLD-0033-probe2 reviewer-queries live-honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
