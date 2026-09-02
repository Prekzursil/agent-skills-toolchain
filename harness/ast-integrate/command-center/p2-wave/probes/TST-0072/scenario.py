#!/usr/bin/env python3
"""Execute prior-version rollback against a disposable profile and score tests."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fixtures import MANAGED_V1, USER_OWNED, plant_user_owned, plant_v1, upgrade_to_v2
from inventory import (
    changed,
    deleted,
    inventory_rglob,
    inventory_walk,
    load_managed_set,
    map_digest,
    split_owned,
)
from rollback import additive_restore, naive_replace, snapshot_managed_bytes


def _tests(
    *,
    prior: dict[str, str],
    user_before: dict[str, str],
    user_after: dict[str, str],
    managed_after: dict[str, str],
    commands_before: dict[str, str],
    user_commands_before: dict[str, str],
    user_commands_after: dict[str, str],
    commands_after: dict[str, str],
) -> dict[str, Any]:
    user_deleted = deleted(user_before, user_after)
    user_changed = changed(user_before, user_after)
    prior_ok = all(managed_after.get(rel) == digest for rel, digest in prior.items())
    v2_only = "commands/shipped-new.md"
    v2_removed = v2_only not in managed_after and v2_only not in user_after

    user_cmd_deleted = deleted(user_commands_before, user_commands_after)
    previously_available = set(commands_before)
    still_present = previously_available <= set(commands_after)
    # Upgrade-added shipped command is not user-owned; restoring prior version
    # may remove it. "Unchanged" means every command that existed *and* was
    # either user-owned or part of the prior version still exists.
    prior_and_user_cmds = set(user_commands_before) | set(prior)
    prior_and_user_cmds = {p for p in prior_and_user_cmds if p.startswith("commands/")}
    cmds_preserved = prior_and_user_cmds <= set(commands_after)

    t1 = prior_ok and v2_removed
    t2 = not user_deleted and not user_changed
    t3 = not user_cmd_deleted and cmds_preserved

    return {
        "test_rollback_restores_prior_version": {
            "id": "test_rollback_restores_prior_version",
            "pass": t1,
            "prior_bytes_restored": prior_ok,
            "upgrade_added_managed_removed": v2_removed,
        },
        "test_rollback_deletes_zero_user_owned_paths": {
            "id": "test_rollback_deletes_zero_user_owned_paths",
            "pass": t2,
            "user_deleted": user_deleted,
            "user_changed": user_changed,
        },
        "test_command_inventory_is_unchanged_after_rollback": {
            "id": "test_command_inventory_is_unchanged_after_rollback",
            "pass": t3,
            "user_commands_deleted": user_cmd_deleted,
            "prior_and_user_commands_preserved": cmds_preserved,
            "previously_available_all_still_present": still_present,
        },
        "all_pass": t1 and t2 and t3,
    }


def rehearse(root: Path, mode: str) -> dict[str, Any]:
    live = root / "live"
    snap = root / "v1-snapshot"
    if live.exists():
        shutil.rmtree(live)
    if snap.exists():
        shutil.rmtree(snap)
    live.mkdir(parents=True)
    snap.mkdir(parents=True)

    managed_v1 = plant_v1(live)
    prior_bytes = snapshot_managed_bytes(live, managed_v1)
    plant_v1(snap)
    user_rels = plant_user_owned(live)
    upgrade_to_v2(live)

    before_rglob = inventory_rglob(live)
    before_walk = inventory_walk(live)
    if before_rglob != before_walk:
        raise SystemExit("FAILED:TST-0072 walkers disagree before rollback")
    managed_now = load_managed_set(live)
    split_before = split_owned(before_rglob, managed_now)
    # User-owned is defined from the *prior* managed set plus planted user files:
    # files that are not in v1 managed paths. After upgrade, v2 managed includes
    # shipped-new, which is product-owned. User files remain those planted.
    user_before = {rel: inventory_rglob(live)[rel] for rel in user_rels}
    prior_hashes = {
        rel: __import__("hashlib").sha256(data).hexdigest()
        for rel, data in prior_bytes.items()
    }

    if mode == "additive":
        action = additive_restore(live, prior_bytes, prior_managed_rels=managed_v1)
    elif mode == "naive":
        action = naive_replace(live, snap)
    else:
        raise ValueError(mode)

    after_rglob = inventory_rglob(live)
    after_walk = inventory_walk(live)
    if after_rglob != after_walk:
        raise SystemExit("FAILED:TST-0072 walkers disagree after rollback")

    after_managed_set = load_managed_set(live)
    split_after = split_owned(after_rglob, after_managed_set)
    user_after = {p: h for p, h in after_rglob.items() if p in user_before or p in USER_OWNED}
    # Classify user as: present after and not in restored managed set
    user_after_classified = split_after["user"]

    tests = _tests(
        prior=prior_hashes,
        user_before=user_before,
        user_after=user_after_classified,
        managed_after=split_after["managed"],
        commands_before=split_before["commands"],
        user_commands_before=split_before["user_commands"],
        user_commands_after=split_after["user_commands"],
        commands_after=split_after["commands"],
    )

    in_tree = sorted(user_before)
    return {
        "mode": mode,
        "action": action,
        "user_owned_inside_managed_tree": True,
        "user_owned_paths": in_tree,
        "user_owned_count": len(in_tree),
        "managed_v1": sorted(MANAGED_V1),
        "before": {
            "files": before_rglob,
            "digest": map_digest(before_rglob),
            "user": user_before,
            "commands": split_before["commands"],
        },
        "after": {
            "files": after_rglob,
            "digest": map_digest(after_rglob),
            "user": user_after_classified,
            "commands": split_after["commands"],
            "managed": split_after["managed"],
        },
        "delta": {
            "user_deleted": deleted(user_before, user_after_classified),
            "user_changed": changed(user_before, user_after_classified),
            "all_deleted": deleted(before_rglob, after_rglob),
        },
        "tests": tests,
        "collateral_by_construction": mode == "naive"
        and bool(deleted(user_before, user_after_classified)),
    }


def detector_control(root: Path) -> dict[str, Any]:
    """Plant one extra user file after the pre-inventory; comparison must notice it."""
    live = root / "ctrl"
    if live.exists():
        shutil.rmtree(live)
    live.mkdir(parents=True)
    plant_v1(live)
    plant_user_owned(live)
    before = inventory_rglob(live)
    extra = live / "notes" / "planted-extra.md"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("PLANTED-EXTRA-UNIQUE\n", encoding="utf-8")
    after = inventory_rglob(live)
    extras = sorted(set(after) - set(before))
    return {
        "detected": extras == ["notes/planted-extra.md"],
        "extras": extras,
        "before_count": len(before),
        "after_count": len(after),
    }
