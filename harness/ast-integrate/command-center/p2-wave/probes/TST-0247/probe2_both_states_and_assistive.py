#!/usr/bin/env python3
"""Probe 2: both-states hide-field control + assistive CSI check.

Independent reviewer (does not call the author's parse_plain_fields /
parse_tui_fields): a second regex over CSI-stripped stdout.

Tests required:
  * both-states: hiding a field from the TUI shows up as a set difference
  * assistive: --plain is line-oriented with no cursor-addressing escapes

A visual comparator (both outputs non-empty) stays silent on the hidden-field
state; the mechanical set comparator fires. That is the detector control.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.hud.cockpit import (  # noqa: E402
    CSI_ANY,
    has_any_csi,
    has_cursor_addressing,
    is_line_oriented_plain,
)

UID = "TST-0247"
HIDDEN = "model"
PAYLOAD = HERE / "fixtures" / "payload.json"
COCKPIT = REPO / "tools" / "hud" / "cockpit.py"
REVIEWER_ID = "TST-0247-probe2-both-states-and-assistive"
REVIEWER_FIELD_RE = re.compile(r"(?m)^([a-z_]+): (.*)$")


def run_cockpit(extra: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(COCKPIT),
            "--payload",
            str(PAYLOAD),
            *extra,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc.returncode, proc.stdout


def reviewer_fields(text: str) -> set[str]:
    """Fresh-context parser: CSI strip then regex; does not import parse_*."""
    stripped = CSI_ANY.sub("", text)
    return {match.group(1) for match in REVIEWER_FIELD_RE.finditer(stripped)}


def visual_nonempty(a: str, b: str) -> bool:
    """Wrong detector: visual impression that both surfaces produced output."""
    return bool(a.strip()) and bool(b.strip())


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    print(json.dumps(payload, sort_keys=True))
    print(msg)
    return 1


def main() -> int:
    rc_plain, plain = run_cockpit(["--plain"])
    rc_tui, tui = run_cockpit([])
    rc_hid, tui_hidden = run_cockpit(["--hide-field", HIDDEN, "--hide-from", "tui"])
    doc: dict = {
        "unit_id": UID,
        "probe": "probe2-both-states-and-assistive",
        "pass": False,
        "reviewer_id": REVIEWER_ID,
        "starts_from": "tests (named probes), not author summary",
        "hidden_field": HIDDEN,
        "exits": {"plain": rc_plain, "tui": rc_tui, "tui_hidden": rc_hid},
    }
    if rc_plain != 0 or rc_tui != 0 or rc_hid != 0:
        return fail(doc, f"FAILED:{UID}-probe2 cockpit exit {doc['exits']}")

    plain_set = reviewer_fields(plain)
    tui_set = reviewer_fields(tui)
    hidden_set = reviewer_fields(tui_hidden)
    diff = sorted(plain_set - hidden_set)
    both_states_fires = hidden_set == (tui_set - {HIDDEN}) and HIDDEN in plain_set
    visual_misses_hide = visual_nonempty(plain, tui_hidden)
    assistive = is_line_oriented_plain(plain) and not has_cursor_addressing(plain)
    tui_is_addressed = has_cursor_addressing(tui) and has_cursor_addressing(tui_hidden)
    full_equal = plain_set == tui_set and HIDDEN in tui_set
    no_csi_plain = not has_any_csi(plain)

    doc.update(
        {
            "independent_signals": {
                "a_plain_field_set": sorted(plain_set),
                "b_tui_pane_field_set": sorted(tui_set),
            },
            "tui_hidden_set": sorted(hidden_set),
            "set_difference": diff,
            "both_states_fires": both_states_fires,
            "full_sets_equal": full_equal,
            "assistive_line_oriented_no_csi": assistive and no_csi_plain,
            "plain_has_cursor_addressing": has_cursor_addressing(plain),
            "plain_has_any_csi": has_any_csi(plain),
            "tui_has_cursor_addressing": tui_is_addressed,
            "visual_comparator_misses_hidden_field": visual_misses_hide,
            "mechanical_set_comparator_catches_hidden_field": both_states_fires,
            "reviewer_used_author_parse_functions": False,
        }
    )

    if not tui_is_addressed:
        return fail(doc, f"FAILED:{UID}-probe2 TUI lacks cursor addressing")
    if not assistive or not no_csi_plain:
        return fail(doc, f"FAILED:{UID}-probe2 plain is not line-oriented CSI-free")
    if not full_equal:
        return fail(doc, f"FAILED:{UID}-probe2 reviewer full sets unequal")
    if not both_states_fires or diff != [HIDDEN]:
        return fail(
            doc,
            f"FAILED:{UID}-probe2 hide-field did not produce set difference "
            f"{HIDDEN!r}: diff={diff} hidden_set={sorted(hidden_set)}",
        )
    if not visual_misses_hide:
        return fail(doc, f"FAILED:{UID}-probe2 visual comparator did not stay silent")

    doc["pass"] = True
    print(json.dumps(doc, sort_keys=True))
    print(
        f"hide={HIDDEN} diff={diff} assistive={assistive} "
        f"visual_misses={visual_misses_hide} mechanical_fires={both_states_fires}"
    )
    print(f"SUCCESS:{UID}-probe2 both-states set difference and assistive CSI-free plain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
