#!/usr/bin/env python3
"""Tests for tools/plugin/cache_policy.py -- the development-loop cache (IMP-0042).

Stdlib-only with its own ``__main__`` (there is no repo-wide pytest autodiscovery),
also collectable by pytest.  Every retention property is checked in BOTH states
where a both-states check is possible: the ceiling is exceeded and eviction fires,
the ceiling is respected and nothing fires; the idle-TTL comparison is inverted in a
scratch copy of the module and the same oracle must go RED (a test that stays green
under the inverted comparison is not protecting anything).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import cache_policy as cp  # noqa: E402

# Every FakeClock tick is 1 microsecond so idle-TTL tests can reason in exact ticks.
TICK_NS = 1_000


class FakeClock:
    def __init__(self, start: int = 2_000_000_000_000) -> None:
        self.ns = start

    def __call__(self) -> int:
        self.ns += TICK_NS
        return self.ns


def compute(source: bytes) -> bytes:
    return hashlib.sha256(b"test-cache-policy\0" + source).digest() + source


def census(root: Path) -> list[tuple[str, int, int]]:
    """os.walk + stat only -- independent of the module's own index."""
    rows: list[tuple[str, int, int]] = []
    if not root.is_dir():
        return rows
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            st = path.stat()
            rows.append((path.relative_to(root).as_posix(), st.st_size, st.st_mtime_ns))
    rows.sort()
    return rows


def fresh_root(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"cache-policy-{prefix}-")) / "cache"


def names_on_disk(root: Path) -> set[str]:
    return {str(e["name"]) for e in cp.list_entries(root)}


def blob_count(root: Path) -> int:
    blobs = root / "blobs"
    return len(list(blobs.iterdir())) if blobs.is_dir() else 0


# ---------------------------------------------------------------------------
# --no-cache
# ---------------------------------------------------------------------------


def test_no_cache_recomputes_and_writes_nothing() -> None:
    root = fresh_root("nocache")
    cache = cp.DevCache(root, max_entries=8, max_bytes=10_000, retention_floor=1)
    first = cache.get_or_compute("a", b"alpha", "1", compute, no_cache=False)
    before = census(root)
    assert before, "populate wrote nothing"
    calls = {"n": 0}

    def counted(body: bytes) -> bytes:
        calls["n"] += 1
        return compute(body)

    again = cache.get_or_compute("a", b"alpha", "1", counted, no_cache=True)
    assert calls["n"] == 1, "compute_fn did not run under --no-cache"
    assert again == first == compute(b"alpha")
    assert cache.counters.recomputes == 1
    assert census(root) == before, "--no-cache changed the directory"
    assert cp.flag_no_cache(["--no-cache", "--name", "a"]) is True
    assert cp.flag_no_cache(["--name", "a"]) is False


def test_cache_hit_does_not_recompute() -> None:
    root = fresh_root("hit")
    cache = cp.DevCache(root, max_entries=8, max_bytes=10_000, retention_floor=1)
    cache.get_or_compute("a", b"alpha", "1", compute)

    def boom(_body: bytes) -> bytes:
        raise AssertionError("hit path called compute_fn")

    assert cache.get_or_compute("a", b"alpha", "1", boom) == compute(b"alpha")
    assert cache.counters.hits == 1 and cache.counters.misses == 1


# ---------------------------------------------------------------------------
# ceilings, LRU order, floor -- both states
# ---------------------------------------------------------------------------


def test_byte_ceiling_evicts_lru_and_newest_survives() -> None:
    root = fresh_root("bytes")
    cache = cp.DevCache(root, max_entries=16, max_bytes=160, retention_floor=1, clock=FakeClock())
    for name in ("old", "mid", "new"):
        cache.get_or_compute(name, name.encode() * 20, "1", compute)  # ~72 bytes each
    names = names_on_disk(root)
    assert "new" in names, f"newest did not survive: {names}"
    assert "old" not in names, f"LRU victim survived: {names}"
    assert cache.counters.evictions >= 1
    assert blob_count(root) == len(names), "index and blobs disagree after eviction"


def test_under_both_ceilings_nothing_is_evicted() -> None:
    root = fresh_root("silent")
    cache = cp.DevCache(root, max_entries=16, max_bytes=10_000, retention_floor=1, clock=FakeClock())
    for name in ("old", "mid", "new"):
        cache.get_or_compute(name, name.encode() * 20, "1", compute)
    assert names_on_disk(root) == {"old", "mid", "new"}
    assert cache.counters.evictions == 0


