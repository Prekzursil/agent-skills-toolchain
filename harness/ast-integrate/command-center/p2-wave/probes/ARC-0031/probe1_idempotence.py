#!/usr/bin/env python3
"""Probe 1: idempotence criterion on three real unit shapes.

Re-run each shape. Byte-identical artifact => IDEMPOTENT. Otherwise
NON-IDEMPOTENT. Classifications must match DESIGN.json when present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shapes as S  # noqa: E402

DESIGN = REPO / "command-center/phase3/A5/DESIGN.json"


def main() -> int:
    rows = S.run_all()
    if len(rows) != 3:
        print(f"FAILED:ARC-0031-probe1 expected 3 shapes got {len(rows)}")
        return 1
    ids = [r["id"] for r in rows]
    if ids != ["generated-ssot", "architecture-dossier-emit", "shared-reducer"]:
        print(f"FAILED:ARC-0031-probe1 unexpected ids={ids}")
        return 1
    fail = False
    for r in rows:
        print(
            f"shape id={r['id']} class={r['classification']} "
            f"sha1={r['run1_sha256'][:12]} sha2={r['run2_sha256'][:12]} "
            f"same={r['run1_sha256']==r['run2_sha256']}"
        )
        if r["id"] == "architecture-dossier-emit" and r["classification"] != "NON-IDEMPOTENT":
            print("FAILED:ARC-0031-probe1 dossier emit was not classified NON-IDEMPOTENT")
            fail = True
        if r["id"] in {"generated-ssot", "shared-reducer"} and r["classification"] != "IDEMPOTENT":
            print(f"FAILED:ARC-0031-probe1 {r['id']} was not IDEMPOTENT")
            fail = True
        if r["idempotent"] != (r["run1_sha256"] == r["run2_sha256"]):
            print(f"FAILED:ARC-0031-probe1 flag/sha disagree for {r['id']}")
            fail = True
    if DESIGN.is_file():
        doc = json.loads(DESIGN.read_text(encoding="utf-8"))
        report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
        samples = doc.get("idempotence_samples") or report.get("idempotence_samples") or []
        recorded = {
            x["id"]: x.get("classification")
            for x in samples
            if isinstance(x, dict)
        }
        for r in rows:
            rec = recorded.get(r["id"])
            if rec and rec != r["classification"]:
                print(
                    f"FAILED:ARC-0031-probe1 DESIGN classification drift "
                    f"{r['id']} live={r['classification']} recorded={rec}"
                )
                fail = True
        guarantee = str(
            (
                doc.get("delivery_guarantee") or report.get("delivery_guarantee") or {}
            ).get("claimed")
            or ""
        )
        if "at-least-once" not in guarantee.lower():
            print(f"FAILED:ARC-0031-probe1 delivery_guarantee.claimed missing at-least-once: {guarantee}")
            fail = True
        if "exactly-once" in guarantee.lower() and "not" not in guarantee.lower():
            # Allow 'not exactly-once'. Reject a positive exactly-once claim.
            if "not exactly-once" not in guarantee.lower() and "not claimed" not in guarantee.lower():
                print("FAILED:ARC-0031-probe1 overclaim: exactly-once listed as the claimed guarantee")
                fail = True
    if fail:
        print("FAILED:ARC-0031-probe1 idempotence criterion")
        return 1
    print("SUCCESS:ARC-0031-probe1 idempotence criterion on three real unit shapes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
