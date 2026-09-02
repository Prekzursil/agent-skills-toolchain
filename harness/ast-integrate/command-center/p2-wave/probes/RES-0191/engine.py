#!/usr/bin/env python3
"""Research-run resume protocol: durable per-query status, not cache keys.

Distinct from RES-0004 (content-addressed fetch snapshots) and RES-0171
(cache-key + staleness). A completed query is not re-paid. A partial or
failed query is not skipped. A corrupted checkpoint is refused loudly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
KIND = "research-run-checkpoint"
REFUSE_PREFIX = "REFUSE:checkpoint"
# Initial empty persist + 5 harvests: Q1 completes, Q2 partial, Q3 failed, Q4 partial.
DIE_AFTER_DEFAULT = 6

PLAN: list[dict[str, Any]] = [
    {"query_id": "Q1", "harvest_total": 2, "fail_first_attempt": False},
    {"query_id": "Q2", "harvest_total": 3, "fail_first_attempt": False},
    {"query_id": "Q3", "harvest_total": 2, "fail_first_attempt": True},
    {"query_id": "Q4", "harvest_total": 2, "fail_first_attempt": False},
]

DURABLE_FIELDS = (
    "query_id",
    "status",
    "harvest_index",
    "harvest_total",
    "emitted_claim_ids",
    "backend_calls",
    "harvest_attempts",
    "error",
)


class CheckpointRefuse(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{REFUSE_PREFIX}-{code}: {detail}")


class DiedMidRun(Exception):
    """In-process tests only. Production kill uses SIGKILL."""


def plan_sha256(plan: list[dict[str, Any]] | None = None) -> str:
    blob = json.dumps(plan or PLAN, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def canonical_payload(doc: dict[str, Any]) -> bytes:
    body = {k: v for k, v in doc.items() if k != "integrity_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def integrity_of(doc: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(doc)).hexdigest()


def checkpoint_path(run_dir: Path) -> Path:
    return Path(run_dir) / "checkpoint.json"


def empty_record(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": spec["query_id"],
        "status": "not_started",
        "harvest_index": 0,
        "harvest_total": int(spec["harvest_total"]),
        "emitted_claim_ids": [],
        "backend_calls": 0,
        "harvest_attempts": 0,
        "error": None,
        "fail_first_attempt": bool(spec["fail_first_attempt"]),
    }


def new_state(run_id: str, plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    p = plan or PLAN
    doc: dict[str, Any] = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "plan_sha256": plan_sha256(p),
        "cursor": 0,
        "persist_count": 0,
        "queries": {spec["query_id"]: empty_record(spec) for spec in p},
    }
    doc["integrity_sha256"] = integrity_of(doc)
    return doc


def validate_loaded(doc: dict[str, Any], plan: list[dict[str, Any]] | None = None) -> None:
    p = plan or PLAN
    if not isinstance(doc, dict):
        raise CheckpointRefuse("unreadable", "checkpoint is not a JSON object")
    if doc.get("kind") != KIND:
        raise CheckpointRefuse("schema", f"kind={doc.get('kind')!r}")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise CheckpointRefuse("schema", f"schema_version={doc.get('schema_version')!r}")
    digest = doc.get("integrity_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise CheckpointRefuse("integrity", "integrity_sha256 missing or malformed")
    if integrity_of(doc) != digest:
        raise CheckpointRefuse("integrity", "payload hash does not match integrity_sha256")
    if doc.get("plan_sha256") != plan_sha256(p):
        raise CheckpointRefuse("plan-mismatch", "checkpoint plan_sha256 != live plan")
    queries = doc.get("queries")
    if not isinstance(queries, dict):
        raise CheckpointRefuse("schema", "queries is not an object")
    expected = {spec["query_id"] for spec in p}
    if set(queries) != expected:
        raise CheckpointRefuse(
            "schema", f"query ids {sorted(queries)} != {sorted(expected)}"
        )
    allowed = {"not_started", "partial", "completed", "failed"}
    for qid, rec in queries.items():
        if not isinstance(rec, dict):
            raise CheckpointRefuse("schema", f"{qid} record is not an object")
        for field in DURABLE_FIELDS:
            if field not in rec:
                raise CheckpointRefuse("schema", f"{qid} missing durable field {field}")
        st = rec.get("status")
        if st not in allowed:
            raise CheckpointRefuse("schema", f"{qid} unknown status {st!r}")
        idx = rec.get("harvest_index")
        total = rec.get("harvest_total")
        if not isinstance(idx, int) or not isinstance(total, int) or idx < 0 or total < 1:
            raise CheckpointRefuse("schema", f"{qid} harvest cursor invalid")
        claims = rec.get("emitted_claim_ids")
        if not isinstance(claims, list):
            raise CheckpointRefuse("schema", f"{qid} emitted_claim_ids is not a list")
        if st == "completed":
            if idx != total:
                raise CheckpointRefuse(
                    "inconsistent-completed",
                    f"{qid} status=completed but harvest_index={idx} total={total}",
                )
            if len(claims) != total:
                raise CheckpointRefuse(
                    "inconsistent-completed",
                    f"{qid} completed but claim count != harvest_total",
                )
        if st == "not_started" and (idx != 0 or claims):
            raise CheckpointRefuse(
                "inconsistent-not-started",
                f"{qid} not_started but cursor or claims are non-empty",
            )
        if st == "partial" and not (0 < idx < total):
            raise CheckpointRefuse(
                "inconsistent-partial",
                f"{qid} status=partial but harvest_index={idx} total={total}",
            )


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def persist(run_dir: Path, doc: dict[str, Any]) -> None:
    doc["persist_count"] = int(doc.get("persist_count") or 0) + 1
    doc["integrity_sha256"] = integrity_of(doc)
    atomic_write(checkpoint_path(run_dir), json.dumps(doc, indent=2, sort_keys=True) + "\n")


def load_checkpoint(run_dir: Path, plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    path = checkpoint_path(run_dir)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckpointRefuse("unreadable", f"missing {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckpointRefuse("unreadable", f"{type(exc).__name__}: {exc}") from exc
    validate_loaded(doc, plan)
    return doc


def claim_id(query_id: str, harvest_index: int) -> str:
    return f"{query_id}:H{harvest_index}"


def harvest(spec: dict[str, Any], rec: dict[str, Any]) -> str:
    rec["backend_calls"] = int(rec["backend_calls"]) + 1
    rec["harvest_attempts"] = int(rec["harvest_attempts"]) + 1
    if (
        spec["fail_first_attempt"]
        and rec["harvest_attempts"] == 1
        and rec["harvest_index"] == 0
    ):
        raise RuntimeError(f"planted-fail {spec['query_id']} harvest 0 attempt 1")
    return claim_id(spec["query_id"], rec["harvest_index"])


def next_spec(
    doc: dict[str, Any],
    plan: list[dict[str, Any]],
    skip_if=None,
) -> dict[str, Any] | None:
    n = len(plan)
    if n == 0:
        return None
    start = int(doc.get("cursor") or 0) % n
    for i in range(n):
        spec = plan[(start + i) % n]
        rec = doc["queries"][spec["query_id"]]
        if rec["status"] == "completed":
            continue
        if skip_if is not None and skip_if(rec):
            continue
        doc["cursor"] = (start + i + 1) % n
        return spec
    return None


def step(doc: dict[str, Any], plan: list[dict[str, Any]], skip_if=None) -> str:
    spec = next_spec(doc, plan, skip_if=skip_if)
    if spec is None:
        return "done"
    rec = doc["queries"][spec["query_id"]]
    try:
        cid = harvest(spec, rec)
        rec["emitted_claim_ids"].append(cid)
        rec["harvest_index"] = int(rec["harvest_index"]) + 1
        rec["harvest_attempts"] = 0
        rec["error"] = None
        rec["status"] = (
            "completed" if rec["harvest_index"] >= rec["harvest_total"] else "partial"
        )
        return rec["status"]
    except RuntimeError as exc:
        rec["status"] = "failed"
        rec["error"] = str(exc)
        return "failed"


def maybe_die(doc: dict[str, Any], die_after: int | None, mode: str) -> None:
    if die_after is None:
        return
    if int(doc.get("persist_count") or 0) < die_after:
        return
    if mode == "exception":
        raise DiedMidRun(f"die_after_persist={die_after}")
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.kill(os.getpid(), signal.SIGKILL)
    except Exception:
        os._exit(99)
    os._exit(99)


def run_until(
    run_dir: Path,
    *,
    run_id: str = "run",
    die_after: int | None = None,
    die_mode: str = "sigkill",
    resume: bool = False,
    plan: list[dict[str, Any]] | None = None,
    skip_if=None,
) -> dict[str, Any]:
    p = plan or PLAN
    path = checkpoint_path(run_dir)
    if resume:
        doc = load_checkpoint(run_dir, p)
    elif path.is_file():
        raise CheckpointRefuse("exists", "checkpoint already present; use resume")
    else:
        doc = new_state(run_id, p)
        persist(run_dir, doc)
        maybe_die(doc, die_after, die_mode)
    while True:
        outcome = step(doc, p, skip_if=skip_if)
        persist(run_dir, doc)
        maybe_die(doc, die_after, die_mode)
        if outcome == "done":
            return doc


def claim_set(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for rec in doc["queries"].values():
        out.extend(rec.get("emitted_claim_ids") or [])
    return sorted(out)


def backend_ledger(doc: dict[str, Any]) -> dict[str, int]:
    return {qid: int(rec["backend_calls"]) for qid, rec in doc["queries"].items()}


def status_map(doc: dict[str, Any]) -> dict[str, str]:
    return {qid: rec["status"] for qid, rec in doc["queries"].items()}


def expected_full_claims(plan: list[dict[str, Any]] | None = None) -> list[str]:
    p = plan or PLAN
    out = []
    for spec in p:
        for i in range(int(spec["harvest_total"])):
            out.append(claim_id(spec["query_id"], i))
    return sorted(out)


def naive_skip_nonzero(
    run_dir: Path, src: dict[str, Any], plan: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Planted mutant: skip every query that is not not_started.

    This is the silent-skip bug: partial and failed look 'already touched'
    so they are never retried. Does not rewrite records as completed.
    """
    p = plan or PLAN
    doc = json.loads(json.dumps(src))
    for rec in doc["queries"].values():
        if rec["status"] != "not_started":
            rec["mutant_skip"] = True
    doc["integrity_sha256"] = integrity_of(doc)
    atomic_write(
        checkpoint_path(run_dir), json.dumps(doc, indent=2, sort_keys=True) + "\n"
    )
    return run_until(
        run_dir,
        run_id=str(doc["run_id"]),
        resume=True,
        plan=p,
        skip_if=lambda rec: rec.get("status") != "not_started",
    )


