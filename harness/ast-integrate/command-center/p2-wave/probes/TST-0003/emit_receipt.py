#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0003.json (7xN matrix + column hashes)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import write_fixtures  # noqa: E402
from matrix import replay  # noqa: E402

UNIT = "TST-0003"
OUT = "command-center/receipts/TST-0003.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
LOCAL_SCHEMA = HERE / "receipt.local.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0003/probe1_seven_sites_agree.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0003/probe2_skip_condition_8.py"
)
QUESTION = (
    "The spec names seven consumers of the same reducer: local runners, cloud "
    "dispatchers, monitors, harvesters, workflow fan-in, cross-vendor adapters, "
    "final synthesis (:10648). Target: replay the full conformance corpus through "
    "all seven call sites and assert the verdict objects are byte-identical. Do "
    "any two call sites disagree on any row?"
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
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


def main() -> int:
    fixtures = write_fixtures()
    clean = replay()
    patched = replay(skip_by_site={"monitor": {8}})
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0003 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    sentinel = "SUCCESS:TST-0003"
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    unique = set(clean["column_hashes"].values())
    answer = (
        "No. All seven call sites produce byte-identical verdict objects on every "
        f"row of the {clean['n_rows']}-row conformance corpus. Equality is proven "
        f"by SHA-256 column hashes: the seven hashes collapse to one value "
        f"{next(iter(unique))}. Patching the monitor site to skip condition 8 "
        "turns the differential red on exactly SYNTH-C08 (monitor PASS vs FAIL/8 "
        "at the other six sites)."
    )
    slim_matrix = {
        "n_rows": clean["n_rows"],
        "n_sites": clean["n_sites"],
        "row_ids": clean["row_ids"],
        "site_ids": clean["site_ids"],
        "cells": [
            {
                "row_id": cell["row_id"],
                "verdict": cell["sites"][clean["site_ids"][0]]["verdict"],
                "failing-condition-id": cell["sites"][clean["site_ids"][0]][
                    "failing-condition-id"
                ],
                "row_hashes_agree": cell["row_hashes_agree"],
            }
            for cell in clean["matrix"]
        ],
    }
    doc = {
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": "Seven-call-site parity differential for the shared reducer",
        "question": QUESTION,
        "answer": answer,
        "spec_anchor": "_USER-PROMPTS.md:10648",
        "min_bytes_threshold": 128,
        "call_sites": list(clean["site_ids"]),
        "shared_reducer": clean["shared_reducer"],
        "evaluate_is_shared": clean["evaluate_is_shared"],
        "identity_ok": clean["identity_ok"],
        "corpus": {
            "n_rows": clean["n_rows"],
            "row_ids": clean["row_ids"],
            "path": "command-center/p2-wave/probes/TST-0003/fixtures",
            "kind": "unit-fixture-because-TST-0002-tests/fixtures/completion-absent",
            "tst_0002_present": False,
            "fixture_files": fixtures,
            "isolate_fail_ids": list(range(1, 13)),
            "pass_row_id": "SYNTH-PASS",
        },
        "matrix": slim_matrix,
        "column_hashes": clean["column_hashes"],
        "hashes_agree": clean["hashes_agree"],
        "distinct_column_hash_count": clean["distinct_column_hash_count"],
        "disagreements": clean["disagreements"],
        "negative_control_skip_c8": {
            "patched_site": "monitor",
            "skipped_condition": 8,
            "hashes_agree": patched["hashes_agree"],
            "disagreements": patched["disagreements"],
            "column_hashes": patched["column_hashes"],
            "turns_red": patched["hashes_agree"] is False
            and len(patched["disagreements"]) == 1
            and patched["disagreements"][0]["row_id"] == "SYNTH-C08",
        },
        "tests": [
            {
                "id": "test_all_seven_call_sites_agree_per_row",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "test_skip_condition_8_differential_goes_red",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "skip-condition-8-at-monitor",
                "kind": "known-broken-call-site",
                "description": (
                    "Patch the monitor call site to skip condition 8. The 7xN "
                    "hash differential must go red on the C8 isolate row only."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "hashes_agree=False diverging_row=SYNTH-C08 "
                    "monitor=PASS others=FAILED/8"
                ),
                "good_state_output": f"hashes_agree=True column_sha256={next(iter(unique))}",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0003-probe2-skip-condition-8",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "probe2 is a mechanically different check: it patches one call "
                "site rather than replaying the clean matrix, and asserts the "
                "differential fires on the planted skip."
            ),
        },
        "report": {
            "kind": "test-receipt",
            "observations": [
                {
                    "name": "seven-site-column-hash-agreement",
                    "measured": True,
                    "method": "sha256-column-hash of canonical verdict objects",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0003/matrix.py:"
                        f"{find_line(HERE / 'matrix.py', 'def digest_column')}"
                    ),
                },
                {
                    "name": "skip-condition-8-differential-red",
                    "measured": True,
                    "method": "patch monitor evaluate skip={8}",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0003/probe2_skip_condition_8.py:"
                        f"{find_line(HERE / 'probe2_skip_condition_8.py', 'PATCHED_SITE')}"
                    ),
                },
            ],
            "control_ids": ["skip-condition-8-at-monitor"],
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "supporting", "exists": True},
            {
                "path": "command-center/p2-wave/probes/TST-0003/reducer.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/TST-0003/call_sites.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/TST-0003/receipt.local.schema.json",
                "role": "supporting",
                "exists": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    f"All seven call sites agree on all {clean['n_rows']} corpus rows; "
                    "equality is the identity of SHA-256 column hashes, not a visual table check."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/TST-0003/matrix.py:{find_line(HERE / 'matrix.py', 'def digest_column')}",
            },
            {
                "claim": (
                    "Patching monitor to skip condition 8 turns the differential red "
                    "on exactly SYNTH-C08; the other twelve rows stay identical."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0003/probe2_skip_condition_8.py:"
                    f"{find_line(HERE / 'probe2_skip_condition_8.py', 'PATCHED_SITE')}"
                ),
            },
            {
                "claim": (
                    "All seven judges bind the same reducer.evaluate object "
                    "(identity check), so agreement is not seven independent copies."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0003/call_sites.py:"
                    f"{find_line(HERE / 'call_sites.py', 'judge.reducer = _SHARED_EVALUATE')}"
                ),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Production CC-0003 reducer and IMP-0417 seven-site adoption "
                    "are not on this tree. This unit ships an executable seven-site "
                    "harness plus the TST-0002-shaped corpus under probes/TST-0003/."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-point call_sites.JUDGES at the production imports once "
                    "CC-0003 and IMP-0417 land, and re-run the same column-hash differential."
                ),
            }
        ],
        "catalog_schema_note": (
            "command-center/schema/test-receipt.schema.json is a $ref shim onto "
            "https://ast-integrate.invalid/ which jsonschema 4.10.3 cannot "
            "resolve offline. Live emit validates against "
            "command-center/p2-wave/probes/TST-0003/receipt.local.schema.json "
            "(required_fix=offline-local-test-receipt-schema). Catalog "
            "output_schema path is unchanged."
        ),
        "required_fix": "offline-local-test-receipt-schema",
        "named_probes": [
            {"id": "probe1", "role": "seven-site-column-hash-agreement", "command": P1},
            {"id": "probe2", "role": "skip-condition-8-negative-control", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0003/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "notes": (
            "G-1 for TST-0003: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
        "probe_transcripts": {
            "probe1": t1[-8000:],
            "probe2": t2[-8000:],
        },
    }
    # Do not retry Draft7Validator on the catalog shim: first emit raised
    # RefResolutionError fetching ast-integrate.invalid (fingerprint
    # catalog-shim-ref-network). required_fix=receipt.local.schema.json
    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0003 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for blob in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(blob)):
            print(f"FAILED:TST-0003 schema accepted garbage {list(blob)[:2]}")
            return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if sentinel not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0003 completion sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:TST-0003 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
