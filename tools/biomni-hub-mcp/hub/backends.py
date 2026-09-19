#!/usr/bin/env python3
"""biomni-hub — backend selector + the adapter INTERFACE both backends implement.

This module owns the *out-of-band* backend selection and lazy adapter loading.
It defines ``BiomniBackend`` (the abstract interface the online adapter and the
Databricks adapter each implement) but implements NEITHER — those live in
``online_adapter.py`` (component A2) and ``databricks_adapter.py`` (component
B1). See ``INTERFACE.md`` for the contract A2 and B1 build to.

Selection rules (fail-closed to online)
----------------------------------------
``select_backend_name(backend_arg, env)`` resolves the target backend name:

1. A valid per-call ``backend_arg`` wins.
2. Otherwise a valid ``BIOMNI_BACKEND`` env value.
3. Otherwise the default (``online``).

Anything invalid, blank, or unknown at any step FAILS CLOSED to ``online`` —
selection never raises and never lands on an unrecognized backend. (Adapter
*loading* is a separate concern: if a selected adapter cannot be imported, the
caller gets a clear ``AdapterUnavailable`` error rather than a silent swap to a
different compute backend.)
"""

from __future__ import annotations

import abc
import importlib
import os
from collections.abc import Mapping

from schema import (
    DEFAULT_BACKEND,
    Backend,
    BackendDescriptor,
    ResultFile,  # re-exported for adapters' convenience  # noqa: F401
    ToolEnvelope,
)

#: Env var that sets the process-wide default backend.
BACKEND_ENV_VAR = "BIOMNI_BACKEND"

#: Candidate (module, factory) pairs per backend, tried in order until one both
#: imports AND returns a conforming ``BiomniBackend``. Supporting more than one
#: naming convention keeps module/function names from being load-bearing across
#: the parallel A2/B1 builds: the canonical form is ``online_adapter.get_backend``
#: / ``databricks_adapter.get_backend`` (see INTERFACE.md), but the ``adapters``
#: package layout (``adapters.online.build_adapter``) is accepted too. The
#: conformance check in ``load_backend`` still enforces the ``BiomniBackend``
#: contract, so a non-conforming adapter fails loudly rather than loading.
_ADAPTER_SPECS: dict[str, tuple[tuple[str, str], ...]] = {
    Backend.ONLINE.value: (
        ("online_adapter", "get_backend"),
        ("adapters.online", "get_backend"),
        ("adapters.online", "build_adapter"),
    ),
    Backend.DATABRICKS.value: (
        ("databricks_adapter", "get_backend"),
        ("adapters.databricks", "get_backend"),
        ("adapters.databricks", "build_adapter"),
    ),
}

_VALID = frozenset(b.value for b in Backend)


class AdapterUnavailable(RuntimeError):
    """Raised when a selected backend's adapter cannot be imported or built."""


