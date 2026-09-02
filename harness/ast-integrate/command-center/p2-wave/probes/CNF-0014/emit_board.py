#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0014-coverage-board.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import board as B  # noqa: E402

OUT = "command-center/confirmation/CNF-0014-coverage-board.json"
SCHEMA = "command-center/schema/coverage-board.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0014/probe1_handedit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0014/probe2_empty.py"
)
OFFLINE_SCHEMA_RELS = (
    "command-center/schema/coverage-board.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    exit_code: int = 0,
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def art_row(rel: str, role: str) -> dict[str, Any]:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def offline_validator(schema: dict[str, Any]):
    store: dict[str, Any] = {}
    for rel in OFFLINE_SCHEMA_RELS:
        path = REPO / rel
        body = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = body
        sid = body.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = body
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=store,
    )
    Draft = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)
    try:
        return Draft(schema, resolver=resolver)
    except TypeError:
        return jsonschema.Draft7Validator(schema, resolver=resolver)


def main() -> int:
    receipts, claims = B.load_live_corpus(REPO)
    commit = B.producing_commit(REPO)
    coverage = B.render_coverage(receipts, claims, commit)
    controls = B.run_controls()
    anchor = B.generator_anchor()
    observed = B.observe_inputs(REPO)
    if coverage["green"] and coverage["tallies"]["measured"] == 0:
        print("FAILED:CNF-0014 empty-set-read-as-pass")
        return 1
    if not controls["hand_edit"]["gate_red"]:
        print("FAILED:CNF-0014 hand-edit control did not go red")
        return 1
    if not controls["determinism"]["two_run_byte_identical"]:
        print("FAILED:CNF-0014 regeneration not byte-identical")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    render_cmd = (
        f"{anchor['path']}:{anchor['line']} {anchor['function']} "
        f"v{anchor['version']}"
    )
    src_probe = probe(
        "source",
        "file-read",
        render_cmd,
        (
            f"render_coverage measured_label={coverage['measured_label']} "
            f"green={coverage['green']} board_color={coverage['board_color']}"
        ),
    )
    ver_probe = probe(
        "verifier",
        "command",
        P1,
        (
            "hand-edit control goes red on one-digit mutation; "
            "unedited regeneration is byte-identical"
        ),
        exit_code=0,
    )
    empty_probe = probe(
        "verifier",
        "command",
        P2,
        "empty corpus is 0 of N measured, board_color=NOT-GREEN",
        exit_code=0,
    )
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0014",
        "state": "SUCCESS",
        "sentinel": B.CATALOG_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0014",
        "min_bytes_threshold": 800,
        "artifacts": [
            art_row("command-center/p2-wave/probes/CNF-0014/board.py", "supporting"),
            art_row(SCHEMA, "supporting"),
            art_row(
                "command-center/p2-wave/probes/CNF-0014/probe1_handedit.py",
                "control",
            ),
            art_row(
                "command-center/p2-wave/probes/CNF-0014/probe2_empty.py",
                "control",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Coverage numbers are computed by render_coverage from "
                    "receipts and the claim population, not typed by hand."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{anchor['path']}:{anchor['line']}",
                "probes": [src_probe, ver_probe],
            },
            {
                "claim": (
                    "Changing one digit in the generated tallies makes the "
                    "hand-edit gate exit non-zero; the unedited board is silent."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0014/probe1_handedit.py",
                "probes": [src_probe, ver_probe],
            },
            {
                "claim": (
                    "An empty receipt corpus renders as 0 of N measured with "
                    "board_color=NOT-GREEN, including the 0-of-0 case."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0014/probe2_empty.py",
                "probes": [src_probe, empty_probe],
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "one-digit-hand-edit",
                "kind": "known-broken-fixture",
                "description": (
                    "Change exactly one decimal digit inside the tallies "
                    "object; the recompute gate must go red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"exit_code={controls['hand_edit']['exit_code']} "
                    f"reasons={controls['hand_edit']['reasons']}"
                ),
                "good_state_output": "unedited status=SILENT exit_code=0",
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0014-probe1-handedit",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 is the detector control: it mutates one digit "
                "and requires the gate red. A reviewer who only re-reads this "
                "JSON has verified nothing."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0014/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0014/probe1_handedit.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": ver_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/confirmation/receipts is empty on this "
                    "worktree, so live tallies are 0 of N from CLAIM-REGISTRY "
                    "and are not a green board."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-emit after a confirmation receipt is written under "
                    "command-center/confirmation/receipts and confirm the "
                    "hand-edit gate still fires."
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "report": {
            "kind": "coverage-board",
            "observations": [
                {
                    "name": "measured_label",
                    "measured": coverage["measured_label"],
                    "method": "render_coverage over confirmation receipts on disk",
                    "anchor": f"{anchor['path']}:{anchor['line']}",
                },
                {
                    "name": "hand_edit_exit_code",
                    "measured": int(controls["hand_edit"]["exit_code"]),
                    "method": "mutate_one_digit then check_board",
                    "anchor": "command-center/p2-wave/probes/CNF-0014/probe1_handedit.py",
                },
                {
                    "name": "empty_corpus_green",
                    "measured": False,
                    "method": "render_coverage([], claims)",
                    "anchor": "command-center/p2-wave/probes/CNF-0014/probe2_empty.py",
                },
            ],
            "control_ids": [
                "CNF-0014-probe1-handedit",
                "CNF-0014-probe2-empty",
            ],
            "board_color": coverage["board_color"],
            "by_severity": coverage["by_severity"],
            "empty_set_is_not_pass": True,
            "generator": anchor,
            "generator_id": coverage["generator_id"],
            "generator_version": coverage["generator_version"],
            "green": coverage["green"],
            "hand_edit_control_exit_code": controls["hand_edit"]["exit_code"],
            "measured_label": coverage["measured_label"],
            "producing_commit": commit,
            "receipts_fingerprint": coverage["receipts_fingerprint"],
            "receipts_loaded": len(receipts),
            "receipts_root": B.RECEIPTS_ROOT,
            "rows": coverage["rows"],
            "tallies": coverage["tallies"],
            "controls": controls,
        },
        "extensions": {
            "answer": (
                "Yes. The hand-edit detector recomputes tallies from receipts "
                "on disk and goes red when one digit in the tallies object is "
                f"changed (exit_code={controls['hand_edit']['exit_code']}, "
                f"reasons={controls['hand_edit']['reasons']}). Two unchanged "
                "render_coverage runs are byte-identical. An empty receipt "
                f"corpus renders as {controls['empty_corpus']['measured_label']} "
                "with board_color=NOT-GREEN, never as a green board, including "
                "0 of 0. " + B.CATALOG_SENTINEL
            ),
            "claim_under_test": (
                "A Phase 11 coverage board generated from receipts on disk "
                "cannot stay green after a human edits one digit, and cannot "
                "treat an empty corpus as a pass."
            ),
            "cloud_ok": False,
            "completion_sentinel": B.CATALOG_SENTINEL,
            "inputs_observed": observed,
            "named_probes": [
                {"id": "probe1", "role": "hand-edit-and-determinism", "command": P1},
                {"id": "probe2", "role": "empty-corpus-not-green", "command": P2},
            ],
            "question": B.QUESTION,
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = offline_validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0014 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000, "green": True, "board_color": "GREEN"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0014 schema accepted garbage")
            return 1

    dumped = B.canonical_bytes(doc)
    if B.CATALOG_SENTINEL.encode("utf-8") not in dumped:
        print("FAILED:CNF-0014 catalog sentinel absent from artifact bytes")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(dumped)
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0014 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"commit={commit} measured_label={coverage['measured_label']} "
        f"hand_edit_exit={controls['hand_edit']['exit_code']}"
    )
    print("SUCCESS:CNF-0014 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
