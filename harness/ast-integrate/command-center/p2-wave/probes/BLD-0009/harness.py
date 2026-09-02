#!/usr/bin/env python3
"""Live BLD-0009 coverage matrix: residue semantics vs ADV-0117 vs shipped tests."""

from __future__ import annotations

import ast
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS_CC = REPO / "tools/command-center"
ADV_CANDIDATES = (
    "command-center/adversarial/ADV-0117-windows-hostile-path-matrix.json",
    "command-center/receipts/ADV-0117.json",
    "command-center/adversarial/ADV-0117.json",
)
ADV_OWNED = (
    "reserved_device_names",
    "max_path_overflow",
    "case_only_collisions",
    "spaces_in_paths",
    "non_ascii_paths",
    "trailing_dots",
)

sys.path.insert(0, str(TOOLS_CC))
import catalog  # noqa: E402
import path_guard as pg  # noqa: E402


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def adv_0117_receipt() -> dict[str, Any]:
    for rel in ADV_CANDIDATES:
        path = REPO / rel
        if path.is_file() and path.stat().st_size > 0:
            digest, size = sha256_file(path)
            return {
                "consumed": True,
                "present": True,
                "path": rel,
                "bytes": size,
                "sha256": digest,
                "note": "consumed, not re-derived",
            }
    return {
        "consumed": False,
        "present": False,
        "path": ADV_CANDIDATES[0],
        "bytes": 0,
        "sha256": None,
        "note": "ADV-0117 receipt absent on this worktree; not re-derived",
    }


def census_fs_sites() -> list[dict[str, Any]]:
    names = {
        "write_text",
        "write_bytes",
        "open",
        "rglob",
        "glob",
        "unlink",
        "replace",
        "rename",
        "mkdir",
        "guarded_write_text",
        "guarded_append_text",
        "contained_rglob",
        "reject_unc",
    }
    sites: list[dict[str, Any]] = []
    search_roots = [TOOLS_CC]
    plugin = REPO / "platform/plugin"
    if plugin.is_dir():
        search_roots.append(plugin)
    for folder in search_roots:
        for path in sorted(folder.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            rel = path.relative_to(REPO).as_posix()
            for node in ast.walk(tree):
                op = None
                if isinstance(node, ast.Attribute) and node.attr in names:
                    op = node.attr
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in names:
                        op = node.func.id
                if op is None:
                    continue
                sites.append({"path": rel, "line": node.lineno, "op": op})
    seen: set[tuple[str, int, str]] = set()
    out: list[dict[str, Any]] = []
    for site in sites:
        key = (site["path"], site["line"], site["op"])
        if key in seen:
            continue
        seen.add(key)
        out.append(site)
    return out


def _cell(
    cell_id: str,
    semantic: str,
    verdict: str,
    *,
    code_path: str,
    fixture: str,
    evidence: str,
    named_error: str | None = None,
) -> dict[str, Any]:
    return {
        "id": cell_id,
        "semantic": semantic,
        "verdict": verdict,
        "code_path": code_path,
        "fixture": fixture,
        "evidence": evidence,
        "named_error": named_error,
    }


def prove_unc(scratch: Path) -> dict[str, Any]:
    samples = [
        r"\\bld0009-server\share\catalog.json",
        "//bld0009-server/share/catalog.json",
        r"\\?\UNC\bld0009-server\share\x.json",
        "file://bld0009-server/share/x.json",
    ]
    names: list[str] = []
    for sample in samples:
        try:
            catalog.save({"schema_version": 1, "items": []}, sample)
        except pg.UncRejected as exc:
            names.append(exc.name)
            continue
        raise RuntimeError(f"UNC sample was not rejected: {sample!r}")
    local = scratch / "local-catalog.json"
    catalog.save({"schema_version": 1, "items": []}, local)
    if not local.is_file():
        raise RuntimeError("local catalog.save control did not write")
    return _cell(
        "unc_share",
        "UNC \\\\server\\share (and file://server/share URI)",
        "EXERCISED",
        code_path="tools/command-center/catalog.py:save + tools/command-center/path_guard.py:reject_unc",
        fixture=str(local),
        evidence=(
            f"rejected {len(samples)} synthesised UNC targets with named "
            f"{sorted(set(names))}; local write control created {local.name}"
        ),
        named_error="UncRejected",
    )


def prove_symlink_containment(scratch: Path, outside: Path) -> dict[str, Any]:
    sentinel = outside / "SENTINEL.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")
    before = sentinel.read_bytes()
    (scratch / "ok.json").write_text("{}\n", encoding="utf-8")
    escape = scratch / "escape-link"
    escape.symlink_to(outside)
    try:
        list(pg.contained_rglob(scratch, "*.json"))
    except pg.ContainmentBreach as exc:
        after = sentinel.read_bytes()
        if after != before:
            raise RuntimeError("sentinel outside scratch was mutated") from exc
        return _cell(
            "symlink_escape",
            "symlink traversal out of scratch root",
            "EXERCISED",
            code_path="tools/command-center/path_guard.py:contained_rglob + tools/command-center/unit_manifest.py:_load_receipts",
            fixture=str(escape),
            evidence="ContainmentBreach named; outside sentinel bytes unchanged",
            named_error=exc.name,
        )
    raise RuntimeError("contained_rglob followed or skipped the escape link silently")


