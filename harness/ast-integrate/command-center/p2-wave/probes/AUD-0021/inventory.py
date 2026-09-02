#!/usr/bin/env python3
"""AUD-0021 shared detectors: package.json classes + lock integrity/desync.

Resumes the round-3 builder in command-center/p2-wave/_build_AUD0021.py.
The lock-format decision is keyed on an explicit kind, not the file name, so
the control fixtures (saved as fixture-lock-*.json) are actually scored.
Workspace `link: true` / non-http resolved entries are not required to carry
an integrity hash.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0021"

SKIP = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
CLASSES = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)
LOCKNAMES = (
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
)
INTEGRITY = re.compile(r"^sha(?:1|256|384|512)-[A-Za-z0-9+/]+={0,2}$")


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def find_manifests() -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP]
        if "package.json" in files:
            out.append(Path(root) / "package.json")
    return sorted(out, key=lambda p: rel(p))


def find_manifests_via_find() -> tuple[int, list[str], str]:
    """Mechanically different population count: find(1) with the same prune set."""
    argv: list[str] = ["find", "."]
    argv.append("(")
    for i, name in enumerate(sorted(SKIP)):
        if i:
            argv.append("-o")
        argv.extend(["-name", name])
    argv.extend([")", "-prune", "-o", "-name", "package.json", "-print"])
    try:
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, [], f"{type(exc).__name__}: {exc}"
    paths: list[str] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("./"):
            line = line[2:]
        if line == "package.json":
            line = "package.json"
        paths.append(line.replace("\\", "/"))
    paths = sorted(p for p in paths if p and "node_modules/" not in p)
    raw = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, paths, raw[:4000]


def parse_manifest(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(doc, dict):
        return {"error": "manifest is not an object"}
    rec: dict[str, Any] = {
        "name": doc.get("name"),
        "version": doc.get("version"),
        "private": bool(doc.get("private")),
        "classes": {},
        "workspaces": doc.get("workspaces") if isinstance(doc.get("workspaces"), list) else None,
        "scripts": (
            sorted((doc.get("scripts") or {}).keys())
            if isinstance(doc.get("scripts"), dict)
            else []
        ),
    }
    for cls in CLASSES:
        value = doc.get(cls)
        if isinstance(value, dict):
            rec["classes"][cls] = {str(k): str(x) for k, x in value.items()}
    return rec


def inventory_manifests() -> dict[str, Any]:
    manifests = find_manifests()
    per_manifest: list[dict[str, Any]] = []
    totals = {c: 0 for c in CLASSES}
    parse_errors: list[dict[str, str]] = []
    for path in manifests:
        rec = parse_manifest(path)
        path_rel = rel(path)
        if "error" in rec:
            parse_errors.append({"path": path_rel, "error": rec["error"]})
            per_manifest.append({"path": path_rel, "error": rec["error"]})
            continue
        counts = {c: len(rec["classes"].get(c, {})) for c in CLASSES}
        for cls in CLASSES:
            totals[cls] += counts[cls]
        per_manifest.append(
            {
                "path": path_rel,
                "name": rec["name"],
                "version": rec["version"],
                "private": rec["private"],
                "counts": counts,
                "dependencies": rec["classes"],
                "script_names": rec["scripts"],
                "workspaces": rec["workspaces"],
            }
        )

    walk_paths = [row["path"] for row in per_manifest]
    find_rc, find_paths, find_raw = find_manifests_via_find()
    only_walk = sorted(p for p in walk_paths if p not in set(find_paths))
    only_find = sorted(p for p in find_paths if p not in set(walk_paths))
    find_available = find_rc != 127
    agreed = find_available and not only_walk and not only_find

    distinct: dict[str, set[str]] = {}
    for row in per_manifest:
        for cls in CLASSES:
            for name, spec in (row.get("dependencies") or {}).get(cls, {}).items():
                distinct.setdefault(name, set()).add(spec)
    multi_spec = {k: sorted(v) for k, v in distinct.items() if len(v) > 1}

    return {
        "unit_id": UNIT,
        "probe": "probe1-manifests",
        "instrument": "json.loads of every package.json (node_modules pruned) into prod/dev/peer/optional",
        "manifests": per_manifest,
        "totals_by_class": totals,
        "parse_errors": parse_errors,
        "walk_count": len(walk_paths),
        "find_count": len(find_paths),
        "find_exit_code": find_rc,
        "find_available": find_available,
        "only_on_walk": only_walk,
        "only_on_find": only_find,
        "walk_vs_find_agreed": agreed,
        "find_raw_head": find_raw,
        "dependencies_declared_at_more_than_one_version": multi_spec,
    }


def check_lock_integrity(lock: Path, kind: str | None = None) -> dict[str, Any]:
    kind = kind or lock.name
    rec: dict[str, Any] = {
        "path": rel(lock) if lock.exists() else str(lock),
        "bytes": lock.stat().st_size if lock.is_file() else 0,
        "kind": kind,
        "entries": 0,
        "with_resolved": 0,
        "local_link_entries": [],
        "missing_integrity": [],
        "malformed_integrity": [],
        "parse_error": None,
        "lockfile_version": None,
    }
    if kind not in ("package-lock.json", "npm-shrinkwrap.json"):
        rec["parse_error"] = f"unsupported-lock-format:{kind}"
        return rec
    try:
        doc = json.loads(lock.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        rec["parse_error"] = f"{type(exc).__name__}: {exc}"
        return rec
    rec["lockfile_version"] = doc.get("lockfileVersion")
    pkgs = doc.get("packages")
    if not isinstance(pkgs, dict):
        rec["parse_error"] = "no 'packages' map (lockfileVersion < 2?)"
        return rec
    for key, ent in pkgs.items():
        if key == "" or not isinstance(ent, dict):
            continue
        rec["entries"] += 1
        resolved = str(ent.get("resolved") or "")
        if not resolved:
            continue
        if ent.get("link") is True or not resolved.startswith(("http://", "https://")):
            rec["local_link_entries"].append(key)
            continue
        rec["with_resolved"] += 1
        integ = ent.get("integrity")
        if integ is None:
            rec["missing_integrity"].append(key)
        elif not INTEGRITY.match(str(integ)):
            rec["malformed_integrity"].append(key)
    return rec


def lock_ok(rec: dict[str, Any]) -> bool:
    return (
        rec.get("parse_error") is None
        and not rec.get("missing_integrity")
        and not rec.get("malformed_integrity")
    )


def desync_lock_root(lockdoc: dict[str, Any]) -> list[str]:
    root = (lockdoc.get("packages") or {}).get("", {})
    declared: set[str] = set()
    for cls in CLASSES:
        declared |= set((root.get(cls) or {}).keys())
    present = {k.split("node_modules/")[-1] for k in (lockdoc.get("packages") or {}) if k}
    return sorted(declared - present)


def desync_manifest_vs_lock(manifest: dict[str, Any], lockdoc: dict[str, Any]) -> list[str]:
    declared: set[str] = set()
    for cls in CLASSES:
        value = manifest.get(cls)
        if isinstance(value, dict):
            declared |= set(value.keys())
    present = {k.split("node_modules/")[-1] for k in (lockdoc.get("packages") or {}) if k}
    return sorted(declared - present)


def find_locks() -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in files:
            if name in LOCKNAMES:
                out.append(Path(root) / name)
    return sorted(out, key=lambda p: rel(p))


def npm_bin() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


def npm_ls(dirpath: Path, timeout: int = 25) -> dict[str, Any]:
    binary = npm_bin()
    if not binary:
        return {
            "dir": rel(dirpath) or ".",
            "exit_code": 127,
            "problem_count": None,
            "first_problem": None,
            "npm_binary": None,
            "raw_head": "npm-binary-absent",
        }
    stdout = ""
    try:
        proc = subprocess.run(
            [binary, "ls", "--all", "--json"],
            cwd=str(dirpath),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout or ""
        out = stdout + (proc.stderr or "")
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        out = f"TIMEOUT after {timeout}s: {binary} ls --all --json"
        rc = 124
    except OSError as exc:
        out = f"{type(exc).__name__}: {exc}"
        rc = 127
    parsed = None
    problems = None
    try:
        parsed = json.loads(stdout) if stdout.strip().startswith("{") else None
        problems = parsed.get("problems") if isinstance(parsed, dict) else None
    except Exception:  # noqa: BLE001
        pass
    return {
        "dir": rel(dirpath) or ".",
        "exit_code": rc,
        "problem_count": len(problems) if isinstance(problems, list) else None,
        "first_problem": (
            problems[0][:180] if isinstance(problems, list) and problems else None
        ),
        "npm_binary": binary,
        "raw_head": out[:600],
    }


def inventory_locks() -> dict[str, Any]:
    locks = find_locks()
    lock_recs: list[dict[str, Any]] = []
    for path in locks:
        rec = check_lock_integrity(path)
        if rec["parse_error"] is None and path.name in (
            "package-lock.json",
            "npm-shrinkwrap.json",
        ):
            lockdoc = json.loads(path.read_text(encoding="utf-8"))
            rec["declared_but_absent_from_lock"] = desync_lock_root(lockdoc)
            sibling = path.parent / "package.json"
            if sibling.is_file():
                try:
                    man = json.loads(sibling.read_text(encoding="utf-8"))
                    rec["manifest_declared_absent_from_lock"] = (
                        desync_manifest_vs_lock(man, lockdoc)
                        if isinstance(man, dict)
                        else []
                    )
                except Exception as exc:  # noqa: BLE001
                    rec["manifest_declared_absent_from_lock"] = [
                        f"manifest-parse:{type(exc).__name__}"
                    ]
            else:
                rec["manifest_declared_absent_from_lock"] = []
        lock_recs.append(rec)
    locked_dirs = {p.parent for p in locks}
    manifests = find_manifests()
    unlocked = [
        rel(m.parent) or "."
        for m in manifests
        if m.parent not in locked_dirs
    ]
    ls_recs = [npm_ls(d) for d in sorted(locked_dirs, key=lambda p: p.as_posix())]
    bad_locks = [r["path"] for r in lock_recs if not lock_ok(r)]
    desynced = {
        r["path"]: r.get("declared_but_absent_from_lock")
        for r in lock_recs
        if r.get("declared_but_absent_from_lock")
    }
    return {
        "unit_id": UNIT,
        "probe": "probe2-locks",
        "instrument": "packages[*].integrity shape/presence plus npm ls --all --json exit status",
        "locks": lock_recs,
        "npm_ls": ls_recs,
        "npm_binary": npm_bin(),
        "failing_integrity": bad_locks,
        "desynced": desynced,
        "manifests_without_a_lock": unlocked,
        "lock_count": len(locks),
    }


def control_fixtures() -> dict[str, Any]:
    good = HERE / "fixture-lock-good.json"
    bad = HERE / "fixture-lock-corrupt.json"
    desync_path = HERE / "fixture-lock-desync.json"
    ctl_good = check_lock_integrity(good, kind="package-lock.json")
    ctl_bad = check_lock_integrity(bad, kind="package-lock.json")
    donor = json.loads(good.read_text(encoding="utf-8"))
    planted = json.loads(desync_path.read_text(encoding="utf-8"))
    ds_bad = desync_lock_root(planted)
    ds_good = desync_lock_root(donor)
    victim_named = [
        name
        for name in ctl_bad["malformed_integrity"]
        if name in (donor.get("packages") or {})
    ]
    return {
        "good": ctl_good,
        "bad": ctl_bad,
        "victim_named": victim_named,
        "fired": (not lock_ok(ctl_bad)) and bool(ctl_bad["malformed_integrity"]),
        "silent": lock_ok(ctl_good),
        "desync_bad": ds_bad,
        "desync_good": ds_good,
        "desync_fired": ds_bad == ["ghost_pkg_that_does_not_exist"],
        "desync_silent": ds_good == [],
    }


def cli_check_lock(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: inventory.py check-lock <path> [--kind package-lock.json]")
        return 2
    path = Path(argv[1])
    if not path.is_absolute():
        path = REPO / path
    kind = "package-lock.json"
    if "--kind" in argv:
        kind = argv[argv.index("--kind") + 1]
    rec = check_lock_integrity(path, kind=kind)
    ok = lock_ok(rec)
    print(json.dumps(rec, indent=1, sort_keys=True))
    if ok:
        print("OK:lock-integrity")
        return 0
    named = rec["malformed_integrity"] + rec["missing_integrity"]
    print("FAIL:lock-integrity names=" + json.dumps(named))
    if rec["parse_error"]:
        print("FAIL:parse_error=" + str(rec["parse_error"]))
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: inventory.py check-lock <path> [--kind package-lock.json]")
        return 2
    if argv[0] == "check-lock":
        return cli_check_lock(argv)
    print("unknown subcommand", argv[0])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
