#!/usr/bin/env python3
"""Probe 1: mechanical coverage + ablation minimum over the 58 protocol records.

Signal class: Python set algebra on protocols.json / templates.json.
Does not read the design-note argument.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402

OUT = HERE / "probe1-coverage.raw.json"


def main() -> int:
    census = C.load_json(C.PROTOCOLS)
    tmpl = C.load_json(C.TEMPLATES)
    report = C.coverage_report(census, tmpl)
    planted = C.coverage_report(C.mutant_unmapped_role(census), tmpl)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ok = (
        report["protocol_n"] == 58
        and report["unique_ids"] == 58
        and report["duplicate_ids"] == []
        and report["template_n"] == 11
        and report["covered"] is True
        and report["unmapped"] == []
        and report["unused_templates"] == []
        and report["minimum_holds"] is True
        and report["library_on_tree"] is False
        and planted["covered"] is False
        and planted["unmapped"] == ["wizard"]
        and report["family_counts"]
        == {
            "DELIBERATIVE": 6,
            "ADVERSARIAL": 7,
            "JUDICIAL": 6,
            "ANONYMOUS": 6,
            "GENERATIVE": 7,
            "FORECASTING": 5,
            "TRADECRAFT": 7,
            "ENGINEERING-REVIEW": 7,
            "META-COMPOSITION": 7,
        }
    )
    print(
        "protocol_n="
        + str(report["protocol_n"])
        + " unique_ids="
        + str(report["unique_ids"])
        + " template_n="
        + str(report["template_n"])
        + " named_role_n="
        + str(report["named_role_n"])
        + " unmapped="
        + json.dumps(report["unmapped"])
        + " unused="
        + json.dumps(report["unused_templates"])
        + " minimum_holds="
        + str(report["minimum_holds"])
        + " library_on_tree="
        + str(report["library_on_tree"])
        + " planted_wizard_unmapped="
        + json.dumps(planted["unmapped"])
        + " family_counts="
        + json.dumps(report["family_counts"], sort_keys=True)
    )
    if not ok:
        print("FAILED:CNL-0028-probe1 coverage")
        return 1
    print("SUCCESS:CNL-0028-probe1 mechanical coverage and ablation minimum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
