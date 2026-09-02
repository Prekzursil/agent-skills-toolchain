#!/usr/bin/env python3
"""Named probe 1: both-states control for DNS-fail-closed install.

Assertion must fire when the resolver is blackholed (nonzero exit, host and
resolver named, index unchanged) and stay silent on a reachable registry.
A cache-success mutant must not satisfy the assertion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0129.json"


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "artifact missing"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0129" not in text:
        return "sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {st}"
    if doc.get("unit_id") != "TST-0129":
        return f"unit_id {doc.get('unit_id')}"
    return None


def main() -> int:
    art_err = check_artifact()
    if art_err:
        print(f"FAILED:TST-0129-probe1 {art_err}")
        return 1

    live = H.evaluate()
    ok, fails = H.verdict(live)
    bh = live["blackhole"]["assertion"]
    reach = live["reachable"]
    mutant = live["mutant_cache_success"]

    summary = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0129",
        "blackhole_holds": bh["holds"],
        "blackhole_nonzero": bh["nonzero_exit"],
        "blackhole_names_host": bh["host_named"],
        "blackhole_names_resolver": bh["resolver_named"],
        "blackhole_index_unchanged": bh["index_unchanged"],
        "reachable_silent": not reach["assertion"]["holds"],
        "reachable_exit": reach["install"]["returncode"],
        "reachable_wrote": reach["wrote_live_index"],
        "mutant_cache_rejected": mutant["detector_rejects_mutant"],
        "fails": fails,
        "pass": ok,
    }
    print(json.dumps(summary, sort_keys=True))
    if not ok:
        print("FAILED:TST-0129-probe1 " + "; ".join(fails))
        print("blackhole install:", json.dumps(live["blackhole"]["install"])[:800])
        print("reachable install:", json.dumps(reach["install"])[:800])
        return 1
    print("both-states: fired on blackhole, silent on reachable registry")
    print("SUCCESS:TST-0129-probe1 DNS fail-closed both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
