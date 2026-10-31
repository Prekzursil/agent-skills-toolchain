#!/usr/bin/env python3
"""Isolate the published artifact away from the git worktree and drive lifecycle."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PUBLISHED_SRC = HERE / "published"

from differ import (  # noqa: E402
    byte_identical,
    diff,
    full_profile_manifest,
    user_data_manifest,
)

V1_BEHAVIOR = "BEHAVIOR:alpha-v1"
V2_BEHAVIOR = "BEHAVIOR:beta-v2"
REPO_MARKERS = ("WORK-UNIT-CATALOG.json", ".git")


@dataclass
class Isolated:
    tmp: Path
    registry: Path
    lifecycle: Path
    profile: Path


def copy_published(dest: Path) -> Path:
    """Copy the published artifact. This is the only input the client may use."""
    shutil.copytree(PUBLISHED_SRC, dest, dirs_exist_ok=True)
    return dest


def seed_user_data(profile: Path, files: dict[str, bytes]) -> dict[str, str]:
    ud = profile / "user-data"
    ud.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    from differ import digest_bytes

    for rel, raw in files.items():
        path = ud / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        hashes[f"user-data/{rel}"] = digest_bytes(raw)
    return hashes


def repo_absence(install_root: Path, lifecycle_py: Path) -> dict[str, Any]:
    """Assert the install path is not a repository checkout."""
    install_root = install_root.resolve()
    hits: list[str] = []
    for marker in REPO_MARKERS:
        for found in install_root.rglob(marker):
            hits.append(found.relative_to(install_root).as_posix())
    catalog_in_profile = list((install_root).rglob("WORK-UNIT-CATALOG.json"))
    git_in_profile = [p for p in install_root.rglob(".git") if p.is_dir() or p.name == ".git"]
    life = lifecycle_py.resolve()
    under_repo = False
    try:
        life.relative_to(REPO.resolve())
        under_repo = True
    except ValueError:
        under_repo = False
    try:
        install_root.relative_to(REPO.resolve())
        profile_under_repo = True
    except ValueError:
        profile_under_repo = False
    return {
        "install_root": str(install_root),
        "lifecycle_path": str(life),
        "lifecycle_loaded_from_published_copy": (not under_repo) and life.name == "lifecycle.py",
        "profile_not_under_repo": not profile_under_repo,
        "repo_markers_in_install_tree": hits,
        "catalog_files_installed": [p.as_posix() for p in catalog_in_profile],
        "git_dirs_installed": [p.as_posix() for p in git_in_profile],
        "ok": (
            not under_repo
            and not profile_under_repo
            and not hits
            and not catalog_in_profile
            and not git_in_profile
        ),
    }


def run_lifecycle(iso: Isolated, verb: str, extra: list[str]) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        "-B",
        str(iso.lifecycle),
        verb,
        "--registry",
        str(iso.registry),
        "--profile",
        str(iso.profile),
        *extra,
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(iso.registry)
    proc = subprocess.run(
        cmd,
        cwd=str(iso.registry),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"lifecycle {verb} rc={proc.returncode}\n"
            f"stdout={proc.stdout[-1500:]}\nstderr={proc.stderr[-1500:]}"
        )
    return proc


def run_behavior(iso: Isolated, pkg_id: str) -> str:
    proc = run_lifecycle(iso, "run", ["--id", pkg_id])
    return (proc.stdout or "").strip().splitlines()[-1]


def _step_row(label: str, profile: Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "step": label,
        "full": full_profile_manifest(profile),
        "user_data": user_data_manifest(profile),
    }
    if extra:
        row.update(extra)
    return row


SEED_A = {
    "notes.txt": b"owner-notes-seed-A: keep-me-byte-identical\n",
    "prefs.json": b'{"theme":"dark","keep":true,"seed":"A"}\n',
}

SEED_B = {
    "journal.md": b"# reviewer seed B\nnever-delete-this-line\n",
    "settings.json": b'{"locale":"nb-NO","seed":"B","retain":true}\n',
    "nested/keep.bin": b"\x00\x01reviewer-B-binary\xff",
}


def healthy_lifecycle(seed: dict[str, bytes]) -> dict[str, Any]:
    """install -> update -> rollback -> uninstall on an isolated published copy."""
    tmp = Path(tempfile.mkdtemp(prefix="cnf0178-healthy-"))
    try:
        iso = Isolated(
            tmp=tmp,
            registry=copy_published(tmp / "published"),
            lifecycle=tmp / "published" / "lifecycle.py",
            profile=tmp / "profile",
        )
        iso.profile.mkdir(parents=True, exist_ok=True)
        seed_hashes = seed_user_data(iso.profile, seed)
        steps: list[dict[str, Any]] = []
        steps.append(_step_row("pre-install", iso.profile))

        run_lifecycle(iso, "install", ["--id", "demo.echo", "--version", "1.0.0"])
        b1 = run_behavior(iso, "demo.echo")
        if b1 != V1_BEHAVIOR:
            raise RuntimeError(f"install behaviour {b1!r} != {V1_BEHAVIOR!r}")
        planted = repo_absence(iso.profile, iso.lifecycle)
        if not planted["ok"]:
            raise RuntimeError(f"repo-absence failed after install: {planted}")
        steps.append(_step_row("post-install", iso.profile, {"behavior": b1}))

        run_lifecycle(iso, "update", ["--id", "demo.echo", "--version", "2.0.0"])
        b2 = run_behavior(iso, "demo.echo")
        if b2 != V2_BEHAVIOR:
            raise RuntimeError(f"update behaviour {b2!r} != {V2_BEHAVIOR!r}")
        ud_after_update = user_data_manifest(iso.profile)
        if not byte_identical(steps[0]["user_data"], ud_after_update):
            raise RuntimeError("update mutated user data")
        steps.append(_step_row("post-update", iso.profile, {"behavior": b2}))

        run_lifecycle(iso, "rollback", ["--id", "demo.echo"])
        b3 = run_behavior(iso, "demo.echo")
        if b3 != V1_BEHAVIOR:
            raise RuntimeError(
                f"rollback reproduced version-string-only; behaviour {b3!r} != {V1_BEHAVIOR!r}"
            )
        # Version string must match restored package.json, but behaviour is the proof.
        state = json.loads(
            (iso.profile / "packages/demo.echo/state.json").read_text(encoding="utf-8")
        )
        if state.get("version") != "1.0.0":
            raise RuntimeError(f"rollback version field {state.get('version')!r}")
        if state.get("behavior_token") != V1_BEHAVIOR:
            raise RuntimeError("rollback restored version string without behaviour token")
        ud_after_rollback = user_data_manifest(iso.profile)
        if not byte_identical(steps[0]["user_data"], ud_after_rollback):
            raise RuntimeError("rollback mutated user data (FC-11347)")
        steps.append(
            _step_row(
                "post-rollback",
                iso.profile,
                {
                    "behavior": b3,
                    "restored_version": state.get("version"),
                    "rolled_back_from": state.get("rolled_back_from"),
                },
            )
        )

        run_lifecycle(iso, "uninstall", ["--id", "demo.echo"])
        owned = iso.profile / "packages" / "demo.echo"
        if owned.exists():
            raise RuntimeError("uninstall left owned package tree")
        ud_after = user_data_manifest(iso.profile)
        if not byte_identical(steps[0]["user_data"], ud_after):
            raise RuntimeError(
                f"healthy uninstall changed user data: {diff(steps[0]['user_data'], ud_after)}"
            )
        steps.append(_step_row("post-uninstall", iso.profile))
        return {
            "ok": True,
            "seed_hashes": seed_hashes,
            "behaviors": {
                "install": b1,
                "update": b2,
                "rollback": b3,
            },
            "repo_absence": planted,
            "user_data_byte_identical_after_uninstall": True,
            "user_data_byte_identical_after_rollback": True,
            "owned_paths_removed": not owned.exists(),
            "steps": [
                {
                    "step": s["step"],
                    "user_data": s["user_data"],
                    "full": s["full"],
                    "full_file_count": len(s["full"]),
                    **{k: v for k, v in s.items() if k not in {"full", "user_data", "step"}},
                }
                for s in steps
            ],
            "lifecycle_module": planted["lifecycle_path"],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def known_broken_caught(seed: dict[str, bytes]) -> dict[str, Any]:
    """A package whose uninstall deletes a seeded file must be caught by the differ."""
    tmp = Path(tempfile.mkdtemp(prefix="cnf0178-broken-"))
    try:
        iso = Isolated(
            tmp=tmp,
            registry=copy_published(tmp / "published"),
            lifecycle=tmp / "published" / "lifecycle.py",
            profile=tmp / "profile",
        )
        iso.profile.mkdir(parents=True, exist_ok=True)
        seed_user_data(iso.profile, seed)
        before = user_data_manifest(iso.profile)
        if not before:
            raise RuntimeError("seed produced empty user-data manifest")
        run_lifecycle(iso, "install", ["--id", "evil.purge", "--version", "1.0.0"])
        after_install = user_data_manifest(iso.profile)
        if not byte_identical(before, after_install):
            raise RuntimeError("evil install mutated user data before uninstall")
        run_lifecycle(iso, "uninstall", ["--id", "evil.purge"])
        after = user_data_manifest(iso.profile)
        delta = diff(before, after)
        caught = not delta["empty"]
        if not caught:
            raise RuntimeError("differ silent: known-broken uninstall left user-data identical")
        return {
            "ok": True,
            "caught": True,
            "before": before,
            "after": after,
            "diff": delta,
            "seed_keys": sorted(before),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def differ_both_states(seed: dict[str, bytes]) -> dict[str, Any]:
    """Healthy uninstall: empty user-data diff. Broken uninstall: non-empty diff."""
    healthy = healthy_lifecycle(seed)
    broken = known_broken_caught(seed)
    if not healthy["ok"] or not broken["ok"]:
        raise RuntimeError("both-states driver failed")
    if not broken["caught"]:
        raise RuntimeError("broken state not discriminated")
    if not healthy["user_data_byte_identical_after_uninstall"]:
        raise RuntimeError("healthy state not discriminated")
    return {"ok": True, "healthy": healthy, "broken": broken}
