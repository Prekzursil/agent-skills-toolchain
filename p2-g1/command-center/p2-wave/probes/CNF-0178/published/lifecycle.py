#!/usr/bin/env python3
"""Marketplace lifecycle client shipped inside the published registry artifact.

This file is the install/update/rollback/uninstall implementation that a
machine without a repository checkout would run after downloading the
published index. It uses only the stdlib and the registry directory beside it.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DENIED_PARTS = {".git", ".svn", ".hg"}
DENIED_NAMES = {"WORK-UNIT-CATALOG.json", ".git"}


def die(msg: str, code: int = 1) -> None:
    print(f"FAILED:lifecycle {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        die(f"unreadable {path}: {exc}")
    if not isinstance(data, dict):
        die(f"not an object: {path}")
    return data


def pkg_src(registry: Path, pkg_id: str, version: str) -> Path:
    src = registry / "packages" / pkg_id / version
    if not (src / "package.json").is_file():
        die(f"published package missing {pkg_id}@{version}")
    return src


def pkg_root(profile: Path, pkg_id: str) -> Path:
    return profile / "packages" / pkg_id


def state_path(profile: Path, pkg_id: str) -> Path:
    return pkg_root(profile, pkg_id) / "state.json"


def current_dir(profile: Path, pkg_id: str) -> Path:
    return pkg_root(profile, pkg_id) / "current"


def previous_dir(profile: Path, pkg_id: str) -> Path:
    return pkg_root(profile, pkg_id) / "previous"


def user_data_dir(profile: Path) -> Path:
    return profile / "user-data"


def should_skip(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & DENIED_PARTS:
        return True
    if rel.name in DENIED_NAMES:
        return True
    return False


def copy_published_tree(src: Path, dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if should_skip(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(rel.as_posix())
    if "package.json" not in copied:
        die(f"package.json not copied from {src}")
    return copied


def write_state(profile: Path, pkg_id: str, payload: dict) -> None:
    path = state_path(profile, pkg_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_state(profile: Path, pkg_id: str) -> dict:
    path = state_path(profile, pkg_id)
    if not path.is_file():
        die(f"package not installed: {pkg_id}")
    return load_json(path)


def owned_rel_paths(pkg_id: str) -> list[str]:
    return [
        f"packages/{pkg_id}/current",
        f"packages/{pkg_id}/previous",
        f"packages/{pkg_id}/state.json",
    ]


def cmd_install(registry: Path, profile: Path, pkg_id: str, version: str) -> None:
    src = pkg_src(registry, pkg_id, version)
    meta = load_json(src / "package.json")
    if meta.get("id") != pkg_id or str(meta.get("version")) != version:
        die(f"package.json identity mismatch for {pkg_id}@{version}")
    dest = current_dir(profile, pkg_id)
    if dest.exists():
        shutil.rmtree(dest)
    copied = copy_published_tree(src, dest)
    write_state(
        profile,
        pkg_id,
        {
            "id": pkg_id,
            "version": version,
            "previous_version": None,
            "failure_class": meta.get("failure_class"),
            "owned": owned_rel_paths(pkg_id),
            "copied_files": copied,
            "behavior_token": meta.get("behavior_token"),
            "entrypoint": meta.get("entrypoint", "commands/echo.py"),
        },
    )
    print(f"OK install {pkg_id}@{version} files={len(copied)}")


def cmd_update(registry: Path, profile: Path, pkg_id: str, version: str) -> None:
    st = read_state(profile, pkg_id)
    cur = current_dir(profile, pkg_id)
    prev = previous_dir(profile, pkg_id)
    if not cur.is_dir():
        die(f"cannot update; current tree missing for {pkg_id}")
    if prev.exists():
        shutil.rmtree(prev)
    shutil.copytree(cur, prev)
    src = pkg_src(registry, pkg_id, version)
    meta = load_json(src / "package.json")
    shutil.rmtree(cur)
    copied = copy_published_tree(src, cur)
    write_state(
        profile,
        pkg_id,
        {
            "id": pkg_id,
            "version": version,
            "previous_version": st.get("version"),
            "previous_behavior_token": st.get("behavior_token"),
            "failure_class": meta.get("failure_class"),
            "owned": owned_rel_paths(pkg_id),
            "copied_files": copied,
            "behavior_token": meta.get("behavior_token"),
            "entrypoint": meta.get("entrypoint", "commands/echo.py"),
        },
    )
    print(f"OK update {pkg_id}@{st.get('version')}->{version} files={len(copied)}")


def cmd_rollback(profile: Path, pkg_id: str) -> None:
    st = read_state(profile, pkg_id)
    cur = current_dir(profile, pkg_id)
    prev = previous_dir(profile, pkg_id)
    if not prev.is_dir():
        die(f"no previous version to rollback for {pkg_id}")
    swap = pkg_root(profile, pkg_id) / "_swap"
    if swap.exists():
        shutil.rmtree(swap)
    shutil.move(str(cur), str(swap))
    shutil.move(str(prev), str(cur))
    shutil.move(str(swap), str(prev))
    restored_meta = load_json(cur / "package.json")
    write_state(
        profile,
        pkg_id,
        {
            "id": pkg_id,
            "version": restored_meta.get("version"),
            "previous_version": st.get("version"),
            "failure_class": restored_meta.get("failure_class"),
            "owned": owned_rel_paths(pkg_id),
            "copied_files": sorted(
                p.relative_to(cur).as_posix() for p in cur.rglob("*") if p.is_file()
            ),
            "behavior_token": restored_meta.get("behavior_token"),
            "entrypoint": restored_meta.get("entrypoint", "commands/echo.py"),
            "rolled_back_from": st.get("version"),
        },
    )
    print(f"OK rollback {pkg_id} -> {restored_meta.get('version')}")


def _purge_user_data(profile: Path) -> None:
    ud = user_data_dir(profile)
    if ud.exists():
        shutil.rmtree(ud)


def cmd_uninstall(profile: Path, pkg_id: str, purge_user_data: bool) -> None:
    st = read_state(profile, pkg_id)
    if purge_user_data:
        _purge_user_data(profile)
        print("WARN purge-user-data removed user-data/")
    elif st.get("failure_class") == "delete-user-data":
        # Known-broken published package: uninstall deletes seeded user files.
        _purge_user_data(profile)
        print("BROKEN-PACKAGE deleted user-data/")
    root = pkg_root(profile, pkg_id)
    if root.exists():
        shutil.rmtree(root)
    print(f"OK uninstall {pkg_id}")


def cmd_run(profile: Path, pkg_id: str) -> str:
    st = read_state(profile, pkg_id)
    entry = current_dir(profile, pkg_id) / str(st.get("entrypoint") or "commands/echo.py")
    if not entry.is_file():
        die(f"entrypoint missing: {entry}")
    proc = subprocess.run(
        [sys.executable, "-B", str(entry)],
        cwd=str(entry.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        die(f"run failed rc={proc.returncode} {(proc.stderr or '')[-400:]}")
    print(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Published-artifact marketplace lifecycle")
    parser.add_argument("verb", choices=["install", "update", "rollback", "uninstall", "run"])
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--id", dest="pkg_id", required=True)
    parser.add_argument("--version", default=None)
    parser.add_argument("--purge-user-data", action="store_true")
    args = parser.parse_args()
    profile = args.profile.resolve()
    profile.mkdir(parents=True, exist_ok=True)
    user_data_dir(profile).mkdir(parents=True, exist_ok=True)
    registry = args.registry.resolve() if args.registry else Path(__file__).resolve().parent
    if args.verb in {"install", "update"}:
        if not args.version:
            die(f"{args.verb} requires --version")
        if args.verb == "install":
            cmd_install(registry, profile, args.pkg_id, args.version)
        else:
            cmd_update(registry, profile, args.pkg_id, args.version)
    elif args.verb == "rollback":
        cmd_rollback(profile, args.pkg_id)
    elif args.verb == "uninstall":
        cmd_uninstall(profile, args.pkg_id, args.purge_user_data)
    elif args.verb == "run":
        cmd_run(profile, args.pkg_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
