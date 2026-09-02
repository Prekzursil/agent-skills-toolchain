#!/usr/bin/env python3
"""Named probe 2: worktree isolation and scoped-add under >=4 concurrent agents.

Live re-run: four worktrees must have distinct index files and no sibling
paths in commits; scoped `git add -- path` + `git commit -- path` on a
shared tree must also keep commits file-disjoint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import (  # noqa: E402
    N_AGENTS,
    run_scoped_add_discipline,
    run_worktree_isolation,
)

ART = REPO / "command-center/receipts/TST-0099.json"


def main() -> int:
    isolated = run_worktree_isolation()
    scoped = run_scoped_add_discipline()

    if isolated.get("n_agents") != N_AGENTS or isolated.get("n_commits") != N_AGENTS:
        print(
            "FAILED:TST-0099-probe2 worktree n_agents="
            f"{isolated.get('n_agents')} n_commits={isolated.get('n_commits')}"
        )
        print(json.dumps(isolated.get("errors"), indent=2))
        return 1
    if not isolated.get("indexes_isolated"):
        print("FAILED:TST-0099-probe2 indexes were not isolated")
        print(isolated.get("index_paths"))
        return 1
    if isolated.get("sibling_commits"):
        print("FAILED:TST-0099-probe2 worktree commit contained a sibling path")
        for q in isolated["sibling_commits"]:
            print("  ", q)
        return 1
    if isolated.get("errors"):
        print("FAILED:TST-0099-probe2 worktree agent errors")
        print(json.dumps(isolated["errors"], indent=2))
        return 1

    if scoped.get("n_agents") != N_AGENTS or scoped.get("n_commits") != N_AGENTS:
        print(
            "FAILED:TST-0099-probe2 scoped n_agents="
            f"{scoped.get('n_agents')} n_commits={scoped.get('n_commits')}"
        )
        print(json.dumps({"errors": scoped.get("errors"), "agents": scoped.get("agents")}, indent=2)[:3000])
        return 1
    if scoped.get("sibling_commits"):
        print("FAILED:TST-0099-probe2 scoped-add commit contained a sibling path")
        for q in scoped["sibling_commits"]:
            print("  ", q)
        return 1
    if scoped.get("errors"):
        print("FAILED:TST-0099-probe2 scoped-add agent errors")
        print(json.dumps(scoped["errors"], indent=2))
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0099-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0099" not in text or doc.get("unit_id") != "TST-0099":
        print("FAILED:TST-0099-probe2 receipt sentinel/unit_id")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t_iso = tests.get("test_worktree_isolation_actually_isolates_the_index") or {}
    t_sib = tests.get("test_no_commit_contains_a_sibling_agents_path") or {}
    if t_iso.get("result") != "PASS" or t_sib.get("result") != "PASS":
        print("FAILED:TST-0099-probe2 receipt isolation tests not PASS")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0099-probe2 self-declared:{st}")
        return 1

    print(json.dumps({
        "probe": "probe2-worktree-isolation",
        "unit_id": "TST-0099",
        "indexes_isolated": True,
        "unique_index_count": isolated.get("unique_index_count"),
        "worktree_commits": isolated.get("n_commits"),
        "scoped_commits": scoped.get("n_commits"),
        "sibling_commits": [],
        "pass": True,
    }, sort_keys=True))
    print(
        "indexes_isolated=True unique="
        f"{isolated.get('unique_index_count')} "
        f"wt_commits={isolated.get('n_commits')} "
        f"scoped_commits={scoped.get('n_commits')}"
    )
    print("SUCCESS:TST-0099-probe2 worktree isolation and scoped-add hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
