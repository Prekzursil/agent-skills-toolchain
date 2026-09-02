#!/usr/bin/env python3
"""Durable workflow resume with no process-table, session-env, or temp dependence.

Resume reads exactly one durable checkpoint file under --durable-root. Session
environment variables, /proc, and TMPDIR are not consulted on the production
path. A mutant path that plants a temp-dir sidecar exists only so the detector
control can prove cold resume fails when that dependency is planted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from handled_ledger import (  # noqa: E402
    VolatileStoreError,
    atomic_write_json,
    is_under_temp,
    read_json,
)

STEPS = ("fetch", "reduce", "emit")
CHECKPOINT_NAME = "checkpoint.json"
SIDECAR_NAME = "volatile-sidecar.json"


class ResumeError(RuntimeError):
    """Resume could not reconstruct run state from durable bytes."""


def durable_checkpoint_path(durable_root: Path) -> Path:
    # STATE_READ durable_root/checkpoint.json DURABLE-DISK
    return Path(durable_root).expanduser().resolve() / CHECKPOINT_NAME


def _new_state(run_id: str, payload: str) -> dict:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "schema": "tst-0169-checkpoint/v1",
        "run_id": run_id,
        "payload_sha256": digest,
        "completed": ["fetch"],
        "open": ["reduce", "emit"],
        "receipts": {"fetch": digest[:16]},
    }


def persist_durable_checkpoint(durable_root: Path, run_id: str, payload: str) -> Path:
    path = durable_checkpoint_path(durable_root)
    if is_under_temp(path):
        raise VolatileStoreError(f"durable_root resolves under temp: {path}")
    return atomic_write_json(path, _new_state(run_id, payload), allow_volatile=False)


def load_durable_checkpoint(durable_root: Path) -> dict:
    path = durable_checkpoint_path(durable_root)
    doc = read_json(path, allow_volatile=False)
    if not isinstance(doc, dict) or doc.get("schema") != "tst-0169-checkpoint/v1":
        raise ResumeError(f"checkpoint schema refused: {path}")
    if "run_id" not in doc or "completed" not in doc:
        raise ResumeError(f"checkpoint missing required fields: {path}")
    return doc


def _finish(doc: dict) -> dict:
    completed = list(doc.get("completed") or [])
    receipts = dict(doc.get("receipts") or {})
    for step in STEPS:
        if step not in completed:
            completed.append(step)
            receipts[step] = hashlib.sha256(
                f"{doc['run_id']}:{step}:{doc['payload_sha256']}".encode("utf-8")
            ).hexdigest()[:16]
    out = dict(doc)
    out["completed"] = completed
    out["open"] = []
    out["receipts"] = receipts
    out["resumed"] = True
    return out


def resume_from_durable(durable_root: Path) -> dict:
    """Production resume: durable checkpoint file only. No env, /proc, or tmp."""
    doc = load_durable_checkpoint(durable_root)
    finished = _finish(doc)
    atomic_write_json(durable_checkpoint_path(durable_root), finished, allow_volatile=False)
    return finished


def mutant_persist_temp_sidecar(durable_root: Path, run_id: str, payload: str) -> Path:
    """Detector-control mutant: plants a sidecar under tempfile.gettempdir()."""
    path = durable_checkpoint_path(durable_root)
    sidecar = Path(tempfile.gettempdir()).resolve() / f"{run_id}-{SIDECAR_NAME}"
    state = _new_state(run_id, payload)
    state["volatile_sidecar_name"] = sidecar.name
    atomic_write_json(path, state, allow_volatile=is_under_temp(path))
    atomic_write_json(
        sidecar,
        {"run_id": run_id, "kind": "session-temp-sidecar"},
        allow_volatile=True,
    )
    return sidecar


def mutant_resume_temp_sidecar(durable_root: Path) -> dict:
    """Resume that requires the temp sidecar. Cold reboot that clears tmp fails."""
    path = durable_checkpoint_path(durable_root)
    doc = json.loads(path.read_text(encoding="utf-8"))
    sidecar = Path(tempfile.gettempdir()).resolve() / str(
        doc.get("volatile_sidecar_name") or SIDECAR_NAME
    )
    if not sidecar.is_file():
        raise ResumeError("TEMP-DEPENDENCY: volatile sidecar missing after cold start")
    extra = json.loads(sidecar.read_text(encoding="utf-8"))
    if extra.get("run_id") != doc.get("run_id"):
        raise ResumeError("TEMP-DEPENDENCY: sidecar run_id mismatch")
    return _finish(doc)


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cold_resume")
    parser.add_argument("action", choices=("persist", "resume", "mutant-persist", "mutant-resume"))
    parser.add_argument("--durable-root", required=True)
    parser.add_argument("--run-id", default="run-1")
    parser.add_argument("--payload", default="fixture-payload")
    parser.add_argument("--tmp-dir", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    root = Path(args.durable_root)
    try:
        if args.action == "persist":
            result = {"checkpoint": str(persist_durable_checkpoint(root, args.run_id, args.payload))}
        elif args.action == "resume":
            result = resume_from_durable(root)
        elif args.action == "mutant-persist":
            sidecar = mutant_persist_temp_sidecar(root, args.run_id, args.payload)
            result = {"sidecar": str(sidecar)}
        else:
            result = mutant_resume_temp_sidecar(root)
    except (ResumeError, VolatileStoreError, OSError, json.JSONDecodeError) as exc:
        print(f"FAILED:{exc}")
        return 1
    text = json.dumps(result, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if args.action in {"resume", "mutant-resume"}:
        completed = result.get("completed") if isinstance(result, dict) else None
        if completed != list(STEPS):
            print("FAILED:resume did not finish all steps")
            return 1
    print(f"SUCCESS:cold-resume action={args.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
