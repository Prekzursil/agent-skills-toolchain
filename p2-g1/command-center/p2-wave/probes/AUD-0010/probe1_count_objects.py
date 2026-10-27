#!/usr/bin/env python3
"""Probe 1: git count-objects -vH twice; runs must agree within 2 percent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = REPO / "command-center/audit/AUD-0010-repo-weight-baseline.json"
SENTINEL = (
    "SUCCESS:AUD-0010 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0010-probe1 {msg}")
    return 1


def main() -> int:
    fixture = M.measure_fixture()
    owner = M.owner_repo_row()
    packed1 = fixture["packed_run1"]
    packed2 = fixture["packed_run2"]
    if packed1["exit_code"] != 0:
        return fail(f"count-objects run1 exit={packed1['exit_code']}")
    if packed2["exit_code"] != 0:
        return fail(f"count-objects run2 exit={packed2['exit_code']}")
    if not fixture["packed_repeat_ok"]:
        return fail(
            f"packed runs disagree p1={packed1['packed_bytes']} "
            f"p2={packed2['packed_bytes']}"
        )
    if owner["git_present"]:
        live = M.count_objects(Path(owner["path"]))
        if live["exit_code"] != 0:
            return fail("owner .git present but count-objects failed")
    else:
        code, text = M.run_git(["rev-parse", "--is-inside-work-tree"], REPO)
        if code == 0:
            return fail("worktree has no .git but rev-parse succeeded")
        if "not a git repository" not in text.lower():
            return fail(f"rev-parse on non-git worktree: {text[:200]}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    blob = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(blob)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in blob:
        return fail("sentinel-absent")
    headline = doc.get("headline") or {}
    if int(headline.get("packed_bytes") or 0) <= 0:
        return fail("headline packed_bytes missing")
    if not M.within_2pct(int(headline["packed_bytes"]), int(fixture["packed_bytes"])):
        return fail("artifact packed_bytes drifted from live fixture")
    rec_owner = (doc.get("owner_repos") or [{}])[0]
    if rec_owner.get("git_present") is not False:
        return fail("artifact did not record owner git_present=false")
    if rec_owner.get("clone_cost") != "NOT-CHECKED":
        return fail("owner clone_cost must be NOT-CHECKED without .git")
    probes = doc.get("named_probes") or []
    if len(probes) < 2:
        return fail("named probes not recorded")
    joined = json.dumps(probes)
    if "count-objects" not in joined and "packed_bytes" not in joined:
        return fail("probe1 transcript missing from artifact")

    payload = {
        "pass": True,
        "probe": "probe1-count-objects",
        "unit_id": "AUD-0010",
        "packed_bytes": fixture["packed_bytes"],
        "packed_run2_bytes": packed2["packed_bytes"],
        "within_2pct": True,
        "object_count": fixture["object_count"],
        "owner_git_present": owner["git_present"],
        "count_objects_raw": packed1["raw"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"packed={fixture['packed_bytes']} run2={packed2['packed_bytes']} "
        f"within_2pct=True owner_git={owner['git_present']}"
    )
    print("SUCCESS:AUD-0010-probe1 count-objects packed size repeated within 2 percent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
