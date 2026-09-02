#!/usr/bin/env python3
"""Probe 1: planted import of each of seven torn-down runtimes (evidence A).

Also the both-states control (silent on a legitimate library, loud on a
runtime import, naming WHICH plane) and the owner-allowlist path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = HERE / "probe1-planted-imports.raw.json"


def main() -> int:
    both = S.both_states()
    a = S.evidence_a()
    doc = {
        "probe": "probe1-planted-imports",
        "unit_id": "WFA-0056",
        "both_states": both,
        "evidence_a": a,
        "pass": bool(both.get("pass") and a.get("pass")),
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not doc["pass"]:
        print("FAILED:WFA-0056-probe1 planted imports / both-states")
        print(json.dumps(doc, indent=2, sort_keys=True)[:4000])
        return 1
    named = [r["control_plane"] for r in a["planted"]]
    print(
        "silent_on_legit="
        + str(both["silent_on_legitimate_library"])
        + " loud_on_runtime="
        + str(both["loud_on_runtime_import"])
        + " named="
        + ",".join(named)
        + " allowlist="
        + str(a["allowlist"]["pass"])
    )
    print("SUCCESS:WFA-0056-probe1 planted imports both-states allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
