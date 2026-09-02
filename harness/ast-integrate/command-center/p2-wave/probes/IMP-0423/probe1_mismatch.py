#!/usr/bin/env python3
"""Named probe 1: forced capability mismatch is DEGRADED, never SUCCESS.

Adversarial: a capable fallback vendor is offered. Silent substitution must
not produce an ordinary-looking success. Retrying the mismatch must not either.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.dispatch import degrade_loudly as dl  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0423.json"
SENTINEL = "SENTINEL:IMP-0423:DEGRADED-LOUD-AND-PRESERVED"
PARTIAL_BODY = (
    b'{"unit":"FIXTURE-CAP-MISMATCH","step":3,'
    b'"note":"partial work product that must survive a capability mismatch"}\n'
)


def _check_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0423-probe1 receipt missing")
        sys.exit(1)
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0423-probe1 receipt unparseable {exc}")
        sys.exit(1)
    if not isinstance(doc, dict):
        print("FAILED:IMP-0423-probe1 receipt not an object")
        sys.exit(1)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0423-probe1 self-declared {doc.get('state')}")
        sys.exit(1)
    if SENTINEL not in text:
        print("FAILED:IMP-0423-probe1 sentinel absent")
        sys.exit(1)
    if doc.get("unit_id") != "IMP-0423":
        print(f"FAILED:IMP-0423-probe1 unit_id {doc.get('unit_id')}")
        sys.exit(1)
    if doc.get("verdict") != "DEGRADED":
        print(f"FAILED:IMP-0423-probe1 receipt verdict {doc.get('verdict')} want DEGRADED")
        sys.exit(1)
    if doc.get("verdict") == "SUCCESS":
        print("FAILED:IMP-0423-probe1 mismatch receipt looks like SUCCESS")
        sys.exit(1)
    if not doc.get("mismatches"):
        print("FAILED:IMP-0423-probe1 receipt has empty mismatches")
        sys.exit(1)
    return doc


def main() -> int:
    doc = _check_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0423-p1-") as tmp:
        path = Path(tmp) / "partial.json"
        dl.seed_partial(path, PARTIAL_BODY)
        req = dl.mismatch_request(path)
        weak = dl.openai_fixture(streaming=False)
        capable = dl.anthropic_fixture()
        live = dl.dispatch(req, weak)
        if live.verdict != dl.VERDICT_DEGRADED:
            print(f"FAILED:IMP-0423-probe1 live verdict {live.verdict}")
            return 1
        if live.verdict == dl.VERDICT_SUCCESS or live.ordinary_looking_success:
            print("FAILED:IMP-0423-probe1 mismatch produced ordinary SUCCESS")
            return 1
        if not any(m.field == "streaming" for m in live.mismatches):
            print("FAILED:IMP-0423-probe1 expected streaming mismatch")
            return 1
        subst = dl.dispatch_with_fallback(req, weak, capable)
        if subst.verdict != dl.VERDICT_DEGRADED:
            print("FAILED:IMP-0423-probe1 substitution produced", subst.verdict)
            return 1
        if not subst.substitution_refused:
            print("FAILED:IMP-0423-probe1 substitution was not refused")
            return 1
        retried = dl.retry_mismatch(live)
        if retried.verdict != dl.VERDICT_DEGRADED or not retried.retry_refused:
            print("FAILED:IMP-0423-probe1 retry escaped DEGRADED")
            return 1
        match_path = Path(tmp) / "match.json"
        dl.seed_partial(match_path, b'{"ok":true}\n')
        matched = dl.dispatch(dl.matched_request(match_path), capable)
        if matched.verdict != dl.VERDICT_SUCCESS:
            print("FAILED:IMP-0423-probe1 negative control (match) was not SUCCESS")
            return 1

    payload = {
        "adversarial_substitution_refused": True,
        "live_verdict": live.verdict,
        "match_control_success": True,
        "mismatches": [m.to_dict() for m in live.mismatches],
        "ordinary_looking_success": live.ordinary_looking_success,
        "pass": True,
        "probe": "probe1-mismatch",
        "receipt_verdict": doc.get("verdict"),
        "retry_refused": True,
        "unit_id": "IMP-0423",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "live_degraded=True substitution_refused=True retry_refused=True "
        "match_control_success=True"
    )
    print("SUCCESS:IMP-0423-probe1 mismatch is DEGRADED not SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
