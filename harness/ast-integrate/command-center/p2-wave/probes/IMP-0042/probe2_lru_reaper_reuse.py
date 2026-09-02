#!/usr/bin/env python3
"""Probe 2: LRU at the byte ceiling, newest survives, reaper task reused.

NEGATIVE CONTROL: exceed the ceiling and assert eviction happens and the
newest entry survives. Reviewer surface: existing reaper mutation tests still
pass, and install_reaper_task.ps1 updates PluginCacheReaper in place.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
REAPER = REPO / "tools" / "plugin-cache-reaper"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(REAPER))

import cache_policy as cp  # noqa: E402
import reap  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0042.json"
SENTINEL = "SUCCESS:IMP-0042"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0042-probe2 {msg}")
    return 1


def compute(source: bytes) -> bytes:
    return hashlib.sha256(b"imp0042-probe2\0" + source).digest() + source


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


def run_script(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-B", str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


class FakeClock:
    def __init__(self, start: int = 2_000_000_000_000) -> None:
        self.ns = start

    def __call__(self) -> int:
        self.ns += 1_000
        return self.ns


def main() -> int:
    err = check_receipt()
    if err:
        return fail(err)

    if reap.cp.apply_retention is not cp.apply_retention:
        return fail("reaper grew a duplicate retention control plane")

    ident = reap.task_identity()
    if ident["task_name"] != "PluginCacheReaper" or ident["replaced"] is not False:
        return fail(f"task identity replaced or renamed: {ident}")
    installer = REAPER / "install_reaper_task.ps1"
    if not installer.is_file():
        return fail("install_reaper_task.ps1 missing")
    ps1 = installer.read_text(encoding="utf-8")
    if ps1.count("Register-ScheduledTask") != 1:
        return fail("installer does not have exactly one Register-ScheduledTask")
    if "Set-ScheduledTask" not in ps1:
        return fail("installer does not update the existing task with Set-ScheduledTask")
    if "PluginCacheReaper" not in ps1 or "reap.py" not in ps1:
        return fail("installer does not bind PluginCacheReaper to reap.py")
    if "--max-entries" not in ps1 or "--max-bytes" not in ps1:
        return fail("installer does not pass retention argv to the existing reaper")
    if "PluginCacheReaperV2" in ps1 or "PluginCacheReaperRetention" in ps1:
        return fail("installer registers a second task name")

    mut_rc, mut_out = run_script(REAPER / "test_reap_mutations.py")
    if mut_rc != 0:
        return fail(f"reaper mutation tests failed\n{mut_out[-1500:]}")
    reap_rc, reap_out = run_script(REAPER / "test_reap.py")
    if reap_rc != 0:
        return fail(f"reaper tests failed\n{reap_out[-1500:]}")

    root = Path(tempfile.mkdtemp(prefix="imp0042-p2-")) / "cache"
    clock = FakeClock()
    cache = cp.DevCache(
        root,
        max_entries=16,
        max_bytes=160,
        retention_floor=1,
        clock=clock,
    )
    bodies = {"old": b"O" * 40, "mid": b"M" * 40, "new": b"N" * 40}
    for name in ("old", "mid", "new"):
        cache.get_or_compute(name, bodies[name], "1", compute, no_cache=False)
    names = {e["name"] for e in cp.list_entries(root)}
    if "new" not in names:
        return fail(f"newest entry did not survive: {names}")
    if "old" in names:
        return fail(f"LRU victim survived the byte ceiling: {names}")
    if cache.counters.evictions < 1:
        return fail("byte ceiling exceeded but eviction counter stayed 0")
    newest = cache.get_or_compute("new", bodies["new"], "1", compute, no_cache=False)
    if newest != compute(bodies["new"]):
        return fail("newest entry content lost after eviction")

    floor_root = Path(tempfile.mkdtemp(prefix="imp0042-p2f-")) / "cache"
    floor_cache = cp.DevCache(
        floor_root,
        max_entries=16,
        max_bytes=80,
        retention_floor=2,
        clock=FakeClock(),
    )
    for name, ch in (("a", b"A"), ("b", b"B"), ("c", b"C")):
        floor_cache.get_or_compute(name, ch * 40, "1", compute, no_cache=False)
    floor_names = {e["name"] for e in cp.list_entries(floor_root)}
    if floor_names != {"b", "c"}:
        return fail(f"retention floor did not keep the two newest: {floor_names}")

    out = {
        "probe": "probe2-lru-reaper-reuse",
        "pass": True,
        "unit_id": "IMP-0042",
        "negative_control": {
            "exceeded_byte_ceiling": True,
            "eviction_happened": True,
            "newest_survived": True,
            "lru_victim_gone": True,
        },
        "retention_floor_kept_two_newest": True,
        "reaper_task_reused_not_replaced": True,
        "task_name": ident["task_name"],
        "retention_via": ident["retention_via"],
        "mutation_tests_pass": True,
        "reviewer_id": "IMP-0042-probe2-reaper-mutations-and-task-reuse",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0042-probe2 LRU eviction; reaper task reused; mutations pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
