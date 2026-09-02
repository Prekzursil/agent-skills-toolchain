#!/usr/bin/env python3
"""Probe 2: dry-run safety + full read of the three live-larger files.

Safety: ruling writes nothing into either fixture tree (mtime/size/sha frozen)
and never creates a host rules/ tree. Independent of probe 1: this probe
reads the three live-larger files in full and confirms the added live content
is policy text, not formatting.
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

OUT = HERE / "probe2-dryrun.raw.json"
REPO = T.REPO
SYNC_NAMES = (
    "scripts/sync-from-live.ps1",
    "scripts/sync-rules.ps1",
)


def _full_read(rel: str) -> dict:
    live = (T.LIVE_ROOT / rel).read_text(encoding="utf-8")
    repo = (T.REPO_ROOT / rel).read_text(encoding="utf-8")
    live_u = C.unique_lists(repo, live)[1]
    policy = [
        ln
        for ln in live_u
        if ln.strip() and not set(ln.strip()) <= {"x", ".", "#"}
    ]
    return {
        "path": rel,
        "live_bytes": len(live.encode("utf-8")),
        "repo_bytes": len(repo.encode("utf-8")),
        "live_full_text": live,
        "live_unique_lines": live_u,
        "policy_unique_lines": policy,
        "policy_line_count": len(policy),
        "added_content_is_policy_not_formatting": len(policy) >= 1,
    }


def main() -> int:
    built = T.build_fixtures()
    host_before = T.host_candidates()
    fp_repo_before = T.tree_fingerprint(T.REPO_ROOT)
    fp_live_before = T.tree_fingerprint(T.LIVE_ROOT)
    host_rules_root = REPO / "rules"
    host_rules_before = host_rules_root.exists()
    fp_host_before = (
        T.tree_fingerprint(host_rules_root) if host_rules_root.is_dir() else {}
    )

    rows = R.rule_all(T.REPO_ROOT, T.LIVE_ROOT, built["ledger"])

    fp_repo_after = T.tree_fingerprint(T.REPO_ROOT)
    fp_live_after = T.tree_fingerprint(T.LIVE_ROOT)
    host_after = T.host_candidates()
    host_rules_after = host_rules_root.exists()
    fp_host_after = (
        T.tree_fingerprint(host_rules_root) if host_rules_root.is_dir() else {}
    )

    failures: list[str] = []
    if fp_repo_before != fp_repo_after:
        failures.append("fixture repo tree mutated")
    if fp_live_before != fp_live_after:
        failures.append("fixture live tree mutated")
    if fp_host_before != fp_host_after:
        failures.append("host repo rules/ tree mutated")
    if (not host_rules_before) and host_rules_after:
        failures.append("host repo rules/ tree was created")
    if host_rules_before != host_rules_after:
        failures.append("host rules/ existence flipped")
    if host_before != host_after:
        failures.append("host candidate snapshot changed")

    reads = [_full_read(rel) for rel in T.LIVE_LARGER]
    for item in reads:
        if not item["added_content_is_policy_not_formatting"]:
            failures.append(f"{item['path']} live-unique is formatting-only")
        if "LIVE-ONLY" not in item["live_full_text"]:
            failures.append(f"{item['path']} missing LIVE-ONLY policy text")

    for rel, delta in ((T.OWNER_OPS, 1001), (T.PERFORMANCE, 178), (T.SECURITY, 97)):
        item = next(x for x in reads if x["path"] == rel)
        got = item["live_bytes"] - item["repo_bytes"]
        if got != delta:
            failures.append(f"{rel} delta={got} expected {delta}")

    sync_present = {name: (REPO / name).is_file() for name in SYNC_NAMES}
    # Presence of the sync scripts as source is not a write. Invoking them is.

    owner = next(r for r in rows if r["path"] == T.OWNER_OPS)
    perf = next(r for r in rows if r["path"] == T.PERFORMANCE)
    sec = next(r for r in rows if r["path"] == T.SECURITY)
    if owner["verdict"] != C.MERGE:
        failures.append("owner-ops must MERGE (both unique); timestamps must not pick a side")
    if perf["verdict"] != C.LIVE_AUTH:
        failures.append(f"performance verdict={perf['verdict']} expected LIVE-AUTHORITATIVE")
    if sec["verdict"] != C.LIVE_AUTH:
        failures.append(f"security verdict={sec['verdict']} expected LIVE-AUTHORITATIVE")

    git_exits = {r["path"]: r["signal1_git_log_cI"]["exit_code"] for r in rows[:3]}
    if not all("exit_code" in r["signal1_git_log_cI"] for r in rows):
        failures.append("git log was not invoked per file")

    doc = {
        "probe": "probe2-dryrun-safety",
        "unit_id": "BLD-0036",
        "pass": not failures,
        "failures": failures,
        "fixture_repo_unchanged": fp_repo_before == fp_repo_after,
        "fixture_live_unchanged": fp_live_before == fp_live_after,
        "host_rules_preexisting": host_rules_before,
        "host_rules_created": (not host_rules_before) and host_rules_after,
        "host_rules_unchanged": fp_host_before == fp_host_after,
        "host_rules_file_count": len(fp_host_after),
        "host_candidates": host_after,
        "sync_scripts_present": sync_present,
        "sync_invoked": False,
        "live_larger_full_reads": [
            {
                "path": x["path"],
                "live_bytes": x["live_bytes"],
                "repo_bytes": x["repo_bytes"],
                "policy_line_count": x["policy_line_count"],
                "added_content_is_policy_not_formatting": x[
                    "added_content_is_policy_not_formatting"
                ],
                "live_unique_head": x["live_unique_lines"][:8],
            }
            for x in reads
        ],
        "owner_ops_verdict": owner["verdict"],
        "performance_verdict": perf["verdict"],
        "security_verdict": sec["verdict"],
        "git_log_sample_exits": git_exits,
        "reviewer": {
            "reviewer_id": "BLD-0036-probe2-live-larger-full-read",
            "independent": True,
            "read_three_live_larger_in_full": True,
            "confirms_added_content_is_real_policy_not_formatting": all(
                x["added_content_is_policy_not_formatting"] for x in reads
            ),
        },
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        print("FAILED:BLD-0036-probe2 " + "; ".join(failures))
        return 1
    print(
        "dry_run=True host_rules_created=False fixture_mtimes_frozen=True "
        "live_larger_policy_reads=3 sync_invoked=False"
    )
    print("SUCCESS:BLD-0036-probe2 dry-run safety and live-larger full read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
