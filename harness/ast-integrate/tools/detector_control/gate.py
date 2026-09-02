"""CI gate for uncontrolled detectors (TST-0014).

A detector (validator rule, hook check, gate script) is *controlled* when the
registry (``tools/detector_control/registry.json``) names a known-present
fixture it must find, a known-broken fixture on which it must FIRE and a
known-good fixture on which it must stay SILENT, and those fixtures exist on
disk. ``run_gate`` runs the enumerator's own known-present control FIRST,
then enumerates the target tree, reports the raw census before applying the
threshold, and exits 1 when more detectors than ``threshold`` have no control.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from detector_control.controls import (
    CONTROLLED,
    FIXTURE_KEYS,
    REGISTRY_PATH,
    UNCONTROLLED,
    fixture_exists,
    load_registry_rows,
)
from detector_control.enumerate import (
    FIXTURES,
    Detector,
    enumerate_detectors,
    enumerator_control,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

REASON_ALL_CONTROLLED = "all-controlled"
REASON_WITHIN_THRESHOLD = "within-threshold"
REASON_UNCONTROLLED = "uncontrolled-detectors"
REASON_CENSUS_ONLY = "census-only"
REASON_CONTROL_MISSED = "enumerator-control-missed"
_FIXTURE_KEYS = FIXTURE_KEYS

__all__ = [
    "REGISTRY_PATH",
    "CONTROLLED",
    "UNCONTROLLED",
    "load_registry",
    "classify_detector",
    "known_present_gate",
    "run_gate",
]


def load_registry(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return registry rows keyed by detector id (empty when the file is absent)."""
    return load_registry_rows(path)


def _fixture_exists(rel: Any, repo: Path) -> bool:
    return fixture_exists(rel, repo)


def classify_detector(
    det: Detector, registry: dict[str, dict[str, Any]], repo: Path = REPO
) -> dict[str, Any]:
    """Inventory row: a detector is controlled only by an existing both-states fixture set."""
    row = registry.get(det.id)
    out: dict[str, Any] = {
        "id": det.id,
        "kind": det.kind,
        "path": det.path,
        "source": det.path,
        "known_present": None,
        "known_broken": None,
        "known_good": None,
        "known_present_exists": False,
        "known_broken_exists": False,
        "known_good_exists": False,
    }
    if row is None:
        out["verdict"] = UNCONTROLLED
        out["reason"] = "no-registry-row"
        return out
    missing: list[str] = []
    for key in _FIXTURE_KEYS:
        rel = row.get(key)
        out[key] = rel if isinstance(rel, str) else None
        exists = _fixture_exists(rel, repo)
        out[f"{key}_exists"] = exists
        if not exists:
            missing.append(key)
    if missing:
        out["verdict"] = UNCONTROLLED
        out["reason"] = "registry-row-missing-fixture:" + ",".join(missing)
    else:
        out["verdict"] = CONTROLLED
        out["reason"] = "registry-row-with-existing-fixtures"
    return out


def known_present_gate(root: Path | None = None) -> bool:
    """True when the enumerator finds every planted known-present detector."""
    return bool(enumerator_control()["fired"])


def run_gate(
    root: Path | str | None = None,
    skip_self_fixtures: bool = False,
    threshold: int = 0,
    census_only: bool = False,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Census the detectors under ``root`` and gate on the uncontrolled count.

    Order is fixed: (1) the enumerator's known-present control runs on the
    planted fixtures, (2) the tree is enumerated, (3) the raw census is
    reported, (4) the threshold is applied. ``census_only`` reports the census
    with exit 0 without gating.
    """
    threshold = max(0, int(threshold))
    repo = REPO
    target = Path(root) if root is not None else repo
    control = dict(enumerator_control())
    control["known_present_run_first"] = True
    control["fired_before_absence_reported"] = True
    if target != repo:
        control["root_scan"] = enumerator_control(target)
    registry = load_registry(registry_path)
    dets = enumerate_detectors(target, skip_self_fixtures=skip_self_fixtures)
    inventory = [classify_detector(d, registry, repo) for d in dets]
    controlled_ids = [r["id"] for r in inventory if r["verdict"] == CONTROLLED]
    uncontrolled_ids = [r["id"] for r in inventory if r["verdict"] == UNCONTROLLED]
    n_un = len(uncontrolled_ids)
    census = {
        "detector_count": len(inventory),
        "controlled_count": len(controlled_ids),
        "uncontrolled_count": n_un,
        "reported_before_threshold": True,
        "threshold": threshold,
    }
    if not control["fired"]:
        exit_code, reason = 1, REASON_CONTROL_MISSED
    elif census_only:
        exit_code, reason = 0, REASON_CENSUS_ONLY
    elif n_un == 0:
        exit_code, reason = 0, REASON_ALL_CONTROLLED
    elif n_un <= threshold:
        exit_code, reason = 0, REASON_WITHIN_THRESHOLD
    else:
        exit_code, reason = 1, REASON_UNCONTROLLED
    return {
        "root": str(target),
        "fixture_root": FIXTURES in target.parents or target == FIXTURES,
        "registry_path": str(registry_path or REGISTRY_PATH),
        "registry_rows": len(registry),
        "exit_code": exit_code,
        "reason": reason,
        "threshold": threshold,
        "census_only": bool(census_only),
        "detector_control": control,
        "census": census,
        "inventory": inventory,
        "controlled_ids": controlled_ids,
        "uncontrolled_ids": uncontrolled_ids,
    }


if __name__ == "__main__":
    import sys

    result = run_gate(root=sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({k: v for k, v in result.items() if k != "inventory"}, indent=1, sort_keys=True))
    raise SystemExit(result["exit_code"])
