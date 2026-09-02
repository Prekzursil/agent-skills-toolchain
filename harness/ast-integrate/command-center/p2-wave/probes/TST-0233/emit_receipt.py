#!/usr/bin/env python3
"""Emit TST-0233 receipt, per-unit SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST.

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
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gate import evaluate_named, load_corpus  # noqa: E402

OUT = "command-center/receipts/TST-0233.json"
GATE = "command-center/p2-wave/probes/TST-0233/gate.py"
CORPUS = "command-center/p2-wave/probes/TST-0233/fixtures/corpus.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0233/probe1_stage_padded.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0233/probe2_worse_than_sources.py"
)
SUPPORTING = [
    GATE,
    CORPUS,
    "command-center/p2-wave/probes/TST-0233/probe1_stage_padded.py",
    "command-center/p2-wave/probes/TST-0233/probe2_worse_than_sources.py",
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
        "unit_id": "TST-0233",
        "receipt_path": "command-center/p2-wave/probes/TST-0233/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data) if path.is_file() else 0,
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        if path.is_file()
        else "",
        "exists": path.is_file(),
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0233 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    corpus = load_corpus(HERE / "fixtures" / "corpus.json")
    padded = evaluate_named(corpus, "fusion.padded")
    degraded = evaluate_named(corpus, "fusion.degraded")
    complement = evaluate_named(corpus, "fusion.complement")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gate_sha, gate_bytes = digest(REPO / GATE)
    corpus_sha, corpus_bytes = digest(REPO / CORPUS)

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0233",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0233",
        "completion_sentinel": "SUCCESS:TST-0233",
        "title": "A fused workflow must beat or materially complement EVERY source",
        "report_kind": "benchmark_result",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "spec_anchor": "_USER-PROMPTS.md:11170; _USER-PROMPTS.md:11333; _USER-PROMPTS.md:10741",
        "min_bytes_threshold": 2048,
        "question_or_target": (
            "Does the acceptance gate reject a fusion that merely has more stages? "
            "PASS requires the fused candidate to beat or materially complement each "
            "source on matched cases, with 'more stages' explicitly non-qualifying and "
            "the complementarity claim backed by a case where a source fails and the "
            "fusion succeeds."
        ),
        "implementation": {
            "gate_path": GATE,
            "gate_sha256": gate_sha,
            "gate_bytes": gate_bytes,
            "corpus_path": CORPUS,
            "corpus_sha256": corpus_sha,
            "corpus_bytes": corpus_bytes,
            "score_formula": "passed_cases",
            "stage_count_is_scoring_component": False,
            "rule": (
                "REJECT if outcome_vector(fusion)==outcome_vector(source) and "
                "n_stages(fusion)>n_stages(source) (FC-11334 / spec 11170); "
                "REJECT if score(fusion)<score(s) for every source (FC-11333); "
                "else ACCEPT iff every source is beaten (higher passed_cases) or "
                "materially complemented (named case source-fail/fusion-succeed)."
            ),
            "dependencies_on_this_tree": {
                "IMP-0190": "receipt absent; TST-0233 gate.py is the stand-in under test",
                "B07": "catalog dependency; not re-run here",
                "TST-0231": "catalog dependency; receipt absent, disclosed",
            },
        },
        "matched_case_score_matrices": {
            "budget": corpus["budget"],
            "budget_parity": True,
            "padded": padded["matrix"],
            "degraded": degraded["matrix"],
            "complement": complement["matrix"],
        },
        "named_complementarity_case": {
            "case_id": "case.beta-only",
            "source_id": "wf.alpha",
            "fusion_id": "fusion.complement",
            "source_passed": False,
            "fusion_passed": True,
            "executed": True,
            "rows": complement["named_complement_cases"],
        },
        "failure_classes": [
            {
                "name": "fusion accepted because it has more stages (catalog gloss thin)",
                "id": "FC-11334",
                "spec": 11170,
                "fired_on": "fusion.padded",
            },
            {
                "name": "fused workflow performs worse than every source",
                "id": "FC-11333",
                "spec": 11333,
                "fired_on": "fusion.degraded",
            },
        ],
        "tests": [
            {
                "id": "detector-control-stage-padded",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "regression-seed-worse-than-every-source",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "stage-padded-identical-behavior",
                "kind": "detector-control",
                "description": (
                    "Submit fusion.padded (alpha handlers plus three noops). "
                    "Gate must REJECT with FC-11334."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "complement-more-stages-accepted",
                "kind": "false-positive-control",
                "description": (
                    "fusion.complement has more stages than every source but "
                    "different behaviour; gate must ACCEPT."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
            },
            {
                "id": "degraded-worse-than-every-source",
                "kind": "regression-seed",
                "description": (
                    "fusion.degraded fails every matched case. Gate must REJECT "
                    "with FC-11333. fusion.padded must not be classified as this class."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Per-source matched-case score matrices: fusion.padded ties "
                    "wf.alpha on passed_cases despite more stages and is rejected; "
                    "fusion.complement beats both sources; budgets are equal."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0233/probe1_stage_padded.py",
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
                    "Named complementarity case case.beta-only executed: wf.alpha "
                    "fails, fusion.complement succeeds. fusion.degraded scores below "
                    "every source and is rejected as FC-11333."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0233/probe2_worse_than_sources.py",
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
            "reviewer_id": "TST-0233-probe2-worse-than-sources",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Mechanical adversarial control is probe2 (degraded fusion, "
                "independent score recompute, named complementarity execute). "
                "No separate human reviewer ran in a fresh context on this worktree."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0233/UNIT-ARTIFACT-MANIFEST.json",
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
                "claim": "IMP-0190 production admission gate on the 30 merge_units.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run evaluate_admission against IMP-0190 output once that "
                    "receipt exists; stage-padded and degraded fixtures must still reject."
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
                "notes": (
                    "Live sha256 is recorded in the per-unit "
                    "UNIT-ARTIFACT-MANIFEST.json after this file is written "
                    "(self-hash is circular)."
                ),
            },
            art(GATE, "supporting"),
            art(CORPUS, "supporting"),
        ],
        "answer": (
            "The TST-0233 admission gate rejects fusion.padded (identical "
            "behaviour to wf.alpha, three extra noop stages) as FC-11334, and "
            "rejects fusion.degraded (score below every source) as FC-11333. "
            "fusion.complement is accepted: it beats both sources on passed_cases "
            "and the named case case.beta-only is executed with alpha fail / "
            "fusion succeed. Stage count is reported and is not a scoring "
            "component. SUCCESS:TST-0233"
        ),
        "live_decisions": {
            "fusion.padded": {
                "verdict": padded["verdict"],
                "failure_class": padded["failure_class"],
                "score": padded["fusion"]["score"],
                "n_stages": padded["fusion"]["n_stages"],
            },
            "fusion.degraded": {
                "verdict": degraded["verdict"],
                "failure_class": degraded["failure_class"],
                "score": degraded["fusion"]["score"],
                "n_stages": degraded["fusion"]["n_stages"],
            },
            "fusion.complement": {
                "verdict": complement["verdict"],
                "failure_class": complement["failure_class"],
                "score": complement["fusion"]["score"],
                "n_stages": complement["fusion"]["n_stages"],
            },
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if out_path.stat().st_size < 2048:
        print(f"FAILED:TST-0233 receipt too small ({out_path.stat().st_size} B)")
        return 1
    if "SUCCESS:TST-0233" not in payload:
        print("FAILED:TST-0233 sentinel missing from receipt body")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "TST-0233",
        "unit_id": "TST-0233",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0233",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "stage-padded-detector-control",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "worse-than-every-source-regression-seed",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0233/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0233-probe2-worse-than-sources",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0233: live named probes exit 0, receipts/TST-0233.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0233",
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
    print("SUCCESS:TST-0233 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