def forge_inconsistent_completed(src: dict[str, Any]) -> dict[str, Any]:
    """Semantic corrupt: mark a partial query completed and recompute integrity."""
    doc = json.loads(json.dumps(src))
    rec = doc["queries"]["Q2"]
    rec["status"] = "completed"
    # harvest_index stays < total so validate_loaded must refuse.
    doc["integrity_sha256"] = integrity_of(doc)
    return doc


def flip_byte(raw: bytes, offset: int | None = None) -> bytes:
    """Flip one ASCII letter so JSON still parses and integrity must fail."""
    if not raw:
        raise ValueError("empty checkpoint")
    if offset is not None:
        i = min(max(offset, 0), len(raw) - 1)
        return raw[:i] + bytes([raw[i] ^ 0x01]) + raw[i + 1 :]
    for i, b in enumerate(raw):
        if 0x61 <= b <= 0x7A:  # a-z inside a JSON string
            return raw[:i] + bytes([b ^ 0x01]) + raw[i + 1 :]
    i = len(raw) // 2
    return raw[:i] + bytes([raw[i] ^ 0x01]) + raw[i + 1 :]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "resume", "show"])
    parser.add_argument("--dir", required=True)
    parser.add_argument("--run-id", default="run")
    parser.add_argument("--die-after", type=int, default=None)
    parser.add_argument(
        "--die-mode", choices=["sigkill", "exception"], default="sigkill"
    )
    args = parser.parse_args()
    run_dir = Path(args.dir)
    try:
        if args.action == "show":
            doc = load_checkpoint(run_dir)
            print(
                json.dumps(
                    {
                        "claims": claim_set(doc),
                        "status": status_map(doc),
                        "pay": backend_ledger(doc),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.action == "run":
            doc = run_until(
                run_dir,
                run_id=args.run_id,
                die_after=args.die_after,
                die_mode=args.die_mode,
                resume=False,
            )
        else:
            doc = run_until(run_dir, run_id=args.run_id, resume=True)
        print(
            json.dumps(
                {
                    "claims": claim_set(doc),
                    "status": status_map(doc),
                    "pay": backend_ledger(doc),
                    "persist_count": doc["persist_count"],
                },
                sort_keys=True,
            )
        )
        return 0
    except CheckpointRefuse as exc:
        print(str(exc), file=sys.stderr)
        print(str(exc))
        return 2
    except DiedMidRun as exc:
        print(f"DIED {exc}", file=sys.stderr)
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
