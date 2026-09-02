#!/usr/bin/env python3
"""Named probe 1: live token curve at 10/100/500 and budget at 500.

Mechanism: re-run tools.router.inject on fresh catalogues and compare the
measured payload token counts to the receipt. Does not re-derive the
variance band (that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import curve as C  # noqa: E402
from tools.router.inject import DEFAULT_CEILING, count_payload_tokens  # noqa: E402

ART = REPO / "command-center/receipts/TST-0085.json"
SENTINEL = "SUCCESS:TST-0085"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0085-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0085":
        print("FAILED:TST-0085-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0085-probe1 self-declared", doc.get("state"))
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0085-probe1 sentinel absent")
        return 1

    live = C.measure_all()
    if not live["budget_held"]:
        print("FAILED:TST-0085-probe1 budget breached", live["at_500_max_injected_tokens"])
        return 1
    if live["at_500_max_injected_tokens"] > DEFAULT_CEILING:
        print("FAILED:TST-0085-probe1 ceiling", live["at_500_max_injected_tokens"])
        return 1
    if not live["sublinear"]["pass"]:
        print("FAILED:TST-0085-probe1 growth not sublinear")
        print(json.dumps(live["sublinear"], sort_keys=True))
        return 1
    if not live["recall_ok"]:
        print("FAILED:TST-0085-probe1 labelled skill missed")
        return 1
    if not live["nomatch_ok"]:
        print("FAILED:TST-0085-probe1 no-match injected tokens")
        return 1

    art_budget = doc.get("budget") or {}
    if art_budget.get("held") is not True:
        print("FAILED:TST-0085-probe1 receipt budget.held is not true")
        return 1
    if int(art_budget.get("at_500_max_injected_tokens") or -1) != live["at_500_max_injected_tokens"]:
        print(
            "FAILED:TST-0085-probe1 receipt 500-max mismatch "
            f"art={art_budget.get('at_500_max_injected_tokens')} live={live['at_500_max_injected_tokens']}"
        )
        return 1

    counts = [int(x) for x in (doc.get("installed_counts") or [])]
    if counts != [10, 100, 500]:
        print("FAILED:TST-0085-probe1 installed_counts", counts)
        return 1

    # Receipt raw_runs must contain the three sizes; recount payloads live.
    by_key = {
        (int(r["installed_count"]), str(r["query_id"])): r
        for r in (doc.get("raw_runs") or [])
        if isinstance(r, dict)
    }
    for n in (10, 100, 500):
        row = by_key.get((n, "q-ambiguous"))
        if not row:
            print("FAILED:TST-0085-probe1 missing ambiguous raw_run at", n)
            return 1
        payload = str(row.get("payload") or "")
        recounted = count_payload_tokens(payload)
        if recounted != int(row["injected_tokens"]):
            print("FAILED:TST-0085-probe1 payload recount", n, recounted, row["injected_tokens"])
            return 1
        if recounted != live["ambiguous_topk"][n]:
            print(
                "FAILED:TST-0085-probe1 live/receipt ambiguous mismatch",
                n,
                recounted,
                live["ambiguous_topk"][n],
            )
            return 1
        if recounted <= 0:
            print("FAILED:TST-0085-probe1 ambiguous tokens were zero at", n)
            return 1

    test_ids = {t.get("id"): t.get("result") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for required in (
        "test_injected_tokens_stay_under_budget_at_500_capabilities",
        "test_growth_is_sublinear_in_the_installed_count",
    ):
        if test_ids.get(required) != "PASS":
            print("FAILED:TST-0085-probe1 receipt test not PASS", required, test_ids.get(required))
            return 1

    out = {
        "probe": "probe1-budget-curve",
        "unit_id": "TST-0085",
        "pass": True,
        "ceiling": DEFAULT_CEILING,
        "at_500_max_injected_tokens": live["at_500_max_injected_tokens"],
        "ambiguous_topk": {str(k): v for k, v in live["ambiguous_topk"].items()},
        "sublinear": live["sublinear"],
        "budget_held": True,
        "labelled_recall_ok": True,
        "no_match_silent": True,
    }
    (HERE / "probe1-budget-curve.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0085-probe1 budget held at 500; growth sublinear at 10/100/500")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
