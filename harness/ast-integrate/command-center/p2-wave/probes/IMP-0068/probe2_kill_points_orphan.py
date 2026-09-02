#!/usr/bin/env python3
"""Named probe 2 (reviewer): kill-points, in-place control, orphan rebuild.

Independent of probe 1's package names and of the unittest campaign seeds.
Rebuild is exercised against a blob missing from the index (an orphan).
"""
from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
STORAGE_PY = TOOLS / "marketplace" / "storage.py"
sys.path.insert(0, str(TOOLS))

from marketplace.storage import (  # noqa: E402
    INDEX_NAME,
    RegistryStorage,
    dumps_index,
    indexes_semantically_equal,
)

N_KILL = 16
CHUNK = 64
SEED = 680068
REVIEWER_ORPHAN = "reviewer-orphan-qkv"


def _fat(label: str) -> dict:
    plugins = []
    for i in range(16):
        plugins.append(
            {
                "name": f"{label}-r-{i:03d}",
                "source": f"./packages/{label}-{i:03d}",
                "version": "3.0.0",
                "license": "MIT",
                "keywords": [label],
                "skills": [],
                "channels": ["stable"],
                "digest": "sha256:" + ("ab" * 32),
                "provenance": {"note": (label * 120)[:120]},
            }
        )
    return {
        "name": "agent-skills-toolchain",
        "owner": {"name": "registry"},
        "description": f"reviewer-{label}-" + ("#" * 160),
        "plugins": plugins,
    }


def _wait_until(pred, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.005)
    return False


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def _classify(dest: Path, old: bytes, new: bytes) -> str:
    if not dest.exists():
        return "absent"
    got = dest.read_bytes()
    if got == old:
        return "old_complete"
    if got == new:
        return "new_complete"
    return "partial"


def _trial(work: Path, mode: str, old: bytes, new: bytes, pause_at: int) -> dict:
    dest = work / INDEX_NAME
    payload = work / "new.json"
    tmp_report = work / "tmp-path.txt"
    start_report = work / "start.txt"
    payload.write_bytes(new)
    dest.write_bytes(old)
    cmd = [
        sys.executable,
        "-B",
        str(STORAGE_PY),
        "child",
        "--mode",
        mode,
        "--dest",
        str(dest),
        "--payload-file",
        str(payload),
        "--pause-at",
        str(pause_at),
        "--chunk",
        str(CHUNK),
        "--tmp-report",
        str(tmp_report),
        "--start-report",
        str(start_report),
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if mode == "atomic":
        ready = _wait_until(
            lambda: tmp_report.is_file()
            and tmp_report.stat().st_size > 0
            and Path(tmp_report.read_text(encoding="utf-8").strip()).is_file()
            and Path(tmp_report.read_text(encoding="utf-8").strip()).stat().st_size
            >= pause_at
        )
    else:
        ready = _wait_until(lambda: start_report.is_file())
        if ready:
            ready = _wait_until(lambda: dest.read_bytes() != old, timeout=2.0)
    live = proc.poll() is None
    if live:
        _kill(proc)
    else:
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _kill(proc)
    return {
        "class": _classify(dest, old, new),
        "live_kill": live,
        "ready": ready,
        "pause_at": pause_at,
    }


def _campaign(mode: str, old: bytes, new: bytes) -> list[dict]:
    rng = random.Random(SEED)
    lo, hi = CHUNK, max(CHUNK + 1, len(new) - CHUNK)
    offsets = [rng.randint(lo, hi - 1) for _ in range(N_KILL)]
    rows = []
    with tempfile.TemporaryDirectory(prefix=f"imp0068-p2-{mode}-") as raw:
        base = Path(raw)
        for i, pause_at in enumerate(offsets):
            work = base / f"k{i:03d}"
            work.mkdir()
            rows.append(_trial(work, mode, old, new, pause_at))
    return rows


def _orphan_review() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0068-p2-orphan-") as raw:
        store = RegistryStorage(raw)
        store.put_package(
            {
                "name": "indexed-alpha",
                "source": "./packages/indexed-alpha",
                "version": "0.4.0",
                "license": "MIT",
                "keywords": [],
                "skills": [],
                "channels": ["stable"],
                "provenance": {"origin": "probe2"},
            },
            b"alpha-bytes",
        )
        consistent = store.read_index()
        planted = store.plant_orphan_blob(
            {
                "name": REVIEWER_ORPHAN,
                "source": "./packages/reviewer-orphan-qkv",
                "version": "0.0.1",
                "license": "MIT",
                "keywords": ["orphan"],
                "skills": [],
                "channels": ["canary"],
                "provenance": {"origin": "reviewer-not-in-probe1-set"},
            },
            b"orphan-qkv-payload",
        )
        before = store.read_index()
        orphan_in_index_before = any(
            p.get("name") == REVIEWER_ORPHAN for p in before["plugins"]
        )
        rebuilt = store.rebuild_from_blobs()
        names = [p["name"] for p in rebuilt["plugins"]]
        return {
            "orphan_name": REVIEWER_ORPHAN,
            "orphan_digest": planted["digest"],
            "orphan_in_index_before_rebuild": orphan_in_index_before,
            "consistent_plugin_count": len(consistent["plugins"]),
            "rebuilt_plugin_count": len(rebuilt["plugins"]),
            "rebuilt_names": names,
            "orphan_in_rebuild": REVIEWER_ORPHAN in names,
            "consistent_vs_rebuilt_equal": indexes_semantically_equal(
                consistent, rebuilt
            ),
        }


def main() -> int:
    old = dumps_index(_fat("old"))
    new = dumps_index(_fat("new"))
    atomic = _campaign("atomic", old, new)
    inplace = _campaign("in_place", old, new)
    atomic_partials = sum(1 for r in atomic if r["class"] == "partial")
    inplace_partials = sum(1 for r in inplace if r["class"] == "partial")
    atomic_live = sum(1 for r in atomic if r["live_kill"])
    inplace_live = sum(1 for r in inplace if r["live_kill"])
    atomic_classes = sorted({r["class"] for r in atomic})
    orphan = _orphan_review()

    payload = {
        "probe": "probe2-kill-points-orphan",
        "unit_id": "IMP-0068",
        "reviewer_id": "IMP-0068-probe2-kill-points-orphan",
        "n_kill": N_KILL,
        "index_bytes": len(new),
        "atomic_partials": atomic_partials,
        "atomic_live_kills": atomic_live,
        "atomic_classes": atomic_classes,
        "inplace_partials": inplace_partials,
        "inplace_live_kills": inplace_live,
        "orphan": orphan,
        "pass": bool(
            atomic_partials == 0
            and atomic_live == N_KILL
            and inplace_partials > 0
            and inplace_live == N_KILL
            and not orphan["orphan_in_index_before_rebuild"]
            and orphan["orphan_in_rebuild"]
            and orphan["rebuilt_plugin_count"] == orphan["consistent_plugin_count"] + 1
            and orphan["consistent_vs_rebuilt_equal"] is False
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0068-probe2 kill-point or orphan rebuild")
        return 1
    print(
        "SUCCESS:IMP-0068-probe2 no partial index at kill points; "
        "in-place control fires; orphan blob included in rebuild"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
