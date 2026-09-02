#!/usr/bin/env python3
"""Serialized unit runner with durable checkpoints and injectable SIGKILL.

Crash mid-unit: the in-progress receipt is a truncated non-sentinel file, the
checkpoint records in_progress, then the process is SIGKILL'd. Resume re-runs
exactly the units whose receipts fail the oracle; completed receipts are never
re-dispatched.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plan as P  # noqa: E402

CHECKPOINT_NAME = "checkpoint.json"
BROKEN_REDISPATCH = "redispatch-complete"
BROKEN_SKIP = "skip-incomplete"
BROKEN_MODES = (BROKEN_REDISPATCH, BROKEN_SKIP)


def checkpoint_path(root: Path) -> Path:
    return Path(root) / CHECKPOINT_NAME


def load_checkpoint(root: Path) -> dict[str, Any] | None:
    path = checkpoint_path(root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"checkpoint is not an object: {path}")
    return data


def save_checkpoint(root: Path, doc: dict[str, Any]) -> None:
    P.atomic_write_text(
        checkpoint_path(root), json.dumps(doc, indent=2, sort_keys=True) + "\n"
    )


def empty_checkpoint(units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "completed": [],
        "in_progress": None,
        "open": [u["id"] for u in units],
        "dispatches": {},
        "last_checkpoint": "start",
    }


def oracle_kept_completed(
    root: Path, units: list[dict[str, Any]], cp: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    index = {u["id"]: u for u in units}
    kept: list[dict[str, Any]] = []
    ids: list[str] = []
    for rec in cp.get("completed") or []:
        if not isinstance(rec, dict) or rec.get("id") not in index:
            continue
        verdict = P.unit_oracle(root, index[rec["id"]], rec)
        if verdict["pass"]:
            kept.append(rec)
            ids.append(str(rec["id"]))
    return ids, kept


def execute_unit(
    root: Path,
    unit: dict[str, Any],
    cp: dict[str, Any],
    kill_at: str | None,
) -> None:
    uid = unit["id"]
    dispatches = dict(cp.get("dispatches") or {})
    dispatches[uid] = int(dispatches.get(uid, 0)) + 1
    cp["dispatches"] = dispatches
    cp["in_progress"] = {"id": uid}
    cp["last_checkpoint"] = f"mid:{uid}"
    save_checkpoint(root, cp)

    art = Path(root) / unit["artifact"]
    art.parent.mkdir(parents=True, exist_ok=True)
    # Visible truncated body: exists, looks like JSON, has no sentinel.
    art.write_bytes(f'{{"unit_id":"{uid}","state":"PARTIAL"'.encode("ascii"))

    print(f"REACHED mid:{uid}", flush=True)
    if kill_at == f"mid:{uid}":
        os.kill(os.getpid(), signal.SIGKILL)

    body = json.dumps(P.render_artifact(unit), indent=2, sort_keys=True) + "\n"
    P.atomic_write_text(art, body)
    sha, n = P.digest_file(art)
    rec = {
        "id": uid,
        "artifact": unit["artifact"],
        "sha256": sha,
        "bytes": n,
    }
    completed = [c for c in (cp.get("completed") or []) if c.get("id") != uid]
    completed.append(rec)
    cp["completed"] = completed
    cp["in_progress"] = None
    cp["open"] = [x for x in (cp.get("open") or []) if x != uid]
    cp["last_checkpoint"] = f"after:{uid}"
    save_checkpoint(root, cp)

    print(f"REACHED after:{uid}", flush=True)
    if kill_at == f"after:{uid}":
        os.kill(os.getpid(), signal.SIGKILL)


def select_skip_ids(
    root: Path,
    units: list[dict[str, Any]],
    resume: bool,
    broken: str | None,
) -> set[str]:
    if not resume:
        save_checkpoint(root, empty_checkpoint(units))
        return set()

    cp = load_checkpoint(root)
    if cp is None:
        raise SystemExit("FAILED:no-checkpoint")

    if broken == BROKEN_REDISPATCH:
        return set()

    ids, kept = oracle_kept_completed(root, units, cp)
    skip = set(ids)

    if broken == BROKEN_SKIP:
        ip = cp.get("in_progress") or {}
        ip_id = ip.get("id") if isinstance(ip, dict) else None
        if ip_id:
            skip.add(str(ip_id))
        cp["completed"] = kept
        cp["in_progress"] = None
        save_checkpoint(root, cp)
        return skip

    cp["completed"] = kept
    cp["in_progress"] = None
    save_checkpoint(root, cp)
    return skip


def run(
    root: Path,
    *,
    resume: bool = False,
    kill_at: str | None = None,
    broken: str | None = None,
) -> int:
    units = P.load_plan(root)
    known = P.known_checkpoints()
    if kill_at and kill_at not in known:
        print(f"FAILED:unknown-checkpoint {kill_at}", flush=True)
        return 2
    if broken and broken not in BROKEN_MODES:
        print(f"FAILED:unknown-broken {broken}", flush=True)
        return 2

    skip = select_skip_ids(root, units, resume, broken)
    cp = load_checkpoint(root)
    if cp is None:
        print("FAILED:checkpoint-missing-after-select", flush=True)
        return 2

    for unit in units:
        if unit["id"] in skip:
            continue
        execute_unit(root, unit, cp, kill_at)

    cp["in_progress"] = None
    cp["last_checkpoint"] = "complete"
    cp["open"] = []
    save_checkpoint(root, cp)
    print("SUCCESS:runner-complete", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TST-0096 crash-resume runner")
    parser.add_argument("--root", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--kill-at", default=None)
    parser.add_argument("--broken", default=None)
    args = parser.parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        return run(
            root,
            resume=bool(args.resume),
            kill_at=args.kill_at or None,
            broken=args.broken or None,
        )
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        print(str(code) or "FAILED:runner", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
