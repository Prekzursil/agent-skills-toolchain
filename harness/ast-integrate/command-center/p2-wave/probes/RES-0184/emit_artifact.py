#!/usr/bin/env python3
"""Write the RES-0184 measurement-run artifact (canonical JSON)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    doc = E.build_document()
    raw = E.canonical_bytes(doc)
    E.ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    E.ARTIFACT.write_bytes(raw)
    print(
        f"wrote {E.ARTIFACT_REL} bytes={len(raw)} sha256={E.sha256_bytes(raw)} "
        f"state={doc['state']} sentinel={doc['sentinel']} "
        f"below={doc['rescore']['below_bar_count']}/20 "
        f"high_below={doc['rescore']['high_severity_below_count']}"
    )
    return 0 if doc["state"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
