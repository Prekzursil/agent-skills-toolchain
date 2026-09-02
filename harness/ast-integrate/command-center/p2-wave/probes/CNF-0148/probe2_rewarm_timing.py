#!/usr/bin/env python3
"""Probe 2: both-states timing restore + egress-not-blocked confound.

Mechanically different from probe 1 (existence/size): this probe compares the
warm vs cold vs re-warm timing profile and requires every result flip to name
a cache entry. Re-warming must restore the original hit timing, proving the
purge actually emptied the store rather than renaming it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import predicates, run  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0148.json"
RAW = HERE / "probe2-rewarm-timing.raw.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0148-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNF-0148" not in text:
        print("FAILED:CNF-0148-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0148-probe2 self-declared", doc.get("state"))
        return 1

    live = run()
    bad = predicates(live)
    RAW.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if bad:
        print("FAILED:CNF-0148-probe2 " + ",".join(bad))
        return 1

    warm_ms = float(live["warm"]["timing_ms_sum"])
    cold_ms = float(live["cold"]["timing_ms_sum"])
    rewarm_ms = float(live["rewarm"]["timing_ms_sum"])
    if cold_ms < warm_ms * 2:
        print(f"FAILED:CNF-0148-probe2 cold not materially slower warm={warm_ms} cold={cold_ms}")
        return 1
    if abs(rewarm_ms - warm_ms) >= abs(rewarm_ms - cold_ms):
        print(
            f"FAILED:CNF-0148-probe2 rewarm did not restore warm timing "
            f"warm={warm_ms} cold={cold_ms} rewarm={rewarm_ms}"
        )
        return 1
    if live["egress"].get("block_installed_by_this_unit") is not False:
        print("FAILED:CNF-0148-probe2 egress confound")
        return 1
    if live["egress"].get("permitted") is not True:
        print("FAILED:CNF-0148-probe2 egress not permitted")
        return 1

    # Reviewer surface: the two most timing-sensitive (largest cold ms) cache confirmations.
    cold_rows = [r for r in live["cold"]["rows"] if r.get("kind")]
    top = sorted(cold_rows, key=lambda r: float(r["ms"]), reverse=True)[:2]
    if len(top) < 2:
        print("FAILED:CNF-0148-probe2 fewer than two cache confirmations")
        return 1

    flips = live["flips"]
    if any(not f.get("named_cache_entry") for f in flips):
        print("FAILED:CNF-0148-probe2 flip without named cache entry")
        return 1
    print(
        f"warm_ms={warm_ms} cold_ms={cold_ms} rewarm_ms={rewarm_ms} "
        f"egress_permitted={live['egress']['permitted']} "
        f"flips={[(f['confirmation'], f['named_cache_entry'], f['class']) for f in flips]} "
        f"timing_sensitive={[t['id'] for t in top]}"
    )
    print("SUCCESS:CNF-0148-probe2 rewarm timing restored and flips attributed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
