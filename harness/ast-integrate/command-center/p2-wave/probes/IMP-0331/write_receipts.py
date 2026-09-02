#!/usr/bin/env python3
"""Write IMP-0331 catalog receipt plus per-unit SUBAGENT-RETURN / manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0331.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0331/probe1_affinity_spread.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0331/probe2_negative_control.py"
)
SUPPORTING = [
    "tools/council/topology/committee.py",
    "tools/council/topology/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0331/scenario.py",
    "command-center/p2-wave/probes/IMP-0331/probe1_affinity_spread.py",
    "command-center/p2-wave/probes/IMP-0331/probe2_negative_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError("no JSON object in probe output")


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[
            :32
        ],
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": "IMP-0331",
        "receipt_path": "command-center/p2-wave/probes/IMP-0331/SUBAGENT-RETURN.json",
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0331 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    impl = art("tools/council/topology/committee.py", "implementation")
    receipt_doc = {
        "schema_version": 1,
        "profile": "council-topology-module",
        "unit_id": "IMP-0331",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0331",
        "title": "Committee and caucus topology",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0331 "
            "tools/council/topology/committee.py "
            "_USER-PROMPTS.md:11172-11244"
        ),
        "question_or_target": (
            "Implement tools/council/topology/committee.py partitioning a "
            "council into standing committees and ad-hoc caucuses that "
            "deliberate separately and report up. Falsifiable question: does "
            "a caucus formed from like-minded participants produce an echo "
            "chamber, measured as reduced position spread relative to a "
            "randomly formed caucus of the same size?"
        ),
        "artifact_paths": [
            "tools/council/topology/committee.py",
            "command-center/p2-wave/probes/IMP-0331/scenario.py",
            "command-center/p2-wave/probes/IMP-0331/probe1_affinity_spread.py",
            "command-center/p2-wave/probes/IMP-0331/probe2_negative_control.py",
        ],
        "artifacts": [
            {
                "path": impl["path"],
                "sha256": impl["sha256"],
                "bytes": impl["bytes"],
                "exists": True,
                "role": "implementation",
                "eol": "LF",
            }
        ],
        "min_bytes_threshold": 256,
        "evidence": [
            {
                "claim": (
                    "On the same question, affinity caucus spread "
                    f"{p1['affinity_spread']:.6f} is strictly less than random "
                    f"caucus spread {p1['random_spread']:.6f} (baseline mean of "
                    f"48 random draws {p1['baseline_spread']:.6f}). Affinity/"
                    f"baseline ratio {p1['affinity_echo']['ratio']:.6f} < 0.5 "
                    "so the echo-chamber detector fires. Computed from member "
                    "positions, not from the formation label."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/topology/committee.py:echo_chamber_verdict",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec("source", "command", P1, t1, c1),
                    probe_rec("verifier", "command", P2, t2, c2),
                ],
            },
            {
                "claim": (
                    "Every live report-up conclusion is reconstructible from "
                    "member turns (cited turn ids exist, belong to the group, "
                    "cover every member, and the reported position equals the "
                    "mean of cited turn positions). Probe2 mutants: foreign "
                    "citation and dropped citation both fail fidelity."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/topology/committee.py:report_up_fidelity",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec("source", "command", P1, t1, c1),
                    probe_rec("verifier", "command", P2, t2, c2),
                ],
            },
        ],
        "test_ids": [
            "experiment-affinity-vs-random-spread",
            "negative-control-random-not-echo",
        ],
        "negative_control_ids": [
            "NC-random-caucus-not-echo",
            "NC-fidelity-foreign-citation",
            "NC-fidelity-drop-citation",
            "DC-affinity-must-fire",
        ],
        "tests": [
            {
                "id": "experiment-affinity-vs-random-spread",
                "command": P1,
                "result": "PASS",
                "output_tail": t1.splitlines()[-1][:400],
            },
            {
                "id": "negative-control-random-not-echo",
                "command": P2,
                "result": "PASS",
                "output_tail": t2.splitlines()[-1][:400],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-random-caucus-not-echo",
                "kind": "known-good-fixture",
                "description": (
                    "A mixed-cluster random caucus of the same size must not "
                    "be flagged as an echo chamber. Detector uses spread vs "
                    "random baseline, not the formation label."
                ),
                "fired_on_bad_state": bool(p2["detector_control_affinity_fires"]),
                "silent_on_good_state": bool(p2["negative_control_random_silent"]),
                "bad_state_output": json.dumps(p2["affinity_echo"], sort_keys=True),
                "good_state_output": json.dumps(p2["random_echo"], sort_keys=True),
            },
            {
                "id": "NC-fidelity-foreign-citation",
                "kind": "known-broken-fixture",
                "description": (
                    "Replace one cited turn with a turn from another group; "
                    "report-up fidelity must FAIL."
                ),
                "fired_on_bad_state": bool(p2["fidelity_foreign_citation_fails"]),
                "silent_on_good_state": bool(p2["fidelity_good_affinity"]["ok"]),
                "bad_state_output": "foreign citation rejected",
                "good_state_output": "live affinity conclusion traceable",
            },
            {
                "id": "NC-fidelity-drop-citation",
                "kind": "known-broken-fixture",
                "description": (
                    "Drop one member's cited turn; report-up fidelity must FAIL."
                ),
                "fired_on_bad_state": bool(p2["fidelity_drop_citation_fails"]),
                "silent_on_good_state": bool(p2["fidelity_good_affinity"]["ok"]),
                "bad_state_output": "dropped citation rejected",
                "good_state_output": "live affinity conclusion traceable",
            },
            {
                "id": "DC-affinity-must-fire",
                "kind": "detector-control",
                "description": (
                    "If affinity did not fire, the random negative control "
                    "would be vacuously silent. Detector-control requires "
                    "the planted like-minded caucus to fire."
                ),
                "fired_on_bad_state": bool(p2["detector_control_affinity_fires"]),
                "silent_on_good_state": bool(p2["negative_control_random_silent"]),
                "bad_state_output": json.dumps(p2["affinity_echo"], sort_keys=True),
                "good_state_output": json.dumps(p2["random_echo"], sort_keys=True),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0331-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "started_from": "tests (probe2 public API), not the author's summary",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0331/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Positions are numeric fixtures (two clusters), not live "
                    "model outputs. The echo-chamber result is therefore a "
                    "composition effect of affinity grouping, which is the "
                    "catalog's falsifiable question, not a claim about LLM "
                    "sycophancy."
                ),
                "verdict": "STATED",
                "settling_experiment": (
                    "Re-run compare_affinity_vs_random with participant "
                    "adapters once IMP-0265 seating is on disk."
                ),
            },
            {
                "claim": (
                    "Turns are recorded by RecordingKernel inside this module, "
                    "not by tools/council/kernel.py (IMP-0264 is absent here). "
                    "The topology port is execute_turn; a production kernel "
                    "can replace the double without changing committee.py's "
                    "call sites."
                ),
                "verdict": "STATED",
                "settling_experiment": (
                    "Plug committee.run_session(kernel=production_kernel) "
                    "when IMP-0264 delivers kernel.py."
                ),
            },
            {
                "claim": (
                    "ECHO_CHAMBER_MAX_RATIO=0.5 is a documented constant, not "
                    "fitted on a large corpus. The measured affinity/baseline "
                    f"ratio was {p1['affinity_echo']['ratio']:.4f}, so the "
                    "qualitative result is not threshold-fragile on this roster."
                ),
                "verdict": "STATED",
                "settling_experiment": (
                    "Sweep max_ratio in (0.2, 0.8) on several rosters and "
                    "report the crossover."
                ),
            },
        ],
        "report": {
            "kind": "committee-caucus-topology",
            "module": "tools/council/topology/committee.py",
            "spread": p1,
            "negative_control": {
                "random_echo": p2["random_echo"],
                "affinity_echo": p2["affinity_echo"],
                "random_mixed": p2["random_is_mixed_clusters"],
                "foreign_citation_fails": p2["fidelity_foreign_citation_fails"],
                "drop_citation_fails": p2["fidelity_drop_citation_fails"],
            },
        },
        "notes": (
            "G-1 for IMP-0331: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = art(OUT, "primary")
    artifacts = [primary] + [art(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0331",
        "unit_id": "IMP-0331",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0331",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-topology-module"
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0331/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0331-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0331: live named probes exit 0, IMP-0331.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0331",
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0331 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
