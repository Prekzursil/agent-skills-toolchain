#!/usr/bin/env python3
"""TST-0060 probe1: receipt matrix recount (live, fail-closed).

Recounts the receipt's own by_transport census against failure_rates and
the matrix invariants (cell_count = payloads x transports; green + red =
cell_count; control transports red; write_tool green), then checks the
delivery predicate.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/receipts/TST-0060.json"
UNIT = "TST-0060"
SENTINEL = "SUCCESS:TST-0060"
MIN_BYTES = 2048

fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= MIN_BYTES, "under-min-bytes", str(OUT.stat().st_size))
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared", str(doc.get("state")))
    chk(str(doc.get("unit_id") or doc.get("id") or "") == UNIT, "unit-id")
    chk(SENTINEL in text, "sentinel-absent")

    m = doc.get("matrix") or {}
    bt = m.get("by_transport") or {}
    rates = doc.get("failure_rates") or {}
    chk(len(bt) >= 4, "by-transport-too-thin", str(len(bt)))
    n_cells = int(m.get("cell_count", -1))
    n_pay = int(m.get("payload_count", -1))
    n_tr = int(m.get("transport_count", -1))
    chk(n_cells == n_pay * n_tr, "cells-invariant", f"{n_cells} != {n_pay}x{n_tr}")
    green, red = int(m.get("green_count", -1)), int(m.get("red_count", -1))
    chk(green + red == n_cells, "green-red-sum", f"{green}+{red} != {n_cells}")
    # recount by_transport against failure_rates and invariants
    total_eq = 0
    for t, row in bt.items():
        n, neq = int(row.get("n", -1)), int(row.get("n_equal", -1))
        chk(n == 59, "per-transport-n:" + t, str(n))
        total_eq += neq
        fr = rates.get(t)
        if fr is None:
            continue
        chk(neq == int(fr.get("n_equal", -1)), "rates-vs-by-transport:" + t)
        exp = 1.0 - (neq / n) if n else 1.0
        chk(abs(exp - float(fr.get("failure_rate", -1))) < 5e-6, "rate-math:" + t)
        kinds = row.get("mismatch_kinds") or {}
        chk(sum(kinds.values()) == n, "kinds-sum:" + t)
    chk(total_eq == green, "green-recount", f"sum(n_equal)={total_eq} green={green}")
    # controls: write_tool all green; both control transports all red
    chk(bt.get("write_tool", {}).get("n_equal") == 59, "write-tool-must-be-green")
    for t in m.get("control_transports") or []:
        chk(bt.get(t, {}).get("failure_rate", 0) > 0, "control-transport-must-be-red:" + t)
    hs = bt.get("here_string") or {}
    chk("extra_trailing_newline" in (hs.get("mismatch_kinds") or {}), "here-string-newline-kind-recorded")
    rc = doc.get("red_cell_control") or {}
    chk(rc.get("fired_on_double_quoted_c") is True and rc.get("fired_on_expanding_heredoc") is True and rc.get("silent_on_write_tool") is True, "red-cell-controls")
    tests = doc.get("tests") or []
    chk(any(str(t.get("result") or t.get("verdict") or "").upper() == "PASS" for t in tests), "no-passing-tests")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 by_transport recount exact (" + str(len(bt)) + " transports, " + str(n_cells) + " cells, green " + str(green) + " red " + str(red) + "); invariants and controls hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
