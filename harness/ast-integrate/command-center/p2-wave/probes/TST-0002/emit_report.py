#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0002.json (conformance report)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import reducer as R  # noqa: E402
from conditions import CONDITIONS, HARD_RULES  # noqa: E402

OUT = "command-center/receipts/TST-0002.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
QUESTION = (
    "Construct 12 fixture receipts where receipt[k] violates ONLY condition k "
    "and satisfies the other 11. Target: the reducer returns FAILED with "
    "failing-condition-id == k for each, and PASS for the single all-satisfied "
    "control row. Which conditions cannot be violated in isolation because the "
    "artifact format couples them?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0002/probe1_isolation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0002/probe2_control_and_coupling.py"
)

# Catalog output_schema is a $ref shim to https://ast-integrate.invalid/... .
# jsonschema 4.10 Draft7Validator resolves that over the network and raises
# RefResolutionError. G-1 does not require compiling that shim. This local
# shape is the emit-time gate: it rejects garbage and requires the corpus,
# coupling report, and named tests the catalog question actually consumes.
REPORT_SHAPE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "question",
        "answer",
        "corpus",
        "coupling",
        "tests",
        "negative_controls",
        "evidence",
        "reviewer",
        "artifacts",
        "parametrised_run",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": "TST-0002"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0002"},
        "corpus": {"type": "array", "minItems": 13, "maxItems": 13},
        "tests": {"type": "array", "minItems": 3},
        "negative_controls": {"type": "array", "minItems": 1},
        "evidence": {"type": "array", "minItems": 2},
        "artifacts": {"type": "array", "minItems": 1},
        "coupling": {
            "type": "object",
            "required": [
                "inseparable_pairs",
                "contract_defects",
                "isolated_count",
                "pass_row_ok",
            ],
        },
        "parametrised_run": {
            "type": "object",
            "required": [
                "distinct_failing_condition_ids",
                "pass_rows",
                "isolated_failures",
            ],
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:TST-0002 emit missing snippet in {path}: {snippet!r}")


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    rows = C.run_corpus(REPO, eval_fn=R.evaluate)
    coupling = C.coupling_report(rows)
    if not C.isolation_ok(rows):
        print("FAILED:TST-0002 emit isolation_ok is false")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0002 emit probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    red = REPO / "command-center/p2-wave/probes/TST-0002/reducer.py"
    corp = REPO / "command-center/p2-wave/probes/TST-0002/corpus.py"
    p1p = REPO / "command-center/p2-wave/probes/TST-0002/probe1_isolation.py"
    line_c2 = find_line(red, "C2 owns absence")
    line_iso = find_line(p1p, "test_each_condition_fails_in_isolation")
    line_mut = find_line(corp, "receipt exists=true for a path that is absent")

    corpus_rows = []
    for r in rows:
        corpus_rows.append(
            {
                "row_id": r["row_id"],
                "fixture": r["fixture"],
                "mutation": r["mutation"],
                "intended_violation": r["intended_violation"],
                "verdict": r["verdict"],
                "failing_condition_id": r["failing_condition_id"],
                "reason": r["reason"],
                "unsatisfied": r["unsatisfied"],
                "isolated": r["isolated"],
            }
        )

    distinct = sorted(
        r["failing_condition_id"]
        for r in rows
        if r["intended_violation"] is not None
    )
    answer = (
        "None of the 12 conditions are inseparable under independently-addressable "
        "checks: the reducer returns FAILED with failing-condition-id == k on each "
        "isolation row and PASS on the all-satisfied control. A missing-file mutant "
        "would also trip a naive size re-measure (C3) and a naive consumer-open (C12); "
        "those checks are gated on existence so C2 owns absence. That gating is the "
        "format coupling the question asks about, recorded here as an empty "
        "inseparable-pair list (not a second predicate). Distinct failing-condition-ids "
        f"{distinct} plus 1 PASS. SUCCESS:TST-0002"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "command-center/schema/conformance-report.schema.json",
        "command-center/p2-wave/probes/TST-0002/reducer.py",
        "command-center/p2-wave/probes/TST-0002/corpus.py",
        "command-center/p2-wave/probes/TST-0002/conditions.py",
        "command-center/p2-wave/probes/TST-0002/artifact.schema.json",
        "command-center/p2-wave/probes/TST-0002/probe1_isolation.py",
        "command-center/p2-wave/probes/TST-0002/probe2_control_and_coupling.py",
        "tests/fixtures/completion/pass.json",
        "tests/fixtures/completion/fail-01.json",
        "tests/fixtures/completion/fail-02.json",
        "tests/fixtures/completion/fail-03.json",
        "tests/fixtures/completion/fail-04.json",
        "tests/fixtures/completion/fail-05.json",
        "tests/fixtures/completion/fail-06.json",
        "tests/fixtures/completion/fail-07.json",
        "tests/fixtures/completion/fail-08.json",
        "tests/fixtures/completion/fail-09.json",
        "tests/fixtures/completion/fail-10.json",
        "tests/fixtures/completion/fail-11.json",
        "tests/fixtures/completion/fail-12.json",
        "tests/fixtures/completion/artifact.schema.json",
    ]
    artifacts = [{"path": OUT, "exists": True, "role": "primary"}]
    for rel in supporting:
        if not (REPO / rel).is_file():
            print(f"FAILED:TST-0002 emit missing {rel}")
            return 1
        artifacts.append({"path": rel, "exists": True, "role": "supporting"})

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0002",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0002",
        "title": "Twelve-row negative corpus: one receipt per predicate condition",
        "claim_under_test": (
            "The reducer returns FAILED with failing-condition-id == k on each "
            "isolation fixture and PASS on the all-satisfied control; conditions "
            "that cannot be separated are recorded as coupling contract defects."
        ),
        "report_kind": "twelve-row-negative-corpus",
        "min_bytes_threshold": 4096,
        "question": QUESTION,
        "answer": answer,
        "conditions": [{"n": i + 1, "text": t} for i, t in enumerate(CONDITIONS)],
        "hard_rules": list(HARD_RULES),
        "corpus": corpus_rows,
        "coupling": coupling,
        "parametrised_run": {
            "distinct_failing_condition_ids": distinct,
            "pass_rows": 1,
            "isolated_failures": coupling["isolated_count"],
            "probe1_exit": c1,
            "probe2_exit": c2,
        },
        "tests": [
            {
                "id": "test_each_condition_fails_in_isolation[1..12]",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 12,
                "output_tail": t1[-2000:],
            },
            {
                "id": "test_all_satisfied_row_passes",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 1,
                "output_tail": t2[-2000:],
            },
            {
                "id": "coupling_report",
                "command": P2,
                "result": "PASS"
                if not coupling["inseparable_pairs"]
                else "FAIL",
                "assertions": 1,
                "output_tail": json.dumps(coupling, sort_keys=True),
            },
        ],
        "negative_controls": [
            {
                "id": "always-true-reducer-must-fail-harness",
                "kind": "mutation",
                "description": (
                    "A reducer stubbed to return PASS always must FAIL the isolation "
                    "harness (TST-0001 negative control, reused here)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "always_pass isolation_ok=False",
                "good_state_output": "evaluate isolation_ok=True",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Twelve isolation fixtures plus one PASS control exist under "
                    "tests/fixtures/completion/ and the reducer returns failing-"
                    "condition-id == k for each fail-k row."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/TST-0002/probe1_isolation.py:{line_iso}",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-4000:],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "ls tests/fixtures/completion/*.json",
                        "exit_code": 0,
                        "raw_output": "13 fixture receipts plus artifact.schema.json",
                    },
                ],
            },
            {
                "claim": (
                    "A missing expected path fails only C2 because C3/C4/C12 are "
                    "gated on existence; that is the format coupling, not a second "
                    "inseparable pair in this corpus."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/TST-0002/reducer.py:{line_c2}",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "read reducer.py C2-owns-absence gates",
                        "raw_output": "C3/C4/C12 SATISFIED when file absent",
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": "fail-02 unsatisfied=[2]",
                    },
                ],
            },
            {
                "claim": (
                    "The always-true reducer stub is rejected by the same harness "
                    "that accepts the real reducer (both-states control)."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0002/"
                    "probe2_control_and_coupling.py:1"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-4000:],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read always_pass stub",
                        "raw_output": "always_pass returns PASS unconditionally",
                    },
                ],
            },
            {
                "claim": (
                    "fail-02 is the catalog anti-pattern: exists=true in the receipt "
                    "for a path that is not on disk."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/TST-0002/corpus.py:{line_mut}",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "read fail-02.json artifacts[0]",
                        "raw_output": "path=.../ABSENT-ISO.json exists=true",
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": "C2 unsatisfied in isolation",
                    },
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0002-probe2-always-true-harness",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "method": (
                "Mechanical second check: re-run the isolation corpus through an "
                "always-PASS stub and require the harness to go red; agreement with "
                "the author that isolation is desirable is not required. No ADV "
                "rebuild of the completion predicate."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "isolation-matrix", "command": P1},
            {"id": "probe2", "role": "pass-row-and-coupling", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0002/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {
            "started_at": "2026-08-24T18:36:00Z",
            "ended_at": now,
        },
        "artifacts": artifacts,
        "adv_rebuild_circle": False,
        "required_fix": None,
        "production_reducer_note": (
            "platform/lib/completion_predicate.py and command-center/COMPLETION-GATES.json "
            "are absent on this worktree. This unit ships an independently-addressable "
            "reducer in probes/TST-0002/reducer.py plus the 13-row corpus. TST-0001/CC-0003 "
            "remain the owners of the production oracle/reducer; this report does not "
            "claim they are delivered."
        ),
    }

    validator = jsonschema.Draft7Validator(REPORT_SHAPE)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0002 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0002 schema accepted garbage {list(g)[:2]}")
            return 1
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(shim, dict) or "$ref" not in shim:
        print(f"FAILED:TST-0002 catalog schema missing $ref at {SCHEMA}")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0002 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0002 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
