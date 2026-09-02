#!/usr/bin/env python3
"""Named probe 1: resume re-executes only incomplete units, four checkpoints.

Live SIGKILL at after:u1, mid:u2, after:u3, mid:u4. After each kill, resume
must dispatch exactly the incomplete set and must not re-dispatch a unit
whose receipt still passes the oracle. Mid-unit leftovers are unparseable
partial files, not SUCCESS.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import plan as P  # noqa: E402
from scenario import run_honest_matrix  # noqa: E402

ART = REPO / "command-center/receipts/TST-0096.json"
SENTINEL = "SUCCESS:TST-0096"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0096-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0096-probe1 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0096-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0096-probe1 self-declared:{st}")
        return 1
    if doc.get("unit_id") != "TST-0096":
        print("FAILED:TST-0096-probe1 unit_id", doc.get("unit_id"))
        return 1
    cases = doc.get("cases") or []
    if len(cases) < 4:
        print("FAILED:TST-0096-probe1 receipt has fewer than 4 checkpoint cases")
        return 1
    for case in cases:
        if not case.get("only_incomplete"):
            print("FAILED:TST-0096-probe1 receipt case not only-incomplete", case.get("id"))
            return 1
    return 0


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="tst0096-p1-") as tmp:
        matrix = run_honest_matrix(Path(tmp))

    print(json.dumps({
        "probe": "probe1-resume-incomplete",
        "unit_id": "TST-0096",
        "checkpoint_count": matrix.get("checkpoint_count"),
        "four_checkpoints": matrix.get("four_checkpoints"),
        "all_only_incomplete": matrix.get("all_only_incomplete"),
        "all_hashes_equal": matrix.get("all_hashes_equal"),
        "clean_hash": (matrix.get("clean") or {}).get("artifact_set_hash"),
        "cases": [
            {
                "kill_at": c.get("kill_at"),
                "kill_rc": c.get("kill_rc"),
                "reexecuted": c.get("reexecuted"),
                "expected_incomplete": c.get("expected_incomplete"),
                "only_incomplete": c.get("only_incomplete"),
                "mid_partial_rejected": c.get("mid_partial_rejected"),
                "hash_equal": (c.get("hash_comparison") or {}).get("equal"),
                "pass": c.get("pass"),
            }
            for c in (matrix.get("cases") or [])
        ],
        "pass": bool(matrix.get("pass")),
    }, sort_keys=True))

    if not matrix.get("pass"):
        print("FAILED:TST-0096-probe1 honest kill-resume matrix")
        return 1
    if not matrix.get("four_checkpoints"):
        print("FAILED:TST-0096-probe1 fewer than four live checkpoints")
        return 1
    if not matrix.get("all_only_incomplete"):
        print("FAILED:TST-0096-probe1 a checkpoint re-executed a complete unit")
        return 1
    for case in matrix.get("cases") or []:
        if case.get("kill_rc") == 0:
            print("FAILED:TST-0096-probe1 kill did not fire", case.get("kill_at"))
            return 1
        if set(case.get("reexecuted") or []) != set(case.get("expected_incomplete") or []):
            print("FAILED:TST-0096-probe1 reexecuted != incomplete", case.get("kill_at"))
            return 1
        if set(case.get("reexecuted") or []) & set(case.get("expected_complete") or []):
            print("FAILED:TST-0096-probe1 completed unit re-dispatched", case.get("kill_at"))
            return 1
        if str(case.get("kill_at") or "").startswith("mid:") and not case.get("mid_partial_rejected"):
            print("FAILED:TST-0096-probe1 mid-unit partial accepted as complete")
            return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    live_hash = (matrix.get("clean") or {}).get("artifact_set_hash")
    rec_hash = (art.get("hash_comparison") or {}).get("clean_artifact_set_hash")
    if rec_hash and live_hash and rec_hash != live_hash:
        print(
            f"FAILED:TST-0096-probe1 clean hash drift receipt={rec_hash} live={live_hash}"
        )
        return 1
    print(
        "checkpoints=%s only_incomplete=%s hashes_equal=%s clean=%s"
        % (
            matrix.get("checkpoint_count"),
            matrix.get("all_only_incomplete"),
            matrix.get("all_hashes_equal"),
            live_hash,
        )
    )
    print("SUCCESS:TST-0096-probe1 resume re-executes only incomplete units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
