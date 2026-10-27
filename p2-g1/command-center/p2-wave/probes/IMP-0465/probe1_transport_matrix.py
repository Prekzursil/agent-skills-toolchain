#!/usr/bin/env python3
"""IMP-0465 probe1: the transport failure matrix, measured not assumed.

Runs the full payload corpus (apostrophes, heredoc terminators, control
bytes, a payload whose BODY quotes a destructive command) through the
quote-safe marshaller and through the naive transports. The marshaller
must round-trip every payload, never leak payload bytes into argv, and
never create the destructive canary; the naive transports must fail on
measured payload shapes (including the embedded-NUL crash)."""
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


def naive_defensive(transport: str, payload: bytes):
    """run_naive with crash-classified outcomes (a crash IS a measured
    naive-transport failure - e.g. embedded NUL raises ValueError inside
    CreateProcess on Windows)."""
    try:
        return Q.run_naive(transport, payload)
    except ValueError:
        return 2, b"", "embedded-null-crash"
    except OSError as exc:
        return 126, b"", "spawn-error:%s" % type(exc).__name__


def fail(msg):
    print("FAILED:IMP-0465-probe1 " + str(msg))
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0465-p1-"))
    canary = tmp / "canary.txt"
    entries = Q.corpus(canary)
    if len(entries) < 8:
        return fail("corpus too small: %d" % len(entries))
    shapes = {e["shape"] for e in entries}
    for needed in ("apostrophe", "heredoc", "injection", "mention", "nul"):
        if needed not in shapes:
            return fail("corpus missing required shape: %s" % needed)

    transports = ["bash_single_quote", "bash_heredoc", "bash_double_quote"]
    cells = []
    marshaller_ok = 0
    for entry in entries:
        payload = entry["payload"]
        if canary.exists():
            canary.unlink()

        # (a) marshaller path: must round-trip, must not touch the canary.
        inv, res = Q.deliver(payload, tmp)
        if not (res.ok and res.round_trip):
            return fail("marshaller failed on %s: %r" % (entry["id"], res.reason))
        if inv.mode == "file" and inv.payload_leaked_into_argv(payload):
            return fail("marshaller leaked payload into argv on %s" % entry["id"])
        if canary.exists():
            return fail("destructive canary created under the marshaller on %s" % entry["id"])
        unsafe = Q.unsafe_reasons(payload)
        if entry["expect_unsafe"] and inv.mode != "file":
            return fail("unsafe payload %s not routed via file: mode=%s" % (entry["id"], inv.mode))
        if not entry["expect_unsafe"] and unsafe:
            return fail("safe payload %s flagged unsafe: %s" % (entry["id"], unsafe))
        marshaller_ok += 1
        cells.append({
            "transport": "marshaller",
            "payload_id": entry["id"],
            "shape": entry["shape"],
            "mode": inv.mode,
            "unsafe_reasons": unsafe,
            "round_trip": True,
            "canary_created": False,
        })

        # (b) naive transports: measured outcome per payload shape.
        for tr in transports:
            if canary.exists():
                canary.unlink()
            rc, out, reason = naive_defensive(tr, payload)
            ok = rc == 0 and out == payload
            cell = {
                "transport": tr,
                "payload_id": entry["id"],
                "shape": entry["shape"],
                "rc": rc,
                "round_trip": ok,
                "canary_created": canary.is_file(),
                "reason": reason,
            }
            cells.append(cell)
            if canary.exists():
                # A naive transport executed the payload as a command -
                # the injection class, recorded as its own defect row.
                cell["reason"] = "payload-scanned-as-command"
                canary.unlink()

    naive_rows = [c for c in cells if c["transport"] != "marshaller"]
    naive_failures = [c for c in naive_rows if not c["round_trip"] or c.get("canary_created")]
    if not naive_failures:
        return fail("no naive transport failed on any payload - matrix vacuous")
    mention_row_ok = any(
        c["payload_id"] == "destructive-mention" and not c["round_trip"]
        for c in naive_rows
    )
    if not mention_row_ok:
        return fail("the destructive-mention payload did not break any naive transport")
    nul_row = [c for c in naive_rows if c["payload_id"] == "control-nul"]
    if not any("nul" in str(c.get("reason", "")) or not c["round_trip"] for c in nul_row):
        return fail("embedded-NUL crash not measured")

    by_transport = {}
    for c in cells:
        t = by_transport.setdefault(c["transport"], {"ok": 0, "fail": 0})
        t["ok" if (c["round_trip"] and not c.get("canary_created")) else "fail"] += 1

    print(json.dumps({
        "probe": "probe1-transport-matrix",
        "unit_id": "IMP-0465",
        "payload_count": len(entries),
        "cell_count": len(cells),
        "marshaller_ok": marshaller_ok,
        "by_transport": by_transport,
        "naive_failing_cells": [
            {k: c[k] for k in ("transport", "payload_id", "rc", "reason")}
            for c in naive_failures
        ][:16],
        "destructive_mention_present": True,
        "measured_not_assumed": True,
        "sentinel": "SENTINEL:IMP-0465:MARSHALLER-QUOTE-SAFE",
    }, indent=2))
    print("SUCCESS:IMP-0465-probe1 marshaller round-trips all shapes, canary never created; naive transports measured failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
