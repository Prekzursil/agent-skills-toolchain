#!/usr/bin/env python3
"""Probe 1: path-set and LF-normalized content comparison.

Recomputes repo-vs-live agents/ and commands/ trees. The planted path-control
must report exactly one content-different, one repo-only, one live-only, and
one equal path. A comparator that reports zero (or all) on that fixture is
broken. Artifact headline counts must match this live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drift as D  # noqa: E402

ART = REPO / D.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0014-probe1 {msg}")
    return 1


def main() -> int:
    live = D.measure()
    pctl = live["path_control"]
    payload = {
        "probe": "probe1-path-content",
        "n_live_only": live["n_live_only"],
        "n_repo_only": live["n_repo_only"],
        "n_content_different": live["n_content_different"],
        "any_host_tree_present": live["any_host_tree_present"],
        "path_control_ok": pctl["ok"],
        "path_control_vacuous": pctl["vacuous"],
        "agents": {
            "repo_is_dir": live["host"]["agents"]["repo_is_dir"],
            "live_is_dir": live["host"]["agents"]["live_is_dir"],
            "repo_count": live["host"]["agents"]["repo_count"],
            "live_count": live["host"]["agents"]["live_count"],
            "n_live_only": live["host"]["agents"]["n_live_only"],
            "n_repo_only": live["host"]["agents"]["n_repo_only"],
            "n_different": live["host"]["agents"]["n_different"],
        },
        "commands": {
            "repo_is_dir": live["host"]["commands"]["repo_is_dir"],
            "live_is_dir": live["host"]["commands"]["live_is_dir"],
            "repo_count": live["host"]["commands"]["repo_count"],
            "live_count": live["host"]["commands"]["live_count"],
            "n_live_only": live["host"]["commands"]["n_live_only"],
            "n_repo_only": live["host"]["commands"]["n_repo_only"],
            "n_different": live["host"]["commands"]["n_different"],
        },
    }
    print(json.dumps(payload, sort_keys=True))

    if pctl["vacuous"]:
        return fail("path-control reported no diffs — comparator is not discriminating")
    if not pctl["ok"]:
        return fail(
            "path-control mismatch "
            f"equal={pctl['content_equal']} different={[r['path'] for r in pctl['content_different']]} "
            f"repo_only={pctl['repo_only']} live_only={pctl['live_only']}"
        )
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if D.SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("n_live_only") != live["n_live_only"]:
        return fail("artifact n_live_only drifted from live path-set")
    if doc.get("n_repo_only") != live["n_repo_only"]:
        return fail("artifact n_repo_only drifted from live path-set")
    if doc.get("n_content_different") != live["n_content_different"]:
        return fail("artifact n_content_different drifted from live content compare")
    art_host = doc.get("host") or {}
    for kind in ("agents", "commands"):
        live_h = live["host"][kind]
        art_h = art_host.get(kind) or {}
        for key in ("repo_only", "live_only", "content_equal"):
            if list(art_h.get(key) or []) != list(live_h.get(key) or []):
                return fail(f"artifact host.{kind}.{key} drifted from live remeasure")
        art_diff = [r.get("path") for r in (art_h.get("content_different") or [])]
        live_diff = [r.get("path") for r in live_h.get("content_different") or []]
        if art_diff != live_diff:
            return fail(f"artifact host.{kind}.content_different drifted from live remeasure")
    art_pctl = doc.get("path_control") or {}
    if art_pctl.get("ok") is not True:
        return fail("artifact path_control.ok is not true")
    if art_pctl.get("vacuous") is True:
        return fail("artifact path_control marked vacuous")

    print(
        f"path_set live_only={live['n_live_only']} repo_only={live['n_repo_only']} "
        f"different={live['n_content_different']} host_trees={live['any_host_tree_present']} "
        f"path_control_ok=True"
    )
    print("SUCCESS:AUD-0014-probe1 live path-set and normalized-content match artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
