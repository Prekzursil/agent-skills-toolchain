#!/usr/bin/env python3
"""Probe 1: advertised vs exposed tool schemas, plus namespacing both-states.

Mechanically this is a structural deep-equal of inputSchema objects after
namespace rewrite. It does not inject CallToolResult payloads (probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from adapter import BARE_NAMES, CONFORMING, SCHEMA_DRIFT, bind  # noqa: E402
from protocol import namespaced, schemas_equal  # noqa: E402
from servers import fixture_pair  # noqa: E402
from suite import rule_namespacing, rule_schema_fidelity  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0044-probe1 {msg}")
    return 1


def main() -> int:
    conforming = bind(CONFORMING, fixture_pair())
    advertised = {}
    for sid, server in conforming.servers.items():
        for tool in server.advertised_tools():
            advertised[namespaced(sid, str(tool["name"]))] = tool
    exposed = {t["name"]: t for t in conforming.list_tools()}
    if set(exposed) != set(advertised):
        return _fail(f"name set {sorted(exposed)} != {sorted(advertised)}")
    for name, tool in advertised.items():
        got = exposed[name]
        if got.get("description") != tool.get("description"):
            return _fail(f"description drift {name}")
        if not schemas_equal(got.get("inputSchema"), tool.get("inputSchema")):
            return _fail(f"inputSchema drift {name}")

    drifted = bind(SCHEMA_DRIFT, fixture_pair())
    drift_hit = False
    for t in drifted.list_tools():
        adv = advertised[t["name"]]
        if not schemas_equal(t.get("inputSchema"), adv.get("inputSchema")):
            drift_hit = True
            break
    if not drift_hit:
        return _fail("schema-drift mutant still matched advertised schemas")

    collision = False
    try:
        bind(BARE_NAMES, fixture_pair()).list_tools()
    except ValueError as exc:
        collision = "collision" in str(exc)
    if not collision:
        return _fail("bare-name mutant did not collide on echo")

    r1 = rule_schema_fidelity()
    r2 = rule_namespacing()
    if not r1["positive"]["pass"] or not r1["negative"]["fired_on_bad"]:
        return _fail(f"schema-fidelity both-states {r1}")
    if not r2["positive"]["pass"] or not r2["negative"]["fired_on_bad"]:
        return _fail(f"namespacing both-states {r2}")

    summary = {
        "probe": "probe1-schema-fidelity",
        "n_tools": len(exposed),
        "tools": sorted(exposed),
        "drift_mutant_fired": drift_hit,
        "bare_name_collision_fired": collision,
        "faithful": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "tools="
        + ",".join(sorted(exposed))
        + f" drift_fired={drift_hit} collision_fired={collision}"
    )
    print("SUCCESS:TST-0044-probe1 schema fidelity both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
