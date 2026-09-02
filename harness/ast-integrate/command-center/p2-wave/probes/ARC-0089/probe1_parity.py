#!/usr/bin/env python3
"""Probe 1: three-way skill-tree parity (repo vs both live trees).

Reports the difference set. Both-states: the planted repo-only skill must
appear in the fail fixture; the matching trio must be silent.
Host trees are enumerated; they are absent on this Linux worktree.
Consumer call site: the census records validate against the ARC-0089 schema.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import parity as P  # noqa: E402

OUT = HERE / "probe1-parity.raw.json"
SCHEMA = REPO / "command-center" / "phase4" / "contracts" / "ARC-0089.json"


def validate_census(doc: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)


def main() -> int:
    host = P.host_skill_trees()
    host_present = [h for h in host if h["is_dir"] and h["skill_md_count"] > 0]
    host_census = P.three_way(
        REPO / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".agents" / "skills",
    )
    fail_trees = F.build_parity_fail()
    ok_trees = F.build_parity_ok()
    fail = P.three_way(
        fail_trees["repo"], fail_trees["live_claude"], fail_trees["live_agents"]
    )
    good = P.three_way(
        ok_trees["repo"], ok_trees["live_claude"], ok_trees["live_agents"]
    )
    validate_census(fail)
    validate_census(good)
    validate_census(host_census)

    ds = fail["difference_set"]
    fired = (
        "repo-only" in ds["repo_not_in_live_claude"]
        and "repo-only" in ds["repo_not_in_live_agents"]
        and "claude-only" in ds["live_claude_not_in_repo"]
        and "agents-only" in ds["live_agents_not_in_repo"]
        and any(row["id"] == "shared-drift" for row in ds["hash_mismatch"])
        and fail["failure_class_repo_not_in_live"] is True
        and fail["parity_ok"] is False
    )
    silent = (
        good["parity_ok"] is True
        and good["difference_set"]["repo_not_in_live_claude"] == []
        and good["difference_set"]["hash_mismatch"] == []
        and set(good["identical"]) == {"always-on", "council", "lazy-scoped"}
    )
    payload = {
        "host_skill_trees": host,
        "host_present_trees": len(host_present),
        "host_census": host_census,
        "fail": fail,
        "good": good,
        "fired_on_fail": fired,
        "silent_on_good": silent,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        "host_present_trees="
        + str(len(host_present))
        + " host.repo_not_live="
        + ",".join(
            sorted(
                set(host_census["difference_set"]["repo_not_in_live_claude"])
                | set(host_census["difference_set"]["repo_not_in_live_agents"])
            )
        )
        + " fail.parity_ok="
        + str(fail["parity_ok"])
        + " good.parity_ok="
        + str(good["parity_ok"])
        + " repo_not_live_claude="
        + ",".join(ds["repo_not_in_live_claude"])
        + " repo_not_live_agents="
        + ",".join(ds["repo_not_in_live_agents"])
        + " live_claude_not_repo="
        + ",".join(ds["live_claude_not_in_repo"])
        + " live_agents_not_repo="
        + ",".join(ds["live_agents_not_in_repo"])
        + " hash_mismatch="
        + ",".join(row["id"] for row in ds["hash_mismatch"])
        + " identical_ok="
        + ",".join(good["identical"])
        + " signals=sha256,byte-size"
        + " fired_on_fail="
        + str(fired)
        + " silent_on_good="
        + str(silent)
    )
    if not fired:
        print("FAILED:ARC-0089-probe1 fail fixture did not report the three-way difference set")
        return 1
    if not silent:
        print("FAILED:ARC-0089-probe1 matching trees were not silent")
        return 1
    print("SUCCESS:ARC-0089-probe1 three-way skill-tree parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
