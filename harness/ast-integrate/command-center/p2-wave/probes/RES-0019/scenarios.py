#!/usr/bin/env python3
"""RES-0019 live scenarios: throwaway count, isolation, scan-all control."""
from __future__ import annotations

import tempfile
from pathlib import Path

from harness import (
    COMMAND_SIBLINGS,
    DECLARED,
    DEV_MARKERS,
    FIXTURE_NAME,
    ON_DISK,
    IsolationError,
    assert_isolated,
    contamination,
    filesystem_skill_count,
    install_plugin,
    live_home,
    live_skill_census,
    load_client_skills,
    make_fresh_profile,
    plant_developer_profile,
    plugin_dir,
    read_inventory,
    uninstall_plugin,
)


def _fork_verdict(plugin_body: int) -> dict:
    if plugin_body == DECLARED:
        arm = "110"
        verdict = "CONFIRMED"
    elif plugin_body == ON_DISK:
        arm = "222"
        verdict = "REFUTED"
    else:
        arm = f"neither:{plugin_body}"
        verdict = "REFUTED"
    return {
        "plugin_body_loaded": plugin_body,
        "arm_110": plugin_body == DECLARED,
        "arm_222": plugin_body == ON_DISK,
        "matched_arm": arm,
        "fork_verdict": verdict,
    }


def scenario_throwaway_count(root: Path) -> dict:
    profile = make_fresh_profile(root, "throwaway-count")
    live_before = live_skill_census()
    uninstall_plugin(profile)
    empty = read_inventory(profile)
    if empty.get("loaded_count", 0) != 0:
        raise AssertionError(f"uninstalled inventory not empty: {empty}")
    installed = install_plugin(profile)
    client = installed["client"]
    fs_count = installed["filesystem_count"]
    body = client["plugin_body_count"]
    if not client["fixture_visible"]:
        raise AssertionError("fixture skill missing from loaded-skill listing")
    if FIXTURE_NAME not in client["loaded_names"]:
        raise AssertionError("fixture name absent from client listing")
    if fs_count != ON_DISK + 1:
        raise AssertionError(f"filesystem SKILL.md count {fs_count} != {ON_DISK + 1}")
    if body == ON_DISK:
        raise AssertionError("client report collapsed onto the 222 fork (no replace)")
    if body != DECLARED:
        raise AssertionError(f"client plugin-body count {body} != {DECLARED}")
    if client["loaded_count"] != DECLARED + 1:
        raise AssertionError(
            f"client loaded_count {client['loaded_count']} != {DECLARED + 1}"
        )
    if client["mode"] != "replace":
        raise AssertionError(f"expected replace mode, got {client['mode']}")
    fork = _fork_verdict(body)
    return {
        "id": "throwaway-count",
        "pass": True,
        "profile": str(profile),
        "client_loaded_count": client["loaded_count"],
        "client_plugin_body": body,
        "filesystem_skill_md_count": fs_count,
        "filesystem_plugin_body": fs_count - 1,
        "fixture_visible": True,
        "fixture_name": FIXTURE_NAME,
        "loaded_names_head": client["loaded_names"][:5],
        "loaded_names_tail": client["loaded_names"][-3:],
        "mode": client["mode"],
        "fork": fork,
        "signals_reported_separately": client["loaded_count"] != fs_count,
        "live_before_count": live_before["count"],
        "live_before_sha256": live_before["sha256"],
    }


def scenario_isolation(root: Path) -> dict:
    before = live_skill_census()
    profile = make_fresh_profile(root, "isolation")
    assert_isolated(profile)
    if live_home() in profile.resolve().parents or profile.resolve() == live_home():
        raise IsolationError("throwaway is the live home")
    install_plugin(profile)
    after = live_skill_census()
    if after["sha256"] != before["sha256"] or after["count"] != before["count"]:
        raise AssertionError(
            f"live profile mutated before={before} after={after}"
        )
    if after["paths"] != before["paths"]:
        raise AssertionError("live SKILL.md path set changed")
    return {
        "id": "isolation",
        "pass": True,
        "profile": str(profile),
        "live_home": before["home"],
        "live_count_before": before["count"],
        "live_count_after": after["count"],
        "live_sha256_before": before["sha256"],
        "live_sha256_after": after["sha256"],
        "unchanged": True,
        "isolated": True,
    }


def scenario_filesystem_and_scan_all(root: Path) -> dict:
    """Probe-2 instrument: filesystem walk + union scan (the 222 fork)."""
    profile = make_fresh_profile(root, "scan-all")
    install_plugin(profile)
    dest = plugin_dir(profile)
    fs_count = filesystem_skill_count(dest)
    union = load_client_skills(dest, replace=False)
    replaced = load_client_skills(dest, replace=True)
    if fs_count != ON_DISK + 1:
        raise AssertionError(f"filesystem count {fs_count} != {ON_DISK + 1}")
    if union["plugin_body_count"] != ON_DISK:
        raise AssertionError(
            f"scan-all body {union['plugin_body_count']} != {ON_DISK}"
        )
    if replaced["plugin_body_count"] != DECLARED:
        raise AssertionError(
            f"replace body {replaced['plugin_body_count']} != {DECLARED}"
        )
    if not union["fixture_visible"] or not replaced["fixture_visible"]:
        raise AssertionError("fixture vanished in scan-all/replace pair")
    inert = ON_DISK - DECLARED
    return {
        "id": "filesystem-and-scan-all",
        "pass": True,
        "profile": str(profile),
        "filesystem_skill_md_count": fs_count,
        "filesystem_plugin_body": ON_DISK,
        "scan_all_plugin_body": union["plugin_body_count"],
        "replace_plugin_body": replaced["plugin_body_count"],
        "scan_all_matches_222_fork": union["plugin_body_count"] == ON_DISK,
        "replace_matches_110_fork": replaced["plugin_body_count"] == DECLARED,
        "inert_undeclared_skills": inert,
        "command_siblings": COMMAND_SIBLINGS,
        "inert_plus_commands": inert + COMMAND_SIBLINGS,
        "author_136_equals_inert_plus_commands": inert + COMMAND_SIBLINGS == 136,
        "detector_not_silent_on_222": True,
    }


def scenario_no_contamination(root: Path) -> dict:
    fresh = make_fresh_profile(root, "no-contam")
    developer = plant_developer_profile(root)
    hits = contamination(fresh)
    if hits:
        raise AssertionError(f"fresh profile inherited developer harness: {hits}")
    present_dev = contamination(developer)
    if set(present_dev) != set(DEV_MARKERS):
        raise AssertionError(f"developer fixture incomplete: {present_dev}")
    assert_isolated(fresh)
    return {
        "id": "no-contamination",
        "pass": True,
        "fresh_hits": hits,
        "developer_markers_present": len(present_dev),
        "fresh_top_level": sorted(p.name for p in fresh.iterdir()),
        "isolated": True,
        "fresh_profile": str(fresh),
        "developer_profile": str(developer),
    }


def run_all() -> dict:
    with tempfile.TemporaryDirectory(prefix="res0019-") as tmp:
        root = Path(tmp)
        try:
            live_home()
        except OSError as exc:
            raise IsolationError(str(exc)) from exc
        results = {
            "throwaway_count": scenario_throwaway_count(root),
            "isolation": scenario_isolation(root),
            "filesystem_and_scan_all": scenario_filesystem_and_scan_all(root),
            "no_contamination": scenario_no_contamination(root),
        }
        return {
            "all_pass": all(v["pass"] for v in results.values()),
            "scenarios": results,
        }
