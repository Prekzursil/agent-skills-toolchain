#!/usr/bin/env python3
"""Named probe 1: throwaway HOME rehearsal — user-created command survives.

Signal (1) of the catalog evidence_requirement. Does not score the hash-census
equality that probe 2 owns.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin import trees as T  # noqa: E402
from plugin.rollback import census, rollback  # noqa: E402

HERE = Path(__file__).resolve().parent
USER = "commands/user-created.md"
OUT = HERE / "probe1-rehearsal.raw.json"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0026-probe1-"))
    home = tmp / "home"
    live = T.seed_v2_with_foreign(home)
    v1 = T.seed_payload(tmp / "payload-v1", T.PAYLOAD_V1)
    user_path = live / USER
    if not user_path.is_file():
        print("FAILED:IMP-0026-probe1 user-created command was not seeded")
        return 1
    before_bytes = user_path.read_bytes()
    pre = census(live)
    report = rollback(live, v1, T.OWNED_V2, T.OWNED_V1)
    still = user_path.is_file()
    after_bytes = user_path.read_bytes() if still else b""
    doc = {
        "probe": "probe1-rehearsal",
        "unit_id": "IMP-0026",
        "throwaway_home": str(home),
        "live_plugin_root": str(live),
        "user_command": USER,
        "seeded": True,
        "exists_after": still,
        "byte_identical": still and after_bytes == before_bytes,
        "pre_sha256": pre.get(USER),
        "post_sha256": census(live).get(USER) if still else None,
        "rollback_mode": report.mode,
        "rollback_error": report.error,
        "foreign_preserved_report": report.foreign_preserved,
        "marker": "IMP-0026-FOREIGN-COMMAND" in after_bytes.decode("utf-8", "replace"),
        "pass": False,
    }
    ok = (
        still
        and after_bytes == before_bytes
        and report.mode == "set-difference"
        and report.error is None
        and b"IMP-0026-FOREIGN-COMMAND" in after_bytes
    )
    doc["pass"] = ok
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0026-probe1 user-created command did not survive rollback")
        return 1
    print("SUCCESS:IMP-0026-probe1 throwaway HOME user-created command survived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
