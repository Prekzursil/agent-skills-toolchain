#!/usr/bin/env python3
"""Measure rebuilt scanners on the historical FP + TP corpora (TST-0341)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from role_scanner import (  # noqa: E402
    REPO,
    measure_all,
    self_reference_silent,
)


def main() -> int:
    report = measure_all()
    # Self-reference: a document that quotes every forbidden pattern as an
    # EXAMPLE must stay silent under the role scanners.
    sample_doc = (
        "# TST-0341 self-reference control\n\n"
        "This receipt documents the forbidden patterns so a raw-text scanner "
        "would self-amplify. Examples (MENTIONS, not uses):\n\n"
        "- A Write of docs quoting `Remove-Item -Recurse` and `git push --force`.\n"
        "- Prose naming a `TODO` or `FIXME` marker inside backticks.\n"
        "- A stub-ledger note that 'zero TODO/FIXME/NotImplementedError exist'.\n"
        '- A result body with `"user_cancelled_or_timedout": false`.\n'
        "- Unquoted snake field list: user_cancelled_or_timedout examples.\n"
        "- Receipt sentinel vocabulary: FAILED:TST-0341 blocked-on-review.\n"
        "- A fixture declaring `ghp_` + FAKE token shape and AKIAEXAMPLE keys.\n"
        "- A guard path `hooks/deny-credential-reads/deny.py`.\n"
    )
    self_ref = self_reference_silent(sample_doc)
    report["self_reference"] = self_ref
    live_receipt = REPO / "command-center/receipts/TST-0341.json"
    if live_receipt.is_file():
        live = self_reference_silent(live_receipt.read_text(encoding="utf-8"))
        report["self_reference_live_receipt"] = live
        report["ok"] = bool(report["ok"] and self_ref["silent"] and live["silent"])
    else:
        report["ok"] = bool(report["ok"] and self_ref["silent"])
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
