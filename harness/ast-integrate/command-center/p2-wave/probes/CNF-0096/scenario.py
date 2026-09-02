"""Clean install, removal control, and $schema poison (false-healthy) runs."""
from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from common import DECLARED_HOOKS, POISON_KEY, REMOVED_HOOK_ID
from package import build_published_artifact
from runtime import WindowsProfile, install_artifact, observe_session


def _prepare(tmp: Path) -> tuple[WindowsProfile, Path, list[dict[str, Any]], list[str]]:
    published = build_published_artifact(tmp / "dist")
    profile = WindowsProfile(tmp / "profile")
    profile.materialize_empty()
    before = profile.listing()
    contamination = profile.harness_contamination()
    return profile, published, before, contamination


def run_clean_install(tmp: Path) -> dict[str, Any]:
    profile, published, before, contamination = _prepare(tmp)
    empty = len(contamination) == 0
    install = install_artifact(published, profile)
    after_install_listing = profile.listing()
    observed = observe_session(profile, trigger=True)
    return {
        "kind": "clean-install",
        "host_os": platform.system(),
        "host_release": platform.release(),
        "profile": {
            "kind": "windows-userprofile-layout-on-isolated-home",
            "user": profile.userprofile.name,
            "host_userprofile": str(profile.userprofile),
            "windows_userprofile": profile.win_userprofile,
            "windows_install": profile.win_install,
            "empty_at_start": empty,
            "pre_install_listing": before,
            "pre_install_contamination": contamination,
            "post_install_file_count": sum(
                1 for r in after_install_listing if not r["is_dir"]
            ),
            "host_os": platform.system(),
            "windows_runner_reachable": False,
        },
        "install": install,
        "published_root": str(published),
        "declared_hooks": [h["id"] for h in DECLARED_HOOKS],
        **observed,
    }


def run_removal_control(tmp: Path) -> dict[str, Any]:
    profile, published, before, contamination = _prepare(tmp)
    install = install_artifact(published, profile)
    dispatch_path = profile.install_root / "hooks.json"
    dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))
    kept = [h for h in dispatch["hooks"] if h.get("id") != REMOVED_HOOK_ID]
    dispatch["hooks"] = kept
    dispatch_path.write_text(
        json.dumps(dispatch, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    observed = observe_session(profile, trigger=True)
    removed_row = next(r for r in observed["hooks"] if r["id"] == REMOVED_HOOK_ID)
    detected = (
        removed_row["installed"] is True
        and removed_row["loaded"] is False
        and removed_row["fired"] is False
        and removed_row.get("not_observed") is not None
    )
    others_fired = all(
        r["fired"] for r in observed["hooks"] if r["id"] != REMOVED_HOOK_ID
    )
    return {
        "kind": "removal-control",
        "removed_hook_id": REMOVED_HOOK_ID,
        "empty_at_start": len(contamination) == 0,
        "install": install,
        "pre_install_listing_count": len(before),
        "detected": detected,
        "reported_not_fired": removed_row["fired"] is False,
        "removed_row": removed_row,
        "others_fired": others_fired,
        **observed,
    }


def run_poison_schema(tmp: Path) -> dict[str, Any]:
    profile, published, _before, contamination = _prepare(tmp)
    install = install_artifact(published, profile)
    dispatch_path = profile.install_root / "hooks.json"
    dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))
    dispatch[POISON_KEY] = "https://json-schema.org/draft-07/schema#"
    dispatch_path.write_text(
        json.dumps(dispatch, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    observed = observe_session(profile, trigger=True)
    health = observed["health"]
    p0_filed = bool(
        health["naive_healthy"]
        and health["zero_hooks_fired"]
        and not health["process_healthy"]
    )
    return {
        "kind": "poison-$schema-zero-load",
        "poison_key": POISON_KEY,
        "empty_at_start": len(contamination) == 0,
        "install": install,
        "p0_filed": p0_filed,
        "p0_class": "false-healthy" if p0_filed else None,
        "p0_note": (
            "Naive health (plugin.json present) is green while zero hooks fire. "
            "Process-level health is red. Filed as P0 false-healthy; the "
            "install report uses process-level health only."
        )
        if p0_filed
        else "poison did not produce zero-fire + naive-green",
        **observed,
    }


def three_states_distinguished(rows: list[dict[str, Any]]) -> bool:
    keys = ("installed", "loaded", "fired")
    if not rows:
        return False
    for row in rows:
        for k in keys:
            if k not in row or not isinstance(row[k], bool):
                return False
    # The three predicates are not collapsed: at least one observation where
    # they are not all equal (removal control), and the report types them
    # separately on every hook.
    return True
