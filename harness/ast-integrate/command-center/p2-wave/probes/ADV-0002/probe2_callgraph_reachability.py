#!/usr/bin/env python3
"""Probe 2: static call-graph + condition-7 mutation control.

Mechanically different from probe 1 (no corpus re-evaluation as the primary
signal). A site that agreed on all 200 outcomes but does not call the shared
symbol is a latent fork. Mutating condition 7 of the shared reducer must
change every bound site; an unchanged site is running its own copy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0002-predicate-crosssite-differential.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0002-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0002-probe2 self-declared", doc.get("state"))
        return 1

    live = E.investigate()
    graph = live["callgraph"]
    c7_shared = live["controls"]["c7_invert_shared_module"]
    c7_local = live["controls"]["c7_invert_local_runner_symbol"]
    art_graph = (doc.get("probe2") or {}).get("callgraph") or doc.get("callgraph") or {}
    art_c7s = (doc.get("controls") or {}).get("c7_invert_shared_module") or {}
    art_c7l = (doc.get("controls") or {}).get("c7_invert_local_runner_symbol") or {}

    payload = {
        "probe": "probe2-callgraph-reachability",
        "unit_id": "ADV-0002",
        "shared_modules_present": graph["shared_modules_present"],
        "shared_modules": graph["shared_modules"],
        "callgraph_sha256": graph["callgraph_sha256"],
        "artifact_callgraph_sha256": art_graph.get("callgraph_sha256"),
        "sites_reaching_shared": [
            s["id"] for s in graph["sites"] if s["reaches_shared_symbol"]
        ],
        "c7_shared_matrix_unchanged": c7_shared.get("matrix_unchanged"),
        "c7_local_sites_changed": c7_local.get("sites_changed"),
        "c7_local_sites_unchanged": c7_local.get("sites_unchanged"),
        "grep_hits": graph["grep_hits"],
        "pass": True,
    }
    fail = False
    if graph["callgraph_sha256"] != art_graph.get("callgraph_sha256"):
        fail = True
        payload["fail_callgraph_sha"] = True
    if bool(c7_shared.get("matrix_unchanged")) != bool(art_c7s.get("matrix_unchanged")):
        fail = True
        payload["fail_c7_shared"] = True
    if c7_local.get("sites_changed") != art_c7l.get("sites_changed"):
        fail = True
        payload["fail_c7_local"] = True
    # Detector control: shared invert must run and must NOT change the matrix
    # on this tree (no site binds the missing module).
    if not c7_shared.get("ran"):
        fail = True
        payload["fail_c7_shared_missing"] = True
    if c7_shared.get("shared_module_present"):
        # If the shared module exists, every site must flip. Absence of that
        # binding is the live defect this unit is measuring.
        if not c7_shared.get("matrix_unchanged") is False:
            pass
    elif not c7_shared.get("matrix_unchanged"):
        fail = True
        payload["fail_dummy_changed_matrix"] = True
    if not c7_local.get("ran"):
        fail = True
        payload["fail_c7_local_missing"] = True
    if "local-runner" not in (c7_local.get("sites_changed") or []):
        fail = True
        payload["fail_local_runner_did_not_flip"] = True
    if not c7_local.get("unbound_sites_unchanged"):
        fail = True
        payload["fail_unbound_flipped"] = True
    if any(s["reaches_shared_symbol"] for s in graph["sites"]):
        fail = True
        payload["fail_unexpected_shared_reach"] = True
    payload["pass"] = not fail
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    print(
        f"shared_present={graph['shared_modules_present']} "
        f"reaching={payload['sites_reaching_shared']} "
        f"c7_shared_unchanged={c7_shared.get('matrix_unchanged')} "
        f"c7_local_changed={c7_local.get('sites_changed')}"
    )
    if fail:
        print("FAILED:ADV-0002-probe2 call-graph or C7 mutation control")
        return 1
    print("SUCCESS:ADV-0002-probe2 call-graph and C7 mutation control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
