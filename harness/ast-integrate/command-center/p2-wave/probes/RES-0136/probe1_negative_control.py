#!/usr/bin/env python3
"""Probe 1: negative control — plain OSI must report NO rider.

Catalog: include one dependency with a plain OSI licence and confirm the
extractor reports NO rider. An extractor that finds a rider everywhere is
matching prose, not clauses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
from extractor import naive_restriction_word  # noqa: E402

ART = REPO / "command-center/research/supply-chain/RES-0136-vendor-rider-propagation.json"
SENTINEL = "SUCCESS:RES-0136"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0136-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    nc = doc.get("negative_control") or {}
    if nc.get("extractor_reports_rider") is not False:
        return fail("artifact negative_control.extractor_reports_rider")
    if nc.get("naive_restriction_word_reports_rider") is not True:
        return fail("artifact did not record the naive MIT false-positive")

    rows = {r["id"]: r for r in C.corpus_rows()}
    js = rows["jsonschema"]
    spdx = rows["spdx_MIT"]
    decoy = rows["decoy_prose"]
    mcp = rows["mcp_agent_mail"]
    llama = rows["llama3"]

    js_text = (HERE / "fixtures" / js["filename"]).read_text(encoding="utf-8")
    if not naive_restriction_word(js_text):
        return fail("naive word-scan silent on jsonschema MIT")
    if js["has_non_osi_rider"] or js["has_non_osi_licence"]:
        return fail("jsonschema classified as having a rider")
    if spdx["has_non_osi_rider"] or decoy["has_non_osi_rider"]:
        return fail("template or decoy classified as rider")
    if not mcp["has_non_osi_rider"]:
        return fail("mcp_agent_mail rider missed")
    if llama["has_non_osi_rider"] or not llama["has_non_osi_licence"]:
        return fail("llama misclassified")
    if not js["signals_agree_on_osi_rider"]:
        return fail("jsonschema signals disagree")
    if not mcp["signals_agree_on_osi_rider"]:
        return fail("mcp_agent_mail signals disagree")

    print("NEGATIVE CONTROL: jsonschema is plain OSI MIT.")
    print("extractor_reports_rider=False naive_restriction_word=True")
    print("decoy_prose_rider=False spdx_MIT_rider=False")
    print("mcp_agent_mail_rider=True llama_non_osi_licence=True llama_osi_rider=False")
    print("SUCCESS:RES-0136-probe1 negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
