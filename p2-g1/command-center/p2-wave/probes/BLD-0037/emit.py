#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0037.json from the live recall audit."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

REPO = HERE.parents[3]


def main() -> int:
    result = A.run_audit(REPO)
    doc = A.artifact_body(result)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0037 emit state={doc.get('state')}")
        for c in doc.get("controls") or []:
            print(f"  control {c['id']} {c['result']}: {c['detail']}")
        return 1
    if "SUCCESS:BLD-0037" not in A.dump(doc):
        print("FAILED:BLD-0037 sentinel missing from artifact body")
        return 1
    kinds = {f.get("kind") for f in doc.get("findings") or []}
    if "UNCONSULTED" not in kinds or "CONTRADICTS" not in kinds or "STALE" not in kinds:
        print(f"FAILED:BLD-0037 findings kinds={sorted(kinds)}")
        return 1
    out = REPO / A.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(A.dump(doc), encoding="utf-8", newline="\n")
    print(
        f"wrote {A.OUT_REL} bytes={out.stat().st_size} "
        f"unconsulted={len(doc['unconsulted'])} findings={len(doc['findings'])} "
        f"state={doc['state']}"
    )
    print("SUCCESS:BLD-0037 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
