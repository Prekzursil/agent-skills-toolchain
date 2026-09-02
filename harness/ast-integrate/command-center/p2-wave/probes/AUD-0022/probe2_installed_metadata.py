#!/usr/bin/env python3
"""Probe 2: installed package metadata in an isolated tree.

Reads dist-info METADATA and node_modules package.json only. Does not parse
lockfiles, so a resolver bug or a stale lock cache cannot define this answer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import fixture_installed_graph, fixture_lock_graph  # noqa: E402
from graph import (  # noqa: E402
    artifact_payload,
    live_installed_snapshot,
    live_resolver_snapshot,
    name_version_set,
)

UNIT = "AUD-0022"
ART = REPO / "command-center/audit/AUD-0022-transitive-dep-graph.json"
SENTINEL = (
    "SUCCESS:AUD-0022 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    clean = fixture_installed_graph("clean").to_public()
    dual = fixture_installed_graph("dual").to_public()
    if clean["duplicate_versions"]:
        return fail(f"clean installed reported duplicates {clean['duplicate_versions']}")
    if clean["max_depth"] != 2:
        return fail(f"clean installed max_depth={clean['max_depth']} want=2")
    lock_clean = fixture_lock_graph("clean").to_public()
    if name_version_set(clean, "npm") != name_version_set(lock_clean, "npm"):
        return fail(
            f"clean npm installed {sorted(name_version_set(clean, 'npm'))} "
            f"!= lock {sorted(name_version_set(lock_clean, 'npm'))}"
        )
    if name_version_set(clean, "pypi") != name_version_set(lock_clean, "pypi"):
        return fail(
            f"clean pypi installed {sorted(name_version_set(clean, 'pypi'))} "
            f"!= lock {sorted(name_version_set(lock_clean, 'pypi'))}"
        )

    dual_by_eco = {(d["ecosystem"], d["name"]): d for d in dual["duplicate_versions"]}
    if ("npm", "widget") not in dual_by_eco or ("pypi", "widget") not in dual_by_eco:
        return fail(f"dual installed missing widget on both ecosystems: {dual['duplicate_versions']}")
    for eco in ("npm", "pypi"):
        vers = set(dual_by_eco[(eco, "widget")]["versions"])
        if vers != {"1.0.0", "2.0.0"}:
            return fail(f"{eco} widget versions {vers}")

    live, live_c = live_installed_snapshot(REPO)
    if live_c.get("host_site_packages_consulted") is not False:
        return fail("host site-packages must not be consulted")

    lock_pub, _ = live_resolver_snapshot(REPO)

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    body = artifact_payload(doc)
    graph = body.get("graph") or {}
    if graph.get("node_count") != lock_pub["node_count"]:
        return fail(
            "headline graph must be the live resolver closure, not host or fixture"
        )
    if graph.get("max_depth") != lock_pub["max_depth"]:
        return fail("headline max_depth drifted from live lock-tree")
    if graph.get("duplicate_versions") != lock_pub["duplicate_versions"]:
        return fail("headline duplicates drifted from live lock-tree")
    inst = body.get("installed_live") or {}
    if inst.get("node_count") != live["node_count"]:
        return fail(
            f"installed_live.node_count artifact={inst.get('node_count')} "
            f"recomputed={live['node_count']}"
        )
    if inst.get("duplicate_versions") != live["duplicate_versions"]:
        return fail("installed_live duplicates mismatch")
    if (doc.get("reviewer") or {}).get("independent") is not True:
        return fail("reviewer.independent")
    if (doc.get("reviewer") or {}).get("verdict") != "PASS":
        return fail("reviewer.verdict")
    recorded = (body.get("lock_vs_installed") or {}).get("duplicate_versions_equal")
    actual_equal = live["duplicate_versions"] == lock_pub["duplicate_versions"]
    if recorded is not actual_equal:
        return fail(
            "lock_vs_installed.duplicate_versions_equal drifted from recompute "
            f"recorded={recorded} actual={actual_equal}"
        )

    print(
        json.dumps(
            {
                "method": "installed-metadata-clean-env",
                "clean_max_depth": clean["max_depth"],
                "clean_duplicates": clean["duplicate_versions"],
                "dual_duplicates": dual["duplicate_versions"],
                "host_site_packages_consulted": False,
                "live_installed_node_count": live["node_count"],
                "live_installed_max_depth": live["max_depth"],
                "lock_vs_installed_npm_clean_equal": True,
            },
            sort_keys=True,
            default=str,
        )
    )
    print(
        "SUCCESS:AUD-0022-probe2 installed metadata; dual fires both ecosystems; "
        "clean silent; host site-packages unused"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
