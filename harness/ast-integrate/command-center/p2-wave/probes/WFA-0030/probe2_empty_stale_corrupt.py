#!/usr/bin/env python3
"""Probe 2: empty store is not OK; expiry refetches; truncate is rejected.

Evidence B, mechanically independent of probe 1's identity-report path.
A cache that reports OK on an empty store is the named failure. A
freshness check that is constant True would serve an expired entry
without a transport call.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cache as C  # noqa: E402
import emit as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0030-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    pages = C.load_pages()
    urls = C.sweep_urls(pages)
    clock = C.Clock()
    transport = C.CountingTransport(pages)
    with tempfile.TemporaryDirectory(prefix="wfa-0030-p2-") as tmp:
        cache = C.AcquisitionCache(Path(tmp), transport, now=clock)
        empty_health = cache.health()
        naive = C.naive_empty_health(Path(tmp))
        if empty_health.get("ok") is True:
            return fail("empty cache reported ok")
        if empty_health.get("status") != "EMPTY":
            return fail(f"empty status {empty_health.get('status')}")
        if naive.get("ok") is not True:
            return fail("naive defect control is not ok=true")

        first = cache.get(urls[0])
        if first.source != "MISS":
            return fail(f"first fetch source={first.source}")
        populated = cache.health()
        if populated.get("ok") is not True:
            return fail("populated cache not ok")

        hit = cache.get(urls[0])
        if hit.source != "HIT":
            return fail(f"warm hit source={hit.source}")
        calls_after_hit = len(transport.calls)

        C.expire_entry(cache, urls[0])
        expired = cache.get(urls[0])
        if expired.source != "STALE-REFETCH":
            return fail(f"expired source={expired.source} (freshness may be constant true)")
        if len(transport.calls) != calls_after_hit + 1:
            return fail("expired entry did not issue a transport call")
        if expired.payload_sha256 != first.payload_sha256:
            return fail("expired refetch body drift")

        second = urls[1]
        orig = cache.get(second)
        if orig.source != "MISS":
            return fail(f"second populate source={orig.source}")
        warm2 = cache.get(second)
        if warm2.source != "HIT":
            return fail("second url not warm")
        cut_len = C.truncate_entry(cache, second)
        before_trunc = len(transport.calls)
        trunc = cache.get(second)
        if trunc.source != "CORRUPT-REFETCH":
            return fail(f"truncated source={trunc.source}")
        if len(transport.calls) != before_trunc + 1:
            return fail("truncated entry did not refetch")
        if len(trunc.body) == cut_len:
            return fail("truncated payload was served")
        if trunc.payload_sha256 != orig.payload_sha256:
            return fail("corrupt refetch body drift")

        third = urls[2]
        cache.get(third)
        C.write_empty_payload(cache, third)
        before_empty = len(transport.calls)
        empty_out = cache.get(third)
        if empty_out.source != "EMPTY-REFETCH":
            return fail(f"empty payload source={empty_out.source}")
        if len(transport.calls) != before_empty + 1:
            return fail("empty payload did not refetch")
        if len(empty_out.body) == 0:
            return fail("empty payload was served")

        # Constant-true freshness mutant: if _is_fresh always returns True,
        # expire would not refetch. Re-seed, expire, patch, confirm the
        # mutant would hide the defect — then confirm live path still refetches.
        fourth = urls[3]
        cache.get(fourth)
        cache.get(fourth)
        C.expire_entry(cache, fourth)
        live_fresh = cache._is_fresh
        cache._is_fresh = lambda meta, now: True  # type: ignore[method-assign]
        before_mutant = len(transport.calls)
        mutant = cache.get(fourth)
        if mutant.source != "HIT":
            return fail("constant-true mutant did not serve as HIT")
        if len(transport.calls) != before_mutant:
            return fail("constant-true mutant issued a network call")
        cache._is_fresh = live_fresh
        recovered = cache.get(fourth)
        if recovered.source != "STALE-REFETCH":
            return fail(f"restored freshness source={recovered.source}")

    ev_b = (doc.get("evidence") or {}).get("B") or {}
    measured = doc.get("measured") or {}
    if ev_b.get("empty_cache_ok") is not False:
        return fail("artifact empty_cache_ok")
    if measured.get("empty_cache_ok") is not False:
        return fail("measured empty_cache_ok")
    if ev_b.get("expired_refetch") is not True:
        return fail("artifact expired_refetch")
    if measured.get("truncated_rejected") is not True:
        return fail("artifact truncated_rejected")
    if ev_b.get("naive_empty_ok") is not True:
        return fail("artifact missing naive-empty contrast")
    if ev_b.get("named_failure") != C.NAMED_EMPTY_FAILURE:
        return fail("named failure token drift")

    print(
        json.dumps(
            {
                "probe": "probe2-empty-stale-corrupt",
                "empty_ok": False,
                "populated_ok": True,
                "expired_refetch": True,
                "truncated_rejected": True,
                "empty_payload_rejected": True,
                "constant_true_mutant_would_hide_expiry": True,
                "pass": True,
                "unit_id": E.UNIT,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0030-probe2 empty-not-ok stale-refetch truncate-reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
