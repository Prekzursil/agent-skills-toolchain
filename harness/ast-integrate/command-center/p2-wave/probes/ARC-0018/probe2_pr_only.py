#!/usr/bin/env python3
"""Probe 2: PR-ONLY cross-check and independent re-derivation.

Mechanically different from probe 1:
  * different data field: second_party_required (not classification, not the walker)
  * different source: WORK-UNIT-CATALOG.json OQ-3 answer (not the necessity walk)

Re-derives headline.dead_weight_count from the static second_party_required
table. Must land inside the stated error band (exact integer, band 0).
If this reading disagrees with COST.json, fail rather than pick one.

Also asserts the cost model does not price a public marketplace: every named
item has priced_as_public_marketplace false, headline.public_marketplace_priced
is false, and no canary/public-registry line item carries a cost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lifecycle import ITEM_SPEC, NAMED_MARKETPLACE  # noqa: E402

ART = REPO / "command-center/phase3/A3/COST.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
OWNER_DECISIONS = REPO / "command-center/OWNER-DECISIONS.md"
PUBLIC_COST_KEYS = (
    "public_registry_hosting",
    "canary_channel",
    "marketplace_publish",
    "moderation_staff",
    "dispute_tribunal",
)


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0018-probe2 {msg}")
    return 1


def catalog_oq3() -> tuple[int, str, str]:
    text = CATALOG.read_text(encoding="utf-8")
    needle = '"id": "OQ-3"'
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit("FAILED:ARC-0018-probe2 OQ-3 missing from catalog")
    line = text[:idx].count("\n") + 1
    data = json.loads(text)
    row = None
    for item in data.get("owner_questions") or data.get("open_questions") or []:
        if isinstance(item, dict) and item.get("id") == "OQ-3":
            row = item
            break
    if row is None:
        # catalog stores questions under a top-level key; search any list
        def walk(obj):
            if isinstance(obj, dict):
                if obj.get("id") == "OQ-3" and "answer" in obj:
                    return obj
                for v in obj.values():
                    found = walk(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for v in obj:
                    found = walk(v)
                    if found:
                        return found
            return None

        row = walk(data)
    if not isinstance(row, dict):
        raise SystemExit("FAILED:ARC-0018-probe2 OQ-3 row not found")
    answer = str(row.get("answer") or "")
    detail = str(row.get("answer_detail") or "")
    return line, answer, detail


def main() -> int:
    if not ART.is_file():
        return fail("COST.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0018" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    line, answer, detail = catalog_oq3()
    if not answer.upper().startswith("PR-ONLY"):
        return fail(f"OQ-3 answer is not PR-ONLY: {answer!r}")
    if "public marketplace" not in detail.lower() and "PUBLIC MARKETPLACE" not in detail:
        # answer_detail must still rule out public marketplace
        if "never a public marketplace" not in detail.lower():
            return fail("OQ-3 detail does not rule out public marketplace")
    print(f"pr_only_anchor command-center/WORK-UNIT-CATALOG.json:{line} answer={answer!r}")

    owner_md = OWNER_DECISIONS.is_file()
    recorded = (doc.get("inputs_on_this_tree") or {}).get(
        "command-center/OWNER-DECISIONS.md"
    )
    if owner_md:
        od_text = OWNER_DECISIONS.read_text(encoding="utf-8")
        if "PR-ONLY" not in od_text:
            return fail("OWNER-DECISIONS.md present but has no PR-ONLY token")
        if recorded is not True:
            return fail("OWNER-DECISIONS.md present but COST.json did not record it")
        print("owner_decisions.md present=True contains=PR-ONLY")
    else:
        print("owner_decisions.md present=False using catalog OQ-3")
        if recorded is not False:
            return fail("COST.json did not record OWNER-DECISIONS.md as absent")

    # Independent re-derivation: count second_party_required on the named 7,
    # reading ITEM_SPEC (not COST.json classification).
    derived = sum(
        1 for i in NAMED_MARKETPLACE if ITEM_SPEC[i]["second_party_required"]
    )
    art_n = (doc.get("headline") or {}).get("dead_weight_count")
    band = int(((doc.get("headline") or {}).get("error_band") or {}).get("dead_weight_count") or 0)
    if art_n is None:
        return fail("headline.dead_weight_count missing")
    if abs(int(art_n) - derived) > band:
        return fail(
            f"re-derive disagree artifact={art_n} second_party_required={derived} band={band}"
        )
    print(f"rederive dead_weight_count artifact={art_n} second_party_required={derived} band={band}")

    if doc.get("headline", {}).get("public_marketplace_priced") is not False:
        return fail("headline.public_marketplace_priced is not false")

    named_rows = [
        r
        for r in (doc.get("machinery") or [])
        if isinstance(r, dict) and r.get("id") in NAMED_MARKETPLACE
    ]
    if len(named_rows) != 7:
        return fail(f"expected 7 named machinery rows, got {len(named_rows)}")
    for row in named_rows:
        if row.get("priced_as_public_marketplace") is not False:
            return fail(f"{row.get('id')} priced_as_public_marketplace")
        live_flag = bool(ITEM_SPEC[row["id"]]["second_party_required"])
        if row.get("second_party_required") is not live_flag:
            return fail(f"{row.get('id')} second_party_required field drifted")

    for key in PUBLIC_COST_KEYS:
        blob = doc.get("priced_line_items") or {}
        if key in blob and float(blob[key] or 0) > 0:
            return fail(f"priced public line item {key}={blob[key]}")
        if key in doc and isinstance(doc[key], (int, float)) and doc[key] > 0:
            return fail(f"top-level public cost {key}")

    release = str(doc.get("release_mode") or "")
    if release != "PR-ONLY":
        return fail(f"release_mode {release!r} is not PR-ONLY")

    payload = {
        "pass": True,
        "probe": "probe2-pr-only",
        "unit_id": "ARC-0018",
        "oq3_line": line,
        "oq3_answer": answer,
        "owner_decisions_md": owner_md,
        "dead_weight_count": derived,
        "public_marketplace_priced": False,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:ARC-0018-probe2 PR-ONLY cross-check and independent re-derivation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
