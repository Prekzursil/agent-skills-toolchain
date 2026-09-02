#!/usr/bin/env python3
"""CNF-0058 probe 1: a prose-only path reference still counts as a consumer.

Re-derives the layout+consumer cross-reference from the fixture trees. Does not
read the confirmation artifact conclusion first (reviewer-requirement).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402
import scenario as S  # noqa: E402


def main() -> int:
    paths = S.materialize()
    result = L.analyze(paths["before"], paths["after"], paths["consumers"])
    xref = {row["path"]: row for row in result["consumer_cross_reference"]}
    if S.MOVED_TO not in xref:
        print(f"FAILED:CNF-0058-probe1 missing changed path {S.MOVED_TO}")
        print(json.dumps(sorted(xref), indent=2))
        return 1
    row = xref[S.MOVED_TO]
    consumers = row.get("consumers") or []
    if row.get("consumer_finding") != "prose-only-consumer":
        print("FAILED:CNF-0058-probe1 prose-only path not classified as prose-only-consumer")
        print(json.dumps(row, indent=2, sort_keys=True))
        return 1
    if not consumers:
        print("FAILED:CNF-0058-probe1 prose path had empty consumer list")
        return 1
    if any(c.get("kind") != "prose" for c in consumers):
        print("FAILED:CNF-0058-probe1 expected exclusively prose consumers")
        print(json.dumps(consumers, indent=2))
        return 1
    if not any(c.get("consumer") == S.PROSE_DOC for c in consumers):
        print(f"FAILED:CNF-0058-probe1 handbook {S.PROSE_DOC} missing from cross-reference")
        print(json.dumps(consumers, indent=2))
        return 1
    # Negative: the workflow must NOT be credited as a consumer of the NEW path.
    if any("publish-layout" in (c.get("consumer") or "") for c in consumers):
        print("FAILED:CNF-0058-probe1 workflow incorrectly attached to the moved-to path")
        return 1
    payload = {
        "pass": True,
        "probe": "probe1-prose-consumer",
        "unit_id": S.UNIT_ID,
        "path": S.MOVED_TO,
        "consumer_finding": row["consumer_finding"],
        "consumers": consumers,
        "assumed_safe": row.get("assumed_safe"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"prose_only={S.MOVED_TO} consumer={S.PROSE_DOC} finding={row['consumer_finding']}")
    print("SUCCESS:CNF-0058-probe1 prose-only documentation consumer counted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
