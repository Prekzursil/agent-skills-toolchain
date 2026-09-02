#!/usr/bin/env python3
"""Probe 2: round-trip integrity + both-states naive control + other-shell matrix.

Independent of probe 1's bash process: re-runs naive transports under dash
(the other POSIX shell on this box; pwsh is absent) and asserts received==sent
for every corpus entry through the marshaller.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from dispatch.quote_safe_marshaller import (  # noqa: E402
    MAX_QUOTE_ATTEMPTS,
    corpus,
    deliver,
    run_naive,
    try_naive_then_file,
    unsafe_reasons,
)

UID = "IMP-0465"
DASH_TRANSPORTS = ("dash_single_quote", "dash_double_quote", "dash_heredoc")


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0465-p2-") as td:
        root = Path(td)
        canary = root / "pwned.canary"
        workdir = root / "payloads"
        entries = corpus(canary)

        roundtrips = []
        for entry in entries:
            if canary.exists():
                canary.unlink()
            inv, result = deliver(entry["payload"], workdir)
            if not result.round_trip or not result.ok:
                return fail(f"round-trip {entry['id']} reason={result.reason}")
            if entry["expect_unsafe"] and inv.mode != "file":
                return fail(f"{entry['id']} expected file mode got {inv.mode}")
            if (not entry["expect_unsafe"]) and inv.mode != "inline-argv":
                return fail(f"{entry['id']} expected inline-argv got {inv.mode}")
            if inv.mode == "file" and inv.payload_leaked_into_argv(entry["payload"]):
                return fail(f"{entry['id']} leaked into argv")
            if canary.is_file():
                return fail(f"{entry['id']} marshaller created canary")
            roundtrips.append(
                {
                    "id": entry["id"],
                    "mode": inv.mode,
                    "bytes": len(entry["payload"]),
                    "reasons": inv.reasons,
                }
            )

        # Both-states control: same naive transport, one payload that must pass
        # and one known to break. A detector that is silent in both states is dead.
        plain = next(e for e in entries if e["id"] == "plain-ascii")["payload"]
        apo = next(e for e in entries if e["id"] == "apostrophe")["payload"]
        rc_good, out_good, reason_good = run_naive("bash_single_quote", plain)
        good_ok = rc_good == 0 and out_good == plain
        rc_bad, out_bad, reason_bad = run_naive("bash_single_quote", apo)
        bad_broke = not (rc_bad == 0 and out_bad == apo)
        if not good_ok:
            return fail(f"positive control died: {reason_good}")
        if not bad_broke:
            return fail("apostrophe control did not break naive bash_single_quote")

        # Other shell: dash. Here-string is bash-only; single-quote still breaks
        # on apostrophe (same quoting class, different interpreter).
        dash_cells = []
        for name in DASH_TRANSPORTS:
            for entry in entries:
                rc, out, reason = run_naive(name, entry["payload"])
                ok = rc == 0 and out == entry["payload"]
                dash_cells.append(
                    {
                        "transport": name,
                        "payload_id": entry["id"],
                        "ok": ok,
                        "reason": reason if ok else f"naive-break:{reason}",
                    }
                )
        dash_apo = next(
            c
            for c in dash_cells
            if c["transport"] == "dash_single_quote" and c["payload_id"] == "apostrophe"
        )
        if dash_apo["ok"]:
            return fail("dash_single_quote unexpectedly survived apostrophe")
        dash_plain = next(
            c
            for c in dash_cells
            if c["transport"] == "dash_single_quote" and c["payload_id"] == "plain-ascii"
        )
        if not dash_plain["ok"]:
            return fail(f"dash positive control died: {dash_plain['reason']}")

        # Retry policy: two quoting failures then switch to file, no third escape.
        switched = try_naive_then_file(apo, workdir, "bash_single_quote", {"id": "apostrophe", "shape": "apostrophe"})
        if switched.quoting_attempts != MAX_QUOTE_ATTEMPTS:
            return fail(f"quoting_attempts={switched.quoting_attempts} want={MAX_QUOTE_ATTEMPTS}")
        if not switched.switched_to_file:
            return fail("did not switch transport after second quoting failure")
        if not switched.ok:
            return fail(f"file switch still failed: {switched.reason}")

        nul = next(e for e in entries if e["id"] == "control-nul")["payload"]
        if not unsafe_reasons(nul):
            return fail("NUL not classified as control byte")
        inv_nul, res_nul = deliver(nul, workdir)
        if inv_nul.mode != "file" or not res_nul.round_trip:
            return fail("NUL did not file-round-trip")

        mention = next(e for e in entries if e["id"] == "destructive-mention")
        if b"rm -rf /" not in mention["payload"]:
            return fail("destructive mention missing from corpus")

        summary = {
            "pass": True,
            "probe": "probe2-roundtrip-other-shell",
            "unit_id": UID,
            "reviewer_id": "IMP-0465-probe2-dash-matrix",
            "roundtrips": len(roundtrips),
            "file_mode_count": sum(1 for r in roundtrips if r["mode"] == "file"),
            "inline_mode_count": sum(1 for r in roundtrips if r["mode"] == "inline-argv"),
            "both_states": {
                "good_plain_bash_single_quote": good_ok,
                "bad_apostrophe_bash_single_quote_broke": bad_broke,
                "bad_reason": reason_bad,
            },
            "other_shell": "dash",
            "dash_cells": len(dash_cells),
            "dash_red": sum(1 for c in dash_cells if not c["ok"]),
            "retry_switched_to_file": True,
            "nul_file_round_trip": True,
        }
        print(json.dumps(summary, sort_keys=True))
        print(
            f"SUCCESS:{UID}-probe2 round-trips={len(roundtrips)} "
            f"dash_red={summary['dash_red']} both-states ok"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
