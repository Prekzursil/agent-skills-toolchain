"""Drop-folder watcher: ChatGPT export JSON → outbox packs + envelopes."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bridge import export_conversation_pack, summarize_conversation
from .envelope import content_hash, make_envelope, write_envelope, utc_now


def _is_conversation_export(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    # Classic ChatGPT export shape (mapping tree)
    if "mapping" in data and isinstance(data["mapping"], dict) and data["mapping"]:
        return True
    # Linear export: conversation_id + messages[]
    if data.get("conversation_id") and isinstance(data.get("messages"), list) and data["messages"]:
        return True
    # backend-api conversation object
    if (data.get("id") or data.get("conversation_id")) and isinstance(data.get("mapping"), dict):
        return True
    return False


def _is_stream_trace(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if _is_conversation_export(data):
        return False
    keys = set(data.keys())
    markers = {"story_events", "events", "async_source", "stream", "message_type"}
    if keys & markers:
        return True
    # tiny / metadata-only blobs
    return len(keys) <= 8 and "messages" not in data and "mapping" not in data


def _normalize_to_backend_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize linear export {conversation_id, messages[]} into mapping-like shape for packer."""
    if isinstance(data.get("mapping"), dict) and data["mapping"]:
        # ensure id field
        if not data.get("id") and data.get("conversation_id"):
            data = dict(data)
            data["id"] = data["conversation_id"]
        return data

    if isinstance(data.get("messages"), list):
        mapping: dict[str, Any] = {}
        for i, msg in enumerate(data["messages"]):
            if not isinstance(msg, dict):
                continue
            node_id = str(msg.get("id") or f"node-{i}")
            # wrap linear message into mapping node
            if "author" in msg or "content" in msg:
                mapping[node_id] = {"id": node_id, "message": msg, "children": []}
            else:
                # already a node?
                mapping[node_id] = msg if "message" in msg else {"id": node_id, "message": msg}
        out = {
            "id": data.get("conversation_id") or data.get("id") or "unknown",
            "conversation_id": data.get("conversation_id") or data.get("id"),
            "title": data.get("title"),
            "create_time": data.get("create_time"),
            "update_time": data.get("update_time"),
            "mapping": mapping,
            "source_format": "linear_messages",
        }
        return out
    return data


def process_export_file(
    path: Path,
    *,
    outbox: Path,
    processed_dir: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Process one dropped file. Moves to processed/ or quarantine/."""
    raw = path.read_bytes()
    sha = content_hash(raw)
    result: dict[str, Any] = {
        "source": str(path),
        "sha256": sha,
        "bytes": len(raw),
        "kind": "unknown",
        "ok": False,
    }
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        result["error"] = f"json_parse:{type(e).__name__}"
        _quarantine(path, processed_dir.parent / "quarantine", result)
        return result

    if _is_conversation_export(data):
        result["kind"] = "conversation_export"
        normalized = _normalize_to_backend_shape(data)
        pack = export_conversation_pack(
            normalized,
            outbox,
            project_id=project_id,
        )
        env_path = Path(pack["envelope_path"])
        env = json.loads(env_path.read_text(encoding="utf-8"))
        env.setdefault("meta", {})
        env["meta"]["ingest"] = {
            "source_path": str(path),
            "source_sha256": sha,
            "mode": "drop_folder",
            "source_format": normalized.get("source_format") or "mapping",
            "ingested_at": utc_now(),
        }
        env_path.write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
        result["ok"] = True
        result["pack"] = pack
        _archive(path, processed_dir, sha)
        return result

    if _is_stream_trace(data):
        result["kind"] = "stream_trace"
        outbox.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = outbox / f"stream_trace_{sha[:12]}_{stamp}.json"
        dest.write_bytes(raw)
        env = make_envelope(
            from_rail="chatgpt_export_folder",
            to_rail="broadcast",
            intent="protocol_fixture",
            payload_ref=str(dest),
            project_id=project_id or str(Path.home() / "source" / "agent-skills-toolchain"),
            completion="SUCCESS",
            meta={
                "kind": "stream_trace",
                "source_path": str(path),
                "source_sha256": sha,
                "note": "UI-layer snapshot; use conversation export or live bridge for text",
                "ingested_at": utc_now(),
            },
        )
        env_path = outbox / f"envelope_stream_{sha[:12]}_{stamp}.json"
        write_envelope(env_path, env)
        result["ok"] = True
        result["payload_path"] = str(dest)
        result["envelope_path"] = str(env_path)
        _archive(path, processed_dir, sha)
        return result

    result["error"] = "unrecognized_shape"
    _quarantine(path, processed_dir.parent / "quarantine", result)
    return result


def _archive(path: Path, processed_dir: Path, sha: str) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    dest = processed_dir / f"{sha[:16]}_{path.name}"
    if dest.exists():
        path.unlink(missing_ok=True)
        return
    shutil.move(str(path), str(dest))


def _quarantine(path: Path, quarantine_dir: Path, result: dict) -> None:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = quarantine_dir / f"{stamp}_{path.name}"
    try:
        shutil.move(str(path), str(dest))
        result["quarantine"] = str(dest)
    except Exception as e:
        result["quarantine_error"] = type(e).__name__
    note = quarantine_dir / f"{stamp}_{path.name}.error.json"
    note.write_text(json.dumps(result, indent=2), encoding="utf-8")


def scan_inbox(
    inbox_dir: Path,
    *,
    outbox: Path,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Process all *.json in inbox (non-recursive). Idempotent via content hash state."""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    processed_dir = inbox_dir / "processed"
    state_path = state_path or (inbox_dir / ".ingest_state.json")
    state: dict[str, Any] = {"seen_sha256": []}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    seen = set(state.get("seen_sha256") or [])

    results = []
    for path in sorted(inbox_dir.glob("*.json")):
        if path.name.startswith("."):
            continue
        sha = content_hash(path.read_bytes())
        if sha in seen:
            results.append({"source": str(path), "skipped": True, "reason": "duplicate_sha", "sha256": sha})
            # still move aside
            _archive(path, processed_dir, sha)
            continue
        r = process_export_file(path, outbox=outbox, processed_dir=processed_dir)
        if r.get("ok"):
            seen.add(sha)
        results.append(r)

    state["seen_sha256"] = sorted(seen)[-500:]  # cap
    state["last_scan"] = utc_now()
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {
        "inbox": str(inbox_dir),
        "outbox": str(outbox),
        "processed": len([r for r in results if r.get("ok")]),
        "skipped": len([r for r in results if r.get("skipped")]),
        "failed": len([r for r in results if not r.get("ok") and not r.get("skipped")]),
        "results": results,
    }


def watch_inbox(
    inbox_dir: Path,
    *,
    outbox: Path,
    interval_sec: float = 5.0,
    once: bool = False,
) -> dict[str, Any]:
    """Poll inbox. once=True runs a single scan (for CLI / scheduled tasks)."""
    if once:
        return scan_inbox(inbox_dir, outbox=outbox)
    # bounded loop for interactive use — Ctrl+C to stop
    last: dict[str, Any] = {}
    try:
        while True:
            last = scan_inbox(inbox_dir, outbox=outbox)
            if last.get("processed") or last.get("failed"):
                print(json.dumps({k: last[k] for k in ("processed", "skipped", "failed")}, indent=2))
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        last["stopped"] = True
        return last
