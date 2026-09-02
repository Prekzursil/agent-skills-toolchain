#!/usr/bin/env python3
"""Named probe 2: no-op-mode refusal + independent red-step attribution."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.REPO / S.OUT


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0435-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0435-probe2 self-declared", doc.get("state"))
        return 1

    noop = S.noop_mode()
    with tempfile.TemporaryDirectory(prefix="imp0435-p2-") as tmp:
        both = S.both_states(Path(tmp))
    # Independent re-run of the red fixture: fail at receipt-validate C3, not elsewhere.
    red_out = both["red"]["output_tail"]
    attributed = (
        both["red"]["failed_at_validator"]
        and "FAILED:receipt-validate" in red_out
        and "C3" in red_out
        and "pytest" not in red_out.lower()
    )
    payload = {
        "probe": "probe2-noop-mode-and-red-attribution",
        "unit_id": "IMP-0435",
        "reviewer_id": "IMP-0435-probe2-noop-mode",
        "all_banned_flags_refused": noop["all_banned_flags_refused"],
        "self_test_ok": noop["self_test_ok"],
        "workflow_ok": noop["workflow_ok"],
        "red_run_id": both["red"]["run_id"],
        "red_failing_step": both["red"]["failing_step"],
        "red_failed_at_validator_not_elsewhere": attributed,
        "pass": bool(
            noop["pass"] and attributed and both["red"]["exit_code"] != 0
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0435-probe2 no-op-mode or red-step attribution")
        print(json.dumps(noop, indent=2, sort_keys=True)[:3000])
        return 1
    print(
        f"banned_refused={noop['all_banned_flags_refused']} "
        f"red_step={both['red']['failing_step']} attributed={attributed}"
    )
    print(
        "SUCCESS:IMP-0435-probe2 no-op-mode refused; red run failed at validator step"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
