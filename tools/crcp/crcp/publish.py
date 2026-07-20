"""Publish outbox envelopes to agent-mail and track what was sent."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .bus import DEFAULT_PROJECT, publish_envelope
from .envelope import utc_now


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Replace a JSON state file only after its new contents are durable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(path))
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def publish_outbox(
    outbox: Path,
    *,
    project: str = DEFAULT_PROJECT,
    limit: int = 20,
    state_path: Path | None = None,
    force: bool = False,
    worker: Any | None = None,
) -> dict[str, Any]:
    """Publish outbox files now, or durably enqueue them for ``worker``."""
    outbox.mkdir(parents=True, exist_ok=True)
    state_path = state_path or (outbox / ".publish_state.json")
    state: dict[str, Any] = {"published_ids": {}}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not isinstance(state, dict):
        state = {"published_ids": {}}
    published = state.setdefault("published_ids", {})
    queued = state.setdefault("queued_ids", {})
    if not isinstance(published, dict):
        published = state["published_ids"] = {}
    if not isinstance(queued, dict):
        queued = state["queued_ids"] = {}

    envelopes = sorted(outbox.glob("envelope_*.json"), key=lambda p: p.stat().st_mtime)
    results = []
    count = 0
    for path in envelopes:
        if count >= limit:
            break
        try:
            env = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            results.append({"path": str(path), "ok": False, "error": type(e).__name__})
            continue
        eid = env.get("id") or path.name
        if eid in published and not force:
            results.append({"path": str(path), "ok": True, "skipped": True, "envelope_id": eid})
            continue
        try:
            send = publish_envelope(env, project=project, worker=worker)
            delivery_record = {
                "at": utc_now(),
                "path": str(path),
                "sender": send.get("sender"),
                "recipients": send.get("recipients"),
            }
            if worker is None:
                published[eid] = delivery_record
            else:
                delivery_record["queue_status"] = send.get("status")
                queued[eid] = delivery_record
            results.append(
                {
                    "path": str(path),
                    "ok": True,
                    "envelope_id": eid,
                    "send": send,
                    "queued": worker is not None,
                }
            )
            count += 1
        except Exception as e:
            results.append(
                {
                    "path": str(path),
                    "ok": False,
                    "envelope_id": eid,
                    "error": f"{type(e).__name__}: {e}"[:300],
                }
            )

    state["last_publish"] = utc_now()
    _write_json_atomic(state_path, state)
    return {
        "outbox": str(outbox),
        "published_now": count if worker is None else 0,
        "enqueued_now": count if worker is not None else 0,
        "results": results,
    }


def publish_file(
    envelope_path: Path,
    *,
    project: str = DEFAULT_PROJECT,
    worker: Any | None = None,
) -> dict[str, Any]:
    env = json.loads(envelope_path.read_text(encoding="utf-8"))
    send = publish_envelope(env, project=project, worker=worker)
    return {"path": str(envelope_path), "envelope_id": env.get("id"), "send": send}
