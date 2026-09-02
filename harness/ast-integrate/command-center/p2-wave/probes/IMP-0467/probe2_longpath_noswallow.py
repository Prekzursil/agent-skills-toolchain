#!/usr/bin/env python3
"""Probe 2: long path above 260 characters, and the no-silent-zero control.

Mechanically different from probe 1: creates a nested path whose character
length exceeds 260, round-trips a marker file through the library, and
compares the crash-swallowing enumerator (returns 0 on reserved names) with
walk_tree on both the ordinary tree and the reserved-name tree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "lib"))

import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0467.json"
SENTINEL = "SENTINEL:IMP-0467:PATH-LIBRARY-WINDOWS-SAFE"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0467-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or doc.get("status") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    live = S.run_evidence()
    ans = S.answers(live)
    lp = live["long_path"]
    if lp["char_len"] <= 260:
        return fail(f"long path only {lp['char_len']} chars")
    if not lp["marker_found"]:
        return fail("library walk missed the long-path marker")
    if not lp["marker_body_matches"]:
        return fail("long-path marker body mismatch (truncation?)")
    if not lp["needs_prefix"]:
        return fail("library did not flag the long path for \\\\?\\ prefix")
    rec_len = (doc.get("answer") or {}).get("long_path_chars")
    if rec_len != lp["char_len"]:
        return fail(f"receipt long_path_chars {rec_len} != live {lp['char_len']}")

    sw = live["swallow_control"]
    if not sw["swallow_zeros_reserved_tree"]:
        return fail(
            f"swallowing enumerator returned {sw['reserved_tree_swallow_count']} "
            "on reserved tree; expected 0"
        )
    if not sw["library_nonzero_reserved_tree"]:
        return fail("library walk returned zero files on reserved tree")
    if not sw["both_states_ordinary_match"]:
        return fail(
            "swallow control is not silent on the ordinary tree: "
            f"swallow={sw['ordinary_tree_swallow_count']} "
            f"library={sw['ordinary_tree_library_entries']}"
        )
    rec_sw = (doc.get("answer") or {}).get("swallow_returns_zero_on_reserved")
    if rec_sw is not True:
        return fail("receipt did not record swallow-zero on reserved tree")
    rec_lib = (doc.get("answer") or {}).get(
        "library_does_not_return_zero_on_reserved"
    )
    if rec_lib is not True:
        return fail("receipt did not record library non-zero on reserved tree")
    if ans["delta"] != 1:
        return fail("cross-check: reserved delta is not 1")

    out = {
        "probe": "probe2-longpath-noswallow",
        "unit_id": "IMP-0467",
        "long_path_chars": lp["char_len"],
        "marker_found": True,
        "marker_round_trip": True,
        "extended_prefix_flagged": True,
        "swallow_zero_on_reserved": True,
        "library_nonzero_on_reserved": True,
        "swallow_matches_library_on_ordinary": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"long_path_chars={lp['char_len']} marker_found=True "
        f"swallow_reserved={sw['reserved_tree_swallow_count']} "
        f"library_reserved_files={sw['reserved_tree_library_files']}"
    )
    print("SUCCESS:IMP-0467-probe2 long-path round-trip and no-silent-zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
