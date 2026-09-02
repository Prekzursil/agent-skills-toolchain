#!/usr/bin/env python3
"""Named probe 2: partial artifact survives mismatch; discard mutation turns red.

Independent of probe 1's verdict assertion: this probe re-reads the live
partial bytes after dispatch and plants a discard mutation that MUST fail
the preservation check.
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


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0423-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0423-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0423-probe2 self-declared {doc.get('state')}")
        return 1
    partial_meta = doc.get("partial_artifact") or {}
    rel = str(partial_meta.get("path") or "")
    live_path = REPO / rel if rel and not Path(rel).is_absolute() else Path(rel)
    if not live_path.is_file():
        print(f"FAILED:IMP-0423-probe2 preserved partial missing: {rel}")
        return 1
    declared_bytes = int(partial_meta.get("bytes") or 0)
    live_size = live_path.stat().st_size
    if declared_bytes < 1 or live_size != declared_bytes:
        print(
            f"FAILED:IMP-0423-probe2 byte-size mismatch declared={declared_bytes} live={live_size}"
        )
        return 1
    if partial_meta.get("preserved") is not True:
        print("FAILED:IMP-0423-probe2 receipt did not mark partial preserved")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0423-p2-") as tmp:
        path = Path(tmp) / "partial.json"
        dl.seed_partial(path, PARTIAL_BODY)
        before = path.read_bytes()
        result = dl.dispatch(dl.mismatch_request(path), dl.openai_fixture(streaming=False))
        if result.verdict != dl.VERDICT_DEGRADED:
            print(f"FAILED:IMP-0423-probe2 live verdict {result.verdict}")
            return 1
        try:
            dl.assert_partial_preserved(path, before)
            honest_ok = True
        except AssertionError as exc:
            print(f"FAILED:IMP-0423-probe2 honest path lost the partial: {exc}")
            return 1

        mutant = Path(tmp) / "mutant.json"
        dl.seed_partial(mutant, PARTIAL_BODY)
        mutant_before = mutant.read_bytes()
        mutant_result = dl.dispatch(
            dl.mismatch_request(mutant), dl.openai_fixture(streaming=False)
        )
        if mutant_result.verdict != dl.VERDICT_DEGRADED:
            print("FAILED:IMP-0423-probe2 mutant dispatch was not DEGRADED")
            return 1
        mutant.unlink()
        mutation_turned_red = False
        try:
            dl.assert_partial_preserved(mutant, mutant_before)
        except AssertionError:
            mutation_turned_red = True
        if not mutation_turned_red:
            print("FAILED:IMP-0423-probe2 discard mutation did not turn the test red")
            return 1

    payload = {
        "declared_bytes": declared_bytes,
        "honest_preserved": honest_ok,
        "live_bytes": live_size,
        "mutation_turned_red": True,
        "pass": True,
        "preserved_path": rel,
        "probe": "probe2-preserve",
        "unit_id": "IMP-0423",
        "verdict": result.verdict,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"preserved_path={rel} bytes={live_size} honest_ok=True mutation_turned_red=True"
    )
    print("SUCCESS:IMP-0423-probe2 partial preserved; discard mutation turns red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
