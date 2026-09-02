#!/usr/bin/env python3
"""Probe 1: file:line beyond EOF is unresolved; command anchors re-execute."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from controls import (  # noqa: E402
    test_command_anchor_reexecutes,
    test_file_line_beyond_eof_is_unresolved,
)

REPO = HERE.parents[3]


def main() -> int:
    t_eof = test_file_line_beyond_eof_is_unresolved(REPO)
    t_cmd = test_command_anchor_reexecutes(REPO)
    payload = {
        "probe": "probe1-file-line-beyond-eof-and-command",
        "unit_id": "TST-0009",
        "pass": bool(t_eof["pass"] and t_cmd["pass"]),
        "test_file_line_beyond_eof_is_unresolved": t_eof["pass"],
        "test_command_anchor_reexecutes": t_cmd["pass"],
        "beyond_eof_reason": t_eof["beyond_eof"]["reason"],
        "beyond_eof_line_count": t_eof["beyond_eof"]["line_count"],
        "command_match_exit": t_cmd["match_exit_0"].get("observed_exit"),
        "command_mismatch_unresolved": t_cmd["mismatch"]["outcome"] == "unresolved",
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0009-probe1 file:line-beyond-eof or command-reexec")
        return 1
    print(
        "SUCCESS:TST-0009-probe1 beyond-eof is unresolved; "
        "command re-exec matches recorded exit"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
