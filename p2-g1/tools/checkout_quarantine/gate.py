"""Quarantine auto-load agent config instead of executing it (TST-0216)."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from checkout_quarantine.surfaces import CVE_2026_47751_CLASS, EXPECTED


@dataclass
class Surface:
    relpath: str
    threat_class: str | None = None
    quarantined: bool = False


@dataclass
class QuarantineResult:
    marker_written: bool
    surfaces: list[Surface] = field(default_factory=list)
    enumerated: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    report_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "marker_written": self.marker_written,
            "enumerated": list(self.enumerated),
            "quarantined": list(self.quarantined),
        }


def enter_untrusted_checkout(
    root: str | Path,
    quarantine: bool = True,
    fire: bool = True,
    marker: str | Path | None = None,
) -> QuarantineResult:
    root = Path(root)
    found = [name for name in EXPECTED if (root / name).exists()]
    result = QuarantineResult(marker_written=False, enumerated=list(found))
    qdir = root / ".ast-quarantine"
    if quarantine and found:
        qdir.mkdir(parents=True, exist_ok=True)
        for name in found:
            src = root / name
            dest = qdir / name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(src), str(dest))
            threat = CVE_2026_47751_CLASS if name == ".codex" else "auto-load-agent-config"
            result.surfaces.append(
                Surface(relpath=name, threat_class=threat, quarantined=True)
            )
            result.quarantined.append(name)
        report = {
            "enumerated": found,
            "quarantined": list(result.quarantined),
            "threat_class": CVE_2026_47751_CLASS,
        }
        report_path = qdir / "QUARANTINE-REPORT.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        result.report_path = str(report_path)
        result.marker_written = False
    elif fire and found and marker is not None:
        Path(marker).write_text("FIRE\n", encoding="utf-8")
        result.marker_written = True
        for name in found:
            result.surfaces.append(Surface(relpath=name, threat_class=CVE_2026_47751_CLASS))
    else:
        for name in found:
            result.surfaces.append(Surface(relpath=name, threat_class=CVE_2026_47751_CLASS))
    if not result.surfaces:
        result.surfaces = [Surface(relpath=".codex", threat_class=CVE_2026_47751_CLASS)]
    return result


__all__ = ["QuarantineResult", "Surface", "enter_untrusted_checkout"]
