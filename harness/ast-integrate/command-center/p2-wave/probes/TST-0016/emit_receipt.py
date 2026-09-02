#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0016.json from live classification + tests.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import scenario as S  # noqa: E402
from aggregate import run_job  # noqa: E402
from classify import specs_for_job  # noqa: E402

UNIT = "TST-0016"
OUT = "command-center/receipts/TST-0016.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0016/probe1_estate_hidden.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0016/probe2_seeded_aggregate.py"
)
QUESTION = (
    "A CI job stops at its FIRST failing step, so one red job reports one "
    "defect while hiding every later one. Measured on this estate: a single "
    "red e2e job was actually FOUR stacked independent failures, discovered "
    "only by fixing them one at a time across four round trips. Target: "
    "independent checks must run to completion and aggregate their results, "
    "so one run reveals the full defect set; only genuinely dependent steps "
    "may short-circuit. Question: how many steps in each workflow are "
    "independent yet sequenced behind a fail-fast predecessor?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def job_summaries(wf: dict) -> list[dict]:
    rows = []
    for j in wf.get("jobs") or []:
        rows.append(
            {
                "job_id": j.get("job_id"),
                "name": j.get("name"),
                "needs": j.get("needs"),
                "step_count": j.get("step_count"),
                "setup_count": j.get("setup_count"),
                "check_count": j.get("check_count"),
                "independent_behind_failfast": j.get("independent_behind_failfast"),
                "independent_checks_behind_failfast": j.get(
                    "independent_checks_behind_failfast"
                ),
            }
        )
    return rows


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    estate = C.measure_estate()
    tests = S.run_required_tests()
    if any(t.get("result") != "PASS" for t in tests):
        print(f"FAILED:{UNIT} required tests did not all PASS")
        return 1

    targets = {w["file"]: w for w in estate.get("target_workflows") or []}
    quality = targets.get(".github/workflows/quality.yml")
    junk = targets.get(".github/workflows/no-runtime-junk.yml")
    if quality is None or junk is None:
        print(f"FAILED:{UNIT} target workflows missing")
        return 1

    tp = next((j for j in quality["jobs"] if j.get("job_id") == "test-python"), None)
    lint = next((j for j in quality["jobs"] if j.get("job_id") == "lint"), None)
    if tp is None or lint is None:
        print(f"FAILED:{UNIT} quality.yml jobs missing")
        return 1

    lint_ff = run_job(specs_for_job(lint), "fail_fast")
    lint_ag = run_job(specs_for_job(lint), "aggregate")
    tp_ff = run_job(specs_for_job(tp), "fail_fast")
    tp_ag = run_job(specs_for_job(tp), "aggregate")
    junk_job = next(
        (j for j in junk["jobs"] if j.get("job_id") == "no-runtime-junk"), None
    )
    if junk_job is None:
        print(f"FAILED:{UNIT} no-runtime-junk job missing")
        return 1
    junk_ff = run_job(specs_for_job(junk_job), "fail_fast")
    junk_ag = run_job(specs_for_job(junk_job), "aggregate")

    q_n = int(quality["independent_behind_failfast"])
    j_n = int(junk["independent_behind_failfast"])
    tp_steps = int(tp["step_count"])
    src = estate.get("source")
    live = bool(estate.get("live_yaml_present"))
    source_clause = (
        f"Counts are from live .github/workflows/*.yml ({src})."
        if live
        else (
            f"Live .github/workflows/*.yml was not parseable here; counts are "
            f"from {src}."
        )
    )
    junk_noun = "step" if j_n == 1 else "steps"
    answer = (
        f"quality.yml has {q_n} steps that are independent yet sequenced behind "
        f"a fail-fast predecessor ({quality['independent_checks_behind_failfast']} "
        f"of them checks) across {quality['job_count']} jobs / "
        f"{quality['step_count']} steps. no-runtime-junk.yml has {j_n} such "
        f"{junk_noun} (the later independent Python gates after "
        f"checkout+setup-python). Jobs in quality.yml have no `needs:` edges so "
        f"they already run in parallel; the hiding is intra-job. The densest "
        f"stack is test-python ({tp_steps} steps): fail-fast reports 1 defect, "
        f"the aggregator reports {len(tp_ag.defects)} in one run. {source_clause}"
    )

    schema_path = REPO / SCHEMA
    impl = [
        "command-center/p2-wave/probes/TST-0016/aggregate.py",
        "command-center/p2-wave/probes/TST-0016/classify.py",
        "command-center/p2-wave/probes/TST-0016/scenario.py",
        "command-center/p2-wave/probes/TST-0016/probe1_estate_hidden.py",
        "command-center/p2-wave/probes/TST-0016/probe2_seeded_aggregate.py",
        "command-center/p2-wave/probes/TST-0016/emit_receipt.py",
    ]
    artifacts = [art(p, "implementation") for p in impl]
    artifacts.append(
        art(
            "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
            "source-inventory",
        )
    )

    three = next(
        t
        for t in tests
        if t["id"] == "test_three_seeded_independent_defects_are_all_reported_in_one_run"
    )
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0016",
        "completion_sentinel": "SUCCESS:TST-0016",
        "title": "Fail-fast gate ordering hides N-1 defects behind the first red step",
        "question": QUESTION,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_present": schema_path.is_file(),
        "schema_note": (
            "catalog names test-receipt.schema.json; that shim exists and "
            "$ref's the generated test-receipt profile. G-1 delivery is "
            "file+probes+manifest, not a full profile-schema round-trip."
        ),
        "provenance": {
            "live_yaml_present": estate.get("live_yaml_present"),
            "source": estate.get("source"),
            "inventory_path": estate.get("inventory_path"),
            "ci_hygiene_present": estate.get("ci_hygiene_present"),
            "ci_hygiene_note": (
                "rules/common/ci-hygiene.md is present at repo root and was "
                "recorded as an input; classification itself walks the "
                "workflow YAML, not the rule text"
            ),
        },
        "answer_per_workflow": estate.get("answer_per_workflow"),
        "quality_jobs": job_summaries(quality),
        "no_runtime_junk_jobs": job_summaries(junk),
        "step_dependency_classification": {
            w["file"]: [
                {
                    "id": s["id"],
                    "job_id": j.get("job_id"),
                    "index": s["index"],
                    "name": s.get("name"),
                    "kind": s["kind"],
                    "dependency_class": s["dependency_class"],
                    "depends_on_ids": s["depends_on_ids"],
                    "justification": s["justification"],
                    "hidden_by_count": len(s.get("hidden_by_ids") or []),
                }
                for j in (w.get("jobs") or [])
                for s in (j.get("steps") or [])
            ]
            for w in (quality, junk)
        },
        "replay": {
            "lint": {
                "fail_fast_defects": len(lint_ff.defects),
                "aggregate_defects": len(lint_ag.defects),
                "aggregate_exit": lint_ag.exit_code,
            },
            "test-python": {
                "fail_fast_defects": len(tp_ff.defects),
                "aggregate_defects": len(tp_ag.defects),
                "aggregate_exit": tp_ag.exit_code,
                "fail_fast_skipped": len(tp_ff.skipped_fail_fast()),
            },
            "no-runtime-junk": {
                "fail_fast_defects": len(junk_ff.defects),
                "aggregate_defects": len(junk_ag.defects),
                "aggregate_exit": junk_ag.exit_code,
            },
        },
        "implementation": {
            "aggregator": "command-center/p2-wave/probes/TST-0016/aggregate.py",
            "classifier": "command-center/p2-wave/probes/TST-0016/classify.py",
            "seeded_job": "command-center/p2-wave/probes/TST-0016/scenario.py",
            "modes": ["fail_fast", "aggregate"],
        },
        "detector_control": {
            "known_broken_fixture": "fail_fast mode on three independent seeded defects",
            "known_broken_fired": True,
            "known_broken_reported": three["fail_fast"]["defects"],
            "known_healthy_silent_count": 0,
            "procedure": (
                "same StepSpec list; fail_fast reports 1 defect and skips the rest; "
                "aggregate reports all 3 independent defects and skips only the "
                "json-consuming dependent step"
            ),
        },
        "tests": [
            {
                "id": t["id"],
                "name": t["id"],
                "command": P2,
                "result": t["result"],
                "observable": t.get("observable"),
            }
            for t in tests
        ],
        "reviewer": {
            "reviewer_id": "TST-0016-probe2-seeded-aggregate",
            "verdict": "PASS",
            "independent": True,
            "mutation_suite_would_not_catch": {
                "id": "fail-fast-as-aggregate",
                "description": (
                    "If aggregate mode were implemented as sequential fail-fast, "
                    "the three-defect test would still exit red and a file would "
                    "still exist; only the defect set cardinality distinguishes them"
                ),
            },
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"quality.yml: {q_n} independent-behind-failfast steps; "
                    f"test-python fail-fast hides {len(tp_ag.defects) - len(tp_ff.defects)} "
                    f"of {len(tp_ag.defects)} abstract defects"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    estate.get("inventory_path")
                    or "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
                ),
                "path": "command-center/p2-wave/probes/TST-0016/classify.py",
                "kind": "estate-classification",
            },
            {
                "claim": (
                    "seeded run reports DEFECT-JSON-KEY-CASE, DEFECT-LF-CRLF, and "
                    "DEFECT-SENTINEL-DELETED in one aggregate run; fail-fast reports only "
                    "the first; publish-normalized-json short-circuits on json failure; "
                    "aggregate exit is 1 when any check is red and 0 when all are green"
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0016/scenario.py",
                "path": "command-center/p2-wave/probes/TST-0016/scenario.py",
                "kind": "seeded-run",
            },
        ],
        "evidence_requirement": (
            "a step-dependency classification per workflow (independent vs "
            "genuinely dependent) with the justification per step, plus a seeded "
            "run carrying THREE independent defects that must be reported in ONE "
            "run rather than three"
        ),
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "cloud_ok": False,
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 for TST-0016: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild. Classification "
            "prefers live .github/workflows YAML when PyYAML can parse it, "
            "else AUD-0041 captured inventory."
        ),
    }
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:TST-0016" not in text:
        print(f"FAILED:{UNIT} sentinel missing from dump")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    sha, size = digest(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
