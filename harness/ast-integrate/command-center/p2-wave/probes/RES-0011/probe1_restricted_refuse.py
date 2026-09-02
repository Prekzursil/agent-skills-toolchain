#!/usr/bin/env python3
"""Probe 1: restricted fixture subagent must refuse the forbidden Bash call.

Signal 1: spawn the restricted definition and observe REFUSED.
Signal 2 (different data field): the markdown body mentions Bash, but the
tools: allowlist does not — mention must not grant the tool.
Both-states: a temp copy with tools including Bash must ALLOW the same call.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from spawn import spawn_agent_forbidden_call, write_transcript  # noqa: E402

ART = REPO / "command-center/research/RES-0011.json"
RESTRICTED = HERE / "fixtures/restricted.md"
SENTINEL = (
    "SUCCESS:RES-0011 in the receipt AND a transcript showing the forbidden "
    "call refused for the restricted agent and allowed for the unrestricted one"
)


def main() -> int:
    event = spawn_agent_forbidden_call(RESTRICTED)
    write_transcript("restricted.json", event)
    if event["decision"] != "REFUSED":
        print("FAILED:RES-0011-probe1 restricted did not refuse", event)
        return 1
    if event["reason"] != "not-in-resolved-tool-set":
        print("FAILED:RES-0011-probe1 unexpected reason", event["reason"])
        return 1
    if "Bash" in (event.get("resolved_tools") or []):
        print("FAILED:RES-0011-probe1 Bash leaked into resolved set")
        return 1
    if not event.get("body_mentions_bash"):
        print("FAILED:RES-0011-probe1 mention control missing from fixture body")
        return 1

    mutant_text = RESTRICTED.read_text(encoding="utf-8").replace(
        "tools: Read, Grep, Glob",
        "tools: Read, Grep, Glob, Bash",
    )
    with tempfile.TemporaryDirectory(prefix="res0011-p1-") as tmp:
        mutant = Path(tmp) / "restricted-with-bash.md"
        mutant.write_text(mutant_text, encoding="utf-8")
        allowed = spawn_agent_forbidden_call(mutant)
    if allowed["decision"] != "ALLOWED":
        print("FAILED:RES-0011-probe1 both-states mutant did not allow", allowed)
        return 1
    if not (allowed.get("execution") or {}).get("stdout"):
        print("FAILED:RES-0011-probe1 mutant allow had no stdout")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0011-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0011-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:RES-0011-probe1 self-declared", doc.get("state"))
        return 1
    tr = ((doc.get("transcripts") or {}).get("restricted") or {})
    if tr.get("decision") != "REFUSED":
        print("FAILED:RES-0011-probe1 artifact transcript not REFUSED", tr)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-restricted-refuse",
                "unit_id": "RES-0011",
                "restricted_decision": event["decision"],
                "reason": event["reason"],
                "mention_did_not_grant": True,
                "mutant_with_bash_allowed": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0011-probe1 restricted refuse and mention control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
