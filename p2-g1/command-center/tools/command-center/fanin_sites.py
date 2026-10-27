"""Seven spec-named fan-in wrappers around the shared completion predicate.

Each site is a thin import of ``completion_predicate.judge``. A site-local
threshold override is the only permitted fork, and it exists so IMP-0418's
planted-divergence control can patch one caller without rewriting the reducer.
"""

from __future__ import annotations

from typing import Any, Mapping

from completion_predicate import DEFAULT_MIN_BYTES, judge

SITE_IDS: tuple[str, ...] = (
    "local_runner",
    "cloud_dispatcher",
    "monitor",
    "harvester",
    "workflow_fanin",
    "cross_vendor_adapter",
    "final_synthesis",
)


def canonical_verdict_bytes(result: Mapping[str, Any]) -> bytes:
    """Byte-identity of a verdict ignores site decoration and timestamps."""
    import json

    payload = {
        "complete": bool(result.get("complete")),
        "failing": list(result.get("failing") or []),
        "verdict": result.get("verdict"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def check_unit(
    site_id: str,
    record: Mapping[str, Any],
    min_bytes: int | None = None,
) -> dict[str, Any]:
    if site_id not in SITE_IDS:
        raise KeyError(f"unknown fan-in site {site_id!r}")
    floor = DEFAULT_MIN_BYTES if min_bytes is None else int(min_bytes)
    out = judge(record, min_bytes=floor)
    out["site"] = site_id
    return out


def local_runner(
    record: Mapping[str, Any], min_bytes: int | None = None
) -> dict[str, Any]:
    return check_unit("local_runner", record, min_bytes=min_bytes)


def cloud_dispatcher(
    record: Mapping[str, Any], min_bytes: int | None = None
) -> dict[str, Any]:
    return check_unit("cloud_dispatcher", record, min_bytes=min_bytes)


def monitor(record: Mapping[str, Any], min_bytes: int | None = None) -> dict[str, Any]:
    return check_unit("monitor", record, min_bytes=min_bytes)


def harvester(
    record: Mapping[str, Any], min_bytes: int | None = None
) -> dict[str, Any]:
    return check_unit("harvester", record, min_bytes=min_bytes)


def workflow_fanin(
    record: Mapping[str, Any], min_bytes: int | None = None
) -> dict[str, Any]:
    return check_unit("workflow_fanin", record, min_bytes=min_bytes)


def cross_vendor_adapter(
    record: Mapping[str, Any], min_bytes: int | None = None
) -> dict[str, Any]:
    return check_unit("cross_vendor_adapter", record, min_bytes=min_bytes)


def final_synthesis(
    record: Mapping[str, Any], min_bytes: int | None = None
) -> dict[str, Any]:
    return check_unit("final_synthesis", record, min_bytes=min_bytes)


SITE_FUNCS = {
    "local_runner": local_runner,
    "cloud_dispatcher": cloud_dispatcher,
    "monitor": monitor,
    "harvester": harvester,
    "workflow_fanin": workflow_fanin,
    "cross_vendor_adapter": cross_vendor_adapter,
    "final_synthesis": final_synthesis,
}
