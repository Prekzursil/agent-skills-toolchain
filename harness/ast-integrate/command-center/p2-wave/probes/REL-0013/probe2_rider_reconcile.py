#!/usr/bin/env python3
"""Probe 2: rider is its own class; inventory/component mismatch fails until itemised."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    inject_component,
    inject_node,
    load_components,
    load_provenance,
    rollup,
)

REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/REL-0013.json"
RIDER_PATH = (
    "command-center/p2-wave/probes/REL-0013/fixtures/licences/MIT-NO-ML-TRAINING.txt"
)


def fail(msg: str) -> int:
    print(f"FAILED:REL-0013-probe2 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact missing"
    try:
        doc = json.loads(ART.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"unparseable:{type(exc).__name__}"
    if not isinstance(doc, dict):
        return "artifact not object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    if "SUCCESS:REL-0013" not in ART.read_text(encoding="utf-8"):
        return "sentinel-absent"
    inv = doc.get("inventory") or {}
    for entry in inv.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        path = entry.get("licence_text_path")
        if path and not (REPO / str(path)).is_file():
            return f"cited licence missing {path}"
    return None


def main() -> int:
    err = check_artifact()
    if err:
        return fail(err)

    comps = load_components()
    prov = load_provenance()

    rider_comps = inject_component(
        comps, {"id": "dep-rider", "name": "mit-plus-noml", "kind": "component"}
    )
    rider_prov = inject_node(
        prov,
        {
            "id": "dep-rider",
            "name": "mit-plus-noml",
            "kind": "component",
            "disposition": "ADOPT-AS-IS",
            "declared_spdx": "MIT",
            "licence_text_path": RIDER_PATH,
        },
    )
    rider_run = rollup(REPO, components=rider_comps, provenance=rider_prov)
    rider = next((e for e in rider_run["entries"] if e["id"] == "dep-rider"), None)
    if rider is None:
        return fail("rider inject missing")
    if rider["licence_class"] == "permissive" or rider["licence_class"] == "MIT":
        return fail(f"rider folded into base {rider}")
    if rider["licence_class"] != "restrictive-rider":
        return fail(f"rider class {rider['licence_class']}")
    if rider["spdx"] == "MIT":
        return fail("rider SPDX folded to MIT")
    if rider["base_spdx"] != "MIT":
        return fail(f"base_spdx {rider['base_spdx']}")
    quote = rider.get("rider_quote") or ""
    if "train" not in quote.lower() and "ml" not in quote.lower():
        return fail(f"rider quote missing {quote!r}")
    if rider["block_reason"] != "restrictive-rider" or rider["gate"] != "BLOCK":
        return fail(f"rider not blocked {rider}")
    if rider_run["gate"]["promotion"] != "REFUSED":
        return fail("rider inject did not refuse promotion")
    if not rider_run["rider_entries"]:
        return fail("rider_entries empty")

    plain = next((e for e in rider_run["entries"] if e["id"] == "dep-mit"), None)
    if plain is None or plain["licence_class"] != "permissive":
        return fail(f"negative control MIT not permissive {plain}")
    if plain["licence_class"] == "restrictive-rider":
        return fail("extractor reports rider on plain MIT")

    dropped = rollup(REPO, components=comps, provenance=prov, skip_ids={"dep-mit"})
    rec = dropped["reconciliation"]
    if rec["status"] != "MISMATCH-UNITEMISED" or rec["ok"] is not False:
        return fail(f"unitemised mismatch not failed {rec}")
    if "dep-mit" not in rec["missing_from_inventory"]:
        return fail(f"missing not listed {rec['missing_from_inventory']}")
    if dropped["gate"]["promotion"] != "REFUSED":
        return fail("unitemised mismatch allowed promotion")

    itemised = rollup(
        REPO,
        components=comps,
        provenance=prov,
        skip_ids={"dep-mit"},
        itemisation=[
            {
                "id": "dep-mit",
                "side": "missing-from-inventory",
                "reason": "deliberate skip to prove mismatch is itemised rather than explained away",
            }
        ],
    )
    irec = itemised["reconciliation"]
    if irec["status"] != "MISMATCH-ITEMISED" or irec["ok"] is not True:
        return fail(f"itemised mismatch not accepted {irec}")
    if not any(r.get("id") == "dep-mit" for r in irec["itemised"]):
        return fail("itemisation dropped the id")
    if itemised["gate"]["promotion"] != "REFUSED":
        return fail("itemised gap still incomplete; promotion must stay refused")

    out = {
        "probe": "probe2-rider-reconcile",
        "unit_id": "REL-0013",
        "rider_class": rider["licence_class"],
        "rider_spdx": rider["spdx"],
        "rider_base_spdx": rider["base_spdx"],
        "rider_quote": rider["rider_quote"],
        "plain_mit_class": plain["licence_class"],
        "unitemised_status": rec["status"],
        "itemised_status": irec["status"],
        "pass": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "SUCCESS:REL-0013-probe2 rider is its own class; mismatch fails until itemised"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
