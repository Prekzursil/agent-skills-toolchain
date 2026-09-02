"""Caller-side harvest AND-gate.

Exit 0 alone is not SUCCESS. A complete parsed output file is required.
Empty, absent, unparseable, or fire-and-forget progress text is SEVERED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BACKGROUND_MARKERS = (
    "started in the background",
    "Check /codex:status",
)
UNIT = "RES-0162"


def harvest(exit_code: int, output_path: Path | None) -> dict[str, Any]:
    """Classify one invocation from the caller's side."""
    rec: dict[str, Any] = {
        "exit_code": exit_code,
        "output_path": None if output_path is None else str(output_path),
        "output_bytes": 0,
        "output_exists": False,
        "verdict": None,
        "classification": None,
        "record": None,
    }
    if output_path is not None and output_path.is_file():
        rec["output_exists"] = True
        rec["output_bytes"] = output_path.stat().st_size

    if exit_code != 0:
        rec["classification"] = f"exit-{exit_code}"
        rec["verdict"] = "FAILED"
        rec["note"] = "non-zero exit is not SUCCESS; harvest does not look at the file to green-wash"
        return rec

    if output_path is None or not rec["output_exists"] or rec["output_bytes"] <= 0:
        rec["classification"] = "severed-stream"
        rec["verdict"] = "SEVERED"
        rec["note"] = "exit 0 with empty or absent output file is SEVERED, not SUCCESS"
        return rec

    text = output_path.read_text(encoding="utf-8", errors="replace")
    if any(m in text for m in BACKGROUND_MARKERS):
        rec["classification"] = "severed-stream"
        rec["verdict"] = "SEVERED"
        rec["note"] = "progress/status stream is not a harvested result"
        return rec
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        rec["classification"] = "severed-stream"
        rec["verdict"] = "SEVERED"
        rec["note"] = "exit 0 with unparseable output is SEVERED, not SUCCESS"
        return rec
    if not isinstance(doc, dict):
        rec["classification"] = "severed-stream"
        rec["verdict"] = "SEVERED"
        rec["note"] = "harvested payload must be a JSON object"
        return rec
    rec["classification"] = "SUCCESS"
    rec["verdict"] = "SUCCESS"
    rec["record"] = doc
    rec["note"] = "AND-gate: exit 0 AND non-empty parseable object"
    return rec


def harvest_exit_only(exit_code: int, output_path: Path | None) -> dict[str, Any]:
    """Naive poller: exit code alone. Used as the known-wrong control."""
    del output_path
    if exit_code == 0:
        return {
            "verdict": "SUCCESS",
            "classification": "exit-0",
            "note": "exit-only harvester cannot see a severed stream",
        }
    return {
        "verdict": "FAILED",
        "classification": f"exit-{exit_code}",
        "note": "exit-only harvester",
    }


def _write(path: Path, body: str | None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        if path.exists():
            path.unlink()
        return path
    path.write_text(body, encoding="utf-8")
    return path


def both_states(tmp: Path) -> dict[str, Any]:
    """Plant complete vs empty/absent vs progress. Exit 0 in every plant."""
    complete_body = json.dumps(
        {"ok": True, "unit_id": UNIT, "payload": "harvest-complete"},
        sort_keys=True,
    )
    plants = [
        {
            "id": "harvest-complete",
            "plant": "exit 0 and a non-empty parseable JSON object at output-last-message",
            "exit_code": 0,
            "body": complete_body,
            "expect_and_gate": "SUCCESS",
            "expect_exit_only": "SUCCESS",
        },
        {
            "id": "harvest-empty",
            "plant": "exit 0 and a zero-byte output-last-message file",
            "exit_code": 0,
            "body": "",
            "expect_and_gate": "SEVERED",
            "expect_exit_only": "SUCCESS",
        },
        {
            "id": "harvest-absent",
            "plant": "exit 0 and no output-last-message file",
            "exit_code": 0,
            "body": None,
            "expect_and_gate": "SEVERED",
            "expect_exit_only": "SUCCESS",
        },
        {
            "id": "harvest-progress-stream",
            "plant": "exit 0 and a fire-and-forget progress blob containing background markers",
            "exit_code": 0,
            "body": "started in the background\nCheck /codex:status\n",
            "expect_and_gate": "SEVERED",
            "expect_exit_only": "SUCCESS",
        },
        {
            "id": "harvest-nonzero",
            "plant": "exit 1 with a complete parseable JSON object (must not SUCCESS)",
            "exit_code": 1,
            "body": complete_body,
            "expect_and_gate": "FAILED",
            "expect_exit_only": "FAILED",
        },
    ]
    cases: list[dict[str, Any]] = []
    for spec in plants:
        path = tmp / spec["id"] / "output-last-message.json"
        if spec["body"] is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.unlink()
        else:
            _write(path, spec["body"])
        gated = harvest(spec["exit_code"], path)
        naive = harvest_exit_only(spec["exit_code"], path)
        and_ok = gated.get("verdict") == spec["expect_and_gate"]
        naive_ok = naive.get("verdict") == spec["expect_exit_only"]
        watcher_wake = gated.get("verdict") == "SUCCESS"
        poller_wake = naive.get("verdict") == "SUCCESS"
        verdict = "PASS" if and_ok and naive_ok else "FAIL"
        cases.append(
            {
                "id": spec["id"],
                "plant": spec["plant"],
                "exit_code": spec["exit_code"],
                "and_gate_verdict": gated.get("verdict"),
                "exit_only_verdict": naive.get("verdict"),
                "classification": gated.get("classification"),
                "watcher_wake": watcher_wake,
                "poller_wake": poller_wake,
                "verdict": verdict,
                "note": gated.get("note"),
            }
        )

    empty = next(c for c in cases if c["id"] == "harvest-empty")
    complete = next(c for c in cases if c["id"] == "harvest-complete")
    # Catalog both-states: complete -> SUCCESS; empty/absent exit 0 -> SEVERED.
    # Exit-only must SUCCESS the empty plant (otherwise the control does not discriminate).
    discriminates = (
        complete["and_gate_verdict"] == "SUCCESS"
        and empty["and_gate_verdict"] == "SEVERED"
        and empty["exit_only_verdict"] == "SUCCESS"
        and complete["exit_only_verdict"] == "SUCCESS"
    )
    passed = discriminates and all(c["verdict"] == "PASS" for c in cases)
    false_success = [
        c["id"]
        for c in cases
        if c["and_gate_verdict"] == "SUCCESS" and c["id"] != "harvest-complete"
    ]
    return {
        "pass": passed,
        "discriminates": discriminates,
        "cases": cases,
        "false_wake_rate": (len(false_success) / max(len(cases), 1)),
        "exit_only_cannot_be_the_gate": bool(empty["exit_only_verdict"] == "SUCCESS"),
    }
