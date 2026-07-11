from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .redaction import redact_text
    from .storage import atomic_write_json, atomic_write_text, read_json
except ImportError:
    from redaction import redact_text
    from storage import atomic_write_json, atomic_write_text, read_json


def default_state_root() -> Path:
    configured = os.environ.get("AGENT_HARNESS_STATE_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agents" / "state" / "harness"


def _safe_component(value: str, limit: int = 36) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in value)
    return safe.strip("-.")[:limit] or "project"


_UNIDENTIFIED_SESSION_IDS = {"", "unknown"}


def _session_isolatable(session_id: str | None) -> bool:
    """Whether a session_id identifies one session well enough to isolate it.

    The event adapter defaults a missing session_id to the literal "unknown",
    which every unidentified session shares. Writing a per-session goal under
    it would silently re-merge concurrent sessions (the exact stomping bug this
    module prevents), so treat those as non-isolatable: callers then decline
    isolation instead of faking it with a shared slot.
    """
    return bool(session_id) and str(session_id) not in _UNIDENTIFIED_SESSION_IDS


def canonical_project_path(cwd: str) -> str:
    """Resolve a stable repository/worktree root without spawning git."""
    candidate = Path(os.path.abspath(str(cwd or ".")))
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        try:
            if (parent / ".git").exists():
                return str(parent)
        except OSError:
            break
    return str(candidate)