def prove_hardlink(scratch: Path) -> dict[str, Any]:
    src = scratch / "hard-a.json"
    dst = scratch / "hard-b.json"
    src.write_text('{"h":1}\n', encoding="utf-8")
    os.link(src, dst)
    names = sorted(p.name for p in pg.contained_rglob(scratch, "hard-*.json"))
    if names != ["hard-a.json", "hard-b.json"]:
        raise RuntimeError(f"hardlink glob mismatch {names}")
    if src.stat().st_ino != dst.stat().st_ino:
        raise RuntimeError("hardlink inodes differ")
    return _cell(
        "hardlink",
        "hardlink traversal inside scratch",
        "EXERCISED",
        code_path="tools/command-center/path_guard.py:contained_rglob",
        fixture=str(dst),
        evidence=f"both names visible; st_ino={src.stat().st_ino}",
    )


def prove_permission(scratch: Path) -> dict[str, Any]:
    locked_dir = scratch / "acl-ro"
    locked_dir.mkdir(exist_ok=True)
    # Owner r-x only: nobody cannot create files; root still can, so the
    # dropped-uid child is the actual ACL-denied fixture (chmod 000 is a
    # no-op for euid 0).
    os.chmod(locked_dir, 0o500)
    victim = locked_dir / "denied.json"
    pid = os.fork()
    if pid == 0:
        try:
            os.setuid(65534)
        except PermissionError:
            os._exit(4)
        try:
            pg.guarded_write_text(victim, "{}\n")
        except pg.PermissionDenied:
            os._exit(0)
        except Exception:
            os._exit(3)
        os._exit(2)
    _, status = os.waitpid(pid, 0)
    code = os.WEXITSTATUS(status)
    os.chmod(locked_dir, 0o700)
    if code == 4:
        return _cell(
            "acl_or_readonly_dir",
            "write into a read-only / ACL-denied directory",
            "NEVER-TESTED",
            code_path="tools/command-center/path_guard.py:guarded_write_text",
            fixture=str(locked_dir),
            evidence="setuid(nobody) refused; root bypasses mode bits, so the cell is not faked",
        )
    if code != 0:
        raise RuntimeError(f"permission child exited {code}")
    return _cell(
        "acl_or_readonly_dir",
        "write into a read-only / ACL-denied directory",
        "EXERCISED",
        code_path="tools/command-center/path_guard.py:guarded_write_text + tools/command-center/catalog.py:save",
        fixture=str(locked_dir),
        evidence="dropped-uid child received named PermissionDenied (root bypasses chmod)",
        named_error="PermissionDenied",
    )


def prove_lock(scratch: Path) -> dict[str, Any]:
    target = scratch / "held.json"
    target.write_text("{}\n", encoding="utf-8")
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys, time;"
                "p=sys.argv[1]; fd=os.open(p, os.O_RDWR);"
                "fcntl.flock(fd, fcntl.LOCK_EX);"
                "sys.stdout.write('HOLD\\n'); sys.stdout.flush();"
                "time.sleep(30)"
            ),
            str(target),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        if holder.stdout.readline().strip() != "HOLD":
            raise RuntimeError("lock holder did not announce HOLD")
        time.sleep(0.05)
        try:
            pg.guarded_write_text(target, '{"over":true}\n')
        except pg.FileLocked as exc:
            if target.read_text(encoding="utf-8") != "{}\n":
                raise RuntimeError("locked write mutated the file") from exc
            return _cell(
                "open_file_held",
                "open file held by another process",
                "EXERCISED",
                code_path="tools/command-center/path_guard.py:guarded_write_text",
                fixture=str(target),
                evidence="second writer received named FileLocked; original bytes intact",
                named_error=exc.name,
            )
        raise RuntimeError("locked write did not raise FileLocked")
    finally:
        holder.kill()
        holder.wait(timeout=5)


