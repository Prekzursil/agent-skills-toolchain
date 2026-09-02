"""Seven named consumers of the shared reducer.

Each judge is a distinct call-site wrapper. All seven bind the SAME
evaluate object (reducer.evaluate). A site that agreed on today's corpus
but held a local copy would fail the identity check in probe1.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from reducer import evaluate as _SHARED_EVALUATE

SITE_IDS = (
    "local_runner",
    "cloud_dispatcher",
    "monitor",
    "harvester",
    "workflow_fan_in",
    "cross_vendor_adapter",
    "final_synthesis",
)

Judge = Callable[..., dict[str, Any]]


def _bind(site_id: str) -> Judge:
    def judge(receipt: dict[str, Any], skip: Iterable[int] | None = None) -> dict[str, Any]:
        return _SHARED_EVALUATE(receipt, skip=skip)

    judge.site_id = site_id  # type: ignore[attr-defined]
    judge.reducer = _SHARED_EVALUATE  # type: ignore[attr-defined]
    return judge


local_runner = _bind("local_runner")
cloud_dispatcher = _bind("cloud_dispatcher")
monitor = _bind("monitor")
harvester = _bind("harvester")
workflow_fan_in = _bind("workflow_fan_in")
cross_vendor_adapter = _bind("cross_vendor_adapter")
final_synthesis = _bind("final_synthesis")

JUDGES: dict[str, Judge] = {
    "local_runner": local_runner,
    "cloud_dispatcher": cloud_dispatcher,
    "monitor": monitor,
    "harvester": harvester,
    "workflow_fan_in": workflow_fan_in,
    "cross_vendor_adapter": cross_vendor_adapter,
    "final_synthesis": final_synthesis,
}


def identity_ok() -> bool:
    return all(fn.reducer is _SHARED_EVALUATE for fn in JUDGES.values()) and len(JUDGES) == 7