def test_entry_ceiling_evicts_least_recently_used_not_oldest_written() -> None:
    root = fresh_root("entries")
    cache = cp.DevCache(root, max_entries=2, max_bytes=10_000, retention_floor=1, clock=FakeClock())
    cache.get_or_compute("a", b"A" * 8, "1", compute)
    cache.get_or_compute("b", b"B" * 8, "1", compute)
    cache.get_or_compute("a", b"A" * 8, "1", compute)  # touch a -> b is now the LRU
    cache.get_or_compute("c", b"C" * 8, "1", compute)
    assert names_on_disk(root) == {"a", "c"}, names_on_disk(root)


def test_retention_floor_beats_the_byte_ceiling() -> None:
    root = fresh_root("floor")
    cache = cp.DevCache(root, max_entries=16, max_bytes=80, retention_floor=2, clock=FakeClock())
    for name, ch in (("a", b"A"), ("b", b"B"), ("c", b"C")):
        cache.get_or_compute(name, ch * 40, "1", compute)
    assert names_on_disk(root) == {"b", "c"}, names_on_disk(root)


# ---------------------------------------------------------------------------
# idle TTL -- both states, plus the plan/apply split the reaper task relies on
# ---------------------------------------------------------------------------


def _ttl_fixture(module=cp) -> tuple[Path, object]:
    root = fresh_root("ttl")
    clock = FakeClock()
    cache = module.DevCache(root, max_entries=16, max_bytes=10_000, retention_floor=1, clock=clock)
    cache.get_or_compute("stale", b"S" * 8, "1", compute)
    clock.ns += 50 * TICK_NS  # stale idles for 50 ticks
    cache.get_or_compute("fresh", b"F" * 8, "1", compute)
    return root, clock


def _ttl_oracle(module) -> None:
    root, clock = _ttl_fixture(module)
    now = clock.ns + TICK_NS
    kept = module.apply_retention(
        root, max_entries=16, max_bytes=10_000, retention_floor=1, idle_ttl_ns=10 * TICK_NS, now_ns=now
    )
    names = {str(r["name"]) for r in kept}
    assert names == {"fresh"}, f"idle-TTL kept {names}"
    assert {str(e["name"]) for e in module.list_entries(root)} == {"fresh"}


def test_idle_ttl_evicts_stale_and_keeps_fresh() -> None:
    _ttl_oracle(cp)


def test_idle_ttl_within_window_evicts_nothing() -> None:
    root, clock = _ttl_fixture()
    kept = cp.apply_retention(
        root, max_entries=16, max_bytes=10_000, retention_floor=1, idle_ttl_ns=10_000 * TICK_NS, now_ns=clock.ns
    )
    assert {str(r["name"]) for r in kept} == {"stale", "fresh"}


def test_idle_ttl_respects_the_floor() -> None:
    root, clock = _ttl_fixture()
    kept = cp.apply_retention(
        root, max_entries=16, max_bytes=10_000, retention_floor=2, idle_ttl_ns=0, now_ns=clock.ns + TICK_NS
    )
    assert {str(r["name"]) for r in kept} == {"stale", "fresh"}, "floor did not beat the TTL"


def test_retention_plan_reports_without_touching_disk() -> None:
    root = fresh_root("plan")
    cache = cp.DevCache(root, max_entries=16, max_bytes=10_000, retention_floor=1, clock=FakeClock())
    for name in ("a", "b", "c"):
        cache.get_or_compute(name, name.encode() * 20, "1", compute)
    before = census(root)
    plan = cp.retention_plan(root, max_entries=1, max_bytes=10_000, retention_floor=1)
    assert [str(v["name"]) for v in plan["victims"]] == ["a", "b"]
    assert [str(k["name"]) for k in plan["kept"]] == ["c"]
    assert plan["bytes_after"] < plan["bytes_before"]
    dry = cp.apply_retention(root, max_entries=1, max_bytes=10_000, retention_floor=1, dry_run=True)
    assert [str(r["name"]) for r in dry] == ["c"]
    assert census(root) == before, "plan/dry-run changed the directory"
    applied = cp.apply_retention(root, max_entries=1, max_bytes=10_000, retention_floor=1)
    assert [str(r["name"]) for r in applied] == ["c"]
    assert names_on_disk(root) == {"c"} and blob_count(root) == 1


def test_retention_plan_on_missing_index_is_a_no_op() -> None:
    root = fresh_root("noindex")
    plan = cp.retention_plan(root)
    assert plan["index_present"] is False and plan["victims"] == []
    assert cp.apply_retention(root) == []
    assert not root.exists(), "retention created a cache that did not exist"


# ---------------------------------------------------------------------------
# both-states on the SUITE: the inverted idle-TTL comparison must be caught
# ---------------------------------------------------------------------------

TTL_NEEDLE = "if idle > int(idle_ttl_ns) and (len(rows) - len(victims)) > floor:"
TTL_MUTANT = "if idle < int(idle_ttl_ns) and (len(rows) - len(victims)) > floor:"
FLOOR_NEEDLE = "    while _over() and len(rows) > floor:"
FLOOR_MUTANT = "    while _over():"

