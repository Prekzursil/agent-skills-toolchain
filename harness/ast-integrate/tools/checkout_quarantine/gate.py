"""Quarantine auto-load agent config in an untrusted checkout instead of executing it.

``enter_untrusted_checkout`` is the single entry point an agent calls before it
touches a freshly cloned repository. With ``quarantine=True`` every auto-load
surface (:data:`EXPECTED`) is moved out of the way into ``.ast-quarantine/`` and a
``QUARANTINE-REPORT.json`` enumerates what was found; nothing is loaded, so a
canary planted in any surface can never write its marker. With
``quarantine=False`` the auto-load step runs and each surface that would have been
executed appends ``FIRED:<surface>`` to ``marker`` -- the detector control that
proves a probe can observe execution when the gate is off.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from checkout_quarantine.surfaces import (
    AUTOLOAD_ACTION,
    CVE_2026_47751_CLASS,
    EXPECTED,
    threat_class_for,
)

QUARANTINE_DIR = ".ast-quarantine"
REPORT_NAME = "QUARANTINE-REPORT.json"


@dataclass
class Surface:
    relpath: str
    kind: str = "missing"
    threat_class: str | None = None
    quarantined: bool = False
    quarantine_path: str | None = None
    fired: bool = False
    autoload_action: str = ""


@dataclass
class QuarantineResult:
    root: str
    quarantine: bool
    fire: bool
    marker: str | None
    marker_written: bool = False
    threat_anchor: str = CVE_2026_47751_CLASS
    surfaces: list[Surface] = field(default_factory=list)
    enumerated: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    fire_records: list[dict] = field(default_factory=list)
    report_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "quarantine": self.quarantine,
            "fire": list(self.fire_records),
            "fire_enabled": self.fire,
            "marker": self.marker,
            "marker_written": self.marker_written,
            "threat_anchor": self.threat_anchor,
            "enumerated": list(self.enumerated),
            "quarantined": list(self.quarantined),
            "surfaces": [asdict(s) for s in self.surfaces],
            "report_path": self.report_path,
        }


def enumerate_surfaces(root: str | Path) -> list[Surface]:
    """Every auto-load surface present under ``root``, in :data:`EXPECTED` order."""
    root = Path(root)
    found: list[Surface] = []
    for name in EXPECTED:
        path = root / name
        if not path.exists():
            continue
        found.append(
            Surface(
                relpath=name,
                kind="dir" if path.is_dir() else "file",
                threat_class=threat_class_for(name),
                autoload_action=AUTOLOAD_ACTION.get(name, ""),
            )
        )
    return found


def _quarantine(root: Path, surfaces: list[Surface]) -> Path:
    qdir = root / QUARANTINE_DIR
    qdir.mkdir(parents=True, exist_ok=True)
    for surface in surfaces:
        src = root / surface.relpath
        dest = qdir / surface.relpath
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        elif dest.exists() or dest.is_symlink():
            dest.unlink()
        shutil.move(str(src), str(dest))
        surface.quarantined = True
        surface.quarantine_path = str(dest)
    return qdir


def _autoload(surfaces: list[Surface], marker: Path | None) -> list[dict]:
    """The unguarded path: every surface is 'loaded' and the canary records it."""
    records: list[dict] = []
    lines: list[str] = []
    for surface in surfaces:
        surface.fired = True
        lines.append(f"FIRED:{surface.relpath}")
        records.append(
            {
                "surface": surface.relpath,
                "tag": surface.relpath,
                "threat_class": surface.threat_class,
                "action": surface.autoload_action,
                "marker": None if marker is None else str(marker),
            }
        )
    if marker is not None and lines:
        marker.parent.mkdir(parents=True, exist_ok=True)
        with marker.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
    return records


def enter_untrusted_checkout(
    root: str | Path,
    quarantine: bool = True,
    fire: bool = True,
    marker: str | Path | None = None,
) -> QuarantineResult:
    """Enter ``root``; quarantine its auto-load surfaces or (gate off) auto-load them."""
    root = Path(root)
    marker_path = None if marker is None else Path(marker)
    surfaces = enumerate_surfaces(root)
    result = QuarantineResult(
        root=str(root),
        quarantine=quarantine,
        fire=fire,
        marker=None if marker_path is None else str(marker_path),
        surfaces=surfaces,
        enumerated=[s.relpath for s in surfaces],
    )
    if quarantine:
        if surfaces:
            qdir = _quarantine(root, surfaces)
            result.quarantined = [s.relpath for s in surfaces]
            report = {
                "root": str(root),
                "threat_anchor": result.threat_anchor,
                "enumerated": list(result.enumerated),
                "quarantined": list(result.quarantined),
                "surfaces": [asdict(s) for s in surfaces],
                "executed": [],
                "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            report_path = qdir / REPORT_NAME
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result.report_path = str(report_path)
        return result
    if fire and surfaces:
        result.fire_records = _autoload(surfaces, marker_path)
        result.marker_written = marker_path is not None and marker_path.is_file()
    return result


__all__ = [
    "QUARANTINE_DIR",
    "QuarantineResult",
    "REPORT_NAME",
    "Surface",
    "enter_untrusted_checkout",
    "enumerate_surfaces",
]
