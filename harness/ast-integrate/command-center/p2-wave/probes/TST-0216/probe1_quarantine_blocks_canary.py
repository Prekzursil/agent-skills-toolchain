#!/usr/bin/env python3
"""Probe 1: quarantine ON — canary marker absent; report enumerates every surface."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from checkout_quarantine.fixture import plant_clean_checkout, plant_hostile_checkout
from checkout_quarantine.gate import enter_untrusted_checkout
from checkout_quarantine.surfaces import CVE_2026_47751_CLASS

EXPECTED = {".claude", ".codex", ".mcp.json", "hooks"}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0216-p1-") as tmp:
        tmp_path = Path(tmp)
        hostile = tmp_path / "hostile"
        plant_hostile_checkout(hostile)
        marker = tmp_path / "hostile-marker.txt"
        on = enter_untrusted_checkout(hostile, quarantine=True, fire=True, marker=marker)
        enumerated = set(on.to_dict()["enumerated"])
        quarantined = set(on.to_dict()["quarantined"])
        originals_gone = not any(
            (hostile / rel).exists() for rel in EXPECTED
        )
        report = hostile / ".ast-quarantine" / "QUARANTINE-REPORT.json"
        if not report.is_file():
            report = hostile / ".ast-quarantine" / "QUARANTINE-REPORT.json"
        report_ok = report.is_file()
        codex = next(s for s in on.surfaces if s.relpath == ".codex")
        threat_ok = (codex.threat_class or "") == CVE_2026_47751_CLASS

        clean = tmp_path / "clean"
        plant_clean_checkout(clean)
        clean_marker = tmp_path / "clean-marker.txt"
        quiet = enter_untrusted_checkout(clean, quarantine=True, fire=True, marker=clean_marker)

        ok = (
            (not on.marker_written)
            and enumerated == EXPECTED
            and quarantined == EXPECTED
            and originals_gone
            and report_ok
            and threat_ok
            and quiet.to_dict()["enumerated"] == []
            and (not quiet.marker_written)
        )
        payload = {
            "probe": "probe1-quarantine-blocks-canary",
            "unit_id": "TST-0216",
            "quarantine_enabled": True,
            "enumerated": sorted(enumerated),
            "quarantined": sorted(quarantined),
            "marker_written": on.marker_written,
            "originals_gone": originals_gone,
            "report_exists": report_ok,
            "report_path": on.report_path,
            "threat_anchor": on.threat_anchor,
            "codex_threat_class": codex.threat_class,
            "clean_enumerated": quiet.to_dict()["enumerated"],
            "clean_marker_written": quiet.marker_written,
            "pass": ok,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not ok:
            print("FAILED:TST-0216-probe1 quarantine did not block canary or missed a surface")
            return 1
        print(
            "SUCCESS:TST-0216-probe1 quarantine ON: marker absent; "
            "report enumerated .claude .codex .mcp.json hooks; "
            f"threat_anchor={on.threat_anchor}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
