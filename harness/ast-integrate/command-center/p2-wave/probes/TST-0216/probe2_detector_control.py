#!/usr/bin/env python3
"""Probe 2: quarantine OFF — same canary MUST write the marker (detector control)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from checkout_quarantine.fixture import plant_hostile_checkout
from checkout_quarantine.gate import enter_untrusted_checkout
from checkout_quarantine.surfaces import CVE_2026_47751_CLASS


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0216-p2-") as tmp:
        tmp_path = Path(tmp)
        root = tmp_path / "hostile"
        plant_hostile_checkout(root)
        marker = tmp_path / "marker.txt"
        off = enter_untrusted_checkout(root, quarantine=False, fire=True, marker=marker)
        body = marker.read_text(encoding="utf-8") if marker.is_file() else ""
        fired_tags = [ln.split(":", 1)[1] for ln in body.splitlines() if ln.startswith("FIRED:")]
        originals_remain = (root / ".codex").is_dir() and (root / ".claude").is_dir()
        marker_ok = off.marker_written and "FIRED:" in body
        # Detector is live: at least one auto-load surface executed the canary.
        ok = marker_ok and originals_remain and bool(off.fire)
        payload = {
            "probe": "probe2-detector-control-quarantine-off",
            "unit_id": "TST-0216",
            "quarantine_enabled": False,
            "marker_written": off.marker_written,
            "marker_body_lines": body.splitlines(),
            "fired_tags": fired_tags,
            "originals_remain": originals_remain,
            "fire_records": off.to_dict()["fire"],
            "enumerated": off.to_dict()["enumerated"],
            "threat_anchor": CVE_2026_47751_CLASS,
            "pass": ok,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not ok:
            print("FAILED:TST-0216-probe2 detector control: canary did not fire with quarantine off")
            return 1
        print(
            "SUCCESS:TST-0216-probe2 quarantine OFF: canary wrote marker "
            f"tags={fired_tags}; detector can see execution"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
