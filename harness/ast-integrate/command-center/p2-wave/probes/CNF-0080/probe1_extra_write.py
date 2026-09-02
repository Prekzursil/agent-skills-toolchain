#!/usr/bin/env python3
"""Probe 1: extra-write control. Tracer must see a write the plan never named."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0080-dryrun-parity.json"
SENTINEL = (
    "SUCCESS:CNF-0080 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the extra-write control "
    "was captured by the tracer and both action lists are attached. Any other "
    "terminal state is FAILED:CNF-0080 <classification> with the diagnostic "
    "tail attached."
)


def main() -> int:
    extra = S.extra_write_control()
    honest = S.honest_parity()
    print(
        f"captured={extra['captured_by_tracer']} "
        f"sneak_in_trace={extra['sneak_in_trace']} "
        f"sneak_in_plan={extra['sneak_in_plan']} "
        f"honest_match={honest['keys_match']} "
        f"dry_zero={honest['dry_run_zero_writes']}"
    )
    print("predicted=" + json.dumps(extra["predicted_actions"], sort_keys=True))
    print("traced=" + json.dumps(extra["traced_actions"], sort_keys=True))
    if not extra["pass"]:
        print("FAILED:CNF-0080-probe1 extra-write not captured by tracer")
        return 1
    if not extra["traced_actions"] or not extra["predicted_actions"]:
        print("FAILED:CNF-0080-probe1 action lists empty")
        return 1
    if not honest["pass"]:
        print("FAILED:CNF-0080-probe1 honest parity failed")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0080-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0080-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text or "SUCCESS:CNF-0080" not in text:
        print("FAILED:CNF-0080-probe1 sentinel absent")
        return 1
    control = S.report_field(doc, "extra_write_control") or {}
    if control.get("captured_by_tracer") is not True:
        print("FAILED:CNF-0080-probe1 artifact extra-write not captured")
        return 1
    predicted = S.report_field(doc, "predicted_actions") or []
    traced = S.report_field(doc, "traced_actions") or []
    if not predicted or not traced:
        print("FAILED:CNF-0080-probe1 artifact missing action lists")
        return 1
    print("SUCCESS:CNF-0080-probe1 extra-write captured by filesystem census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
