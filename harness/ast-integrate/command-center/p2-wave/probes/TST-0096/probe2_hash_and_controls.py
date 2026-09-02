#!/usr/bin/env python3
"""Named probe 2: resumed artifact-set hash equals the clean run.

Independent of probe1's workspace. Rehearses an uninterrupted run against
kill-then-resume at each of the four checkpoints, then plants two broken
resume modes (redispatch completed units; skip an incomplete mid-unit) and
requires both predicates to fire. Silent-on-good is the honest mid:u2 case.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_honest_matrix, run_negative_controls  # noqa: E402

ART = REPO / "command-center/receipts/TST-0096.json"
SENTINEL = "SUCCESS:TST-0096"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0096-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0096-probe2 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0096-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0096-probe2 self-declared:{st}")
        return 1
    hc = doc.get("hash_comparison") or {}
    if hc.get("all_resumed_equal_clean") is not True:
        print("FAILED:TST-0096-probe2 receipt did not claim hash equality")
        return 1
    ctrls = doc.get("negative_controls") or []
    if len(ctrls) < 2:
        print("FAILED:TST-0096-probe2 receipt missing negative controls")
        return 1
    return 0


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="tst0096-p2-") as tmp:
        base = Path(tmp)
        matrix = run_honest_matrix(base / "honest")
        clean_hash = (matrix.get("clean") or {}).get("artifact_set_hash") or ""
        controls = run_negative_controls(base / "ctrl", clean_hash)

    payload = {
        "probe": "probe2-hash-and-controls",
        "unit_id": "TST-0096",
        "clean_hash": clean_hash,
        "all_hashes_equal": matrix.get("all_hashes_equal"),
        "checkpoint_count": matrix.get("checkpoint_count"),
        "controls_pass": controls.get("pass"),
        "redispatch_fired": (controls.get("redispatch_complete") or {}).get("fired"),
        "skip_fired": (controls.get("skip_incomplete") or {}).get("fired"),
        "silent_on_good": (controls.get("honest_mid_u2") or {}).get("silent_on_good"),
        "pass": bool(matrix.get("pass") and controls.get("pass")),
    }
    print(json.dumps(payload, sort_keys=True))

    if not matrix.get("pass") or not matrix.get("all_hashes_equal"):
        print("FAILED:TST-0096-probe2 resumed hash != clean hash")
        return 1
    if not clean_hash:
        print("FAILED:TST-0096-probe2 empty clean hash")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    rec_hash = (art.get("hash_comparison") or {}).get("clean_artifact_set_hash")
    if rec_hash != clean_hash:
        print(
            f"FAILED:TST-0096-probe2 hash drift receipt={rec_hash} live={clean_hash}"
        )
        return 1
    red = controls.get("redispatch_complete") or {}
    skip = controls.get("skip_incomplete") or {}
    good = controls.get("honest_mid_u2") or {}
    if not red.get("fired"):
        print("FAILED:TST-0096-probe2 redispatch-complete control did not fire")
        return 1
    if not skip.get("fired"):
        print("FAILED:TST-0096-probe2 skip-incomplete control did not fire")
        return 1
    if not good.get("silent_on_good"):
        print("FAILED:TST-0096-probe2 honest resume was not silent-on-good")
        return 1
    if skip.get("hash_equal") is True:
        print("FAILED:TST-0096-probe2 skip-incomplete hash still matched clean")
        return 1
    print(
        "clean=%s hashes_equal=%s redispatch_fired=%s skip_fired=%s silent=%s"
        % (
            clean_hash,
            matrix.get("all_hashes_equal"),
            red.get("fired"),
            skip.get("fired"),
            good.get("silent_on_good"),
        )
    )
    print("SUCCESS:TST-0096-probe2 resumed artifact-set hash equals the clean run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
