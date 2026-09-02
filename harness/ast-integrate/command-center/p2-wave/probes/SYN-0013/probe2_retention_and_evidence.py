#!/usr/bin/env python3
"""Probe 2: per-class retention (not blended) and EVIDENCE gate on every candidate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from synthesis.digest_loss import (  # noqa: E402
    CLASSES,
    aggregate_would_hide,
    apply_word_cap_exempt_evidence,
    count_body,
    evidence_gate,
    rates_are_per_class,
    retention_rates,
)

RECEIPT = REPO / "command-center" / "receipts" / "SYN-0013.json"
SOURCE = HERE / "fixtures" / "source_full.md"
SYNTH = HERE / "fixtures" / "synthesis_lossy.md"
CANDIDATES = (
    ("candidate_good.md", True),
    ("candidate_no_block.md", False),
    ("candidate_two_anchors.md", False),
    ("candidate_six_anchors.md", False),
)


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0013-probe2 {msg}")
    return 1


def main() -> int:
    src = SOURCE.read_text(encoding="utf-8")
    syn = SYNTH.read_text(encoding="utf-8")
    rows = retention_rates(count_body(src)["use"], count_body(syn)["use"])
    hide = aggregate_would_hide(rows)
    print(
        json.dumps(
            {
                "probe": "probe2-retention-and-evidence",
                "unit_id": "SYN-0013",
                "fixture_retention": rows,
                "aggregate_would_hide": hide,
            },
            indent=1,
            sort_keys=True,
        )
    )
    if not rates_are_per_class(rows):
        return fail("fixture rates are not per-class")
    if rows["UNVERIFIED"]["retention_rate"] != 1.0:
        return fail("UNVERIFIED fixture retention")
    if rows["file_line"]["retention_rate"] != 0.0:
        return fail("file_line fixture retention")
    if rows["URL"]["retention_rate"] != 0.0:
        return fail("URL fixture retention")
    if not hide["aggregate_hides_class_loss"]:
        return fail("blended rate would not hide class loss on this fixture")

    gated = []
    for name, expect in CANDIDATES:
        text = (HERE / "fixtures" / name).read_text(encoding="utf-8")
        gate = evidence_gate(text)
        gated.append(
            {
                "file": name,
                "expect_pass": expect,
                "pass": gate["pass"],
                "reason": gate["reason"],
            }
        )
        if gate["pass"] != expect:
            return fail(f"{name} gate pass={gate['pass']} expect={expect} reason={gate['reason']}")
        if expect:
            capped = apply_word_cap_exempt_evidence(text, cap=8)
            after = evidence_gate(capped)
            if not after["pass"]:
                return fail(f"{name} evidence lost under word cap")
            if after["anchor_count"] < 3:
                return fail(f"{name} cap stripped anchors to {after['anchor_count']}")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    published = (doc.get("fixture_retention") or {}).get("per_class")
    if not rates_are_per_class(published):
        return fail("receipt did not publish per-class retention")
    for cls in CLASSES:
        if published[cls].get("retention_rate") != rows[cls]["retention_rate"]:
            return fail(f"receipt {cls} rate mismatch")
    live_rows = (doc.get("live_measurement") or {}).get("naive_retention")
    if not rates_are_per_class(live_rows):
        return fail("live naive_retention not per-class")
    enf = doc.get("evidence_block_enforcement") or {}
    if not enf.get("every_candidate_gated"):
        return fail("receipt did not gate every candidate")
    print(json.dumps({"candidates": gated, "pass": True}, indent=1, sort_keys=True))
    print("SUCCESS:SYN-0013-probe2 per-class retention and EVIDENCE gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
