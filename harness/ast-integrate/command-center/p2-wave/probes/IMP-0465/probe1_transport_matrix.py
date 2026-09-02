#!/usr/bin/env python3
"""Probe 1: transport x payload-shape failure matrix, measured not assumed.

A red cell is required (naive apostrophe / heredoc / injection). Marshaller
cells must be green for every corpus entry, including the body that quotes a
destructive command as mention.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from dispatch.quote_safe_marshaller import (  # noqa: E402
    corpus,
    deliver,
    run_matrix,
    run_naive,
    unsafe_reasons,
)

UID = "IMP-0465"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0465-p1-") as td:
        root = Path(td)
        canary = root / "pwned.canary"
        workdir = root / "payloads"
        matrix = run_matrix(workdir, canary)
        entries = corpus(canary)

        if not matrix["destructive_mention_present"]:
            return fail("corpus missing payload whose body quotes a destructive command")
        if matrix["payload_count"] < 8:
            return fail(f"corpus too small {matrix['payload_count']}")

        marsh = [c for c in matrix["cells"] if c["transport"] == "marshaller"]
        if len(marsh) != len(entries):
            return fail(f"marshaller cells {len(marsh)} != corpus {len(entries)}")
        missed = [c["payload_id"] for c in marsh if not c["ok"] or not c["round_trip"]]
        if missed:
            return fail(f"marshaller miss {missed}")
        leaked = [c["payload_id"] for c in marsh if c.get("leaked_into_argv")]
        if leaked:
            return fail(f"unsafe payload inlined into argv {leaked}")
        if any(c["canary_created"] for c in marsh):
            return fail("marshaller executed injection canary")

        by_id = {e["id"]: e for e in entries}

        apo = by_id["apostrophe"]["payload"]
        rc, out, reason = run_naive("bash_single_quote", apo)
        if rc == 0 and out == apo:
            return fail("naive bash_single_quote unexpectedly round-tripped apostrophe")

        eof_payload = by_id["heredoc-eof-line"]["payload"]
        rc, out, reason = run_naive("bash_heredoc", eof_payload)
        if rc == 0 and out == eof_payload:
            return fail("naive bash_heredoc unexpectedly round-tripped EOF-in-body")

        inj = by_id["injection-canary"]["payload"]
        if canary.exists():
            canary.unlink()
        rc, out, reason = run_naive("bash_single_quote", inj)
        naive_executed = canary.is_file()
        naive_corrupt = not (rc == 0 and out == inj)
        if not (naive_executed or naive_corrupt):
            return fail("injection control silent in both states")
        if canary.exists():
            canary.unlink()
        inv, mres = deliver(inj, workdir)
        if canary.is_file():
            return fail("marshaller ran the injected touch")
        if inv.mode != "file":
            return fail(f"injection used {inv.mode}, want file")
        if not mres.round_trip:
            return fail("marshaller failed injection round-trip")

        for entry in entries:
            reasons = unsafe_reasons(entry["payload"])
            if bool(reasons) != bool(entry["expect_unsafe"]):
                return fail(
                    f"{entry['id']} unsafe={bool(reasons)} expect={entry['expect_unsafe']} {reasons}"
                )

        red = [c for c in matrix["cells"] if c["transport"] != "marshaller" and not c["ok"]]
        if not red:
            return fail("matrix has no red cell; harness cannot show a known-failing transport")

        mention = [c for c in marsh if c["payload_id"] == "destructive-mention"]
        if not mention or not mention[0]["round_trip"]:
            return fail("destructive-mention did not round-trip through marshaller")

        summary = {
            "pass": True,
            "probe": "probe1-transport-matrix",
            "unit_id": UID,
            "payload_count": matrix["payload_count"],
            "cell_count": matrix["cell_count"],
            "marshaller_ok": all(c["ok"] for c in marsh),
            "red_cells": len(red),
            "naive_apostrophe_broke": True,
            "naive_heredoc_eof_broke": True,
            "injection_naive_executed_or_corrupt": True,
            "injection_canary_executed_on_naive": naive_executed,
            "destructive_mention_present": True,
            "by_transport": {
                t: {"ok": v["ok"], "fail": v["fail"]}
                for t, v in matrix["by_transport"].items()
            },
        }
        print(json.dumps(summary, sort_keys=True))
        for t, v in sorted(matrix["by_transport"].items()):
            print(f"  {t}: ok={v['ok']} fail={v['fail']}")
        print(
            f"SUCCESS:{UID}-probe1 matrix measured; "
            f"marshaller {len(marsh)}/{len(marsh)}; red_cells={len(red)}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
