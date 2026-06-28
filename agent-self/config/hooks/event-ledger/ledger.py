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
import time
from pathlib import Path

ROOT = Path(
    os.environ.get("EVENT_LEDGER_ROOT", str(Path.home() / ".claude" / "event-ledger"))
)

# Event kinds. "turn" = objective per-turn harvest (hook-written); decision/failure/goal/
# milestone = annotations (agent- or hook-written). failure entries are first-class because
# they carry the corrective signal a summary discards.
KINDS = ("turn", "decision", "failure", "goal", "milestone", "note")


def _slug(project_path: str) -> str:
    """Stable, readable, collision-resistant per-project directory name."""
    p = str(project_path or os.getcwd())
    base = Path(p).name or "root"
    h = hashlib.sha256(p.encode("utf-8", "replace")).hexdigest()[
        :8
    ]  # non-crypto slug; sha256 per CWE-327
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in base)[:40]
    return f"{safe}-{h}"


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
        "last_event_ts": None,
    }


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
