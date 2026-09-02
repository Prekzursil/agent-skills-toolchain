"""Catalog tests for TST-0071: in-place upgrade from every supported prior version."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from surface import file_census, finish_diff, version_diff
from upgrade import (
    CURRENT_VERSION,
    SUPPORTED_PRIOR,
    USER_DISABLED,
    USER_PLUGINS,
    extract_intent,
    seed_profile,
    upgrade,
)


def upgrade_from(version: str, *, wipe: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"tst0071-v{version}-") as raw:
        root = seed_profile(Path(raw) / "profile", version)
        before = version_diff(root, version, CURRENT_VERSION)
        result = upgrade(root, CURRENT_VERSION, wipe_curation=wipe)
        after = finish_diff(before, root)
        return {
            "from_version": version,
            "upgrade": result,
            "diff": after,
            "intent": extract_intent(root),
            "layout_version": (root / "layout-version").read_text(encoding="utf-8").strip(),
        }


def test_upgrade_from_each_supported_version() -> dict[str, Any]:
    diffs: list[dict[str, Any]] = []
    failures: list[str] = []
    for version in SUPPORTED_PRIOR:
        row = upgrade_from(version)
        diffs.append(row["diff"])
        if row["layout_version"] != CURRENT_VERSION:
            failures.append(f"v{version} landed at {row['layout_version']}")
        if row["upgrade"]["status"] != "upgraded":
            failures.append(f"v{version} status={row['upgrade']['status']}")
        if not row["diff"]["zero_loss"]:
            failures.append(f"v{version} lost {row['diff']['lost_user_keys']}")
        if not row["upgrade"]["steps"]:
            failures.append(f"v{version} applied zero steps (vacuous)")
    ok = not failures
    return {
        "id": "test_upgrade_from_each_supported_version",
        "result": "PASS" if ok else "FAIL",
        "detail": (
            "zero-loss upgrade from each supported prior layout "
            + ",".join(SUPPORTED_PRIOR)
            + f" -> {CURRENT_VERSION}"
            if ok
            else "; ".join(failures)
        ),
        "version_diffs": diffs,
        "supported_prior": list(SUPPORTED_PRIOR),
    }


def test_upgrade_preserves_enabled_disabled_curation() -> dict[str, Any]:
    failures: list[str] = []
    seen: list[dict[str, Any]] = []
    for version in SUPPORTED_PRIOR:
        row = upgrade_from(version)
        intent = row["intent"]
        seen.append(
            {
                "from_version": version,
                "mcp.disabled": intent.get("mcp.disabled"),
                "plugins.enabled": intent.get("plugins.enabled"),
            }
        )
        if list(intent.get("mcp.disabled") or []) != list(USER_DISABLED):
            failures.append(f"v{version} mcp.disabled={intent.get('mcp.disabled')}")
        if intent.get("plugins.enabled") != USER_PLUGINS:
            failures.append(f"v{version} plugins.enabled={intent.get('plugins.enabled')}")
        if not intent.get("mcp.servers"):
            failures.append(f"v{version} custom mcp.servers missing")
    ok = not failures
    return {
        "id": "test_upgrade_preserves_enabled_disabled_curation",
        "result": "PASS" if ok else "FAIL",
        "detail": (
            "MCP disabled list and plugin enable map survived every prior version"
            if ok
            else "; ".join(failures)
        ),
        "observed": seen,
    }


def test_upgrade_is_idempotent_when_already_current() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0071-idemp-") as raw:
        root = seed_profile(Path(raw) / "profile", CURRENT_VERSION)
        before_files = file_census(root)
        before_intent = extract_intent(root)
        first = upgrade(root, CURRENT_VERSION)
        mid_files = file_census(root)
        second = upgrade(root, CURRENT_VERSION)
        after_files = file_census(root)
        after_intent = extract_intent(root)
    same_files = before_files == mid_files == after_files
    same_intent = before_intent == after_intent
    noop = first["status"] == "already-current" and second["status"] == "already-current"
    ok = same_files and same_intent and noop and not first["steps"] and not second["steps"]
    return {
        "id": "test_upgrade_is_idempotent_when_already_current",
        "result": "PASS" if ok else "FAIL",
        "detail": (
            "already-current upgrade is a no-op: file census and user intent unchanged"
            if ok
            else f"noop={noop} files={same_files} intent={same_intent} steps={first['steps']}"
        ),
        "first_status": first["status"],
        "second_status": second["status"],
        "file_census_unchanged": same_files,
        "intent_unchanged": same_intent,
    }


def wipe_control() -> dict[str, Any]:
    healthy = upgrade_from("2", wipe=False)
    mutant = upgrade_from("2", wipe=True)
    fired = (not mutant["diff"]["zero_loss"]) and bool(mutant["diff"]["lost_user_keys"])
    silent = healthy["diff"]["zero_loss"] is True
    curation_lost = "mcp.disabled" in mutant["diff"]["lost_user_keys"] or (
        "plugins.enabled" in mutant["diff"]["lost_user_keys"]
    )
    ok = fired and silent and curation_lost
    return {
        "id": "wipe-on-schema-change",
        "kind": "known-broken-upgrade-drops-mcp-curation",
        "fired_on_bad_state": fired and curation_lost,
        "silent_on_good_state": silent,
        "ok": ok,
        "detail": (
            "wipe mutant drops MCP/plugin curation; healthy v2→v3 keeps every user key"
            if ok
            else f"fired={fired} silent={silent} lost={mutant['diff']['lost_user_keys']}"
        ),
        "mutant_lost_user_keys": mutant["diff"]["lost_user_keys"],
        "healthy_zero_loss": healthy["diff"]["zero_loss"],
    }


def run_suite() -> dict[str, Any]:
    t_each = test_upgrade_from_each_supported_version()
    t_curation = test_upgrade_preserves_enabled_disabled_curation()
    t_idemp = test_upgrade_is_idempotent_when_already_current()
    control = wipe_control()
    tests = [t_each, t_curation, t_idemp]
    ok = all(t["result"] == "PASS" for t in tests) and control["ok"]
    return {
        "ok": ok,
        "tests": tests,
        "version_diffs": t_each["version_diffs"],
        "negative_controls": [control],
    }
