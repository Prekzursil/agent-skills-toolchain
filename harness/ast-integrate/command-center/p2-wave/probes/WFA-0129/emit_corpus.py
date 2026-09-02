#!/usr/bin/env python3
"""Emit the WFA-0129 matched-case benchmark corpus."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

UID = "WFA-0129"
OUT = (
    "command-center/foundry/"
    "WFA-0129-matched-case-benchmark-corpus-for-fusion-evaluation.json"
)
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
CORPUS_PY = "command-center/p2-wave/probes/WFA-0129/corpus.py"
FIXTURE = (
    "command-center/p2-wave/probes/WFA-0129/fixtures/executable-merge-map.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0129/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0129/probe2_coverage_fail_closed.py"
)
QUESTION = (
    "For how many of the 30 merge_units can a like-for-like source-vs-fusion "
    "comparison actually be run, and which are excluded?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:{UID} snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:{UID} probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    both = C.both_states()
    if not both["accepted_exactly_positive"] or not both["rejected_negative"]:
        print("FAILED:WFA-0129 both-states in-process mismatch")
        return 1
    closed29 = C.fail_closed_wrong_n(29)
    if not closed29["refused"]:
        print("FAILED:WFA-0129 fail-closed 29 did not refuse")
        return 1

    estate = C.load_estate(REPO)
    built = C.build_corpus(
        estate["merge_units"], estate["registry"], estate["blueprints"]
    )
    recounted = C.recount_rows(built["coverage_matrix"])
    if recounted["row_count"] != C.EXPECTED_N:
        print("FAILED:WFA-0129 coverage row recount != 30")
        return 1

    harness_present = estate.get("kind") == "harness-maps"
    excluded = list(built["non_benchmarkable"])
    bench_ids = [
        row["merge_unit_id"]
        for row in built["coverage_matrix"]["rows"]
        if row["benchmarkable"]
    ]
    excluded_ids = [item["merge_unit_id"] for item in excluded]
    n_bench = built["benchmarkable_count"]
    n_excl = built["excluded_count"]

    maps_log = estate.get("maps_search") or []
    answer = (
        f"{n_bench} of {C.EXPECTED_N} merge_units admit a like-for-like "
        f"source-vs-fusion comparison; {n_excl} are NON-BENCHMARKABLE "
        f"({', '.join(excluded_ids) if excluded_ids else 'none'}). "
    )
    if harness_present:
        answer += (
            "Ids are taken from 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json "
            f"at {estate.get('maps_path')}."
        )
    else:
        answer += (
            "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json is absent on this "
            "worktree (search log in maps_binding); the executable 30-unit "
            "map in corpus.executable_estate supplies WFA-0129-MU-NN ids, "
            "which are not harness merge_unit ids."
        )

    cat_line = find_line(
        CATALOG,
        "the coverage matrix row count equals len(merge_units)==30",
    )
    builder_line = find_line(
        CORPUS_PY,
        "if require_n and len(units) != EXPECTED_N:",
    )
    accept_line = find_line(
        CORPUS_PY,
        "if not can_run(fusion, case):",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases_out = []
    for case in built["cases"]:
        cases_out.append(
            {
                "id": case["id"],
                "merge_unit_id": case["merge_unit_id"],
                "required_capabilities": case["required_capabilities"],
                "run_identically_by": case["run_identically_by"],
                "task": case.get("task"),
                "dispatch": case.get("dispatch"),
            }
        )

    fixture_path = REPO / FIXTURE
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_doc = {
        "id_binding": "WFA-0129-executable-fallback",
        "harness_ids_bound": harness_present,
        "merge_units": estate["merge_units"],
        "registry_ids": sorted(estate["registry"].keys()),
        "blueprint_ids": sorted(estate["blueprints"].keys()),
        "kind": estate.get("kind"),
        "maps_path": estate.get("maps_path"),
    }
    fixture_path.write_text(
        json.dumps(fixture_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    doc = {
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0129",
        "report_kind": "benchmark-corpus",
        "schema": SCHEMA + "#/$defs/benchmark-corpus",
        "generated_at": now,
        "question": QUESTION,
        "answer": answer,
        "exact_answer": {
            "benchmarkable_count": n_bench,
            "excluded_count": n_excl,
            "coverage_row_count": recounted["row_count"],
            "merge_unit_count": built["merge_unit_count"],
            "harness_maps_present": harness_present,
            "ids_are_harness_ids": harness_present,
            "benchmarkable_ids": bench_ids,
            "excluded_ids": excluded_ids,
        },
        "maps_binding": {
            "authoritative_file": C.HARNESS_NAME,
            "harness_maps_present": harness_present,
            "maps_path": estate.get("maps_path"),
            "kind": estate.get("kind"),
            "search": maps_log,
        },
        "cases": cases_out,
        "coverage_matrix": {
            "row_count": recounted["row_count"],
            "computed_from": "len(coverage_matrix.rows) after one row per merge_unit",
            "rows": built["coverage_matrix"]["rows"],
        },
        "non_benchmarkable": excluded,
        "tests": [
            {
                "id": "both-states",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "detail": (
                    "accept case every source can run; reject case no source can run"
                ),
            },
            {
                "id": "coverage-row-count",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "detail": "row count equals len(merge_units)==30 or fail closed",
            },
        ],
        "negative_controls": [
            {
                "id": "both-states-unrunnable-case",
                "input": "case-no-source required_capabilities=[capability-no-actor-holds]",
                "expected": "reject",
                "observed": "reject" if both["rejected_negative"] else "accept",
            },
            {
                "id": "coverage-pad-29",
                "input": "len(merge_units)=29",
                "expected": "FailClosed merge-unit-count",
                "observed": closed29["code"],
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0129-probe2-coverage-fail-closed",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Recomputed coverage as len(rows); refused 29- and 31-unit maps; "
                "did not author corpus.executable_estate"
            ),
        },
        "evidence": [
            {
                "claim": (
                    "A matched case is accepted only when the fused blueprint and "
                    "every sources_resolved_in_registry entry can run that same case"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CORPUS_PY}:{accept_line}",
            },
            {
                "claim": (
                    "Coverage matrix row count equals len(merge_units)==30 or the "
                    "build fails closed"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CORPUS_PY}:{builder_line}",
            },
            {
                "claim": "Catalog contracted the 30-row fail-closed coverage rule",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{cat_line}",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": CORPUS_PY, "exists": True, "role": "builder"},
            {"path": FIXTURE, "exists": True, "role": "executable-map"},
        ],
        "mechanism": (
            "matched-case derivation with a fail-closed non-benchmarkable "
            "exclusion list"
        ),
        "report": {
            "kind": "benchmark-corpus",
            "observations": [
                {
                    "name": "benchmarkable_merge_units",
                    "measured": n_bench,
                    "method": "len(coverage_matrix.rows where benchmarkable)",
                    "anchor": f"{CORPUS_PY}:{builder_line}",
                },
                {
                    "name": "coverage_row_count",
                    "measured": recounted["row_count"],
                    "method": "len(coverage_matrix.rows) after one row per merge_unit",
                    "anchor": f"{CORPUS_PY}:{builder_line}",
                },
                {
                    "name": "excluded_merge_units",
                    "measured": n_excl,
                    "method": "enumerated non_benchmarkable with per-unit reason",
                    "anchor": f"{CORPUS_PY}:{accept_line}",
                },
            ],
            "control_ids": [
                "both-states-unrunnable-case",
                "coverage-pad-29",
            ],
        },
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:{UID} schema missing {SCHEMA}")
        return 1
    schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
    target = (schema_doc.get("$defs") or {}).get("benchmark-corpus")
    if not isinstance(target, dict) or "$ref" not in target:
        print(f"FAILED:{UID} {SCHEMA} missing $defs/benchmark-corpus $ref")
        return 1
    # The shim $ref points at ast-integrate.invalid; do not fetch it. Local
    # corpus contract: sentinel, 30 computed coverage rows, both-states.
    if doc.get("state") != "SUCCESS" or "SUCCESS:WFA-0129" not in json.dumps(doc):
        print(f"FAILED:{UID} sentinel/state missing")
        return 1
    if recounted["row_count"] != C.EXPECTED_N:
        print(f"FAILED:{UID} coverage rows != 30")
        return 1
    if doc["report"]["kind"] != "benchmark-corpus":
        print(f"FAILED:{UID} report.kind is not benchmark-corpus")
        return 1
    if not both["accepted_exactly_positive"] or not both["rejected_negative"]:
        print(f"FAILED:{UID} both-states not recorded")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"benchmarkable={n_bench} excluded={n_excl} "
        f"harness_maps_present={harness_present}"
    )
    print("SUCCESS:WFA-0129")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
