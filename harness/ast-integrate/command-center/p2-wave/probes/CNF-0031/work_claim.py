"""Crash-safe exclusive work-claim (tmp + os.link) and advisory file leases.

os.link fails if the destination exists, so two sessions cannot both publish a
claim. os.rename is NOT exclusive on POSIX and is kept only as a mutation that
the contested probe requires to turn the test red.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GRANTED = "GRANTED"
ALREADY_CLAIMED = "ALREADY-CLAIMED"
DUPLICATE_SUPPRESSED = "DUPLICATE-SUPPRESSED"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def register_session(sessions_dir: Path, session_id: str) -> dict[str, Any]:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    dest = sessions_dir / f"{session_id}.json"
    payload = {
        "id": session_id,
        "pid": os.getpid(),
        "registered_at": utc_now(),
    }
    tmp = sessions_dir / f".{session_id}.{os.getpid()}.{time.time_ns()}.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.link(tmp, dest)
    except FileExistsError as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"session already registered: {session_id}") from exc
    tmp.unlink(missing_ok=True)
    return payload


def acquire(
    claims_dir: Path,
    unit_id: str,
    session: dict[str, Any],
    ttl_s: float = 300.0,
    exclusive: bool = True,
) -> dict[str, Any]:
    """Publish a per-unit claim. exclusive=True uses tmp+link (one winner)."""
    claims_dir.mkdir(parents=True, exist_ok=True)
    dest = claims_dir / f"{unit_id}.json"
    now = time.time()
    # The pre-check is part of exclusive acquire. The rename mutation skips it so
    # both callers publish GRANTED (POSIX rename replaces), which is the red state.
    if exclusive and dest.is_file():
        try:
            existing = _read_json(dest)
        except (OSError, json.JSONDecodeError):
            existing = {}
        expires = float(existing.get("expires_at") or 0)
        if expires > now:
            return _denied(unit_id, session, existing)
        try:
            dest.unlink()
        except FileNotFoundError:
            pass

    payload = {
        "acquired_at": now,
        "acquired_at_iso": utc_now(),
        "expires_at": now + ttl_s,
        "session_id": session["id"],
        "status": GRANTED,
        "unit_id": unit_id,
    }
    tmp = claims_dir / f".{unit_id}.{session['id']}.{os.getpid()}.{time.time_ns()}.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    try:
        if exclusive:
            os.link(tmp, dest)
        else:
            os.rename(tmp, dest)
            tmp = None  # renamed away
        result = {
            **payload,
            "loser_response": None,
            "result": GRANTED,
            "status": GRANTED,
        }
        return result
    except FileExistsError:
        try:
            existing = _read_json(dest)
        except (OSError, json.JSONDecodeError):
            existing = {"session_id": "unknown"}
        return _denied(unit_id, session, existing)
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def _denied(unit_id: str, session: dict[str, Any], holder: dict[str, Any]) -> dict[str, Any]:
    holder_id = str(holder.get("session_id") or "unknown")
    text = (
        f"{ALREADY_CLAIMED} unit={unit_id} holder={holder_id} "
        f"loser={session['id']} result={DUPLICATE_SUPPRESSED}"
    )
    return {
        "holder_session_id": holder_id,
        "loser_response": text,
        "result": DUPLICATE_SUPPRESSED,
        "session_id": session["id"],
        "status": ALREADY_CLAIMED,
        "unit_id": unit_id,
    }


def declare_lease(leases_dir: Path, session_id: str, paths: list[str]) -> dict[str, Any]:
    leases_dir.mkdir(parents=True, exist_ok=True)
    rec = {
        "holder": session_id,
        "paths": list(paths),
        "declared_at": utc_now(),
        "advisory": True,
    }
    atomic_write(leases_dir / f"{session_id}.json", rec)
    return rec


def note_write(
    leases_dir: Path,
    events_path: Path,
    session_id: str,
    rel_path: str,
) -> dict[str, Any]:
    """Advisory: never refuse a write; log a conflict if another session leased the path."""
    holders: list[str] = []
    if leases_dir.is_dir():
        for p in leases_dir.glob("*.json"):
            if p.name.startswith("."):
                continue
            try:
                rec = _read_json(p)
            except (OSError, json.JSONDecodeError):
                continue
            holder = str(rec.get("holder") or "")
            leased = [str(x) for x in (rec.get("paths") or [])]
            if holder and holder != session_id and rel_path in leased:
                holders.append(holder)
    event = {
        "advisory": True,
        "blocked": False,
        "conflict": bool(holders),
        "holders": holders,
        "path": rel_path,
        "session_id": session_id,
        "ts": utc_now(),
        "write_allowed": True,
    }
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    return event