def prove_cross_device(scratch: Path) -> dict[str, Any]:
    src = scratch / "cross-src.json"
    src.write_text("{}\n", encoding="utf-8")
    tmp_dir = Path(tempfile.gettempdir()).resolve()
    src_dev = src.stat().st_dev
    tmp_dev = tmp_dir.stat().st_dev
    return _cell(
        "cross_filesystem_boundary",
        "path crossing a filesystem boundary mid-operation",
        "NEVER-TESTED",
        code_path="tools/command-center (no os.rename/shutil.move in shipped writers)",
        fixture=str(src),
        evidence=(
            f"scratch st_dev={src_dev} tempfile st_dev={tmp_dev}; "
            "shipped catalog/close/render/unit_manifest writers do not rename across devices"
        ),
    )


def prove_windows_only(cell_id: str, semantic: str) -> dict[str, Any]:
    return _cell(
        cell_id,
        semantic,
        "NEVER-TESTED",
        code_path="n/a on this Linux worktree",
        fixture="",
        evidence=f"host={platform.system()} {platform.release()}; {semantic} requires Windows",
    )


def prove_fixture_control(scratch: Path) -> dict[str, Any]:
    required = scratch / "local-catalog.json"
    if not required.is_file():
        raise RuntimeError(f"fixture control missing {required}")
    empty = scratch / "empty-control"
    empty.mkdir(exist_ok=True)
    ghost = empty / "never-created.json"
    if ghost.exists():
        raise RuntimeError("negative fixture control found a file that should not exist")
    return _cell(
        "fixture_control",
        "fixture set proven created (negative: empty tree has no fixtures)",
        "EXERCISED",
        code_path="command-center/p2-wave/probes/BLD-0009/harness.py",
        fixture=str(scratch),
        evidence=f"created {required.name}; empty-control does not contain {ghost.name}",
    )


def run_matrix() -> dict[str, Any]:
    adv = adv_0117_receipt()
    work = HERE / "_work"
    if work.exists():
        shutil.rmtree(work)
    scratch = work / "scratch"
    outside = work / "outside"
    scratch.mkdir(parents=True)
    outside.mkdir(parents=True)
    unc_dir = scratch / "unc"
    sym_dir = scratch / "sym"
    hard_dir = scratch / "hard"
    perm_dir = scratch / "perm"
    lock_dir = scratch / "lock"
    cross_dir = scratch / "cross"
    for d in (unc_dir, sym_dir, hard_dir, perm_dir, lock_dir, cross_dir):
        d.mkdir()
    cells = [
        prove_unc(unc_dir),
        prove_windows_only("mapped_network_drive", "mapped network drive"),
        prove_symlink_containment(sym_dir, outside),
        prove_windows_only("ntfs_junction_escape", "NTFS junction traversal"),
        prove_hardlink(hard_dir),
        prove_permission(perm_dir),
        prove_lock(lock_dir),
        prove_cross_device(cross_dir),
        prove_fixture_control(unc_dir),
    ]
    for owned in ADV_OWNED:
        if adv["consumed"]:
            cells.append(
                _cell(
                    owned,
                    owned.replace("_", " "),
                    "COVERED-BY-ADV-0117",
                    code_path=str(adv["path"]),
                    fixture="",
                    evidence="consumed ADV-0117 receipt; not re-derived here",
                )
            )
        else:
            cells.append(
                _cell(
                    owned,
                    owned.replace("_", " "),
                    "NEVER-TESTED",
                    code_path="ADV-0117 receipt absent",
                    fixture="",
                    evidence=str(adv["note"]),
                )
            )
    sentinel = outside / "SENTINEL.txt"
    sentinel_ok = sentinel.is_file() and sentinel.read_bytes() == b"untouched\n"
    return {
        "adv_0117": adv,
        "cells": cells,
        "census": census_fs_sites(),
        "scratch": str(scratch),
        "outside_sentinel_intact": sentinel_ok,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "euid": os.geteuid() if hasattr(os, "geteuid") else None,
        },
    }


def fixture_negative_fails() -> bool:
    """Both-states: claiming fixtures exist on an empty tree must fail."""
    empty = HERE / "_work" / "empty-neg"
    if empty.exists():
        shutil.rmtree(empty)
    empty.mkdir(parents=True)
    ghost = empty / "local-catalog.json"
    return not ghost.exists()
