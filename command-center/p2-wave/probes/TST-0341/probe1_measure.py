#!/usr/bin/env python3
"""TST-0341 probe: measure rebuilt role scanners on FP + TP corpora."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOL = REPO / "tools" / "fixture-role-scanner"
sys.path.insert(0, str(TOOL))

from role_scanner import measure_all, self_reference_silent  # noqa: E402

PROBE = Path(__file__).resolve().parent


def main() -> int:
    report = measure_all()
    # Soft sample (quoted JSON field) plus hard sample that previously FAIL'd
    # adversarial review: unquoted snake embed + FAILED:UNIT sentinel vocabulary.
    receipt_like = (
        "# command-center/receipts/TST-0341.json (documentary)\n\n"
        "Evidence requirement: report, for each rebuilt scanner, its result on "
        "the historical false-positive corpus AND on a true-positive corpus.\n\n"
        "Forbidden patterns quoted as EXAMPLES (must not flag):\n"
        "- CMD-FP-writebody: Write docs quoting `git push --force` / `Remove-Item`.\n"
        "- MRK-FP-inlinecode: naming `TODO` / `FIXME` in backticks.\n"
        "- STUB-FP-negated-absence: 'zero TODO/FIXME/NotImplementedError exist'.\n"
        '- RES-FP-fieldname: `{"user_cancelled_or_timedout": false}`.\n'
        "- RES-FP-snake-prose: user_cancelled_or_timedout examples in unquoted prose.\n"
        "- RES-FP-sentinel: FAILED:TST-0341 blocked-on-independent-review vocabulary.\n"
        "- SEC-FP-declared: synthetic AKIAEXAMPLE / ghp_ FAKE tokens in fixtures.\n"
        "- PATH-FP-guardfile: hooks/deny-credential-reads/deny.py.\n"
    )
    self_ref = self_reference_silent(receipt_like)
    report["self_reference"] = self_ref
    live_path = REPO / "command-center" / "receipts" / "TST-0341.json"
    live_silent = True
    if live_path.is_file():
        live = self_reference_silent(live_path.read_text(encoding="utf-8"))
        report["self_reference_live_receipt"] = live
        live_silent = bool(live["silent"])
    report["ok"] = bool(report["ok"] and self_ref["silent"] and live_silent)
    out = PROBE / "corpus-measure.json"
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"ok": report["ok"], "path": str(out.relative_to(REPO))}, indent=2)
    )
    # Human-readable both-numbers table
    print("--- per-scanner FP/TP ---")
    for kind, row in sorted(report["scanners"].items()):
        print(
            f"{kind}: role_fp={row['role_fp_flags']}/{row['fp_corpus_size']} "
            f"role_tp={row['role_tp_flags']}/{row['tp_corpus_size']} "
            f"raw_fp={row['raw_fp_flags']}"
        )
    live_bit = f" live_receipt_silent={live_silent}" if live_path.is_file() else ""
    print(
        f"totals: role_fp={report['role_fp_total']} "
        f"role_tp_missed={report['role_tp_missed']} "
        f"raw_fp={report['raw_fp_total']} "
        f"self_ref_silent={self_ref['silent']}{live_bit}"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
