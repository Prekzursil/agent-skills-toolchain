#!/usr/bin/env python3
"""Read-only discovery adapter for installed skills, plugins, and LIVE harness trees.

Enumerates workflow-shaped capabilities (skills, commands, agents, hooks, plugins,
workflows) under independently supplied live and repo roots. Neither side is treated
as authoritative: each row records both sides' presence, hashes, and a direction.

This module never writes. Writes under live roots (including creation of absent
host trees such as ~/.claude) are refused by an audit guard for the duration of
a discover() call.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

KINDS = ("skills", "commands", "agents", "hooks", "plugins", "workflows")
SKIP_DIR_NAMES = {"__pycache__", ".git", "node_modules", ".DS_Store"}
HOST_LIVE_REL = (".claude", ".agents")
OPEN_WRITE_CHARS = set("wxa+")

# os/open events that mutate a tree. Audited only while a guard is active.
WRITE_EVENTS = {
    "os.mkdir",
    "os.makedirs",
    "os.rmdir",
    "os.remove",
    "os.unlink",
    "os.rename",
    "os.replace",
    "os.link",
    "os.symlink",
    "os.chmod",
    "os.utime",
    "os.truncate",
}


def host_live_roots() -> list[Path]:
    home = Path.home()
    return [home / name for name in HOST_LIVE_REL]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def eol_of(data: bytes) -> str:
    if b"\x00" in data[:8192]:
        return "BINARY"
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    return "LF"


def measure_bytes(data: bytes) -> dict[str, Any]:
    lf = data.replace(b"\r\n", b"\n")
    return {
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "sha256_lf": sha256_bytes(lf),
        "eol": eol_of(data),
    }


def _posix(path: Path) -> str:
    return path.as_posix()


def _norm_abs(path: Path) -> str:
    return str(path).replace("\\", "/")


class ReadOnlyGuard:
    """Refuse mutation of protected roots while active.

    sys.addaudithook cannot be unregistered, so `active` is the off switch.
    Protected paths need not exist: creating ~/.claude is a live-tree write.
    """

    def __init__(self, roots: Iterable[Path]):
        self.roots = [Path(r) for r in roots]
        self.active = False
        self.violations: list[str] = []
        self._installed = False

    def __enter__(self) -> "ReadOnlyGuard":
        self.active = True
        if not self._installed:
            sys.addaudithook(self._hook)
            self._installed = True
        return self

    def __exit__(self, *exc: object) -> None:
        self.active = False

    def _protected(self, path: object) -> bool:
        try:
            raw = os.fsdecode(path)
        except TypeError:
            return False
        s = raw.replace("\\", "/")
        for root in self.roots:
            r = _norm_abs(root)
            if s == r or s.startswith(r + "/"):
                return True
        return False

    def _refuse(self, msg: str) -> None:
        self.violations.append(msg)
        raise PermissionError(f"IMP-0151 read-only adapter: {msg}")

    def _hook(self, event: str, args: tuple[Any, ...]) -> None:
        if not self.active:
            return
        if event == "open" and args:
            path = args[0]
            mode = args[1] if len(args) > 1 else "r"
            if isinstance(mode, str) and any(c in mode for c in OPEN_WRITE_CHARS):
                if self._protected(path):
                    self._refuse(f"open({path!r}, {mode!r})")
            return
        if event in WRITE_EVENTS and args:
            if self._protected(args[0]):
                self._refuse(f"{event}({args[0]!r})")


def snapshot_tree(root: Path) -> dict[str, dict[str, Any]]:
    """mtime/size/ino/sha256 of every file under root. Empty if root is absent."""
    out: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                st = path.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            rel = path.relative_to(root).as_posix()
            try:
                data = _read_bytes(path)
            except OSError:
                data = b""
            out[rel] = {
                "mtime_ns": st.st_mtime_ns,
                "size": st.st_size,
                "ino": st.st_ino,
                "mode": st.st_mode,
                "sha256": sha256_bytes(data),
            }
    return out


def snapshots_equal(before: dict, after: dict) -> bool:
    return before == after


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _walk_files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            if name.endswith(".pyc") or name == ".DS_Store":
                continue
            path = Path(dirpath) / name
            try:
                st = path.lstat()
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                yield path


def is_workflow_shaped(kind: str, rel_under_kind: str) -> bool:
    """Capability documents only — supporting files next to a skill are not rows."""
    name = Path(rel_under_kind).name
    if kind == "skills":
        return name == "SKILL.md"
    if kind == "commands":
        return Path(rel_under_kind).suffix.lower() in {".md", ".py", ".sh", ".js", ".json"}
    if kind == "agents":
        return name == "AGENT.md" or Path(rel_under_kind).suffix.lower() == ".md"
    if kind == "hooks":
        return True
    if kind == "plugins":
        return name == "plugin.json"
    if kind == "workflows":
        return Path(rel_under_kind).suffix.lower() in {".json", ".js", ".yaml", ".yml", ".md"}
    return False


def capability_id(kind: str, rel_under_kind: str) -> str:
    posix = rel_under_kind.replace("\\", "/")
    if kind == "skills" and posix.endswith("/SKILL.md"):
        return posix[: -len("/SKILL.md")]
    if kind == "plugins" and posix.endswith("/plugin.json"):
        return posix[: -len("/plugin.json")]
    if posix == "plugin.json":
        return "root-plugin"
    return Path(posix).with_suffix("").as_posix()


def index_kind(root: Path, kind: str) -> dict[str, dict[str, Any]]:
    kind_root = root / kind
    found: dict[str, dict[str, Any]] = {}
    if not kind_root.is_dir():
        # A plugin.json at the tree root still counts.
        if kind == "plugins":
            plugin = root / "plugin.json"
            if plugin.is_file():
                data = _read_bytes(plugin)
                found["plugin.json"] = {
                    "rel": "plugin.json",
                    "abs": _posix(plugin),
                    "access": f"read_file:{_posix(plugin)}",
                    **measure_bytes(data),
                }
        return found
    for path in _walk_files(kind_root):
        rel = path.relative_to(kind_root).as_posix()
        if not is_workflow_shaped(kind, rel):
            continue
        data = _read_bytes(path)
        found[rel] = {
            "rel": rel,
            "abs": _posix(path),
            "access": f"read_file:{_posix(path)}",
            **measure_bytes(data),
        }
    return found


def classify_pair(repo_row: dict | None, live_row: dict | None) -> str:
    if repo_row is None and live_row is None:
        raise ValueError("empty pair")
    if repo_row is None:
        return "live-only"
    if live_row is None:
        return "repo-only"
    if repo_row["sha256"] == live_row["sha256"]:
        return "identical"
    return "divergent"


def discover(
    live_root: Path,
    repo_root: Path,
    *,
    kinds: tuple[str, ...] = KINDS,
    protect_host: bool = True,
) -> dict[str, Any]:
    """Read-only two-tree census. Does not assume either side is source of truth."""
    live_root = Path(live_root)
    repo_root = Path(repo_root)
    protected = [live_root, repo_root]
    if protect_host:
        protected.extend(host_live_roots())
    rows: list[dict[str, Any]] = []
    counts = {
        "identical": 0,
        "divergent": 0,
        "repo-only": 0,
        "live-only": 0,
    }
    with ReadOnlyGuard(protected):
        live_present = live_root.is_dir()
        repo_present = repo_root.is_dir()
        for kind in kinds:
            repo_idx = index_kind(repo_root, kind) if repo_present else {}
            live_idx = index_kind(live_root, kind) if live_present else {}
            keys = sorted(set(repo_idx) | set(live_idx))
            for rel in keys:
                rp, lp = repo_idx.get(rel), live_idx.get(rel)
                direction = classify_pair(rp, lp)
                counts[direction] += 1
                rec: dict[str, Any] = {
                    "kind": kind,
                    "capability_id": capability_id(kind, rel),
                    "rel": f"{kind}/{rel}",
                    "classification": direction,
                    "in_repo": rp is not None,
                    "in_live": lp is not None,
                    "authoritative_side": None,
                    "repo": rp,
                    "live": lp,
                }
                rows.append(rec)
    host = []
    for p in host_live_roots():
        host.append(
            {
                "path": _posix(p),
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "created_by_adapter": False,
            }
        )
    return {
        "live_root": _posix(live_root),
        "repo_root": _posix(repo_root),
        "live_present": live_root.is_dir(),
        "repo_present": repo_root.is_dir(),
        "kinds": list(kinds),
        "counts": counts,
        "union": len(rows),
        "host_live_trees": host,
        "cited_historical_5_of_88": False,
        "authoritative_side": None,
        "read_only": True,
        "rows": rows,
    }


def discover_host(repo_root: Path | None = None) -> dict[str, Any]:
    """Enumerate default host live trees without creating them if absent."""
    repo = Path(repo_root) if repo_root is not None else default_repo_root()
    scans = []
    for live in host_live_roots():
        pair_repo = repo / ".agents" if live.name == ".agents" and (repo / ".agents").is_dir() else repo
        scans.append(discover(live, pair_repo, protect_host=True))
    return {
        "host_live_roots": [_posix(p) for p in host_live_roots()],
        "any_host_live_present": any(s["live_present"] for s in scans),
        "scans": scans,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="IMP-0151 read-only live/repo discovery")
    parser.add_argument("--live", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = discover(Path(args.live), Path(args.repo))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"union={report['union']} identical={c['identical']} "
            f"divergent={c['divergent']} repo-only={c['repo-only']} "
            f"live-only={c['live-only']} live_present={report['live_present']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
