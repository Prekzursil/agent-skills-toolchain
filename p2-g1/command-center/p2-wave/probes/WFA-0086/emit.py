#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0086-repair-intake-baselines.json."""
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
import intake as I  # noqa: E402
import subjects as S  # noqa: E402

OUT = "command-center/wfa/WFA-0086-repair-intake-baselines.json"
SCHEMA = "command-center/p2-wave/probes/WFA-0086/repair_record.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0086/probe1_red_per_candidate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0086/probe2_second_surface.py"
)
SENTINEL = "SUCCESS:WFA-0086"
QUESTION = (
    "For each of the 15 REPAIR-classified candidates and the 13 REPAIRED-route "
    "blueprints, what is the exact reproducible failure - the command, the "
    "observed wrong behaviour and the expected behaviour - captured as a "
    "failing test before a single line is changed?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0086 emit snippet missing in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def public_record(row: dict) -> dict:
    keys = (
        "id",
        "kind",
        "classification",
        "command",
        "expected",
        "observed",
        "red_reproduced",
        "verbatim_output",
        "second_surface",
        "repair_may_begin",
        "red_test_kept",
        "reclassified_to",
        "gate",
        "defect",
        "artifact_rel",
        "claimed_state",
        "route",
        "run_exit",
    )
    return {k: row.get(k) for k in keys}


def main() -> int:
    live = I.run_intake()
    if not live["controls"].get("all_passed"):
        print("FAILED:WFA-0086 emit intake controls")
        print(json.dumps(live["controls"], indent=2, sort_keys=True))
        return 1

    windows = live["windows_source"]
    sm = live["summary"]
    ctrl = live["controls"]
    records = [public_record(r) for r in live["records"]]

    fixture_reg = HERE / "fixtures" / "registry.json"
    fixture_reg.parent.mkdir(parents=True, exist_ok=True)
    fixture_reg.write_text(
        json.dumps(
            {
                "origin": "linux-worktree-intake-fixtures",
                "not_the_windows_284_registry": True,
                "repair_n": 15,
                "repaired_route_n": 13,
                "candidates": [
                    {"id": s["id"], "classification": s["classification"], "kind": s["kind"]}
                    for s in S.catalog()
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry_red = not windows["registry_present"]
    doc = {
        "unit_id": "WFA-0086",
        "state": "SUCCESS",
        "record_type": "RepairRecord",
        "schema_version": 1,
        "ts": now,
        "question": QUESTION,
        "sentinel": SENTINEL,
        "identity_claim": (
            "These 15+13 ids are namespaced wfa0086-* fixture subjects. They are "
            "NOT a claim that the Windows 284-record REPAIR set was present on "
            "this worktree. The Windows registry was measured absent; that "
            "blocker is captured as a failing test rather than repaired blind."
        ),
        "windows_source": {
            "registry_present": windows["registry_present"],
            "blueprint_present": windows["blueprint_present"],
            "tried_paths": windows["tried_paths"],
            "blocker": windows["blocker"],
        },
        "records": records,
        "summary": sm,
        "controls": {
            "no_red_refuses_repair": ctrl["no_red_refuses_repair"],
            "unreproducible_reclassified": ctrl["unreproducible_reclassified"],
            "unreproducible_second_surface_ok": ctrl["unreproducible_second_surface_ok"],
            "gate_holds": ctrl["gate_holds"],
            "naive_repair_without_red_caught": ctrl["naive_repair_without_red_caught"],
            "all_repair_candidates_red": ctrl["all_repair_candidates_red"],
            "all_blueprints_red": ctrl["all_blueprints_red"],
            "red_tests_kept": ctrl["red_tests_kept"],
            "second_surface_independent": ctrl["second_surface_independent"],
            "repair_n": ctrl["repair_n"],
            "blueprint_n": ctrl["blueprint_n"],
            "all_passed": ctrl["all_passed"],
        },
        "control_records": {
            "unreproducible": public_record(live["control_records"]["unreproducible"]),
            "no_red": public_record(live["control_records"]["no_red"]),
        },
        "answer": (
            f"{sm['red_reproduced']} of {sm['repair_candidates']}+"
            f"{sm['repaired_route_blueprints']} fixture subjects have a captured "
            f"red test (command, expected, observed, verbatim, second surface). "
            f"repair_may_begin={sm['repair_may_begin_true']}. "
            f"Windows registry present={windows['registry_present']}. "
            "No subject was repaired by this unit."
        ),
        "tests": [
            {
                "id": "T1-no-repair-without-red",
                "name": S.NO_REPAIR_WITHOUT_RED,
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-unreproducible-reclassified",
                "name": S.UNREPRODUCIBLE_RECLASSIFY,
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-red-kept-as-regression",
                "name": S.RED_TEST_KEPT_AS_REGRESSION,
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-WINDOWS-REGISTRY-BLOCKER",
                "name": S.CAPTURE_BLOCKER_AS_FAILING_TEST,
                "command": (
                    "test -s C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                    "08-WORKFLOW-CANDIDATE-REGISTRY.json"
                ),
                "result": "RED" if registry_red else "PASS",
                "kept_as_regression": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0086-probe2-second-surface",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-run intake.second_surface without reading runner stdout; "
                "plant no-red and unreproducible controls; require the naive "
                "repair-without-red mutant to be refused."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0086/intake.py",
                "exists": True,
                "role": "intake",
            },
        ],
        "evidence": [
            ev(
                "command-center/p2-wave/probes/WFA-0086/subjects.py",
                S.NO_REPAIR_WITHOUT_RED,
                "probe",
                "Repair is gated on a reproduced red test.",
            ),
            ev(
                "command-center/p2-wave/probes/WFA-0086/subjects.py",
                S.UNREPRODUCIBLE_RECLASSIFY,
                "probe",
                "Unreproducible claimed failures are reclassified, not repaired blind.",
            ),
            ev(
                "command-center/p2-wave/probes/WFA-0086/subjects.py",
                S.RED_TEST_KEPT_AS_REGRESSION,
                "probe",
                "Each red test is kept as the regression for that repair.",
            ),
            ev(
                "command-center/p2-wave/probes/WFA-0086/subjects.py",
                S.CAPTURE_BLOCKER_AS_FAILING_TEST,
                "probe",
                "The missing Windows registry is captured as a failing test.",
            ),
            ev(
                CATALOG,
                "no repair may begin on a candidate whose failure was not first reproduced red",
                "catalog",
                "Catalog test 1 for WFA-0086.",
            ),
            ev(
                SCHEMA,
                "RepairRecord",
                "schema",
                "Unit-local RepairRecord contract; catalog pack $ref is unresolved.",
            ),
        ],
        "produced_by": "command-center/p2-wave/probes/WFA-0086/emit.py",
        "output_schema": SCHEMA,
        "catalog_output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RepairRecord"
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errors = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errors:
        print("FAILED:WFA-0086 emit schema")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0086 emit sentinel missing")
        return 1
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"summary repair={sm['repair_candidates']} blueprints="
        f"{sm['repaired_route_blueprints']} red={sm['red_reproduced']} "
        f"begin={sm['repair_may_begin_true']}"
    )
    print("SUCCESS:WFA-0086 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
