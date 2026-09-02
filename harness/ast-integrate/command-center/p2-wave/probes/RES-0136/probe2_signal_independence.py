#!/usr/bin/env python3
"""Probe 2: two signals independent; mutations flip both; prose does not.

Security rail: an extractor that keys on the word 'restriction' or on
mention of riders in README prose is matching prose, not clauses.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extractor import (  # noqa: E402
    FIXTURES,
    classify,
    load_spdx_mit,
)

ART = REPO / "command-center/research/supply-chain/RES-0136-vendor-rider-propagation.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0136-probe2 {msg}")
    return 1


def strip_rider(text: str) -> str:
    lines = text.replace("\r\n", "\n").splitlines()
    keep = []
    skipping = False
    for line in lines:
        if re.match(r"(?i)^\s*additional\s+rider\b", line):
            skipping = True
            continue
        if skipping and line.startswith("The above copyright notice"):
            skipping = False
            keep.append(line)
            continue
        if not skipping:
            keep.append(line)
    return "\n".join(keep) + "\n"


def rider_block(text: str) -> str:
    lines = text.replace("\r\n", "\n").splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"(?i)^\s*additional\s+rider\b", line):
            start = i
            break
    if start is None:
        raise SystemExit("FAILED:RES-0136-probe2 no rider block to copy")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("The above copyright notice"):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS":
        return fail(f"artifact state {doc.get('state')}")
    sec = (doc.get("reviewer") or {}).get("security") or {}
    if sec.get("verdict") != "PASS":
        return fail("security reviewer not PASS")

    spdx = load_spdx_mit()
    mcp = (FIXTURES / "mcp_agent_mail.LICENSE").read_text(encoding="utf-8")
    js = (FIXTURES / "jsonschema.COPYING").read_text(encoding="utf-8")
    decoy = (FIXTURES / "decoy-prose.txt").read_text(encoding="utf-8")

    mcp_c = classify(mcp, spdx)
    js_c = classify(js, spdx)
    if not mcp_c["signals_agree_on_osi_rider"] or not mcp_c["has_non_osi_rider"]:
        return fail("live mcp signals")
    if js_c["has_non_osi_rider"] or not js_c["signals_agree_on_osi_rider"]:
        return fail("live jsonschema signals")
    s1 = mcp_c["signal_structural"]["id"]
    s2 = mcp_c["signal_mit_residual"]["id"]
    if s1 == s2:
        return fail("signals share an id — not independent")

    stripped = classify(strip_rider(mcp), spdx)
    if stripped["has_non_osi_rider"]:
        return fail("stripped mcp still has rider")
    if stripped["signal_structural"]["osi_plus_rider"]:
        return fail("structural still fires after strip")
    if stripped["signal_mit_residual"]["osi_plus_rider"]:
        return fail("residual still fires after strip")

    grafted = classify(js.rstrip() + "\n\n" + rider_block(mcp) + "\n", spdx)
    if not grafted["has_non_osi_rider"]:
        return fail("grafted rider onto jsonschema not detected")
    if not grafted["signal_structural"]["osi_plus_rider"]:
        return fail("structural silent on graft")
    if not grafted["signal_mit_residual"]["osi_plus_rider"]:
        return fail("residual silent on graft")

    prose = classify(js.rstrip() + "\n\n" + decoy + "\n", spdx)
    if prose["has_non_osi_rider"]:
        return fail("decoy prose grafted onto MIT fired as rider")

    print("signal1=" + s1 + " signal2=" + s2 + " independent=True")
    print("stripped_rider=False grafted_rider=True decoy_on_mit=False")
    print("SUCCESS:RES-0136-probe2 signal independence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
