#!/usr/bin/env python3
"""CC-0010 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the nine-class freeze (all captured), the program rollback pin, and the three controls: adversarial writer refused, quiescence two-signal baseline, rollback rehearsal SHA-anchored.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/CC-0010.json"
UNIT = "CC-0010"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (": " + detail if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe1 artifact unreadable/unparseable: %s" % (UNIT, type(exc).__name__))
        return 1
    if not isinstance(doc, dict):
        print("FAILED:%s-probe1 artifact is not a JSON object" % UNIT)
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold",
          "%s < %s" % (OUT.stat().st_size, minb))
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    fp = doc.get("freeze_protocol") or {}
    lf = doc.get("live_freeze") or {}
    nine = [str(c) for c in (fp.get("nine_classes") or [])]
    check(len(nine) == 9, "nine_classes != 9", str(len(nine)))
    check([str(c) for c in (lf.get("class_ids") or [])] == nine, "live class_ids != nine_classes")
    status = lf.get("class_status") or {}
    check(all(status.get(c) == "captured" for c in nine), "a freeze class is not captured",
          str([c for c in nine if status.get(c) != "captured"]))
    ctrls = doc.get("controls") or {}
    aw = ctrls.get("adversarial_writer") or {}
    check(aw.get("refused_baseline") is True and aw.get("ok") is True and aw.get("verdict") == "SAMPLE",
          "adversarial-writer control drift", str(aw))
    qs = ctrls.get("quiescent_scratch") or {}
    check(qs.get("git_status_match") is True and qs.get("mtime_scan_match") is True
          and int(qs.get("independent_signal_count", -1)) == 2 and qs.get("verdict") == "BASELINE",
          "quiescent-scratch control drift", str(qs))
    rr = ctrls.get("rollback_rehearsal") or {}
    check(rr.get("digests_reproduced") is True and rr.get("restored_verdict") == "SHA-ANCHORED",
          "rollback-rehearsal control drift", str(rr))
    check("53c37c6c" in text, "program rollback pin 53c37c6c absent from artifact text")
    check((HERE / "lib.py").is_file(), "instrument lib.py missing")
    check(len(doc.get("negative_controls") or []) >= 1 or (fp.get("retry_policy") and fp.get("baseline_rule")),
          "negative controls / protocol fields absent")

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe1 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe1 delivery predicate holds" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
