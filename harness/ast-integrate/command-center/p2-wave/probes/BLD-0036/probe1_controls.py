#!/usr/bin/env python3
"""Probe 1: classification controls for BLD-0036.

1. Five byte-identical files classify NO-ACTION.
2. Fifty-five EOL-only files classify EOL-ONLY and never enter the merge plan.
3. A planted two-directional file (unique lines on both sides) classifies MERGE,
   never a pick-a-side verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import ruling as R  # noqa: E402
import trees as T  # noqa: E402

OUT = HERE / "probe1-controls.raw.json"


def main() -> int:
    built = T.build_fixtures()
    rows = R.rule_all(T.REPO_ROOT, T.LIVE_ROOT, built["ledger"])
    plan = R.merge_plan(rows)
    plan_paths = {p["path"] for p in plan}
    by_verdict: dict[str, list[str]] = {}
    for row in rows:
        by_verdict.setdefault(row["verdict"], []).append(row["path"])

    no_action = by_verdict.get(C.NO_ACTION, [])
    eol_only = by_verdict.get(C.VERDICT_EOL, [])
    merge = by_verdict.get(C.MERGE, [])
    repo_auth = by_verdict.get(C.REPO_AUTH, [])
    live_auth = by_verdict.get(C.LIVE_AUTH, [])

    failures: list[str] = []
    if len(rows) != 88:
        failures.append(f"union={len(rows)} expected 88")
    if len(no_action) != 5:
        failures.append(f"NO-ACTION={len(no_action)} expected 5")
    if len(eol_only) != 55:
        failures.append(f"EOL-ONLY={len(eol_only)} expected 55")
    if any(p in plan_paths for p in eol_only):
        failures.append("EOL-ONLY path entered merge plan")
    if any(p in plan_paths for p in no_action):
        failures.append("NO-ACTION path entered merge plan")

    planted = next((r for r in rows if r["path"] == T.PLANTED), None)
    if planted is None:
        failures.append("planted two-directional file missing")
    else:
        if planted["verdict"] != C.MERGE:
            failures.append(
                f"planted verdict={planted['verdict']} expected MERGE "
                "(must not pick a side)"
            )
        if planted["classification"] != C.BOTH_UNIQUE:
            failures.append(f"planted classification={planted['classification']}")
        if planted["path"] not in plan_paths:
            failures.append("planted MERGE file missing from merge plan")
        if planted["verdict"] in {C.REPO_AUTH, C.LIVE_AUTH}:
            failures.append("planted received a pick-a-side verdict")

    live_larger = [r for r in rows if r["live_larger"]]
    repo_larger = [r for r in rows if r["repo_larger"]]
    if len(live_larger) != 3:
        failures.append(f"live_larger={len(live_larger)} expected 3")
    if len(repo_larger) != 25:
        failures.append(f"repo_larger={len(repo_larger)} expected 25")
    named = {r["path"] for r in live_larger}
    if set(T.LIVE_LARGER) != named:
        failures.append(f"live-larger paths={sorted(named)}")

    owner = next(r for r in rows if r["path"] == T.OWNER_OPS)
    if owner["verdict"] != C.MERGE:
        failures.append(f"owner-ops verdict={owner['verdict']} expected MERGE (both unique)")

    for rel, delta in ((T.OWNER_OPS, 1001), (T.PERFORMANCE, 178), (T.SECURITY, 97)):
        row = next(r for r in rows if r["path"] == rel)
        got = row["live_bytes"] - row["repo_bytes"]
        if got != delta:
            failures.append(f"{rel} delta={got} expected {delta}")

    content = len(rows) - len(no_action) - len(eol_only)
    if content != 28:
        failures.append(f"content-differing={content} expected 28")

    doc = {
        "probe": "probe1-controls",
        "unit_id": "BLD-0036",
        "pass": not failures,
        "failures": failures,
        "union": len(rows),
        "no_action": len(no_action),
        "eol_only": len(eol_only),
        "merge": len(merge),
        "repo_authoritative": len(repo_auth),
        "live_authoritative": len(live_auth),
        "merge_plan_size": len(plan),
        "eol_in_merge_plan": sorted(p for p in eol_only if p in plan_paths),
        "planted_path": T.PLANTED,
        "planted_verdict": None if planted is None else planted["verdict"],
        "planted_classification": None if planted is None else planted["classification"],
        "live_larger_paths": sorted(named),
        "fixture_counts": built["counts"],
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        print("FAILED:BLD-0036-probe1 " + "; ".join(failures))
        return 1
    print(
        "union=88 NO-ACTION=5 EOL-ONLY=55 content=28 repo_larger=25 live_larger=3 "
        f"MERGE={len(merge)} planted=MERGE eol_in_plan=0"
    )
    print("SUCCESS:BLD-0036-probe1 classification controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
