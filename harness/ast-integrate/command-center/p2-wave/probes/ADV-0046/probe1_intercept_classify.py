#!/usr/bin/env python3
"""Probe 1: intercept outbound requests and classify content by origin.

Mechanically: accepted HTTP POST + MCP stdio child capture + CLI argv
capture, then origin labels from planted public / program / owner markers.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0046-probe1 {msg}")
    return 1


def main() -> int:
    prompt = S.build_prompt(include_private=True)
    if S.PUBLIC_MARK not in prompt or S.PROGRAM_MARK not in prompt:
        return fail("constructed prompt missing public or program markers")
    if S.CANARY_ATTACHED not in prompt:
        return fail("constructed prompt missing attached owner canary")
    if S.CANARY_UNATTACHED in prompt:
        return fail("unattached canary leaked into constructed prompt")

    with tempfile.TemporaryDirectory(prefix="adv0046-p1-") as td:
        report = S.send_on_transports(prompt, Path(td))

    http = report["http"]
    mcp = report["mcp"]
    cli = report["cli"]
    clf = report["classification"]
    out = {
        "probe": "probe1-intercept-classify",
        "unit_id": "ADV-0046",
        "observation_method": (
            "ThreadingHTTPServer.bind(127.0.0.1:ephemeral) accepted-POST, "
            "MCP stdio child independently recorded stdin, CLI stub independently "
            "recorded argv. Localhost only; no vendor, no API keys."
        ),
        "http": {
            "hits": http["hits"],
            "connects": http["connects"],
            "bytes_sent": http["bytes_sent"],
        },
        "mcp": {
            "exit_code": mcp["exit_code"],
            "parent_matches_child": mcp["parent_matches_child"],
            "child_bytes": mcp["child_bytes"],
        },
        "cli": {
            "exit_code": cli["exit_code"],
            "parent_matches_child": cli["parent_matches_child"],
            "workspace": cli["workspace"],
        },
        "classification": clf,
        "census": S.census_live_tree(),
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    if http["hits"] < 1:
        return fail("HTTP observer accepted no POST")
    if http["connects"] < 1:
        return fail("socket.connect silent on HTTP send")
    if mcp["exit_code"] != 0 or not mcp["parent_matches_child"]:
        return fail("MCP stdio parent/child mismatch or nonzero exit")
    if cli["exit_code"] != 0 or not cli["parent_matches_child"]:
        return fail("CLI subprocess parent/child mismatch or nonzero exit")
    for origin in ("public_knowledge", "program_generated", "owner_private"):
        if origin not in clf["origins"]:
            return fail(f"origin {origin} missing from intercepted payload")
    if not clf["has_attached_canary"]:
        return fail("attached canary absent from intercepted payload")
    if clf["has_unattached_canary"]:
        return fail("unattached canary appeared on a transport")
    if S.OWNER_WORDS_MARK not in report["joined"]:
        return fail("owner words absent from intercepted payload")
    if S.OWNER_SOURCE_MARK not in report["joined"]:
        return fail("owner source absent from intercepted payload")
    if S.WORKTREE not in report["joined"]:
        return fail("repository path absent from intercepted payload")

    print(
        "origins="
        + ",".join(clf["origins"])
        + f" http_hits={http['hits']} mcp_match={mcp['parent_matches_child']}"
        + f" cli_match={cli['parent_matches_child']}"
    )
    print("SUCCESS:ADV-0046-probe1 intercept-classify three-origins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
