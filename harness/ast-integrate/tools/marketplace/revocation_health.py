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
        owned = {
            "manifest.json": json.dumps({"name": name, "version": REVOKED_VERSION}) + "\n",
            "README.md": f"# {name}\n\nInstalled by the marketplace; owned by the package.\n",
            f"commands/{name}.md": f"# {name} command (package-owned)\n",
            "scripts/run.py": f"print({name!r})\n",
        }
        for rel, body in owned.items():
            path = pkg / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        # plugin.json is the package's owned-file set; removal is the set
        # difference "files on disk minus this list", so anything the user
        # dropped into the plugin folder afterwards is foreign and survives.
        (pkg / "plugin.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "version": REVOKED_VERSION,
                    "owned_files": sorted(owned) + ["plugin.json"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        # User-created content inside the package folder: not in owned_files.
        cmd = pkg / "commands" / "user-created.md"
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


def owned_files(pkg: Path) -> list[str]:
    """The package's declared owned-file set (plugin.json); empty when undeclared."""
    meta = pkg / "plugin.json"
    if not meta.is_file():
        return []
    try:
        doc = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    files = doc.get("owned_files") if isinstance(doc, dict) else None
    out = [str(f).replace("\\", "/") for f in (files or []) if str(f).strip()]
    if "plugin.json" not in out:
        out.append("plugin.json")
    return sorted(set(out))


def _prune_empty_dirs(root: Path) -> None:
    for path in sorted((d for d in root.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
        try:
            path.rmdir()
        except OSError:
            pass
    try:
        root.rmdir()
    except OSError:
        pass


def remove_set_difference(home: Path, package: str) -> dict[str, Any]:
    """Remove exactly the package-owned files; every foreign file stays byte-identical."""
    home = Path(home)
    pkg = home / "plugins" / package
    if not pkg.is_dir():
        return {"ok": False, "error": f"package {package} not installed", "removed": None}
    owned = owned_files(pkg)
    if not owned:
        return {"ok": False, "error": f"{package}/plugin.json declares no owned_files", "removed": None}
    on_disk = sorted(
        p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()
    )
    owned_set = set(owned)
    foreign = [rel for rel in on_disk if rel not in owned_set]
    deleted: list[str] = []
    for rel in owned:
        path = pkg / rel
        if path.is_file():
            path.unlink()
            deleted.append(rel)
    _prune_empty_dirs(pkg)
    remaining = sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()) if pkg.is_dir() else []
    return {
        "ok": True,
        "mode": "set-difference",
        "removed": package,
        "owned_files": owned,
        "deleted": deleted,
        "foreign_files": foreign,
        "foreign_preserved": remaining == foreign,
        "plugin_dir_retained": pkg.is_dir(),
    }


def remove_wholesale(home: Path, package: str) -> dict[str, Any]:
    """The regression seed: 'restore' the home by deleting the plugin folder AND
    user-data. Kept only as a negative control; it never reports delivery."""
    import shutil

    home = Path(home)
    for victim in (home / "plugins" / package, home / USER_DATA_REL):
        if victim.is_dir():
            shutil.rmtree(victim)
    return {
        "ok": False,
        "mode": "wholesale",
        "removed": package,
        "foreign_preserved": False,
        "error": "wholesale restore destroyed user-data and foreign files; not a delivery",
    }


def remove_revoked(home: Path, package: str = REVOKED_PACKAGE, mode: str = "set-difference") -> dict[str, Any]:
    if mode == "wholesale":
        return remove_wholesale(home, package)
    if mode != "set-difference":
        return {"ok": False, "error": f"unknown remove mode {mode!r}", "removed": None, "mode": mode}
    return remove_set_difference(home, package)


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
        doc = remove_revoked(
            Path(args.home),
            getattr(args, "package", None) or REVOKED_PACKAGE,
            getattr(args, "mode", None) or "set-difference",
        )
        _dump(doc)
        return 0 if doc.get("ok") else 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
