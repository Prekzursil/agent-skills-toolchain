#!/usr/bin/env python3
"""Probe 2: unrestricted twin must succeed at the same Bash call.

Mechanically different from probe 1: different definition (tools omitted),
and a second field (command allowed-tools) showing the command-side grant
is advisory. Also settles model resolution order on a third data field.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import resolve_model  # noqa: E402
from spawn import (  # noqa: E402
    spawn_agent_forbidden_call,
    spawn_command_forbidden_call,
    write_transcript,
)

ART = REPO / "command-center/research/RES-0011.json"
UNRESTRICTED = HERE / "fixtures/unrestricted.md"
CMD_ADV = HERE / "fixtures/command-advisory.md"
CMD_DENY = HERE / "fixtures/command-disallow.md"
SENTINEL = (
    "SUCCESS:RES-0011 in the receipt AND a transcript showing the forbidden "
    "call refused for the restricted agent and allowed for the unrestricted one"
)


def _model_cases() -> list[tuple[str, dict]]:
    fm_sonnet = {"model": "sonnet"}
    fm_inherit = {"model": "inherit"}
    return [
        (
            "env-wins",
            resolve_model(
                fm_sonnet,
                env_value="opus",
                invocation_model="haiku",
                parent_model="fable",
            ),
        ),
        (
            "invocation-wins",
            resolve_model(
                fm_sonnet,
                env_value="inherit",
                invocation_model="haiku",
                parent_model="fable",
            ),
        ),
        (
            "frontmatter-wins",
            resolve_model(
                fm_sonnet,
                env_value=None,
                invocation_model="inherit",
                parent_model="fable",
            ),
        ),
        (
            "parent-wins",
            resolve_model(
                fm_inherit,
                env_value=None,
                invocation_model=None,
                parent_model="fable",
            ),
        ),
    ]


def main() -> int:
    os.environ.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
    event = spawn_agent_forbidden_call(UNRESTRICTED)
    write_transcript("unrestricted.json", event)
    if event["decision"] != "ALLOWED":
        print("FAILED:RES-0011-probe2 unrestricted did not allow", event)
        return 1
    exe = event.get("execution") or {}
    if exe.get("returncode") != 0 or "RES-0011-FORBIDDEN-CALL" not in (
        exe.get("stdout") or ""
    ):
        print("FAILED:RES-0011-probe2 unrestricted subprocess", exe)
        return 1
    if "Bash" not in (event.get("resolved_tools") or []):
        print("FAILED:RES-0011-probe2 Bash missing from inherited set")
        return 1

    advisory = spawn_command_forbidden_call(CMD_ADV)
    write_transcript("command-advisory.json", advisory)
    if advisory["decision"] != "ALLOWED":
        print("FAILED:RES-0011-probe2 allowed-tools incorrectly restricted", advisory)
        return 1
    if advisory.get("in_preapproved") is True:
        print("FAILED:RES-0011-probe2 Bash was preapproved; advisory control invalid")
        return 1

    denied = spawn_command_forbidden_call(CMD_DENY)
    write_transcript("command-disallow.json", denied)
    if denied["decision"] != "REFUSED":
        print("FAILED:RES-0011-probe2 disallowed-tools did not refuse", denied)
        return 1

    want = {
        "env-wins": ("opus", "env"),
        "invocation-wins": ("haiku", "invocation"),
        "frontmatter-wins": ("sonnet", "frontmatter"),
        "parent-wins": ("fable", "parent"),
    }
    for name, got in _model_cases():
        exp_model, exp_src = want[name]
        if got.get("model") != exp_model or got.get("source") != exp_src:
            print(f"FAILED:RES-0011-probe2 model {name} got={got} want={want[name]}")
            return 1

    if not ART.is_file():
        print("FAILED:RES-0011-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0011-probe2 sentinel-absent")
        return 1
    tr = ((doc.get("transcripts") or {}).get("unrestricted") or {})
    if tr.get("decision") != "ALLOWED":
        print("FAILED:RES-0011-probe2 artifact transcript not ALLOWED", tr)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-unrestricted-allow",
                "unit_id": "RES-0011",
                "unrestricted_decision": event["decision"],
                "command_allowed_tools_advisory": True,
                "command_disallowed_tools_refused": True,
                "model_order": {k: list(v) for k, v in want.items()},
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0011-probe2 unrestricted allow and command advisory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
