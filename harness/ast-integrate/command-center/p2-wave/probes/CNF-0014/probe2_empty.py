#!/usr/bin/env python3
"""Probe 2: empty receipt corpus renders 0 of N measured, never a green board."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import board as B  # noqa: E402
from sample import CLAIMS, FIXTURE_COMMIT  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0014-coverage-board.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0014-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    live = json.loads(ART.read_text(encoding="utf-8"))
    view = B.coverage_view(live)
    if view.get("green") is True and (view.get("tallies") or {}).get("measured") == 0:
        return fail("empty-set-read-as-pass on live board")
    if view.get("empty_set_is_not_pass") is not True:
        return fail("empty_set_is_not_pass is not true")

    with tempfile.TemporaryDirectory(prefix="cnf0014-p2-") as tmp:
        root = Path(tmp)
        empty_dir = root / "receipts"
        empty_dir.mkdir()
        B.write_claims(CLAIMS, root / "claims.json")
        disk_receipts = B.load_receipts(empty_dir)
        disk_claims = B.load_claims(root / "claims.json")
        if disk_receipts:
            return fail("empty dir produced receipts")
        board_n = B.render_coverage(disk_receipts, disk_claims, FIXTURE_COMMIT)
        print(
            f"empty_n_claims measured_label={board_n['measured_label']} "
            f"green={board_n['green']} color={board_n['board_color']} "
            f"tallies={json.dumps(board_n['tallies'], sort_keys=True)}"
        )
        if board_n["measured_label"] != f"0 of {len(CLAIMS)} measured":
            return fail(f"label={board_n['measured_label']}")
        if board_n["green"] is True or board_n["board_color"] != "NOT-GREEN":
            return fail("empty corpus with N>0 rendered green")
        if board_n["tallies"]["measured"] != 0:
            return fail("measured != 0 on empty corpus")
        if board_n["tallies"]["confirmed"] != 0:
            return fail("confirmed != 0 on empty corpus")

        board_00 = B.render_coverage([], [], FIXTURE_COMMIT)
        print(
            f"empty_zero_of_zero measured_label={board_00['measured_label']} "
            f"green={board_00['green']} color={board_00['board_color']}"
        )
        if board_00["measured_label"] != "0 of 0 measured":
            return fail(f"0-of-0 label={board_00['measured_label']}")
        if board_00["green"] is True or board_00["board_color"] != "NOT-GREEN":
            return fail("0-of-0 rendered as a green board")

        live_receipts, live_claims = B.load_live_corpus(REPO)
        if not live_receipts:
            if view.get("board_color") == "GREEN" or view.get("green") is True:
                return fail("live empty corpus is green")
            label = str(view.get("measured_label") or "")
            if not label.startswith("0 of ") or not label.endswith(" measured"):
                return fail(f"live measured_label={label}")
            print(f"live_empty_corpus measured_label={label} green=False")

    print(
        "empty_n_not_green=True zero_of_zero_not_green=True "
        "empty_set_read_as_pass=False"
    )
    print("SUCCESS:CNF-0014-probe2 empty corpus is 0 of N, never green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
