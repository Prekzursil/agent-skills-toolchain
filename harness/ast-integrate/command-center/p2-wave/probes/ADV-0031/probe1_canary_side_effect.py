#!/usr/bin/env python3
"""Probe 1: canary side-effect oracle for workflow-parameter injection.

Drive each adapter with the corpus. A canary file is the injected fragment's
side effect. Stdout is not consulted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

UNIT = "ADV-0031"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = H.run_canary_campaign()
    sys.stdout.write(H.dump_json(live))
    c = live["controls"]
    if not c["benign_no_canary_any_adapter"]:
        return fail("benign parameter created a canary; instrumentation is noisy")
    if not c["benign_launcher_argv_match"]:
        return fail("benign parameter did not round-trip launcher argv")
    if not c["semicolon_string_unquoted_canary"]:
        return fail("planted string-command adapter did not fire canary (detector silent)")
    if not c["apostrophe_quoted_canary"]:
        return fail("apostrophe did not break planted single-quote wrapping")
    print(
        f"SUCCESS:{UNIT}-probe1 canary oracle planted-red="
        f"{c['semicolon_string_unquoted_canary']} argv-semicolon-canary="
        f"{c['semicolon_launcher_no_canary']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
