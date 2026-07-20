"""CRCP capability registry with durable, expiring claim leases.

Definitions and leases use an atomic JSON state file.  Optional Python handlers
remain process-local because callables cannot be represented safely on disk.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


RAILS = ("chatgpt", "claude", "codex", "grok", "agent_mail")
DEFAULT_STATE = Path(__file__).resolve().parent / "reports" / "capabilities.json"
DEFAULT_DB = DEFAULT_STATE  # Compatibility name for callers selecting a backend path.
STATE_SCHEMA = "crcp.capabilities.v1"

Handler = Callable[..., Any]


def _validate_identifier(label: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a non-empty, trimmed string")
    if len(value) > 255:
        raise ValueError(f"{label} must not exceed 255 characters")


def _validate_ttl(ttl_s: float) -> float:
    if isinstance(ttl_s, bool) or not isinstance(ttl_s, (int, float)):
        raise TypeError("ttl_s must be a number")
    ttl = float(ttl_s)
    if not math.isfinite(ttl) or ttl <= 0.0:
        raise ValueError("ttl_s must be finite and greater than zero")
    return ttl


@dataclass(frozen=True)
class Capability:
    """A named operation provided by one CRCP rail."""

    name: str
    rail: str
    handler: Handler | None = None

    def __post_init__(self) -> None:
        _validate_identifier("capability name", self.name)
        _validate_identifier("rail", self.rail)
        if self.rail not in RAILS:
            raise ValueError(f"unknown rail: {self.rail!r}")
        if self.handler is not None and not callable(self.handler):
            raise TypeError("handler must be callable or None")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rail": self.rail,
            "has_handler": self.handler is not None,
        }


DEFAULT_CAPABILITIES = (
    Capability("chatgpt_backend_api", "chatgpt"),
    Capability("claude_orchestration", "claude"),
    Capability("codex_execution", "codex"),
    Capability("grok_reasoning", "grok"),
    Capability("agent_mail_bus", "agent_mail"),
)


def unsupported_capability(
    capability: str,
    *,
    supported: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the typed payload used when a bus request cannot be routed."""

    return {
        "completion": "UNSUPPORTED_CAPABILITY",
        "error": {
            "code": "UNSUPPORTED_CAPABILITY",
            "capability": str(capability),
            "message": f"capability is not registered: {capability}",
        },
        "capabilities_supported": sorted(set(supported)),
    }


class UnsupportedCapabilityError(LookupError):
    """Raised by strict APIs for an unregistered capability."""

    def __init__(self, capability: str, supported: Iterable[str] = ()):
        self.capability = capability
        self.supported = tuple(sorted(set(supported)))
        super().__init__(f"unsupported capability: {capability}")

    def as_bus_result(self) -> dict[str, Any]:
        return unsupported_capability(self.capability, supported=self.supported)


class _StateLock:
    """Portable inter-process lock based on atomic directory creation."""

    def __init__(
        self,
        state_path: Path,
        *,
        timeout_s: float = 10.0,
        stale_s: float = 30.0,
    ):
        self.path = state_path.with_name(f"{state_path.name}.lock")
        self.timeout_s = timeout_s
        self.stale_s = stale_s
        self.acquired = False

    def __enter__(self) -> _StateLock:
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                self.path.mkdir()
                self.acquired = True
                return self
            except FileExistsError:
                self._remove_if_stale()
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out acquiring capability state lock: {self.path}")
                time.sleep(0.01)

    def _remove_if_stale(self) -> None:
        try:
            age = time.time() - self.path.stat().st_mtime
            if age > self.stale_s:
                self.path.rmdir()
        except (FileNotFoundError, OSError):
            pass

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.acquired:
            try:
                self.path.rmdir()
            except FileNotFoundError:
                pass
            self.acquired = False


