#!/usr/bin/env python3
"""IMP-0009 negative control: clean passes while planted fails in the same run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402

PROBE = Path(__file__).resolve().parent


def main() -> int:
    live_raw = (REPO / M.MANIFEST_RELPATH).read_text(encoding="utf-8")

    clean_ok = True
    try:
        M.parse_manifest_text(live_raw)
        M.assert_path_free_of_key_collisions(REPO / M.MANIFEST_RELPATH)
        M.assert_path_free_of_key_collisions(REPO / M.DISPATCH_MANIFEST_RELPATH)
    except M.ManifestSchemaError:
        clean_ok = False

    case_planted = M.mutate_case_collision_text(live_raw)
    case_failed = False
    case_code = None
    try:
        M.parse_manifest_text(case_planted)
    except M.ManifestSchemaError as exc:
        case_failed = True
        case_code = exc.code

    dup_planted = M.mutate_duplicate_key_text(live_raw)
    dup_failed = False
    dup_code = None
    try:
        M.parse_manifest_text(dup_planted)
    except M.ManifestSchemaError as exc:
        dup_failed = True
        dup_code = exc.code

    fired = bool(
        clean_ok
        and case_failed
        and case_code == M.ERR_CASE_COLLISION
        and dup_failed
        and dup_code == M.ERR_DUPLICATE_KEY
    )

    meas = {
        "negative_control_fired": fired,
        "ok": fired,
        "silent_on_good": clean_ok,
        "case_planted_failed": case_failed,
        "case_code": case_code,
        "dup_planted_failed": dup_failed,
        "dup_code": dup_code,
        "same_run": True,
    }
    (PROBE / "negative-control-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NEGATIVE CONTROL: CLEAN PASSES / PLANTED FAILS (SAME RUN)",
        "NEG-BEGIN:IMP-0009",
        f"silent_on_good={clean_ok}",
        f"case_planted_failed={case_failed}",
        f"case_code={case_code}",
        f"dup_planted_failed={dup_failed}",
        f"dup_code={dup_code}",
        f"negative_control_fired={fired}",
        "NEG-COMPLETE:IMP-0009",
        "SUCCESS:IMP-0009-neg" if fired else "FAILED:IMP-0009-neg",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if fired else 1


if __name__ == "__main__":
    raise SystemExit(main())
