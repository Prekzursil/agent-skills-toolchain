#!/usr/bin/env python3
"""Probe 2: durable-log mechanisms routed to architecture-lane, not a file.

GOOD: every REQUIRES-DURABLE-LOG row has routed_to=architecture-lane and
      history_file is null; no forbidden history files in the probe dir.
BAD: Temporal deterministic_replay rewritten to a JSONL history file —
     mutant_caught fires.
Also: no scheduler package importable / binary on PATH.
Independent of probe 1 (replay sequencer).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import durable as D  # noqa: E402
import ir_vocab as V  # noqa: E402
import mappings as M  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0051-adapter-dag-schedulers.json"
SENTINEL = "SUCCESS:WFA-0051"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0051-probe2 {msg}")
    return 1


def main() -> int:
    rows = M.mechanism_rows()
    M.assert_no_file_fake(rows)
    routing = D.routing_report(HERE)
    mutant = D.mutant_caught(rows)
    inst = C.census()

    if routing["unrouted"]:
        return fail(f"unrouted durable rows {routing['unrouted']}")
    if routing["fake_history_files"]:
        return fail(f"fake history files {routing['fake_history_files']}")
    if not routing["mapped_or_flagged_all"]:
        return fail("a mechanism is neither mapped nor REQUIRES-DURABLE-LOG")
    if routing["row_count"] != 24:
        return fail(f"row_count={routing['row_count']}")
    if routing["architecture_ticket_count"] != routing["durable_row_count"]:
        return fail("ticket count != durable row count")
    if mutant["caught"] is not True:
        return fail("file-fake mutant not caught")
    if not inst["clean"]:
        return fail(
            "scheduler present importable="
            f"{inst['importable']} bins={inst['binaries_on_path']}"
        )

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    art_rows = doc.get("mechanism_mappings") or []
    if len(art_rows) != 24:
        return fail(f"artifact rows {len(art_rows)}")
    for r in art_rows:
        if r.get("history_file"):
            return fail(f"artifact history_file on {r['framework']}:{r['mechanism']}")
        if r.get("requires_durable_log") and r.get("routed_to") != V.ARCHITECTURE_LANE:
            return fail(f"artifact unrouted {r['framework']}:{r['mechanism']}")
        if not r.get("source_anchor"):
            return fail(f"missing source_anchor {r['framework']}:{r['mechanism']}")
        if not r.get("ir_field") and r.get("disposition") != V.REQUIRES_DURABLE_LOG:
            return fail(f"unmapped {r['framework']}:{r['mechanism']}")
    both = (doc.get("both_states") or {}).get("durable_log") or {}
    if both.get("good_routed_to_architecture") is not True:
        return fail("artifact good routing flag not true")
    if both.get("bad_file_fake_caught") is not True:
        return fail("artifact bad file-fake flag not true")
    tests = {t["id"]: t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "durable-log-routed-to-architecture-lane",
        "not-faked-with-a-file",
        "file-fake-mutant-caught",
        "no-scheduler-installed-or-run",
    ):
        if tests.get(tid, {}).get("pass") is not True:
            return fail(f"artifact test {tid} not pass")
    if (doc.get("schedulers_installed") or {}).get("clean") is not True:
        return fail("artifact schedulers_installed.clean not true")

    payload = {
        "architecture_tickets": routing["architecture_ticket_count"],
        "caught_file_fake": mutant["caught"],
        "pass": True,
        "probe": "probe2-durable-log-routing",
        "reviewer": "independent-file-fake-mutant",
        "schedulers_clean": inst["clean"],
        "unrouted": routing["unrouted"],
        "unit_id": "WFA-0051",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"tickets={routing['architecture_ticket_count']} "
        f"caught={mutant['caught']} clean={inst['clean']}"
    )
    print(
        "SUCCESS:WFA-0051-probe2 durable-log → architecture-lane; "
        "file-fake mutant caught; no scheduler installed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