class CapabilityRegistry:
    """Atomic file-backed capability catalog and lease coordinator."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_STATE,
        *,
        capabilities: Iterable[Capability] = DEFAULT_CAPABILITIES,
        clock: Callable[[], float] = time.time,
    ):
        self.state_path = Path(db_path)
        self.db_path = self.state_path
        self._clock = clock
        self._handlers: dict[str, Handler] = {}
        self._handler_lock = threading.RLock()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        definitions = tuple(capabilities)
        with self._state_lock():
            state = self._read_state()
            changed = not self.state_path.is_file()
            for capability in definitions:
                existing = state["capabilities"].get(capability.name)
                if existing is not None and existing["rail"] != capability.rail:
                    raise ValueError(
                        f"capability {capability.name!r} is already assigned to "
                        f"rail {existing['rail']!r}"
                    )
                if existing is None:
                    state["capabilities"][capability.name] = {"rail": capability.rail}
                    changed = True
            if changed:
                self._write_state(state)
        for capability in definitions:
            if capability.handler is not None:
                self._handlers[capability.name] = capability.handler

    def register(self, capability: Capability, *, replace: bool = False) -> None:
        """Register a definition and retain its optional handler in this process."""

        if not isinstance(capability, Capability):
            raise TypeError("capability must be a Capability")
        with self._state_lock():
            state = self._read_state()
            existing = state["capabilities"].get(capability.name)
            if existing is not None and existing["rail"] != capability.rail and not replace:
                raise ValueError(
                    f"capability {capability.name!r} is already assigned to "
                    f"rail {existing['rail']!r}"
                )
            state["capabilities"][capability.name] = {"rail": capability.rail}
            self._write_state(state)
        with self._handler_lock:
            if capability.handler is None:
                self._handlers.pop(capability.name, None)
            else:
                self._handlers[capability.name] = capability.handler

    def get(self, name: str) -> Capability | None:
        with self._state_lock():
            definition = self._read_state()["capabilities"].get(name)
        if definition is None:
            return None
        with self._handler_lock:
            handler = self._handlers.get(name)
        return Capability(name, definition["rail"], handler)

    def list_capabilities(self, rail: str | None = None) -> list[Capability]:
        if rail is not None and rail not in RAILS:
            raise ValueError(f"unknown rail: {rail!r}")
        with self._state_lock():
            definitions = self._read_state()["capabilities"].copy()
        with self._handler_lock:
            result = [
                Capability(name, item["rail"], self._handlers.get(name))
                for name, item in definitions.items()
                if rail is None or item["rail"] == rail
            ]
        return sorted(result, key=lambda item: (item.rail, item.name))

    def claim_lease(self, capability: str, owner: str, ttl_s: float) -> bool:
        """Atomically claim/renew, or return false for another live owner."""

        _validate_identifier("owner", owner)
        ttl = _validate_ttl(ttl_s)
        now = float(self._clock())
        with self._state_lock():
            state = self._read_state()
            self._require_supported_in_state(capability, state)
            lease = state["leases"].get(capability)
            if lease is not None and lease["owner"] != owner and lease["expires_at"] > now:
                return False
            state["leases"][capability] = {
                "owner": owner,
                "claimed_at": now,
                "expires_at": now + ttl,
            }
            self._write_state(state)
        return True

    def release(self, capability: str, owner: str) -> bool:
        """Release only the caller's lease; return whether it was removed."""

        _validate_identifier("owner", owner)
        with self._state_lock():
            state = self._read_state()
            self._require_supported_in_state(capability, state)
            lease = state["leases"].get(capability)
            if lease is None or lease["owner"] != owner:
                return False
            del state["leases"][capability]
            self._write_state(state)
        return True

    def is_available(self, capability: str) -> bool:
        """Return whether a supported capability has no unexpired claim."""

        now = float(self._clock())
        with self._state_lock():
            state = self._read_state()
            self._require_supported_in_state(capability, state)
            lease = state["leases"].get(capability)
        return lease is None or lease["expires_at"] <= now

    def unsupported(self, capability: str) -> dict[str, Any] | None:
        if self.get(capability) is not None:
            return None
        return unsupported_capability(capability, supported=self.supported_names())

    def check_required(self, required: Iterable[str]) -> dict[str, Any] | None:
        """Validate envelope ``capabilities_required`` values for bus routing."""

        supported = set(self.supported_names())
        for capability in required:
            if capability not in supported:
                return unsupported_capability(capability, supported=supported)
        return None

    def supported_names(self) -> list[str]:
        with self._state_lock():
            names = self._read_state()["capabilities"].keys()
            return sorted(names)

    def dispatch(self, capability: str, *args: Any, **kwargs: Any) -> Any:
        definition = self.get(capability)
        if definition is None:
            raise UnsupportedCapabilityError(capability, self.supported_names())
        if definition.handler is None:
            raise RuntimeError(f"no handler configured for capability: {capability}")
        return definition.handler(*args, **kwargs)

    def _state_lock(self) -> _StateLock:
        return _StateLock(self.state_path)

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {"schema": STATE_SCHEMA, "capabilities": {}, "leases": {}}
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid capability state: {self.state_path}") from exc
        if (
            not isinstance(state, dict)
            or state.get("schema") != STATE_SCHEMA
            or not isinstance(state.get("capabilities"), dict)
            or not isinstance(state.get("leases"), dict)
        ):
            raise RuntimeError(f"invalid capability state schema: {self.state_path}")
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.state_path.parent,
                prefix=f".{self.state_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                json.dump(state, temporary, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self.state_path)
            temporary_name = None
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _require_supported_in_state(capability: str, state: dict[str, Any]) -> None:
        if capability not in state["capabilities"]:
            raise UnsupportedCapabilityError(capability, state["capabilities"].keys())


_default_registry: CapabilityRegistry | None = None
_default_lock = threading.Lock()


def default_registry() -> CapabilityRegistry:
    """Return a lazily created process-wide registry using ``DEFAULT_STATE``."""

    global _default_registry
    if _default_registry is None:
        with _default_lock:
            if _default_registry is None:
                _default_registry = CapabilityRegistry()
    return _default_registry


def claim_lease(capability: str, owner: str, ttl_s: float) -> bool:
    return default_registry().claim_lease(capability, owner, ttl_s)


def release(capability: str, owner: str) -> bool:
    return default_registry().release(capability, owner)


def is_available(capability: str) -> bool:
    return default_registry().is_available(capability)
