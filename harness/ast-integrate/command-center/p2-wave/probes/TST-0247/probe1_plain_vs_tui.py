#!/usr/bin/env python3
"""Probe 1: field-level set comparison of --plain vs TUI panes.

Two independent signals from live CLI stdout (not an internal dict dump):
  (a) field set parsed from --plain output
  (b) field set parsed from TUI pane output after CSI strip

PASS requires the sets equal. Raw bytes must NOT be equal (TUI uses cursor
addressing; a visual/raw comparator is the wrong detector).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.hud.cockpit import (  # noqa: E402
    FIELD_NAMES,
    has_cursor_addressing,
    parse_plain_fields,
    parse_tui_fields,
)

UID = "TST-0247"
PAYLOAD = HERE / "fixtures" / "payload.json"
COCKPIT = REPO / "tools" / "hud" / "cockpit.py"


def run_cockpit(extra: list[str]) -> tuple[int, str, str]:
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
    return proc.returncode, proc.stdout, proc.stderr


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    print(json.dumps(payload, sort_keys=True))
    print(msg)
    return 1


def main() -> int:
    rc_tui, tui, err_tui = run_cockpit([])
    rc_plain, plain, err_plain = run_cockpit(["--plain"])
    doc: dict = {
        "unit_id": UID,
        "probe": "probe1-plain-vs-tui-field-set",
        "pass": False,
        "tui_exit": rc_tui,
        "plain_exit": rc_plain,
        "tui_stderr_empty": not err_tui.strip(),
        "plain_stderr_empty": not err_plain.strip(),
        "detector": "mechanical field-set equality of parsed stdout",
        "not_a_detector": "visual impression or raw-byte equality",
    }
    if rc_tui != 0 or rc_plain != 0:
        return fail(doc, f"FAILED:{UID}-probe1 cockpit exit tui={rc_tui} plain={rc_plain}")

    try:
        plain_fields = parse_plain_fields(plain)
        tui_fields = parse_tui_fields(tui)
    except ValueError as exc:
        doc["parse_error"] = str(exc)
        return fail(doc, f"FAILED:{UID}-probe1 parse: {exc}")

    plain_set = set(plain_fields)
    tui_set = set(tui_fields)
    expected = set(FIELD_NAMES)
    raw_equal = tui == plain
    values_equal = plain_fields == tui_fields
    tui_has_cup = has_cursor_addressing(tui)
    doc.update(
        {
            "plain_fields": dict(sorted(plain_fields.items())),
            "tui_fields": dict(sorted(tui_fields.items())),
            "plain_set": sorted(plain_set),
            "tui_set": sorted(tui_set),
            "expected_fields": list(FIELD_NAMES),
            "sets_equal": plain_set == tui_set == expected,
            "values_equal": values_equal,
            "raw_bytes_equal": raw_equal,
            "tui_has_cursor_addressing": tui_has_cup,
            "plain_bytes": len(plain.encode("utf-8")),
            "tui_bytes": len(tui.encode("utf-8")),
            "independent_signals": {
                "a_plain_field_set": sorted(plain_set),
                "b_tui_pane_field_set": sorted(tui_set),
            },
        }
    )
    if not tui_has_cup:
        return fail(doc, f"FAILED:{UID}-probe1 TUI stdout has no cursor addressing")
    if raw_equal:
        return fail(doc, f"FAILED:{UID}-probe1 raw TUI equals plain; comparison is not field-level")
    if plain_set != tui_set:
        return fail(
            doc,
            f"FAILED:{UID}-probe1 field-set mismatch "
            f"only_plain={sorted(plain_set - tui_set)} "
            f"only_tui={sorted(tui_set - plain_set)}",
        )
    if plain_set != expected:
        return fail(doc, f"FAILED:{UID}-probe1 missing fields {sorted(expected - plain_set)}")
    if not values_equal:
        return fail(doc, f"FAILED:{UID}-probe1 field values differ between plain and TUI")

    doc["pass"] = True
    print(json.dumps(doc, sort_keys=True))
    print(
        f"plain_set={sorted(plain_set)} tui_set={sorted(tui_set)} "
        f"raw_equal={raw_equal} values_equal={values_equal}"
    )
    print(f"SUCCESS:{UID}-probe1 field sets equal; raw bytes differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
