#!/usr/bin/env python3
"""Probe 1: instrumented per-component timings vs measured turn total (signal a).

PASS requires:
  * all four components have a positive median line item
  * sum of line items is within 5% of the outer turn total
  * that total is under the declared wall-clock ceiling
  * no context-token figures are produced (TST-0240's job)

Mechanically different from probe 2 (no A/B disable, no missing-instrument mutant).
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
    if "token" in text.lower() and "TST-0240" not in text:
        return "artifact reports tokens outside the TST-0240 pointer"
    return None


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        print(f"FAILED:TST-0237-probe1 {art_err}")
        return 1

    inst = H.measure_instrumented(H.N_TURNS)
    if not inst["all_components_positive"]:
        print("FAILED:TST-0237-probe1 a component median was zero")
        print(json.dumps(inst["parts_median_ms"], sort_keys=True))
        return 1
    if not inst["pass_reconcile_sum_vs_total"]:
        print(
            "FAILED:TST-0237-probe1 instrumented sum vs total "
            f"rel_err={inst['sum_vs_total_rel_err']:.4f} > {H.RECONCILE_TOLERANCE}"
        )
        return 1
    if not inst["under_ceiling"]:
        print(
            "FAILED:TST-0237-probe1 total "
            f"{inst['total_median_ms']:.3f}ms >= ceiling {H.DECLARED_CEILING_MS}ms"
        )
        return 1

    summary = {
        "pass": True,
        "probe": "probe1-instrumented-sum",
        "unit_id": H.UNIT,
        "n": inst["n"],
        "parts_median_ms": inst["parts_median_ms"],
        "instrumented_sum_ms": inst["instrumented_sum_ms"],
        "total_median_ms": inst["total_median_ms"],
        "sum_vs_total_rel_err": inst["sum_vs_total_rel_err"],
        "ceiling_ms": H.DECLARED_CEILING_MS,
        "under_ceiling": True,
        "token_counts_reported": False,
    }
    print(json.dumps(summary, sort_keys=True))
    parts = " ".join(f"{k}={v:.3f}ms" for k, v in inst["parts_median_ms"].items())
    print(
        f"sum={inst['instrumented_sum_ms']:.3f}ms total={inst['total_median_ms']:.3f}ms "
        f"rel_err={inst['sum_vs_total_rel_err']:.4f} {parts}"
    )
    print("SUCCESS:TST-0237-probe1 instrumented sum within 5% of total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
