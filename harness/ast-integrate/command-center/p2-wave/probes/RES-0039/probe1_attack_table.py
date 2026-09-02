#!/usr/bin/env python3
"""Probe 1: attack-class table completeness, dual rails, local instantiations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import surface as S  # noqa: E402


def main() -> int:
    try:
        doc = C.load_artifact()
        C.validate_schema(doc)
        stats = C.check_table(doc)
        n_rails = C.check_dual_rails(doc)
        live = S.run_surface()
        body = C.payload(doc)
        if live["survived_ids"] != body.get("survived_ids"):
            print("FAILED:RES-0039-probe1 live survived_ids drifted")
            return 1
        if live["bypassed_ids"] != body.get("bypassed_ids"):
            print("FAILED:RES-0039-probe1 live bypassed_ids drifted")
            return 1
    except Exception as exc:
        print(f"FAILED:RES-0039-probe1 {type(exc).__name__}: {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-attack-table",
                "unit_id": "RES-0039",
                "classes": stats["n_classes"],
                "survived": stats["survived"],
                "bypassed": stats["bypassed"],
                "rails": n_rails,
                "schema_ok": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"classes={stats['n_classes']} survived={stats['survived']} "
        f"bypassed={stats['bypassed']} rails={n_rails}"
    )
    print(
        "SUCCESS:RES-0039-probe1 attack-class table complete; every mitigation "
        "has an attempted-bypass outcome; dual rails rehash"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
