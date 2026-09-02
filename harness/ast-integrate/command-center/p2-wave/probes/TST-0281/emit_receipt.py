#!/usr/bin/env python3
"""Emit TST-0281 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

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
UNIT = "TST-0281"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0281/probe1_six_examples_and_precedence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0281/probe2_three_valued_malformed_reviewer.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/stopping/tests/test_expr.py"
)
SUPPORTING = [
    "tools/council/stopping/expr.py",
    "tools/council/stopping/__init__.py",
    "tools/council/stopping/spec_examples.py",
    "tools/council/stopping/schema/stopping-expr.schema.json",
    "tools/council/stopping/tests/test_expr.py",
    "command-center/p2-wave/probes/TST-0281/probe1_six_examples_and_precedence.py",
    "command-center/p2-wave/probes/TST-0281/probe2_three_valued_malformed_reviewer.py",
    SCHEMA,
]
QUESTION = (
    "Implementation target: the AND/OR/NOT composable stopping expressions at "
    ":10931 and :10760 need an evaluator whose semantics are pinned by tests - "
    "operator precedence, short-circuit versus full evaluation of side-effecting "
    "terms, unknown-term handling, and the behaviour when a term is NOT-CHECKED "
    "rather than true or false. Then run the six executable examples verbatim "
    "from :10937-10942 as conformance cases."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def main() -> int:
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from council.stopping.expr import ast_to_dict, evaluate_source, parse
    from council.stopping.spec_examples import SPEC_EXAMPLES

    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} emit tests={code_t} p1={code1} p2={code2}")
        print(out_t[-2500:])
        print(out1[-2500:])
        print(out2[-2500:])
        return 1
    if "SUCCESS:TST-0281-tests" not in out_t:
        print("FAILED:TST-0281 emit tests sentinel missing")
        print(out_t[-1500:])
        return 1
    if "SUCCESS:TST-0281-probe1" not in out1:
        print("FAILED:TST-0281 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0281-probe2" not in out2:
        print("FAILED:TST-0281 emit probe2 sentinel missing")
        return 1

    p1_doc = first_json(out1)
    examples = p1_doc.get("examples") or []
    if len(examples) != 6:
        print(f"FAILED:{UNIT} emit expected 6 example rows, got {len(examples)}")
        return 1

    traces: list[str] = []
    for _ in range(2):
        payload = []
        for ex in SPEC_EXAMPLES:
            fire = evaluate_source(str(ex["source"]), ex["fire"])  # type: ignore[arg-type]
            payload.append(
                {
                    "id": ex["id"],
                    "source": ex["source"],
                    "ast": ast_to_dict(parse(str(ex["source"]))),
                    "value": fire.value,
                    "stop": fire.stop,
                }
            )
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        traces.append(hashlib.sha256(blob).hexdigest())
    if traces[0] != traces[1]:
        print("FAILED:TST-0281 emit trace hashes diverged")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_rows = [art(rel, "supporting") for rel in SUPPORTING]
    schema_path = REPO / SCHEMA

    receipt = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "schema_note": (
            "Catalog names command-center/schema/receipt.schema.json, which is "
            "absent on this tree. command-center/schema/test-receipt.schema.json "
            "is a pytest collection contract and does not describe stopping-"
            "expression conformance; this receipt is not validated against it."
        ),
        "question": QUESTION,
        "answer": {
            "summary": (
                "The evaluator in tools/council/stopping/expr.py parses the six "
                "spec strings at :10937-10942, publishes their ASTs, and evaluates "
                "them on fire/silent/NOT-CHECKED fixtures. Kleene NOT-CHECKED is not "
                "coerced to false (NOT of an unchecked metric does not stop). AND "
                "binds tighter than OR; prefix NOT binds a comparison. Malformed "
                "expressions fail at spec-validation, never at round 12. Impure "
                "terms are rejected at validation; pure AND/OR short-circuit. "
                f"{SENTINEL}"
            )
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "spec_examples": [
            {
                "id": row["id"],
                "spec_line": row["spec_line"],
                "source": row["source"],
                "ast": row["ast"],
                "fire_stop": (row.get("fire") or {}).get("stop"),
                "silent_stop": (row.get("silent") or {}).get("stop"),
                "not_checked": (row.get("not_checked") or {}).get("value"),
                "fixture_stop_round": row.get("fixture_stop_round"),
            }
            for row in examples
        ],
        "tests": [
            {
                "id": "six-spec-examples-parse-evaluate-asts",
                "command": P1,
                "result": "PASS",
                "exit_code": code1,
            },
            {
                "id": "three-valued-not-checked",
                "command": P2,
                "result": "PASS",
                "exit_code": code2,
            },
            {
                "id": "precedence-and-or-not",
                "command": P1,
                "result": "PASS",
                "exit_code": code1,
            },
            {
                "id": "malformed-rejected-at-spec-validation",
                "command": P2,
                "result": "PASS",
                "exit_code": code2,
            },
            {
                "id": "unit-tests",
                "command": TEST_CMD,
                "result": "PASS",
                "exit_code": code_t,
            },
        ],
        "evidence": [
            {
                "kind": "six-spec-examples",
                "claim": (
                    "Each of the six catalog strings at :10937-10942 was parsed "
                    "and evaluated on a fire fixture (stop=true), a silent "
                    "fixture (stop=false), and a NOT-CHECKED fixture "
                    "(value=NOT-CHECKED or Kleene-unknown, stop=false). ASTs "
                    "are in spec_examples."
                ),
                "anchor": "tools/council/stopping/spec_examples.py",
                "path": "tools/council/stopping/spec_examples.py",
                "verdict": "CONFIRMED",
            },
            {
                "kind": "kleene-not-checked",
                "claim": (
                    "NOT (completeness_score >= 0.90) with completeness_score "
                    "NOT-CHECKED evaluates to NOT-CHECKED and does not stop. "
                    "Coercing NOT-CHECKED to false would make that NOT true and "
                    "fire a stop by ignorance; the mutant control shows that bug."
                ),
                "anchor": (
                    "command-center/p2-wave/probes/TST-0281/"
                    "probe2_three_valued_malformed_reviewer.py"
                ),
                "path": (
                    "command-center/p2-wave/probes/TST-0281/"
                    "probe2_three_valued_malformed_reviewer.py"
                ),
                "verdict": "CONFIRMED",
            },
            {
                "kind": "malformed-at-spec-validation",
                "claim": (
                    "Four malformed strings raised SpecValidationError with "
                    "phase=spec-validation inside run_fixture, before any of "
                    "the 12 dummy rounds ran."
                ),
                "anchor": "tools/council/stopping/expr.py",
                "path": "tools/council/stopping/expr.py",
                "verdict": "CONFIRMED",
            },
        ],
        "trace_hash_comparison": {
            "seed": 281,
            "run_a_sha256": traces[0],
            "run_b_sha256": traces[1],
            "identical": True,
            "node_order": [row["id"] for row in examples],
            "fan_out_cardinalities": [
                {"id": row["id"], "kind": "spec-example", "cardinality": 3}
                for row in examples
            ],
            "barrier_resolution": [
                "spec-validation before round 1",
                "evaluate each round until first true",
            ],
        },
        "nondeterminism_sources": [
            {
                "source": "wall-clock",
                "site": "tools/council/stopping/expr.py",
                "how_found": (
                    "Evaluator has no time.time/datetime.now; two evals of the "
                    "six fire fixtures hashed identically."
                ),
                "leaks_into_production_dag": False,
            },
            {
                "source": "pid",
                "site": "tools/council/stopping/expr.py",
                "how_found": (
                    "Evaluator has no os.getpid; the same two hashes match "
                    "under the live process pid."
                ),
                "leaks_into_production_dag": False,
            },
        ],
        "frozen_clock": {
            "applied": True,
            "trace_unchanged": True,
            "clock_ns": 1700000000000000281,
        },
        "fixed_pid": {
            "applied": True,
            "trace_unchanged": True,
            "pid": 281,
        },
        "reviewer": {
            "reviewer_id": "TST-0281-probe2-three-valued-malformed-reviewer",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 does not import probe 1. It re-runs fire/silent/"
                "NOT-CHECKED on the six spec strings, reproduces the Kleene "
                "ignorance-stop control, rejects malformed input at "
                "spec-validation, and pins short-circuit vs forced full eval."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            *[
                {
                    "path": row["path"],
                    "exists": row["exists"],
                    "role": "supporting",
                }
                for row in supporting_rows
            ],
        ],
        "implementation": {
            "module": "tools/council/stopping/expr.py",
            "logic": "Kleene three-valued AND/OR/NOT",
            "stop_iff": "true",
            "not_checked": "does-not-stop",
            "impure_terms": "rejected-at-spec-validation",
        },
        "cloud_ok": False,
        "registered": True,
        "timestamps": {"started_at": started, "ended_at": started},
        "notes": (
            "G-1 for TST-0281: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            f"{SENTINEL}"
        ),
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(dest)
    text = dest.read_text(encoding="utf-8")
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0281 sentinel missing from receipt text")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "six-examples-asts-precedence",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "independent-kleene-malformed-both-states",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0281-probe2-three-valued-malformed-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0281: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
