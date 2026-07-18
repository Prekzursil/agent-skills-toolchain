#!/usr/bin/env python3
"""Emit truthful, privacy-bounded OATS tool-selection events.

Supported hook events:

* UserPromptSubmit caches the submitted prompt for a bounded time.  This is a
  fallback only; it emits no selection event.
* PostToolUse emits a positive selection when its tool_use_id can be correlated
  to a real user turn in the transcript or to that session's prompt cache.
* PostToolUseFailure emits the same schema with success=false.

The destination is the existing event-ledger project so event-ledger/oats.py
sees kind="selection" without adaptation.  The canonical ledger natively admits
this kind and serializes per-shard appends; monotonic seq and state.json stay
intact even when a parallel tool batch completes concurrently.

Privacy and bounds:

* selection records and the prompt cache never persist tool_input,
  tool_response, error text, transcript paths, or raw session ids; canonical
  event-ledger state.json still retains its existing project cwd/alias metadata;
* redacts common credential forms and truncates query text to 2,000 characters;
* reads at most 1 MiB / 5,000 lines from a transcript tail and 2 MiB for dedup;
* prompt fallback files expire after 24 hours and are capped at 128 files;
* one compact append (at most 16 KiB) per unique documented tool_use_id;
* cross-process claim markers are capped at 4,096 and retained for seven days.

FAIL-OPEN: every input, correlation, cache, and append error is swallowed and
main always returns zero.  This hook never blocks or injects context.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
HOOKS_ROOT = HERE.parent
STATE_ROOT = Path(
    os.environ.get(
        "SELECTION_EVENT_STATE_ROOT",
        str(Path.home() / ".claude" / "selection-events"),
    )
)

SCHEMA = "selection.v1"
MAX_QUERY_CHARS = 2_000
MAX_TOOL_CHARS = 256
MAX_TRANSCRIPT_BYTES = 1 * 1024 * 1024
MAX_TRANSCRIPT_LINES = 5_000
MAX_DEDUP_BYTES = 2 * 1024 * 1024
MAX_EVENT_BYTES = 16 * 1024
MAX_INPUT_BYTES = 2 * 1024 * 1024
PROMPT_TTL_SECONDS = 24 * 60 * 60
MAX_PROMPT_FILES = 128
CLAIM_TTL_SECONDS = 7 * 24 * 60 * 60
PENDING_STALE_SECONDS = 5 * 60
MAX_CLAIM_FILES = 4_096
CLAIM_GC_INTERVAL_SECONDS = 60 * 60
CLAIM_GC_LOCK_STALE_SECONDS = 60


_PEM_SECRET = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_LABELED_SECRET = re.compile(
    r"\b(password|passwd|api[_ -]?key|access[_ -]?token|auth[_ -]?token|secret|token)"
    r"\s*([:=])\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)",
    re.IGNORECASE,
)
_COMMON_TOKENS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
)
_URL_CREDENTIAL = re.compile(
    r"\b([A-Za-z][A-Za-z0-9+.-]*://[^:/\s]+:)[^@\s]+@", re.IGNORECASE
)


def _hash(value: str, length: int = 64) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:length]


def _redact_and_bound(raw: Any) -> tuple[str, str]:
    """Return (safe query, hash of safe query). Empty means unusable evidence."""
    if not isinstance(raw, str):
        return "", ""
    text = raw.replace("\x00", "").replace("\r\n", "\n").strip()
    if not text:
        return "", ""
    text = _PEM_SECRET.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _LABELED_SECRET.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text
    )
    for pattern in _COMMON_TOKENS:
        text = pattern.sub("[REDACTED]", text)
    text = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", text)
    marker = "…[TRUNCATED]"
    if len(text) > MAX_QUERY_CHARS:
        text = text[: MAX_QUERY_CHARS - len(marker)] + marker
    return text, _hash(text)


def _tail_lines(path_text: str) -> list[str] | None:
    """Read a bounded transcript tail; discard a partial first line after seek."""
    path = Path(path_text)
    if not path_text or not path.is_file():
        return None
    size = path.stat().st_size
    start = max(0, size - MAX_TRANSCRIPT_BYTES)
    with path.open("rb") as handle:
        handle.seek(start)
        raw = handle.read(MAX_TRANSCRIPT_BYTES)
    lines = raw.decode("utf-8", "replace").splitlines()
    if start and lines:
        lines = lines[1:]
    return lines[-MAX_TRANSCRIPT_LINES:]


def _real_user_text(event: dict[str, Any]) -> tuple[str, str] | None:
    """Return (text, evidence id) for genuine user speech, never tool results/meta."""
    if not isinstance(event, dict) or event.get("isMeta") is True:
        return None
    message = event.get("message")
    if not isinstance(message, dict):
        message = {}
    if event.get("type") != "user" or message.get("role") not in (None, "user"):
        return None
    content = message.get("content", event.get("content"))
    if isinstance(content, list):
        if any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        ):
            return None
        pieces = [
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        raw_text = "\n".join(piece for piece in pieces if piece).strip()
    elif isinstance(content, str):
        raw_text = content
    else:
        return None
    safe_text, query_hash = _redact_and_bound(raw_text)
    if not safe_text:
        return None
    uuid = str(event.get("uuid") or "")
    evidence = _hash(f"transcript\0{uuid}\0{query_hash}", 24)
    return safe_text, query_hash + ":" + evidence


def _is_nonhuman_user_boundary(event: dict[str, Any]) -> bool:
    """True for explicit system/agent notifications represented as user events.

    Tool-result user events are intentionally not boundaries: they are part of the
    current human turn and must not erase its query.
    """
    if not isinstance(event, dict) or event.get("type") != "user":
        return False
    message = event.get("message")
    if not isinstance(message, dict):
        message = {}
    content = message.get("content", event.get("content"))
    if isinstance(content, list) and any(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    ):
        return False
    if any(
        event.get(flag) is True
        for flag in ("isMeta", "isSidechain", "isCompactSummary")
    ):
        return True
    prompt_source = str(
        event.get("promptSource") or message.get("promptSource") or ""
    ).strip().lower()
    if prompt_source in {"system", "hook", "agent", "tool", "task-notification"}:
        return True
    origin = event.get("origin") or message.get("origin") or {}
    if isinstance(origin, dict):
        origin_kind = str(origin.get("kind") or "").strip().lower()
        if origin_kind in {
            "system",
            "hook",
            "agent",
            "subagent",
            "tool",
            "task-notification",
        }:
            return True
    raw_text = content if isinstance(content, str) else ""
    lowered = raw_text.lstrip().lower()
    return lowered.startswith(
        (
            "<task-notification>",
            "<system-reminder>",
            "<local-command-caveat>",
        )
    )


def _tool_use_ids(event: dict[str, Any]) -> list[str]:
    message = event.get("message") if isinstance(event, dict) else None
    if not isinstance(message, dict):
        message = {}
    content = message.get("content", event.get("content") if isinstance(event, dict) else None)
    if not isinstance(content, list):
        return []
    return [
        str(block.get("id") or "")
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "tool_use"
        and block.get("id")
    ]


def _query_from_transcript(
    path_text: str, tool_use_id: str
) -> tuple[str, dict[str, str] | None]:
    """Return correlation status plus evidence.

    Status is one of:
      matched              exact tool_use_id plus preceding real user text;
      target_without_query exact tool_use_id, but user text fell outside the tail;
      absent               readable transcript proves target id is not present;
      unavailable          transcript is missing, unreadable, or wholly malformed.
    """
    try:
        lines = _tail_lines(path_text)
    except Exception:
        return "unavailable", None
    if lines is None:
        return "unavailable", None
    parsed = False
    target_index: int | None = None
    # Tool-use ids are normally near the transcript tail. Find the exact target
    # backwards first so the hot path does not JSON-parse thousands of old turns.
    for index in range(len(lines) - 1, -1, -1):
        try:
            event = json.loads(lines[index])
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        parsed = True
        if tool_use_id in _tool_use_ids(event):
            target_index = index
            break
    if target_index is None:
        return ("absent" if parsed else "unavailable"), None

    # Walk only from the target back to its nearest user-shaped boundary.
    for index in range(target_index - 1, -1, -1):
        try:
            event = json.loads(lines[index])
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        if _is_nonhuman_user_boundary(event):
            return "nonhuman", None
        matched = _real_user_text(event)
        if matched is None:
            continue
        query, packed = matched
        query_hash, evidence = packed.split(":", 1)
        return "matched", {
            "query": query,
            "query_hash": query_hash,
            "query_source": "transcript",
            "query_evidence": evidence,
        }
    return "target_without_query", None


def _prompt_file(session_id: str) -> Path:
    return STATE_ROOT / "prompts" / f"{_hash(session_id or 'unknown', 24)}.json"


def _gc_prompt_cache() -> None:
    """Bound fallback prompt retention by age and count. Best-effort only."""
    directory = STATE_ROOT / "prompts"
    if not directory.is_dir():
        return
    now = time.time()
    kept: list[tuple[float, Path]] = []
    for path in directory.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
            if now - mtime > PROMPT_TTL_SECONDS:
                path.unlink(missing_ok=True)
            else:
                kept.append((mtime, path))
        except Exception:
            continue
    for _, path in sorted(kept, reverse=True)[MAX_PROMPT_FILES:]:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _store_prompt(data: dict[str, Any]) -> None:
    session_id = str(data.get("session_id") or "")
    raw_prompt = data.get("prompt")
    # Claude can deliver background completions and hook/system reminders through the
    # UserPromptSubmit surface. Treat the same explicit provenance/markup as a hard
    # non-human boundary here; otherwise an internal notification could overwrite the
    # real prompt cache and later become false OATS training evidence.
    candidate = dict(data)
    candidate["type"] = "user"
    message = candidate.get("message")
    if not isinstance(message, dict):
        message = {}
    else:
        message = dict(message)
    message["role"] = "user"
    message["content"] = raw_prompt
    candidate["message"] = message
    if _is_nonhuman_user_boundary(candidate):
        return
    query, query_hash = _redact_and_bound(raw_prompt)
    if not session_id or not query:
        return
    cwd_hash = _hash(str(data.get("cwd") or ""), 24)
    record = {
        "schema": "selection-prompt-cache.v1",
        "session_hash": _hash(session_id, 24),
        "cwd_hash": cwd_hash,
        "query": query,
        "query_hash": query_hash,
        "query_evidence": _hash(f"prompt\0{query_hash}", 24),
        "captured_at": time.time(),
    }
    path = _prompt_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        temp_path.write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temp_path, path)
        try:
            path.chmod(0o600)
        except Exception:
            pass
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
    _gc_prompt_cache()


def _query_from_prompt_cache(data: dict[str, Any]) -> dict[str, str] | None:
    session_id = str(data.get("session_id") or "")
    if not session_id:
        return None
    try:
        record = json.loads(_prompt_file(session_id).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(record, dict) or record.get("schema") != "selection-prompt-cache.v1":
        return None
    if record.get("session_hash") != _hash(session_id, 24):
        return None
    if record.get("cwd_hash") != _hash(str(data.get("cwd") or ""), 24):
        return None
    try:
        age = time.time() - float(record.get("captured_at", 0))
        if age < -300 or age > PROMPT_TTL_SECONDS:
            return None
    except Exception:
        return None
    query = record.get("query")
    query_hash = record.get("query_hash")
    evidence = record.get("query_evidence")
    if not all(isinstance(value, str) and value for value in (query, query_hash, evidence)):
        return None
    if len(query) > MAX_QUERY_CHARS:
        return None
    checked_query, checked_hash = _redact_and_bound(query)
    if checked_query != query or checked_hash != query_hash:
        return None
    if evidence != _hash(f"prompt\0{query_hash}", 24):
        return None
    return {
        "query": query,
        "query_hash": query_hash,
        "query_source": "user_prompt_submit",
        "query_evidence": evidence,
    }


def _ledger_module():
    """Resolve the canonical event-ledger module lazily, fail-open on import drift."""
    event_ledger = HOOKS_ROOT / "event-ledger"
    if str(event_ledger) not in sys.path:
        sys.path.insert(0, str(event_ledger))
    import ledger  # type: ignore  # noqa: PLC0415

    return ledger


def _ledger_has_event(ledger, cwd: str, event_id: str) -> bool:
    path = ledger._events_file(cwd)  # noqa: SLF001 - compatibility seam
    if not path.is_file():
        return False
    size = path.stat().st_size
    start = max(0, size - MAX_DEDUP_BYTES)
    with path.open("rb") as handle:
        handle.seek(start)
        raw = handle.read(MAX_DEDUP_BYTES)
    lines = raw.decode("utf-8", "replace").splitlines()
    if start and lines:
        lines = lines[1:]
    for line in reversed(lines):
        if event_id not in line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("kind") == "selection" and event.get("event_id") == event_id:
            return True
    return False


def _gc_claims() -> None:
    directory = STATE_ROOT / "claims"
    if not directory.is_dir():
        return
    now = time.time()
    stamp = directory / ".gc-stamp"
    try:
        if now - stamp.stat().st_mtime < CLAIM_GC_INTERVAL_SECONDS:
            return
    except Exception:
        pass
    gc_lock = directory / ".gc-lock"
    try:
        descriptor = os.open(gc_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            if now - gc_lock.stat().st_mtime > CLAIM_GC_LOCK_STALE_SECONDS:
                gc_lock.unlink(missing_ok=True)
        except Exception:
            pass
        return
    try:
        os.close(descriptor)
        try:
            if now - stamp.stat().st_mtime < CLAIM_GC_INTERVAL_SECONDS:
                return
        except Exception:
            pass
        _gc_claim_files(directory, now)
        stamp.touch(exist_ok=True)
    finally:
        try:
            gc_lock.unlink(missing_ok=True)
        except Exception:
            pass


def _gc_claim_files(directory: Path, now: float) -> None:
    """Perform the bounded scan; caller throttles and serializes this hot-path work."""
    done: list[tuple[float, Path]] = []
    for pending in directory.glob("*.pending"):
        try:
            if now - pending.stat().st_mtime > PENDING_STALE_SECONDS:
                pending.unlink(missing_ok=True)
        except Exception:
            continue
    for path in directory.glob("*.done"):
        try:
            mtime = path.stat().st_mtime
            if now - mtime > CLAIM_TTL_SECONDS:
                path.unlink(missing_ok=True)
            else:
                done.append((mtime, path))
        except Exception:
            continue
    for _, path in sorted(done, reverse=True)[MAX_CLAIM_FILES:]:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _claim_event(event_id: str) -> Path | None:
    directory = STATE_ROOT / "claims"
    directory.mkdir(parents=True, exist_ok=True)
    _gc_claims()
    done = directory / f"{event_id}.done"
    pending = directory / f"{event_id}.pending"
    if done.exists():
        return None
    try:
        descriptor = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return None
    try:
        os.write(descriptor, b"pending\n")
    finally:
        os.close(descriptor)
    # Close the done-check -> pending-create transition race: an earlier owner
    # can rename its pending file to done between those two operations.
    if done.exists():
        _release_claim(pending)
        return None
    return pending


def _finish_claim(pending: Path) -> None:
    os.replace(pending, pending.with_suffix(".done"))


def _release_claim(pending: Path) -> None:
    try:
        pending.unlink(missing_ok=True)
    except Exception:
        pass


def _append_event(cwd: str, fields: dict[str, Any]) -> None:
    """Append via the canonical lock-safe ledger after a unique event claim."""
    encoded = json.dumps(
        {"seq": 0, "ts": "", "kind": "selection", **fields},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_EVENT_BYTES:
        return
    event_id = str(fields.get("event_id") or "")
    pending = _claim_event(event_id)
    if pending is None:
        return
    ledger = None
    try:
        ledger = _ledger_module()
        kinds = tuple(getattr(ledger, "KINDS", ()))
        if "selection" not in kinds:
            raise RuntimeError("event-ledger does not admit selection events")
        written = ledger.append(cwd, "selection", **fields)
        if not isinstance(written, dict) or written.get("kind") != "selection":
            raise RuntimeError("ledger did not preserve selection kind")
    except Exception:
        try:
            landed = bool(ledger and _ledger_has_event(ledger, cwd, event_id))
        except Exception:
            landed = False
        if not landed:
            _release_claim(pending)
            raise
    try:
        _finish_claim(pending)
    except Exception:
        pass


def _emit_selection(data: dict[str, Any], success: bool) -> None:
    session_id = str(data.get("session_id") or "")
    tool_use_id = str(data.get("tool_use_id") or "")
    tool_name = str(data.get("tool_name") or "").strip()[:MAX_TOOL_CHARS]
    cwd = str(data.get("cwd") or "")
    if not session_id or not tool_use_id or not tool_name or not cwd:
        return
    transcript_status, evidence = _query_from_transcript(
        str(data.get("transcript_path") or ""), tool_use_id
    )
    if transcript_status in ("unavailable", "target_without_query"):
        evidence = _query_from_prompt_cache(data)
    elif transcript_status in ("absent", "nonhuman"):
        return
    if evidence is None:
        return
    event_id = _hash(f"{SCHEMA}\0{session_id}\0{tool_use_id}", 32)
    fields: dict[str, Any] = {
        "schema": SCHEMA,
        "event_id": event_id,
        "query": evidence["query"],
        "query_hash": evidence["query_hash"],
        "query_source": evidence["query_source"],
        "query_evidence": evidence["query_evidence"],
        "chosen_tool": tool_name,
        "success": bool(success),
        "session_hash": _hash(session_id, 24),
        "tool_use_id": tool_use_id,
    }
    _append_event(cwd, fields)


def main() -> int:
    try:
        try:
            stream = getattr(sys.stdin, "buffer", None)
            if stream is not None:
                raw_bytes = stream.read(MAX_INPUT_BYTES + 1)
                if len(raw_bytes) > MAX_INPUT_BYTES:
                    return 0
                raw = raw_bytes.decode("utf-8", "replace")
            else:
                raw = sys.stdin.read(MAX_INPUT_BYTES + 1)
                if len(raw.encode("utf-8", "replace")) > MAX_INPUT_BYTES:
                    return 0
            data = json.loads(raw or "{}")
        except Exception:
            return 0
        if not isinstance(data, dict):
            return 0
        event_name = str(data.get("hook_event_name") or "")
        if event_name == "UserPromptSubmit":
            try:
                _store_prompt(data)
            except Exception:
                pass
        elif event_name == "PostToolUse":
            try:
                _emit_selection(data, True)
            except Exception:
                pass
        elif event_name == "PostToolUseFailure":
            try:
                _emit_selection(data, False)
            except Exception:
                pass
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
