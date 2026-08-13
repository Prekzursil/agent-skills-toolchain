#!/usr/bin/env python3
r"""B4: does per-edit-check's `return 2` actually PREVENT a write?

Round 5 read the vendor doc, found that PostToolUse runs AFTER the tool and that exit 2 is
IGNORED there, and correctly declined to call the finding CONFIRMED because it had not run the
experiment. It named the settling experiment instead. This is that experiment, split into the
two halves it needs.

  HALF A (here): does the live hook's detector DISCRIMINATE, and does it return 2?
      A1 a credential-shaped line with no placeholder marker  -> expect rc 2 + a BLOCKED message
      A2 the same shape WITH a placeholder marker adjacent    -> expect rc 0 (not a blanket 2)
      A3 a file with no credential shape at all               -> expect rc 0
      Without A2/A3 an rc of 2 could just mean "this hook always returns 2", which would make
      half B unreadable.

  HALF B (the tool call, run by the agent, recorded in the artifact): write a
      credential-shaped placeholder through the real Write tool and check the file exists
      afterwards. If it does, exit 2 did not prevent the write.

NOTHING REAL IS WRITTEN. Every literal is assembled at runtime from fragments so this source
file contains no credential-shaped string, and every temp file is deleted. The fixture uses the
AWS access-key-ID SHAPE because it is the cheapest to synthesise, not because it is a key.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

LIVE_HOOK = Path.home() / ".claude" / "hooks" / "per-edit-check" / "check.py"
OUT = Path(__file__).resolve().parent / "B4-POSTTOOL-BLOCK.json"

# Assembled at runtime: the literal never appears in this file, so this probe cannot itself trip
# the very gate it is measuring (and cannot be committed as a credential-shaped string).
_SHAPE = "AK" + "IA" + "".join(chr(ord("A") + i % 26) for i in range(16))


def run_case(name: str, body: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "fixture.py"
        target.write_text(body, encoding="utf-8")
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target)},
            "hook_event_name": "PostToolUse",
        }
        env = dict(os.environ)
        env.pop("PER_EDIT_SECRETS", None)
        env.pop("PER_EDIT_CHECK", None)
        proc = subprocess.run(
            [sys.executable, str(LIVE_HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        survived = target.is_file()
    return {
        "case": name,
        "returncode": proc.returncode,
        "blocked_message": "BLOCKED" in proc.stderr,
        "file_still_on_disk_after_hook": survived,
        "stderr_head": proc.stderr.strip().splitlines()[:1],
    }


def main() -> int:
    if not LIVE_HOOK.is_file():
        print(f"FAILED:b4-posttool live hook not found at {LIVE_HOOK}")
        return 2

    cases = [
        run_case("A1_credential_shape_no_marker", f'KEY = "{_SHAPE}"\n'),
        run_case("A2_same_shape_with_placeholder_marker", f'KEY = "{_SHAPE}"  # EXAMPLE\n'),
        run_case("A3_no_credential_shape", 'KEY = "nothing to see"\n'),
    ]
    by_name = {c["case"]: c for c in cases}

    controls = {
        "A1_fires_rc2": by_name["A1_credential_shape_no_marker"]["returncode"] == 2,
        "A1_names_the_block": by_name["A1_credential_shape_no_marker"]["blocked_message"],
        "A2_placeholder_exempt_rc0": by_name["A2_same_shape_with_placeholder_marker"]["returncode"] == 0,
        "A3_clean_rc0": by_name["A3_no_credential_shape"]["returncode"] == 0,
    }
    controls["detector_discriminates"] = (
        controls["A1_fires_rc2"] and controls["A2_placeholder_exempt_rc0"] and controls["A3_clean_rc0"]
    )
    # The load-bearing observation: the hook ran to completion and the file it objected to is
    # STILL THERE. The hook has no power to unwrite it -- at PostToolUse the tool already ran.
    controls["A1_file_survived_the_block"] = by_name["A1_credential_shape_no_marker"][
        "file_still_on_disk_after_hook"
    ]

    result = {"live_hook": str(LIVE_HOOK), "controls": controls, "cases": cases}
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    if not controls["detector_discriminates"]:
        print("FAILED:b4-posttool detector does not discriminate -- rc 2 proves nothing")
        return 1
    print("SUCCESS:b4-posttool detector discriminates across all three states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
