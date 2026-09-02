#!/usr/bin/env python3
"""Run one self-contained replication package. Exit 0 iff pass criterion holds."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import guards  # noqa: E402
import normalizers as N  # noqa: E402
import toolchain as T  # noqa: E402
import verify_claim as V  # noqa: E402


def fail(msg: str, code: int = 1) -> int:
    print(f"FAILED:package {msg}")
    return code


def load_package(pkg_dir: Path) -> dict:
    path = pkg_dir / "PACKAGE.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return C.load_json(path)


def resolve_pkg_dir(spec: str) -> Path:
    pkg_dir = Path(spec)
    if not pkg_dir.is_absolute():
        under_repo = C.REPO / pkg_dir
        pkg_dir = under_repo.resolve() if under_repo.exists() else pkg_dir.resolve()
    else:
        pkg_dir = pkg_dir.resolve()
    return pkg_dir


def check_credentials(pkg: dict, pkg_dir: Path) -> str | None:
    creds = pkg.get("credentials") or {}
    if creds.get("bundled") is True:
        return "package illegally sets credentials.bundled=true"
    needed = list(creds.get("runtime_inject") or [])
    for name in needed:
        if not os.environ.get(name):
            return f"runtime credential {name} missing (inject at start; not bundled)"
        val = os.environ[name]
        for path in pkg_dir.rglob("*"):
            if not path.is_file() or path.suffix == ".pyc":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if val and val in text:
                return f"runtime credential {name} leaked into {path.name}"
    hits = guards.scan_tree(pkg_dir)
    if hits:
        return f"secret-scan hits={len(hits)}"
    return None


def execute(pkg_dir: Path) -> int:
    if not pkg_dir.is_dir():
        return fail(f"not a directory {pkg_dir}")
    pkg = load_package(pkg_dir)
    ok, why = T.pin_ok(pkg.get("pinned_toolchain") or [])
    if not ok:
        return fail(f"toolchain {why}")
    cred = check_credentials(pkg, pkg_dir)
    if cred:
        return fail(cred, 2)
    for inp in pkg.get("inputs") or []:
        ip = pkg_dir / str(inp.get("path") or "")
        if not ip.is_file():
            return fail(f"missing input {inp.get('path')}")
        sha, _ = C.digest_file(ip)
        if sha != str(inp.get("sha256") or ""):
            return fail(f"input sha256 mismatch {inp.get('path')}")
    verdict = V.evaluate(pkg, pkg_dir)
    names = list(pkg.get("normalizers") or ["json-stable"])
    actual = N.apply(json.dumps(verdict, indent=1, sort_keys=True) + "\n", names)
    expected_rel = None
    for exp in pkg.get("expected_outputs") or []:
        expected_rel = exp.get("path")
        break
    if not expected_rel:
        return fail("no expected_outputs")
    expected_path = pkg_dir / expected_rel
    if not expected_path.is_file():
        return fail(f"missing expected {expected_rel}")
    expected = N.apply_file(expected_path, names)
    holds = bool(verdict.get("holds")) and actual == expected
    print(
        f"package_id={pkg.get('package_id')} holds={verdict.get('holds')} "
        f"bytes_match={actual == expected}"
    )
    if not holds:
        return fail("pass criterion not met")
    print(f"SUCCESS:package {pkg.get('package_id')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, help="Package directory")
    args = ap.parse_args()
    return execute(resolve_pkg_dir(args.package))


if __name__ == "__main__":
    raise SystemExit(main())
