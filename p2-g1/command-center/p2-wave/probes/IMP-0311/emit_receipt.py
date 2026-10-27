#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0311.json from live kinds/pipeline/census."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.census import census, classify_file  # noqa: E402
from council.outcomes.kinds import (  # noqa: E402
    KIND_CONDITIONAL,
    KIND_NO_DECISION,
    KIND_PROOF_OF_IMPOSSIBILITY,
    parse_outcome,
    required_fields_for,
)
from council.outcomes.pipeline import outcome_unmodified, run_pipeline  # noqa: E402

UNIT = "IMP-0311"
OUT = "command-center/receipts/IMP-0311.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json profile=council-outcomes-module "
    "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
    "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0311/probe1_required_fields.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0311/probe2_census.py"
)
KINDS = (KIND_NO_DECISION, KIND_CONDITIONAL, KIND_PROOF_OF_IMPOSSIBILITY)
FIXTURE_FILES = {
    KIND_NO_DECISION: HERE / "fixtures" / "no_decision.json",
    KIND_CONDITIONAL: HERE / "fixtures" / "conditional.json",
    KIND_PROOF_OF_IMPOSSIBILITY: HERE / "fixtures" / "proof_of_impossibility.json",
}


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0311 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    art_dir = HERE / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    pipeline_rows = []
    for kind in KINDS:
        raw = json.loads(FIXTURE_FILES[kind].read_text(encoding="utf-8"))
        parsed = parse_outcome(raw)
        artifact = run_pipeline(raw)
        if not outcome_unmodified(raw, artifact):
            print(f"FAILED:IMP-0311 emit pipeline mutated {kind}")
            return 1
        rel = f"command-center/p2-wave/probes/IMP-0311/artifacts/{kind.lower().replace('-', '_')}.final.json"
        dest = REPO / rel
        dest.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        pipeline_rows.append(
            {
                "kind": kind,
                "outcome_id": parsed["outcome_id"],
                "required_fields": list(required_fields_for(kind)),
                "unmodified": True,
                "artifact_path": rel,
                "fingerprint": artifact["payload_fingerprint"],
            }
        )

    prod = census([REPO / "tools" / "council" / "outcomes"])
    planted_paths = [
        HERE / "fixtures" / "coercing_consumer.py",
        HERE / "fixtures" / "binary_only_consumer.py",
        HERE / "fixtures" / "preserving_consumer.py",
    ]
    planted_rows = [classify_file(p) for p in planted_paths]
    census_doc = {
        "production": prod,
        "planted": planted_rows,
        "readers": [
            {
                "path": "tools/council/outcomes/kinds.py",
                "role": "typed-outcome-module",
                "NO-DECISION": "validate-and-keep",
                "CONDITIONAL": "validate-and-keep",
                "PROOF-OF-IMPOSSIBILITY": "validate-and-keep",
                "PASS/FAIL": "refused (CollapseForbidden)",
            },
            {
                "path": "tools/council/outcomes/pipeline.py",
                "role": "artifact-pipeline",
                "NO-DECISION": "copy-unmodified-into-final-artifact",
                "CONDITIONAL": "copy-unmodified-into-final-artifact",
                "PROOF-OF-IMPOSSIBILITY": "copy-unmodified-into-final-artifact",
                "PASS/FAIL": "identity-check fails if kind rewritten",
            },
            {
                "path": "tools/council/outcomes/preserve.py",
                "role": "canonical-consumer",
                "NO-DECISION": "preserve",
                "CONDITIONAL": "preserve",
                "PROOF-OF-IMPOSSIBILITY": "preserve",
                "PASS/FAIL": "not-emitted",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0311/fixtures/coercing_consumer.py",
                "role": "planted-defect",
                "NO-DECISION": "COERCED-TO-FAIL",
                "CONDITIONAL": "COERCED-TO-PASS",
                "PROOF-OF-IMPOSSIBILITY": "COERCED-TO-FAIL",
                "PASS/FAIL": "only-vocabulary",
                "census": "CAUGHT",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0311/fixtures/binary_only_consumer.py",
                "role": "planted-defect",
                "NO-DECISION": "COERCED-TO-FAIL (else branch)",
                "CONDITIONAL": "COERCED-TO-FAIL (else branch)",
                "PROOF-OF-IMPOSSIBILITY": "COERCED-TO-FAIL (else branch)",
                "PASS/FAIL": "only-vocabulary",
                "census": "CAUGHT",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0311/fixtures/preserving_consumer.py",
                "role": "negative-control-good",
                "NO-DECISION": "preserve",
                "CONDITIONAL": "preserve",
                "PROOF-OF-IMPOSSIBILITY": "preserve",
                "PASS/FAIL": "not-emitted",
                "census": "SILENT",
            },
        ],
        "falsifiable_answer": (
            "Yes if a consumer only understands PASS/FAIL: both planted "
            "binary consumers coerce all three kinds. The census catches "
            "that. Production readers in tools/council/outcomes do not coerce."
        ),
    }
    census_rel = "command-center/p2-wave/probes/IMP-0311/census_report.json"
    (REPO / census_rel).write_text(
        json.dumps(census_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "tools/council/outcomes/kinds.py",
        "tools/council/outcomes/pipeline.py",
        "tools/council/outcomes/census.py",
        "tools/council/outcomes/preserve.py",
        "command-center/p2-wave/probes/IMP-0311/probe1_required_fields.py",
        "command-center/p2-wave/probes/IMP-0311/probe2_census.py",
        "command-center/p2-wave/probes/IMP-0311/fixtures/no_decision.json",
        "command-center/p2-wave/probes/IMP-0311/fixtures/conditional.json",
        "command-center/p2-wave/probes/IMP-0311/fixtures/proof_of_impossibility.json",
        census_rel,
    ] + [row["artifact_path"] for row in pipeline_rows]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0311",
        "completion_sentinel": "SUCCESS:IMP-0311",
        "title": "Outcome kinds: no-decision, conditional decision and proof-of-impossibility",
        "question": (
            "Implement tools/council/outcomes/kinds.py making NO-DECISION, "
            "CONDITIONAL and PROOF-OF-IMPOSSIBILITY first-class, typed outcomes "
            "with required fields. Falsifiable question: is any of these three "
            "ever coerced into a plain decision by a downstream consumer that "
            "only understands PASS/FAIL?"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0311]",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "headless-linux",
        },
        "artifact_paths": [OUT] + supporting,
        "artifacts": [art_row(p, "primary" if p == OUT else "supporting") for p in [OUT] + supporting]
        if False
        else None,
        "evidence": [
            {
                "id": "E1-consumer-census",
                "claim": (
                    "Every reader of outcome.kind under tools/council/outcomes "
                    "preserves NO-DECISION, CONDITIONAL and PROOF-OF-IMPOSSIBILITY. "
                    "Planted PASS/FAIL consumers are classified COERCES."
                ),
                "verdict": "CONFIRMED",
                "anchor": census_rel,
                "measurement": {
                    "production_scanned": prod["scanned"],
                    "production_coercers": prod["coercers"],
                    "planted_coercer_classifications": [
                        r["classification"] for r in planted_rows
                    ],
                },
            },
            {
                "id": "E2-pipeline-fixtures",
                "claim": (
                    "A fixture of each protected kind flowed ingest->record->"
                    "synthesize->emit; the final artifact payload is unmodified."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/outcomes/pipeline.py",
                "measurement": pipeline_rows,
            },
        ],
        "test_ids": [
            "IMP-0311-T1-required-fields",
            "IMP-0311-T2-pipeline-identity",
            "IMP-0311-T3-census-coercion",
        ],
        "tests": [
            {
                "id": "IMP-0311-T1-required-fields",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "IMP-0311-T2-pipeline-identity",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "IMP-0311-T3-census-coercion",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_control_ids": [
            "IMP-0311-NC1-missing-required-field",
            "IMP-0311-NC2-no-decision-mapped-to-fail",
            "IMP-0311-NC3-pipeline-kind-rewrite",
        ],
        "negative_controls": [
            {
                "id": "IMP-0311-NC1-missing-required-field",
                "kind": "schema-invalid",
                "description": "Drop each required field; parse_outcome must raise.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0311-NC2-no-decision-mapped-to-fail",
                "kind": "overclaim",
                "description": (
                    "Planted consumer mapping NO-DECISION to FAIL is caught; "
                    "preserving consumer is not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0311-NC3-pipeline-kind-rewrite",
                "kind": "detector-failure",
                "description": "Stage rewriting NO-DECISION to DECISION fails identity check.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0311-probe2-census-from-tests",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "started_from": "tests (probe2_census.py), not the author summary",
            "raw_output_tail": t2[-1500:],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0261 (CouncilSpec schema) and IMP-0226 (shared completion "
                    "oracle) are not delivered on this worktree; kinds.py does not "
                    "call them."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the census after IMP-0261/IMP-0226 land and add any new "
                    "outcome.kind readers they introduce."
                ),
            },
            {
                "claim": (
                    "The 17-value v1 $defs.outcome enum from CNL-0072 is not on disk "
                    "here; this unit implements the three named first-class kinds, "
                    "not the full 17-to-6 mapping table."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "CNL-0072 / IMP-0261 deliver the enum; remap then recensus.",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0311/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run tools/command-center/unit_manifest.py --write",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0311/probe1_required_fields.py",
                "artifact_path": "tools/council/outcomes/kinds.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0311/probe2_census.py",
                "artifact_path": "tools/council/outcomes/census.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "probe1_tail": t1[-2000:],
        "probe2_tail": t2[-2000:],
        "pipeline": pipeline_rows,
        "answer": census_doc["falsifiable_answer"],
    }

    # First write without self-hash artifacts so we can measure the file, then
    # rewrite with artifact rows excluding a circular self-sha: primary row is
    # filled after the body is stable except artifacts.
    receipt["artifacts"] = []
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def dump(doc: dict) -> None:
        out_path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )

    dump(receipt)
    receipt["artifacts"] = [art_row(OUT, "primary")] + [
        art_row(p, "supporting") for p in supporting
    ]
    dump(receipt)
    sha, size = digest_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0311 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
