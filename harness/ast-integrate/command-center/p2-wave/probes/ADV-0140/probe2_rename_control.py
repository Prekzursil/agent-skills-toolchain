#!/usr/bin/env python3
"""Named probe 2: rename control + independent effect re-classification."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import effects as E  # noqa: E402
import enumerate as EN  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0140-owner-gate-bypass.json"
SCHEMA = REPO / "command-center/schema/gate-reachability.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0140-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0140-probe2 self-declared", doc.get("state"))
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:ADV-0140-probe2 schema", errs[0].message)
        return 1

    rename = EN.rename_control()
    # Independent: classify the mutated source here without trusting emit's copy.
    src = (HERE / "fixtures" / "gated_publish.py").read_text(encoding="utf-8")
    mutated = src.replace("def upload_distribution", "def dispatch_bytes_to_index")
    bags = E.classify_module(mutated, "probe2-renamed.py")
    hit = [b for b in bags if "public_publishing" in b.effects()]
    name_hit = E.name_based_would_hit("dispatch_bytes_to_index")
    effect_hit = bool(hit)
    ok = (
        rename["effect_still_classified"]
        and rename["name_based_lost_renamed_sink"]
        and effect_hit
        and not name_hit
        and doc.get("tests", {}).get("rename_control_still_classified") is True
        and doc.get("reviewer", {}).get("independent") is True
    )
    payload = {
        "probe": "probe2-rename-control-independent-review",
        "unit_id": "ADV-0140",
        "reviewer_id": "ADV-0140-probe2-rename-control",
        "pass": bool(ok),
        "effect_still_classified": effect_hit,
        "name_based_hit_on_renamed": name_hit,
        "renamed_symbol": "dispatch_bytes_to_index",
        "urls": hit[0].urls if hit else [],
        "schema_ok": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:ADV-0140-probe2 rename control")
        return 1
    print(
        "SUCCESS:ADV-0140-probe2 effect classifier kept renamed sink; "
        "name-based foil lost it"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
