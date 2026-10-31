#!/usr/bin/env python3
"""Named probe 1: three tamper classes detected on a copy of the real ledger.

Independent of probe 2 (no concurrent processes, no lock stress). Copies
command-center/bench/results/ledger.jsonl, verifies the clean copy
silently, then applies in-place edit, deleted row, and inserted row on
separate copies. Each class must be named by verify_ledger. Reports the
live row count and verification wall-clock.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.results_ledger import (  # noqa: E402
    LEDGER_REL,
    canonical,
    verify_ledger,
)

UNIT = "TST-0322"
ART = REPO / "command-center" / "receipts" / "TST-0322.json"
LEDGER = REPO / LEDGER_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def copy_ledger(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def tamper_in_place(src: Path, dest: Path, line_index: int = 2) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[line_index])
    payload = dict(event["payload"])
    value = payload.get("value")
    payload["value"] = (value + 1) if isinstance(value, int) else "TAMPERED"
    event["payload"] = payload
    lines[line_index] = canonical(event)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tamper_delete(src: Path, dest: Path, line_index: int = 2) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    del lines[line_index]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tamper_insert(src: Path, dest: Path, after_index: int = 1) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    duplicate = lines[after_index]
    lines.insert(after_index + 1, duplicate)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not LEDGER.is_file() or LEDGER.stat().st_size <= 0:
        return fail(f"real ledger missing {LEDGER_REL}")

    with tempfile.TemporaryDirectory(prefix="tst0322-p1-") as tmp:
        root = Path(tmp)
        clean = root / "clean.jsonl"
        copy_ledger(LEDGER, clean)
        clean_report = verify_ledger(clean, check_tip=False)
        if not clean_report.ok:
            return fail(f"clean copy not silent: {clean_report.findings}")
        if clean_report.events < 8:
            return fail(f"row_count={clean_report.events} too small to tamper a middle row")
        if clean_report.broken_tail:
            return fail("clean copy reported a torn tail")

        in_place = root / "in_place.jsonl"
        tamper_in_place(clean, in_place)
        ip = verify_ledger(in_place, check_tip=False)
        if ip.ok or not ip.has_class("in-place-edit"):
            return fail(f"in-place edit not detected classes={ip.classes} findings={ip.findings}")

        deleted = root / "deleted.jsonl"
        tamper_delete(clean, deleted)
        dl = verify_ledger(deleted, check_tip=False)
        if dl.ok or not dl.has_class("deleted-row"):
            return fail(f"deleted row not detected classes={dl.classes} findings={dl.findings}")

        inserted = root / "inserted.jsonl"
        tamper_insert(clean, inserted)
        ins = verify_ledger(inserted, check_tip=False)
        if ins.ok or not ins.has_class("inserted-row"):
            return fail(f"inserted row not detected classes={ins.classes} findings={ins.findings}")

        live = verify_ledger(LEDGER, check_tip=True)
        if not live.ok:
            return fail(f"real ledger does not verify: {live.findings}")

    if not ART.is_file():
        return fail(f"receipt missing {ART.relative_to(REPO)}")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    measured = (receipt.get("measured") or {}).get("real_ledger") or {}
    if measured.get("row_count") != live.events:
        return fail(
            f"receipt row_count={measured.get('row_count')} live={live.events}"
        )
    tamper = (receipt.get("measured") or {}).get("tamper") or {}
    for key, cls in (
        ("in_place_edit", "in-place-edit"),
        ("deleted_row", "deleted-row"),
        ("inserted_row", "inserted-row"),
    ):
        row = tamper.get(key) or {}
        if row.get("detected") is not True:
            return fail(f"receipt tamper.{key}.detected is not true")
        if cls not in (row.get("classes") or []):
            return fail(f"receipt tamper.{key} missing class {cls}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0322" not in text:
        return fail("receipt sentinel absent")

    out = {
        "pass": True,
        "probe": "probe1-tamper-classes",
        "unit_id": UNIT,
        "row_count": live.events,
        "verify_wall_clock_s": live.wall_clock_s,
        "clean_ok": clean_report.ok,
        "clean_findings": clean_report.findings,
        "in_place_classes": ip.classes,
        "deleted_classes": dl.classes,
        "inserted_classes": ins.classes,
        "all_three_detected": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"row_count={live.events} wall_clock_s={live.wall_clock_s:.6f} "
        f"clean_ok={clean_report.ok} "
        f"in_place={ip.classes} deleted={dl.classes} inserted={ins.classes}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 three tamper classes detected on a copy of "
        f"the real ledger; clean verifies silently"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
