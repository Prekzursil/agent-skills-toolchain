#!/usr/bin/env python3
"""CNF-0146 live scenarios: both-states, known-broken, no-contamination, idempotence."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from harness import (
    DEV_MARKERS,
    EVENTS,
    IsolationError,
    assert_isolated,
    both_signals_agree_loaded,
    both_signals_agree_unloaded,
    contamination,
    fire_all,
    install_plugin,
    listing_says_installed,
    make_fresh_profile,
    plant_developer_profile,
    uninstall_plugin,
)


def scenario_both_states(root: Path) -> dict:
    profile = make_fresh_profile(root, "both-states")
    uninstall_plugin(profile)
    uninstalled = fire_all(profile)
    if not both_signals_agree_unloaded(uninstalled):
        raise AssertionError(f"uninstalled still looks loaded: {uninstalled}")
    if listing_says_installed(profile):
        raise AssertionError("listing claimed install while uninstalled")
    install_plugin(profile, inject_schema=False)
    installed = fire_all(profile)
    if not both_signals_agree_loaded(installed):
        raise AssertionError(f"installed did not fire+inventory: {installed}")
    return {
        "id": "both-states",
        "pass": True,
        "uninstalled_beacons": uninstalled["beacons"],
        "uninstalled_loaded_count": uninstalled["inventory"]["loaded_count"],
        "installed_beacons": installed["beacons"],
        "installed_loaded_count": installed["inventory"]["loaded_count"],
        "installed_hook_ids": installed["inventory"]["hook_ids"],
        "listing_uninstalled": False,
        "listing_installed": listing_says_installed(profile),
        "profile": str(profile),
    }


def scenario_known_broken(root: Path) -> dict:
    profile = make_fresh_profile(root, "known-broken")
    install_plugin(profile, inject_schema=True)
    broken = fire_all(profile)
    if not both_signals_agree_unloaded(broken):
        raise AssertionError(f"$schema mutation still loaded hooks: {broken}")
    if not listing_says_installed(profile):
        raise AssertionError("listing must still pass in the broken state")
    if not broken["settings_present"]:
        raise AssertionError("settings claim missing in broken state")
    err = broken["inventory"].get("load_error") or ""
    if "$schema" not in err:
        raise AssertionError(f"expected $schema in load_error, got {err!r}")
    return {
        "id": "known-broken",
        "pass": True,
        "listing_says_installed": True,
        "settings_present": True,
        "loaded_count": broken["inventory"]["loaded_count"],
        "beacons": broken["beacons"],
        "load_error": err,
        "file_listing_passes_while_unloaded": True,
        "profile": str(profile),
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


def scenario_idempotence(root: Path) -> dict:
    profile = make_fresh_profile(root, "idempotence")
    install_plugin(profile, inject_schema=False)
    first = fire_all(profile)
    if not both_signals_agree_loaded(first):
        raise AssertionError(f"first install did not load: {first}")
    first_ids = list(first["inventory"]["hook_ids"])
    install_plugin(profile, inject_schema=False)
    second = fire_all(profile)
    if not both_signals_agree_loaded(second):
        raise AssertionError(f"second install did not load: {second}")
    second_ids = list(second["inventory"]["hook_ids"])
    if second_ids != first_ids:
        raise AssertionError(f"hook ids changed on reinstall: {first_ids} vs {second_ids}")
    if len(second_ids) != len(EVENTS):
        raise AssertionError(f"double-register suspected: {second_ids}")
    per_event = second["inventory"]["events"]
    for event in EVENTS:
        n = len(per_event.get(event) or [])
        if n != 1:
            raise AssertionError(f"{event} registered {n} times after second install")
    return {
        "id": "idempotence",
        "pass": True,
        "first_hook_ids": first_ids,
        "second_hook_ids": second_ids,
        "registered_count_first": len(first_ids),
        "registered_count_second": len(second_ids),
        "no_double_register": True,
        "profile": str(profile),
    }


def run_all() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf0146-") as tmp:
        root = Path(tmp)
        try:
            Path.home().resolve()
        except OSError as exc:
            raise IsolationError(str(exc)) from exc
        results = {
            "both_states": scenario_both_states(root),
            "known_broken": scenario_known_broken(root),
            "no_contamination": scenario_no_contamination(root),
            "idempotence": scenario_idempotence(root),
        }
        return {
            "all_pass": all(v["pass"] for v in results.values()),
            "scenarios": results,
        }


if __name__ == "__main__":
    doc = run_all()
    print(json.dumps(doc, indent=2, sort_keys=True))
    raise SystemExit(0 if doc["all_pass"] else 1)
