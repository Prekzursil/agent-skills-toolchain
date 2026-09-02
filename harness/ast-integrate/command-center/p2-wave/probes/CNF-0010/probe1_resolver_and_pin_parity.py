#!/usr/bin/env python3
"""Named probe 1: PowerShell resolver vs POSIX which, plus pin-parity comparison.

Signal 1 is PATHEXT .cmd resolution. Signal 2 is CI-pin vs locally resolved
formatter/linter version. A POSIX `which` miss on the shim is required.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from capture import capture_live, pin_parity_rows  # noqa: E402
from ci_pins import extract_pins  # noqa: E402
from contract import COMPLETION_SENTINEL, FORMATTER_LINTER_NAMES, OUT_REL, UNIT_ID  # noqa: E402
from resolver import cmd_shim_control  # noqa: E402
from schema_local import payload  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0010-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = payload(doc)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:CNF-0010-probe1 unit_id", doc.get("unit_id"))
        return 1
    if COMPLETION_SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0010-probe1 sentinel absent")
        return 1
    families = {m.get("os", {}).get("family") for m in body.get("manifests") or []}
    if families != {"linux", "windows"}:
        print("FAILED:CNF-0010-probe1 os families", sorted(families))
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0010-p1-") as tmp:
        control = cmd_shim_control(Path(tmp) / "shim", "ruff")
    if not control["pass"]:
        print("FAILED:CNF-0010-probe1 .cmd shim control")
        print(json.dumps(control, indent=2))
        return 1
    recorded = body.get("resolver_control") or {}
    if not recorded.get("powershell_found_cmd_shim") or not recorded.get(
        "posix_which_missed_cmd_shim"
    ):
        print("FAILED:CNF-0010-probe1 artifact resolver_control drift")
        return 1

    ci = extract_pins(REPO)
    live = capture_live(REPO)
    rows = pin_parity_rows(live, ci)
    names = {r["name"] for r in rows}
    missing = [n for n in FORMATTER_LINTER_NAMES if n not in names]
    if missing:
        print("FAILED:CNF-0010-probe1 pin-parity skipped", missing)
        return 1
    art_rows = (body.get("pin_parity") or {}).get("rows") or []
    art_names = {r.get("name") for r in art_rows if isinstance(r, dict)}
    if names != art_names:
        print("FAILED:CNF-0010-probe1 pin-parity name drift", names, art_names)
        return 1
    if not (body.get("pin_parity") or {}).get("compared"):
        print("FAILED:CNF-0010-probe1 pin_parity.compared is not true")
        return 1
    # Both-states: planting an unequal local version must flip equal to False.
    flipped = False
    for row in rows:
        if row["ci_pinned"] and row["local_resolved"] != row["ci_pinned"]:
            flipped = True
            break
    if not flipped:
        # Local happened to match every pin. Force a synthetic unequal row
        # through the same comparator by overlaying a fake local version.
        from capture import tool_version_token  # local import for the control

        fake_live = json.loads(json.dumps(live))
        for t in fake_live.get("tools") or []:
            if t.get("name") == "ruff":
                t["version"] = "ruff 0.0.0"
        fake_rows = pin_parity_rows(fake_live, ci)
        ruff_row = next(r for r in fake_rows if r["name"] == "ruff")
        if ruff_row["equal"] or tool_version_token("ruff 0.0.0") == ruff_row["ci_pinned"]:
            print("FAILED:CNF-0010-probe1 pin-parity comparator is stuck-true")
            return 1
        flipped = True

    out = {
        "probe": "probe1-resolver-and-pin-parity",
        "unit_id": UNIT_ID,
        "powershell_found_cmd_shim": True,
        "posix_which_missed_cmd_shim": True,
        "pin_parity_names": sorted(names),
        "pin_parity_all_equal": all(r["equal"] for r in rows),
        "os_families": sorted(families),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0010-probe1 resolver .cmd shim and pin-parity comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
