#!/usr/bin/env python3
"""Named probe 1: python -m pytest from the source tree (good + include-omit)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402


def main() -> int:
    art = S.REPO / S.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:AUD-0043-probe1 artifact missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not SL.shim_path().is_file():
        print("FAILED:AUD-0043-probe1 catalog schema missing")
        return 1
    if not SL.rejects_garbage():
        print("FAILED:AUD-0043-probe1 local contract accepted garbage")
        return 1
    errors = SL.iter_errors(doc)
    if errors:
        print("FAILED:AUD-0043-probe1 local-contract", errors[0])
        return 1
    if S.SENTINEL not in text:
        print("FAILED:AUD-0043-probe1 catalog sentinel absent")
        return 1
    if doc.get("unit_id") != S.UNIT:
        print("FAILED:AUD-0043-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:AUD-0043-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="aud0043-p1-") as tmp:
        root = Path(tmp)
        good_src = H.copy_pkg(root / "src-good", mutant=False)
        mutant_src = H.copy_pkg(root / "src-mutant", mutant=True)
        py = H.pytest_python_for(root)
        source_good = H.run_source_pytest(good_src, py)
        source_mutant = H.run_source_pytest(mutant_src, py)

    if not source_good["ok"]:
        print("FAILED:AUD-0043-probe1 source pytest on good package failed")
        print(json.dumps(source_good, indent=2)[:2000])
        return 1
    if (source_good.get("collected") or 0) <= 0:
        print("FAILED:AUD-0043-probe1 collected count is zero")
        return 1
    if not source_mutant["ok"]:
        print("FAILED:AUD-0043-probe1 source pytest on include-omit mutant failed")
        print(json.dumps(source_mutant, indent=2)[:2000])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-source-pytest",
                "unit_id": S.UNIT,
                "pass": True,
                "good_ok": source_good["ok"],
                "good_collected": source_good["collected"],
                "good_passed": source_good["passed"],
                "good_returncode": source_good["returncode"],
                "mutant_ok": source_mutant["ok"],
                "mutant_collected": source_mutant["collected"],
                "mutant_passed": source_mutant["passed"],
                "command": source_good["command"],
            },
            sort_keys=True,
        )
    )
    print(
        f"source_good collected={source_good['collected']} "
        f"passed={source_good['passed']} mutant_still_green=True"
    )
    print("SUCCESS:AUD-0043-probe1 source-tree python -m pytest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
