#!/usr/bin/env python
"""event-ledger — the N2 keystone: an append-only typed event ledger per project.

Why it exists (research-backed): post-compaction agents re-act on the lossy auto-summary
as ground truth and loop ("echo chamber"). The fix is to recover by REPLAYING an
append-only, failure-aware ground-truth log — not a self-narrative summary. Compaction
keeps *what happened* but destroys *why* (decisions / failures / rationale); this stores
exactly that, written continuously by hooks (the agent is an annotator, not the writer).

Storage: ~/.claude/event-ledger/<project-slug>/events.jsonl  (+ state.json projection).
Events are one JSON object per line. Append-only; recovery = replay the tail.

This module is dependency-free (stdlib only) and safe to import from hooks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(
    os.environ.get("EVENT_LEDGER_ROOT", str(Path.home() / ".claude" / "event-ledger"))
)

# Shared repo-identity resolver (hooks/_shared/projid.py). Imported best-effort and lazily
# so the ledger keeps working even if it is missing/broken — identity resolution must never
# crash a session (FAIL-OPEN).
_projid_mod = None
_projid_tried = False


def _get_projid():
    global _projid_mod, _projid_tried
    if not _projid_tried:
        _projid_tried = True
        try:
            shared = str(Path(__file__).resolve().parent.parent / "_shared")
            if shared not in sys.path:
                sys.path.insert(0, shared)
            import projid as _p  # noqa: PLC0415 - lazy, fail-open

            _projid_mod = _p
        except Exception:
            _projid_mod = None
    return _projid_mod


# Event kinds. "turn" = objective per-turn harvest (hook-written); decision/failure/goal/
# milestone = annotations (agent- or hook-written). failure entries are first-class because
# they carry the corrective signal a summary discards.
KINDS = ("turn", "decision", "failure", "goal", "milestone", "thread", "note")
# Statuses that RETIRE an open thread. A thread is a RECONCILED PROJECTION, not another
# memory source: re-recording the same --id with a closing status REMOVES the row instead
# of appending a second one, so what replays is exactly what is still owed. Without this
# kind a deferred item had to be filed as a generic "note", which the SessionStart replay
# dropped — so open threads silently vanished across compaction/resume/clear.
THREAD_CLOSED_STATUSES = ("closed", "done", "resolved", "dropped", "superseded")


def _legacy_slug(p: str) -> str:
    """The original cwd-hash slug. Retained as the FAIL-OPEN fallback and so migrations can
    still recognise pre-unification shard names."""
    base = Path(p).name or "root"
    h = hashlib.sha256(p.encode("utf-8", "replace")).hexdigest()[
        :8
    ]  # non-crypto slug; sha256 per CWE-327
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in base)[:40]
    return f"{safe}-{h}"


def _slug(project_path: str) -> str:
    """Stable, readable, collision-resistant per-project directory name.

    Prefers the shared ``projid`` resolver, so every worktree / sub-directory / case-variant
    path of one repo collapses to ONE shard (fixes the cwd-hash fragmentation that split e.g.
    Reframe across many shards). For a non-git directory projid reproduces the exact legacy
    formula, so those shards are unchanged (zero churn). Falls back to the legacy slug if
    projid is unavailable — never breaks a session.
    """
    p = str(project_path or os.getcwd())
    mod = _get_projid()
    if mod is not None:
        try:
            candidate = mod.ledger_slug(p)
            legacy = _legacy_slug(p)
            # CONTINUITY (deploy-safe without first migrating): if a pre-existing legacy shard
            # for THIS exact cwd still lives directly under ROOT, keep writing to it so no prior
            # history is silently abandoned. Once `projid migrate --apply` folds that shard into
            # the canonical one (moving it under ROOT/.migrated/), this check fails and the
            # canonical slug takes over automatically — and from then on all worktrees unify.
            if candidate != legacy and (ROOT / legacy).is_dir():
                return legacy
            return candidate
        except Exception:
            pass
    return _legacy_slug(p)


def _dir(project_path: str) -> Path:
    d = ROOT / _slug(project_path)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _events_file(project_path: str) -> Path:
    return _dir(project_path) / "events.jsonl"


def _state_file(project_path: str) -> Path:
    return _dir(project_path) / "state.json"


def _load_state(project_path: str) -> dict:
    f = _state_file(project_path)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "seq": 0,
        "project": str(project_path),
        "goal": None,
        "head": None,
        "open_failures": [],
        "open_threads": [],
        "last_event_ts": None,
    }


def _reconcile_threads(rows, seq: int, fields: dict) -> list[dict]:
    """Fold one thread event into the open-threads projection (idempotent per thread id).

    One row per ``id``: re-recording the same id replaces it, and a closing status drops it
    outright. That keeps the projection a reconciliation of what is still owed rather than
    an append-only second memory source that would replay settled items forever.
    """
    tid = str(fields.get("id") or f"seq:{seq}")
    status = str(fields.get("status") or "open").strip().lower()
    kept = [r for r in (rows or []) if r.get("id") != tid]
    if status not in THREAD_CLOSED_STATUSES:
        kept.append(
            {"id": tid, "seq": seq, "text": fields.get("text"), "status": status}
        )
    return kept[-25:]


def append(project_path: str, kind: str, **fields) -> dict:
    """Append a typed event; bump the monotonic seq; update the state projection.

    Returns the written event dict. Never raises on a malformed field (hooks must not crash
    a session) — best-effort serialization.
    """
    if kind not in KINDS:
        kind = "note"
    state = _load_state(project_path)
    seq = int(state.get("seq", 0)) + 1
    ev = {"seq": seq, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind}
    for k, v in fields.items():
        try:
            json.dumps(v)
            ev[k] = v
        except Exception:
            ev[k] = repr(v)
    # append the event line (append-only; the source of truth)
    with _events_file(project_path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    # update the cheap projection (best-effort; events.jsonl is authoritative)
    state["seq"] = seq
    state["last_event_ts"] = ev["ts"]
    # Record every distinct cwd that maps into this (now identity-unified) shard, so a repo
    # opened from several worktrees keeps a non-destructive trail of where it was worked on.
    if project_path:
        aliases = state.get("aliases") or []
        if str(project_path) not in aliases:
            aliases.append(str(project_path))
            state["aliases"] = aliases[-50:]
    if kind == "goal":
        state["goal"] = fields.get("text")
    if kind == "turn" and fields.get("head"):
        state["head"] = fields.get("head")
    if kind == "failure":
        ofs = state.get("open_failures", [])
        ofs.append(
            {
                "seq": seq,
                "text": fields.get("text"),
                "preconditions": fields.get("preconditions"),
            }
        )
        state["open_failures"] = ofs[-25:]
    if kind == "milestone" and fields.get("supersedes_failures"):
        # a contradicting success auto-tombstones the named open failures
        keep = [
            f
            for f in state.get("open_failures", [])
            if f.get("seq") not in set(fields["supersedes_failures"])
        ]
        state["open_failures"] = keep
    if kind == "thread":
        state["open_threads"] = _reconcile_threads(
            state.get("open_threads"), seq, fields
        )
    _state_file(project_path).write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return ev


def replay(project_path: str, n: int = 40) -> list[dict]:
    """Return the last n events (ground truth), oldest→newest."""
    f = _events_file(project_path)
    if not f.exists():
        return []
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for ln in lines[-n:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def state(project_path: str) -> dict:
    return _load_state(project_path)


def staging_paths(root: Path) -> list[Path]:
    return list(Path(root).glob("*.jsonl.staging")) + list(Path(root).glob(".*.staging"))


def inspect_published_bytes(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="replace")
    rows = []
    truncated = False
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            truncated = True
    last = text.splitlines()[-1] if text.splitlines() else ""
    half = False
    if last.strip():
        try:
            json.loads(last)
        except json.JSONDecodeError:
            half = True
            truncated = True
    return {
        "parseable": not truncated,
        "n_records": len(rows),
        "line_count": len([ln for ln in text.splitlines() if ln.strip()]),
        "truncated": truncated,
        "half_written": half,
        "rows": rows,
    }


# --------------------------------------------------------------------------
# run-ledger-v1: the hash-chained, monotonic per-run event log
# (command-center/events/EVENTS.jsonl, command-center/events/run-ledger.jsonl)
# --------------------------------------------------------------------------

RUN_LEDGER_KIND = "run-ledger-v1"
GENESIS_PREV_SHA256 = "0" * 64
RUN_RECORD_REQUIRED = (
    "kind",
    "seq",
    "ts",
    "actor",
    "unit_id",
    "phase",
    "from_state",
    "to_state",
    "correlation_id",
    "causality_id",
    "payload",
    "prev_sha256",
)
_RUN_RECORD_STRINGS = (
    "actor",
    "unit_id",
    "phase",
    "from_state",
    "to_state",
    "correlation_id",
    "causality_id",
)
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def encode_run_record(record: dict) -> bytes:
    """Canonical single-line encoding: compact, sorted keys, ASCII, LF-terminated.

    The hash chain is computed over exactly these bytes, so every writer and
    verifier must agree on them.
    """
    text = json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if "\n" in text or "\r" in text:
        raise ValueError("run-ledger record must encode to a single line")
    return (text + "\n").encode("utf-8")


def run_record_errors(record: object) -> list[str]:
    """Field-level violations of the run-ledger-v1 record contract ([] when clean)."""
    if not isinstance(record, dict):
        return ["not-object"]
    errs = [f"missing:{k}" for k in RUN_RECORD_REQUIRED if k not in record]
    if record.get("kind") != RUN_LEDGER_KIND:
        errs.append(f"kind:{record.get('kind')!r}")
    seq = record.get("seq")
    if type(seq) is not int or seq < 1:
        errs.append(f"seq:{seq!r}")
    ts = record.get("ts")
    if not isinstance(ts, str) or not _TS_RE.match(ts):
        errs.append(f"ts:{ts!r}")
    for key in _RUN_RECORD_STRINGS:
        val = record.get(key)
        if not isinstance(val, str) or not val.strip():
            errs.append(f"empty:{key}")
    if not isinstance(record.get("payload"), dict):
        errs.append("payload:not-object")
    prev = record.get("prev_sha256")
    if not isinstance(prev, str) or not _SHA_RE.match(prev):
        errs.append(f"prev_sha256:{prev!r}")
    return errs


def run_ledger_chain_state(raw: bytes) -> dict:
    """Walk published bytes and return where the next record must attach.

    ``seq`` is the last conforming record's sequence number (0 for an empty
    log), ``prev_sha256`` the digest of that record's line bytes (the genesis
    digest for an empty log) and ``complete`` whether the tail ends in LF.
    Lines that do not parse or do not conform are counted, never trusted.
    """
    seq = 0
    prev = GENESIS_PREV_SHA256
    conforming = 0
    rejected = 0
    complete = (not raw) or raw.endswith(b"\n")
    parts = raw.split(b"\n")
    if raw.endswith(b"\n"):
        parts = parts[:-1]
    if not complete:
        parts = parts[:-1]  # the torn fragment is not a record
    for part in parts:
        if part == b"":
            rejected += 1
            continue
        try:
            obj = json.loads(part.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            rejected += 1
            continue
        if run_record_errors(obj):
            rejected += 1
            continue
        conforming += 1
        seq = obj["seq"]
        prev = hashlib.sha256(part + b"\n").hexdigest()
    return {
        "seq": seq,
        "prev_sha256": prev,
        "conforming": conforming,
        "rejected": rejected,
        "complete": complete,
    }


class LedgerWriter:
    """Atomic, hash-chained append of ``run-ledger-v1`` records.

    Every ``append`` reads the published file, derives the next monotonic
    ``seq`` and ``prev_sha256`` (SHA-256 of the previous record's line bytes,
    64 zeros for genesis) from the durable bytes, stamps ``kind`` and an
    ISO-8601 UTC ``ts``, validates the record against
    :func:`run_record_errors`, and publishes ``current + line`` through a
    staging file plus ``os.replace`` so a reader never observes a torn line.
    Concurrent writers may lose an update (last snapshot wins) but cannot
    interleave bytes.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text("", encoding="utf-8")

    def chain_state(self) -> dict:
        current = self.path.read_bytes() if self.path.is_file() else b""
        return run_ledger_chain_state(current)

    def append(self, **fields: object) -> dict:
        current = self.path.read_bytes() if self.path.is_file() else b""
        state = run_ledger_chain_state(current)
        if not state["complete"]:
            # Terminate a torn tail so the new record starts on its own line;
            # the fragment stays in place (append-only) and verifiers flag it.
            current += b"\n"
        record: dict = {}
        for key, value in fields.items():
            try:
                json.dumps(value)
                record[key] = value
            except (TypeError, ValueError):
                record[key] = repr(value)
        record.setdefault("kind", RUN_LEDGER_KIND)
        record["seq"] = int(state["seq"]) + 1
        record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        record["prev_sha256"] = state["prev_sha256"]
        errs = run_record_errors(record)
        if errs:
            raise ValueError("run-ledger record rejected: " + ", ".join(errs))
        blob = encode_run_record(record)
        staging = self.path.with_name(self.path.name + ".staging")
        with staging.open("wb") as fh:
            fh.write(current + blob)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(staging, self.path)
        return record