# --------------------------------------------------------------------------- #
# Selection (pure — no imports, no I/O, deterministic, fail-closed)
# --------------------------------------------------------------------------- #
def select_backend_name(
    backend_arg: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve the target backend name, failing closed to ``online``.

    ``backend_arg`` is the optional per-call override; ``env`` defaults to
    ``os.environ`` and supplies ``BIOMNI_BACKEND``. Case/whitespace-insensitive.
    """
    if env is None:
        env = os.environ

    arg = (backend_arg or "").strip().lower()
    if arg in _VALID:
        return arg

    env_val = (env.get(BACKEND_ENV_VAR) or "").strip().lower()
    if env_val in _VALID:
        return env_val

    return DEFAULT_BACKEND


# --------------------------------------------------------------------------- #
# The adapter interface (A2 + B1 implement this; A1 does NOT)
# --------------------------------------------------------------------------- #
class BiomniBackend(abc.ABC):
    """The interface every backend adapter implements.

    Ten methods mirror the ten canonical tools one-to-one, plus ``describe()``
    for the catalog. Every method returns a :class:`ToolEnvelope` — adapters
    never raise for handled errors (bad ids, auth expiry, empty results); they
    return ``ToolEnvelope.failure(...)``. Unhandled/programmer errors may raise
    and are wrapped by the server into an error envelope.

    Methods are synchronous to match the ``bm_*`` REST client (online) and the
    Databricks Jobs/Context API (databricks); the async *task* model is
    expressed through ``start_new_task`` / ``wait_for_next_update``, not through
    Python async.
    """

    #: Backend name — one of ``Backend`` values. Set by each adapter.
    name: str

    @abc.abstractmethod
    def describe(self) -> BackendDescriptor:
        """Report availability / status / cost for the ``biomni_backends`` catalog."""

    @abc.abstractmethod
    def create_project(self, name: str, description: str = "") -> ToolEnvelope: ...

    @abc.abstractmethod
    def list_projects(self) -> ToolEnvelope: ...

    @abc.abstractmethod
    def list_workspaces(self) -> ToolEnvelope: ...

    @abc.abstractmethod
    def switch_workspace(self, workspace_id: str) -> ToolEnvelope: ...

    @abc.abstractmethod
    def upload_file(
        self, local_path: str, project_id: str = "", destination: str = ""
    ) -> ToolEnvelope: ...

    @abc.abstractmethod
    def start_new_task(
        self, project_id: str, prompt: str, model_profile: str = "standard"
    ) -> ToolEnvelope: ...

    @abc.abstractmethod
    def send_message(self, task_id: str, content: str) -> ToolEnvelope: ...

    @abc.abstractmethod
    def wait_for_next_update(
        self, task_id: str, timeout_seconds: float = 60.0, *, since: int | None = None
    ) -> ToolEnvelope: ...

    @abc.abstractmethod
    def list_tasks(self, project_id: str = "") -> ToolEnvelope: ...

    @abc.abstractmethod
    def list_result_files(self, task_id: str = "") -> ToolEnvelope: ...


# --------------------------------------------------------------------------- #
# Lazy adapter loading (cached per process)
# --------------------------------------------------------------------------- #
_CACHE: dict[str, BiomniBackend] = {}


def register_backend(name: str, backend: BiomniBackend) -> None:
    """Inject a pre-built backend for ``name`` (used by tests and embedders)."""
    _CACHE[name] = backend


def reset_cache() -> None:
    """Clear the adapter cache (used by tests)."""
    _CACHE.clear()


def load_backend(name: str) -> BiomniBackend:
    """Import + build the adapter for ``name`` (cached). Raises AdapterUnavailable.

    ``name`` is assumed already normalized by :func:`select_backend_name`.
    """
    if name in _CACHE:
        return _CACHE[name]

    candidates = _ADAPTER_SPECS.get(name)
    if not candidates:  # pragma: no cover - guarded by select_backend_name upstream
        raise AdapterUnavailable(f"no adapter registered for backend {name!r}")

    errors: list[str] = []
    for module_name, factory_name in candidates:
        try:
            module = importlib.import_module(module_name)
            factory = getattr(module, factory_name)
            backend = factory()
        except Exception as exc:  # noqa: BLE001 - collected, reported if all fail
            errors.append(f"{module_name}.{factory_name}: {type(exc).__name__}: {exc}")
            continue

        if not isinstance(backend, BiomniBackend):
            errors.append(
                f"{module_name}.{factory_name}: did not return a BiomniBackend "
                f"(got {type(backend).__name__})"
            )
            continue

        backend.name = name
        _CACHE[name] = backend
        return backend

    raise AdapterUnavailable(
        f"backend {name!r} adapter unavailable; tried: " + " | ".join(errors)
    )


def resolve_backend(
    backend_arg: str | None = None,
    env: Mapping[str, str] | None = None,
) -> BiomniBackend:
    """Select + load the backend for a call. Raises AdapterUnavailable on load fail.

    Selection fails closed to ``online``; a *load* failure is surfaced (never a
    silent swap to a different compute backend).
    """
    return load_backend(select_backend_name(backend_arg, env))
