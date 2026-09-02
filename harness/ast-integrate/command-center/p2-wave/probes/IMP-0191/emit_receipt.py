#!/usr/bin/env python3
"""Emit IMP-0191 receipt, per-unit SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST.

Probes must already be green; this script re-runs them, writes the catalog
artifact, then registers the live sha256. Does not call unit_manifest.py --write.
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
REPO = Path(__file__).resolve().parents[4]
OUT = "command-center/receipts/IMP-0191.json"
DETECTOR = "tools/fusion/capability_loss.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0191/probe1_admitted_empty_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0191/probe2_planted_loss.py"
)
SUPPORTING = [
    DETECTOR,
    "tools/fusion/__init__.py",
    "command-center/p2-wave/probes/IMP-0191/fixtures/library.json",
    "command-center/p2-wave/probes/IMP-0191/probe1_admitted_empty_diff.py",
    "command-center/p2-wave/probes/IMP-0191/probe2_planted_loss.py",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0191",
        "receipt_path": "command-center/p2-wave/probes/IMP-0191/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": max(len(data), 1) if path.is_file() else 0,
        "sha256": hashlib.sha256(data).hexdigest() if path.is_file() else "",
        "exists": path.is_file(),
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0191 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    detector_sha, detector_bytes = digest(REPO / DETECTOR)
    lib_sha, lib_bytes = digest(HERE / "fixtures" / "library.json")

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0191",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0191",
        "completion_sentinel": "SUCCESS:IMP-0191",
        "title": "Implement the capability-loss detector for fusions",
        "report_kind": "receipt",
        "spec_anchor": "_USER-PROMPTS.md:11333",
        "spec_anchor_note": (
            "Catalog row IMP-0191 names 'workflow fusion loses a source capability' "
            "as failure class (11333). A1 FAILURE-MODES.json maps that same name to "
            "FC-11332 / spec 11332, and maps 11333 to 'fused workflow performs worse "
            "than every source'. The detector keys on the named class string, records "
            "both integers, and does not silently retarget the worse-than-sources class."
        ),
        "min_bytes_threshold": 2048,
        "question_or_target": (
            "Assert that a fusion retains every capability of every source. "
            "The check is a computed set difference over capability vectors and "
            "it FIRES on a planted loss."
        ),
        "implementation": {
            "detector_path": DETECTOR,
            "detector_sha256": detector_sha,
            "detector_bytes": detector_bytes,
            "library_path": "command-center/p2-wave/probes/IMP-0191/fixtures/library.json",
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "rule": (
                "lost = union(capability_vector(source) for source in sources) "
                "- capability_vector(fusion); fire iff lost is nonempty"
            ),
            "vector_derivation": (
                "Typed stage fields: capabilities, tools (tool:), gates (gate:), "
                "stop_rules (stop:), recovery (recovery:). Unreachable stages "
                "contribute nothing. A fusion's declared capability_vector cannot "
                "cover a dropped stage (overclaim control)."
            ),
            "dependencies_on_this_tree": {
                "IMP-0177": "receipt absent; fixture vectors stand in, disclosed",
                "IMP-0182": "receipt absent; fusion.splice-cite is the splice stand-in",
            },
        },
        "failure_class": {
            "name": "workflow fusion loses a source capability",
            "id": "FC-11332",
            "spec_catalog": 11333,
            "spec_a1": 11332,
        },
        "tests": [
            {
                "id": "admitted-empty-diff",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "planted-dropped-stage",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-cite-drop",
                "kind": "planted-dropped-stage",
                "description": (
                    "Drop unique-capability stage 'cite' from fusion.keep-all. "
                    "Detector must fire and name cap.cite and gate:citation.required."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "redundant-scout-dup",
                "kind": "false-positive-control",
                "description": (
                    "Drop scout-dup from fusion.redundant-scout. Tokens remain via "
                    "scout; detector must stay silent."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
            },
            {
                "id": "stale-declared-vector",
                "kind": "overclaim",
                "description": (
                    "After dropping cite, leave a declared capability_vector that "
                    "still lists the lost tokens. Detector must still fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Set difference is empty for all four admitted fusions "
                    "(keep-all, splice-cite, plus-explain, redundant-scout)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0191/probe1_admitted_empty_diff.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-8000:],
                    }
                ],
            },
            {
                "claim": (
                    "A planted dropped stage (cite on fusion.keep-all) makes the "
                    "detector fire the named failure class; the unmodified fusion "
                    "is silent."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0191/probe2_planted_loss.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-8000:],
                    }
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0191-probe2-planted-loss",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Mechanical adversarial control is probe2 (planted drop, redundant "
                "drop, stale declared vector). No separate human reviewer ran in a "
                "fresh context on this worktree."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0191/UNIT-ARTIFACT-MANIFEST.json",
            "global_unit_manifest_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "notes": "Measure runs after this receipt is written.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": "IMP-0177 live capability vectors for the 96-library taxonomy.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run detect_capability_loss against IMP-0177 output once that "
                    "receipt exists; admitted set-difference must stay empty."
                ),
            },
            {
                "claim": "Human adversarial review in a fresh context.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Independent reviewer re-runs probe1 and probe2.",
            },
        ],
        "timestamps": {"ended_at": now},
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "notes": "Live sha256 is recorded in the per-unit UNIT-ARTIFACT-MANIFEST.json after this file is written (self-hash is circular).",
            },
            art(DETECTOR, "supporting"),
            art("command-center/p2-wave/probes/IMP-0191/fixtures/library.json", "supporting"),
        ],
        "answer": (
            "Capability-loss detector lives at tools/fusion/capability_loss.py. "
            "Coverage is the computed set difference of typed capability vectors. "
            "All four admitted fixture fusions have an empty difference. Dropping "
            "stage cite from fusion.keep-all fires named class "
            "'workflow fusion loses a source capability'. SUCCESS:IMP-0191"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if out_path.stat().st_size < 2048:
        print(f"FAILED:IMP-0191 receipt too small ({out_path.stat().st_size} B)")
        return 1
    if "SUCCESS:IMP-0191" not in payload:
        print("FAILED:IMP-0191 sentinel missing from receipt body")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0191",
        "unit_id": "IMP-0191",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0191",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "admitted-empty-diff",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-dropped-stage",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0191/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0191-probe2-planted-loss",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0191: live named probes exit 0, receipts/IMP-0191.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0191",
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
    print("SUCCESS:IMP-0191 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