_MUTANT_RUNNER = r'''
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("cache_policy_mutant", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module  # dataclasses resolve string annotations via sys.modules
spec.loader.exec_module(module)
sys.path.insert(0, sys.argv[2])
import test_cache_policy as suite
oracle = getattr(suite, sys.argv[3])
oracle(module)
print("MUTANT-SURVIVED")
'''


def _oracle_survives(mutant_source: str, oracle_name: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="cache-policy-mutant-") as raw:
        mutant = Path(raw) / "cache_policy_mutant.py"
        mutant.write_text(mutant_source, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-B", "-c", _MUTANT_RUNNER, str(mutant), str(HERE), oracle_name],
            capture_output=True,
            text=True,
            timeout=60,
        )
    return proc.returncode == 0 and "MUTANT-SURVIVED" in proc.stdout


def _floor_oracle(module) -> None:
    root = fresh_root("floor-oracle")
    cache = module.DevCache(root, max_entries=16, max_bytes=80, retention_floor=2, clock=FakeClock())
    for name, ch in (("a", b"A"), ("b", b"B"), ("c", b"C")):
        cache.get_or_compute(name, ch * 40, "1", compute)
    assert {str(e["name"]) for e in module.list_entries(root)} == {"b", "c"}


def test_inverted_idle_ttl_comparison_is_caught() -> None:
    source = (PLUGIN / "cache_policy.py").read_text(encoding="utf-8")
    assert TTL_NEEDLE in source, "TTL anchor moved; update the mutation needle"
    assert not _oracle_survives(source.replace(TTL_NEEDLE, TTL_MUTANT, 1), "_ttl_oracle"), (
        "inverted idle-TTL comparison SURVIVED the oracle"
    )
    assert _oracle_survives(source, "_ttl_oracle"), "oracle is RED on the unmutated module"


def test_dropped_retention_floor_is_caught() -> None:
    source = (PLUGIN / "cache_policy.py").read_text(encoding="utf-8")
    assert FLOOR_NEEDLE in source, "floor anchor moved; update the mutation needle"
    assert not _oracle_survives(source.replace(FLOOR_NEEDLE, FLOOR_MUTANT, 1), "_floor_oracle"), (
        "dropped retention floor SURVIVED the oracle"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_reports_a_plan_and_applies_only_with_apply() -> None:
    root = fresh_root("cli")
    cache = cp.DevCache(root, max_entries=16, max_bytes=10_000, retention_floor=1, clock=FakeClock())
    for name in ("a", "b"):
        cache.get_or_compute(name, name.encode() * 20, "1", compute)
    common = [sys.executable, "-B", str(PLUGIN / "cache_policy.py"), "--cache-dir", str(root), "--max-entries", "1"]
    dry = subprocess.run(common, capture_output=True, text=True, timeout=60)
    assert dry.returncode == 0, dry.stderr
    report = json.loads(dry.stdout)
    assert report["retention"]["applied"] is False and report["retention"]["victims"] == ["a"]
    assert names_on_disk(root) == {"a", "b"}, "dry-run CLI evicted"
    applied = subprocess.run([*common, "--apply"], capture_output=True, text=True, timeout=60)
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["retention"]["applied"] is True
    assert names_on_disk(root) == {"b"}
    assert 'add_argument("--no-cache"' in (PLUGIN / "cache_policy.py").read_text(encoding="utf-8")


TESTS = [
    test_no_cache_recomputes_and_writes_nothing,
    test_cache_hit_does_not_recompute,
    test_byte_ceiling_evicts_lru_and_newest_survives,
    test_under_both_ceilings_nothing_is_evicted,
    test_entry_ceiling_evicts_least_recently_used_not_oldest_written,
    test_retention_floor_beats_the_byte_ceiling,
    test_idle_ttl_evicts_stale_and_keeps_fresh,
    test_idle_ttl_within_window_evicts_nothing,
    test_idle_ttl_respects_the_floor,
    test_retention_plan_reports_without_touching_disk,
    test_retention_plan_on_missing_index_is_a_no_op,
    test_inverted_idle_ttl_comparison_is_caught,
    test_dropped_retention_floor_is_caught,
    test_cli_reports_a_plan_and_applies_only_with_apply,
]


def main() -> int:
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"ok   {test.__name__}")
        except Exception:  # noqa: BLE001 - report every failure, then the verdict
            failed += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    if failed:
        print(f"FAILED:test_cache_policy {failed}/{len(TESTS)} checks failed")
        return 1
    print(f"SUCCESS:test_cache_policy {len(TESTS)}/{len(TESTS)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
