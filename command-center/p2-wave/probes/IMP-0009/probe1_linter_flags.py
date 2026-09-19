#!/usr/bin/env python3
"""IMP-0009 probe1: linter flags fixture with Name/name (signal 1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) the linter flags a fixture with `Name`/`name`; "
    "(2) a raw byte-level key extraction (json.loads with object_pairs_hook, which "
    "preserves duplicates) independently confirms both keys were present in the "
    "source — because a naive dict load would have already destroyed the evidence."
)


def main() -> int:
    live_raw = (REPO / M.MANIFEST_RELPATH).read_text(encoding="utf-8")
    planted = M.mutate_case_collision_text(live_raw)

    flagged = False
    code = None
    message = None
    try:
        M.lint_json_text_for_key_collisions(planted)
    except M.ManifestSchemaError as exc:
        flagged = True
        code = exc.code
        message = str(exc)

    clean_ok = True
    try:
        M.assert_path_free_of_key_collisions(REPO / M.MANIFEST_RELPATH)
        M.assert_path_free_of_key_collisions(REPO / M.DISPATCH_MANIFEST_RELPATH)
    except M.ManifestSchemaError:
        clean_ok = False

    confirmed = bool(
        flagged
        and code == M.ERR_CASE_COLLISION
        and clean_ok
        and message
        and "Name" in message
        and "name" in message
    )

    meas = {
        "probe": "probe1-linter-flags-name-name",
        "probe_1_confirmed": confirmed,
        "ok": confirmed,
        "linter_flagged": flagged,
        "error_code": code,
        "message": message,
        "clean_plugin_ok": clean_ok,
        "planted_keys_hint": ["Name", "name"],
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 1: LINTER FLAGS Name/name FIXTURE",
        "PROBE-1-BEGIN:IMP-0009",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"linter_flagged={flagged}",
        f"error_code={code}",
        f"clean_plugin_ok={clean_ok}",
        f"probe_1_confirmed={confirmed}",
        "PROBE-1-COMPLETE:IMP-0009",
        "SUCCESS:IMP-0009-probe1" if confirmed else "FAILED:IMP-0009-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-linter-flags.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
