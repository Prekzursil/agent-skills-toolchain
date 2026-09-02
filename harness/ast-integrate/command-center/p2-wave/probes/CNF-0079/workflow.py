#!/usr/bin/env python3
"""Resumable fixture workflow for CNF-0079 kill/resume parity.

Four stages with durable checkpoints and append-only side effects.
Resume skips completed stages. A corrupted checkpoint is refused.
This is a fixture runner: the tree has no production workflow engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

STAGES = ("ingest", "transform", "fuse", "emit")
WORKFLOW_ID = "cnf-0079-resume-fixture"
MAC_SECRET = "cnf-0079-checkpoint-mac-v1"
DEFAULT_INPUT: dict[str, Any] = {
    "seed": 20260824,
    "routing_pin": "fixture-route-v1",
    "records": [
        {"id": "a", "value": 11},
        {"id": "b", "value": 23},
        {"id": "c", "value": 41},
        {"id": "d", "value": 7},
    ],
}


class CorruptCheckpoint(Exception):
    """Checkpoint failed integrity or consistency checks."""


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(obj, sort_keys=True, indent=2) + "\n"
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line if line.endswith("\n") else line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def checkpoint_body(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc[k] for k in sorted(doc) if k != "integrity"}


def sign_checkpoint(doc: dict[str, Any]) -> str:
    payload = canonical(checkpoint_body(doc))
    return hashlib.sha256(f"{MAC_SECRET}|".encode() + payload).hexdigest()


def verify_checkpoint(doc: dict[str, Any]) -> None:
    got = str(doc.get("integrity") or "")
    want = sign_checkpoint(doc)
    if got != want:
        raise CorruptCheckpoint("checkpoint integrity mismatch")
    if doc.get("schema_version") != 1:
        raise CorruptCheckpoint("unsupported checkpoint schema_version")
    if doc.get("workflow_id") != WORKFLOW_ID:
        raise CorruptCheckpoint("workflow_id mismatch")
    completed = doc.get("completed_stages")
    if not isinstance(completed, list):
        raise CorruptCheckpoint("completed_stages missing")
    for name in completed:
        if name not in STAGES:
            raise CorruptCheckpoint(f"unknown completed stage {name}")
    receipts = doc.get("stage_receipts")
    if not isinstance(receipts, dict):
        raise CorruptCheckpoint("stage_receipts missing")
    for name in completed:
        if name not in receipts:
            raise CorruptCheckpoint(f"missing receipt for {name}")


def input_digest(inputs: dict[str, Any]) -> str:
    return sha256_obj(inputs)


def stage_ingest(ctx: dict[str, Any]) -> dict[str, Any]:
    src = ctx["inputs"]
    return {
        "kind": "ingest",
        "input_digest": ctx["input_digest"],
        "routing_pin": src["routing_pin"],
        "seed": src["seed"],
        "records": [
            {"id": rec["id"], "value": int(rec["value"])} for rec in src["records"]
        ],
    }


def stage_transform(ctx: dict[str, Any]) -> dict[str, Any]:
    ingest = ctx["stage_outputs"]["ingest"]
    factor = int(ctx["inputs"]["seed"]) % 7 + 1
    rows = []
    for rec in ingest["records"]:
        value = int(rec["value"])
        rows.append(
            {
                "id": rec["id"],
                "value": value,
                "folded": value * factor + len(str(rec["id"])),
            }
        )
    return {"kind": "transform", "factor": factor, "rows": rows}


def stage_fuse(ctx: dict[str, Any]) -> dict[str, Any]:
    ingest = ctx["stage_outputs"]["ingest"]["records"]
    rows = ctx["stage_outputs"]["transform"]["rows"]
    fused = []
    for left, right in zip(ingest, rows):
        fused.append(
            {
                "id": left["id"],
                "ingest": int(left["value"]),
                "folded": int(right["folded"]),
                "mix": int(left["value"]) ^ int(right["folded"]),
            }
        )
    return {"kind": "fuse", "fused": fused}


def stage_emit(ctx: dict[str, Any]) -> dict[str, Any]:
    prior = {
        name: sha256_obj(ctx["stage_outputs"][name])
        for name in STAGES
        if name in ctx["stage_outputs"] and name != "emit"
    }
    return {
        "workflow_id": WORKFLOW_ID,
        "input_digest": ctx["input_digest"],
        "routing_pin": ctx["inputs"]["routing_pin"],
        "seed": ctx["inputs"]["seed"],
        "digest_chain": sha256_obj(prior),
        "stage_digests": prior,
        "output": ctx["stage_outputs"]["fuse"]["fused"],
    }


STAGE_FN = {
    "ingest": stage_ingest,
    "transform": stage_transform,
    "fuse": stage_fuse,
    "emit": stage_emit,
}


def empty_checkpoint(inputs: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "input_digest": input_digest(inputs),
        "completed_stages": [],
        "stage_receipts": {},
    }
    doc["integrity"] = sign_checkpoint(doc)
    return doc


def load_checkpoint(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorruptCheckpoint(f"checkpoint unreadable: {type(exc).__name__}") from exc
    if not isinstance(doc, dict):
        raise CorruptCheckpoint("checkpoint is not an object")
    verify_checkpoint(doc)
    return doc


def save_checkpoint(path: Path, doc: dict[str, Any]) -> None:
    doc = dict(doc)
    doc["integrity"] = sign_checkpoint(doc)
    write_json_atomic(path, doc)


def load_stage_outputs(workdir: Path, completed: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in completed:
        path = workdir / "stages" / f"{name}.json"
        if not path.is_file():
            raise CorruptCheckpoint(f"completed stage {name} missing output file")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CorruptCheckpoint(
                f"stage output {name} unreadable: {type(exc).__name__}"
            ) from exc
        out[name] = payload
    return out


def effect_counts(path: Path) -> dict[str, int]:
    counts = {name: 0 for name in STAGES}
    if not path.is_file():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        stage = line.split("\t", 1)[0]
        if stage in counts:
            counts[stage] += 1
    return counts


def run_workflow(
    workdir: Path,
    inputs: dict[str, Any] | None = None,
    *,
    resume: bool = False,
    stop_after: str | None = None,
    pause_after: str | None = None,
    redo_completed: bool = False,
) -> dict[str, Any]:
    """Execute or resume the fixture workflow.

    stop_after: write checkpoint after that stage and return (clean boundary).
    pause_after: write PAUSED then sleep (parent SIGKILL).
    redo_completed: known-broken mode that re-executes completed stages.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    inputs = json.loads(canonical(inputs or DEFAULT_INPUT).decode("utf-8"))
    ckpt_path = workdir / "checkpoint.json"
    effects_path = workdir / "effects.log"
    log_path = workdir / "run.log.jsonl"
    artifact_path = workdir / "artifact.json"

    digest = input_digest(inputs)
    executed: list[str] = []
    skipped: list[str] = []

    if resume:
        if not ckpt_path.is_file():
            raise CorruptCheckpoint("resume requested but checkpoint.json absent")
        ckpt = load_checkpoint(ckpt_path)
        if ckpt.get("input_digest") != digest:
            raise CorruptCheckpoint("checkpoint input_digest does not match inputs")
        completed = list(ckpt.get("completed_stages") or [])
        stage_outputs = load_stage_outputs(workdir, completed)
        for name in completed:
            recorded = ((ckpt.get("stage_receipts") or {}).get(name) or {}).get(
                "output_sha256"
            )
            live = sha256_obj(stage_outputs[name])
            if recorded != live:
                raise CorruptCheckpoint(f"stage {name} receipt hash mismatch")
        append_line(
            log_path,
            json.dumps(
                {"event": "resume", "completed": completed, "input_digest": digest},
                sort_keys=True,
            ),
        )
    else:
        if ckpt_path.is_file():
            ckpt_path.unlink()
        if effects_path.is_file():
            effects_path.unlink()
        if artifact_path.is_file():
            artifact_path.unlink()
        if log_path.is_file():
            log_path.unlink()
        stages_dir = workdir / "stages"
        if stages_dir.is_dir():
            for child in stages_dir.glob("*.json"):
                child.unlink()
        ckpt = empty_checkpoint(inputs)
        save_checkpoint(ckpt_path, ckpt)
        completed = []
        stage_outputs = {}
        append_line(
            log_path,
            json.dumps(
                {"event": "start", "input_digest": digest},
                sort_keys=True,
            ),
        )

    ctx = {
        "inputs": inputs,
        "input_digest": digest,
        "stage_outputs": stage_outputs,
        "workflow_id": WORKFLOW_ID,
    }

    for name in STAGES:
        already = name in completed
        if already and not redo_completed:
            skipped.append(name)
            append_line(
                log_path,
                json.dumps(
                    {
                        "event": "stage-skip",
                        "stage": name,
                        "reason": "checkpoint-complete",
                    },
                    sort_keys=True,
                ),
            )
            continue
        append_line(
            log_path,
            json.dumps({"event": "stage-start", "stage": name}, sort_keys=True),
        )
        payload = STAGE_FN[name](ctx)
        ctx["stage_outputs"][name] = payload
        write_json_atomic(workdir / "stages" / f"{name}.json", payload)
        token = sha256_obj(payload)
        append_line(effects_path, f"{name}\t{token}")
        if name not in completed:
            completed.append(name)
        receipts = dict(ckpt.get("stage_receipts") or {})
        receipts[name] = {"output_sha256": token, "effect_token": token}
        ckpt["completed_stages"] = list(completed)
        ckpt["stage_receipts"] = receipts
        ckpt["input_digest"] = digest
        save_checkpoint(ckpt_path, ckpt)
        executed.append(name)
        append_line(
            log_path,
            json.dumps(
                {"event": "stage-complete", "stage": name, "output_sha256": token},
                sort_keys=True,
            ),
        )
        if name == "emit":
            write_json_atomic(artifact_path, payload)
        if stop_after == name:
            append_line(
                log_path,
                json.dumps({"event": "stopped", "after": name}, sort_keys=True),
            )
            return {
                "status": "stopped",
                "after": name,
                "executed": executed,
                "skipped": skipped,
                "artifact_sha256": None,
                "effects": effect_counts(effects_path),
                "checkpoint": json.loads(ckpt_path.read_text(encoding="utf-8")),
            }
        if pause_after == name:
            paused = workdir / "PAUSED"
            with paused.open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(name + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            append_line(
                log_path,
                json.dumps({"event": "paused", "after": name}, sort_keys=True),
            )
            while True:
                time.sleep(30)

    artifact_sha = sha256_bytes(artifact_path.read_bytes())
    append_line(
        log_path,
        json.dumps(
            {"event": "complete", "artifact_sha256": artifact_sha},
            sort_keys=True,
        ),
    )
    return {
        "status": "complete",
        "after": None,
        "executed": executed,
        "skipped": skipped,
        "artifact_sha256": artifact_sha,
        "effects": effect_counts(effects_path),
        "checkpoint": json.loads(ckpt_path.read_text(encoding="utf-8")),
        "artifact": json.loads(artifact_path.read_text(encoding="utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNF-0079 resumable fixture workflow")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after", choices=STAGES, default=None)
    parser.add_argument("--pause-after", choices=STAGES, default=None)
    parser.add_argument("--redo-completed", action="store_true")
    parser.add_argument("--inputs", default=None)
    args = parser.parse_args(argv)
    workdir = Path(args.workdir)
    inputs = DEFAULT_INPUT
    if args.inputs:
        inputs = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
    try:
        result = run_workflow(
            workdir,
            inputs,
            resume=args.resume,
            stop_after=args.stop_after,
            pause_after=args.pause_after,
            redo_completed=args.redo_completed,
        )
    except CorruptCheckpoint as exc:
        print(f"REFUSED:corrupt-checkpoint {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
