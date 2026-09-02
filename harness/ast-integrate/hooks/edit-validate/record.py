#!/usr/bin/env python3
"""PostToolUse(Edit|Write|MultiEdit): record the edited file path for Stop-time
validation by validate-stop.py.

This is the loop-proof replacement for the old per-Edit async-validate design:
it does NO validation and NEVER wakes Claude — it just appends the edited path
to a per-session list. A workflow doing thousands of edits appends thousands of
lines (cheap) but triggers ZERO wakes; validation happens once at turn end.

FAIL-OPEN: any error -> exit 0, silent.
"""

import json
import os
import sys
import tempfile


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
            return 0
        fp = (data.get("tool_input") or {}).get("file_path")
        if not fp:
            return 0
        sid = (
            str(data.get("session_id") or "default")
            .replace("/", "_")
            .replace("\\", "_")
        )
        d = os.path.join(tempfile.gettempdir(), "edit-validate")
        os.makedirs(d, exist_ok=True)
        with open(
            os.path.join(d, f"{sid}.edits"), "a", encoding="utf-8", errors="replace"
        ) as f:
            f.write(fp + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
