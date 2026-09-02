#!/usr/bin/env python3
"""Named probe 2: wrong-scope settings + independent changelog re-read.

Catalog control: a settings key written at the wrong scope must be detected
(the root-scope disabledMcpServers write that was inert because the live key
is per-project). Also re-reads changelog pins without trusting receipt prose
for CONFIRMED grades.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import check_settings_scope  # noqa: E402
from hosts import adjacent_install_attempt, load_pins  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0012.json"
WRONG = HERE / "fixtures/wrong_scope_claude.json"
RIGHT = HERE / "fixtures/correct_scope_claude.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0012-probe2 {msg}")
    return 1


def _bags(doc: dict) -> list:
    return [doc, doc.get("report") or {}, doc.get("extensions") or {}]


def cells_of(doc: dict) -> list:
    for bag in _bags(doc):
        cells = bag.get("cells")
        if isinstance(cells, list) and cells:
            return cells
    return []


def host_of(doc: dict) -> dict:
    for bag in _bags(doc):
        host = bag.get("host_under_test")
        if isinstance(host, dict) and host:
            return host
    return {}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0012":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:BLD-0012" not in json.dumps(doc):
        return fail("sentinel absent")

    wrong = json.loads(WRONG.read_text(encoding="utf-8"))
    right = json.loads(RIGHT.read_text(encoding="utf-8"))
    w = check_settings_scope(wrong, "claude.json")
    r = check_settings_scope(right, "claude.json")
    if w["ok"] or w["code"] != "WRONG_SCOPE" or "disabledMcpServers" not in w["message"]:
        return fail(f"wrong-scope root write not detected {w}")
    if not r["ok"] or r["code"] != "OK":
        return fail(f"correct per-project map was flagged {r}")
    if w["ok"] == r["ok"]:
        return fail("scope detector does not discriminate")

    pins = load_pins()
    quotes = {e["quote"] for e in pins.get("entries") or [] if e.get("quote")}
    quotes.update(p["quote"] for p in pins.get("doc_pins") or [] if p.get("quote"))
    cells = cells_of(doc)
    if len(cells) < 15:
        return fail(f"cells {len(cells)} want>=15")
    confirmed = 0
    for cell in cells:
        grade = cell.get("evidence_grade")
        cite = str(cell.get("evidence_cite") or "")
        slot = cell.get("version_slot")
        if grade == "CONFIRMED":
            confirmed += 1
            if not any(q in cite or cite in q or q[:40] in cite for q in quotes):
                # Allow CONFIRMED cites that quote the pin version heading.
                ver = str(cell.get("host_version") or "")
                if ver not in cite and not any(ver in q for q in quotes):
                    return fail(f"CONFIRMED cite not in host pins {cite[:120]}")
        if slot == "one_forward" and grade not in {"NOT-CHECKED", "INFERRED"}:
            return fail(f"one_forward overclaimed {cell}")
        if grade == "CONFIRMED" and "INFERRED from our code alone" in cite:
            return fail("INFERRED labeled CONFIRMED")

    if confirmed < 3:
        return fail(f"too few changelog-backed CONFIRMED cells {confirmed}")

    adj = adjacent_install_attempt()
    if adj.get("status") != "NOT-CHECKED":
        return fail(f"adjacent install must stay NOT-CHECKED got {adj.get('status')}")
    if "npm-not-installed" not in str(adj.get("blocker")) and not adj.get("strike1", {}).get(
        "present"
    ):
        # If claude is still absent, npm blocker must be named.
        if "claude-binary-absent" not in str(adj.get("blocker")):
            return fail(f"install blocker unnamed {adj.get('blocker')}")

    host = host_of(doc)
    if host.get("live_claude_present") is True:
        return fail("receipt claims live Claude Code which this box does not have")
    if str((host.get("adjacent_install") or {}).get("status")) != "NOT-CHECKED":
        return fail("receipt adjacent_install is not NOT-CHECKED")

    print(
        json.dumps(
            {
                "probe": "probe2-scope-drift",
                "unit_id": "BLD-0012",
                "wrong_scope_detected": True,
                "correct_scope_accepted": True,
                "confirmed_cells": confirmed,
                "adjacent": adj["status"],
                "blocker": adj["blocker"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0012-probe2 wrong-scope settings and changelog re-read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
