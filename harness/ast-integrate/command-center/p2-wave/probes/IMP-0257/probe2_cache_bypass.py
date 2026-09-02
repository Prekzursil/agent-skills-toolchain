#!/usr/bin/env python3
"""Named probe 2: cache-bypass / transport-layer revalidation reviewer.

Starts from the negative control, not the author's summary: point
revalidation at a warmed cache and assert the transport-layer check FIRES.
The cache's own revalidation report is ignored. A disk mutation after the
cache is filled must be visible on the transport read and invisible on the
cache read.

Both-states: the same stale anchor revalidated through FileTransport is
SILENT on the check, restamped, and admitted.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.freshness import (  # noqa: E402
    FIRED,
    REVALIDATED,
    SILENT,
    FileTransport,
    MemoryCache,
    admit_for_binding,
    bind_on_fresh_anchors,
    is_stale,
    load_recorded_council,
    revalidate_anchor,
    transport_check,
)

FIXTURE = HERE / "fixtures" / "recorded-council.json"
SOURCES = HERE / "fixtures" / "sources"
URI = "live-url-stale.txt"
MUTATED = b"live-url stale source body v2 MUTATED\n"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0257-probe2 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0257-probe2-"))
    try:
        shutil.copytree(SOURCES, tmp, dirs_exist_ok=True)
        recorded = load_recorded_council(FIXTURE, sources_root=tmp)
        now = recorded["decision_at"]
        stale = next(
            a for a in recorded["anchors"] if a["anchor_id"] == "A-LIVE-STALE"
        )
        if not is_stale(stale, now):
            return fail("fixture A-LIVE-STALE is not stale at decision_at")

        original = (tmp / URI).read_bytes()
        original_sha = hashlib.sha256(original).hexdigest()
        transport = FileTransport(tmp)
        cache = MemoryCache()
        cache.put(URI, original)

        # Mutate disk AFTER the cache is filled so the two layers diverge.
        (tmp / URI).write_bytes(MUTATED)
        mutated_sha = hashlib.sha256(MUTATED).hexdigest()
        if mutated_sha == original_sha:
            return fail("mutation did not change content hash")

        # Negative control: point revalidation at the cache.
        bad = revalidate_anchor(stale, now, transport=transport, reader=cache)
        if bad["transport_check"] != FIRED:
            return fail(f"transport check did not FIRE on cache reader: {bad}")
        if bad["ok"] is True or bad["admitted"] is True:
            return fail("cache-pointed revalidation was admitted")
        if bad["cache_claimed_revalidation"] is not True:
            return fail("cache did not claim revalidation (control not armed)")
        if bad["cache_report_ignored"] is not True:
            return fail("cache report was treated as proof")
        if transport.ledger:
            return fail(f"transport ledger grew on cache path: {transport.ledger}")
        check = transport_check(transport, URI, cache_report=cache.report())
        if not check["fired"] or check["status"] != FIRED:
            return fail(f"transport_check silent despite empty ledger: {check}")
        # Cache still holds v1.
        if hashlib.sha256(cache.get(URI)).hexdigest() != original_sha:
            return fail("cache did not still hold the pre-mutation bytes")
        row_bad = admit_for_binding(stale, now, revalidation=bad)
        if row_bad["admitted"] is True:
            return fail("stale anchor admitted after cache-pointed revalidation")

        # Good state: real transport read sees the mutation and restamps.
        good = revalidate_anchor(stale, now, transport=transport)
        if good["transport_check"] != SILENT:
            return fail(f"transport check fired on real read: {good}")
        if good["ok"] is not True:
            return fail(f"transport revalidation not ok: {good}")
        if good["content_changed"] is not True:
            return fail("transport read did not observe the disk mutation")
        restamped = good["anchor"]
        if restamped["content_sha256"] != mutated_sha:
            return fail(
                f"restamped sha {restamped['content_sha256']} != mutated {mutated_sha}"
            )
        if restamped["content_sha256"] == original_sha:
            return fail("transport restamped the cached (old) hash")
        if transport.ledger[-1]["layer"] != "transport":
            return fail("ledger entry was not layer=transport")
        if is_stale(restamped, now):
            return fail("restamped anchor still stale")
        row_good = admit_for_binding(stale, now, revalidation=good)
        if row_good["freshness"] != REVALIDATED or row_good["admitted"] is not True:
            return fail(f"transport revalidation did not admit: {row_good}")
        decision = bind_on_fresh_anchors(
            [restamped], now, revalidations={"A-LIVE-STALE": good}
        )
        if decision["binding"] is not True:
            return fail("binding still refused after transport revalidation")

        payload = {
            "probe": "probe2-cache-bypass",
            "unit_id": "IMP-0257",
            "cache_pointed_check": bad["transport_check"],
            "cache_claimed_revalidation": bad["cache_claimed_revalidation"],
            "cache_report_ignored": bad["cache_report_ignored"],
            "cache_path_admitted": row_bad["admitted"],
            "transport_check_good": good["transport_check"],
            "transport_content_changed": good["content_changed"],
            "transport_sha256": restamped["content_sha256"],
            "cache_sha256": original_sha,
            "mutated_sha256": mutated_sha,
            "ledger_n": len(transport.ledger),
            "binding_after_transport": decision["binding"],
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"cache_check={bad['transport_check']} "
            f"transport_check={good['transport_check']} "
            f"content_changed={good['content_changed']} "
            f"binding={decision['binding']}"
        )
        print(
            "SUCCESS:IMP-0257-probe2 cache-bypass transport check FIRED; "
            "real read SILENT"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
