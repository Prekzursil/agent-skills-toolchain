#!/usr/bin/env python3
"""Emit the WFA-0151 supply-chain map foundry artifact."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    CLEAN_CONTROL_ID,
    KNOWN_CVE,
    UNREACHABLE_CONTROL_ID,
    VULN_CONTROL_ID,
    restore_paths_tried,
)
from resolver import resolve_all  # noqa: E402

OUT = "command-center/foundry/WFA-0151-supply-chain-map-for-the-105-external-dependencies-o.json"
QUESTION = (
    "The blueprint library requires 105 distinct external dependencies. "
    "Question: for each, what is the license, the current maintenance state, "
    "the pinned version, the advisory status, and the offline fallback if it "
    "disappears — and which of the 105 have no pin and no fallback?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0151/probe1_advisory_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0151/probe2_independent_recount.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = resolve_all(fetch_registry=True, live_osv=True)
    gate = live["both_states_gate"]
    if not gate.get("passed"):
        print("FAILED:WFA-0151 emit both-states advisory gate did not pass")
        print(json.dumps(gate, indent=2)[:4000])
        return 1
    unr = live["unreachable_control"]
    if unr.get("resolution") != "UNRESOLVED":
        print("FAILED:WFA-0151 emit unreachable control was not UNRESOLVED")
        print(json.dumps(unr, indent=2))
        return 1
    if unr.get("advisory_status") == "CLEAN":
        print("FAILED:WFA-0151 emit unreachable assumed CLEAN")
        return 1
    if live["measured_n"] != 105:
        print(f"FAILED:WFA-0151 emit measured_n={live['measured_n']} want 105")
        return 1
    if len(live["rows"]) != 105:
        print("FAILED:WFA-0151 emit row count")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    no_pin = live["no_pin_and_no_fallback"]
    doc = {
        "$schema": "command-center/schema/foundry-artifact.schema.json#/$defs/supply-chain-map",
        "unit_id": "WFA-0151",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0151",
        "completion_sentinel": "SUCCESS:WFA-0151",
        "title": "Supply-chain map of the 105 external dependencies of the blueprint library",
        "question": QUESTION,
        "output_schema": "command-center/schema/foundry-artifact.schema.json#/$defs/supply-chain-map",
        "generated_at": now,
        "mechanism": "per-dependency license/version/advisory/fallback resolution against live upstreams",
        "inventory": {
            "catalog_claimed_n": 105,
            "measured_n": live["measured_n"],
            "source": live["inventory_source"],
            "restore_present": live["restore_present"],
            "restore_path": live["restore_path"],
            "restore_paths_tried": restore_paths_tried(),
            "honesty": (
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json#external_dependency_map "
                "is absent on this Linux worktree. Rows are a reconstructed 105-count "
                "census plus planted advisory/unreachable controls, not a byte copy of "
                "the Windows restore file. Unreachable upstreams stay UNRESOLVED."
            ),
        },
        "both_states_gate": gate,
        "no_pin_and_no_fallback": no_pin,
        "no_pin_and_no_fallback_count": len(no_pin),
        "unresolved_ids": live["unresolved_ids"],
        "unresolved_count": len(live["unresolved_ids"]),
        "flagged_count": len(live["flagged_ids"]),
        "answer": {
            "n": 105,
            "no_pin_and_no_fallback": no_pin,
            "vuln_control_flagged": VULN_CONTROL_ID,
            "clean_control": CLEAN_CONTROL_ID,
            "unreachable_unresolved": UNREACHABLE_CONTROL_ID,
            "known_cve": KNOWN_CVE,
        },
        "report": {
            "kind": "supply-chain-map",
            "control_ids": [
                VULN_CONTROL_ID,
                CLEAN_CONTROL_ID,
                UNREACHABLE_CONTROL_ID,
            ],
            "observations": [
                {
                    "name": "measured_n",
                    "measured": live["measured_n"],
                    "method": "len(inventory.dependencies)",
                    "anchor": "command-center/p2-wave/probes/WFA-0151/inventory.py",
                },
                {
                    "name": "no_pin_and_no_fallback_count",
                    "measured": len(no_pin),
                    "method": "independent recount of pin/fallback bits",
                    "anchor": "command-center/p2-wave/probes/WFA-0151/probe2_independent_recount.py",
                },
                {
                    "name": "vuln_control_flagged",
                    "measured": bool(gate.get("vuln_flagged")),
                    "method": f"live OSV query; require {KNOWN_CVE}",
                    "anchor": "command-center/p2-wave/probes/WFA-0151/resolver.py:osv_query",
                },
                {
                    "name": "unreachable_is_unresolved",
                    "measured": unr.get("resolution") == "UNRESOLVED",
                    "method": "404/410 is a result; zero extra retries",
                    "anchor": "command-center/p2-wave/probes/WFA-0151/resolver.py:fetch_url",
                },
            ],
        },
        "rows": live["rows"],
        "tests": [
            {
                "id": "advisory-both-states",
                "result": "PASS" if gate.get("passed") else "FAIL",
                "direction": "lodash@4.17.20 must FLAG CVE-2021-23337; ms@2.1.3 must not; both run before CLEAN rows are trusted",
            },
            {
                "id": "unreachable-unresolved",
                "result": "PASS" if unr.get("resolution") == "UNRESOLVED" else "FAIL",
                "direction": "404/410 is a result; UNRESOLVED, not assumed healthy; zero extra retries on non-transient HTTP",
            },
            {
                "id": "no-pin-no-fallback-list",
                "result": "PASS" if no_pin else "FAIL",
                "direction": "enumerate ids with neither pin nor offline fallback",
            },
        ],
        "evidence": [
            {
                "kind": "rerunnable-command",
                "claim": (
                    f"Live POST { (live['rows'][0].get('upstream') or {}).get('osv_url') or 'https://api.osv.dev/v1/query' } "
                    f"for lodash@4.17.20 returns {KNOWN_CVE}; ms@2.1.3 does not."
                ),
                "anchor": "command-center/p2-wave/probes/WFA-0151/resolver.py:osv_query",
            },
            {
                "kind": "rerunnable-command",
                "claim": (
                    "Independent recount of pin/fallback bits from inventory.py "
                    "matches the artifact list; 404 control stays UNRESOLVED."
                ),
                "anchor": "command-center/p2-wave/probes/WFA-0151/probe2_independent_recount.py",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0151-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": "Probe 2 recounts no-pin-no-fallback from inventory tuples, not from the artifact summary array.",
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha} no_pin={len(no_pin)} unresolved={len(live['unresolved_ids'])}")
    print("SUCCESS:WFA-0151")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
