#!/usr/bin/env python3
"""Dump resolved-view evidence for IMP-0436 three-unit fixture catalog.

Writes effective value + provenance (default|override|explicit-null|unset)
per overrideable field. Also re-checks the live catalog admits overrides and
that deleting defaults turns validate red.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import validate as val  # noqa: E402

PROBE = Path(__file__).resolve().parent
FIXTURE = PROBE / "fixtures" / "override-catalog.json"
OUT = PROBE / "resolved-view.json"
MUT_OUT = PROBE / "defaults-mutation.json"


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    defaults = fixture["defaults"]
    units = {u["id"]: u for u in fixture["items"]}
    wanted = ("FIX-ALL-DEFAULTS", "FIX-THREE-OVERRIDES", "FIX-ALL-NINE")
    views = []
    for uid in wanted:
        views.append(cat.resolve_unit(units[uid], defaults))

    # Live catalog: prove an override on a scratch copy of one item wins.
    live = cat.load()
    scratch = copy.deepcopy(live)
    sample = scratch["items"][0]
    sample_id = sample["id"]
    sample["timeout_seconds"] = 42
    sample["reviewer_requirement"] = None  # explicit-null
    live_probe = {
        "sample_id": sample_id,
        "timeout": cat.resolve_field(sample, scratch["defaults"], "timeout_seconds"),
        "reviewer_requirement": cat.resolve_field(
            sample, scratch["defaults"], "reviewer_requirement"
        ),
        "assignment_still_default": cat.resolve_field(
            sample, scratch["defaults"], "assignment"
        ),
    }

    # Mutation: delete defaults on live scratch → V-DEFAULTS without --require-complete.
    deleted = copy.deepcopy(live)
    del deleted["defaults"]
    v_del, _ = val.validate(deleted, require_complete=False)
    v_ok, _ = val.validate(live, require_complete=False)
    single = copy.deepcopy(live)
    del single["defaults"]["timeout_seconds"]
    v_single, _ = val.validate(single, require_complete=False)

    mutation = {
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "good_state_violations": len(v_ok),
        "delete_defaults_block": {
            "violations": len(v_del),
            "checks": sorted({x["check"] for x in v_del}),
            "fired": any(x["check"] == "V-DEFAULTS" for x in v_del),
            "sample_detail": next(
                (x["detail"] for x in v_del if x["check"] == "V-DEFAULTS"), ""
            ),
        },
        "delete_single_default_field": {
            "field": "timeout_seconds",
            "violations": len(v_single),
            "fired": any(x["check"] == "V-DEFAULTS" for x in v_single),
            "sample_detail": next(
                (x["detail"] for x in v_single if x["check"] == "V-DEFAULTS"), ""
            ),
        },
        "both_states": len(v_ok) == 0
        and any(x["check"] == "V-DEFAULTS" for x in v_del)
        and any(x["check"] == "V-DEFAULTS" for x in v_single),
    }
    MUT_OUT.write_text(
        json.dumps(mutation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    doc = {
        "unit_id": "IMP-0436",
        "measured_at": mutation["measured_at"],
        "precedence_rule": (
            "Unit-declared key wins over catalog.defaults (including explicit "
            "JSON null → provenance=explicit-null, no fall-through). Missing "
            "key → provenance=default. Enforced by "
            "tools/command-center/catalog.py:resolve_field; V-DEFAULTS in "
            "validate.py fails closed if the defaults block is deleted while "
            "items rely on it (no --require-complete needed)."
        ),
        "approach": (
            "Resolved-view dump uses fixtures/override-catalog.json (three "
            "representative units) rather than wholesale-mutating the live "
            "2007 work_units / 103 items. Live override admission is probed "
            "via a scratch copy of one item."
        ),
        "overrideable_fields": list(cat.OVERRIDEABLE_DEFAULT_FIELDS),
        "units": views,
        "live_scratch_override_probe": live_probe,
        "defaults_mutation": mutation,
        "sentinel_ready_when_dual_reviewed": "SENTINEL:IMP-0436:CATALOG-OVERRIDES-ENFORCED",
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ok = (
        mutation["both_states"]
        and all(v["fields"][f]["provenance"] == "default" for f in cat.OVERRIDEABLE_DEFAULT_FIELDS for v in [views[0]])
        and sum(
            1
            for f in cat.OVERRIDEABLE_DEFAULT_FIELDS
            if views[1]["fields"][f]["provenance"] == "override"
        )
        == 3
        and views[2]["fields"]["timeout_seconds"]["provenance"] == "explicit-null"
        and live_probe["timeout"]["provenance"] == "override"
        and live_probe["reviewer_requirement"]["provenance"] == "explicit-null"
        and live_probe["assignment_still_default"]["provenance"] == "default"
    )
    print(json.dumps({"ok": ok, "out": str(OUT.relative_to(REPO)), "mutation_both_states": mutation["both_states"]}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
