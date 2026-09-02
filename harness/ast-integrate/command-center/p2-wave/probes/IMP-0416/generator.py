#!/usr/bin/env python3
"""Negative-control fixture generator for the completion reducer.

Synthesizes one all-conditions-satisfied workspace and twelve mutants. Each
mutant differs from the positive workspace by exactly one intentional change
targeting one of the twelve completion conditions. The reducer is then run
against every workspace so ACCEPT on a mutant names an unenforced condition.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any, Callable

from reducer import CONDITIONS, digest_file, judge

PAYLOAD_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "completion-subject-payload",
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "payload", "unit_id"],
    "properties": {
        "kind": {"const": "completion-subject-payload"},
        "payload": {"type": "string", "minLength": 16},
        "unit_id": {"type": "string", "minLength": 3},
    },
}

POSITIVE_SENTINEL = "SENTINEL:GEN-0001:ALL-GREEN"
UNIT = "GEN-0001"


def _dump(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def positive_payload() -> dict[str, Any]:
    return {
        "kind": "completion-subject-payload",
        "payload": "positive-control-payload-" + ("*" * 220),
        "unit_id": UNIT,
    }


def tiny_valid_payload() -> dict[str, Any]:
    return {
        "kind": "completion-subject-payload",
        "payload": "sixteen-chars-ok",
        "unit_id": UNIT,
    }


def large_invalid_payload() -> dict[str, Any]:
    return {
        "kind": "not-the-required-const",
        "payload": "x" * 220,
        "unit_id": UNIT,
    }


def positive_subject() -> dict[str, Any]:
    return {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": POSITIVE_SENTINEL,
        "expected_sentinel": POSITIVE_SENTINEL,
        "artifact_rel": "artifact.json",
        "schema_rel": "payload.schema.json",
        "manifest_rel": "UNIT-ARTIFACT-MANIFEST.json",
        "min_bytes_threshold": 128,
        "evidence": [
            {
                "claim": "Primary artifact is on disk.",
                "anchor": "artifact.json:1",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "Schema validation passed.",
                "anchor": "payload.schema.json:1",
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [{"id": "t1", "command": "pytest -q", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "c1",
                "kind": "mutation",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "consumers": [
            {
                "consumer": "downstream-reader",
                "artifact_rel": "artifact.json",
                "executed": True,
                "read_ok": True,
            }
        ],
    }


def write_manifest(workspace: Path, subject: dict[str, Any]) -> None:
    art = workspace / str(subject["artifact_rel"])
    sha, size = digest_file(art)
    _dump(
        workspace / str(subject["manifest_rel"]),
        {
            "schema_version": 1,
            "unit_id": subject["unit_id"],
            "artifacts": [
                {
                    "path": subject["artifact_rel"],
                    "sha256": sha,
                    "bytes": size,
                    "present": art.is_file(),
                    "unit_id": subject["unit_id"],
                    "role": "primary",
                }
            ],
        },
    )


def write_positive(workspace: Path) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    subject = positive_subject()
    _dump(workspace / "payload.schema.json", PAYLOAD_SCHEMA)
    _dump(workspace / "artifact.json", positive_payload())
    _dump(workspace / "subject.json", subject)
    write_manifest(workspace, subject)
    return subject


def _rewrite_subject(workspace: Path, mutator: Callable[[dict], None]) -> None:
    path = workspace / "subject.json"
    subject = json.loads(path.read_text(encoding="utf-8"))
    mutator(subject)
    _dump(path, subject)


def apply_c01(workspace: Path) -> str:
    _rewrite_subject(workspace, lambda s: s.update(state="RUNNING"))
    return "state set to RUNNING (non-terminal)"


def apply_c02(workspace: Path) -> str:
    art = workspace / "artifact.json"
    if art.is_file():
        art.unlink()
    return "unlinked artifact.json (path in subject remains)"


def apply_c03(workspace: Path) -> str:
    _dump(workspace / "artifact.json", tiny_valid_payload())
    subject = json.loads((workspace / "subject.json").read_text(encoding="utf-8"))
    write_manifest(workspace, subject)
    return "replaced artifact with schema-valid payload below min_bytes_threshold"


def apply_c04(workspace: Path) -> str:
    _dump(workspace / "artifact.json", large_invalid_payload())
    subject = json.loads((workspace / "subject.json").read_text(encoding="utf-8"))
    write_manifest(workspace, subject)
    return "replaced artifact with oversized JSON that fails payload.schema.json"


def apply_c05(workspace: Path) -> str:
    _rewrite_subject(workspace, lambda s: s.update(sentinel=""))
    return "sentinel set to empty string"


def apply_c06(workspace: Path) -> str:
    _rewrite_subject(workspace, lambda s: s.update(evidence=s["evidence"][:1]))
    return "evidence reduced to one anchor (SUCCESS needs two)"


def apply_c07(workspace: Path) -> str:
    def mut(s: dict) -> None:
        tests = copy.deepcopy(s["tests"])
        tests[0]["result"] = "FAIL"
        s["tests"] = tests

    _rewrite_subject(workspace, mut)
    return "tests[0].result set to FAIL"


def apply_c08(workspace: Path) -> str:
    def mut(s: dict) -> None:
        controls = copy.deepcopy(s["negative_controls"])
        controls[0]["fired_on_bad_state"] = False
        s["negative_controls"] = controls

    _rewrite_subject(workspace, mut)
    return "negative_control.fired_on_bad_state false (inert detector)"


def apply_c09(workspace: Path) -> str:
    def mut(s: dict) -> None:
        reviewer = copy.deepcopy(s["reviewer"])
        reviewer["independent"] = False
        s["reviewer"] = reviewer

    _rewrite_subject(workspace, mut)
    return "reviewer.independent flipped to false (self-review)"


def apply_c10(workspace: Path) -> str:
    def mut(s: dict) -> None:
        s["defects"] = [
            {
                "id": "D1",
                "severity": "P0",
                "status": "open",
                "summary": "open blocker attached to a success subject",
            }
        ]

    _rewrite_subject(workspace, mut)
    return "open P0 defect attached"


def apply_c11(workspace: Path) -> str:
    subject = json.loads((workspace / "subject.json").read_text(encoding="utf-8"))
    _dump(
        workspace / str(subject["manifest_rel"]),
        {"schema_version": 1, "unit_id": subject["unit_id"], "artifacts": []},
    )
    return "manifest artifacts list emptied (file still on disk)"


def apply_c12(workspace: Path) -> str:
    def mut(s: dict) -> None:
        consumers = copy.deepcopy(s["consumers"])
        consumers[0]["executed"] = False
        consumers[0]["read_ok"] = False
        s["consumers"] = consumers

    _rewrite_subject(workspace, mut)
    return "consumer.executed and read_ok set false (file still readable)"


MUTATORS: dict[int, Callable[[Path], str]] = {
    1: apply_c01,
    2: apply_c02,
    3: apply_c03,
    4: apply_c04,
    5: apply_c05,
    6: apply_c06,
    7: apply_c07,
    8: apply_c08,
    9: apply_c09,
    10: apply_c10,
    11: apply_c11,
    12: apply_c12,
}


def rel_of(path: Path, repo: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return str(path)


def write_exit_zero_alone(workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    _dump(workspace / "process_exit.json", {"exit_code": 0, "note": "no subject"})


def materialize(root: Path, repo: Path | None = None) -> dict[str, Any]:
    """Write positive, twelve negatives, and the exit-zero-alone control."""
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    repo = repo or root.parents[3]

    pos_dir = root / "positive"
    write_positive(pos_dir)
    pos_verdict = judge(pos_dir, process_exit_code=0)

    rows: list[dict[str, Any]] = []
    for n, cid, text in ((c[1], c[0], c[2]) for c in CONDITIONS):
        dest = root / f"negative-{n:02d}"
        write_positive(dest)
        how = MUTATORS[n](dest)
        verdict = judge(dest)
        accept = verdict["verdict"] == "ACCEPT"
        rows.append(
            {
                "id": cid,
                "condition": n,
                "condition_text": text,
                "mutation": how,
                "fixture_path": rel_of(dest, repo),
                "reducer_verdict": verdict["verdict"],
                "overall": verdict["overall"],
                "failing": verdict["failing"],
                "unenforced_condition": (
                    f"{cid} {text}" if accept else None
                ),
                "conditions": verdict["conditions"],
            }
        )

    ez_dir = root / "exit-zero-alone"
    write_exit_zero_alone(ez_dir)
    ez_verdict = judge(ez_dir, process_exit_code=0)

    unenforced = [
        f"{r['id']} {r['condition_text']}"
        for r in rows
        if r["reducer_verdict"] == "ACCEPT"
    ]
    return {
        "positive": {
            "fixture_path": rel_of(pos_dir, repo),
            "reducer_verdict": pos_verdict["verdict"],
            "overall": pos_verdict["overall"],
            "failing": pos_verdict["failing"],
            "conditions": pos_verdict["conditions"],
            "process_exit_code": 0,
            "exit_code_consulted_for_complete": pos_verdict[
                "exit_code_consulted_for_complete"
            ],
        },
        "mutations": rows,
        "exit_zero_alone": {
            "fixture_path": rel_of(ez_dir, repo),
            "reducer_verdict": ez_verdict["verdict"],
            "overall": ez_verdict["overall"],
            "failing": ez_verdict["failing"],
            "process_exit_code": 0,
            "exit_code_consulted_for_complete": ez_verdict[
                "exit_code_consulted_for_complete"
            ],
        },
        "unenforced_conditions": unenforced,
        "all_twelve_rejected": all(r["reducer_verdict"] == "REJECT" for r in rows),
        "positive_accepted": pos_verdict["verdict"] == "ACCEPT",
        "exit_zero_alone_rejected": ez_verdict["verdict"] == "REJECT",
        "reducer_module": rel_of(Path(__file__).resolve().parent / "reducer.py", repo),
    }


def independence_ok(row: dict[str, Any]) -> bool:
    """C02 may cascade into size/schema/consumer. All other mutants must isolate."""
    failing = list(row.get("failing") or [])
    cid = row["id"]
    if cid not in failing:
        return False
    if cid == "C02":
        return True
    return failing == [cid]
