#!/usr/bin/env python3
"""Probe 2: dynamic reachability from CLI entries, CI, docs, and registries.

Mechanically different from probe 1: follows string-named plugin registries
and CI/docs python -m seeds. The planted registry-only module must be LIVE.
Stripping string edges must return it to DEAD (independence strawman).
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
    probe2_payload,
)

ART = REPO / "command-center/audit/AUD-0032-dead-code-census.json"
SENTINEL = "SUCCESS:AUD-0032"


def main() -> int:
    cen = build()
    payload = probe2_payload(cen)
    print(json.dumps(payload, sort_keys=True))
    assert_control(cen)
    ctl = control_report(cen)
    if payload["plugin_only"] != "LIVE":
        print("FAILED:AUD-0032-probe2 plugin_only not LIVE via registry/CI")
        return 1
    if payload["live_mod"] != "LIVE":
        print("FAILED:AUD-0032-probe2 live_mod not LIVE")
        return 1
    if payload["truly_dead"] != "DEAD":
        print("FAILED:AUD-0032-probe2 truly_dead must stay DEAD")
        return 1
    if payload["mention_only"] != "DEAD":
        print("FAILED:AUD-0032-probe2 mention_only counted as a use")
        return 1
    if ctl["probe2_without_string_edges"] != "DEAD":
        print("FAILED:AUD-0032-probe2 string-edge strawman did not fire")
        return 1
    if payload.get("string_edge_count", 0) < 1:
        print("FAILED:AUD-0032-probe2 no string registry edges")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0032-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0032-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:AUD-0032-probe2 sentinel absent")
        return 1
    art_ctl = (
        doc.get("planted_control")
        or (doc.get("report") or {}).get("planted_control")
        or (doc.get("extensions") or {}).get("planted_control")
        or {}
    )
    if art_ctl.get("probe2_verdict") != "LIVE":
        print("FAILED:AUD-0032-probe2 artifact probe2_verdict not LIVE")
        return 1
    if art_ctl.get("independent") is not True:
        print("FAILED:AUD-0032-probe2 artifact control not independent")
        return 1
    items = (
        doc.get("items")
        or (doc.get("report") or {}).get("items")
        or (doc.get("extensions") or {}).get("items")
        or []
    )
    by_id = {i["id"]: i for i in items if i.get("kind") == "module"}
    row = by_id.get(PLUGIN_ONLY)
    if not row or row.get("probe2_verdict") != "LIVE":
        print("FAILED:AUD-0032-probe2 artifact item probe2 not LIVE")
        return 1
    if row.get("probe1_verdict") == row.get("probe2_verdict"):
        print("FAILED:AUD-0032-probe2 probes agree on registry-only module")
        return 1
    print("SUCCESS:AUD-0032-probe2 registry-only LIVE; strawman DEAD without strings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
