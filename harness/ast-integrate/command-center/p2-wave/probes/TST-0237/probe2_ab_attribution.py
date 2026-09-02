#!/usr/bin/env python3
"""Probe 2: A/B harness-off delta + both-states disable + missing-instrument control.

Mechanically different from probe 1:
  * end-to-end A/B (all four on vs all four off)
  * both-states: disabling one component must move its line item AND the total
  * negative control: omitting one component from the instrumented dict must
    break the 5% attribution check
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
DISABLE = "hook_dispatch"


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0237" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        print(f"FAILED:TST-0237-probe2 {art_err}")
        return 1

    ab = H.measure_ab(H.N_TURNS)
    if not ab["harness_off_faster"]:
        print("FAILED:TST-0237-probe2 harness-off was not faster than harness-on")
        return 1
    if not ab["pass_attribution"]:
        print(
            "FAILED:TST-0237-probe2 instrumented sum vs A/B delta "
            f"rel_err={ab['sum_vs_ab_rel_err']:.4f} delta={ab['ab_delta_ms']:.3f}ms"
        )
        return 1

    both = H.measure_both_states(H.N_TURNS, disable=DISABLE)
    if not both["line_item_moved"]:
        print(
            "FAILED:TST-0237-probe2 disabling "
            f"{DISABLE} did not move its line item "
            f"on={both['line_item_on_ms']:.3f} off={both['line_item_off_ms']:.3f}"
        )
        return 1
    if not both["total_moved"]:
        print(
            "FAILED:TST-0237-probe2 disabling "
            f"{DISABLE} did not move the total "
            f"paired_drop={both['paired_median_drop_ms']:.3f}ms"
        )
        return 1

    missing = H.measure_missing_instrument(H.N_TURNS)
    if not missing["pass_negative_control"]:
        print(
            "FAILED:TST-0237-probe2 missing-instrument mutant did not break "
            f"the 5% check hide={missing['hidden']} "
            f"sum_vs_total={missing['sum_vs_total_rel_err']:.4f} "
            f"sum_vs_ab={missing['sum_vs_ab_rel_err']:.4f}"
        )
        return 1

    summary = {
        "pass": True,
        "probe": "probe2-ab-attribution",
        "unit_id": H.UNIT,
        "ab_delta_ms": ab["ab_delta_ms"],
        "sum_vs_ab_rel_err": ab["sum_vs_ab_rel_err"],
        "harness_on_ms": ab["harness_on"]["total_median_ms"],
        "harness_off_ms": ab["harness_off"]["total_median_ms"],
        "both_states_disabled": DISABLE,
        "line_item_on_ms": both["line_item_on_ms"],
        "line_item_off_ms": both["line_item_off_ms"],
        "paired_median_drop_ms": both["paired_median_drop_ms"],
        "missing_instrument_hidden": missing["hidden"],
        "missing_instrument_fired": True,
        "token_counts_reported": False,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"ab_delta={ab['ab_delta_ms']:.3f}ms rel_err={ab['sum_vs_ab_rel_err']:.4f} "
        f"disable_{DISABLE} drop={both['paired_median_drop_ms']:.3f}ms "
        f"missing={missing['hidden']} fired=True"
    )
    print("SUCCESS:TST-0237-probe2 A/B attribution and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
