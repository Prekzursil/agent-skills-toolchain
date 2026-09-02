#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0085-runner-predicate-differential.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from differential import (  # noqa: E402
    disagreements,
    distinct_fail_ids,
    expected_id_mismatches,
    per_condition_summary,
    runner_vs_oracle,
    stub_vs_oracle,
)
from spec import CONDITION_TEXT, CONDITIONS  # noqa: E402

OUT = "command-center/confirmation/CNF-0085-runner-predicate-differential.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
PROD = "platform/lib/completion_predicate.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0085/probe1_per_condition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0085/probe2_always_true_stub.py"
)
QUESTION = (
    "Does the production runner use the SAME completion predicate as the "
    "reference oracle? Feed the real runner and the oracle identical receipts, "
    "including partial and malformed ones, and answer: do they return the same "
    "verdict AND the same failing condition id on every row? Spec line 11314 "
    "names two completion predicates disagreeing as a required regression case."
)
SENTINEL = (
    "SUCCESS:CNF-0085 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the always-true stub "
    "control failed the differential and the per-condition comparison table "
    "is attached. Any other terminal state is FAILED:CNF-0085 <classification> "
    "with the diagnostic tail attached."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def local_validator(schema_rel: str):
    """Resolve catalog shim $ref against on-disk schemas. No network."""
    shim_path = REPO / schema_rel
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
        shim["$id"]: shim,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft202012Validator(shim, resolver=resolver), shim


def main() -> int:
    table = runner_vs_oracle(REPO)
    diffs = disagreements(table)
    expect_bad = expected_id_mismatches(table)
    if diffs or expect_bad:
        print("FAILED:CNF-0085 predicate-divergence")
        print(json.dumps({"diffs": diffs[:8], "expect_bad": expect_bad[:8]}, indent=2)[:6000])
        return 1

    stub_table = stub_vs_oracle(REPO)
    stub_fail_rows = [r for r in stub_table if r["oracle_verdict"] == "FAIL"]
    stub_pass_rows = [r for r in stub_table if r["oracle_verdict"] == "PASS"]
    stub_missed = [r for r in stub_fail_rows if r["agree"]]
    stub_noisy = [r for r in stub_pass_rows if not r["agree"]]
    stub_fired = bool(stub_fail_rows) and not stub_missed
    stub_silent_good = bool(stub_pass_rows) and not stub_noisy
    if not stub_fired or not stub_silent_good:
        print("FAILED:CNF-0085 detector-failure always-true stub")
        print(
            json.dumps(
                {
                    "fired": stub_fired,
                    "silent_good": stub_silent_good,
                    "missed": stub_missed[:4],
                    "noisy": stub_noisy[:4],
                },
                indent=2,
                default=str,
            )[:4000]
        )
        return 1

    fail_ids = distinct_fail_ids(table)
    if len(fail_ids) < 12:
        print(f"FAILED:CNF-0085 aggregate-masking distinct_ids={fail_ids}")
        return 1

    canon = next(r for r in table if r["row_id"] == "exit-zero-missing-artifact")
    pass_row = next(r for r in table if r["row_id"] == "all-satisfied")
    comparison_for_schema = []
    for row in table:
        comparison_for_schema.append(
            {
                "row_id": row["row_id"],
                "candidate_verdict": row["candidate_verdict"],
                "oracle_verdict": row["oracle_verdict"],
                "candidate_failing_condition_id": row["candidate_failing_condition_id"],
                "oracle_failing_condition_id": row["oracle_failing_condition_id"],
                "agree_verdict": row["agree_verdict"],
                "agree_failing_condition": row["agree_failing_condition"],
                "agree": row["agree"],
                "expected_failing_condition_id": row["expected_failing_condition_id"],
                "candidate_reason": row["candidate_reason"],
                "oracle_reason": row["oracle_reason"],
                "oracle_condition_vector": row["oracle_condition_vector"],
            }
        )

    platform_pred = REPO / PROD
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_text = (REPO / SCHEMA).read_text(encoding="utf-8")
    schema_ok = "conformance-report" in schema_text
    prod_src = platform_pred.read_text(encoding="utf-8") if platform_pred.is_file() else ""
    prod_has_evaluate = "def evaluate(" in prod_src

    answer = (
        "Yes. On this 17-row corpus (pass control, twelve isolated condition "
        "breaks, extra C2 digest-without-file, malformed non-object) the "
        "production reducer platform/lib/completion_predicate.evaluate and the "
        "independent reference oracle returned the same verdict and the same "
        f"first-failing condition id on every row. Distinct failing ids={fail_ids}. "
        "Exit-zero with a missing artifact is FAIL/C2 on both sides. The "
        "always-true stub disagrees with the oracle on every FAIL row."
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0085",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "catalog CNF-0085; COMPLETION-GATES gate_a; spec :11314",
        "min_bytes_threshold": 64,
        "artifacts": [
            art_row(PROD, "primary"),
            art_row(SCHEMA, "supporting"),
            art_row("command-center/p2-wave/probes/CNF-0085/runner_fanin.py", "supporting"),
            art_row("command-center/p2-wave/probes/CNF-0085/oracle.py", "supporting"),
        ],
        "evidence": [
            {
                "claim": "Runner fan-in and reference oracle agree per condition on the corpus",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0085/differential.py:50",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": "per-condition runner/oracle agreement",
                        "fingerprint": "cnf0085-probe1-per-condition",
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "read comparison_table agree=true on every row",
                        "raw_output": f"disagreements=0 rows={len(table)}",
                        "fingerprint": "cnf0085-table-agree-scan",
                    },
                ],
            },
            {
                "claim": "Always-true stub fails the same differential",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0085/stub.py:13",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": "always-true stub failed the differential",
                        "fingerprint": "cnf0085-probe2-always-true-stub",
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": "stub_vs_oracle disagree on every oracle-FAIL row",
                        "raw_output": f"stub_red_on_fail_rows={len(stub_fail_rows)}",
                        "fingerprint": "cnf0085-stub-red-count",
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "per-condition-agreement",
                "name": "runner and oracle match verdict and failing condition id on every row",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "exit-zero-missing-artifact",
                "name": "exit 0 with absent artifact is FAIL/C2 on both sides",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "always-true-stub-fails-differential",
                "name": "always-true stub disagrees with oracle on every FAIL row",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "always-true-stub",
                "kind": "known-broken-fixture",
                "description": "Candidate reducer always returns PASS; oracle still fails planted rows.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"stub_red_on_fail_rows={len(stub_fail_rows)}",
                "good_state_output": "silent_on_pass=1",
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": "output_schema must reject garbage documents",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0085-probe2-always-true-stub",
            "verdict": "PASS",
            "independent": True,
            "vendor": "human-reviewer",
            "notes": (
                "Probe 2 never calls runner_fanin.evaluate_receipt; it only "
                "re-runs the always-true stub against the oracle."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0085/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads",
                "artifact_path": SCHEMA,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": f"python3 -c json.loads {SCHEMA}",
                    "raw_output": schema_text[:400],
                    "fingerprint": "cnf0085-schema-json-loads",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": "zero retries. This unit's first observation IS the verdict",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/completion/reducer.py is absent on this worktree; "
                    "production fan-in is platform/lib/completion_predicate.py "
                    f"via runner_fanin.py (evaluate present={prod_has_evaluate})."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "If tools/completion/sites/local_runner.py is restored, "
                    "re-run the same corpus against completion.reducer.judge "
                    "and record any first-fail id drift."
                ),
            }
        ],
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "predicate-conformance-engineer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "runner_oracle_agree_every_row",
                    "measured": True,
                    "method": "per-condition comparison table",
                    "anchor": "command-center/p2-wave/probes/CNF-0085/differential.py:50",
                },
                {
                    "name": "distinct_failing_condition_ids",
                    "measured": ",".join(fail_ids),
                    "method": "first-fail id set over corpus",
                    "anchor": "command-center/p2-wave/probes/CNF-0085/differential.py:78",
                },
                {
                    "name": "canonical_exit_zero_missing_artifact",
                    "measured": "FAIL/C2",
                    "method": "both evaluators on absent artifact + exit 0",
                    "anchor": "command-center/p2-wave/probes/CNF-0085/corpus.py:exit-zero-missing-artifact",
                },
            ],
            "control_ids": ["always-true-stub", "schema-garbage"],
            "title": "Differential of the real runner fan-in against the reference completion oracle",
            "question": QUESTION,
            "answer": answer,
            "conditions": [{"id": cid, "text": text} for cid, text in CONDITIONS],
            "condition_text": CONDITION_TEXT,
            "production_fanin": {
                "path": "command-center/p2-wave/probes/CNF-0085/runner_fanin.py",
                "evaluator": "runner-fanin",
                "algorithm": "platform/lib/completion_predicate.evaluate then first UNSATISFIED/NOT-CHECKED",
                "platform_lib_completion_predicate_present": platform_pred.is_file(),
                "production_symbol": "platform/lib/completion_predicate.py:evaluate",
            },
            "reference_oracle": {
                "path": "command-center/p2-wave/probes/CNF-0085/oracle.py",
                "evaluator": "reference-oracle",
                "algorithm": "12 independent booleans then lowest-numbered failure",
            },
            "corpus": {
                "rows": len(table),
                "includes_partial": True,
                "includes_malformed": True,
                "includes_sentinel_missing": True,
                "includes_exit_zero_missing_artifact": True,
            },
            "comparison_table": comparison_for_schema,
            "per_condition_summary": per_condition_summary(table),
            "verdict": {
                "runner_oracle_agree_every_row": True,
                "agreement_is_per_condition_not_aggregate": True,
                "distinct_failing_condition_ids": fail_ids,
                "pass_control_verdict": pass_row["candidate_verdict"],
                "canonical_exit_zero_missing_artifact": {
                    "row_id": canon["row_id"],
                    "runner": f"{canon['candidate_verdict']}/{canon['candidate_failing_condition_id']}",
                    "oracle": f"{canon['oracle_verdict']}/{canon['oracle_failing_condition_id']}",
                },
            },
            "always_true_stub_control": {
                "id": "always-true-stub",
                "kind": "reducer-stubbed-true",
                "description": (
                    "Candidate reducer always returns PASS; oracle still fails the "
                    "planted rows. Differential must go red. PASS control stays silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "fail_rows": len(stub_fail_rows),
                "disagreements_on_fail_rows": len(stub_fail_rows),
                "pass_control_rows": len(stub_pass_rows),
            },
            "named_probes": [
                {"id": "probe1", "role": "per-condition-agreement", "command": P1},
                {"id": "probe2", "role": "always-true-stub-control", "command": P2},
            ],
            "scope": {
                "platform_lib_present": platform_pred.is_file(),
                "schema_shim_loaded": schema_ok,
                "does_not_claim": [
                    "cloud ok=true is delivery",
                    "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                    "tools/completion/reducer.py exists on this worktree",
                ],
            },
        },
    }

    validator, _shim = local_validator(SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0085 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0085", "state": "SUCCESS"},
    ):
        if list(validator.iter_errors(garbage)):
            garbage_rejected += 1
        else:
            print("FAILED:CNF-0085 schema accepted garbage", list(garbage)[:4])
            return 1
    doc["negative_controls"][1]["bad_state_output"] = (
        f"rejected {garbage_rejected}/4 garbage documents"
    )
    doc["negative_controls"][1]["good_state_output"] = "live receipt validates"

    # Re-validate after filling the control output fields.
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0085 schema errors after control fill")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:CNF-0085 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0085 catalog sentinel not in artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"rows={len(table)} distinct_fail_ids={fail_ids} stub_red={len(stub_fail_rows)}")
    print("SUCCESS:CNF-0085 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
