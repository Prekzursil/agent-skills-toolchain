"""Backend seam for hub feature tools.

The hub owns concrete adapters (Track A ``online`` proxy over cloud-hub's
``bm_*`` REST client, and Track B ``databricks`` adapter). Feature tools in this
package never import those adapters directly -- they call through the
:class:`BackendClient` protocol that the hub injects on ``HubContext``. This
keeps the features backend-agnostic and lets this component build/import/verify
before the sibling adapter components have landed.

Backend selection is out-of-band and FAILS CLOSED to ``online``:
  1. explicit ``backend=`` argument on a tool call, else
  2. ``BIOMNI_BACKEND`` env var, else
  3. the context default (``online``).
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

# Capability tokens a backend may advertise. Feature tools gate on these
# instead of on the backend name, so a future third backend "just works".
CAP_LIST_SKILLS = "list_skills"
CAP_BILLING = "billing"
CAP_LIST_RESULTS = "list_results"
CAP_FETCH_BYTES = "fetch_bytes"  # can return real result-file bytes (self-host)
CAP_BIOMNI_URL = "biomni_url"  # can surface a deep link into the Lab UI
CAP_ADD_MCP = "add_mcp"  # self-hosted Biomni can consume other MCPs

DEFAULT_BACKEND = "online"


@runtime_checkable
class BackendClient(Protocol):
    """Contract every hub backend adapter satisfies.

    All methods are async. Adapters that cannot service a capability should
    still implement the method and raise :class:`BackendUnsupported` (or return
    the documented empty value) rather than be absent -- feature tools probe
    :meth:`capabilities` first and degrade gracefully.
    """

    name: str

    def capabilities(self) -> set[str]:
        """Return the capability tokens (``CAP_*``) this backend supports."""
        ...

    async def list_skills(self) -> list[dict[str, Any]]:
        """Introspect Biomni's tool/skill registry (~150 entries)."""
        ...

    async def billing_balance(self) -> dict[str, Any]:
        """Return remaining credits / balance for token-cost reconciliation."""

    async def list_results(self, session_id: str) -> list[dict[str, Any]]:
        """List result files for a session (name + size, possibly URL)."""

    async def fetch_result_bytes(self, session_id: str, name: str) -> bytes | None:
        """Return the real bytes of a result file, or ``None`` if unavailable.

        Online Lab returns names-only / blocked S3 links, so it returns
        ``None`` here; self-host backends return actual bytes.
        """

    async def biomni_url(self, session_id: str) -> str | None:
        """Return a deep link into the Lab UI for this session, if any."""

    async def add_mcp(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Register another MCP into a self-hosted Biomni ``A1`` agent."""


class BackendUnsupported(RuntimeError):
    """Raised when a backend is asked for a capability it does not have."""


class NullBackend:
    """No-op backend used as a safe default before real adapters are wired.

    Advertises no capabilities; every method returns the documented empty
    value or raises :class:`BackendUnsupported`. Guarantees this component
    imports, registers, and self-tests with zero external dependencies.
    """

    def __init__(self, name: str = DEFAULT_BACKEND) -> None:
        self.name = name

    def capabilities(self) -> set[str]:
        return set()

    async def list_skills(self) -> list[dict[str, Any]]:
        return []

    async def billing_balance(self) -> dict[str, Any]:
        return {}

    async def list_results(self, session_id: str) -> list[dict[str, Any]]:
        return []

    async def fetch_result_bytes(self, session_id: str, name: str) -> bytes | None:
        return None

    async def biomni_url(self, session_id: str) -> str | None:
        return None

    async def add_mcp(self, spec: dict[str, Any]) -> dict[str, Any]:
        raise BackendUnsupported(f"backend {self.name!r} cannot inject MCPs")


class BackendRegistry:
    """Holds the live backend adapters, keyed by name, with a default.

    The hub populates this at startup (e.g. ``register("online", OnlineAdapter())``).
    Until then it hands out a :class:`NullBackend` so features stay importable.
    """

    def __init__(self, default: str = DEFAULT_BACKEND) -> None:
        self._backends: dict[str, BackendClient] = {}
        self._default = default

    def register(self, name: str, client: BackendClient) -> None:
        self._backends[name] = client

    @property
    def default(self) -> str:
        return self._default

    def names(self) -> list[str]:
        return sorted(self._backends) or [self._default]

    def _select_name(self, name: str | None) -> str:
        """Resolve the target backend name using the hub's canonical selector.

        Delegates to :func:`backends.select_backend_name` (arg -> ``$BIOMNI_BACKEND``
        -> ``online``; case/whitespace-insensitive; validated; fail-closed) so
        feature-tool precedence is IDENTICAL to the canonical tool dispatch. When
        the top-level ``backends`` module is not importable (features imported
        standalone), fall back to the historical literal precedence so this
        package still self-tests with zero hub context.
        """
        try:
            import backends as _hub_backends
        except Exception:  # pragma: no cover - standalone fallback
            chosen = name or os.environ.get("BIOMNI_BACKEND") or self._default
            return chosen.strip().lower() if isinstance(chosen, str) else self._default
        return _hub_backends.select_backend_name(name)

    def resolve(self, name: str | None = None) -> BackendClient:
        """Resolve a backend, FAILING CLOSED to the default.

        Precedence is delegated to :func:`backends.select_backend_name` (see
        :meth:`_select_name`). Unknown names fall back to the default rather than
        erroring, so a stale caller never hard-fails the hub.
        """
        chosen = self._select_name(name)
        client = self._backends.get(chosen)
        if client is not None:
            return client
        # fall closed: try default, else a NullBackend named for the request
        client = self._backends.get(self._default)
        return client if client is not None else NullBackend(chosen)
