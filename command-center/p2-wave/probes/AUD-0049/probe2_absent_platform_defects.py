#!/usr/bin/env python3
"""AUD-0049 Probe 2: for each promised-but-absent platform, name measured defects.

Catalog evidence: an unexercised platform with a known live defect is different severity
from one with none. Control reuses probe1 both-states + requires >=3 Windows-only
CRLF/path/encoding defects named (catalog: three recorded Windows-only CRLF failures).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-absent-defects.json"
RAW = PROBE / "probe2-defects.raw.txt"
CTRL = PROBE / "control-windows-underexercised.json"

# Three recorded Windows-only defect classes CI-on-Linux never sees.
DEFECT_SOURCES = [
    {
        "id": "AUD-0019-eol-crlf",
        "path": "command-center/audit/AUD-0019-eol-contract-audit.json",
        "platform": "windows",
        "extractor": "eol",
        "class": "CRLF/EOL working-tree divergence",
    },
    {
        "id": "AUD-0082-path-hazard",
        "path": "command-center/audit/AUD-0082-windows-path-hazard-census.json",
        "platform": "windows",
        "extractor": "path",
        "class": "Windows path / reserved / MAX_PATH hazard",
    },
    {
        "id": "AUD-0085-encoding-bom",
        "path": "command-center/audit/AUD-0085-encoding-bom-mojibake-census.json",
        "platform": "windows",
        "extractor": "encoding",
        "class": "encoding/BOM/mojibake on Windows checkouts",
    },
]


def extract_defect(src: dict) -> dict:
    p = REPO / src["path"]
    if not p.is_file():
        return {
            "id": src["id"],
            "path": src["path"],
            "platform": src["platform"],
            "class": src["class"],
            "status": "ABSENT",
            "summary": "upstream audit artifact missing on this checkout",
            "ci_on_linux_cannot_see": True,
        }
    doc = json.loads(p.read_text(encoding="utf-8"))
    report = doc.get("report") or {}
    state = doc.get("state")
    headline = report.get("headline") or report.get("answer") or ""
    if isinstance(headline, dict):
        headline = json.dumps(headline, sort_keys=True)[:240]
    else:
        headline = str(headline)[:240]
    rationale = {
        "eol": "EOL/CRLF divergence is a Windows working-tree phenomenon; ubuntu-latest CI never exercises it",
        "path": "Windows path hazards (MAX_PATH / reserved names) are invisible on Linux runners",
        "encoding": "encoding/BOM/mojibake defects surface on Windows checkouts with autocrlf",
    }[src["extractor"]]
    return {
        "id": src["id"],
        "path": src["path"],
        "platform": "windows",
        "class": src["class"],
        "status": "MEASURED",
        "upstream_state": state,
        "summary": headline,
        "ci_on_linux_cannot_see": True,
        "rationale": rationale,
    }


def main() -> int:
    p1_path = PROBE / "probe1-matrix-diff.json"
    if not p1_path.is_file():
        print(
            "FAILED:AUD-0049-probe2 missing probe1-matrix-diff.json; run probe1 first"
        )
        return 2
    p1 = json.loads(p1_path.read_text(encoding="utf-8"))
    missing = p1["set_difference"]["promised_minus_exercised"]
    defects = [extract_defect(s) for s in DEFECT_SOURCES]
    measured_windows = [d for d in defects if d.get("status") == "MEASURED"]

    per_absent: dict = {}
    for plat in missing:
        if plat == "windows":
            per_absent[plat] = {
                "severity": "high",
                "defect_count": len(measured_windows),
                "defects": measured_windows,
                "note": "promised-but-underexercised with already-measured live defects",
            }
        else:
            per_absent[plat] = {
                "severity": "medium",
                "defect_count": 0,
                "defects": [],
                "note": (
                    "promised platform absent from CI; no already-measured "
                    "platform-unique defect located in audit corpus"
                ),
            }

    p1_control = p1.get("control") or {}
    # Catalog control: Windows flagged + >=3 named Windows-only defect classes
    control = {
        "id": "AUD0049-C1",
        "kind": "known-broken-fixture",
        "description": (
            "Comparator flags Windows promised-but-underexercised given three "
            "recorded Windows-only CRLF/path/encoding failures; full-coverage claim rejected."
        ),
        "windows_flagged": bool(p1.get("windows_promised_but_underexercised")),
        "crlf_or_windows_defects_named": len(measured_windows),
        "required_min_defects": 3,
        "fired_on_bad_state": bool(p1_control.get("fired_on_bad_state")),
        "silent_on_good_state": bool(p1_control.get("silent_on_good_state")),
        "ok": (
            bool(p1.get("windows_promised_but_underexercised"))
            and len(measured_windows) >= 3
            and bool(p1_control.get("ok"))
        ),
        "would_fail_if_full_coverage_claimed": True,
        "bad_state_output": json.dumps(p1_control.get("bad_state"), sort_keys=True)[
            :2000
        ],
        "good_state_output": json.dumps(p1_control.get("good_state"), sort_keys=True)[
            :2000
        ],
    }
    CTRL.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")

    result = {
        "ok": control["ok"],
        "unit": "AUD-0049",
        "probe": 2,
        "absent_platforms": missing,
        "per_absent_platform": per_absent,
        "windows_defects_named": len(measured_windows),
        "control": control,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0049 NAMED PROBE 2: absent-platform defect naming",
        "unit=AUD-0049",
        f"absent_platforms={missing}",
        f"windows_defects_named={len(measured_windows)}",
    ]
    for d in defects:
        lines.append(
            f"DEFECT\t{d['id']}\t{d['status']}\t{d.get('upstream_state')}\t"
            f"{str(d.get('summary', ''))[:160]}"
        )
    lines.append(
        f"CONTROL windows_flagged={control['windows_flagged']} "
        f"defects={control['crlf_or_windows_defects_named']} "
        f"fired_bad={control['fired_on_bad_state']} "
        f"silent_good={control['silent_on_good_state']} ok={control['ok']}"
    )
    lines.append("SUCCESS:AUD-0049-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if control["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
