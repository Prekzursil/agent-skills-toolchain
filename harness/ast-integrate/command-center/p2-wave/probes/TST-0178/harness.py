"""Live pressure + mutation harness for pin-aware cache eviction (TST-0178)."""
from __future__ import annotations

import random
import sys
import threading
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.cache import PinnedLRUCache  # noqa: E402


def _cross_ref_pinned_evictions(eviction_log: list[dict]) -> list[dict]:
    """Signal (a): eviction log vs pin table recorded at the eviction instant."""
    conflicts = []
    for event in eviction_log:
        table = event.get("pin_table_before") or {}
        key = event.get("key")
        pin_at = int(event.get("pin_count_at_eviction") or 0)
        table_pins = int(table.get(key, 0) or 0)
        if pin_at > 0 or table_pins > 0:
            conflicts.append(event)
    return conflicts


def run_trial(
    *,
    seed: int,
    pinning_enabled: bool,
    max_entries: int | None = None,
    n_held: int | None = None,
    n_churn: int | None = None,
    payload_lo: int = 24,
    payload_hi: int = 96,
) -> dict[str, Any]:
    """Randomized pressure with concurrent holders.

    Holders pin (or attempt to pin) before churn, then re-read after churn.
    They do not refresh LRU during the dump, so recency alone cannot save them.
    """
    rng = random.Random(seed)
    if max_entries is None:
        max_entries = rng.randint(6, 14)
    if n_held is None:
        n_held = rng.randint(2, max(2, max_entries // 2))
    n_held = min(n_held, max_entries - 1)
    if n_held < 1:
        n_held = 1
    if n_churn is None:
        n_churn = rng.randint(max_entries * 4, max_entries * 10)
    max_bytes = max_entries * (payload_hi + 8)

    cache = PinnedLRUCache(
        max_entries=max_entries,
        max_bytes=max_bytes,
        pinning_enabled=pinning_enabled,
    )

    expected: dict[str, bytes] = {}
    resident: list[str] = []
    for i in range(max_entries):
        key = f"resident-{i}"
        data = bytes(rng.getrandbits(8) for _ in range(rng.randint(payload_lo, payload_hi)))
        cache.put(data, key=key)
        expected[key] = data
        resident.append(key)

    held_keys = list(resident[:n_held])
    pin_ok: dict[str, bool] = {}
    for key in held_keys:
        pin_ok[key] = cache.pin(key)

    start = threading.Event()
    done_pressure = threading.Event()
    outcomes: list[dict[str, Any]] = []
    out_lock = threading.Lock()

    def holder(key: str) -> None:
        first = cache.get(key)
        start.wait(timeout=10)
        # Stay pinned while pressure runs; do not call get() (would bump LRU).
        done_pressure.wait(timeout=30)
        after = cache.get(key)
        miss = after != expected[key]
        with out_lock:
            outcomes.append(
                {
                    "key": key,
                    "first_hit": first == expected[key],
                    "after_hit": after == expected[key],
                    "miss": miss,
                    "after_is_none": after is None,
                    "after_len": None if after is None else len(after),
                }
            )

    threads = [threading.Thread(target=holder, args=(k,), name=f"hold-{k}") for k in held_keys]
    for t in threads:
        t.start()

    start.set()
    for j in range(n_churn):
        key = f"churn-{seed}-{j}"
        data = bytes(rng.getrandbits(8) for _ in range(rng.randint(payload_lo, payload_hi)))
        cache.put(data, key=key)
        expected[key] = data
        time.sleep(0)  # yield so holders can schedule
    done_pressure.set()
    for t in threads:
        t.join(timeout=10)

    table_during = cache.pin_table()
    present_held_while_pinned = [k for k in held_keys if cache.get(k) == expected[k]]

    for key in held_keys:
        cache.unpin(key)

    log = cache.eviction_log()
    table_after = cache.pin_table()
    pinned_conflicts = _cross_ref_pinned_evictions(log)
    held_evictions = [e for e in log if e.get("key") in set(held_keys)]
    reader_misses = [o for o in outcomes if o.get("miss")]
    first_misses = [o for o in outcomes if not o.get("first_hit")]

    pins_match_holders = True
    if pinning_enabled:
        pins_match_holders = all(int(table_during.get(k, 0) or 0) > 0 for k in held_keys)

    property_holds = (
        len(pinned_conflicts) == 0
        and len(reader_misses) == 0
        and len(first_misses) == 0
        and all(pin_ok.values())
        and pins_match_holders
        and set(present_held_while_pinned) == set(held_keys)
    )
    # Independent of pin table: did the eviction log name a key a holder still owned?
    in_use_evicted = len(held_evictions) > 0 or len(reader_misses) > 0

    present_held = [k for k in held_keys if cache.get(k) == expected[k]]
    return {
        "seed": seed,
        "pinning_enabled": pinning_enabled,
        "max_entries": max_entries,
        "max_bytes": max_bytes,
        "n_held": n_held,
        "n_churn": n_churn,
        "held_keys": held_keys,
        "pin_ok": pin_ok,
        "evictions_total": len(log),
        "eviction_log": log,
        "pin_table_during": table_during,
        "pin_table_after": table_after,
        "pinned_conflicts": pinned_conflicts,
        "held_evictions": held_evictions,
        "reader_outcomes": outcomes,
        "reader_misses": reader_misses,
        "stats": cache.stats(),
        "present_held": present_held_while_pinned,
        "present_held_after_unpin": present_held,
        "property_holds": property_holds,
        "in_use_evicted": in_use_evicted,
        "pressure_real": len(log) > 0,
    }


def summarize(trial: dict[str, Any]) -> dict[str, Any]:
    """Compact trial row for the receipt (full logs stay on the named-probe path)."""
    return {
        "seed": trial["seed"],
        "pinning_enabled": trial["pinning_enabled"],
        "max_entries": trial["max_entries"],
        "n_held": trial["n_held"],
        "n_churn": trial["n_churn"],
        "evictions_total": trial["evictions_total"],
        "pinned_conflict_count": len(trial["pinned_conflicts"]),
        "held_eviction_count": len(trial["held_evictions"]),
        "reader_miss_count": len(trial["reader_misses"]),
        "property_holds": trial["property_holds"],
        "in_use_evicted": trial["in_use_evicted"],
        "pressure_real": trial["pressure_real"],
        "stats": trial["stats"],
        "present_held_n": len(trial["present_held"]),
        "pin_table_during": trial.get("pin_table_during") or {},
    }


def run_property_suite(n_trials: int = 16, start_seed: int = 1) -> dict[str, Any]:
    trials = [
        run_trial(seed=start_seed + i, pinning_enabled=True) for i in range(n_trials)
    ]
    fails = [summarize(t) for t in trials if not t["property_holds"]]
    vacuous = [summarize(t) for t in trials if not t["pressure_real"]]
    ok = (
        len(trials) == n_trials
        and not fails
        and not vacuous
        and all(t["property_holds"] and t["pressure_real"] for t in trials)
    )
    # Keep one full log as evidence (a) for the receipt.
    sample = trials[0]
    return {
        "ok": ok,
        "n_trials": n_trials,
        "fail_count": len(fails),
        "vacuous_count": len(vacuous),
        "fails": fails,
        "vacuous": vacuous,
        "rows": [summarize(t) for t in trials],
        "sample_eviction_log": sample["eviction_log"][:24],
        "sample_pin_table_during": sample["pin_table_during"],
        "sample_pin_table_after": sample["pin_table_after"],
        "sample_reader_outcomes": sample["reader_outcomes"],
        "sample_held_keys": sample["held_keys"],
        "sample_pinned_conflicts": sample["pinned_conflicts"],
        "total_evictions": sum(t["evictions_total"] for t in trials),
        "total_pinned_conflicts": sum(len(t["pinned_conflicts"]) for t in trials),
        "total_reader_misses": sum(len(t["reader_misses"]) for t in trials),
    }


def run_mutation_suite() -> dict[str, Any]:
    """Disable pinning. The no-pinned-eviction property must fail."""
    harsh = run_trial(
        seed=99,
        pinning_enabled=False,
        max_entries=5,
        n_held=4,
        n_churn=40,
    )
    randoms = [
        run_trial(seed=200 + i, pinning_enabled=False) for i in range(8)
    ]
    all_trials = [harsh, *randoms]
    property_failed = [t for t in all_trials if not t["property_holds"]]
    in_use = [t for t in all_trials if t["in_use_evicted"]]
    ok = (
        not harsh["property_holds"]
        and harsh["in_use_evicted"]
        and harsh["pressure_real"]
        and len(in_use) >= 1
        and len(property_failed) >= 1
    )
    return {
        "ok": ok,
        "harsh": summarize(harsh),
        "harsh_held_evictions": harsh["held_evictions"][:12],
        "harsh_reader_outcomes": harsh["reader_outcomes"],
        "harsh_eviction_log_head": harsh["eviction_log"][:16],
        "rows": [summarize(t) for t in all_trials],
        "property_failed_count": len(property_failed),
        "in_use_evicted_count": len(in_use),
        "n_trials": len(all_trials),
        "detector_fired": not harsh["property_holds"] and harsh["in_use_evicted"],
    }
