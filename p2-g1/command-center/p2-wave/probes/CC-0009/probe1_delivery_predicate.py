#!/usr/bin/env python3
"""CC-0009 probe1 - registration currency + declared-consumer readability.

Condition 11 live: the CC-0009 row in command-center/ARTIFACT-MANIFEST.json
must carry the LIVE artifact sha (register-on-write is current, digest drift
fails). Condition 12 live: read_with_consumer opens the row with its declared
consumer (consume_json) and reports the first parsed key. The referenced
implementation surface (artifact_register.py, completion_c11_c12.py) must be
importable and expose the reducer functions. Rebuilt 2026-10-26 (wave-3
shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
OUT = REPO / "command-center/receipts/CC-0009.json"
UNIT = "CC-0009"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

from artifact_register import (  # noqa: E402
    check_condition_11,
    check_condition_12,
    read_with_consumer,
)


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))

    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    check(doc.get("unit_id") == UNIT, "unit_id matches catalog unit")
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "artifact not self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact non-empty")
    check(OUT.stat().st_size >= int(doc.get("min_bytes_threshold") or 0),
          "artifact above min_bytes_threshold", str(OUT.stat().st_size))
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel present in artifact text")
    # ---- condition 11 live: registration current, digest drift fails ----
    r11 = check_condition_11(REPO, unit_id=UNIT,
                             output_path="command-center/receipts/CC-0009.json")
    check(r11.ok, "condition 11: row registered AND sha current (no digest drift)",
          r11.reason)
    am = json.loads((REPO / "command-center/ARTIFACT-MANIFEST.json")
                    .read_text(encoding="utf-8"))
    rows = [r for r in am.get("artifacts", [])
            if isinstance(r, dict)
            and r.get("path", "").replace("\\", "/")
            == "command-center/receipts/CC-0009.json"]
    check(len(rows) == 1, "exactly one CC-0009 row in ARTIFACT-MANIFEST.json",
          str(len(rows)))
    row = rows[0]
    check(row.get("consumer") == "json"
          and str(row.get("consumer_reader", "")).endswith("consume_json"),
          "row declares its consumer reader (consume_json)",
          str(row.get("consumer_reader")))
    check(bool(row.get("first_parsed_key")), "row records the first parsed key",
          str(row.get("first_parsed_key")))

    # ---- condition 12 live: declared consumer opens the artifact ----
    read = read_with_consumer(REPO, "command-center/receipts/CC-0009.json",
                              consumer="json")
    check(bool(read.get("ok")), "consume_json opens the live receipt",
          str(read.get("error")))
    check(bool(read.get("first_parsed_key")), "first parsed key reported",
          str(read.get("first_parsed_key")))

    # ---- implementation surface importable + reducer functions exposed ----
    import completion_c11_c12  # noqa: F401

    check(hasattr(completion_c11_c12, "check_condition_11")
          and hasattr(completion_c11_c12, "check_condition_12"),
          "completion_c11_c12 exposes the reducer import surface")
    ext = doc.get("extensions", {}).get("legacy_root", {})
    check(ext.get("condition_11", {}).get("implementation")
          == "tools/command-center/artifact_register.py:check_condition_11"
          and ext.get("condition_12", {}).get("implementation")
          == "tools/command-center/artifact_register.py:check_condition_12",
          "receipt citations point at the live implementations")

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "checks": checks,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 registration current and consumer-readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
