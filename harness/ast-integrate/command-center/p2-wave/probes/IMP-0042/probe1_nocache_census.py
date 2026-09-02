#!/usr/bin/env python3
"""Probe 1: --no-cache recomputes (counter) and writes nothing (os.walk census).

Two independent signals, as IMP-0042 requires. The counter alone could be
miswired; the census is an out-of-band os.stat walk that does not consult
cache metadata. Also checks that compute_fn actually ran.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import cache_policy as cp  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0042.json"
SENTINEL = "SUCCESS:IMP-0042"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0042-probe1 {msg}")
    return 1


def walk_census(root: Path) -> list[tuple[str, int, int]]:
    """Independent of cache_policy.directory_census: os.walk + stat only."""
    rows: list[tuple[str, int, int]] = []
    if not root.is_dir():
        return rows
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            st = path.stat()
            rel = path.relative_to(root).as_posix()
            rows.append((rel, int(st.st_size), int(st.st_mtime_ns)))
    rows.sort()
    return rows


def compute(source: bytes) -> bytes:
    return hashlib.sha256(b"imp0042-probe1\0" + source).digest() + source


def check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "sentinel absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable:{exc}"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    return None


def main() -> int:
    err = check_receipt()
    if err:
        return fail(err)

    source_text = (PLUGIN / "cache_policy.py").read_text(encoding="utf-8")
    if 'add_argument("--no-cache"' not in source_text:
        return fail("--no-cache flag not declared on the cache CLI")

    root = Path(tempfile.mkdtemp(prefix="imp0042-p1-")) / "cache"
    cache = cp.DevCache(root, max_entries=32, max_bytes=1_000_000, retention_floor=1)
    payloads = {
        "a": b"alpha-payload",
        "b": b"bravo-payload",
        "c": b"charlie-payload",
    }
    first = {
        name: cache.get_or_compute(name, body, "1.0.0", compute, no_cache=False)
        for name, body in payloads.items()
    }
    census_before = walk_census(root)
    if not census_before:
        return fail("cache populate wrote nothing; cannot census")
    recomputes_before = cache.counters.recomputes
    calls = {"n": 0}

    def counted(body: bytes) -> bytes:
        calls["n"] += 1
        return compute(body)

    recomputed = {}
    for name, body in payloads.items():
        recomputed[name] = cache.get_or_compute(
            name, body, "1.0.0", counted, no_cache=True
        )
    census_after = walk_census(root)

    if calls["n"] != 3:
        return fail(f"compute_fn ran {calls['n']} times, want 3")
    if cache.counters.recomputes != recomputes_before + 3:
        return fail(
            f"recompute counter {cache.counters.recomputes} "
            f"want {recomputes_before + 3} (counter could be miswired)"
        )
    if census_before != census_after:
        return fail(
            "directory census changed under --no-cache "
            f"before={census_before} after={census_after}"
        )
    for name, body in payloads.items():
        if recomputed[name] != first[name] or recomputed[name] != compute(body):
            return fail(f"recomputed content mismatch for {name}")
    if not cp.flag_no_cache(["--cache-dir", str(root), "--no-cache", "--name", "a"]):
        return fail("flag_no_cache missed --no-cache")
    if cp.flag_no_cache(["--cache-dir", str(root), "--name", "a"]):
        return fail("flag_no_cache true without the flag")

    out = {
        "probe": "probe1-no-cache-census",
        "pass": True,
        "unit_id": "IMP-0042",
        "two_independent_signals": True,
        "recompute_counter_delta": 3,
        "compute_fn_calls": calls["n"],
        "census_file_count": len(census_before),
        "census_unchanged": True,
        "content_recomputed": True,
        "methods": [
            "DevCache.counters.recomputes instrumentation",
            "os.walk+stat directory census (not cache metadata)",
        ],
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0042-probe1 --no-cache recomputes; census unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
