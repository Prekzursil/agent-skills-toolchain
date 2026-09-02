"""Isolated-worktree repair batch: one shard per candidate, no repair commit."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from candidates import CANDIDATES, assert_fifteen  # noqa: E402
from isolate import (  # noqa: E402
    IsolateError,
    Shard,
    assert_isolated,
    git,
    git_env,
    porcelain_paths,
    provision_shard,
    staged_paths,
    write_tree,
)


def run_script(root: Path, rel: str, cwd_rel: str) -> dict[str, Any]:
    script = root / rel
    cwd = root / cwd_rel
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"exit_code": proc.returncode, "output": text[-800:]}


def apply_scoped(shard: Shard, files: dict[str, str], declared: list[str]) -> None:
    extra = sorted(set(files) - set(declared))
    if extra:
        raise IsolateError(f"repair files outside declared scope: {extra}")
    for rel in files:
        if rel.startswith("canary/") or rel == "canary":
            raise IsolateError(f"repair must not write canary path {rel}")
    write_tree(shard.path, files)


def restore_files(shard: Shard, files: dict[str, str]) -> None:
    """Byte restore (no git checkout/restore)."""
    write_tree(shard.path, files)


def _scope_ok(changed: list[str], declared: list[str]) -> tuple[bool, list[str]]:
    allowed = set(declared)
    extras: list[str] = []
    for rel in changed:
        if rel.startswith("canary/"):
            extras.append(rel)
            continue
        if rel in allowed:
            continue
        if rel.startswith("target/"):
            continue
        extras.append(rel)
    return (not extras, extras)


def repair_one(candidate: dict[str, Any], parent: Path, env: dict[str, str]) -> dict[str, Any]:
    shard = provision_shard(parent, candidate["id"], candidate["files_broken"], env)
    red = run_script(shard.path, candidate["intake_rel"], candidate["intake_cwd"])
    canary_before = run_script(shard.path, candidate["canary_rel"], candidate["canary_cwd"])
    apply_scoped(shard, candidate["files_fixed"], candidate["declared_scope"])
    green = run_script(shard.path, candidate["intake_rel"], candidate["intake_cwd"])
    canary_after = run_script(shard.path, candidate["canary_rel"], candidate["canary_cwd"])
    head = shard.git("rev-parse", "HEAD").stdout.strip()
    log_count = int(shard.git("rev-list", "--count", "HEAD").stdout.strip() or "0")
    changed = porcelain_paths(shard)
    scoped, extras = _scope_ok(changed, candidate["declared_scope"])
    commits_by_repair = head != shard.seed_head or log_count != 1
    red_to_green = red["exit_code"] != 0 and green["exit_code"] == 0
    canary_held = canary_before["exit_code"] == 0 and canary_after["exit_code"] == 0
    ok = red_to_green and canary_held and scoped and not commits_by_repair
    return {
        "id": candidate["id"],
        "title": candidate["title"],
        "defect_class": candidate["defect_class"],
        "shard_path": str(shard.path),
        "index_path": str(shard.index),
        "seed_head": shard.seed_head,
        "head_after_repair": head,
        "log_count": log_count,
        "repair_committed": commits_by_repair,
        "declared_scope": list(candidate["declared_scope"]),
        "changed_paths": changed,
        "scope_extras": extras,
        "scope_ok": scoped,
        "intake_red": red,
        "intake_green": green,
        "canary_before": canary_before,
        "canary_after": canary_after,
        "red_to_green": red_to_green,
        "canary_held": canary_held,
        "ok": ok,
    }


def run_batch(parent: Path | None = None) -> dict[str, Any]:
    assert_fifteen()
    own = parent is None
    if parent is None:
        parent = Path(tempfile.mkdtemp(prefix="wfa0087-batch-", dir="/tmp"))
    parent = assert_isolated(parent)
    home = parent / ".home"
    home.mkdir(parents=True, exist_ok=True)
    env = git_env(home)
    rows: list[dict[str, Any]] = []
    try:
        for cand in CANDIDATES:
            rows.append(repair_one(cand, parent / "shards", env))
        indexes = [r["index_path"] for r in rows]
        unique = len(set(indexes)) == len(indexes) == 15
        all_ok = all(r["ok"] for r in rows) and unique
        return {
            "n": len(rows),
            "rows": rows,
            "index_paths": indexes,
            "indexes_unique": unique,
            "shared_index_detected": not unique,
            "all_red_to_green": all(r["red_to_green"] for r in rows),
            "all_canary_held": all(r["canary_held"] for r in rows),
            "all_scoped": all(r["scope_ok"] for r in rows),
            "any_repair_commit": any(r["repair_committed"] for r in rows),
            "ok": all_ok,
            "parent": str(parent),
        }
    finally:
        if own:
            shutil.rmtree(parent, ignore_errors=True)


def control_shared_index(parent: Path, env: dict[str, str]) -> dict[str, Any]:
    """Two dirty targets in ONE worktree; git add -A must stage the sibling."""
    path = assert_isolated(parent / "shared-index")
    path.mkdir(parents=True, exist_ok=True)
    init = git(["init", "--object-format=sha1", "-b", "main"], path, env, check=False)
    if init.returncode != 0:
        git(["init", "-b", "main"], path, env)
    git(["config", "user.email", "wfa-0087@fixture.local"], path, env)
    git(["config", "user.name", "WFA-0087 fixture"], path, env)
    write_tree(
        path,
        {
            "a/workflow.py": "def add(x, y):\n    return x + y + 1\n",
            "b/workflow.py": "def mul(x, y):\n    return x * y + 1\n",
        },
    )
    git(["add", "-A"], path, env)
    git(["commit", "-m", "seed shared"], path, env)
    write_tree(
        path,
        {
            "a/workflow.py": "def add(x, y):\n    return x + y\n",
            "b/workflow.py": "def mul(x, y):\n    return x * y\n",
        },
    )
    git(["add", "-A"], path, env)
    staged = staged_paths(path, env)
    contamination = "a/workflow.py" in staged and "b/workflow.py" in staged
    declared = ["a/workflow.py"]
    rejected = sorted(p for p in staged if p not in declared)
    return {
        "id": "control-shared-index",
        "worktree": str(path),
        "staged": staged,
        "contamination_detected": contamination,
        "rejected_sibling_paths": rejected,
        "unit_failure_if_shared_index": True,
        "ok": contamination and "b/workflow.py" in rejected,
    }


def control_scope_and_sibling(parent: Path, env: dict[str, str]) -> dict[str, Any]:
    """Poisoned canary write is red; byte-restore (no checkout) then scoped re-apply."""
    cand = CANDIDATES[0]
    shard = provision_shard(
        parent / "scope-sib", cand["id"], cand["files_broken"], env
    )
    apply_scoped(shard, cand["files_fixed"], cand["declared_scope"])
    poison = {"canary/stable.py": "def ping():\n    return 'poisoned'\n"}
    write_tree(shard.path, poison)
    poisoned_canary = run_script(shard.path, cand["canary_rel"], cand["canary_cwd"])
    changed_poisoned = porcelain_paths(shard)
    scoped_poisoned, extras = _scope_ok(changed_poisoned, cand["declared_scope"])
    restore_files(shard, {"canary/stable.py": cand["files_broken"]["canary/stable.py"]})
    restored_canary = run_script(shard.path, cand["canary_rel"], cand["canary_cwd"])
    target_green = run_script(shard.path, cand["intake_rel"], cand["intake_cwd"])
    changed_restored = porcelain_paths(shard)
    scoped_restored, extras2 = _scope_ok(changed_restored, cand["declared_scope"])
    return {
        "id": "control-scope-sibling-revert",
        "poisoned_canary_red": poisoned_canary["exit_code"] != 0,
        "poisoned_scope_rejected": (not scoped_poisoned)
        and any(p.startswith("canary/") for p in extras),
        "restore_method": "byte-rewrite-from-spec (no git checkout/restore/reset)",
        "restored_canary_green": restored_canary["exit_code"] == 0,
        "target_still_green": target_green["exit_code"] == 0,
        "restored_scope_ok": scoped_restored,
        "poisoned_canary_output": poisoned_canary["output"],
        "extras_while_poisoned": extras,
        "extras_after_restore": extras2,
        "ok": (
            poisoned_canary["exit_code"] != 0
            and not scoped_poisoned
            and restored_canary["exit_code"] == 0
            and target_green["exit_code"] == 0
            and scoped_restored
        ),
    }


def run_controls(parent: Path | None = None) -> dict[str, Any]:
    own = parent is None
    if parent is None:
        parent = Path(tempfile.mkdtemp(prefix="wfa0087-ctrl-", dir="/tmp"))
    parent = assert_isolated(parent)
    home = parent / ".home"
    home.mkdir(parents=True, exist_ok=True)
    env = git_env(home)
    try:
        shared = control_shared_index(parent, env)
        scope = control_scope_and_sibling(parent, env)
        ok = bool(shared["ok"] and scope["ok"])
        return {
            "shared_index": shared,
            "scope_sibling": scope,
            "ok": ok,
            "parent": str(parent),
        }
    finally:
        if own:
            shutil.rmtree(parent, ignore_errors=True)


def run_campaign() -> dict[str, Any]:
    batch = run_batch()
    controls = run_controls()
    return {
        "batch": batch,
        "controls": controls,
        "ok": bool(batch["ok"] and controls["ok"]),
    }
