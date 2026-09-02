#!/usr/bin/env python3
"""Probe 1: inventory check counted mechanically.

Every council capability maps to a workflow primitive or is listed as a
required extension. Catalog anchors are re-checked. A planted unmapped row
must fail the same check (negative control is not vacuous).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import capabilities as C  # noqa: E402
import compile as K  # noqa: E402
import plane as P  # noqa: E402

OUT = HERE / "probe1-inventory.raw.json"
ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0124-council-as-a-first-class-workflow-type-on-the-single-contr.md"
)


def fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        print(json.dumps(payload, indent=2, default=str)[:4000])
    print(f"FAILED:CNL-0124-probe1 {msg}")
    return 1


def main() -> int:
    rows = C.inventory_rows()
    summary = C.inventory_summary(rows)
    anchors = C.verify_catalog_anchors()
    families = C.family_coverage()
    prim = P.primitives_agree()
    planted = C.inventory_summary(C.plant_unmapped(rows))

    mapped = K.duplicate_probe(K.load_fixture("mapped-council.json"))
    standing = K.duplicate_probe(K.load_fixture("standing-watch.json"))
    nested = K.duplicate_probe(K.load_fixture("nested.json"))
    anon = K.duplicate_probe(K.load_fixture("anonymous.json"))

    report = {
        "probe": "probe1-inventory",
        "unit_id": "CNL-0124",
        "summary": summary,
        "anchors_ok": anchors["ok"],
        "anchor_misses": anchors["misses"],
        "families": families,
        "primitives": {
            "ok": prim["ok"],
            "missing_from_catalog_parse": prim["missing_from_catalog_parse"],
        },
        "planted_unmapped": {
            "n_unmapped": planted["n_unmapped"],
            "ok": planted["ok"],
            "unmapped_ids": planted["unmapped_ids"],
        },
        "mapped_council_gate": mapped["gate"],
        "standing_watch_extensions": standing["extensions_named"],
        "standing_watch_gate": standing["gate"],
        "nested_kinds": nested["compile"]["node_kinds"],
        "anonymous_extensions": anon["extensions_named"],
        "no_home": C.NO_HOME_ID,
    }

    if not prim["ok"]:
        return fail("catalog primitive parse missed IMP node types", report)
    if not anchors["ok"]:
        return fail("catalog anchors missed", report)
    if not families["ok"]:
        return fail(f"family coverage missing {families['missing']}", report)
    if summary["n_capabilities"] != 20:
        return fail(f"expected 20 capabilities, got {summary['n_capabilities']}", report)
    if not summary["ok"] or summary["n_unmapped"] != 0:
        return fail(f"unmapped capabilities {summary['unmapped_ids']}", report)
    if summary["no_home_capability"] != C.NO_HOME_ID:
        return fail("no-home capability is not CAP-STANDING", report)
    if sorted(summary["required_extensions_named"]) != [
        "BallotReduce",
        "BlindEnvelope",
        "Watch",
    ]:
        return fail("required extensions set drifted", report)
    if planted["ok"] or "CAP-PLANTED-UNMAPPED" not in planted["unmapped_ids"]:
        return fail("planted unmapped row did not fail inventory (check vacuous)", report)
    if mapped["gate"] != "PASS" or mapped["over_one"]:
        return fail("mapped home-plane council did not PASS", report)
    if "BallotReduce" not in mapped["extensions_named"]:
        return fail("majority council did not name BallotReduce", report)
    if standing["gate"] != "PASS":
        return fail("standing-watch on agentspec must PASS (Watch is not a scheduler)", report)
    if "Watch" not in standing["extensions_named"]:
        return fail("standing-watch compile did not name Watch", report)
    if "Subworkflow" not in nested["compile"]["node_kinds"]:
        return fail("nested council did not compile to Subworkflow", report)
    if "BlindEnvelope" not in anon["extensions_named"]:
        return fail("anonymous council did not name BlindEnvelope", report)

    scheduler_needing = [r["id"] for r in rows if r.get("needs_own_scheduler")]
    if scheduler_needing:
        return fail(f"inventory listed a scheduler-needing cap as allowed {scheduler_needing}", report)

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        pub = doc.get("inventory") or {}
        for key in ("n_capabilities", "n_mapped", "n_required_extension", "n_unmapped"):
            if pub.get(key) != summary[key]:
                return fail(
                    f"artifact inventory {key}={pub.get(key)} != live {summary[key]}",
                    report,
                )
        if doc.get("no_home_capability") != C.NO_HOME_ID:
            return fail("artifact no_home_capability drifted", report)

    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("summary", "no_home", "mapped_council_gate", "standing_watch_gate")}, indent=2))
    print(
        "SUCCESS:CNL-0124-probe1 "
        f"n={summary['n_capabilities']} mapped={summary['n_mapped']} "
        f"ext={summary['n_required_extension']} unmapped={summary['n_unmapped']} "
        f"no_home={C.NO_HOME_ID}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
