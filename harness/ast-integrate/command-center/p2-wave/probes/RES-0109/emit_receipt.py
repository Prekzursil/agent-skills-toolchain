#!/usr/bin/env python3
"""Emit command-center/research/RES-0109.json from captured LICENSE files."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import salvage as S  # noqa: E402


def main() -> int:
    doc = S.emit()
    extract = [
        r["row_id"]
        for r in doc.get("salvage_register") or []
        if r.get("disposition") == "EXTRACT"
    ]
    print(f"wrote {S.OUT_REL}")
    print(
        "extract="
        + ",".join(extract)
        + " disagreements="
        + str(doc.get("license_label_vs_file_disagreement_count"))
        + " quoted="
        + str(doc.get("quoted_license_row_count"))
    )
    print("SUCCESS:RES-0109 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
