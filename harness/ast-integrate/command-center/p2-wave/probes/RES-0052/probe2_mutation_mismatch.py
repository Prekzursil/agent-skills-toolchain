#!/usr/bin/env python3
"""Probe 2: mutation reports mismatch; silent detector does not.

Known-good: unmutated install matches the lockfile.
Known-broken: one mutated file; compare_install.match is False.
Control: an always-match comparator stays green in both states.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/research/RES-0052.json"
SENTINEL = (
    "SUCCESS:RES-0052 in the receipt AND two installs whose per-file blob "
    "hashes match exactly, plus a demonstrated mismatch on mutation"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0052-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
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

    report = S.run_suite()
    mut = report["mutation"]
    print(
        f"before_match={mut['before_match']} "
        f"after_match={mut['after_match']} "
        f"mismatch_count={mut['after_mismatch_count']} "
        f"mutated_path={mut['mutated_path']}"
    )
    print(
        "silent_both_green="
        f"{mut['silent_detector_cannot_discriminate']} "
        "real_discriminates="
        f"{mut['real_detector_discriminates']}"
    )
    if mut["before_match"] is not True:
        return fail("known-good install did not match before mutation")
    if mut["after_match"] is not False:
        return fail("mutation did not produce a mismatch")
    if mut["after_mismatch_count"] < 1:
        return fail("mismatch_count < 1 after mutation")
    if not mut["demonstrated_mismatch_on_mutation"]:
        return fail("demonstrated_mismatch_on_mutation is false")
    if not mut["silent_detector_cannot_discriminate"]:
        return fail("silent-detector control did not stay green in both states")
    if not mut["real_detector_discriminates"]:
        return fail("real detector silent in both states")
    if not report["ok"]:
        return fail("suite ok=false")
    print("SUCCESS:RES-0052-probe2 mutation mismatch and silent-detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
