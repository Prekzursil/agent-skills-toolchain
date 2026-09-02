#!/usr/bin/env python3
"""Named probe 1: enumeration/read vs agent-visible rendering (display vs bytes)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    control_display_matches,
    listing_phantoms_on_naive_not_on_json,
    planted_control_display_fires,
    planted_rtl_on_ordinary,
)
from fixtures import ORDINARY, ensure_tree  # noqa: E402
from rendering import probe1_measure  # noqa: E402

UNIT = "ADV-0075"
ART = REPO / "command-center/adversarial/ADV-0075-filename-path-unicode-injection.json"
SCHEMA = REPO / "command-center/schema/injection-corpus-result.schema.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def probe1_payload(tree) -> dict:
    live = probe1_measure(tree)
    listing_ctrl = listing_phantoms_on_naive_not_on_json(live["true_names"])
    return {
        "probe": "probe1-enumerate-render",
        "unit_id": UNIT,
        "ordinary": live["ordinary"],
        "ordinary_display_matches_bytes": live["ordinary_display_matches_bytes"],
        "rtl_display_diverges": live["rtl_display_diverges"],
        "rtl_visual": live["rtl_visual"],
        "newline_splits_listing": live["newline_splits_listing"],
        "phantom_lines": live["phantom_lines"],
        "homoglyph_nfc_equal": live["homoglyph_nfc_equal"],
        "homoglyph_confusable_equal": live["homoglyph_confusable_equal"],
        "naive_fires": listing_ctrl["naive_fires"],
        "json_silent": listing_ctrl["json_silent"],
        "planted_control_fires": planted_control_display_fires(ORDINARY),
        "planted_rtl_fires": planted_rtl_on_ordinary(ORDINARY),
        "true_names_hex": live["true_names_hex"],
        "ordinary_payload": live["ordinary_payload"],
    }


def main() -> int:
    tree = ensure_tree()
    live = probe1_payload(tree)
    if not live["ordinary_display_matches_bytes"]:
        return fail("ordinary filename display diverged (comparison broken)", live)
    if not control_display_matches(ORDINARY, ORDINARY):
        return fail("control matcher broken")
    if not live["planted_control_fires"] or not live["planted_rtl_fires"]:
        return fail("planted-defect detector silent", live)
    if not live["rtl_display_diverges"]:
        return fail("RTL visual did not diverge from bytes", live)
    if not live["newline_splits_listing"] or not live["naive_fires"]:
        return fail("newline listing did not split", live)
    if not live["json_silent"]:
        return fail("JSON listing was not a silent control", live)
    if live["homoglyph_nfc_equal"]:
        return fail("latin and homoglyph names compared equal before fold")
    if not live["homoglyph_confusable_equal"]:
        return fail("confusable fold did not equate homoglyph twin", live)

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != UNIT:
            return fail("unit_id", doc.get("unit_id"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {doc.get('state')}")
        blob = json.dumps(doc)
        if "SUCCESS:ADV-0075" not in blob:
            return fail("sentinel absent")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            import jsonschema
        except ImportError:
            return fail("jsonschema missing")
        errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
        if errors:
            return fail("schema", [e.message for e in errors[:8]])
        targets = {t["id"]: t["verdict"] for t in doc.get("targets") or []}
        if targets.get("rtl-override") != "CONFIRMED":
            return fail("artifact rtl-override verdict", targets)
        if targets.get("embedded-newline") != "CONFIRMED":
            return fail("artifact embedded-newline verdict", targets)
        art_p1 = None
        for item in doc.get("named_probes") or []:
            if item.get("id") == "probe1":
                art_p1 = item
                break
        if not art_p1 or "rtl_display_diverges" not in (art_p1.get("raw_output") or ""):
            return fail("artifact missing probe1 raw_output")

    print(json.dumps(live, sort_keys=True))
    print("SUCCESS:ADV-0075-probe1 enumerate/render display-vs-bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
