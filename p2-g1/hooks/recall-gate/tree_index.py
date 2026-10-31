#!/usr/bin/env python3
"""recall-gate/tree_index.py — prior-art index over the LOCAL HARNESS TREE.

Why this exists (measured 2026-08-08, not assumed)
--------------------------------------------------
The harness already ships a working recall path: `RecallModule` /
`bounded_recall` (``~/.agents/harness/modules.py:1984``), wired live on
UserPromptSubmit through ``~/.agents/harness/dispatcher.py``. It fires — an
end-to-end dispatcher probe on a use-vs-mention query returned a MEMORY RECALL
block naming the right note in 0.68 s.

But it indexes the **basic-memory vault only**. Measured against the live
``~/.agents/state/harness/recall-index.json`` (597 notes, built 2026-08-07):

    .claude/hooks    ->   0 notes
    .agents/harness  ->   0 notes
    .claude/rules    ->   0 notes

Of the seven wrong claims recorded on 2026-08-07, the majority named a **tree
artifact** — ``_shared/use_vs_mention.py``, ``ci-hygiene.md`` §4, a benchmark
script, a gate's own output — every one present on disk and absent from the
vault index. This module indexes exactly that unserved surface. It deliberately
does NOT index the vault: that is ``bounded_recall``'s job and duplicating it
would double the cost for zero new coverage.

Budget discipline (the DISARMED lesson)
---------------------------------------
Four Stop checks report DISARMED because they parse the WHOLE transcript, so
cost is O(session length) with no deadline. This module is O(tree) with a hard
monotonic deadline:
  * a scoped ``os.scandir`` walk over three pinned roots — NEVER a bare walk of
    ``~/.claude`` (14 GB; blew a 10-minute timeout twice),
  * a content-snapshot hash (path|size|mtime_ns) so the hot path is a cache read,
  * a deadline checked between phases AND inside the build loop,
  * a byte cap per file — symbols come from a head slice, never a full read.

Measured surface: 331 files / 3.5 MB / 33 ms to walk.

Stdlib only. Fail-open everywhere: the worst case is an empty index, never a
raised exception. An index that could not be built returns ``ok=False`` so the
caller can emit NOT-CHECKED rather than a false CLEAN.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
INDEX_PATH = THIS / "state" / "tree_index.json"

SCHEMA_VERSION = 1

#: Pinned scan roots. Adding a root here is a deliberate cost decision.
ROOTS: tuple[Path, ...] = (
    HOME / ".claude" / "hooks",
    HOME / ".agents" / "harness",
    HOME / ".claude" / "rules",
)

#: Directories that carry no prior art (caches, vendored copies, and — crucially
#: — ``backups``/``_fleet-backups``, whose stale copies would surface as live art).
SKIP_DIRS = frozenset(
    {
        "__pycache__",
        "node_modules",
        "backups",
        "_fleet-backups",
        ".pytest_cache",
        ".ruff_cache",
        ".git",
        "venv",
        ".venv",
        "index",
        "state",
        "dist",
        "build",
        ".mypy_cache",
    }
)
EXTS = frozenset({".py", ".md"})

#: Only the head of each file is read — enough for module docstring, imports and
#: the first symbols, which is where a "does this already exist" answer lives.
HEAD_BYTES = 8192
MAX_FILES = 1200

_DEF = re.compile(r"^(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]{2,})", re.M)
_H = re.compile(r"^#{1,3}\s+(.+)$", re.M)
_PART = re.compile(r"[a-z0-9]{3,}")


def _parts(name: str) -> set[str]:
    """Split an identifier/filename into lowercase alphanumeric parts >=3 chars."""
    return set(_PART.findall(name.lower()))


def snapshot_hash(roots: tuple[Path, ...] = ROOTS) -> str:
    """Stable hash over (path|size|mtime_ns) for every indexable file."""
    entries: list[str] = []
    for root in roots:
        stack = [str(root)]
        while stack:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if e.is_dir(follow_symlinks=False):
                            if e.name.startswith(".") or e.name in SKIP_DIRS:
                                continue
                            stack.append(e.path)
                        elif os.path.splitext(e.name)[1] in EXTS:
                            try:
                                st = e.stat(follow_symlinks=False)
                                entries.append(
                                    f"{e.path}|{st.st_size}|{st.st_mtime_ns}"
                                )
                            except OSError:
                                pass
            except OSError:
                pass
    entries.sort()
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()[:24]


def _iter_files(roots: tuple[Path, ...], deadline: float) -> list[str]:
    out: list[str] = []
    for root in roots:
        stack = [str(root)]
        while stack:
            if time.monotonic() > deadline or len(out) >= MAX_FILES:
                return out
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if e.is_dir(follow_symlinks=False):
                            if e.name.startswith(".") or e.name in SKIP_DIRS:
                                continue
                            stack.append(e.path)
                        elif os.path.splitext(e.name)[1] in EXTS:
                            out.append(e.path)
            except OSError:
                pass
    return out


def build(roots: tuple[Path, ...] = ROOTS, budget_sec: float = 6.0) -> dict:
    """Build the tree index. Returns a dict with ``ok`` False if incomplete."""
    deadline = time.monotonic() + max(0.1, budget_sec)
    files = _iter_files(roots, deadline)
    entries: list[dict] = []
    truncated = False
    for fp in files:
        if time.monotonic() > deadline:
            truncated = True
            break
        p = Path(fp)
        try:
            with open(fp, "rb") as fh:
                head = fh.read(HEAD_BYTES).decode("utf-8", errors="replace")
        except OSError:
            continue
        keys: set[str] = set()
        stem = p.stem
        keys.add(stem.lower())
        keys |= _parts(stem)
        keys |= _parts(p.parent.name)
        if p.suffix == ".py":
            for sym in _DEF.findall(head):
                keys.add(sym.lower())
                keys |= _parts(sym)
        else:
            for h in _H.findall(head)[:12]:
                keys |= _parts(h)
        summary = ""
        for line in head.splitlines():
            s = line.strip().strip('"').strip("#").strip()
            if len(s) > 24 and not s.startswith(("from ", "import ", "---")):
                summary = s[:160]
                break
        entries.append(
            {
                "path": fp,
                "rel": _rel(p),
                "stem": stem,
                "keys": sorted(k for k in keys if len(k) >= 3),
                "summary": summary,
                "size": p.stat().st_size if p.exists() else 0,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "built_at": time.time(),
        "tree_hash": snapshot_hash(roots),
        "ok": (not truncated) and bool(entries),
        "truncated": truncated,
        "entries": entries,
    }


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(HOME)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def get_or_build(
    index_path: Path | None = None,
    roots: tuple[Path, ...] = ROOTS,
    budget_sec: float = 6.0,
) -> dict:
    """Return the cached index if the tree is unchanged, else rebuild.

    Never raises. On failure returns a dict with ``ok=False`` and no entries,
    which the caller MUST surface as NOT-CHECKED (not as CLEAN).
    """
    empty = {
        "schema_version": SCHEMA_VERSION,
        "built_at": 0.0,
        "tree_hash": "",
        "ok": False,
        "truncated": False,
        "entries": [],
    }
    ip = index_path or INDEX_PATH
    try:
        current = snapshot_hash(roots)
    except Exception:  # noqa: BLE001
        return empty
    try:
        if ip.exists():
            cached = json.loads(ip.read_text(encoding="utf-8"))
            if (
                isinstance(cached, dict)
                and cached.get("tree_hash") == current
                and cached.get("schema_version") == SCHEMA_VERSION
                and cached.get("ok")
            ):
                return cached
    except Exception:  # noqa: BLE001
        pass
    try:
        idx = build(roots, budget_sec=budget_sec)
    except Exception:  # noqa: BLE001
        return empty
    try:
        ip.parent.mkdir(parents=True, exist_ok=True)
        tmp = ip.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(idx), encoding="utf-8")
        os.replace(tmp, ip)
    except Exception:  # noqa: BLE001
        pass
    return idx


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build the recall-gate tree index.")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--budget", type=float, default=15.0)
    a = ap.parse_args()
    if a.rebuild and INDEX_PATH.exists():
        try:
            INDEX_PATH.unlink()
        except OSError:
            pass
    t0 = time.monotonic()
    ix = get_or_build(budget_sec=a.budget)
    dt = time.monotonic() - t0
    print(
        f"entries={len(ix['entries'])} ok={ix['ok']} truncated={ix['truncated']} "
        f"hash={ix['tree_hash']} in {dt:.3f}s"
    )
