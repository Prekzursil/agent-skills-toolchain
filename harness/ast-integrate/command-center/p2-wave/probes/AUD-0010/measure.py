#!/usr/bin/env python3
"""Packed git size vs materialized clone disk for AUD-0010.

count-objects reports the packed/loose object store. A clone materializes a
working tree as well, so the two instruments must be allowed to disagree.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOMINATE_REL = "weight/dominate.bin"
DOMINATE_LEN = 262144
DOMINATE_BYTE = b"W"
REPEAT_LIMIT = 0.02
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0010/probe1_count_objects.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0010/probe2_timed_clone.py"
)


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "AUD-0010",
            "GIT_AUTHOR_EMAIL": "aud-0010@fixture.invalid",
            "GIT_COMMITTER_NAME": "AUD-0010",
            "GIT_COMMITTER_EMAIL": "aud-0010@fixture.invalid",
            "GIT_AUTHOR_DATE": "2026-08-24T18:00:00Z",
            "GIT_COMMITTER_DATE": "2026-08-24T18:00:00Z",
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def run_git(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=git_env(),
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT git {' '.join(args)}"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def parse_count_objects(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        fields[key.strip()] = val.strip()
    return fields


def int_field(fields: dict[str, str], name: str) -> int:
    raw = fields.get(name, "0").split()[0]
    try:
        return int(float(raw))
    except ValueError:
        return 0


def human_bytes(val: str) -> int:
    parts = val.replace(",", "").split()
    if not parts:
        return 0
    try:
        number = float(parts[0])
    except ValueError:
        return 0
    unit = parts[1] if len(parts) > 1 else ""
    mul = {
        "": 1024,
        "bytes": 1,
        "byte": 1,
        "B": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
    }.get(unit, 1024)
    return int(number * mul)


def packed_bytes_from_fields(fields: dict[str, str]) -> int:
    return human_bytes(fields.get("size", "0")) + human_bytes(
        fields.get("size-pack", "0")
    )


def within_2pct(a: int, b: int) -> bool:
    if a == 0 and b == 0:
        return True
    return abs(a - b) / max(a, b) <= REPEAT_LIMIT


def du_bytes(path: Path) -> int:
    proc = subprocess.run(
        ["du", "-sb", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "du failed").strip())
    return int((proc.stdout or "0").split()[0])


def count_objects(repo: Path) -> dict[str, Any]:
    code, text = run_git(["count-objects", "-vH"], repo)
    fields = parse_count_objects(text)
    return {
        "exit_code": code,
        "raw": text,
        "fields": fields,
        "packed_bytes": packed_bytes_from_fields(fields) if code == 0 else 0,
        "object_count": int_field(fields, "count") + int_field(fields, "in-pack"),
        "packs": int_field(fields, "packs"),
    }


def blob_inventory(repo: Path, limit: int = 10) -> list[dict[str, Any]]:
    rev = subprocess.run(
        ["git", "-c", "safe.directory=*", "rev-list", "--objects", "--all"],
        cwd=str(repo),
        capture_output=True,
        timeout=60,
        env=git_env(),
    )
    if rev.returncode != 0:
        return []
    chk = subprocess.run(
        [
            "git",
            "-c",
            "safe.directory=*",
            "cat-file",
            "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)",
        ],
        cwd=str(repo),
        input=rev.stdout,
        capture_output=True,
        timeout=60,
        env=git_env(),
    )
    rows: list[dict[str, Any]] = []
    for line in (chk.stdout or b"").decode("utf-8", "replace").splitlines():
        parts = line.split(" ", 3)
        if len(parts) < 3 or parts[0] != "blob":
            continue
        try:
            size = int(parts[2])
        except ValueError:
            continue
        path = parts[3] if len(parts) > 3 else ""
        rows.append({"sha": parts[1], "bytes": size, "path": path})
    rows.sort(key=lambda r: r["bytes"], reverse=True)
    return rows[:limit]


def build_fixture(root: Path) -> Path:
    repo = root / "src"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "weight").mkdir(parents=True, exist_ok=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text(
        "AUD-0010 fixture: one compressible blob dominates weight.\n",
        encoding="utf-8",
    )
    (repo / DOMINATE_REL).write_bytes(DOMINATE_BYTE * DOMINATE_LEN)
    (repo / "src" / "tiny.py").write_text("print('aud-0010')\n", encoding="utf-8")
    code, text = run_git(["-c", "init.defaultBranch=main", "init"], repo)
    if code != 0:
        raise RuntimeError(f"git init failed: {text}")
    code, text = run_git(["add", "-A"], repo)
    if code != 0:
        raise RuntimeError(f"git add failed: {text}")
    code, text = run_git(["commit", "-m", "AUD-0010 fixture"], repo)
    if code != 0:
        raise RuntimeError(f"git commit failed: {text}")
    run_git(["gc", "--quiet", "--prune=now"], repo)
    return repo


def timed_clone(src: Path, dst: Path) -> dict[str, Any]:
    if dst.exists():
        shutil.rmtree(dst)
    start = time.perf_counter()
    code, text = run_git(
        ["clone", "--no-hardlinks", "--", str(src), str(dst)],
        src.parent,
        timeout=90,
    )
    wall_ms = (time.perf_counter() - start) * 1000.0
    disk = du_bytes(dst) if dst.exists() and code == 0 else 0
    return {
        "exit_code": code,
        "raw": text[-4000:],
        "wall_ms": round(wall_ms, 3),
        "clone_disk_bytes": disk,
        "dst": str(dst),
    }


def owner_repo_row() -> dict[str, Any]:
    git = REPO / ".git"
    present = git.exists()
    kind = "absent"
    if git.is_dir():
        kind = "directory"
    elif git.is_file():
        kind = "file"
    row: dict[str, Any] = {
        "id": "ast-integrate",
        "path": str(REPO),
        "in_scope": True,
        "git_present": present,
        "git_kind": kind,
        "filesystem_bytes": du_bytes(REPO),
        "clone_cost": "measured" if present else "NOT-CHECKED",
        "packed_bytes": "NOT-CHECKED",
        "clone_disk_bytes": "NOT-CHECKED",
        "clone_wall_ms": "NOT-CHECKED",
        "reason": None
        if present
        else "worktree has no .git; git rev-parse is not-a-repository",
    }
    if present:
        packed = count_objects(REPO)
        row["packed_bytes"] = packed["packed_bytes"]
        row["count_objects_raw"] = packed["raw"]
    return row


def measure_fixture() -> dict[str, Any]:
    scratch = Path(tempfile.mkdtemp(prefix="aud0010-"))
    try:
        src = build_fixture(scratch)
        packed1 = count_objects(src)
        packed2 = count_objects(src)
        blobs = blob_inventory(src)
        clone1 = timed_clone(src, scratch / "clone-a")
        clone2 = timed_clone(src, scratch / "clone-b")
        packed_ok = (
            packed1["exit_code"] == 0
            and packed2["exit_code"] == 0
            and packed1["packed_bytes"] > 0
            and within_2pct(packed1["packed_bytes"], packed2["packed_bytes"])
        )
        clone_ok = (
            clone1["exit_code"] == 0
            and clone2["exit_code"] == 0
            and clone1["clone_disk_bytes"] > 0
            and within_2pct(clone1["clone_disk_bytes"], clone2["clone_disk_bytes"])
        )
        packed = packed1["packed_bytes"]
        clone_disk = clone1["clone_disk_bytes"]
        dominant = blobs[0] if blobs else {"path": "", "bytes": 0, "sha": ""}
        return {
            "packed_run1": packed1,
            "packed_run2": packed2,
            "clone_run1": clone1,
            "clone_run2": clone2,
            "blobs": blobs,
            "packed_bytes": packed,
            "clone_disk_bytes": clone_disk,
            "clone_wall_ms": clone1["wall_ms"],
            "packed_repeat_ok": packed_ok,
            "clone_repeat_ok": clone_ok,
            "packed_equals_clone": packed == clone_disk,
            "clone_exceeds_packed": clone_disk > packed,
            "dominant_path": dominant.get("path") or "",
            "dominant_blob_bytes": int(dominant.get("bytes") or 0),
            "dominate_planted_bytes": DOMINATE_LEN,
            "object_count": packed1["object_count"],
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def live_bundle() -> dict[str, Any]:
    return {"fixture": measure_fixture(), "owner": owner_repo_row()}
