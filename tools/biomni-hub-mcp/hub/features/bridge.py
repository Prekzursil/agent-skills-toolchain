"""R6 bridge -- adapt the sync ``BiomniBackend`` adapters onto the async
``BackendClient`` protocol the A3 feature tools consume.

The canonical adapters (``adapters.online`` / ``adapters.databricks``) are
SYNCHRONOUS and return :class:`schema.ToolEnvelope`. The A3 feature tools
(``biomni_run_history`` / ``biomni_fetch_artifact`` / ``biomni_cost`` /
``biomni_tool_catalog`` / ``biomni_inject_mcp``) talk to the ASYNC
:class:`features.backend.BackendClient` protocol. This module is the seam: wrap a
concrete adapter and expose the async methods the tools call, mapping:

    capabilities()      -> per-backend token set (what the adapter can do today)
    list_results()      -> adapter.list_result_files() (unwrap the envelope)
    fetch_result_bytes()-> adapter.fetch_artifact()     (decode base64 or None)
    biomni_url()        -> adapter._biomni_url()/_run_page_url()
    add_mcp()           -> adapter.add_mcp() if present, else BackendUnsupported
    list_skills()       -> adapter.list_skills() if present, else []
    billing_balance()   -> adapter.billing_balance() if present, else {}

Capabilities are advertised HONESTLY: only what the concrete adapter can service
today. ``online`` can list results + surface a deep link; ``databricks`` can also
stream real result bytes. Neither adapter yet implements ``add_mcp`` /
``list_skills`` / ``billing_balance``, so those feature tools degrade gracefully
(exactly the documented ``NullBackend`` behaviour) until the methods land.
"""

from __future__ import annotations

import base64
from typing import Any

from .backend import (
    CAP_BIOMNI_URL,
    CAP_FETCH_BYTES,
    CAP_LIST_RESULTS,
    BackendUnsupported,
)

# Capability tokens each concrete backend can actually service today. Keyed by
# adapter ``name`` so a future third backend can register its own row.
_CAPS: dict[str, set[str]] = {
    "online": {CAP_LIST_RESULTS, CAP_BIOMNI_URL},
    "databricks": {CAP_LIST_RESULTS, CAP_FETCH_BYTES, CAP_BIOMNI_URL},
}


def _envelope_ok(env: Any) -> bool:
    ok = getattr(env, "ok", None)
    if ok is None and isinstance(env, dict):
        ok = env.get("ok")
    return bool(ok)


def _envelope_data(env: Any) -> dict[str, Any]:
    data = getattr(env, "data", None)
    if data is None and isinstance(env, dict):
        data = env.get("data")
    return data if isinstance(data, dict) else {}


class BiomniBackendClient:
    """Async ``BackendClient`` view over a sync ``BiomniBackend`` adapter."""

    def __init__(self, adapter: Any) -> None:
        self._a = adapter
        self.name: str = getattr(adapter, "name", "online")

    def capabilities(self) -> set[str]:
        return set(_CAPS.get(self.name, {CAP_LIST_RESULTS}))

    async def list_skills(self) -> list[dict[str, Any]]:
        fn = getattr(self._a, "list_skills", None)
        if fn is None:
            return []
        return list(fn())

    async def billing_balance(self) -> dict[str, Any]:
        fn = getattr(self._a, "billing_balance", None)
        return dict(fn()) if fn is not None else {}

    async def list_results(self, session_id: str) -> list[dict[str, Any]]:
        env = self._a.list_result_files(session_id)
        if not _envelope_ok(env):
            return []
        return list(_envelope_data(env).get("result_files", []))

    async def fetch_result_bytes(self, session_id: str, name: str) -> bytes | None:
        """Return real bytes if the adapter can stream them, else ``None``.

        The concrete adapters expose ``fetch_artifact`` returning a dict: the
        online backend returns a URL hint (no ``content_base64`` -> ``None``); the
        databricks backend returns real base64 bytes.
        """
        fn = getattr(self._a, "fetch_artifact", None)
        if fn is None:
            return None
        res = fn(session_id, name)
        data = res if isinstance(res, dict) else _envelope_data(res)
        b64 = data.get("content_base64") if isinstance(data, dict) else None
        if not b64:
            return None
        try:
            return base64.b64decode(b64)
        except (ValueError, TypeError):
            return None

    async def biomni_url(self, session_id: str) -> str | None:
        fn = getattr(self._a, "_biomni_url", None)
        if fn is not None:
            try:
                return fn(session_id)
            except Exception:  # noqa: BLE001 - best-effort deep link
                return None
        fn = getattr(self._a, "_run_page_url", None)
        if fn is not None:
            try:
                return fn()
            except Exception:  # noqa: BLE001
                return None
        return None

    async def add_mcp(self, spec: dict[str, Any]) -> dict[str, Any]:
        fn = getattr(self._a, "add_mcp", None)
        if fn is None:
            raise BackendUnsupported(
                f"backend {self.name!r} cannot inject MCPs (add_mcp not wired)"
            )
        return dict(fn(spec))


def bridge_adapter(adapter: Any) -> BiomniBackendClient:
    """Wrap a concrete ``BiomniBackend`` adapter as an async ``BackendClient``."""
    return BiomniBackendClient(adapter)
