#!/usr/bin/env python3
"""Probe 1: both-states enumerator control.

Inject a synthetic 12th candidate heading AND matrix column; agreed count
must rise to 12. Remove it; agreed count must return to 11. Mapping is
refused while the two enumerations disagree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import enumerator as E  # noqa: E402


def main() -> int:
    snap = E.snapshot()
    text = snap["candidates_text"]
    base_h = E.enumerate_headings(text)
    base_m = E.enumerate_matrix(text)
    base_n = len(base_h)
    agreed = E.agree(base_h, base_m)
    print(
        f"baseline headings={base_n} matrix={len(base_m)} "
        f"ids={E.ids_of(base_h)} agreed={agreed} kind={snap['candidates_kind']}"
    )
    if not agreed:
        print("FAILED:ARC-0001-probe1 baseline enumerations disagree")
        return 1
    if base_n != 11:
        print(f"FAILED:ARC-0001-probe1 baseline count {base_n} != 11")
        return 1

    injected = E.inject_synthetic_twelfth(text)
    inj_h = E.enumerate_headings(injected)
    inj_m = E.enumerate_matrix(injected)
    inj_ok = E.agree(inj_h, inj_m)
    print(
        f"injected headings={len(inj_h)} matrix={len(inj_m)} "
        f"ids={E.ids_of(inj_h)} agreed={inj_ok}"
    )
    if len(inj_h) != 12 or len(inj_m) != 12 or not inj_ok:
        print("FAILED:ARC-0001-probe1 inject did not raise agreed count to 12")
        return 1
    if "A12" not in E.ids_of(inj_h):
        print("FAILED:ARC-0001-probe1 A12 missing after inject")
        return 1

    # Disagreement control: heading-only inject must refuse mapping.
    heading_only = (
        text[: E.SECTION3_RE.search(text).start()]
        + "## A12 (heading-only-disagreement)\n\n"
        + text[E.SECTION3_RE.search(text).start() :]
    )
    d_h = E.enumerate_headings(heading_only)
    d_m = E.enumerate_matrix(heading_only)
    disagree = not E.agree(d_h, d_m)
    print(
        f"heading-only headings={len(d_h)} matrix={len(d_m)} disagree={disagree}"
    )
    if not disagree:
        print("FAILED:ARC-0001-probe1 heading-only inject still agreed")
        return 1

    restored_h = E.enumerate_headings(text)
    restored_m = E.enumerate_matrix(text)
    restored_ok = E.agree(restored_h, restored_m) and len(restored_h) == 11
    print(
        f"restored headings={len(restored_h)} matrix={len(restored_m)} "
        f"agreed={restored_ok}"
    )
    if not restored_ok:
        print("FAILED:ARC-0001-probe1 restore did not return to 11")
        return 1

    payload = {
        "baseline": 11,
        "injected": 12,
        "restored": 11,
        "heading_only_disagrees": True,
        "kind": snap["candidates_kind"],
        "path": snap["candidates_path"],
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:ARC-0001-probe1 both-states enumerator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
