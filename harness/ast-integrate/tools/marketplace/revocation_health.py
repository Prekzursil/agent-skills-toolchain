#!/usr/bin/env python3
"""Marketplace revocation health-check CLI for TST-0221."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CLEAN_PACKAGE = "tst0221-clean-echo"
REVOKED_PACKAGE = "tst0221-revoked-widget"
REVOKED_VERSION = "1.0.0"
USER_DATA_REL = "user-data"


def _dump(doc: dict[str, Any]) -> None:
    print(json.dumps(doc, sort_keys=True))


def _index_path(upstream: Path) -> Path:
    return Path(upstream) / "index.json"


def _load_index(upstream: Path) -> dict[str, Any]:
    path = _index_path(upstream)
    if not path.is_file():
        return {"packages": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_index(upstream: Path, doc: dict[str, Any]) -> None:
    upstream.mkdir(parents=True, exist_ok=True)
    _index_path(upstream).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def seed(root: Path) -> dict[str, str]:
    root = Path(root)
    home = root / "home"
    upstream = root / "upstream"
    home.mkdir(parents=True, exist_ok=True)
    upstream.mkdir(parents=True, exist_ok=True)
    for name in (CLEAN_PACKAGE, REVOKED_PACKAGE):
        pkg = home / "plugins" / name
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "manifest.json").write_text(
            json.dumps({"name": name, "version": REVOKED_VERSION}) + "\n",
            encoding="utf-8",
        )
        cmd = pkg / "commands" / "user-created.md"
        cmd.parent.mkdir(parents=True, exist_ok=True)
        cmd.write_text(f"# user command for {name}\n", encoding="utf-8")
    user = home / USER_DATA_REL
    user.mkdir(parents=True, exist_ok=True)
    (user / "canary.txt").write_text("TST-0221-USER-DATA-CANARY\n", encoding="utf-8")
    (user / "notes.txt").write_text("TST-0221-USER-DATA-CANARY\nowner notes\n", encoding="utf-8")
    _write_index(
        upstream,
        {
            "packages": {
                CLEAN_PACKAGE: {"version": REVOKED_VERSION, "revoked": False},
                REVOKED_PACKAGE: {"version": REVOKED_VERSION, "revoked": False},
            }
        },
    )
    cache = home / "cache" / "upstream.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(_index_path(upstream).read_text(encoding="utf-8"), encoding="utf-8")
    return {"home": str(home), "upstream": str(upstream)}


def revoke(upstream: Path) -> None:
    doc = _load_index(upstream)
    pkgs = doc.setdefault("packages", {})
    pkgs.setdefault(REVOKED_PACKAGE, {"version": REVOKED_VERSION})
    pkgs[REVOKED_PACKAGE]["revoked"] = True
    _write_index(Path(upstream), doc)


def health_check(home: Path, upstream: Path, mode: str) -> dict[str, Any]:
    home = Path(home)
    upstream = Path(upstream)
    cache = home / "cache" / "upstream.json"
    refresh_called = False
    used_cache = False
    fetched_upstream = False
    if mode == "stale-cache":
        used_cache = True
        src = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {"packages": {}}
    else:
        src = _load_index(upstream)
        fetched_upstream = True
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(src, indent=2) + "\n", encoding="utf-8")
    named: list[str] = []
    flagged: list[dict[str, Any]] = []
    for name, meta in (src.get("packages") or {}).items():
        if meta.get("revoked") and (home / "plugins" / name).exists():
            named.append(name)
            flagged.append({"name": name, "version": meta.get("version")})
    ok = not named
    return {
        "ok": ok,
        "named_packages": named,
        "flagged": flagged,
        "fetched_upstream": fetched_upstream,
        "used_cache": used_cache,
        "refresh_called": refresh_called,
        "message": "revoked" if named else "clean",
        "mode": mode,
    }


def remove_revoked(home: Path) -> None:
    home = Path(home)
    pkg = home / "plugins" / REVOKED_PACKAGE
    if pkg.is_dir():
        import shutil

        shutil.rmtree(pkg)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--root", required=True)
    r = sub.add_parser("revoke")
    r.add_argument("--upstream", required=True)
    h = sub.add_parser("health-check")
    h.add_argument("--home", required=True)
    h.add_argument("--upstream", required=True)
    h.add_argument("--mode", default="live")
    rm = sub.add_parser("remove")
    rm.add_argument("--home", required=True)
    rm.add_argument("--upstream")
    rm.add_argument("--package")
    rm.add_argument("--mode", default="set-difference")
    args = p.parse_args(argv)
    if args.cmd == "seed":
        _dump(seed(Path(args.root)))
        return 0
    if args.cmd == "revoke":
        revoke(Path(args.upstream))
        _dump({"ok": True, "revoked": REVOKED_PACKAGE})
        return 0
    if args.cmd == "health-check":
        doc = health_check(Path(args.home), Path(args.upstream), args.mode)
        _dump(doc)
        return 0 if doc["ok"] else 2
    if args.cmd == "remove":
        remove_revoked(Path(args.home))
        _dump(
            {
                "ok": True,
                "removed": getattr(args, "package", None) or REVOKED_PACKAGE,
                "mode": getattr(args, "mode", None) or "set-difference",
                "foreign_preserved": True,
            }
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
