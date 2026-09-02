#!/usr/bin/env python3
"""Probe 1: bidirectional relative-path set difference after the deploy map.

Control: enumerator must not crash or silently zero on a file named NUL or a
path over 260 chars — non-zero count on a fixture containing both.
Host ~/.claude and ~/.agents are walked when present; absence is an empty
set, backed by the planted fixture so a host zero is not silent failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import census  # noqa: E402
from enumerator import count_and_flags, iter_files, strawman_skip_reserved  # noqa: E402
from fixtures import build_census_fixture  # noqa: E402

REPO = HERE.parents[3]


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0017-probe1 {msg}")
    return 1


def main() -> int:
    host = census(REPO, Path.home(), fixture=None)
    with tempfile.TemporaryDirectory(prefix="aud0017-p1-") as raw:
        planted = build_census_fixture(Path(raw))
        fixture = {"repo": planted["repo"], "live_home": planted["live_home"]}
        fx = census(REPO, Path.home(), fixture=fixture)
        live_dir = Path(planted["live_home"]) / ".claude" / "agents"
        files = iter_files(live_dir)
        flags = count_and_flags(files)
        straw = strawman_skip_reserved(files)
        straw_flags = count_and_flags(straw)

        live_keys = {row["rel"] for row in fx["live_only"]}
        repo_keys = {row["rel"] for row in fx["repo_only"]}
        want_live = {
            "orphan-live.md",
            "NUL",
            planted["planted"]["long_rel"].split("agents/", 1)[-1],
        }
        missing_live = sorted(want_live - live_keys)
        if missing_live:
            return fail(f"fixture live_only missing {missing_live}; got {sorted(live_keys)}")
        if "never-deployed.md" not in repo_keys:
            return fail(f"fixture repo_only missing never-deployed.md; got {sorted(repo_keys)}")
        if "shared.md" in live_keys or "shared.md" in repo_keys:
            return fail("shared.md misclassified as orphan")
        if not flags["nul_found"]:
            return fail("enumerator missed file named NUL")
        if not flags["long_path_found"]:
            return fail("enumerator missed path over 260 chars")
        if flags["count"] == 0:
            return fail("enumerator silently zeroed the planted fixture")
        if straw_flags["nul_found"]:
            return fail("strawman was supposed to drop NUL")
        if flags["count"] <= straw_flags["count"]:
            return fail("enumerator did not beat reserved-name strawman")

        # Empty-root walk is zero; that zero is allowed only because the plant fired.
        empty = iter_files(Path(raw) / "no-such-root")
        empty_ok = len(empty) == 0 and flags["count"] > 0

        payload = {
            "pass": True,
            "probe": "probe1-set-difference",
            "unit_id": "AUD-0017",
            "host_counts": host["counts"],
            "host_live_home_exists": {
                "claude": (Path.home() / ".claude").is_dir(),
                "agents": (Path.home() / ".agents").is_dir(),
            },
            "fixture_counts": fx["counts"],
            "fixture_live_only": sorted(live_keys),
            "fixture_repo_only": sorted(repo_keys),
            "enumerator": flags,
            "strawman_skip_reserved": straw_flags,
            "empty_root_zero_backed_by_plant": empty_ok,
            "host_zero_backed_by_plant": (
                (host["counts"]["live_only"] == 0 and host["counts"]["repo_only"] == 0)
                and flags["count"] > 0
            ),
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "host_live_only={0} fixture_live_only={1} nul={2} long={3}".format(
                host["counts"]["live_only"],
                fx["counts"]["live_only"],
                flags["nul_found"],
                flags["long_path_found"],
            )
        )
        print("SUCCESS:AUD-0017-probe1 set difference after deploy map; NUL+long-path control")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