def project_key(cwd: str) -> str:
    normalized = os.path.normcase(canonical_project_path(cwd))
    digest = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()[:12]
    return f"project-{digest}"


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return redact_text(value, redact_paths=True, max_chars=1000)
    if depth >= 5:
        return redact_text(repr(value), redact_paths=True, max_chars=1000)
    if isinstance(value, dict):
        return {
            redact_text(str(key), redact_paths=True, max_chars=120): _sanitize_value(
                nested, depth + 1
            )
            for key, nested in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(nested, depth + 1) for nested in list(value)[:100]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(repr(value), redact_paths=True, max_chars=1000)


class _FileLock:
    def __init__(self, path: Path, timeout: float = 10.0):
        self.path = path
        self.timeout = timeout
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return self
            except (FileExistsError, PermissionError):
                try:
                    if time.time() - self.path.stat().st_mtime > 30:
                        self.path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("ledger lock unavailable")
                time.sleep(0.01)

    def __exit__(self, *_args):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


class EventLedger:
    """Append-only, secret-redacted event facts shared by both providers."""

    def __init__(
        self,
        state_root: Path | str | None = None,
        *,
        legacy_root: Path | str | None = None,
    ):
        self.root = Path(state_root or default_state_root()).expanduser() / "ledger"
        self.legacy_root = Path(
            legacy_root or Path.home() / ".claude" / "event-ledger"
        ).expanduser()
        self._legacy_cache: dict[str, tuple[dict[str, Any], Path | None]] = {}

    def _dir(self, cwd: str) -> Path:
        return self.root / project_key(cwd)

    def _events(self, cwd: str) -> Path:
        return self._dir(cwd) / "events.jsonl"

    def _state_path(self, cwd: str) -> Path:
        return self._dir(cwd) / "state.json"

    def _shared_event_paths(self, cwd: str) -> list[Path]:
        target = self._events(cwd)
        digest = project_key(cwd).removeprefix("project-")
        try:
            compatible = list(self.root.glob(f"*-{digest}/events.jsonl"))
            compatible.extend(
                self.root.glob(f"project-{digest}-legacy-*/events.jsonl")
            )
        except OSError:
            compatible = []
        paths = list(dict.fromkeys(path for path in compatible if path != target))
        if target.exists():
            paths.append(target)
        return paths

    def _load_state(self, cwd: str) -> dict[str, Any]:
        default = {
            "schema_version": 1,
            "project": project_key(cwd),
            "seq": 0,
            "goal": None,
            "goal_ts": None,
            "decisions": [],
            "open_failures": [],
            "last_event_ts": None,
        }
        loaded = read_json(self._state_path(cwd), default)
        if not isinstance(loaded, dict):
            return default
        return default | loaded

    def _shared_events(self, cwd: str, *, repair: bool = False) -> list[dict[str, Any]]:
        valid: list[dict[str, Any]] = []
        target = self._events(cwd)
        for path in self._shared_event_paths(cwd):
            invalid = False
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            path_valid: list[dict[str, Any]] = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    invalid = True
                    continue
                if isinstance(item, dict):
                    path_valid.append(item)
                else:
                    invalid = True
            valid.extend(path_valid)
            if repair and invalid and path == target:
                content = "".join(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for item in path_valid
                )
                atomic_write_text(path, content)
        return valid

    @staticmethod
    def _tail_bytes(path: Path, max_bytes: int) -> tuple[bytes, bool]:
        try:
            size = path.stat().st_size
            start = max(0, size - max(1, int(max_bytes)))
            with path.open("rb") as handle:
                handle.seek(start)
                data = handle.read()
        except OSError:
            return b"", False
        if start:
            boundary = data.find(b"\n")
            if boundary < 0:
                return b"", False
            data = data[boundary + 1 :]
        return data, start == 0

    @classmethod
    def _last_event_from_path(cls, path: Path) -> dict[str, Any] | None:
        data, _ = cls._tail_bytes(path, 1024 * 1024)
        for raw_line in reversed(data.splitlines()):
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except (UnicodeDecodeError, ValueError):
                continue
            if isinstance(item, dict):
                return item
        return None

    @classmethod
    def _last_shared_seq(cls, paths: list[Path]) -> int:
        latest = 0
        for path in paths:
            item = cls._last_event_from_path(path)
            if item is not None:
                latest = max(latest, int(item.get("seq") or 0))
        return latest

    @classmethod
    def _last_shared_marker(cls, paths: list[Path]) -> tuple[int, str]:
        candidates = [
            item
            for path in paths
            if (item := cls._last_event_from_path(path)) is not None
        ]
        if not candidates:
            return 0, ""
        latest = max(
            candidates,
            key=lambda item: (int(item.get("seq") or 0), str(item.get("ts") or "")),
        )
        return int(latest.get("seq") or 0), str(latest.get("ts") or "")

    @staticmethod
    def _find_event_by_id(paths: list[Path], event_id: str) -> dict[str, Any] | None:
        encoded = event_id.encode("ascii")
        pattern = re.compile(rb'"event_id"\s*:\s*"' + re.escape(encoded) + rb'"')
        for path in paths:
            try:
                data = path.read_bytes()
            except OSError:
                continue
            for match in pattern.finditer(data):
                start = data.rfind(b"\n", 0, match.start()) + 1
                end = data.find(b"\n", match.end())
                if end < 0:
                    end = len(data)
                try:
                    item = json.loads(data[start:end])
                except (UnicodeDecodeError, ValueError):
                    continue
                if isinstance(item, dict) and item.get("event_id") == event_id:
                    return item
        return None

    @classmethod
    def _tail_events_from_path(
        cls, path: Path, *, max_bytes: int
    ) -> list[dict[str, Any]]:
        data, _ = cls._tail_bytes(path, max_bytes)
        result: list[dict[str, Any]] = []
        for raw_line in data.splitlines():
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except (UnicodeDecodeError, ValueError):
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    @classmethod
    def _recent_shared_events(
        cls, paths: list[Path], *, after_seq: int, through_seq: int
    ) -> tuple[list[dict[str, Any]], bool]:
        gap = max(0, through_seq - after_seq)
        if gap == 0:
            return [], True
        if gap > 1000:
            return [], False
        budget = max(64 * 1024, min(16 * 1024 * 1024, (gap + 8) * 16 * 1024))
        events: list[dict[str, Any]] = []
        for path in paths:
            events.extend(cls._tail_events_from_path(path, max_bytes=budget))
        events = [item for item in events if int(item.get("seq") or 0) > after_seq]
        events.sort(key=lambda item: (int(item.get("seq") or 0), str(item.get("ts") or "")))
        if not events:
            return [], False
        covered = {int(item.get("seq") or 0) for item in events}
        complete = all(seq in covered for seq in range(after_seq + 1, through_seq + 1))
        return events, complete

    @classmethod
    def _bounded_shared_events(cls, paths: list[Path], limit: int) -> list[dict[str, Any]]:
        budget = max(256 * 1024, min(8 * 1024 * 1024, max(1, limit) * 16 * 1024))
        events: list[dict[str, Any]] = []
        for path in paths:
            events.extend(cls._tail_events_from_path(path, max_bytes=budget)[-limit:])
        events.sort(key=lambda item: (str(item.get("ts") or ""), int(item.get("seq") or 0)))
        return events[-limit:]

    @staticmethod
    def _ensure_append_boundary(path: Path) -> None:
        try:
            if not path.exists() or path.stat().st_size == 0:
                return
            with path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                terminated = handle.read(1) == b"\n"
            if not terminated:
                with path.open("ab") as handle:
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
        except OSError:
            return

    def _apply_events_to_state(
        self, cwd: str, fallback: dict[str, Any], events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        state = dict(fallback)
        state.update(
            {
                "schema_version": 1,
                "project": project_key(cwd),
                "seq": int(fallback.get("seq") or 0),
                "goal": fallback.get("goal"),
                "goal_ts": fallback.get("goal_ts"),
                "decisions": list(fallback.get("decisions") or []),
                "open_failures": list(fallback.get("open_failures") or []),
                "last_event_ts": fallback.get("last_event_ts"),
            }
        )
        for event in events:
            seq = int(event.get("seq") or 0)
            if seq <= int(state["seq"]):
                continue
            state["seq"] = seq
            if event.get("ts"):
                state["last_event_ts"] = event["ts"]
            kind = event.get("kind")
            if kind == "goal" and event.get("text"):
                state["goal"] = event["text"]
                state["goal_ts"] = event.get("ts")
            elif kind == "decision":
                state["decisions"].append(
                    {"seq": seq, "text": event.get("text", "")}
                )
            elif kind == "failure":
                state["open_failures"].append(
                    {
                        "seq": seq,
                        "text": event.get("text", ""),
                        "preconditions": event.get("preconditions", ""),
                    }
                )
            elif kind == "milestone":
                supersedes = set(event.get("supersedes_failures") or [])
                if supersedes:
                    state["open_failures"] = [
                        item
                        for item in state["open_failures"]
                        if item.get("seq") not in supersedes
                    ]
        state["decisions"] = state["decisions"][-20:]
        state["open_failures"] = state["open_failures"][-20:]
        return state

    def _project_state(
        self,
        cwd: str,
        events: list[dict[str, Any]],
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fallback = fallback or {}
        state: dict[str, Any] = {
            "schema_version": 1,
            "project": project_key(cwd),
            "seq": 0,
            "goal": fallback.get("goal"),
            "goal_ts": fallback.get("goal_ts"),
            "decisions": [],
            "open_failures": [],
            "last_event_ts": fallback.get("last_event_ts"),
        }
        failures: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        for event in events:
            seq = int(event.get("seq") or 0)
            state["seq"] = max(int(state["seq"]), seq)
            if event.get("ts"):
                state["last_event_ts"] = event["ts"]
            kind = event.get("kind")
            if kind == "goal" and event.get("text"):
                state["goal"] = event["text"]
                state["goal_ts"] = event.get("ts")
            elif kind == "decision":
                decisions.append({"seq": seq, "text": event.get("text", "")})
            elif kind == "failure":
                failures.append(
                    {
                        "seq": seq,
                        "text": event.get("text", ""),
                        "preconditions": event.get("preconditions", ""),
                    }
                )
            elif kind == "milestone":
                supersedes = set(event.get("supersedes_failures") or [])
                if supersedes:
                    failures = [item for item in failures if item.get("seq") not in supersedes]
        state["decisions"] = decisions[-20:]
        state["open_failures"] = failures[-20:]
        return state

    def append(
        self,
        cwd: str,
        kind: str,
        *,
        dedupe_key: str | None = None,
        **fields: Any,
    ) -> dict[str, Any] | None:
        directory = self._dir(cwd)
        directory.mkdir(parents=True, exist_ok=True)
        with _FileLock(directory / ".lock"):
            persisted = self._load_state(cwd)
            paths = self._shared_event_paths(cwd)
            tail_seq = self._last_shared_seq(paths)
            recent, state_complete = self._recent_shared_events(
                paths,
                after_seq=int(persisted.get("seq") or 0),
                through_seq=tail_seq,
            )
            state = (
                self._apply_events_to_state(cwd, persisted, recent)
                if state_complete
                else persisted
            )
            event_id = ""
            if dedupe_key:
                event_id = hashlib.sha256(
                    dedupe_key.encode("utf-8", "replace")
                ).hexdigest()
                if self._find_event_by_id(paths, event_id) is not None:
                    if state_complete and state != persisted:
                        atomic_write_json(self._state_path(cwd), state)
                    return None

            seq = max(tail_seq, int(persisted.get("seq") or 0)) + 1
            event: dict[str, Any] = {
                "schema_version": 1,
                "seq": seq,
                "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "kind": _safe_component(str(kind), 32),
            }
            if event_id:
                event["event_id"] = event_id
            for key, value in fields.items():
                clean_key = _safe_component(str(key), 48)
                event[clean_key] = _sanitize_value(value)

            target = self._events(cwd)
            self._ensure_append_boundary(target)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

            if state_complete:
                state = self._apply_events_to_state(cwd, state, [event])
                atomic_write_json(self._state_path(cwd), state)
            return event

    def replay(self, cwd: str, limit: int = 40) -> list[dict[str, Any]]:
        requested = max(1, min(int(limit), 200))
        result = self._bounded_shared_events(self._shared_event_paths(cwd), requested)
        combined = self._legacy_events(cwd) + result
        deduped: dict[str, dict[str, Any]] = {}
        for item in combined:
            identity = str(item.get("event_id") or json.dumps(
                    {
                        "ts": item.get("ts"),
                        "kind": item.get("kind"),
                        "text": item.get("text"),
                        "seq": item.get("seq"),
                        "tool": item.get("tool"),
                        "result_hash": item.get("result_hash"),
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ))
            deduped[identity] = item
        return sorted(
            deduped.values(), key=lambda item: (str(item.get("ts") or ""), int(item.get("seq") or 0))
        )[-requested:]

    def state(self, cwd: str) -> dict[str, Any]:
        persisted = self._load_state(cwd)
        paths = self._shared_event_paths(cwd)
        tail_seq, tail_ts = self._last_shared_marker(paths)
        state_matches_tail = (
            int(persisted.get("seq") or 0) >= tail_seq
            and str(persisted.get("last_event_ts") or "") == tail_ts
        )
        if state_matches_tail:
            shared_events: list[dict[str, Any]] = []
            shared = persisted
        else:
            shared_events = self._shared_events(cwd)
            shared = self._project_state(cwd, shared_events, persisted)
        legacy, _ = self._find_legacy(cwd)
        events = self._legacy_events(cwd)
        decisions = [
            {"seq": item.get("seq"), "text": item.get("text", "")}
            for item in events
            if item.get("kind") == "decision"
        ]
        shared["goal"] = self._latest_goal(
            shared_events=shared_events,
            legacy_events=events,
            shared_state=persisted,
            legacy_state=legacy,
        )
        shared["decisions"] = (decisions + list(shared.get("decisions") or []))[-20:]
        shared["open_failures"] = (
            list(legacy.get("open_failures") or []) + list(shared.get("open_failures") or [])
        )[-20:]
        shared["legacy_seq"] = int(legacy.get("seq") or 0)
        return shared

    @staticmethod
    def _timestamp(value: Any) -> float:
        if not value:
            return 0.0
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (TypeError, ValueError):
            return 0.0

    def _latest_goal(
        self,
        *,
        shared_events: list[dict[str, Any]],
        legacy_events: list[dict[str, Any]],
        shared_state: dict[str, Any],
        legacy_state: dict[str, Any],
    ) -> str | None:
        candidates: list[tuple[float, int, str]] = []
        for order, event in enumerate(legacy_events + shared_events):
            if event.get("kind") == "goal" and event.get("text"):
                candidates.append(
                    (self._timestamp(event.get("ts")), order, str(event["text"]))
                )
        if legacy_state.get("goal") and not any(
            event.get("kind") == "goal" and event.get("text")
            for event in legacy_events
        ):
            candidates.append(
                (
                    self._timestamp(legacy_state.get("last_event_ts")),
                    -2,
                    str(legacy_state["goal"]),
                )
            )
        if shared_state.get("goal") and not any(
            event.get("kind") == "goal" and event.get("text")
            for event in shared_events
        ):
            candidates.append(
                (
                    self._timestamp(
                        shared_state.get("goal_ts") or shared_state.get("last_event_ts")
                    ),
                    -1,
                    str(shared_state["goal"]),
                )
            )
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item[0], item[1]))[2]

    def _session_goal_path(self, session_id: str) -> Path:
        token = hashlib.sha256(
            str(session_id or "").encode("utf-8", "replace")
        ).hexdigest()[:20]
        return self.root.parent / "session-goals" / f"{token}.json"

    def _read_session_goal(self, session_id: str) -> str:
        data = read_json(self._session_goal_path(session_id), {})
        if isinstance(data, dict):
            goal = data.get("goal")
            if goal:
                return str(goal)
        return ""

    def _write_session_goal(self, session_id: str, text: str) -> None:
        atomic_write_json(
            self._session_goal_path(session_id),
            {
                "goal": text,
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )

    def set_goal(self, cwd: str, text: str, session_id: str | None = None) -> None:
        clean = redact_text(text, redact_paths=True, max_chars=500).strip()
        if not clean:
            return
        # The append keeps a durable project audit trail; the active goal used
        # for re-injection/replay is resolved per-session to stop concurrent
        # sessions in one cwd from stomping each other's goal.
        self.append(cwd, "goal", text=clean)
        if _session_isolatable(session_id):
            self._write_session_goal(session_id, clean)

    def goal(self, cwd: str, session_id: str | None = None) -> str:
        # A provided session_id requests STRICT per-session isolation: return
        # that session's own goal or empty, never another session's. An
        # unidentified session ("unknown"/empty) cannot be isolated, so decline
        # rather than serve a shared goal. Only the no-session form (None, for
        # legacy inspection) falls back to the project-latest goal.
        if session_id is not None:
            if _session_isolatable(session_id):
                return self._read_session_goal(session_id)
            return ""
        goal = self.state(cwd).get("goal")
        if goal:
            return str(goal)
        return ""

    def pointer(self, cwd: str) -> dict[str, Any]:
        state = self.state(cwd)
        return {
            "project": project_key(cwd),
            "seq": int(state.get("seq") or 0),
            "legacy_seq": int(state.get("legacy_seq") or 0),
        }

    def has_verification(self, cwd: str, turn_id: str = "") -> bool:
        for item in reversed(self.replay(cwd, limit=60)):
            if item.get("kind") != "tool_result":
                continue
            if turn_id and item.get("turn_id") not in {"", turn_id}:
                continue
            if item.get("verified") is True:
                return True
        return False

    def _find_legacy(self, cwd: str) -> tuple[dict[str, Any], Path | None]:
        key = project_key(cwd)
        if key in self._legacy_cache:
            return self._legacy_cache[key]
        if not self.legacy_root.exists():
            result = ({}, None)
            self._legacy_cache[key] = result
            return result
        target = os.path.normcase(canonical_project_path(cwd))
        try:
            candidates = list(self.legacy_root.glob("*/state.json"))
        except OSError:
            result = ({}, None)
            self._legacy_cache[key] = result
            return result
        for path in candidates[:200]:
            raw_state = read_json(path, {})
            if not isinstance(raw_state, dict):
                continue
            paths = [raw_state.get("project"), *(raw_state.get("aliases") or [])]
            for candidate in paths:
                if candidate and os.path.normcase(canonical_project_path(str(candidate))) == target:
                    safe_state = _sanitize_value(raw_state)
                    result = (
                        safe_state if isinstance(safe_state, dict) else {},
                        path.parent,
                    )
                    self._legacy_cache[key] = result
                    return result
        result = ({}, None)
        self._legacy_cache[key] = result
        return result

    def _legacy_events(self, cwd: str) -> list[dict[str, Any]]:
        _, directory = self._find_legacy(cwd)
        if directory is None:
            return []
        path = directory / "events.jsonl"
        if not path.exists():
            return []
        lines: list[str] = []
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.strip():
                        lines.append(line)
        except OSError:
            return []
        result: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            cleaned = _sanitize_value(item)
            if isinstance(cleaned, dict):
                result.append(cleaned)
        return result
