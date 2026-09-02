"""Mid-phase checkpoint / resume pipeline for TST-0164.

Three phases write a four-file downstream artifact tree. Pause after ingest
serializes a checkpoint; resume continues transform+emit without re-running
ingest. Wall-clock and PID enter only the declared meta/ledger fields.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from mask import DECLARED_NONDETERMINISTIC_FIELDS, apply_declared_mask

CHECKPOINT_FORMAT = "tst-0164-checkpoint.v1"
PHASES = ("ingest", "transform", "emit")
PAUSE_AFTER = "ingest"
SEED = 164
FROZEN_NS = 1_725_000_000_000_000_164
FIXED_PID = 16401


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def canonical_line(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


class WallClock:
    def now_ns(self) -> int:
        return time.time_ns()


class FrozenClock:
    def __init__(self, ns: int = FROZEN_NS) -> None:
        self.ns = int(ns)

    def now_ns(self) -> int:
        return self.ns


class LivePid:
    def pid(self) -> int:
        return os.getpid()


class FixedPid:
    def __init__(self, value: int = FIXED_PID) -> None:
        self.value = int(value)

    def pid(self) -> int:
        return self.value


@dataclass
class Host:
    clock: Any
    pid_source: Any

    def now_ns(self) -> int:
        return int(self.clock.now_ns())

    def pid(self) -> int:
        return int(self.pid_source.pid())


def wall_host() -> Host:
    return Host(WallClock(), LivePid())


def frozen_host(ns: int = FROZEN_NS, pid: int = FIXED_PID) -> Host:
    return Host(FrozenClock(ns), FixedPid(pid))


def corpus(seed: int) -> list[dict[str, Any]]:
    names = ("alpha.txt", "beta.txt", "gamma.txt")
    rows = []
    for i, name in enumerate(names):
        text = f"{name}:{seed}:phase-payload:{i}".encode("utf-8")
        rows.append(
            {
                "name": name,
                "size": len(text),
                "sha256": sha256_bytes(text),
                "text": text.decode("ascii"),
            }
        )
    return rows


def _meta(host: Host, stage: str) -> dict[str, Any]:
    return {
        "pid": host.pid(),
        "stage": stage,
        "timestamp_ns": str(host.now_ns()),
    }


def _write_json(tree: dict[str, bytes], name: str, obj: Any) -> None:
    tree[name] = canonical(obj)


@dataclass
class RunResult:
    artifacts: dict[str, bytes]
    executions: list[str]
    from_checkpoint: bool
    seed: int
    defective_undeclared_nd: bool
    host_kind: str
    checkpoint: dict[str, Any] | None = None
    ingest_sha256: str = ""
    notes: dict[str, Any] = field(default_factory=dict)


def _ingest(seed: int, host: Host) -> dict[str, Any]:
    items = corpus(seed)
    payload = [
        {"name": r["name"], "sha256": r["sha256"], "size": r["size"]} for r in items
    ]
    return {
        "meta": _meta(host, "ingest"),
        "payload": payload,
        "seed": seed,
        "stage": "ingest",
        "digest": sha256_bytes(canonical(payload)),
    }


def _transform(ingest: dict[str, Any], host: Host) -> dict[str, Any]:
    records = []
    for item in ingest["payload"]:
        tag_src = f"{ingest['seed']}:{item['name']}:{item['sha256']}".encode("utf-8")
        records.append(
            {
                "name": item["name"],
                "sha256": item["sha256"],
                "size": item["size"],
                "tag": hashlib.sha256(tag_src).hexdigest()[:16],
            }
        )
    digest = sha256_bytes(canonical(records))
    return {
        "digest": digest,
        "meta": _meta(host, "transform"),
        "records": records,
        "seed": ingest["seed"],
        "stage": "transform",
    }


def _emit(
    transform: dict[str, Any],
    host: Host,
    *,
    defective_undeclared_nd: bool,
    nonce_fn: Callable[[], str] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    names = [r["name"] for r in transform["records"]]
    downstream = {
        "names": names,
        "record_count": len(names),
        "transform_digest": transform["digest"],
    }
    doc: dict[str, Any] = {
        "downstream": downstream,
        "meta": _meta(host, "emit"),
        "seed": transform["seed"],
        "stage": "emit",
        "digest": sha256_bytes(canonical(downstream)),
    }
    if defective_undeclared_nd:
        fn = nonce_fn or (lambda: hashlib.sha256(os.urandom(16)).hexdigest()[:16])
        doc["session_nonce"] = fn()
    ledger = []
    for i, rec in enumerate(transform["records"]):
        raw = canonical(rec)
        ledger.append(
            {
                "byte_count": str(len(raw)),
                "id": str(10_000 + i),
                "seq": i,
                "timestamp_ns": str(host.now_ns()),
            }
        )
    emit_raw = canonical(doc)
    ledger.append(
        {
            "byte_count": str(len(emit_raw)),
            "id": str(10_000 + len(transform["records"])),
            "seq": len(transform["records"]),
            "timestamp_ns": str(host.now_ns()),
        }
    )
    return doc, ledger


def _pack_ledger(records: list[dict[str, Any]]) -> bytes:
    packed = []
    for rec in records:
        if isinstance(rec, dict) and "entries" in rec:
            packed.append(rec)
            continue
        row = rec if isinstance(rec, dict) else {"payload": rec}
        packed.append(
            {
                "entries": [
                    {
                        "id": str(row.get("id") or ""),
                        "payload": row,
                    }
                ],
                "id": row.get("id"),
                "timestamp_ns": row.get("timestamp_ns"),
                "byte_count": row.get("byte_count"),
                "seq": row.get("seq"),
            }
        )
    return b"".join(canonical_line(r) for r in packed)


def snapshot_after_ingest(ingest: dict[str, Any], seed: int, host_kind: str) -> dict[str, Any]:
    return {
        "completed_phases": ["ingest"],
        "format": CHECKPOINT_FORMAT,
        "host_kind": host_kind,
        "ingest": ingest,
        "next_phase": "transform",
        "seed": seed,
    }


def run_uninterrupted(
    *,
    seed: int = SEED,
    host: Host | None = None,
    defective_undeclared_nd: bool = False,
    nonce_fn: Callable[[], str] | None = None,
) -> RunResult:
    host = host or wall_host()
    host_kind = type(host.clock).__name__
    executions: list[str] = []
    tree: dict[str, bytes] = {}

    ingest = _ingest(seed, host)
    executions.append("ingest")
    _write_json(tree, "ingest.json", ingest)

    transform = _transform(ingest, host)
    executions.append("transform")
    _write_json(tree, "transform.json", transform)

    emit, ledger = _emit(
        transform, host, defective_undeclared_nd=defective_undeclared_nd, nonce_fn=nonce_fn
    )
    executions.append("emit")
    _write_json(tree, "emit.json", emit)
    tree["ledger.jsonl"] = _pack_ledger(ledger)

    return RunResult(
        artifacts=tree,
        executions=executions,
        from_checkpoint=False,
        seed=seed,
        defective_undeclared_nd=defective_undeclared_nd,
        host_kind=host_kind,
        ingest_sha256=sha256_bytes(tree["ingest.json"]),
    )


def continue_from_checkpoint(
    ckpt: dict[str, Any],
    *,
    host: Host | None = None,
    defective_undeclared_nd: bool = False,
    nonce_fn: Callable[[], str] | None = None,
) -> RunResult:
    if ckpt.get("format") != CHECKPOINT_FORMAT:
        raise ValueError(f"unsupported checkpoint format {ckpt.get('format')!r}")
    if ckpt.get("completed_phases") != ["ingest"]:
        raise ValueError("checkpoint is not a mid-phase ingest snapshot")
    host = host or wall_host()
    host_kind = type(host.clock).__name__
    executions: list[str] = []
    tree: dict[str, bytes] = {}

    restored = json.loads(json.dumps(ckpt["ingest"]))
    _write_json(tree, "ingest.json", restored)

    transform = _transform(restored, host)
    executions.append("transform")
    _write_json(tree, "transform.json", transform)

    emit, ledger = _emit(
        transform, host, defective_undeclared_nd=defective_undeclared_nd, nonce_fn=nonce_fn
    )
    executions.append("emit")
    _write_json(tree, "emit.json", emit)
    tree["ledger.jsonl"] = _pack_ledger(ledger)

    return RunResult(
        artifacts=tree,
        executions=executions,
        from_checkpoint=True,
        seed=ckpt["seed"],
        defective_undeclared_nd=defective_undeclared_nd,
        host_kind=host_kind,
        checkpoint=ckpt,
        ingest_sha256=sha256_bytes(tree["ingest.json"]),
        notes={
            "pre_suspend_executions": ["ingest"],
            "resume_executions": ["transform", "emit"],
            "checkpoint_completed": list(ckpt["completed_phases"]),
            "ingest_reexecuted": False,
        },
    )


def run_resumed(
    *,
    seed: int = SEED,
    host: Host | None = None,
    defective_undeclared_nd: bool = False,
    nonce_fn: Callable[[], str] | None = None,
    pause_after: str = PAUSE_AFTER,
) -> RunResult:
    if pause_after != "ingest":
        raise ValueError("TST-0164 mid-phase checkpoint is after ingest")
    host = host or wall_host()
    ingest = _ingest(seed, host)
    ckpt = snapshot_after_ingest(ingest, seed, type(host.clock).__name__)
    return continue_from_checkpoint(
        ckpt,
        host=host,
        defective_undeclared_nd=defective_undeclared_nd,
        nonce_fn=nonce_fn,
    )


def artifact_names() -> tuple[str, ...]:
    return ("ingest.json", "transform.json", "emit.json", "ledger.jsonl")


def parse_artifact(name: str, raw: bytes) -> Any:
    text = raw.decode("utf-8")
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def mask_artifact_bytes(name: str, raw: bytes) -> bytes:
    parsed = parse_artifact(name, raw)
    masked = apply_declared_mask(parsed)
    if name.endswith(".jsonl"):
        return _pack_ledger(masked)
    return canonical(masked)


def declared_mask() -> tuple[str, ...]:
    return DECLARED_NONDETERMINISTIC_FIELDS
