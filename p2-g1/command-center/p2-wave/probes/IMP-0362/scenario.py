#!/usr/bin/env python3
"""IMP-0362 scenario: a full council prep picture.

Builds a prepared seat and the three receipt-declared negative controls in one
temporary tree, prints the scenario JSON, and exits non-zero if ANY prepared
seat is refused or ANY negative control is allowed to speak.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.prep import PrepGate, UnpreparedError  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gate = PrepGate(root)

        def make_seat(name, notes, sources, tool_calls, asserted=False):
            seat = root / name
            seat.mkdir()
            (seat / "prep.json").write_text(json.dumps({
                "seat": name, "notes": "notes.md", "sources": sources,
                "asserted_prepared": asserted,
            }), encoding="utf-8")
            (seat / "notes.md").write_text(notes, encoding="utf-8")
            (seat / "tool_log.json").write_text(
                json.dumps({"tool_calls": tool_calls}), encoding="utf-8")

        src = "Sources read: brief.md covers the quorum floor of five seats."
        make_seat("alice",
                  "alice notes: the quorum floor five seats is load-bearing",
                  ["brief.md"],
                  [{"tool": "Read", "target": "brief.md", "status": "ok"}])
        (root / "alice" / "brief.md").write_text(
            "brief: quorum floor five seats.\n", encoding="utf-8")
        make_seat("carol",
                  "carol asserts preparation without any fetch",
                  ["brief.md"],
                  [],
                  asserted=True)
        make_seat("dan",
                  "dan claims reads via asserted status",
                  ["brief.md"],
                  [{"tool": "Read", "target": "brief.md", "status": "asserted"}])
        (root / "dan" / "brief.md").write_text("brief: reviewer count two.\n",
                                               encoding="utf-8")
        verdicts = {}
        for seat in ("alice", "carol", "dan"):
            try:
                v = gate.require_prepared(seat)
                verdicts[seat] = {"allowed": True, "anchors": v["anchors"]}
            except UnpreparedError as exc:
                verdicts[seat] = {"allowed": False, "reasons": exc.reasons}
        ok = (verdicts["alice"]["allowed"] is True
              and verdicts["carol"]["allowed"] is False
              and verdicts["dan"]["allowed"] is False)
        print(json.dumps({"scenario": "council-prep", "unit_id": "IMP-0362",
                          "pass": ok, "verdicts": verdicts}, sort_keys=True))
        if not ok:
            print("FAILED:IMP-0362-scenario verdicts wrong")
            return 1
        print("SUCCESS:IMP-0362-scenario prepared speaks; asserted refused")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
