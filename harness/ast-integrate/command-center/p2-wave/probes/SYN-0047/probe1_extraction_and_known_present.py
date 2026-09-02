#!/usr/bin/env python3
"""Probe 1: extraction count asserted; every class is a row; known-present COVERED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classes as C  # noqa: E402
import controls as CTL  # noqa: E402
import inventory as I  # noqa: E402
import mapper as M  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0047.failure-class-coverage.json"
SENTINEL = (
    "SUCCESS:SYN-0047 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the row count equals the "
    "extracted class count and the uncovered set is enumerated. Any other "
    "terminal state is FAILED:SYN-0047 <classification> with the diagnostic "
    "tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0047-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if SENTINEL not in text:
        return fail("completion_sentinel absent")
    doc = S.payload(raw)
    if doc.get("unit_id") != "SYN-0047":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    errs = S.error_list(raw)
    if errs:
        return fail(f"schema {errs[0]}")
    if str((raw.get("report") or {}).get("kind") or "") != "coverage-map":
        return fail("report.kind is not coverage-map")

    extracted = C.extract_classes(REPO)
    classes = extracted["classes"]
    if extracted["extracted_count"] != C.EXPECTED_COUNT:
        return fail(
            f"extracted {extracted['extracted_count']} != {C.EXPECTED_COUNT}"
        )
    art_rows = doc.get("rows") or []
    if len(art_rows) != extracted["extracted_count"]:
        return fail(
            f"artifact rows {len(art_rows)} != extracted {extracted['extracted_count']}"
        )
    live_ids = [c["id"] for c in classes]
    art_ids = [r.get("id") for r in art_rows]
    if art_ids != live_ids:
        missing = [i for i in live_ids if i not in art_ids]
        extra = [i for i in art_ids if i not in live_ids]
        return fail(f"row id set drift missing={missing[:5]} extra={extra[:5]}")

    inv = I.collect_inventory(REPO)
    live_rows = M.map_classes(classes, inv["tests"], inv["mutations"], inv["causes"])
    live_status = {r["id"]: r["status"] for r in live_rows}
    for row in art_rows:
        if live_status.get(row["id"]) != row.get("status"):
            return fail(
                f"status drift {row['id']} art={row.get('status')} live={live_status.get(row['id'])}"
            )

    uncovered_art = {u.get("id") for u in (doc.get("uncovered") or [])}
    uncovered_live = {r["id"] for r in M.uncovered_rows(live_rows)}
    if uncovered_art != uncovered_live:
        return fail("uncovered set drift versus live recompute")
    if len(uncovered_art) != int((doc.get("counts") or {}).get("uncovered") or -1):
        return fail("uncovered count denominator mismatch")

    known = CTL.assert_known_present()
    print(
        json.dumps(
            {
                "extracted": extracted["extracted_count"],
                "rows": len(art_rows),
                "source_status": extracted["source_status"],
                "known_present_status": known["status"],
                "uncovered": len(uncovered_art),
                "schema_ok": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:SYN-0047-probe1 extraction count asserted; every class is a row; "
        "known-present COVERED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
