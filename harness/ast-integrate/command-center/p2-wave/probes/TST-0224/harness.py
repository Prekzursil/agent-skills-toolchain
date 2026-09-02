#!/usr/bin/env python3
"""Live file-scope write harness for TST-0224.

Two independent signals per case:
  (a) allow/deny verdict from tools/lib/workspace.mjs (realpath + relative)
  (b) filesystem stat after the attempted write

A naive String StartsWith checker is kept as the named regression seed:
tools/libextra is admitted when the scope is tools/lib.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE = "tools/lib/workspace.mjs"
SCOPE = "tools/lib"
MARKER = "TST-0224-IN-SCOPE\n"
CANARY = "TST-0224-CANARY-UNTOUCHED\n"

CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "in-scope",
        "dest": "tools/lib/in-scope.txt",
        "expect_allow": True,
        "landing": "tools/lib/in-scope.txt",
        "regression_seed": False,
    },
    {
        "id": "prefix-sibling-libextra",
        "dest": "tools/libextra/escape.txt",
        "expect_allow": False,
        "landing": "tools/libextra/escape.txt",
        "regression_seed": True,
    },
    {
        "id": "dotdot-escape",
        "dest": "tools/lib/../x/escape.txt",
        "expect_allow": False,
        "landing": "tools/x/escape.txt",
        "regression_seed": False,
    },
    {
        "id": "symlink-outside",
        "dest": "tools/lib/link-out/escape.txt",
        "expect_allow": False,
        "landing": "outside/escape.txt",
        "regression_seed": False,
    },
    {
        "id": "case-variant",
        "dest": "tools/Lib/escape.txt",
        "expect_allow": False,
        "landing": "tools/Lib/escape.txt",
        "regression_seed": False,
    },
)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def naive_startswith(root: Path, scope_rel: str, dest_rel: str) -> bool:
    """Known-broken prefix check: no realpath, no trailing-separator guard."""
    scope_p = (root / scope_rel).as_posix()
    dest_p = (root / dest_rel).as_posix()
    return dest_p.startswith(scope_p)


def physical_py(path: Path) -> Path:
    abs_path = Path(os.path.abspath(str(path)))
    acc = Path(abs_path.anchor)
    rest = abs_path.parts[1:]
    for i, part in enumerate(rest):
        cand = acc / part
        try:
            if cand.is_symlink() or cand.exists():
                acc = Path(os.path.realpath(cand))
                continue
        except OSError:
            return acc.joinpath(*rest[i:])
        return acc.joinpath(*rest[i:])
    return acc


def python_inside(scope: Path, dest: Path) -> bool:
    try:
        physical_py(dest).relative_to(physical_py(scope))
        return True
    except ValueError:
        return False


def fs_stat(path: Path) -> dict[str, Any]:
    exists = path.exists()
    is_file = path.is_file() if exists else False
    sha = None
    size = 0
    if is_file:
        sha, size = digest_file(path)
    return {
        "exists": exists,
        "is_file": is_file,
        "path": str(path),
        "realpath": os.path.realpath(path) if exists else None,
        "sha256": sha,
        "size": size,
    }


def prepare_sandbox(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    (root / "tools" / "lib").mkdir(parents=True)
    (root / "tools" / "libextra").mkdir(parents=True)
    (root / "tools" / "x").mkdir(parents=True)
    (root / "outside").mkdir(parents=True)
    (root / "tools" / "lib" / ".keep").write_text("keep\n", encoding="utf-8")
    (root / "tools" / "libextra" / ".keep").write_text("keep\n", encoding="utf-8")
    (root / "tools" / "x" / ".keep").write_text("keep\n", encoding="utf-8")
    (root / "outside" / "canary.txt").write_text(CANARY, encoding="utf-8")
    link = root / "tools" / "lib" / "link-out"
    os.symlink(os.path.relpath(root / "outside", start=root / "tools" / "lib"), link)


def call_sut(cmd: str, root: Path, dest_rel: str, data: str | None = None) -> dict[str, Any]:
    gate = REPO / GATE
    if not gate.is_file():
        raise FileNotFoundError(GATE)
    argv = [
        "node",
        str(gate),
        cmd,
        "--root",
        str(root),
        "--scope",
        SCOPE,
        "--dest",
        dest_rel,
    ]
    if cmd == "write":
        argv.extend(["--data", data if data is not None else MARKER])
    proc = subprocess.run(
        argv,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = (proc.stdout or "").strip().splitlines()
    payload: dict[str, Any]
    if not text:
        payload = {
            "allowed": False,
            "error": "empty-stdout",
            "stderr": (proc.stderr or "")[-500:],
        }
    else:
        try:
            parsed = json.loads(text[-1])
        except json.JSONDecodeError:
            parsed = {
                "allowed": False,
                "error": "unparseable",
                "raw": text[-1][:500],
            }
        payload = parsed if isinstance(parsed, dict) else {"allowed": False, "error": "non-object"}
    payload["exit_code"] = proc.returncode
    payload["allowed"] = bool(payload.get("allowed"))
    payload["written"] = bool(payload.get("written"))
    return payload


def run_case(root: Path, case: dict[str, Any], canary_before: str) -> dict[str, Any]:
    dest_rel = str(case["dest"])
    landing = root / str(case["landing"])
    before = fs_stat(landing)
    naive = naive_startswith(root, SCOPE, dest_rel)
    independent_would_allow = python_inside(root / SCOPE, root / dest_rel)
    sut = call_sut("write", root, dest_rel, MARKER if case["expect_allow"] else "ESCAPE\n")
    after = fs_stat(landing)
    canary_after = (root / "outside" / "canary.txt").read_text(encoding="utf-8")
    ok_verdict = sut["allowed"] is bool(case["expect_allow"])
    ok_fs = after["exists"] is bool(case["expect_allow"]) and (
        after["is_file"] is bool(case["expect_allow"])
    )
    if case["expect_allow"]:
        ok_fs = ok_fs and after.get("sha256") == digest_bytes(MARKER.encode("utf-8"))
        ok_inside = python_inside(root / SCOPE, landing)
    else:
        ok_inside = not python_inside(root / SCOPE, landing) if landing.exists() else True
        ok_fs = ok_fs and not landing.exists()
    ok_independent = independent_would_allow is bool(case["expect_allow"])
    ok_canary = canary_after == canary_before
    ok_agree = sut["allowed"] is independent_would_allow
    passed = all((ok_verdict, ok_fs, ok_inside, ok_independent, ok_canary, ok_agree))
    return {
        "agree_sut_python": ok_agree,
        "canary_unchanged": ok_canary,
        "dest": dest_rel,
        "expect_allow": case["expect_allow"],
        "fs_after": after,
        "fs_before": before,
        "fs_matches_expect": ok_fs,
        "id": case["id"],
        "independent_would_allow": independent_would_allow,
        "landing": str(case["landing"]),
        "naive_startswith_allows": naive,
        "pass": passed,
        "regression_seed": case["regression_seed"],
        "sut": {
            "allowed": sut.get("allowed"),
            "exit_code": sut.get("exit_code"),
            "method": sut.get("method"),
            "reason": sut.get("reason"),
            "written": sut.get("written"),
            "dest_physical": sut.get("dest_physical"),
        },
        "verdict_matches_expect": ok_verdict,
    }


def run_all() -> dict[str, Any]:
    root = HERE / "runtime" / "sandbox"
    prepare_sandbox(root)
    canary_before = (root / "outside" / "canary.txt").read_text(encoding="utf-8")
    canary_sha = digest_bytes(canary_before.encode("utf-8"))
    results = [run_case(root, case, canary_before) for case in CASES]
    by_id = {r["id"]: r for r in results}
    in_scope = by_id["in-scope"]
    libextra = by_id["prefix-sibling-libextra"]
    denials = [r for r in results if not r["expect_allow"]]
    both_states = bool(in_scope["pass"] and in_scope["sut"]["allowed"] and in_scope["fs_after"]["exists"])
    all_denies_hold = all(r["pass"] and not r["sut"]["allowed"] and not r["fs_after"]["exists"] for r in denials)
    seed_naive_allows = bool(libextra["naive_startswith_allows"])
    seed_sut_denies = (not libextra["sut"]["allowed"]) and (not libextra["fs_after"]["exists"])
    canary_after = (root / "outside" / "canary.txt").read_text(encoding="utf-8")
    summary = {
        "all_denies_hold": all_denies_hold,
        "both_states": both_states,
        "canary_sha256": canary_sha,
        "canary_unchanged": canary_after == canary_before,
        "cases": results,
        "gate": GATE,
        "naive_allows_libextra": seed_naive_allows,
        "pass": bool(
            both_states
            and all_denies_hold
            and seed_naive_allows
            and seed_sut_denies
            and canary_after == canary_before
            and all(r["pass"] for r in results)
        ),
        "sandbox": str(root.relative_to(REPO).as_posix()),
        "scope": SCOPE,
        "seed_sut_denies_libextra": seed_sut_denies,
        "unit_id": "TST-0224",
    }
    out = HERE / "last_run.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
