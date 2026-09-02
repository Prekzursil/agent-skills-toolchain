#!/usr/bin/env python3
"""Probe 1: recipe control.

git cat-file -p and git show agree byte-for-byte; git archive differs by CRLF.
Classification must name cat-file, never archive.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import receipt_body, run_campaign  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0018.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0018-probe1 {msg}")
    return 1


def main() -> int:
    campaign = run_campaign()
    recipe = campaign["recipe"]
    if not recipe.get("passed"):
        return fail(f"recipe-control {recipe}")
    if recipe.get("cat_file_bytes") == recipe.get("archive_bytes"):
        return fail("archive-identical-to-blob trap-not-visible")
    if int(recipe.get("archive_crlf") or 0) < 1:
        return fail("archive-missing-crlf")
    if int(recipe.get("cat_file_crlf") or 0) != 0:
        return fail("cat-file-has-crlf")
    if recipe.get("used_for_classification") != "git cat-file -p":
        return fail("classification-recipe-not-cat-file")
    if "archive" in str(recipe.get("used_for_classification") or "").split():
        return fail("archive-used-for-classification")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rec_recipe = receipt_body(doc).get("recipe") or {}
    if rec_recipe.get("cat_file_equals_show") is not True:
        return fail("receipt-cat-file-equals-show")
    if rec_recipe.get("archive_differs_by_crlf") is not True:
        return fail("receipt-archive-differs")
    if rec_recipe.get("used_for_classification") != "git cat-file -p":
        return fail("receipt-used-recipe")
    if "git archive" in str(rec_recipe.get("used_for_classification") or ""):
        return fail("receipt-classified-via-archive")
    sentinel = str(doc.get("sentinel") or "")
    if "SUCCESS:SYN-0018" not in sentinel:
        return fail("sentinel-absent")

    summary = {
        "probe": "probe1-recipe",
        "unit_id": "SYN-0018",
        "cat_file_equals_show": True,
        "archive_differs_by_crlf": True,
        "cat_file_bytes": recipe["cat_file_bytes"],
        "archive_bytes": recipe["archive_bytes"],
        "archive_crlf": recipe["archive_crlf"],
        "used_for_classification": "git cat-file -p",
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"cat-file={recipe['cat_file_bytes']}B/0CRLF "
        f"show={recipe['show_bytes']}B/0CRLF "
        f"archive={recipe['archive_bytes']}B/{recipe['archive_crlf']}CRLF"
    )
    print("SUCCESS:SYN-0018-probe1 recipe control cat-file==show archive=CRLF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
