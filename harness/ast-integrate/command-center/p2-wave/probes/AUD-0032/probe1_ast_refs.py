#!/usr/bin/env python3
"""Probe 1: AST-level symbol reference resolution.

Recomputes the import graph. A module referenced only by a registry string
must be DEAD. Live AST imports must be LIVE. Does not trust the artifact
self-report without a live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from census import (  # noqa: E402
    PLUGIN_ONLY,
    assert_control,
    build,
    control_report,
    probe1_payload,
)

ART = REPO / "command-center/audit/AUD-0032-dead-code-census.json"
SENTINEL = "SUCCESS:AUD-0032"


def main() -> int:
    cen = build()
    payload = probe1_payload(cen)
    print(json.dumps(payload, sort_keys=True))
    assert_control(cen)
    ctl = control_report(cen)
    if payload["plugin_only"] != "DEAD":
        print("FAILED:AUD-0032-probe1 plugin_only not DEAD on AST")
        return 1
    if payload["live_mod"] != "LIVE":
        print("FAILED:AUD-0032-probe1 live_mod not LIVE on AST")
        return 1
    if payload["truly_dead"] != "DEAD":
        print("FAILED:AUD-0032-probe1 truly_dead not DEAD")
        return 1
    if payload["mention_only"] != "DEAD":
        print("FAILED:AUD-0032-probe1 mention_only counted as a use")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0032-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0032-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:AUD-0032-probe1 sentinel absent")
        return 1
    art_ctl = (
        doc.get("planted_control")
        or (doc.get("report") or {}).get("planted_control")
        or (doc.get("extensions") or {}).get("planted_control")
        or {}
    )
    if art_ctl.get("probe1_verdict") != "DEAD":
        print("FAILED:AUD-0032-probe1 artifact probe1_verdict not DEAD")
        return 1
    if art_ctl.get("independent") is not True:
        print("FAILED:AUD-0032-probe1 artifact control not independent")
        return 1
    items = (
        doc.get("items")
        or (doc.get("report") or {}).get("items")
        or (doc.get("extensions") or {}).get("items")
        or []
    )
    by_id = {i["id"]: i for i in items if i.get("kind") == "module"}
    row = by_id.get(PLUGIN_ONLY)
    if not row or row.get("probe1_verdict") != "DEAD":
        print("FAILED:AUD-0032-probe1 artifact item probe1 not DEAD")
        return 1
    if ctl["probe1_verdict"] != "DEAD":
        print("FAILED:AUD-0032-probe1 live control drifted")
        return 1
    print("SUCCESS:AUD-0032-probe1 AST refs match artifact; registry-only is DEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
