"""Completion sites sharing one judge object."""
from __future__ import annotations

from typing import Any

from completion import reducer

from . import (
    cloud_dispatcher,
    cross_vendor_adapter,
    final_synthesis,
    harvester,
    local_runner,
    monitor,
    workflow_fanin,
)

SITE_FILES: dict[str, str] = {
    "reducer": "tools/completion/reducer.py",
    "harvester": "tools/completion/sites/harvester.py",
    "cross_vendor_adapter": "tools/completion/sites/cross_vendor_adapter.py",
    "local_runner": "tools/completion/sites/local_runner.py",
    "monitor": "tools/completion/sites/monitor.py",
    "workflow_fanin": "tools/completion/sites/workflow_fanin.py",
    "final_synthesis": "tools/completion/sites/final_synthesis.py",
    "cloud_dispatcher": "tools/completion/sites/cloud_dispatcher.py",
}

SITE_IDS: tuple[str, ...] = (
    "harvester",
    "cross_vendor_adapter",
    "local_runner",
    "monitor",
    "workflow_fanin",
    "final_synthesis",
    "cloud_dispatcher",
)

_MODULES = {
    "reducer": reducer,
    "harvester": harvester,
    "cross_vendor_adapter": cross_vendor_adapter,
    "local_runner": local_runner,
    "monitor": monitor,
    "workflow_fanin": workflow_fanin,
    "final_synthesis": final_synthesis,
    "cloud_dispatcher": cloud_dispatcher,
}


class SiteAdapter:
    """Thin handle over one site module.

    ``judge`` is bound to the very object the site module imported from
    ``completion.reducer`` (no wrapper, no copy), so an identity audit that
    asks the adapter for its judge sees the same object the site calls.
    Any other attribute falls through to the underlying module.
    """

    def __init__(self, site_id: str, module: Any) -> None:
        self.site_id = site_id
        self.module = module
        self.judge = getattr(module, "judge", None)

    def check_unit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.module.check_unit(payload)

    def __getattr__(self, name: str) -> Any:
        # Only reached when normal lookup fails; delegate to the site module
        # so callers can treat the adapter as the module it stands for.
        module = self.__dict__.get("module")
        if module is None or name.startswith("__"):
            raise AttributeError(name)
        return getattr(module, name)


def load_site(site_id: str) -> SiteAdapter:
    if site_id not in _MODULES:
        raise KeyError(site_id)
    return SiteAdapter(site_id, _MODULES[site_id])


def load_all() -> dict[str, Any]:
    return dict(_MODULES)
