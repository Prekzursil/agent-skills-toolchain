#!/usr/bin/env python3
"""IMP-0465 probe2: round-trip integrity over the whole corpus plus the
naive-transport control that must demonstrably break.

For EVERY corpus entry the received bytes must equal the sent bytes through
the marshaller. As the both-states control, one payload known to break the
naive single-quote transport is shown breaking it (so the marshaller's file
routing is not guarding against a transport that never fails anyway)."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
QSM_PY = REPO / "tools" / "dispatch" / "quote_safe_marshaller.py"

spec = importlib.util.spec_from_file_location("imp0465_marshaller", QSM_PY)
Q = importlib.util.module_from_spec(spec)
sys.modules["imp0465_marshaller"] = Q
spec.loader.exec_module(Q)


def fail(msg):
    print("FAILED:IMP-0465-probe2 " + str(msg))
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0465-p2-"))
    canary = tmp / "canary.txt"
    entries = Q.corpus(canary)

    # (a) round-trip integrity for every corpus entry, sha-verified.
    results = []
    for entry in entries:
        payload = entry["payload"]
        inv, res = Q.deliver(payload, tmp)
        ok = res.ok and res.round_trip and res.received == payload
        results.append({
            "id": entry["id"],
            "mode": inv.mode,
            "sent_bytes": len(payload),
            "received_bytes": len(res.received),
            "sha_sent": Q.sha256_hex(payload)[:16],
            "sha_received": Q.sha256_hex(res.received)[:16],
            "round_trip": bool(ok),
        })
        if not ok:
            return fail("round-trip broken for %s" % entry["id"])
    if len(results) != len(entries):
        return fail("not every corpus entry measured")

    # (b) control: the apostrophe payload MUST break the naive
    # single-quote transport (rc!=0 or bytes differ). If it ever passed,
    # the control would be inert and the marshaller unnecessary.
    apos = next(e for e in entries if e["id"] == "apostrophe")
    try:
        rc, out, reason = Q.run_naive("bash_single_quote", apos["payload"])
        naive_broke = not (rc == 0 and out == apos["payload"])
        naive_detail = {"rc": rc, "reason": reason}
    except (ValueError, OSError) as exc:
        naive_broke = True
        naive_detail = {"crash": type(exc).__name__}
    if not naive_broke:
        return fail("control inert: naive single-quote transport survived the apostrophe payload")

    # (c) the same payload through the marshaller arrives byte-identical.
    inv, res = Q.deliver(apos["payload"], tmp)
    if not (res.ok and res.received == apos["payload"] and inv.mode == "file"):
        return fail("marshaller did not file-route the apostrophe payload")

    print(json.dumps({
        "probe": "probe2-roundtrip",
        "unit_id": "IMP-0465",
        "entries": results,
        "all_round_trip": all(r["round_trip"] for r in results),
        "naive_control_broke": naive_broke,
        "naive_control_detail": naive_detail,
        "marshaller_file_routed_apostrophe": inv.mode == "file",
        "sentinel": "SENTINEL:IMP-0465:MARSHALLER-QUOTE-SAFE",
    }, indent=2))
    print("SUCCESS:IMP-0465-probe2 every corpus entry round-trips byte-identical; naive control demonstrably breaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
