#!/usr/bin/env python3
"""HumanCheckpoint executor: ``pause`` writes a durable owner packet and EXITS.

The executor never waits for the owner. ``pause`` validates the owner packet,
persists it (with the workflow's completed units) under ``<workspace>/pauses``,
prints a JSON envelope and returns, so no process stays resident across the
checkpoint. ``resume`` reloads the record by token, records the owner's answer
(or the declared default when unanswered), skips every completed unit without
re-dispatching it, and writes a resume ledger.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_PKG_PARENT = Path(__file__).resolve().parents[1]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from agentspec.owner_packet import check_owner_packet, foundation_question_count  # noqa: E402

STATUS_PAUSED = "PAUSED"
STATUS_RESUMED = "RESUMED"
STATUS_REFUSED = "REFUSED"
ANSWER_SOURCE_OWNER = "owner"
ANSWER_SOURCE_DEFAULT = "default_if_unanswered"
PAUSE_DIR = "pauses"
RESUME_DIR = "resumes"
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class CheckpointError(ValueError):
    """A pause or resume request that cannot be honoured; reported, never waited on."""


def _write_json_atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def new_token() -> str:
    """22-char URL-safe token from 16 random bytes (stdlib ``secrets`` is shadowed
    by the package's own ``secrets`` module when this file runs as a script)."""
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")


def _record_path(workspace: Path, token: str) -> Path:
    return workspace / PAUSE_DIR / f"hcp_{token}.json"


def _ledger_path(workspace: Path, token: str) -> Path:
    return workspace / RESUME_DIR / f"resume_{token}.json"


def parse_completed(items: list[str] | None) -> list[dict[str, str]]:
    """``UNIT=<sha256>`` pairs -> ordered records; malformed entries are refused."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in items or []:
        unit_id, sep, digest = raw.partition("=")
        unit_id = unit_id.strip()
        digest = digest.strip().lower()
        if not sep or not unit_id or not _SHA_RE.match(digest):
            raise CheckpointError(f"--completed expects UNIT=<sha256 hex>, got {raw!r}")
        if unit_id in seen:
            raise CheckpointError(f"--completed names {unit_id} twice")
        seen.add(unit_id)
        out.append({"unit_id": unit_id, "sha256": digest})
    return out


def build_owner_packet(args: argparse.Namespace, durable_record: Path) -> dict[str, Any]:
    return {
        "checkpoint_id": args.checkpoint_id,
        "prompt_ref": args.prompt_ref,
        "question": args.question,
        "recommendation": args.recommendation,
        "tradeoff": args.tradeoff,
        "default": args.default,
        "allowed": list(args.allowed),
        "durable_record": str(durable_record),
    }


def cmd_pause(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    completed = parse_completed(args.completed)
    token = new_token()
    record_path = _record_path(workspace, token)
    packet = build_owner_packet(args, record_path)
    errors = check_owner_packet(packet)
    if errors:
        print(
            json.dumps(
                {
                    "status": STATUS_REFUSED,
                    "checkpoint_id": args.checkpoint_id,
                    "errors": errors,
                    "resident_waiter": False,
                    "hang": False,
                },
                sort_keys=True,
            )
        )
        return 2
    record = {
        "status": STATUS_PAUSED,
        "checkpoint_id": args.checkpoint_id,
        "prompt_ref": args.prompt_ref,
        "pause_token": token,
        "owner_packet": packet,
        "workflow_state": {
            "checkpoint_id": args.checkpoint_id,
            "completed_units": completed,
        },
        "resident_waiter": False,
    }
    _write_json_atomic(record_path, record)
    envelope = {
        "status": STATUS_PAUSED,
        "checkpoint_id": args.checkpoint_id,
        "pause_token": token,
        "pause_record_path": str(record_path),
        "owner_packet": packet,
        "foundation_question_count": foundation_question_count(packet),
        "completed_units": len(completed),
        "resident_waiter": False,
        "hang": False,
        "marker": args.marker,
    }
    print(json.dumps(envelope, sort_keys=True))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    record_path = _record_path(workspace, args.token)
    if not record_path.is_file():
        raise CheckpointError(f"no pause record for token {args.token!r} under {workspace}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    packet = record.get("owner_packet") or {}
    allowed = list(packet.get("allowed") or [])
    if args.answer is not None:
        if allowed and args.answer not in allowed:
            raise CheckpointError(f"answer {args.answer!r} not in allowed {allowed}")
        answer, source = args.answer, ANSWER_SOURCE_OWNER
    else:
        answer, source = packet.get("default"), ANSWER_SOURCE_DEFAULT
        if not answer:
            raise CheckpointError("no answer given and the packet declares no default")

    completed = list((record.get("workflow_state") or {}).get("completed_units") or [])
    events: list[dict[str, Any]] = [
        {
            "type": "skip_completed",
            "unit_id": unit["unit_id"],
            "sha256": unit.get("sha256"),
            "re_dispatch": False,
        }
        for unit in completed
    ]
    events.append(
        {
            "type": "answer_recorded",
            "answer": answer,
            "answer_source": source,
            "re_dispatch": False,
        }
    )
    re_dispatch_count = sum(1 for e in events if e.get("re_dispatch") is True)
    ledger = {
        "pause_token": args.token,
        "checkpoint_id": record.get("checkpoint_id"),
        "events": events,
        "re_dispatch_count": re_dispatch_count,
        "skipped_completed": [u["unit_id"] for u in completed],
    }
    ledger_path = _ledger_path(workspace, args.token)
    _write_json_atomic(ledger_path, ledger)

    record["status"] = STATUS_RESUMED
    record["resume"] = {
        "answer": answer,
        "answer_source": source,
        "resume_ledger_path": str(ledger_path),
    }
    _write_json_atomic(record_path, record)

    continuation = {
        "status": STATUS_RESUMED,
        "checkpoint_id": record.get("checkpoint_id"),
        "pause_token": args.token,
        "answer": answer,
        "answer_source": source,
        "re_dispatch_count": re_dispatch_count,
        "skipped_completed": ledger["skipped_completed"],
        "resume_ledger_path": str(ledger_path),
        "pause_record_path": str(record_path),
        "resident_waiter": False,
        "hang": False,
    }
    print(json.dumps(continuation, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="human_checkpoint", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pause", help="persist the owner packet and exit without waiting")
    p.add_argument("--workspace", required=True)
    p.add_argument("--checkpoint-id", required=True)
    p.add_argument("--prompt-ref", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--recommendation", required=True)
    p.add_argument("--tradeoff", required=True)
    p.add_argument("--default", required=True)
    p.add_argument("--allowed", nargs="+", required=True)
    p.add_argument("--completed", action="append", default=[], metavar="UNIT=SHA256")
    p.add_argument("--marker", default=None, help="inert argv tag for process-table probes")
    p.set_defaults(func=cmd_pause)

    r = sub.add_parser("resume", help="continue from a pause record")
    r.add_argument("--workspace", required=True)
    r.add_argument("--token", required=True)
    r.add_argument("--answer", default=None)
    r.set_defaults(func=cmd_resume)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except CheckpointError as exc:
        print(json.dumps({"status": STATUS_REFUSED, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
