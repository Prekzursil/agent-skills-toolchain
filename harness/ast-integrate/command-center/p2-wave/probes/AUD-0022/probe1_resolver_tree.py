#!/usr/bin/env python3
"""Probe 1: resolver frozen trees (npm lock + uv.lock). Independent of installed metadata."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import fixture_lock_graph  # noqa: E402
from graph import artifact_payload, live_resolver_snapshot, name_version_set  # noqa: E402

UNIT = "AUD-0022"
ART = REPO / "command-center/audit/AUD-0022-transitive-dep-graph.json"
SENTINEL = (
    "SUCCESS:AUD-0022 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    clean = fixture_lock_graph("clean").to_public()
    dual = fixture_lock_graph("dual").to_public()
    if clean["duplicate_versions"]:
        return fail(f"clean lock reported duplicates {clean['duplicate_versions']}")
    if clean["max_depth"] != 2:
        return fail(f"clean lock max_depth={clean['max_depth']} want=2")
    names = {(n["name"], n["version"], n["ecosystem"]) for n in clean["nodes"]}
    if ("mid-pkg", "1.0.0", "npm") not in names or ("leaf-pkg", "1.0.0", "npm") not in names:
        return fail(f"clean npm nodes missing: {sorted(names)}")
    if ("midpkg", "1.0.0", "pypi") not in names or ("leafpkg", "1.0.0", "pypi") not in names:
        return fail(f"clean pypi nodes missing: {sorted(names)}")
    dual_names = {d["name"] for d in dual["duplicate_versions"]}
    if "widget" not in dual_names:
        return fail(f"dual lock did not name widget: {dual['duplicate_versions']}")
    widget = next(d for d in dual["duplicate_versions"] if d["name"] == "widget")
    if set(widget["versions"]) != {"1.0.0", "2.0.0"}:
        return fail(f"widget versions {widget['versions']}")
    if widget["ecosystem"] != "npm":
        return fail(f"probe1 dual should be npm-nested, got {widget}")

    live, live_c = live_resolver_snapshot(REPO)

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
    if graph.get("node_count") != live["node_count"]:
        return fail(
            f"live node_count artifact={graph.get('node_count')} recomputed={live['node_count']}"
        )
    if graph.get("max_depth") != live["max_depth"]:
        return fail(
            f"live max_depth artifact={graph.get('max_depth')} recomputed={live['max_depth']}"
        )
    if graph.get("duplicate_versions") != live["duplicate_versions"]:
        return fail("live duplicate_versions mismatch vs lock-tree recompute")
    both = body.get("both_states_control") or {}
    if both.get("dual_version_fired") is not True:
        return fail("both_states dual_version_fired")
    if both.get("clean_resolution_silent") is not True:
        return fail("both_states clean_resolution_silent")
    method = str((body.get("probes_methods") or {}).get("probe1") or "")
    if "lock" not in method.lower() and "resolver" not in method.lower():
        return fail("artifact does not record probe1 as resolver/lock tree")

    print(
        json.dumps(
            {
                "method": "resolver-lock-tree",
                "clean_max_depth": clean["max_depth"],
                "clean_duplicates": clean["duplicate_versions"],
                "dual_duplicates": dual["duplicate_versions"],
                "live_lockfile_count": live_c.get("lockfile_count"),
                "live_node_count": live["node_count"],
                "live_max_depth": live["max_depth"],
                "live_duplicates": live["duplicate_versions"],
                "npm_name_versions": sorted(name_version_set(clean, "npm")),
            },
            sort_keys=True,
            default=str,
        )
    )
    print(
        "SUCCESS:AUD-0022-probe1 resolver lock tree; dual widget fires; clean silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
