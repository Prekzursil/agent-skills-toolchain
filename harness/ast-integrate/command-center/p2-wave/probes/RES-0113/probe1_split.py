#!/usr/bin/env python3
"""Probe 1: additive-versus-renaming split, rejected technique, live anchors.

Both-states: live artifact must pass; stripping rejected[] must fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402

ART = C.ART


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0113-probe1 artifact missing")
        return 1
    doc = C.load_art()
    err = C.both_states_split(doc)
    print(
        json.dumps(
            {
                "probe": "probe1-split",
                "unit_id": "RES-0113",
                "both_states": err is None,
                "error": err,
                "renaming": len(
                    (doc.get("additive_versus_renaming_split") or {}).get(
                        "renaming"
                    )
                    or []
                ),
                "additive": len(
                    (doc.get("additive_versus_renaming_split") or {}).get(
                        "additive"
                    )
                    or []
                ),
                "rejected": len(
                    (doc.get("additive_versus_renaming_split") or {}).get(
                        "rejected"
                    )
                    or []
                ),
            },
            sort_keys=True,
        )
    )
    if err:
        print(f"FAILED:RES-0113-probe1 {err}")
        return 1
    if C.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:RES-0113-probe1 sentinel absent from bytes")
        return 1
    print("SUCCESS:RES-0113-probe1 additive-versus-renaming split and reject control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
