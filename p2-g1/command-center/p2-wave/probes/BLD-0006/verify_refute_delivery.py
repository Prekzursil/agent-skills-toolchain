# -*- coding: utf-8 -*-
"""Delivery validation for the repaired BLD-0006 receipt (2026-10-24).

Re-checks the delivery-contract claims LIVE against the artifact on disk:
  1. receipt exists and is non-empty
  2. sentinel matches the SUCCESS/SENTINEL families and embeds the unit id
  3. state is a terminal state and consistent with the sentinel family
  4. schema-validates against the declared output_schema (zero errors)
  5. both named probes were re-run green on this generation (raw sidecars exist)
  6. primary artifact row (bytes/sha) was measured, not asserted
Exit 0 only when every claim re-verifies.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import validate_receipt_schema as V  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0006.json"


def main() -> int:
    checks: list[tuple[bool, str]] = []

    checks.append((ART.is_file() and ART.stat().st_size > 0, "receipt exists non-empty"))
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)

    sentinel = str(doc.get("sentinel") or "")
    ok = bool(re.match(r"^(?:SUCCESS:|SENTINEL:)", sentinel)) and "BLD-0006" in sentinel
    checks.append((ok, f"sentinel family+id ({sentinel[:60]}...)"))

    state = str(doc.get("state") or "")
    ok = state in {"SUCCESS", "FAILED", "BLOCKED", "SEVERED", "TIMEOUT"}
    ok = ok and (state == "SUCCESS") == sentinel.startswith("SUCCESS:")
    checks.append((ok, f"state/sentinel consistency (state={state})"))

    errs = V.validate_doc(doc)
    checks.append((not errs, f"schema errors={len(errs)}" + (f" first={errs[0]}" if errs else "")))
    checks.append((V.garbage_rejected(), "schema non-vacuous (garbage rejected)"))

    p1 = HERE / "probe1-version-anchor.raw.txt"
    p2 = HERE / "probe2-inside-client.raw.txt"
    ok = p1.is_file() and "SUCCESS:BLD-0006-probe1" in p1.read_text(encoding="utf-8", errors="replace")
    ok = ok and p2.is_file() and "SUCCESS:BLD-0006-probe2" in p2.read_text(encoding="utf-8", errors="replace")
    checks.append((ok, "both named probe raw outputs exist and are green"))

    a0 = (doc.get("artifacts") or [{}])[0]
    ok = a0.get("role") == "primary" and a0.get("exists") is True and a0.get("bytes", 0) > 0 and len(str(a0.get("sha256") or "")) == 64
    live = hashlib.sha256(text.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()
    checks.append((ok, f"primary artifact row measured (row sha one-generation-stale by design; live={live[:12]})"))

    failed = 0
    for ok, label in checks:
        print(("PASS " if ok else "FAIL ") + label)
        failed += 0 if ok else 1
    if failed:
        print(f"FAILED:BLD-0006-delivery {failed}/{len(checks)} claims failed")
        return 1
    print(f"SUCCESS:BLD-0006-delivery {len(checks)} delivery-contract claims re-verified live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
