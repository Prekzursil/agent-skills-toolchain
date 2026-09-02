#!/usr/bin/env python3
"""Probe 1: enabledPlugins map from user, project, local, and the inert trap file.

Does not walk plugin command/skill trees. That is probe 2's field.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL
SCHEMA = L.REPO / L.SCHEMA_REL
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0016-probe1 {msg}")
    return 1


def main() -> int:
    payload = L.probe1_payload()
    print(L.dumps(payload))
    ctl = payload["control"]
    if not ctl["agentbridge_disabled"]:
        return fail("agentbridge not disabled on the settings map")
    if not ctl["trap_says_agentbridge_true"]:
        return fail("trap file does not plant agentbridge=true; control is inert")
    if not ctl["trap_ignored"]:
        return fail("trap ~/.claude.json enabledPlugins won; wrong file")
    if not ctl["trap_only_plugin_does_not_win"]:
        return fail("trap-only plugin treated as winning-enabled")
    if not ctl["all_three_scopes_read"]:
        return fail("user/project/local maps were not all read")
    if not ctl["ok"]:
        return fail(f"control {ctl}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if L.SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared:{doc.get('state')}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    if not list(jsonschema.Draft7Validator(schema).iter_errors({})):
        return fail("schema accepts empty object")

    stored = None
    for item in doc.get("named_probes") or []:
        if item.get("id") == "probe1":
            stored = item.get("raw_output")
            break
    if not stored:
        return fail("named probe1 raw_output missing")
    stored_doc = json.loads(stored)
    for key in ("control", "scopes_read", "win_order"):
        if stored_doc.get(key) != payload.get(key):
            return fail(f"artifact drift on {key}")
    art_fix = (stored_doc.get("fixture") or {}).get("agentbridge")
    if art_fix != payload["fixture"]["agentbridge"]:
        return fail("artifact drift on fixture.agentbridge")
    live_ids_art = (stored_doc.get("live") or {}).get("plugin_ids")
    if live_ids_art != payload["live"]["plugin_ids"]:
        return fail("artifact drift on live.plugin_ids")

    print(
        "SUCCESS:AUD-0016-probe1 enabledPlugins-map "
        f"agentbridge_disabled={ctl['agentbridge_disabled']} "
        f"trap_ignored={ctl['trap_ignored']} "
        f"scopes={payload['scopes_read']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
