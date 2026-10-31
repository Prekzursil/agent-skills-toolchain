#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
from plugin.doctor.coverage import missing_mappings, validate_join  # noqa: E402
from plugin.doctor.io import load_mapping, load_taxonomy  # noqa: E402


def test_every_code_has_a_remediation() -> None:
    report = validate_join()
    assert report["complete"], report["missing"]
    assert not missing_mappings()


def test_negative_control_unmapped_goes_red() -> None:
    tax = load_taxonomy()
    tax = dict(tax)
    tax["codes"] = list(tax["codes"]) + [
        {"code": "PLUGIN.HEALTH.TEST_UNMAPPED", "category": "health", "severity": "error", "retryable": True}
    ]
    missing = missing_mappings(taxonomy=tax, mapping=load_mapping())
    assert "PLUGIN.HEALTH.TEST_UNMAPPED" in missing


def main() -> int:
    test_every_code_has_a_remediation()
    print("test_every_code_has_a_remediation ... ok")
    test_negative_control_unmapped_goes_red()
    print("test_negative_control_unmapped_goes_red ... ok")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
