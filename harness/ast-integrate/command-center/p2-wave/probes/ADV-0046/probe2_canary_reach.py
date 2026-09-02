#!/usr/bin/env python3
"""Probe 2: canary-in-private-artifact reach (mechanically different from probe 1).

Plant a distinctive string in a private artifact and search interceptor
bytes. Control: the same canary is detectable when deliberately sent once
on HTTP, MCP stdio, and CLI subprocess. Negative: an unattached canary
must stay off every transport. Both-states: attached vs omitted private body.
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
    print(f"FAILED:ADV-0046-probe2 {msg}")
    return 1


def _canaries(report: dict) -> dict[str, bool]:
    return {
        "http": S.CANARY_ATTACHED in (report["http"]["body"] or ""),
        "mcp": S.CANARY_ATTACHED in (report["mcp"]["stdin"] or ""),
        "cli": S.CANARY_ATTACHED in (report["cli"]["prompt"] or ""),
        "unattached": S.CANARY_UNATTACHED in report["joined"],
    }


def main() -> int:
    if not S.unattached_file_present():
        return fail("unattached canary fixture missing; negative control void")

    control = S.deliberate_canary_once()
    if not control["all_three"]:
        return fail(
            "control: deliberate canary not seen on all three transports "
            f"http={control['http_saw']} mcp={control['mcp_saw']} cli={control['cli_saw']}"
        )

    attached_prompt = S.build_prompt(include_private=True)
    omitted_prompt = S.build_prompt(include_private=False)
    if S.CANARY_ATTACHED not in attached_prompt:
        return fail("attached prompt missing planted canary")
    if S.CANARY_ATTACHED in omitted_prompt:
        return fail("omitted prompt still contains planted canary")
    if S.CANARY_UNATTACHED in attached_prompt or S.CANARY_UNATTACHED in omitted_prompt:
        return fail("unattached canary present in a constructed prompt")

    with tempfile.TemporaryDirectory(prefix="adv0046-p2-") as td:
        tmp = Path(td)
        on = S.send_on_transports(attached_prompt, tmp / "on")
        off = S.send_on_transports(omitted_prompt, tmp / "off")
        adapter = S.inprocess_adapter_egress(attached_prompt)

    on_c = _canaries(on)
    off_c = _canaries(off)
    out = {
        "probe": "probe2-canary-reach",
        "unit_id": "ADV-0046",
        "observation_method": (
            "Search interceptor-accepted bytes for the planted canary. "
            "Not inferred from prompt constructors alone: HTTP body, MCP "
            "child stdin, and CLI child argv must each contain or lack it."
        ),
        "control_deliberate_send": control,
        "attached": on_c,
        "omitted": off_c,
        "inprocess_adapters": adapter,
        "unattached_fixture_on_disk": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))

    if not (on_c["http"] and on_c["mcp"] and on_c["cli"]):
        return fail(f"attached canary missed a transport {on_c}")
    if on_c["unattached"] or off_c["unattached"]:
        return fail("unattached canary appeared on a transport")
    if off_c["http"] or off_c["mcp"] or off_c["cli"]:
        return fail(f"omitted private body still reached a transport {off_c}")
    if adapter["egressed"]:
        return fail(
            "in-process vendor_runtime opened HTTP/MCP/CLI; unexpected "
            f"hits={adapter['http_hits']} connects={adapter['socket_connects']}"
        )
    if not adapter["canary_in_prompt"] or adapter["anthropic_prompt_chars"] < 1:
        return fail("in-process adapter did not receive the planted prompt")

    print(
        "control_all_three=True attached=http/mcp/cli omitted=none "
        f"inprocess_egressed={adapter['egressed']}"
    )
    print("SUCCESS:ADV-0046-probe2 canary-reach both-states and three-transport control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
