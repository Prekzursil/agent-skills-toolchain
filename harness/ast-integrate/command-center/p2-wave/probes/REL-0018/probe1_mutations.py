#!/usr/bin/env python3
"""Probe 1: remove-evidence → NOT-CHECKED/NO-GO; wrong schema must not count as TRUE."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluator import evaluate  # noqa: E402
from fixtures import (  # noqa: E402
    passing_wrong_schema,
    write_green_tree,
)

STOP4 = "command-center/receipts/stopping/SC-04.json"
STOP8 = "command-center/receipts/stopping/SC-08.json"


def _fail(msg: str) -> int:
    print(f"FAILED:REL-0018-probe1 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="rel0018-p1-"))
    try:
        green = tmp / "green"
        write_green_tree(green)
        g = evaluate(green)
        if g["decision"] != "GO" or g["counts"]["TRUE"] != 21:
            return _fail(f"green-fixture not GO: {g['decision']} {g['counts']}")

        missing = tmp / "missing-sc04"
        shutil.copytree(green, missing)
        (missing / STOP4).unlink()
        m = evaluate(missing)
        row4 = next(r for r in m["conditions"] if r["id"] == 4)
        if row4["verdict"] != "NOT-CHECKED":
            return _fail(f"removed SC-04 verdict={row4['verdict']} want NOT-CHECKED")
        if m["decision"] != "NO-GO":
            return _fail("removed evidence still GO")
        if m["counts"]["NOT-CHECKED"] < 1:
            return _fail("NOT-CHECKED count did not rise")

        wrong = tmp / "wrong-schema"
        shutil.copytree(green, wrong)
        (wrong / STOP8).write_text(
            __import__("json").dumps(passing_wrong_schema(8), indent=2) + "\n",
            encoding="utf-8",
        )
        w = evaluate(wrong)
        row8 = next(r for r in w["conditions"] if r["id"] == 8)
        if row8["verdict"] == "TRUE":
            return _fail("wrong-schema file counted as TRUE")
        if row8["schema_ok"] is True:
            return _fail("wrong-schema marked schema_ok")
        if "schema-invalid" not in row8["reason"]:
            return _fail(f"wrong-schema reason={row8['reason']}")
        if w["decision"] != "NO-GO":
            return _fail("wrong-schema still GO")

        print(
            "green_go=True missing_not_checked=True missing_nogo=True "
            f"wrong_schema_verdict={row8['verdict']} wrong_schema_nogo=True"
        )
        print("SUCCESS:REL-0018-probe1 remove-evidence and wrong-schema")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
