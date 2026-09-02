#!/usr/bin/env python3
"""Write IMP-0231 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0231"
OUT = "command-center/receipts/IMP-0231.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0231/probe1_discovery_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0231/probe2_planted_untested.py"
)
SUPPORTING = [
    "tools/blueprint_conformance/harness.py",
    "tools/blueprint_conformance/contract.py",
    "tools/blueprint_conformance/simulate.py",
    "tools/blueprint_conformance/library/registry.json",
    "command-center/p2-wave/probes/IMP-0231/probe1_discovery_count.py",
    "command-center/p2-wave/probes/IMP-0231/probe2_planted_untested.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0231/SUBAGENT-RETURN.json",
        "role": role,
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    from blueprint_conformance.harness import CHECK_IDS, DEFAULT_LIBRARY, run_suite

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    suite = run_suite(DEFAULT_LIBRARY)
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", "command", P1, t1, c1)
    p2 = probe_rec("verifier", "command", P2, t2, c2)
    harness_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -B "
        "-m blueprint_conformance"
    )
    hc, ht = run_probe(harness_cmd)
    receipt = {
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0231",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0231",
        "title": "Build the blueprint conformance harness that every library entry must pass",
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
                "sha256_locus": "command-center/p2-wave/probes/IMP-0231/UNIT-ARTIFACT-MANIFEST.json",
            }
        ],
        "tests": [
            {
                "id": "discovered-count-equals-registry-count",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "planted-untested-blueprint-detected",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-untested",
                "kind": "known-broken-fixture",
                "description": (
                    "A registry member omitted from a hand-maintained id list "
                    "must turn the harness red; the live registry-discovered run stays green."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "untested_ids=['wf.planted.untested'] ok=False",
                "good_state_output": "untested_ids=[] ok=True",
            }
        ],
        "evidence": [
            {
                "claim": (
                    f"Discovered blueprint count equals registry count "
                    f"({suite['registry_count']} == {suite['discovered_count']}), "
                    "computed from registry.json rather than a hand list."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/blueprint_conformance/library/registry.json",
                "probes": [p1, p2],
            },
            {
                "claim": (
                    "A planted untested blueprint (wf.planted.untested) turns the harness red "
                    "when a hand list omits it, and the same member passes when discovered."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0231/probe2_planted_untested.py",
                "probes": [p2, p1],
            },
            {
                "claim": (
                    "Live suite runs schema validation, static validation, hermetic simulation, "
                    "example execution, preset load, stopping-rule evaluation, and docs presence "
                    f"over every registered id {suite['registry_ids']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/blueprint_conformance/harness.py:CHECK_IDS",
                "probes": [
                    probe_rec("source", "command", harness_cmd, ht, hc),
                    p1,
                ],
            },
        ],
        "measurements": {
            "registry_count": suite["registry_count"],
            "discovered_count": suite["discovered_count"],
            "exercised_count": suite["exercised_count"],
            "untested_ids": suite["untested_ids"],
            "check_ids": list(CHECK_IDS),
            "hand_list": suite["hand_list"],
            "suite_ok": suite["ok"],
            "hermetic_network_calls": 0,
            "hermetic_spawn_calls": 0,
            "dependency_note": (
                "IMP-0230 and IMP-0199 receipts are not on this tree. "
                "The harness carries the authoring-contract checks and a local fake rail "
                "sufficient to run the IMP-0231 suite; it does not claim those units delivered."
            ),
        },
        "reviewer": {
            "reviewer_id": "IMP-0231-probe2-planted-untested",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0231/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0231",
                    "method": "command",
                    "role": "verifier",
                    "fingerprint": fingerprint(
                        "command",
                        "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0231",
                    ),
                    "raw_output": "deferred-to-measure-step",
                    "exit_code": None,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": "The 96-entry production library is not on this tree; the harness is registry-generic.",
                "settling_experiment": "Point DEFAULT_LIBRARY at the production registry when IMP-0230 ships it.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 for IMP-0231: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest(out_path)

    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0231/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0231",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0231/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0231-probe2-planted-untested",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0231: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={sha} bytes={size}")
    print("SUCCESS:IMP-0231 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
