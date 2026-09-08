#!/usr/bin/env python3
"""CC-0023 probe1 — materialize DEFERRED ledger + run four catalog controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
import owner_option_id_adjudication as adj  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
OUT_JSON = PROBE_DIR / "probe1-controls.json"
OUT_RAW = PROBE_DIR / "probe1-controls.raw.txt"
FIXTURE_BEFORE = PROBE_DIR / "fixtures" / "doc18-blocks-before.md"
FIXTURE_AFTER_SILENT = PROBE_DIR / "fixtures" / "doc18-blocks-silent-rewrite.md"


def main() -> int:
    FIXTURE_BEFORE.parent.mkdir(parents=True, exist_ok=True)
    before = (
        "# Planted doc-18 BLOCKS excerpt (CC-0023 silent-rewrite control)\n\n"
        "**BLOCKS:** A6 beyond its snapshot step; M-16, M-18\n"
    )
    silent = (
        "# Planted doc-18 BLOCKS excerpt (CC-0023 silent-rewrite control)\n\n"
        "**BLOCKS:** A6 beyond its snapshot step; MECH-16, MECH-18\n"
    )
    FIXTURE_BEFORE.write_text(before, encoding="utf-8")
    FIXTURE_AFTER_SILENT.write_text(silent, encoding="utf-8")

    led = adj.materialize(defer_stamp="2026-09-08T02:10:00Z")

    # Good state: unchanged source excerpt (no silent rewrite).
    good_rewrite = adj.silent_rewrite_control(
        before_text=FIXTURE_BEFORE.read_text(encoding="utf-8"),
        after_text=FIXTURE_BEFORE.read_text(encoding="utf-8"),
    )
    # Bad state: unattributed MECH rewrite must FAIL the control.
    bad_rewrite = adj.silent_rewrite_control(
        before_text=FIXTURE_BEFORE.read_text(encoding="utf-8"),
        after_text=FIXTURE_AFTER_SILENT.read_text(encoding="utf-8"),
    )

    report = adj.run_all_controls(
        ledger=led,
        rewrite_before=FIXTURE_BEFORE.read_text(encoding="utf-8"),
        rewrite_after=FIXTURE_BEFORE.read_text(encoding="utf-8"),
    )
    # Inject explicit bad-state fire into report for receipt negative_controls.
    report["controls"]["silent-rewrite-bad-state-fires"] = {
        "pass": bad_rewrite.passed is False,
        "detail": bad_rewrite.detail,
    }
    report["controls"]["zero-silent-rewrites"]["pass"] = good_rewrite.passed
    report["controls"]["zero-silent-rewrites"]["detail"] = good_rewrite.detail
    report["ok"] = all(
        v["pass"]
        for k, v in report["controls"].items()
        if k != "silent-rewrite-bad-state-fires"
    ) and report["controls"]["silent-rewrite-bad-state-fires"]["pass"]

    payload = {
        "unit": "CC-0023",
        "ok": report["ok"],
        "counts": led["counts"],
        "honesty": led["honesty"],
        "n_questions": len(adj.QUESTIONS),
        "controls": report["controls"],
        "ledger_path": str(adj.LEDGER_PATH.relative_to(REPO)),
        "packet_path": str(adj.PACKET_PATH.relative_to(REPO)),
        "census_path": str(adj.CENSUS_PATH.relative_to(REPO)),
        "owner_decisions_path": str(adj.OWNER_DECISIONS.relative_to(REPO)),
        "recorded_owner_answers": led["recorded_owner_answers"],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw = (
        "CC-0023 probe1 controls\n"
        f"total_refs={led['counts']['total_refs']}\n"
        f"deferred={led['counts']['deferred']}\n"
        f"owner_answered={led['counts']['owner_answered']}\n"
        f"invented_owner_answers={led['honesty']['invented_owner_answers']}\n"
        f"n_questions={len(adj.QUESTIONS)}\n"
        f"ok={report['ok']}\n"
        + "\n".join(
            f"control.{name}.pass={info['pass']}"
            for name, info in sorted(report["controls"].items())
        )
        + "\n--- json ---\n"
        + json.dumps(payload, indent=2, sort_keys=True)
        + "\n"
    )
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
