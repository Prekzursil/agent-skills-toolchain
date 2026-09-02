#!/usr/bin/env python3
"""Probe 2: live exit-2 block, additionalContext inject, timeout; overclaim mutants.

Mechanically different from probe 1: does not re-hash every event payload.
Signal pairs:
  block: returncode==2 AND stderr marker; interpreter says PreToolUse blocks
         while SessionStart does not.
  inject: stdout JSON additionalContext AND envelope hookSpecificOutput.
  timeout: timed_out True AND elapsed < sleep.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import lib as L  # noqa: E402
from constants import BLOCK_STDERR, INJECT_MARKER, OUTPUT_REL, SENTINEL, UNIT_ID  # noqa: E402

ART = L.REPO / OUTPUT_REL
EXIT2 = HERE / "hooks" / "exit2.py"
INJECT = HERE / "hooks" / "inject.py"
SLEEP = HERE / "hooks" / "sleep.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    errs = C.validate_artifact(doc)
    if errs:
        return fail("; ".join(errs[:12]))

    cli_text, _sdk = L.load_docs()
    table = L.parse_exit2_table(cli_text)
    pre = L.run_hook(EXIT2, L.make_payload("PreToolUse"), timeout_s=8)
    start = L.run_hook(EXIT2, L.make_payload("SessionStart"), timeout_s=8)
    inj = L.run_hook(INJECT, L.make_payload("PostToolUse"), timeout_s=8)
    slow = L.run_hook(SLEEP, L.make_payload("PreToolUse"), timeout_s=0.6)

    pre_i = L.interpret_exit2("PreToolUse", table, pre["returncode"])
    start_i = L.interpret_exit2("SessionStart", table, start["returncode"])
    if pre["returncode"] != 2 or BLOCK_STDERR not in pre["stderr"]:
        return fail("live-block-pretooluse")
    if not pre_i["blocked"]:
        return fail("interpreter-pretooluse-not-blocked")
    if start["returncode"] != 2:
        return fail("live-exit2-sessionstart")
    if start_i["blocked"]:
        return fail("interpreter-sessionstart-blocked")
    if inj["returncode"] != 0 or INJECT_MARKER not in inj["stdout"]:
        return fail("live-inject")
    if "hookSpecificOutput" not in inj["stdout"]:
        return fail("live-inject-envelope")
    if not slow["timed_out"] or slow["elapsed_s"] >= 5:
        return fail(f"live-timeout timed_out={slow['timed_out']} elapsed={slow['elapsed_s']}")

    art_block = (doc.get("controls") or {}).get("block") or {}
    art_inj = (doc.get("controls") or {}).get("inject") or {}
    art_to = (doc.get("controls") or {}).get("timeout") or {}
    if int(art_block.get("returncode") or 0) != 2:
        return fail("artifact-block-rc")
    if art_inj.get("returncode") not in (0, "0"):
        return fail("artifact-inject-rc")
    if art_to.get("timed_out") is not True:
        return fail("artifact-timeout-flag")

    timeout_errs = C.validate_artifact(C.mutant_drop_timeout(doc))
    overclaim_errs = C.validate_artifact(C.mutant_live_client_overclaim(doc))
    if not timeout_errs:
        return fail("drop-timeout-mutant-silent")
    if not overclaim_errs:
        return fail("live-client-overclaim-mutant-silent")

    print(
        json.dumps(
            {
                "probe": "probe2-block-inject-timeout",
                "unit_id": UNIT_ID,
                "pre_tool_use": pre_i,
                "session_start": start_i,
                "inject_returncode": inj["returncode"],
                "timeout_elapsed_s": slow["elapsed_s"],
                "timeout_timed_out": slow["timed_out"],
                "drop_timeout_errors": timeout_errs[:8],
                "overclaim_errors": overclaim_errs[:8],
                "pass": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0009-probe2 block/inject/timeout and overclaim mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
