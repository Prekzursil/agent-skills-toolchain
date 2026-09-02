#!/usr/bin/env python3
"""Probe 2: transcript text is DATA; instruction-shaped spans are neutralized, never executed."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import INJECT_MARKER, INJECT_TEXT, materialize  # noqa: E402
from neutralize import REPLACEMENT, neutralize_events, neutralize_text  # noqa: E402

UNIT = "WFA-0020"
MARKER_PATH = HERE / "fixtures" / INJECT_MARKER


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def assert_no_exec_of_payload() -> None:
    text = (HERE / "neutralize.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    forbidden = {"eval", "exec", "compile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = None
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            # re.compile is fine; only bare eval/exec/compile names are forbidden.
            if isinstance(fn, ast.Name) and name in forbidden:
                raise SystemExit(f"neutralize.py calls forbidden {name}")
            if isinstance(fn, ast.Attribute) and name in {"system", "Popen"}:
                raise SystemExit(f"neutralize.py invokes process helper {name}")
    if "Never eval" not in text and "Never eval, exec" not in text:
        raise SystemExit("neutralize.py missing never-eval contract comment")


def follower_mutant(text: str, dest: Path) -> None:
    """Bad-state actor: treat transcript text as instructions and follow them."""
    if INJECT_MARKER in text or "ignore previous instructions" in text.lower():
        dest.write_text("pwned=1\n", encoding="utf-8")


def main() -> int:
    assert_no_exec_of_payload()
    if MARKER_PATH.exists():
        MARKER_PATH.unlink()

    clean_text, clean_hits = neutralize_text("ran stage plan then execute; no prompt injection")
    if clean_hits:
        return fail(f"clean text was neutralized {clean_hits}")
    if clean_text != "ran stage plan then execute; no prompt injection":
        return fail("clean text mutated")

    planted = materialize()
    inj_events = planted["transcripts"]["ag-inject-01"]
    cleaned, hits = neutralize_events(inj_events)
    if len(hits) < 1:
        return fail("injected instruction was not neutralized")
    blob = json.dumps(cleaned)
    if "Ignore previous instructions" in blob:
        return fail("raw ignore-previous span survived neutralization")
    if "rm -rf /" in blob:
        return fail("rm -rf span survived neutralization")
    if REPLACEMENT not in blob:
        return fail("replacement token missing from cleaned events")
    if MARKER_PATH.exists():
        return fail("neutralizer followed the write-EXECUTED_INSTRUCTION payload")

    # Bad state: a follower would create the marker. Honest path must not.
    follower_mutant(INJECT_TEXT, MARKER_PATH)
    if not MARKER_PATH.exists():
        return fail("follower mutant did not fire on injected text (control broken)")
    MARKER_PATH.unlink()
    neutralize_events(inj_events)
    if MARKER_PATH.exists():
        return fail("honest neutralize followed instructions after follower control")

    match_events = planted["transcripts"]["ag-match-01"]
    _cleaned_match, match_hits = neutralize_events(match_events)
    if match_hits:
        return fail(f"conforming transcript produced hits {match_hits}")

    payload = {
        "pass": True,
        "probe": "probe2-untrusted-transcript",
        "unit_id": UNIT,
        "clean_hits": len(clean_hits),
        "injected_hits": len(hits),
        "replacement_present": True,
        "marker_path": str(MARKER_PATH.relative_to(HERE.parents[3])),
        "marker_created_by_honest_path": False,
        "conforming_transcript_hits": len(match_hits),
        "both_states": {
            "conforming_silent": True,
            "injected_neutralized": True,
            "follower_mutant_writes_marker": True,
            "honest_path_does_not_write_marker": True,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0020-probe2 injected instruction neutralized; "
        "conforming transcript silent; marker file not written"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
