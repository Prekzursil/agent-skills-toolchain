#!/usr/bin/env python
"""event-ledger â€” the N2 keystone: an append-only typed event ledger per project.

Why it exists (research-backed): post-compaction agents re-act on the lossy auto-summary
as ground truth and loop ("echo chamber"). The fix is to recover by REPLAYING an
append-only, failure-aware ground-truth log â€” not a self-narrative summary. Compaction
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
import sys
import time
from pathlib import Path

ROOT = Path(
    os.environ.get("EVENT_LEDGER_ROOT", str(Path.home() / ".claude" / "event-ledger"))
)


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    """Read bounded hook configuration without creating an import-time failure path."""
    try:
        return min(hi, max(lo, float(os.environ.get(name, str(default)))))
    except (TypeError, ValueError, OverflowError):
        return default


# Stay comfortably inside the 5-second selection hook budget; ordinary append critical
# sections are millisecond-scale, so multi-second contention signals a stuck writer.
APPEND_LOCK_TIMEOUT = _env_float("EVENT_LEDGER_LOCK_TIMEOUT", 3.0, 0.1, 15.0)
APPEND_LOCK_POLL = 0.01

# Shared repo-identity resolver (hooks/_shared/projid.py). Imported best-effort and lazily
# so the ledger keeps working even if it is missing/broken â€” identity resolution must never
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
# milestone = annotations (agent- or hook-written); selection = a correlated tool-choice
# outcome consumed by oats.py. Failure entries are first-class because they carry the
# corrective signal a summary discards.
# Event kinds. "turn" = objective per-turn harvest (hook-written); decision/failure/goal/
# milestone = annotations (agent- or hook-written); selection = a correlated tool-choice
# outcome consumed by oats.py; claim_edge = a typed relation between two claim references.
# Failure entries are first-class because they carry the corrective signal a summary discards.
KINDS = (
    "turn",
    "decision",
    "failure",
    "goal",
    "milestone",
    "selection",
    "claim_edge",
    "thread",
    "note",
)
# Statuses that RETIRE an open thread. A thread is a RECONCILED PROJECTION, not another
# memory source: re-recording the same --id with a closing status REMOVES the row instead
# of appending a second one, so what replays is exactly what is still owed. Without this
# kind a deferred item had to be filed as a generic "note", which the SessionStart replay
# dropped — so open threads silently vanished across compaction/resume/clear.
THREAD_CLOSED_STATUSES = ("closed", "done", "resolved", "dropped", "superseded")
CLAIM_RELATIONS = (
    "supports",
    "contradicts",
    "duplicate_of",
    "supersedes",
    "derived_from",
)
NOTE_KINDS = tuple(kind for kind in KINDS if kind != "claim_edge")


def _claim_ref(value: str, field: str) -> str:
    """Validate a non-empty claim reference such as ``seq:12``."""
    if isinstance(value, str):
        clean = value.strip()
        if clean:
            return clean
    raise ValueError(f"{field} must be a non-empty string claim reference")


def _relation(value: str) -> str:
    if value not in CLAIM_RELATIONS:
        raise ValueError(f"relation must be one of: {', '.join(CLAIM_RELATIONS)}")
    return value


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
    projid is unavailable â€” never breaks a session.
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
            # canonical slug takes over automatically â€” and from then on all worktrees unify.
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


def _load_state_path(f: Path, project_path: str) -> dict:
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


def _load_state(project_path: str) -> dict:
    return _load_state_path(_state_file(project_path), project_path)


def _acquire_append_lock(path: Path):
    """Acquire one per-shard OS lock; process death releases it automatically."""
    deadline = time.monotonic() + APPEND_LOCK_TIMEOUT
    while True:
        stream = None
        try:
            stream = path.open("a+b")
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return stream
        except OSError:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            if time.monotonic() >= deadline:
                return None
            time.sleep(APPEND_LOCK_POLL)
        except Exception:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            return None


def _release_append_lock(stream) -> None:
    if stream is None:
        return
    try:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _last_event_seq(path: Path) -> int:
    """Recover the last valid source-of-truth seq if the projection lagged a crash."""
    try:
        if not path.is_file():
            return 0
        size = path.stat().st_size
        with path.open("rb") as handle:
            start = max(0, size - 64 * 1024)
            handle.seek(start)
            raw = handle.read(64 * 1024)
        lines = raw.decode("utf-8", "replace").splitlines()
        if start and lines:
            lines = lines[1:]
        for line in reversed(lines):
            try:
                return max(0, int(json.loads(line).get("seq") or 0))
            except Exception:
                continue
    except Exception:
        pass
    return 0


def _write_state_atomic(path: Path, state: dict) -> None:
    """Replace the projection atomically so readers see old-or-new, never truncation."""
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temp.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass


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

    Returns the written event dict. Claim edges reject an invalid schema before touching
    disk; other malformed fields use best-effort serialization so hooks do not crash.
    """
    if kind == "claim_edge":
        fields["source"] = _claim_ref(fields.get("source"), "source")
        fields["relation"] = _relation(fields.get("relation"))
        fields["target"] = _claim_ref(fields.get("target"), "target")
    directory = _dir(project_path)  # resolve canonical identity exactly once per append
    events_path = directory / "events.jsonl"
    state_path = directory / "state.json"
    claim = _acquire_append_lock(directory / ".append.lock")
    if claim is None:
        raise TimeoutError("event-ledger append lock unavailable")
    try:
        if kind not in KINDS:
            kind = "note"
        state = _load_state_path(state_path, project_path)
        try:
            projected_seq = max(0, int(state.get("seq", 0)))
        except (TypeError, ValueError, OverflowError):
            projected_seq = 0
        seq = max(projected_seq, _last_event_seq(events_path)) + 1
        ev = {"seq": seq, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind}
        for k, v in fields.items():
            try:
                json.dumps(v)
                ev[k] = v
            except Exception:
                ev[k] = repr(v)
        # Append the event first: events.jsonl is authoritative. If projection writing is
        # interrupted, the next append recovers its seq from this tail under the same lock.
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            fh.flush()
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
        _write_state_atomic(state_path, state)
        return ev
    finally:
        _release_append_lock(claim)


def replay(project_path: str, n: int = 40) -> list[dict]:
    """Return the last n events (ground truth), oldestâ†’newest."""
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


def append_claim_edge(
    project_path: str,
    relation: str,
    source: str,
    target: str,
) -> dict:
    """Append one typed claim relation to the same authoritative JSONL stream."""
    return append(
        project_path,
        "claim_edge",
        source=source,
        relation=relation,
        target=target,
    )


def claim_edges(
    project_path: str,
    *,
    source: str | None = None,
    relation: str | None = None,
    target: str | None = None,
    n: int = 200,
) -> list[dict]:
    """Return matching claim edges from the last n events, oldest to newest."""
    source_ref = _claim_ref(source, "source") if source is not None else None
    target_ref = _claim_ref(target, "target") if target is not None else None
    relation_name = _relation(relation) if relation is not None else None
    return [
        event
        for event in replay(project_path, n)
        if event.get("kind") == "claim_edge"
        and (source_ref is None or event.get("source") == source_ref)
        and (relation_name is None or event.get("relation") == relation_name)
        and (target_ref is None or event.get("target") == target_ref)
    ]
