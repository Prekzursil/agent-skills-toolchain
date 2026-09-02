"""Live measurements for TST-0176: negative-TTL fetch cache."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fetch_cache import (
    ABSENCE_TTL_S,
    FetchCache,
    FakeClock,
    HttpResp,
    PermanentTransientCache,
    POSITIVE_TTL_S,
    ScriptedTransport,
    TRANSIENT_TTL_S,
    TYPE_NEGATIVE_ABSENCE,
    TYPE_NEGATIVE_TRANSIENT,
    TYPE_POSITIVE,
    empty_ok_detector,
    empty_ok_mutant_status,
)

URL_TRANSIENT = "https://estate.test/pkg/transient-fix"
URL_ABSENCE = "https://estate.test/pkg/genuine-missing"
URL_POSITIVE = "https://estate.test/pkg/present"
URL_TIMEOUT = "https://estate.test/pkg/timeout"


def _cache(tmp: str, transport: ScriptedTransport, clock: FakeClock) -> FetchCache:
    return FetchCache(Path(tmp), transport, clock)


def measure_retry_after_negative_ttl() -> dict[str, Any]:
    """Signal (a): after the short negative ttl, the next fetch hits the network."""
    clock = FakeClock()
    transport = ScriptedTransport(
        {
            URL_TRANSIENT: [
                HttpResp(503, b"unavailable"),
                HttpResp(200, b"payload-after-retry"),
            ]
        }
    )
    with tempfile.TemporaryDirectory(prefix="tst0176-retry-") as tmp:
        cache = _cache(tmp, transport, clock)
        first = cache.fetch(URL_TRANSIENT)
        calls_after_first = transport.call_count
        within = cache.fetch(URL_TRANSIENT)
        calls_within = transport.call_count
        clock.advance(TRANSIENT_TTL_S + 0.05)
        after = cache.fetch(URL_TRANSIENT)
        calls_after = transport.call_count
        observed = list(transport.calls)

    second_attempt_network = (
        calls_after == 2
        and observed[-1]["url"] == URL_TRANSIENT
        and after.from_cache is False
        and after.entry_type == TYPE_POSITIVE
        and after.body == b"payload-after-retry"
    )
    passed = (
        first.entry_type == TYPE_NEGATIVE_TRANSIENT
        and first.from_cache is False
        and first.ttl == TRANSIENT_TTL_S
        and calls_after_first == 1
        and within.from_cache is True
        and within.entry_type == TYPE_NEGATIVE_TRANSIENT
        and calls_within == 1
        and second_attempt_network
    )
    return {
        "pass": passed,
        "signal": "second-attempt-network-call",
        "first_type": first.entry_type,
        "first_ttl": first.ttl,
        "first_from_cache": first.from_cache,
        "within_ttl_from_cache": within.from_cache,
        "within_ttl_calls": calls_within,
        "after_ttl_from_cache": after.from_cache,
        "after_ttl_type": after.entry_type,
        "after_ttl_calls": calls_after,
        "second_attempt_observed_network": second_attempt_network,
        "observed_calls": observed,
        "transient_ttl_s": TRANSIENT_TTL_S,
    }


def measure_entry_type_and_ttl() -> dict[str, Any]:
    """Signal (b): recorded type (negative vs positive) and ttl on disk."""
    clock = FakeClock()
    transport = ScriptedTransport(
        {
            URL_TRANSIENT: [HttpResp(503, b"x")],
            URL_ABSENCE: [HttpResp(404, b"missing")],
            URL_POSITIVE: [HttpResp(200, b"ok-body")],
            URL_TIMEOUT: [TimeoutError("connect timeout")],
        }
    )
    with tempfile.TemporaryDirectory(prefix="tst0176-types-") as tmp:
        cache = _cache(tmp, transport, clock)
        t = cache.fetch(URL_TRANSIENT)
        a = cache.fetch(URL_ABSENCE)
        p = cache.fetch(URL_POSITIVE)
        to = cache.fetch(URL_TIMEOUT)
        rec_t = cache.inspect(URL_TRANSIENT)
        rec_a = cache.inspect(URL_ABSENCE)
        rec_p = cache.inspect(URL_POSITIVE)
        rec_to = cache.inspect(URL_TIMEOUT)
        types = {
            "transient": rec_t["type"] if rec_t else None,
            "absence": rec_a["type"] if rec_a else None,
            "positive": rec_p["type"] if rec_p else None,
            "timeout": rec_to["type"] if rec_to else None,
        }
        ttls = {
            "transient": rec_t["ttl"] if rec_t else None,
            "absence": rec_a["ttl"] if rec_a else None,
            "positive": rec_p["ttl"] if rec_p else None,
            "timeout": rec_to["ttl"] if rec_to else None,
        }
        distinguished = (
            types["transient"] == TYPE_NEGATIVE_TRANSIENT
            and types["absence"] == TYPE_NEGATIVE_ABSENCE
            and types["positive"] == TYPE_POSITIVE
            and types["timeout"] == TYPE_NEGATIVE_TRANSIENT
            and types["transient"] != types["absence"]
            and types["transient"] != types["positive"]
            and ttls["transient"] == TRANSIENT_TTL_S
            and ttls["absence"] == ABSENCE_TTL_S
            and ttls["positive"] == POSITIVE_TTL_S
            and ttls["transient"] < ttls["absence"]
            and t.ttl == TRANSIENT_TTL_S
            and a.ttl == ABSENCE_TTL_S
            and p.ttl == POSITIVE_TTL_S
            and to.ttl == TRANSIENT_TTL_S
        )
    return {
        "pass": distinguished,
        "signal": "recorded-type-and-ttl",
        "types": types,
        "ttls": ttls,
        "http_status": {
            "transient": t.http_status,
            "absence": a.http_status,
            "positive": p.http_status,
            "timeout": to.http_status,
        },
        "timeout_error": to.error,
    }


def measure_genuine_404() -> dict[str, Any]:
    """Both-states: a genuine 404 stays negatively cached for its full ttl."""
    clock = FakeClock()
    transport = ScriptedTransport(
        {
            URL_ABSENCE: [
                HttpResp(404, b"nope"),
                HttpResp(200, b"appeared-later"),
            ]
        }
    )
    with tempfile.TemporaryDirectory(prefix="tst0176-404-") as tmp:
        cache = _cache(tmp, transport, clock)
        first = cache.fetch(URL_ABSENCE)
        rec = cache.inspect(URL_ABSENCE)
        clock.advance(TRANSIENT_TTL_S + 0.05)
        mid = cache.fetch(URL_ABSENCE)
        calls_mid = transport.call_count
        still_absence = (
            mid.from_cache is True
            and mid.entry_type == TYPE_NEGATIVE_ABSENCE
            and calls_mid == 1
            and rec is not None
            and rec["ttl"] == ABSENCE_TTL_S
        )
        clock.advance(ABSENCE_TTL_S)
        late = cache.fetch(URL_ABSENCE)
        calls_late = transport.call_count
        refetch_after_full_ttl = (
            late.from_cache is False
            and calls_late == 2
            and late.entry_type == TYPE_POSITIVE
        )
    passed = (
        first.entry_type == TYPE_NEGATIVE_ABSENCE
        and first.ttl == ABSENCE_TTL_S
        and first.http_status == 404
        and still_absence
        and refetch_after_full_ttl
    )
    return {
        "pass": passed,
        "first_type": first.entry_type,
        "first_ttl": first.ttl,
        "stayed_cached_past_transient_ttl": still_absence,
        "mid_from_cache": mid.from_cache,
        "mid_calls": calls_mid,
        "after_full_ttl_calls": calls_late,
        "after_full_ttl_type": late.entry_type,
        "absence_ttl_s": ABSENCE_TTL_S,
        "transient_ttl_s": TRANSIENT_TTL_S,
    }


def measure_empty_not_ok() -> dict[str, Any]:
    """Regression seed: EMPTY cache reporting OK must be detected, not emitted."""
    clock = FakeClock()
    transport = ScriptedTransport({})
    with tempfile.TemporaryDirectory(prefix="tst0176-empty-") as tmp:
        cache = _cache(tmp, transport, clock)
        good = cache.status()
        mutant = empty_ok_mutant_status()
        populated_transport = ScriptedTransport(
            {URL_POSITIVE: [HttpResp(200, b"x")]}
        )
        cache2 = FetchCache(Path(tmp) / "populated", populated_transport, FakeClock())
        cache2.fetch(URL_POSITIVE)
        populated = cache2.status()

    detector_on_good = empty_ok_detector(good)
    detector_on_mutant = empty_ok_detector(mutant)
    detector_on_populated = empty_ok_detector(populated)
    passed = (
        good["empty"] is True
        and good["ok"] is False
        and good["exit_code"] == 1
        and good["entries"] == 0
        and detector_on_good is False
        and mutant["empty"] is True
        and mutant["ok"] is True
        and mutant["exit_code"] == 0
        and detector_on_mutant is True
        and populated["empty"] is False
        and populated["ok"] is True
        and populated["exit_code"] == 0
        and detector_on_populated is False
    )
    return {
        "pass": passed,
        "good_status": good,
        "mutant_status": mutant,
        "populated_status": populated,
        "detector_silent_on_good": detector_on_good is False,
        "detector_fires_on_mutant": detector_on_mutant is True,
        "detector_silent_on_populated": detector_on_populated is False,
    }


def measure_permanent_transient_mutant() -> dict[str, Any]:
    """Negative control: permanent-transient suppresses the post-ttl retry."""
    clock_bad = FakeClock()
    transport_bad = ScriptedTransport(
        {
            URL_TRANSIENT: [
                HttpResp(503, b"x"),
                HttpResp(200, b"should-not-be-reached"),
            ]
        }
    )
    clock_good = FakeClock()
    transport_good = ScriptedTransport(
        {
            URL_TRANSIENT: [
                HttpResp(503, b"x"),
                HttpResp(200, b"retry-body"),
            ]
        }
    )
    with tempfile.TemporaryDirectory(prefix="tst0176-mut-") as tmp:
        bad = PermanentTransientCache(
            Path(tmp) / "bad", transport_bad, clock_bad
        )
        good = FetchCache(Path(tmp) / "good", transport_good, clock_good)
        bad.fetch(URL_TRANSIENT)
        good.fetch(URL_TRANSIENT)
        clock_bad.advance(TRANSIENT_TTL_S + 0.05)
        clock_good.advance(TRANSIENT_TTL_S + 0.05)
        after_bad = bad.fetch(URL_TRANSIENT)
        after_good = good.fetch(URL_TRANSIENT)
        mutant_suppressed = (
            transport_bad.call_count == 1
            and after_bad.from_cache is True
            and after_bad.entry_type == TYPE_NEGATIVE_TRANSIENT
        )
        good_retried = (
            transport_good.call_count == 2
            and after_good.from_cache is False
            and after_good.entry_type == TYPE_POSITIVE
        )
    passed = mutant_suppressed and good_retried
    return {
        "pass": passed,
        "fired_on_mutant": mutant_suppressed,
        "silent_on_good": good_retried,
        "mutant_calls_after_short_ttl": transport_bad.call_count,
        "good_calls_after_short_ttl": transport_good.call_count,
        "mutant_from_cache": after_bad.from_cache,
        "good_from_cache": after_good.from_cache,
    }


def measure_positive_hit() -> dict[str, Any]:
    """Cache still works: a 200 is served from cache inside its ttl."""
    clock = FakeClock()
    transport = ScriptedTransport({URL_POSITIVE: [HttpResp(200, b"once")]})
    with tempfile.TemporaryDirectory(prefix="tst0176-pos-") as tmp:
        cache = _cache(tmp, transport, clock)
        first = cache.fetch(URL_POSITIVE)
        second = cache.fetch(URL_POSITIVE)
    passed = (
        first.entry_type == TYPE_POSITIVE
        and first.from_cache is False
        and second.from_cache is True
        and second.body == b"once"
        and transport.call_count == 1
    )
    return {
        "pass": passed,
        "calls": transport.call_count,
        "first_type": first.entry_type,
        "second_from_cache": second.from_cache,
        "positive_ttl_s": POSITIVE_TTL_S,
    }


def run_all() -> dict[str, Any]:
    retry = measure_retry_after_negative_ttl()
    types = measure_entry_type_and_ttl()
    genuine = measure_genuine_404()
    empty = measure_empty_not_ok()
    mutant = measure_permanent_transient_mutant()
    positive = measure_positive_hit()
    passed = all(
        x["pass"]
        for x in (retry, types, genuine, empty, mutant, positive)
    )
    return {
        "pass": passed,
        "retry_after_negative_ttl": retry,
        "entry_type_and_ttl": types,
        "genuine_404": genuine,
        "empty_not_ok": empty,
        "permanent_transient_mutant": mutant,
        "positive_hit": positive,
    }
