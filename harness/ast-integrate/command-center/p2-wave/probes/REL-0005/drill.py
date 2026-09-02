#!/usr/bin/env python3
"""REL-0005 drills: idempotence, dirty-migration control, skill survival, skip-version."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import upgrade as U

DIRTY_ID = "m120-settings-v3"


def _pkgs(base: Path) -> dict[str, Path]:
    return U.make_packages(base / "packages")


def drill_n1_to_n(base: Path) -> dict[str, Any]:
    base.mkdir(parents=True, exist_ok=True)
    pkgs = _pkgs(base)
    profile = U.create_profile(base / "profiles")
    try:
        iso = U.assert_isolated(profile)
        U.install(profile, pkgs[U.N1])
        planted = U.populate_user_state(profile, from_version=U.N1)
        first = U.upgrade(profile, pkgs[U.N])
        second = U.upgrade(profile, pkgs[U.N])
        skill_after = U.sha256_file(U.user_skill_path(profile))
        ledger = U.load_ledger(profile)
        n_ids = [m["id"] for m in U.MIGRATIONS if m["to_version"] == U.N]
        counts = {mid: int(ledger.get("executions", {}).get(mid, 0)) for mid in n_ids}
        settings = U.load_settings(profile)
        return {
            "isolation": iso,
            "profile": str(profile.resolve()),
            "planted": planted,
            "first": first,
            "second": second,
            "second_run_mutation_count": int(second["mutations"]["mutation_count"]),
            "second_run_measured": bool(second["mutations"]["measured"]),
            "skill_sha256_before": planted["skill_sha256"],
            "skill_sha256_after": skill_after,
            "skill_identical": planted["skill_sha256"] == skill_after,
            "execution_counts": counts,
            "each_migration_once": bool(counts) and all(v == 1 for v in counts.values()),
            "owner_canary_preserved": settings.get("owner.canary") == "keep-me",
            "ui_color_migrated": settings.get("ui.color") == "obsidian",
            "legacy_color_gone": "legacy.color" not in settings,
            "version": U.installed_version(profile),
            "ledger": ledger,
        }
    finally:
        U.destroy_profile(profile)


def drill_dirty_control(base: Path) -> dict[str, Any]:
    base.mkdir(parents=True, exist_ok=True)
    pkgs = _pkgs(base)
    profile = U.create_profile(base / "profiles")
    try:
        U.install(profile, pkgs[U.N1])
        U.populate_user_state(profile, from_version=U.N1)
        first = U.upgrade(profile, pkgs[U.N], dirty_id=DIRTY_ID)
        second = U.upgrade(profile, pkgs[U.N], dirty_id=DIRTY_ID)
        fired = U.double_run_check_fires(second)
        return {
            "first_mutation_count": int(first["mutations"]["mutation_count"]),
            "second_mutation_count": int(second["mutations"]["mutation_count"]),
            "second_run_measured": bool(second["mutations"]["measured"]),
            "double_run_check_fired": fired,
            "dirty_id": DIRTY_ID,
            "second_executions": second["ledger"].get("executions"),
        }
    finally:
        U.destroy_profile(profile)


def drill_skip_complete(base: Path) -> dict[str, Any]:
    base.mkdir(parents=True, exist_ok=True)
    pkgs = _pkgs(base)
    profile = U.create_profile(base / "profiles")
    try:
        U.install(profile, pkgs[U.N2])
        planted = U.populate_user_state(profile, from_version=U.N2)
        result = U.upgrade(profile, pkgs[U.N])
        ledger = U.load_ledger(profile)
        ids = [m["id"] for m in U.MIGRATIONS]
        counts = {mid: int(ledger.get("executions", {}).get(mid, 0)) for mid in ids}
        skill_ok = U.sha256_file(U.user_skill_path(profile)) == planted["skill_sha256"]
        return {
            "outcome": result["outcome"],
            "partial_apply": result["partial_apply"],
            "chain_status": result.get("chain_status"),
            "version": U.installed_version(profile),
            "execution_counts": counts,
            "all_four_once": all(v == 1 for v in counts.values()) and len(counts) == 4,
            "skill_identical": skill_ok,
            "mutations_first": result["mutations"]["mutation_count"],
        }
    finally:
        U.destroy_profile(profile)


def drill_skip_refuse(base: Path) -> dict[str, Any]:
    base.mkdir(parents=True, exist_ok=True)
    pkgs = _pkgs(base)
    profile = U.create_profile(base / "profiles")
    try:
        U.install(profile, pkgs[U.N2])
        U.populate_user_state(profile, from_version=U.N2)
        before = U.tree_hashes(U.ast_root(profile))
        version_before = U.installed_version(profile)
        result = U.upgrade(profile, pkgs[U.N], drop_ids={"m110-settings-rename"})
        after = U.tree_hashes(U.ast_root(profile))
        return {
            "outcome": result["outcome"],
            "reason": result.get("reason"),
            "partial_apply": result["partial_apply"],
            "version_before": version_before,
            "version_after": U.installed_version(profile),
            "version_unchanged": version_before == U.installed_version(profile),
            "mutation_count": U.mutations(before, after)["mutation_count"],
            "refused_loudly": result["outcome"] == "refused",
        }
    finally:
        U.destroy_profile(profile)


def drill_partial_fails(base: Path) -> dict[str, Any]:
    base.mkdir(parents=True, exist_ok=True)
    pkgs = _pkgs(base)
    profile = U.create_profile(base / "profiles")
    try:
        U.install(profile, pkgs[U.N1])
        U.populate_user_state(profile, from_version=U.N1)
        broken = U.apply_partial_unsafe(profile, pkgs[U.N], stop_after=1)
        drill_fail = broken["chain_status"] == "partial" and broken["partial_apply"] is True
        return {"broken": broken, "partial_chain_fails_drill": drill_fail}
    finally:
        U.destroy_profile(profile)


def drill_isolation_control() -> dict[str, Any]:
    fired = False
    message = ""
    try:
        U.assert_isolated(U.OWNER_HOME)
    except U.IsolationError as exc:
        fired = True
        message = str(exc)
    return {"isolation_control_fired": fired, "message": message}


def run_all(base: Path) -> dict[str, Any]:
    n1 = drill_n1_to_n(base / "n1")
    dirty = drill_dirty_control(base / "dirty")
    skip_ok = drill_skip_complete(base / "skip-ok")
    skip_no = drill_skip_refuse(base / "skip-no")
    partial = drill_partial_fails(base / "partial")
    iso = drill_isolation_control()
    tests = {
        "idempotence": (
            n1["second_run_mutation_count"] == 0
            and n1["second_run_measured"]
            and n1["each_migration_once"]
            and n1["version"] == U.N
        ),
        "dirty_control": dirty["double_run_check_fired"] is True
        and dirty["second_mutation_count"] > 0,
        "skill_sha256": n1["skill_identical"] is True,
        "skip_complete_or_refuse": (
            skip_ok["outcome"] == "completed"
            and skip_ok["partial_apply"] is False
            and skip_ok["all_four_once"]
            and skip_no["outcome"] == "refused"
            and skip_no["version_unchanged"]
            and partial["partial_chain_fails_drill"] is True
        ),
        "isolation": iso["isolation_control_fired"] is True
        and n1["isolation"]["owner_home_touched"] is False,
    }
    return {
        "n1_to_n": n1,
        "dirty": dirty,
        "skip_complete": skip_ok,
        "skip_refuse": skip_no,
        "partial": partial,
        "isolation": iso,
        "tests": tests,
        "all_pass": all(tests.values()),
    }


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="rel0005-drill-"))
    try:
        report = run_all(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(json.dumps({k: report[k] for k in ("tests", "all_pass")}, indent=2))
    print("SUCCESS:REL-0005-drill" if report["all_pass"] else "FAILED:REL-0005-drill")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
