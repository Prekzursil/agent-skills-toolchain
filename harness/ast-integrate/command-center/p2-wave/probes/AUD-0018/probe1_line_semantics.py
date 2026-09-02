#!/usr/bin/env python3
"""Probe 1: line-level read of each deploy/sync script.

Names the copy primitive and every guard clause. Does not execute scripts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{E.UNIT}-probe1 {msg}")
    return 1


def check_artifact(disc: dict, ctl: dict) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if E.COMPLETION not in text:
        return "artifact completion_sentinel absent"
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"artifact self-declared {doc.get('state')}"
    if str(doc.get("report_kind") or "") != "audit-finding":
        return "artifact report_kind is not audit-finding"
    rec_absent = list((doc.get("discovery") or {}).get("catalog_absent") or [])
    live_absent = list(disc.get("catalog_absent") or [])
    if rec_absent != live_absent:
        return f"catalog_absent drift rec={rec_absent} live={live_absent}"
    rec_mode = None
    for row in (doc.get("discovery") or {}).get("planted") or []:
        if str(row.get("path") or "").endswith("copy-item-force-verbatim.ps1"):
            rec_mode = row.get("copy_mode")
    if rec_mode != "verbatim":
        return f"artifact planted verbatim copy_mode={rec_mode!r}"
    if not (doc.get("line_control") or {}).get("pass"):
        return "artifact line_control.pass is not true"
    _ = ctl
    return None


def main() -> int:
    disc = E.discover()
    ctl = E.control_line_semantics(disc)
    if not ctl.get("pass"):
        return fail(f"line-semantics controls failed {ctl.get('failed')}")
    planted = {Path(r["path"]).name: r for r in disc["planted"]}
    verbatim = planted.get("copy-item-force-verbatim.ps1") or {}
    if not verbatim.get("catalog_line_67_copy_item_force"):
        return fail("planted Copy-Item -Force is not at line 67")
    err = check_artifact(disc, ctl)
    if err:
        return fail(err)
    payload = {
        "probe": "probe1-line-semantics",
        "unit_id": E.UNIT,
        "method": "line-level read of copy primitives and guard clauses",
        "command": E.P1,
        "catalog_absent": disc["catalog_absent"],
        "catalog_present_count": disc["catalog_present_count"],
        "scripts_dir_exists": disc["scripts_dir_exists"],
        "planted": [E.slim_row(r) for r in disc["planted"]],
        "other_deploy": [E.slim_row(r) for r in disc["other_deploy"]],
        "catalog_named": [E.slim_row(r) for r in disc["catalog_named"]],
        "control": ctl["checks"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"catalog_absent={len(disc['catalog_absent'])} "
        f"planted_verbatim_line67={verbatim.get('catalog_line_67_copy_item_force')} "
        f"transform={planted.get('transform-replace.ps1', {}).get('copy_mode')} "
        f"guards={planted.get('guarded-sync.ps1', {}).get('guard_kinds')}"
    )
    print("SUCCESS:AUD-0018-probe1 line-level copy primitive and guard census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
