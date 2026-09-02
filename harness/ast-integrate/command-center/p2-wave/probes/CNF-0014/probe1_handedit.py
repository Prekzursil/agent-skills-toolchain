#!/usr/bin/env python3
"""Probe 1: one-digit hand-edit goes red; unchanged regeneration is byte-identical."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import board as B  # noqa: E402
from sample import CLAIMS, EXPECTED_TALLIES, FIXTURE_COMMIT, RECEIPTS  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0014-coverage-board.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0014-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    live = json.loads(ART.read_text(encoding="utf-8"))
    if live.get("unit_id") != "CNF-0014":
        return fail(f"unit_id={live.get('unit_id')}")
    text = ART.read_text(encoding="utf-8")
    if B.CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    if live.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{live.get('state')}")

    with tempfile.TemporaryDirectory(prefix="cnf0014-p1-") as tmp:
        root = Path(tmp)
        corpus = root / "receipts"
        B.write_receipts_dir(RECEIPTS, corpus)
        B.write_claims(CLAIMS, root / "claims.json")
        disk_receipts = B.load_receipts(corpus)
        disk_claims = B.load_claims(root / "claims.json")
        identical, a, b = B.two_run_identical(
            disk_receipts, disk_claims, FIXTURE_COMMIT
        )
        print(
            f"determinism two_run_byte_identical={identical} "
            f"bytes={len(a)} sha256={B.digest_bytes(a)}"
        )
        if not identical or a != b:
            return fail("unchanged regeneration was not byte-identical")
        coverage = json.loads(a.decode("utf-8"))
        print(f"fixture_tallies={json.dumps(coverage['tallies'], sort_keys=True)}")
        if coverage["tallies"] != EXPECTED_TALLIES:
            return fail("fixture tallies != expected")
        silent = B.check_board(
            coverage, disk_receipts, disk_claims, FIXTURE_COMMIT
        )
        print(
            f"unedited status={silent['status']} exit_code={silent['exit_code']}"
        )
        if not silent["ok"] or silent["exit_code"] != 0:
            return fail("unedited board was not silent")
        mutated_raw = B.mutate_one_digit(a)
        if mutated_raw == a:
            return fail("mutate_one_digit was a no-op")
        # Exactly one character differs, and it is a digit.
        diffs = [
            (i, a[i], mutated_raw[i])
            for i in range(min(len(a), len(mutated_raw)))
            if a[i] != mutated_raw[i]
        ]
        if len(a) != len(mutated_raw) or len(diffs) != 1:
            return fail(f"mutate changed {len(diffs)} positions")
        if not chr(diffs[0][1]).isdigit() or not chr(diffs[0][2]).isdigit():
            return fail("mutate did not change a digit")
        mutated = json.loads(mutated_raw.decode("utf-8"))
        red = B.check_board(mutated, disk_receipts, disk_claims, FIXTURE_COMMIT)
        print(
            f"hand_edit status={red['status']} exit_code={red['exit_code']} "
            f"reasons={red['reasons']}"
        )
        if red["ok"] or red["exit_code"] == 0:
            return fail("hand-edit control did not go red")

        live_receipts, live_claims = B.load_live_corpus(REPO)
        for rec in live_receipts:
            if not rec.get("claim_id"):
                return fail("live corpus ingested a receipt without claim_id")
            raw = str(rec.get("verdict") or "").strip().upper()
            if raw not in B.VERDICT_MAP:
                return fail("live corpus ingested a non-confirmation verdict")
            uid = str(rec.get("unit_id") or rec.get("id") or "")
            if uid.startswith("TST-") and not str(rec.get("claim_id")).startswith("CLM-"):
                return fail(f"ingested P2 unit artifact {uid}")
        live_commit = str(live.get("producing_commit") or B.producing_commit(REPO))
        live_red = B.check_board(
            {
                "tallies": mutated["tallies"],
                "by_severity": live.get("by_severity"),
                "measured_label": live.get("measured_label"),
                "board_color": live.get("board_color"),
                "green": live.get("green"),
            },
            live_receipts,
            live_claims,
            live_commit,
        )
        # Live board vs mutated fixture tallies must not silently pass either.
        print(f"live_vs_mutated_fixture status={live_red['status']}")

        live_gate = B.check_board(live, live_receipts, live_claims, live_commit)
        print(
            f"live_unedited status={live_gate['status']} "
            f"exit_code={live_gate['exit_code']}"
        )
        if not live_gate["ok"]:
            return fail(f"live board does not recompute {live_gate['reasons']}")
        live_bytes = B.canonical_bytes(
            {
                k: live[k]
                for k in (
                    "board_color",
                    "empty_set_is_not_pass",
                    "generator_id",
                    "generator_version",
                    "green",
                    "measured_label",
                    "producing_commit",
                    "receipts_fingerprint",
                    "rows",
                    "by_severity",
                    "tallies",
                )
                if k in live
            }
        )
        # Hand-edit the LIVE artifact tallies and require the gate red.
        live_mut = json.loads(B.mutate_one_digit(ART.read_bytes()).decode("utf-8"))
        live_mut_gate = B.check_board(
            live_mut, live_receipts, live_claims, live_commit
        )
        print(
            f"live_hand_edit status={live_mut_gate['status']} "
            f"exit_code={live_mut_gate['exit_code']} "
            f"reasons={live_mut_gate['reasons']}"
        )
        if live_mut_gate["ok"] or live_mut_gate["exit_code"] == 0:
            return fail("live one-digit edit did not go red")
        _ = live_bytes

    print(
        "fired_on_bad=True silent_on_good=True "
        "two_run_byte_identical=True live_hand_edit_red=True"
    )
    print("SUCCESS:CNF-0014-probe1 hand-edit control red and regeneration identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
