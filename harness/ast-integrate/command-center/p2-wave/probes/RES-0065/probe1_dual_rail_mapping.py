#!/usr/bin/env python3
"""Probe 1: dual rails + live re-fetch + file:line mapping."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    UNIT,
    check_artifact_core,
    check_claims,
    check_mapping,
    live_recheck_pinned_markdown,
    live_recheck_schemas,
    load_artifact,
    load_index,
    verify_local_captures,
)


def main() -> int:
    try:
        index = load_index()
        verify_local_captures(index)
        doc = load_artifact()
        check_artifact_core(doc)
        cites = check_mapping(doc)
        check_claims(doc, index)
        pinned = live_recheck_pinned_markdown(index)
        schemas = live_recheck_schemas()
    except (AssertionError, KeyError, json.JSONDecodeError, OSError) as exc:
        print(f"FAILED:{UNIT}-probe1 {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-dual-rail-mapping",
                "unit_id": UNIT,
                "citations": cites,
                "claims": len(doc.get("claims") or []),
                "pinned_live_match": {k: v["match"] for k, v in pinned.items()},
                "schema_live": {k: v["tokens_ok"] for k, v in schemas.items()},
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe1 dual-rail mapping live-pinned-docs schema-tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
