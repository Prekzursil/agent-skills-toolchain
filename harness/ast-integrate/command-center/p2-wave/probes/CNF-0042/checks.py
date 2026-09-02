"""Shared live checks for CNF-0042 probes and emit."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rollback import execute, inventory, sha256_bytes
from scenario import (
    COLLISION_SHIPPED_REL,
    COLLISION_USER_REL,
    N_ONLY_REL,
    N1_PLUGIN_BYTES,
    PLUGIN,
    USER_ITEMS,
    build_work,
)

N_ONLY_PROFILE_REL = f"{PLUGIN}/{N_ONLY_REL}"


def preservation_report(
    pre: dict[str, dict[str, Any]], post: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    passed = True
    for rel, data, role in USER_ITEMS:
        expected = sha256_bytes(data)
        before = pre.get(rel)
        after = post.get(rel)
        ok = (
            before is not None
            and after is not None
            and before.get("sha256") == expected
            and after.get("sha256") == expected
            and after.get("bytes") == len(data)
        )
        if not ok:
            passed = False
        items.append(
            {
                "path": rel,
                "role": role,
                "expected_sha256": expected,
                "pre_sha256": None if before is None else before.get("sha256"),
                "post_sha256": None if after is None else after.get("sha256"),
                "present_before": before is not None,
                "present_after": after is not None,
                "byte_identical": bool(ok),
            }
        )
    return {"passed": passed, "items": items}


def collision_report(
    pre: dict[str, dict[str, Any]], post: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    user_ok = (
        COLLISION_USER_REL in post
        and post[COLLISION_USER_REL]["sha256"]
        == sha256_bytes(next(d for r, d, _ in USER_ITEMS if r == COLLISION_USER_REL))
        and pre.get(COLLISION_USER_REL, {}).get("sha256")
        == post[COLLISION_USER_REL]["sha256"]
    )
    shipped_expected = sha256_bytes(N1_PLUGIN_BYTES["commands/status.md"])
    shipped_restored = (
        COLLISION_SHIPPED_REL in post
        and post[COLLISION_SHIPPED_REL]["sha256"] == shipped_expected
    )
    same_basename = Path(COLLISION_USER_REL).name == Path(COLLISION_SHIPPED_REL).name
    passed = bool(user_ok and shipped_restored and same_basename)
    return {
        "passed": passed,
        "basename": Path(COLLISION_USER_REL).name,
        "user_path": COLLISION_USER_REL,
        "shipped_path": COLLISION_SHIPPED_REL,
        "user_survived_byte_identical": bool(user_ok),
        "shipped_restored_to_n1": bool(shipped_restored),
    }


def removal_report(
    pre: dict[str, dict[str, Any]], post: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    present_before = N_ONLY_PROFILE_REL in pre
    present_after = N_ONLY_PROFILE_REL in post
    passed = bool(present_before and not present_after)
    return {
        "path": N_ONLY_PROFILE_REL,
        "present_before": present_before,
        "present_after": present_after,
        "passed": passed,
        "vacuous": not present_before,
    }


def wholesale_destruction_report(post: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = [rel for rel, _data, _role in USER_ITEMS if rel not in post]
    passed = len(missing) > 0
    return {
        "passed": passed,
        "destroyed_user_paths": missing,
        "surviving_user_paths": [
            rel for rel, _data, _role in USER_ITEMS if rel in post
        ],
        "discriminates": passed,
    }


def run_set_difference(work: Path) -> dict[str, Any]:
    profile = work / "profile"
    pre = inventory(profile)
    transcript = execute(work, "set-difference")
    post = inventory(profile)
    return {
        "pre": pre,
        "post": post,
        "transcript": transcript,
        "preservation": preservation_report(pre, post),
        "collision": collision_report(pre, post),
        "removal": removal_report(pre, post),
    }


def run_wholesale(work: Path) -> dict[str, Any]:
    profile = work / "profile"
    pre = inventory(profile)
    transcript = execute(work, "wholesale")
    post = inventory(profile)
    return {
        "pre": pre,
        "post": post,
        "transcript": transcript,
        "destruction": wholesale_destruction_report(post),
    }


def live_both_engines(work: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build once, clone-style: set-difference on `work`, wholesale on sibling."""
    build_work(work)
    sd = run_set_difference(work)
    wholesale_work = work.parent / (work.name + "-wholesale")
    if wholesale_work.exists():
        raise SystemExit(f"wholesale work already exists: {wholesale_work}")
    build_work(wholesale_work)
    wh = run_wholesale(wholesale_work)
    return sd, wh
