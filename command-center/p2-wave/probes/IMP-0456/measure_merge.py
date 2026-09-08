#!/usr/bin/env python3
"""IMP-0456: measure live catalog-slice merge contiguity + write merge report.

Honest measure: live tree is known short (2007 vs floor 2048) with IMP index
gaps — contiguous gate must refuse. Does not invent SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog_slice_merge as m  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
OUT = PROBE_DIR / "merge-report.json"
SUMMARY = PROBE_DIR / "measure.out"


def main() -> int:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = m.build_merge_report(
        m.DEFAULT_SLICES,
        catalog_path=m.DEFAULT_CATALOG,
        require_field_complete=True,
    )
    report["measured_at"] = ended
    report["dep_IMP_0436"] = _dep_state()

    refused = None
    try:
        m.assert_merge_contiguous(
            m.DEFAULT_SLICES, require_field_complete=True
        )
        refused = False
    except (m.CollisionError, m.ContiguityError, m.FieldCompletenessError) as exc:
        refused = True
        report["assert_merge_contiguous_error"] = (
            f"{type(exc).__name__}: {exc}"
        )[:4000]

    report["assert_merge_contiguous_refused"] = refused

    OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    lines = [
        f"IMP-0456 measure at {ended}",
        f"unique_ids={report['contiguity']['unique_id_count']}",
        f"declared={report['contiguity']['declared_program_count']}",
        f"gaps={report['contiguity']['total_gap_count']}",
        f"dups={report['inventory']['duplicate_count']}",
        f"merge_allowed={report['merge_allowed']}",
        f"block_reasons={report['block_reasons']}",
        f"exact_question_answer={report['exact_question']['answer']}",
        f"assert_refused={refused}",
        f"wrote={OUT.relative_to(REPO)}",
        "SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS withheld pending independent recount",
    ]
    text = "\n".join(lines) + "\n"
    SUMMARY.write_text(text, encoding="utf-8")
    print(text, end="")

    # Measure succeeds as a probe when the report is honest. Live refusal is
    # expected and is NOT a measure-script failure.
    if report["exact_question"]["answer"] and not refused:
        print("NOTE: live contiguous gate green — unexpected on current shortfall tip")
    elif not refused:
        print("FAILED:measure expected live assert_merge_contiguous to refuse", file=sys.stderr)
        return 1
    return 0


def _dep_state() -> dict:
    path = REPO / "command-center" / "receipts" / "IMP-0436.json"
    if not path.is_file():
        return {"exists": False, "state": None}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"exists": True, "state": None, "error": str(exc)}
    return {
        "exists": True,
        "state": doc.get("state"),
        "sentinel": doc.get("sentinel"),
        "path": "command-center/receipts/IMP-0436.json",
    }


if __name__ == "__main__":
    raise SystemExit(main())
