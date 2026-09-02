"""Live rollback drill + controls for ADV-0119.

Probe 1 is a three-point inventory. Probe 2 executes golden journeys.
Controls run on the same engine so a matching inventory cannot hide
leftover N-format state.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
import lifecycle as L  # noqa: E402


def _stage_prefix(root: Path, name: str) -> tuple[Path, Path, Path]:
    stage = root / name
    stage.mkdir(parents=True, exist_ok=True)
    canary = L.write_live_canary(stage)
    prefix = stage / "profile"
    return stage, prefix, canary


def run_honest_rollback(root: Path) -> dict:
    stage, prefix, canary = _stage_prefix(root, "honest")
    dist = stage / "dist"
    packages = L.build_packages(dist)
    L.install_n1(packages["n1_zip"], prefix, packages)
    seeded = L.seed_user_data(prefix)
    pre = L.inventory(prefix)
    pre_journeys = L.golden_journeys(prefix)
    L.upgrade_to_n(packages["n_zip"], prefix)
    post_up = L.inventory(prefix)
    post_up_journeys = L.golden_journeys(prefix)
    L.rollback_honest(packages["n1_zip"], prefix, packages)
    post_rb = L.inventory(prefix)
    post_rb_journeys = L.golden_journeys(prefix)
    diff = L.diff_user_files(pre, post_rb)
    leftover_state = (post_rb.get("state") or {}).get("schema_version") != 1
    disposable = L.prefix_is_disposable(prefix, stage)
    canary_ok = L.canary_intact(canary)
    ok = (
        pre_journeys.get("pass")
        and post_up_journeys.get("pass")
        and post_rb_journeys.get("pass")
        and diff["user_byte_identical"]
        and diff["commands_restored"]
        and diff["no_n_only_leftover"]
        and not leftover_state
        and post_rb.get("version") == L.N1_VERSION
        and disposable
        and canary_ok
        and "ast-n-only" in (post_up.get("commands") or [])
        and "ast-n1-only" in (pre.get("commands") or [])
    )
    return {
        "pass": bool(ok),
        "kind": "honest-rollback",
        "packages": {
            "n1_sha256": packages["n1_sha256"],
            "n_sha256": packages["n_sha256"],
            "n1_artifact": L.PKG_N1,
            "n_artifact": L.PKG_N,
            "manifest": packages["manifest"],
        },
        "seeded_hashes": seeded,
        "pre_upgrade": pre,
        "post_upgrade": post_up,
        "post_rollback": post_rb,
        "diff": diff,
        "journeys": {
            "pre_upgrade": pre_journeys,
            "post_upgrade": post_up_journeys,
            "post_rollback": post_rb_journeys,
        },
        "leftover_n_format_state": leftover_state,
        "disposable_prefix": disposable,
        "live_canary_intact": canary_ok,
        "prefix_under_tmp": str(prefix),
    }


def run_clean_n1_control(root: Path) -> dict:
    """Catalog control: a clean N-1 install must pass the same golden journeys."""
    stage, prefix, canary = _stage_prefix(root, "clean-n1")
    packages = L.build_packages(stage / "dist")
    L.install_n1(packages["n1_zip"], prefix, packages)
    L.seed_user_data(prefix)
    journeys = L.golden_journeys(prefix)
    inv = L.inventory(prefix)
    ok = (
        journeys.get("pass")
        and inv.get("version") == L.N1_VERSION
        and L.canary_intact(canary)
        and "ast-n-only" not in (inv.get("commands") or [])
    )
    return {
        "pass": bool(ok),
        "kind": "clean-n1-install",
        "journeys": journeys,
        "inventory": inv,
        "live_canary_intact": L.canary_intact(canary),
        "disposable_prefix": L.prefix_is_disposable(prefix, stage),
    }


def run_leftover_n_state_control(root: Path) -> dict:
    """Inventory of user files can still match while leftover v2 state breaks journeys."""
    stage, prefix, canary = _stage_prefix(root, "leftover-state")
    packages = L.build_packages(stage / "dist")
    L.install_n1(packages["n1_zip"], prefix, packages)
    L.seed_user_data(prefix)
    pre = L.inventory(prefix)
    L.upgrade_to_n(packages["n_zip"], prefix)
    L.rollback_honest(packages["n1_zip"], prefix, packages)
    after_honest = L.inventory(prefix)
    honest_j = L.golden_journeys(prefix)
    honest_diff = L.diff_user_files(pre, after_honest)
    L.plant_n_format_state(prefix)
    planted = L.inventory(prefix)
    planted_j = L.golden_journeys(prefix)
    planted_diff = L.diff_user_files(pre, planted)
    fired = (
        honest_j.get("pass") is True
        and planted_j.get("pass") is False
        and honest_diff["user_byte_identical"]
        and planted_diff["user_byte_identical"]
        and (planted.get("state") or {}).get("schema_version") == 2
        and L.canary_intact(canary)
    )
    return {
        "pass": bool(fired),
        "kind": "leftover-n-format-state",
        "fired_on_bad_state": planted_j.get("pass") is False,
        "silent_on_good_state": honest_j.get("pass") is True,
        "user_inventory_still_matches": planted_diff["user_byte_identical"],
        "honest_journeys_pass": honest_j.get("pass"),
        "planted_journeys_pass": planted_j.get("pass"),
        "planted_journey_stderr": (planted_j.get("rows") or [{}])[0].get("stderr"),
        "live_canary_intact": L.canary_intact(canary),
    }


def run_naive_rollback_control(root: Path) -> dict:
    """Naive overlay leaves N-only command + v2 state; inventory/journeys must go red."""
    stage, prefix, canary = _stage_prefix(root, "naive")
    packages = L.build_packages(stage / "dist")
    L.install_n1(packages["n1_zip"], prefix, packages)
    L.seed_user_data(prefix)
    pre = L.inventory(prefix)
    L.upgrade_to_n(packages["n_zip"], prefix)
    L.rollback_naive(packages["n1_zip"], prefix)
    post = L.inventory(prefix)
    journeys = L.golden_journeys(prefix)
    diff = L.diff_user_files(pre, post)
    fired = (
        journeys.get("pass") is False
        and (
            not diff["no_n_only_leftover"]
            or (post.get("state") or {}).get("schema_version") == 2
        )
        and diff["user_byte_identical"]
        and L.canary_intact(canary)
    )
    return {
        "pass": bool(fired),
        "kind": "naive-rollback",
        "fired_on_bad_state": journeys.get("pass") is False,
        "silent_on_good_state": True,
        "user_inventory_still_matches": diff["user_byte_identical"],
        "leftover_commands": diff["leftover_commands"],
        "state": post.get("state"),
        "journeys": journeys,
        "live_canary_intact": L.canary_intact(canary),
    }


def run_all(tmp: Path | None = None) -> dict:
    owns = tmp is None
    ctx = tempfile.TemporaryDirectory(prefix="adv0119-") if owns else None
    root = Path(ctx.name) if ctx else Path(tmp)
    try:
        honest = run_honest_rollback(root)
        clean = run_clean_n1_control(root)
        leftover = run_leftover_n_state_control(root)
        naive = run_naive_rollback_control(root)
        ok = (
            honest.get("pass")
            and clean.get("pass")
            and leftover.get("pass")
            and naive.get("pass")
        )
        return {
            "pass": bool(ok),
            "honest": honest,
            "clean_n1": clean,
            "leftover_n_state": leftover,
            "naive_rollback": naive,
        }
    finally:
        if ctx is not None:
            ctx.cleanup()
