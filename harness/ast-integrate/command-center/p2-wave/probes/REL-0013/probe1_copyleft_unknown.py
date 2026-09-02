#!/usr/bin/env python3
"""Probe 1: copyleft-into-permissive blocks; UNKNOWN does not default to MIT."""
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
GPL_PATH = "command-center/p2-wave/probes/REL-0013/fixtures/licences/GPL-3.0.excerpt.txt"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0013-probe1 {msg}")
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
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:REL-0013" not in text:
        return "sentinel-absent"
    return None


def main() -> int:
    err = check_artifact()
    if err:
        return fail(err)

    comps = load_components()
    prov = load_provenance()
    baseline = rollup(REPO, components=comps, provenance=prov)
    if baseline["gate"]["promotion"] != "ALLOWED":
        return fail(f"baseline not ALLOWED {baseline['gate']}")
    if baseline["reconciliation"]["status"] != "MATCH":
        return fail(f"baseline reconcile {baseline['reconciliation']}")
    hist = baseline["classes_histogram"]
    if hist.get("restrictive-rider") or hist.get("unknown-terms"):
        return fail(f"baseline unclean histogram {hist}")
    if "CLEAN-ROOM-REIMPLEMENT" not in baseline["disposition_histogram"]:
        return fail("baseline missing CLEAN-ROOM-REIMPLEMENT")
    cr = [e for e in baseline["entries"] if e["id"] == "wf-cleanroom-gpl"]
    if len(cr) != 1 or cr[0]["carried_into_release"] is not False:
        return fail(f"clean-room must not be carried {cr}")
    if cr[0]["gate"] != "ALLOW":
        return fail("clean-room GPL must not block outbound MIT")

    copyleft_comps = inject_component(
        comps, {"id": "dep-gpl", "name": "copyleft-inject", "kind": "component"}
    )
    copyleft_prov = inject_node(
        prov,
        {
            "id": "dep-gpl",
            "name": "copyleft-inject",
            "kind": "component",
            "disposition": "ADOPT-AS-IS",
            "declared_spdx": "GPL-3.0-only",
            "licence_text_path": GPL_PATH,
        },
    )
    copyleft = rollup(REPO, components=copyleft_comps, provenance=copyleft_prov)
    gpl = next((e for e in copyleft["entries"] if e["id"] == "dep-gpl"), None)
    if gpl is None:
        return fail("copyleft inject missing from inventory")
    if gpl["licence_class"] != "strong-copyleft":
        return fail(f"copyleft class {gpl['licence_class']}")
    if gpl["block_reason"] != "licence-incompatible" or gpl["gate"] != "BLOCK":
        return fail(f"copyleft not blocked {gpl}")
    if copyleft["gate"]["promotion"] != "REFUSED":
        return fail("copyleft inject did not refuse promotion")
    if "licence-incompatible" not in copyleft["gate"]["failure_classes"]:
        return fail(f"failure_classes {copyleft['gate']['failure_classes']}")

    unknown_comps = inject_component(
        comps,
        {"id": "dep-unknown", "name": "unknown-inject", "kind": "component"},
    )
    unknown_prov = inject_node(
        prov,
        {
            "id": "dep-unknown",
            "name": "unknown-inject",
            "kind": "component",
            "disposition": "ADOPT-AS-IS",
            "declared_spdx": "MIT",
            "licence_text_path": None,
        },
    )
    unknown = rollup(REPO, components=unknown_comps, provenance=unknown_prov)
    unk = next((e for e in unknown["entries"] if e["id"] == "dep-unknown"), None)
    if unk is None:
        return fail("unknown inject missing from inventory")
    if unk["licence_class"] == "permissive" or unk["spdx"] == "MIT":
        return fail(f"UNKNOWN defaulted to permissive {unk}")
    if unk["licence_class"] != "unknown-terms" or unk["spdx"] != "UNKNOWN":
        return fail(f"UNKNOWN class {unk}")
    if not unk.get("unknown_reason"):
        return fail("UNKNOWN missing individual reason")
    if unk["block_reason"] != "unknown-terms" or unk["gate"] != "BLOCK":
        return fail(f"UNKNOWN not blocked {unk}")
    if unknown["gate"]["promotion"] != "REFUSED":
        return fail("UNKNOWN inject did not refuse promotion")
    if "unknown-terms" not in unknown["gate"]["failure_classes"]:
        return fail(f"failure_classes {unknown['gate']['failure_classes']}")
    listed = [u["id"] for u in unknown["unknown_entries"]]
    if "dep-unknown" not in listed:
        return fail(f"unknown_entries {listed}")

    out = {
        "probe": "probe1-copyleft-unknown",
        "unit_id": "REL-0013",
        "baseline_promotion": baseline["gate"]["promotion"],
        "copyleft_blocked": True,
        "copyleft_class": gpl["licence_class"],
        "unknown_blocked": True,
        "unknown_class": unk["licence_class"],
        "unknown_not_defaulted_to_mit": True,
        "unknown_reason": unk["unknown_reason"],
        "clean_room_gpl_allowed": True,
        "pass": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:REL-0013-probe1 copyleft inject blocks; UNKNOWN does not default to MIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
