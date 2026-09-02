#!/usr/bin/env python3
"""Package installer with a Win32 MAX_PATH preflight.

B07-style writer: plan every destination path, then either write the full
tree or write nothing. A >260 character path with LongPathsEnabled=false
must fail with an error that names the limit, never a truncated or partial
tree.

This host may not be Windows. The policy is an explicit flag; the installer
does not toggle HKLM LongPathsEnabled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

WIN32_MAX_PATH = 260
LIMIT_NAME = "MAX_PATH"
POLICY_NAME = "LongPathsEnabled"
EXIT_OK = 0
EXIT_MAX_PATH = 2
EXIT_PARTIAL_NAIVE = 3
EXIT_USAGE = 1


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(lf(data)).hexdigest()


def normalize_rel(rel: str) -> str:
    text = rel.replace("\\", "/").strip()
    if not text or text.startswith("/") or ".." in Path(text).parts:
        raise ValueError(f"refused package path {rel!r}")
    return text


def abs_dest(dest: Path) -> Path:
    """Absolute destination without creating it.

    resolve() on a missing path still returns an absolute path on this
    Python; we walk up so a missing leaf is joined onto a resolved prefix.
    """
    dest = Path(dest)
    if dest.exists():
        return dest.resolve()
    missing: list[str] = []
    cur = dest
    while not cur.exists() and cur != cur.parent:
        missing.append(cur.name)
        cur = cur.parent
    base = cur.resolve() if cur.exists() else cur.absolute()
    for name in reversed(missing):
        base = base / name
    return base


def win32_form(path: Path) -> str:
    """Backslash form of an absolute path for length measurement and messages."""
    return str(path).replace("/", "\\")


def measure(path: Path) -> dict[str, Any]:
    native = str(path)
    windows = win32_form(path)
    return {
        "native": native,
        "windows_form": windows,
        "native_chars": len(native),
        "windows_chars": len(windows),
        "measured_chars": len(native),
    }


def plan_install(dest: Path, package: dict[str, str]) -> list[dict[str, Any]]:
    root = abs_dest(dest)
    rows: list[dict[str, Any]] = []
    for raw_rel, body in package.items():
        rel = normalize_rel(raw_rel)
        target = root / rel
        row = {
            "rel": rel,
            "target": str(target),
            "bytes": len(body.encode("utf-8")),
            "sha256": sha256_bytes(body.encode("utf-8")),
            **measure(target),
        }
        rows.append(row)
    return rows


def over_limit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if int(r["measured_chars"]) > WIN32_MAX_PATH]


def refusal_message(offenders: list[dict[str, Any]]) -> str:
    worst = max(offenders, key=lambda r: int(r["measured_chars"]))
    n = int(worst["measured_chars"])
    return (
        f"install refused: destination path exceeds {LIMIT_NAME} "
        f"({WIN32_MAX_PATH} characters) while {POLICY_NAME} is false "
        f"(measured {n} characters at {worst['windows_form']}). "
        "No files were written; the destination was left empty or absent. "
        "PASS forbids a truncated or partially populated destination."
    )


def atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tst0200-tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def install(
    dest: Path,
    package: dict[str, str],
    *,
    long_paths_enabled: bool,
    naive_partial: bool = False,
) -> dict[str, Any]:
    """Install package to dest. Never leaves a partial tree on the policy path."""
    dest = Path(dest)
    existed = dest.exists()
    planned = plan_install(dest, package)
    offenders = over_limit(planned)
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": EXIT_USAGE,
        "long_paths_enabled": bool(long_paths_enabled),
        "limit_name": LIMIT_NAME,
        "limit_chars": WIN32_MAX_PATH,
        "policy_name": POLICY_NAME,
        "dest": str(abs_dest(dest)),
        "dest_existed_before": existed,
        "planned": [
            {
                "rel": r["rel"],
                "measured_chars": r["measured_chars"],
                "windows_form": r["windows_form"],
            }
            for r in planned
        ],
        "longest_measured_chars": max(int(r["measured_chars"]) for r in planned),
        "offenders": [
            {
                "rel": r["rel"],
                "measured_chars": r["measured_chars"],
                "windows_form": r["windows_form"],
            }
            for r in offenders
        ],
        "message": "",
        "wrote_rels": [],
        "created_dest": False,
        "naive_partial": bool(naive_partial),
    }

    if naive_partial:
        dest.mkdir(parents=True, exist_ok=True)
        result["created_dest"] = not existed
        wrote: list[str] = []
        for rel, body in list(package.items())[:2]:
            atomic_write(dest / normalize_rel(rel), body)
            wrote.append(normalize_rel(rel))
        result["wrote_rels"] = wrote
        result["ok"] = False
        result["exit_code"] = EXIT_PARTIAL_NAIVE
        result["message"] = (
            "naive installer wrote a prefix of the package then stopped; "
            "this is the PARTIAL tree the policy path must never produce"
        )
        return result

    if offenders and not long_paths_enabled:
        result["ok"] = False
        result["exit_code"] = EXIT_MAX_PATH
        result["message"] = refusal_message(offenders)
        result["wrote_rels"] = []
        result["created_dest"] = False
        return result

    created = not dest.exists()
    dest.mkdir(parents=True, exist_ok=True)
    result["created_dest"] = created
    wrote = []
    try:
        for rel, body in package.items():
            atomic_write(dest / normalize_rel(rel), body)
            wrote.append(normalize_rel(rel))
    except Exception as exc:
        if created:
            shutil.rmtree(dest, ignore_errors=True)
        result["ok"] = False
        result["exit_code"] = EXIT_USAGE
        result["message"] = f"install failed after mkdir: {type(exc).__name__}: {exc}"
        result["wrote_rels"] = wrote
        return result

    result["ok"] = True
    result["exit_code"] = EXIT_OK
    result["message"] = f"install complete: {len(wrote)} files"
    result["wrote_rels"] = wrote
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TST-0200 package installer")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--package", required=True, help="JSON object of rel -> text")
    parser.add_argument(
        "--long-paths-enabled",
        choices=("true", "false", "1", "0", "yes", "no"),
        default="false",
    )
    parser.add_argument("--naive-partial", action="store_true")
    args = parser.parse_args(argv)
    enabled = args.long_paths_enabled.lower() in {"true", "1", "yes"}
    package = json.loads(Path(args.package).read_text(encoding="utf-8"))
    if not isinstance(package, dict) or not package:
        print("FAILED:installer empty package", file=sys.stderr)
        return EXIT_USAGE
    result = install(
        Path(args.dest),
        {str(k): str(v) for k, v in package.items()},
        long_paths_enabled=enabled,
        naive_partial=args.naive_partial,
    )
    print(json.dumps(result, indent=1, sort_keys=True))
    print(result["message"], file=sys.stderr)
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
