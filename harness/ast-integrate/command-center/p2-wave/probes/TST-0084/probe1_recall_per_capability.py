#!/usr/bin/env python3
"""Named probe 1: per-capability recall on the committed labelled set.

Recomputes the matrix from repertoire.json + labelled_set.json. Does not trust
the receipt's headline average. Requires every labelled capability to appear as
its own recall/precision row, and requires the rarely-used skills to be selected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import metrics as M  # noqa: E402
import scenario as S  # noqa: E402
from router import FALLBACK_ID  # noqa: E402

OUT = HERE / "probe1-recall.raw.json"
ART = REPO / "command-center/receipts/TST-0084.json"
RARE = ("skill.nul-device-census", "skill.windows-long-path")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0084-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if doc.get("unit_id") != "TST-0084":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:TST-0084" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    ev = S.evaluate()
    table = ev["tables"]["full"]
    labelled = ev["labelled"]
    gold_ids = sorted({c["expected"] for c in labelled})
    missing = [g for g in gold_ids if g not in table]
    if missing:
        return fail(f"per-capability rows missing {missing}")

    zeros = M.zero_recall_capabilities(table)
    if zeros:
        return fail(f"fusion zero-recall {zeros}")

    for cid in RARE:
        row = table[cid]
        if row["gold"] < 1 or row["recall"] != 1.0:
            return fail(f"rare {cid} gold={row['gold']} recall={row['recall']}")
        hits = [p for p in ev["policies"]["full"] if p["expected"] == cid]
        if not hits or any(p["capability_id"] != cid for p in hits):
            return fail(f"rarely-used skill {cid} not selected")

    receipt_rows = {
        r["capability_id"]: r for r in (doc.get("per_capability") or {}).get("full") or []
    }
    if not receipt_rows:
        return fail("receipt per_capability.full missing")
    for cid in gold_ids:
        live = table[cid]["recall"]
        claimed = receipt_rows.get(cid, {}).get("recall")
        if claimed != live:
            return fail(f"receipt/live recall mismatch {cid} {claimed} vs {live}")

    headline_only = doc.get("headline", {}).get("full_micro_recall")
    if headline_only is None:
        return fail("headline micro missing")
    if len(table) < 2:
        return fail("only aggregate")

    # Negative rows exist in the gold set so fallback is a labelled capability.
    if FALLBACK_ID not in table or table[FALLBACK_ID]["gold"] < 1:
        return fail("fallback not labelled")

    payload = {
        "probe": "probe1-recall-per-capability",
        "unit_id": "TST-0084",
        "gold_capabilities": gold_ids,
        "per_capability": M.per_capability_table(labelled, ev["policies"]["full"]),
        "macro_recall": ev["macros"]["full"],
        "micro_recall": ev["micros"]["full"],
        "rare_selected": True,
        "zeros": zeros,
        "computed_not_asserted": True,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "macro": ev["macros"]["full"],
                "micro": ev["micros"]["full"],
                "n_capabilities": len(table),
                "rare": list(RARE),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0084-probe1 per-capability recall recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
