"""Shared context object the hub injects into every feature tool."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .backend import DEFAULT_BACKEND, BackendRegistry, NullBackend
from .store import RunStore


@dataclass
class HubContext:
    """Everything the feature tools need, injected by the hub at register time.

    The hub constructs one of these, populates ``backends`` with real online /
    databricks adapters, and passes it to :func:`register_all`. When built via
    :func:`build_default_context` the registry holds only a ``NullBackend`` so
    this component imports/registers/self-tests standalone.
    """

    data_dir: str
    store: RunStore
    backends: BackendRegistry = field(default_factory=BackendRegistry)


def default_data_dir() -> str:
    """Resolve the hub data dir (``$BIOMNI_HUB_DATA_DIR`` or a per-user default)."""
    env = os.environ.get("BIOMNI_HUB_DATA_DIR")
    if env:
        return env
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "biomni-hub")


def build_default_context(data_dir: str | None = None) -> HubContext:
    """Build a self-contained context (NullBackend default). For tests/standalone."""
    ddir = data_dir or default_data_dir()
    store = RunStore(os.path.join(ddir, "biomni_hub.sqlite3"))
    registry = BackendRegistry(default=DEFAULT_BACKEND)
    registry.register(DEFAULT_BACKEND, NullBackend(DEFAULT_BACKEND))
    return HubContext(data_dir=ddir, store=store, backends=registry)
