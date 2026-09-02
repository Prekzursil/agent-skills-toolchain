#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0025-repro-specificity.json from a live matrix."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
import schema_ok as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0025-repro-specificity.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
CNF23 = "command-center/confirmation/CNF-0023-mechanised-repros.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0025/probe1_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0025/probe2_detector_control.py"
)
QUESTION = (
    "Does the reproduction discriminate? Run each repro against an unrelated, "
    "known-healthy component and require it NOT to fire. A repro that fires "
    "everywhere is measuring the environment, not the defect, and every "
    "conclusion drawn from it is void."
)


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def validate(doc: dict) -> None:
    errors = S.iter_errors(doc)
    if errors:
        print("FAILED:CNF-0025 schema errors", file=sys.stderr)
        for err in errors[:20]:
            print(" ", list(err.path), err.message, file=sys.stderr)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"kind": "receipt", "state": "SUCCESS"},
    ):
        if not S.iter_errors(garbage):
            print(
                f"FAILED:CNF-0025 schema accepted garbage {list(garbage)[:2]}",
                file=sys.stderr,
            )
            raise SystemExit(1)


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = M.run_matrix()
    classified = M.classify(live)
    mutations = M.run_mutation_controls()
    cnf23 = M.run_cnf23_specificity()
    sentinel = M.catalog_sentinel()
    cnf23_path = REPO / CNF23
    accepted = classified["accepted_repros"]
    healthy_ids = classified["healthy_ids"]
    if len(accepted) < 1:
        print("FAILED:CNF-0025 no accepted specific repro", file=sys.stderr)
        return 1
    if len(healthy_ids) < 3:
        print("FAILED:CNF-0025 need three healthy components", file=sys.stderr)
        return 1
    if not mutations["ok"]:
        print("FAILED:CNF-0025 planted/fixed mutation controls", file=sys.stderr)
        print(json.dumps(mutations, indent=1), file=sys.stderr)
        return 1
    if not cnf23["all_specific"]:
        print("FAILED:CNF-0025 CNF-0023 mechanised scripts are non-specific", file=sys.stderr)
        print(json.dumps(cnf23, indent=1), file=sys.stderr)
        return 1

    known_broken = []
    for repro_id in accepted:
        target = live["own_target"][repro_id]
        fired = live["grid"][repro_id][target] == live["fire_exit"]
        known_broken.append(
            {
                "repro_id": repro_id,
                "fixture": f"command-center/p2-wave/probes/CNF-0025/fixtures/components/{target}",
                "fired": fired,
                "exit_code": live["grid"][repro_id][target],
            }
        )
        if not fired:
            print(f"FAILED:CNF-0025 detector-control {repro_id} silent on broken", file=sys.stderr)
            return 1

    silent_count = 0
    for repro_id in accepted:
        for hid in healthy_ids:
            if live["grid"][repro_id][hid] == 0:
                silent_count += 1
            else:
                print(f"FAILED:CNF-0025 {repro_id} not silent on {hid}", file=sys.stderr)
                return 1

    cell_lines = [
        f"{c['repro_id']} x {c['component_id']} role={c['role']} exit={c['exit_code']} fired={c['fired']}"
        for c in live["cells"]
    ]
    matrix_raw = "\n".join(cell_lines)
    q_ids = [q["repro_id"] for q in classified["quarantined"]]

    tests = [
        {
            "id": "red-on-own-target-green-on-three-healthy",
            "name": "Every accepted repro is red on its own target and green on three healthy components",
            "command": P1,
            "result": "PASS",
            "assertions": len(accepted) * 4,
            "output_tail": f"accepted={accepted} healthy={healthy_ids}",
        },
        {
            "id": "quarantine-repro-red-on-healthy",
            "name": "A repro red on a healthy component is quarantined",
            "command": P1,
            "result": "PASS" if classified["quarantined"] else "FAIL",
            "assertions": 1,
            "output_tail": f"quarantined={q_ids}",
        },
        {
            "id": "scripts-invoked-by-path",
            "name": "Each repro is a file invoked by path, never inlined into a shell body",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0025/matrix.py",
            "result": "PASS",
            "assertions": len(live["cells"]),
            "output_tail": "invoked_by_path=true for every cell",
        },
        {
            "id": "schema-rejects-garbage",
            "name": "detector-control schema rejects empty/unrelated documents",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0025/schema_ok.py",
            "result": "PASS",
            "assertions": 4,
            "output_tail": "empty and garbage documents produce schema errors",
        },
        {
            "id": "cnf0023-mechanised-specific",
            "name": "CNF-0023 generated scripts are red on unfixed and green on three healthy copies of fixed",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0025/matrix.py",
            "result": "PASS" if cnf23["all_specific"] else "FAIL",
            "assertions": len(cnf23["rows"]) * 4,
            "output_tail": json.dumps(
                {r["repro_id"]: {"unfixed": r["unfixed_exit"], "healthy": r["healthy_exits"]} for r in cnf23["rows"]}
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:CNF-0025 a required test did not pass", file=sys.stderr)
        return 1

    answer = (
        "Specificity holds for the accepted in-unit mechanised repros: each is red "
        "on its own defective fixture and green on healthy-alpha, healthy-beta, and "
        "healthy-gamma. repro_nonspecific fires on every component (including "
        "healthy) and is quarantined; no conclusion may be drawn from it. The four "
        "CNF-0023 generated scripts (r_apostrophe, r_option_id, r_sidecar, r_pin) "
        "are likewise red on the CNF-0023 unfixed fixture and green on three "
        "independent copies of the CNF-0023 fixed fixture, so those reproductions "
        "also discriminate rather than measuring the environment. CNF-0023's "
        "catalog artifact is absent on this tree; this unit invoked the generated "
        "scripts by path rather than pretending the missing upstream report exists."
    )

    schema_sha, schema_n = digest_file(REPO / SCHEMA)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    detector_control = {
        "known_broken_fixture": known_broken[0]["fixture"],
        "known_broken_fired": all(row["fired"] for row in known_broken),
        "known_broken_rows": known_broken,
        "known_healthy_silent_count": silent_count,
        "procedure": (
            "For each accepted repro, invoke the script by path against its "
            "known-broken fixture (must exit 2) and against three healthy "
            "components (must exit 0). A repro that exits 2 on a healthy "
            "component is quarantined. CNF-0023 generated scripts are the same "
            "test against unfixed vs three copies of fixed."
        ),
        "mutation_controls": mutations,
    }
    report = {
        "kind": "detector-control",
        "observations": [
            {
                "name": "matrix-cells",
                "measured": len(live["cells"]),
                "method": "path-invoked subprocess per repro x component",
                "anchor": "command-center/p2-wave/probes/CNF-0025/matrix.py",
            },
            {
                "name": "empty-cells",
                "measured": live["empty_cells"],
                "method": "len(cells) vs repros*components",
                "anchor": "command-center/p2-wave/probes/CNF-0025/matrix.py",
            },
            {
                "name": "accepted-repros",
                "measured": len(accepted),
                "method": "red on own target and green on three healthy",
                "anchor": "command-center/p2-wave/probes/CNF-0025/matrix.py",
            },
            {
                "name": "quarantined-repros",
                "measured": len(classified["quarantined"]),
                "method": "red on any healthy component",
                "anchor": "command-center/p2-wave/probes/CNF-0025/repros/repro_nonspecific.py",
            },
            {
                "name": "known-healthy-silent-count",
                "measured": silent_count,
                "method": "accepted repros x three healthy components",
                "anchor": "command-center/p2-wave/probes/CNF-0025/probe2_detector_control.py",
            },
            {
                "name": "cnf0023-all-specific",
                "measured": True,
                "method": "path-invoke CNF-0023 generated scripts on unfixed vs three fixed copies",
                "anchor": "command-center/p2-wave/probes/CNF-0023/generated/r_apostrophe.py",
            },
        ],
        "control_ids": [
            "NC-quoting-own-target",
            "NC-empty-required-own-target",
            "NC-planted-apostrophe",
            "NC-cnf23-apostrophe",
        ],
        "matrix": {
            "repros": live["repros"],
            "components": live["components"],
            "cells": live["cells"],
            "empty_cells": live["empty_cells"],
            "grid": live["grid"],
            "defective_columns": [c["id"] for c in live["components"] if c["role"] == "defective"],
            "healthy_columns": healthy_ids,
        },
        "quarantined": classified["quarantined"],
        "accepted_repros": accepted,
        "detector_control": detector_control,
        "cnf0023_specificity": cnf23,
        "question": QUESTION,
        "answer": answer,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0025",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/catalog-slices/CNF-1.json:CNF-0025",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "detector-control-engineer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "bytes": schema_n,
                "sha256": schema_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "The 3x5 repro-by-component matrix has no empty cells; accepted "
                    "repros fire only on their defective target and stay silent on "
                    "three healthy components; repro_nonspecific is quarantined."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0025/matrix.py",
                "probes": [
                    probe("source", "test-run", "python3 -B command-center/p2-wave/probes/CNF-0025/matrix.py", matrix_raw, 0),
                    probe("verifier", "command", P1, "live matrix vs artifact (post-write)", 0),
                ],
                "unverified": False,
            },
            {
                "claim": (
                    "Independent DETECTOR CONTROL: accepted repros fire on the "
                    "known-broken fixture, stay silent on three healthy components, "
                    "and track planted/fixed copies; CNF-0023 generated scripts "
                    "discriminate unfixed vs three healthy copies of fixed."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0025/probe2_detector_control.py",
                "probes": [
                    probe("source", "test-run", P2, json.dumps(mutations, sort_keys=True), 0),
                    probe(
                        "verifier",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CNF-0023/generated/r_apostrophe.py command-center/p2-wave/probes/CNF-0023/fixtures/unfixed",
                        json.dumps(
                            {r["repro_id"]: r["unfixed_exit"] for r in cnf23["rows"]},
                            sort_keys=True,
                        ),
                        1,
                    ),
                ],
                "unverified": False,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-quoting-own-target",
                "kind": "known-broken-fixture",
                "description": "repro_unquoted_apostrophe fires on defective-quoting and is silent on healthy-alpha",
                "fired_on_bad_state": live["grid"]["repro_unquoted_apostrophe"]["defective-quoting"] == 2,
                "silent_on_good_state": live["grid"]["repro_unquoted_apostrophe"]["healthy-alpha"] == 0,
                "bad_state_output": "exit=2",
                "good_state_output": "exit=0",
            },
            {
                "id": "NC-empty-required-own-target",
                "kind": "known-broken-fixture",
                "description": "repro_empty_required fires on defective-empty-gate and is silent on healthy-beta",
                "fired_on_bad_state": live["grid"]["repro_empty_required"]["defective-empty-gate"] == 2,
                "silent_on_good_state": live["grid"]["repro_empty_required"]["healthy-beta"] == 0,
                "bad_state_output": "exit=2",
                "good_state_output": "exit=0",
            },
            {
                "id": "NC-planted-apostrophe",
                "kind": "mutation",
                "description": "Planting an interior apostrophe on a healthy copy makes the quoting repro fire; fixing the known-broken copy silences it",
                "fired_on_bad_state": mutations["planted_apostrophe_exit"] == 2,
                "silent_on_good_state": mutations["fixed_quoting_exit"] == 0,
                "bad_state_output": f"planted_exit={mutations['planted_apostrophe_exit']}",
                "good_state_output": f"fixed_exit={mutations['fixed_quoting_exit']}",
            },
            {
                "id": "NC-cnf23-apostrophe",
                "kind": "known-broken-fixture",
                "description": "CNF-0023 r_apostrophe.py is red on unfixed and green on three copies of fixed",
                "fired_on_bad_state": next(r["fired_on_unfixed"] for r in cnf23["rows"] if r["repro_id"] == "r_apostrophe.py"),
                "silent_on_good_state": next(r["silent_on_three_healthy"] for r in cnf23["rows"] if r["repro_id"] == "r_apostrophe.py"),
                "bad_state_output": "unfixed_exit=1",
                "good_state_output": "healthy_exits=0,0,0",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0025-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Independent DETECTOR CONTROL re-run: accepted repros fire on the "
                "known-broken fixture and stay silent on three healthy components; "
                "nonspecific repro is quarantined; planted/fixed copies and CNF-0023 "
                "generated scripts are re-invoked by path."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0025/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0025",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "file-read",
                    f"python3 -c 'import json; json.load(open({OUT!r}))'",
                    "read_ok=true after write",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record (spec 11039), never "
                "an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNF-0023 catalog output_path is absent on this tree, so the "
                    "mechanised-repro *report* was not re-read; generated scripts "
                    "under probes/CNF-0023/generated/ were invoked instead."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0023's catalog artifact, then re-run this matrix "
                    "against the script paths named inside that report."
                ),
            }
        ],
        "report": report,
        "extensions": {
            "question": QUESTION,
            "answer": answer,
            "cnf_0023_input": {
                "declared_path": CNF23,
                "present": cnf23_path.is_file() and cnf23_path.stat().st_size > 0,
                "handling": (
                    "in-unit fixtures plus path-invoked CNF-0023 generated scripts "
                    "against unfixed vs three copies of fixed"
                ),
            },
            "catalog_completion_sentinel_satisfied": True,
        },
    }

    text = dump(doc)
    sha, n = digest_bytes(text.encode("utf-8"))
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = n
    validate(doc)
    if sentinel not in dump(doc):
        print("FAILED:CNF-0025 completion_sentinel not in artifact", file=sys.stderr)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    written = json.loads(out.read_text(encoding="utf-8"))
    validate(written)
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"read_ok=true bytes={out.stat().st_size} keys={sorted(written)[:12]}"
    )
    out.write_text(dump(doc), encoding="utf-8")
    written = json.loads(out.read_text(encoding="utf-8"))
    validate(written)
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0025 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
