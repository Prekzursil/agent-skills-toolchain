#!/usr/bin/env python3
"""Probe 2: command/skill reachability on installed plugin trees.

Does not read enabledPlugins, settings.json, or .claude.json. That is probe 1.
If agentbridge cannot be distinguished from a reachable plugin, this probe
measures nothing.
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
    print(f"FAILED:AUD-0016-probe2 {msg}")
    return 1


def main() -> int:
    payload = L.probe2_payload()
    print(L.dumps(payload))
    ctl = payload["control"]
    if not ctl["agentbridge_installed"]:
        return fail("agentbridge missing from installed tree; probe measures nothing")
    if ctl["agentbridge_reachable"]:
        return fail("agentbridge commands/skills resolved; known-disabled control failed")
    if not ctl["live_skill_reachable"]:
        return fail("live-skill-plugin did not resolve; reachability probe is inert")
    if ctl["green_not_live_reachable"]:
        return fail("green-not-live plugin resolved; missing-path plant failed")
    if not ctl["distinguished"]:
        return fail("reachability probe cannot distinguish agentbridge from live-skill-plugin")
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

    stored = None
    for item in doc.get("named_probes") or []:
        if item.get("id") == "probe2":
            stored = item.get("raw_output")
            break
    if not stored:
        return fail("named probe2 raw_output missing")
    stored_doc = json.loads(stored)
    for key in ("control",):
        if stored_doc.get(key) != payload.get(key):
            return fail(f"artifact drift on {key}")
    art_ids = (stored_doc.get("fixture") or {}).get("plugin_ids")
    if art_ids != payload["fixture"]["plugin_ids"]:
        return fail("artifact drift on fixture.plugin_ids")
    art_reach = (stored_doc.get("fixture") or {}).get("reachable_ids")
    if art_reach != payload["fixture"]["reachable_ids"]:
        return fail("artifact drift on fixture.reachable_ids")
    live_ids_art = (stored_doc.get("live") or {}).get("plugin_ids")
    if live_ids_art != payload["live"]["plugin_ids"]:
        return fail("artifact drift on live.plugin_ids")

    # Independent recount: reachable iff command_files or skill_files nonempty.
    recount = sorted(
        p["id"]
        for p in payload["fixture"]["plugins"]
        if p.get("command_files") or p.get("skill_files")
    )
    if recount != payload["fixture"]["reachable_ids"]:
        return fail(f"recount reachable {recount} != {payload['fixture']['reachable_ids']}")

    print(
        "SUCCESS:AUD-0016-probe2 reachability "
        f"agentbridge_reachable={ctl['agentbridge_reachable']} "
        f"live_skill_reachable={ctl['live_skill_reachable']} "
        f"distinguished={ctl['distinguished']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
