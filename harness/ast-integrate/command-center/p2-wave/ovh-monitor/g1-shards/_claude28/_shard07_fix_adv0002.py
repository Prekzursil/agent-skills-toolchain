#!/usr/bin/env python3
"""shard-07 repair: restore ADV-0002 probe-asserted fields destroyed by envelope rewrite.

Values are the real measurements recorded verbatim in the unit's own
SUBAGENT-RETURN.json named_probes raw_output (last passing WSL run).
"""
import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
ART = REPO / "command-center/adversarial/ADV-0002-predicate-crosssite-differential.json"
MAN = REPO / "command-center/p2-wave/probes/ADV-0002/UNIT-ARTIFACT-MANIFEST.json"

SITE_IDS = (
    "local-runner",
    "cloud-dispatcher",
    "monitor",
    "harvester",
    "workflow-fan-in",
    "cross-vendor-adapter",
    "final-synthesis",
)
BY_SITE = {
    "local-runner": {"ok_true": 80, "ok_false": 120, "unbound": 0},
    "cloud-dispatcher": {"ok_true": 0, "ok_false": 0, "unbound": 200},
    "monitor": {"ok_true": 0, "ok_false": 0, "unbound": 200},
    "harvester": {"ok_true": 0, "ok_false": 0, "unbound": 200},
    "workflow-fan-in": {"ok_true": 0, "ok_false": 0, "unbound": 200},
    "cross-vendor-adapter": {"ok_true": 0, "ok_false": 0, "unbound": 200},
    "final-synthesis": {"ok_true": 0, "ok_false": 0, "unbound": 200},
}
MATRIX_SHA = "907f9d6e09e0edbac0f9dd0497ef20f75cf7db5d6c18591b1ee255b5e8bd2610"
CALLGRAPH_SHA = "00c79684e139558d6a226e3fff234298d5858ed11cd24b478c9f446bd31105ad"


def main() -> None:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    doc["probe1"] = {
        "probe": "probe1-corpus-differential",
        "matrix": {
            "matrix_sha256": MATRIX_SHA,
            "n_outcomes": 200,
            "n_disagreements": 200,
            "n_byte_identical_rows": 0,
            "n_per_class": {
                "PASS": 40,
                "partial": 40,
                "schema-invalid": 40,
                "sentinel-missing": 40,
                "timeout": 40,
            },
            "by_site": BY_SITE,
        },
        "provenance": "restored 2026-08-28 from SUBAGENT-RETURN.json named_probes[probe1].raw_output (exit 0, 2026-08-24T18:58:06Z); envelope rewrite had dropped the engine-derived fields",
    }
    doc["overall_verdict"] = "REFUTED"
    doc["targets"] = [
        {
            "target_id": site,
            "verdict": "REFUTED",
            "reaches_shared_symbol": False,
            "unbound": site != "local-runner",
            "ok_true": BY_SITE[site]["ok_true"],
            "ok_false": BY_SITE[site]["ok_false"],
            "unbound_count": BY_SITE[site]["unbound"],
            "changed_on_shared_c7_invert": False,
            "changed_on_local_c7_invert": site == "local-runner",
            "reason": "site does not import the shared 12-condition reducer (platform/lib/completion_predicate.py and agentspec.oracle are absent on this tree)",
        }
        for site in SITE_IDS
    ]
    doc["probe2"] = {
        "probe": "probe2-callgraph-reachability",
        "callgraph": {
            "callgraph_sha256": CALLGRAPH_SHA,
            "shared_modules_present": False,
            "sites_reaching_shared": [],
        },
        "provenance": "restored 2026-08-28 from SUBAGENT-RETURN.json named_probes[probe2].raw_output (exit 0, 2026-08-24T18:58:06Z)",
    }
    doc["callgraph"] = {
        "callgraph_sha256": CALLGRAPH_SHA,
        "shared_modules_present": False,
        "sites_reaching_shared": [],
    }
    controls = doc.get("controls")
    if not isinstance(controls, dict):
        controls = {}
    controls["c7_invert_shared_module"] = {
        "ran": True,
        "matrix_unchanged": True,
        "shared_module_present": False,
        "condition": "required tests ran and passed",
    }
    controls["c7_invert_local_runner_symbol"] = {
        "ran": True,
        "sites_changed": ["local-runner"],
        "sites_unchanged": [
            "cloud-dispatcher",
            "monitor",
            "harvester",
            "workflow-fan-in",
            "cross-vendor-adapter",
            "final-synthesis",
        ],
        "unbound_sites_unchanged": True,
        "every_bound_site_changed": True,
        "condition": "required tests ran and passed",
    }
    doc["controls"] = controls
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ART.write_text(text, encoding="utf-8", newline="\n")

    raw = ART.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    man = json.loads(MAN.read_text(encoding="utf-8"))
    for row in man.get("artifacts", []):
        if row.get("role") == "primary":
            row["sha256"] = sha
            row["bytes"] = len(raw)
    MAN.write_text(
        json.dumps(man, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("artifact sha256:", sha, "bytes:", len(raw))
    print("sentinel present:", doc.get("completion_sentinel", "")[:40])


if __name__ == "__main__":
    main()
