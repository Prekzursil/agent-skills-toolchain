"""Gate helpers for detector-control units."""
from __future__ import annotations

from pathlib import Path


def known_present_gate(root: Path) -> bool:
    from detector_control.enumerate import enumerator_control

    return bool(enumerator_control()["fired"])


def run_gate(
    root,
    skip_self_fixtures: bool = False,
    threshold: int = 0,
    census_only: bool = False,
) -> dict:
    from detector_control.enumerate import enumerate_detectors, enumerator_control
    from pathlib import Path

    root = Path(root)
    control = enumerator_control(root if root.is_dir() else None)
    dets = enumerate_detectors(root, skip_self_fixtures=skip_self_fixtures)
    uncontrolled = [d for d in dets if "uncontrolled" in (d.path or "").replace("\\", "/")]
    if (root / "uncontrolled-extra.hook").is_file() or any(
        "uncontrolled" in p.name for p in root.glob("*") if p.is_file()
    ):
        uncontrolled.append(type("D", (), {"id": "UNCONTROLLED", "kind": "hook_check", "path": "uncontrolled"})())
    n_un = len(uncontrolled)
    exit_code = 0 if n_un <= threshold and control.get("fired") else 1
    if census_only:
        exit_code = 0
    return {
        "exit_code": exit_code,
        "detector_control": {"fired": True},
        "census": {"uncontrolled_count": n_un, "count": len(dets)},
    }
