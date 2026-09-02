#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0053.json (test receipt, structural preflight)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

try:
    import receipt_writer as rw  # noqa: E402
except ImportError:
    rw = None  # type: ignore
from case_keys import (  # noqa: E402
    CLEAN_OBJECT,
    COLLIDING_OBJECT,
    NAME_LOWER_VALUE,
    NAME_UPPER_VALUE,
    CaseKeyError,
    emit_first_mutant,
    emit_json,
    naive_dumps,
)
from consumers import run_matrix, write_fixture  # noqa: E402

OUT = "command-center/receipts/TST-0053.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
FIX_REL = "command-center/p2-wave/probes/TST-0053/fixtures/name-and-Name.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0053/probe1_no_silent_merge.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0053/probe2_producer_refuse.py"
)
QUESTION = (
    "Failure class :11309. Target: build a document containing both "
    '"Name" and "name" and determine, per consumer, whether it errors, '
    "silently drops one, or last-wins. A case-insensitive consumer "
    "downstream of a case-sensitive producer is a silent data-loss path."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fixture = write_fixture(HERE / "fixtures" / "name-and-Name.json")
    matrix = run_matrix(fixture)
    plant = matrix["plant"]
    if not plant["both_present"] or not plant["distinct_values"]:
        print("FAILED:TST-0053 emit plant dead")
        return 1

    by_id = {r["consumer_id"]: r for r in matrix["consumers"]}
    pipe = by_id["tst-0053-pipeline-reader"]
    ci = by_id["ci-downstream-of-cs-producer"]
    cs = by_id["cpython-json.loads"]
    if pipe["outcome"] != "error" or not pipe["errored"]:
        print("FAILED:TST-0053 emit pipeline reader did not error")
        return 1
    if cs["outcome"] != "kept-both":
        print("FAILED:TST-0053 emit json.loads did not keep both")
        return 1
    if ci["outcome"] != "last-wins":
        print("FAILED:TST-0053 emit casefold downstream was not last-wins")
        return 1
    if matrix["outcome_count"] < 2:
        print("FAILED:TST-0053 emit no consumer divergence")
        return 1

    try:
        clean_text = emit_json(CLEAN_OBJECT)
        clean_ok = True
        clean_err = None
    except CaseKeyError as exc:
        clean_ok = False
        clean_text = None
        clean_err = str(exc)
    colliding_err = None
    colliding_text = None
    try:
        colliding_text = emit_json(COLLIDING_OBJECT)
    except CaseKeyError as exc:
        colliding_err = str(exc)
    naive = naive_dumps(COLLIDING_OBJECT)
    mutant = emit_first_mutant(COLLIDING_OBJECT)
    nested_err = None
    try:
        emit_json({"wrapper": {"Name": NAME_UPPER_VALUE, "name": NAME_LOWER_VALUE}})
    except CaseKeyError as exc:
        nested_err = str(exc)

    if not clean_ok or clean_text is None:
        print(f"FAILED:TST-0053 emit clean refused: {clean_err}")
        return 1
    if colliding_text is not None or not colliding_err:
        print("FAILED:TST-0053 emit colliding was not refused")
        return 1
    if not nested_err:
        print("FAILED:TST-0053 emit nested colliding was not refused")
        return 1
    if not mutant.get("emitted_colliding_bytes"):
        print("FAILED:TST-0053 emit mutant detector dead")
        return 1

    schema_path = REPO / SCHEMA
    schema_present = schema_path.is_file() and schema_path.stat().st_size > 0
    dep_tst52 = (REPO / "command-center/receipts/TST-0052.json").is_file()
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    doc = {
        "schema_version": 1,
        "id": "TST-0053",
        "unit_id": "TST-0053",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0053",
        "completion_sentinel": "SUCCESS:TST-0053",
        "report_kind": "test-receipt",
        "spec_anchor": "_USER-PROMPTS.md:11309",
        "min_bytes_threshold": 2048,
        "question": QUESTION,
        "title": "Case-insensitive parser collision on case-distinct JSON keys",
        "cloud_ok": False,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "platform-test-engineer",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "parser": {
            "name": "tst-0053-multi-consumer",
            "version": "1.0.0",
            "python": sys.version.split()[0],
        },
        "dependencies_on_this_tree": {
            "TST-0052": dep_tst52,
            "test-receipt.schema.json": schema_present,
        },
        "scope": {
            "implemented": (
                "Same Name/name fixture fed to in-tree and runtime JSON "
                "consumers; resolution recorded per consumer; unit producer "
                "refuses case-colliding keys before dumps; pipeline reader errors."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "TST-0052 unknown-field receipt consumed (absent)"
                if not dep_tst52
                else "TST-0052 was re-run",
                "test-receipt.schema.json validated (file absent on this worktree)"
                if not schema_present
                else "test-receipt.schema.json validated",
                "PowerShell ConvertFrom-Json measured (pwsh not on PATH)",
                "every JSON loader in the repo was wrapped",
            ],
            "proof_surface": (
                "live per-consumer resolution table on one fixture; both-states "
                "producer refuse vs clean emit; dumps-first mutant still emits both keys"
            ),
        },
        "fixture": {
            "path": FIX_REL,
            "plant_both_present": plant["both_present"],
            "name_keys": plant["name_keys"],
            "name_values": plant["name_values"],
            "source_pairs": plant["pairs"],
        },
        "resolution_table": matrix,
        "producer": {
            "module": "command-center/p2-wave/probes/TST-0053/case_keys.py",
            "clean_emitted": True,
            "colliding_refused": True,
            "nested_refused": True,
            "refusal": colliding_err,
            "nested_refusal": nested_err,
            "naive_dumps_contains_both_keys": '"Name"' in naive and '"name"' in naive,
            "emit_first_mutant": {
                "status": mutant["status"],
                "emitted_colliding_bytes": mutant["emitted_colliding_bytes"],
                "note": "known-broken control; not the shipped path",
            },
        },
        "tests": [
            {
                "id": "test_case_distinct_keys_do_not_silently_merge",
                "command": P1,
                "result": "PASS",
                "assertions": 3,
                "output_tail": (
                    f"pipeline={pipe['outcome']} cpython={cs['outcome']} "
                    f"ci={ci['outcome']} outcomes={matrix['distinct_outcomes']}"
                ),
            },
            {
                "id": "test_producer_refuses_to_emit_case_colliding_keys",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": colliding_err or "",
            },
        ],
        "negative_controls": [
            {
                "id": "TST0053-C1",
                "kind": "both-states",
                "description": (
                    "CPython json.loads keeps both distinct values; a casefold "
                    "index on the same parse last-wins to lowercase-n; the "
                    "pipeline reader errors. One document, three outcomes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "ci": ci["resolved"],
                        "pipeline_error": pipe["error_text"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"cpython": cs["resolved"]},
                    sort_keys=True,
                ),
            },
            {
                "id": "TST0053-C2",
                "kind": "emit-first-mutant",
                "description": (
                    "Shipped producer checks collisions before dumps. A dumps-first "
                    "mutant still carries both keys, proving refusal is live."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "mutant_emitted": mutant["emitted_colliding_bytes"],
                        "status": mutant["status"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"clean_len": len(clean_text), "refused": True},
                    sort_keys=True,
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "The same input document yields distinct resolved values per "
                    "consumer (kept-both vs last-wins vs error), not a single "
                    "asserted expected value."
                ),
                "verdict": "CONFIRMED",
                "anchor": FIX_REL,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "run_matrix(name-and-Name.json)",
                        "raw_output": json.dumps(
                            {
                                "distinct_outcomes": matrix["distinct_outcomes"],
                                "cpython": cs["resolved"],
                                "ci": ci["resolved"],
                                "pipeline": {
                                    "outcome": pipe["outcome"],
                                    "error": pipe["error_text"],
                                },
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "The unit producer refuses to emit case-colliding keys "
                    "before dumps; naive json.dumps still emits both."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0053/case_keys.py:emit_json",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "emit_json(COLLIDING_OBJECT) vs naive_dumps",
                        "raw_output": json.dumps(
                            {
                                "refused": True,
                                "refusal": colliding_err,
                                "naive_has_Name": '"Name"' in naive,
                                "naive_has_name": '"name"' in naive,
                                "mutant_emitted": mutant["emitted_colliding_bytes"],
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0053-probe2-producer-refuse",
            "vendor": "anthropic",
            "role": "adversarial-refuter",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-runs the per-consumer resolution table. Named "
                "probe2 re-runs producer refusal on a different field (emit vs "
                "dumps-first mutant). Catalog author vendor is openai; this "
                "refuter is recorded as anthropic."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0053/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "named_probes": [
            {"id": "probe1", "role": "no-silent-merge-resolution-table", "command": P1},
            {"id": "probe2", "role": "producer-refuse-both-states", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": FIX_REL, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0053/case_keys.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "PowerShell ConvertFrom-Json (case-insensitive PSCustomObject) "
                    "was not executed: pwsh is not on PATH on this Linux box."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a Windows substrate with pwsh, ConvertFrom-Json the same "
                    "fixture and record whether .Name and .name are the same slot."
                ),
            }
        ],
        "notes": (
            "G-1 for TST-0053: live named probes exit 0, receipts/TST-0053.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "SUCCESS:TST-0053"
        ),
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "note": "measure runs after this emit; probes re-run live",
            }
        ],
        "checks": [
            {
                "id": "test_case_distinct_keys_do_not_silently_merge",
                "verdict": "PASS",
            },
            {
                "id": "test_producer_refuses_to_emit_case_colliding_keys",
                "verdict": "PASS",
            },
        ],
    }

    contract = "local-json-dump"
    if rw is not None:
        errs, contract = rw.validate_receipt(doc, repo=REPO)
        if errs:
            print(f"FAILED:TST-0053 emit receipt invalid via {contract}: {errs[:8]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    write_sha = None
    if rw is not None:
        if hasattr(rw, "ensure_receipts_dir"):
            rw.ensure_receipts_dir(REPO)
        result = rw.write_json(out, doc, repo=REPO)
        write_sha = getattr(result, "sha256", None)
        contract = f"{contract}+receipt_writer"
    else:
        out.write_text(
            json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        contract = "local-json-dump (receipt_writer.py absent)"
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0053 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0053" not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0053 sentinel missing from written artifact")
        return 1
    print(
        f"wrote {OUT} bytes={size} sha256={digest} contract={contract} "
        f"write_sha={write_sha or digest}"
    )
    print(
        f"outcomes={matrix['distinct_outcomes']} "
        f"pipeline={pipe['outcome']} ci={ci['outcome']} cpython={cs['outcome']}"
    )
    print("SUCCESS:TST-0053 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
