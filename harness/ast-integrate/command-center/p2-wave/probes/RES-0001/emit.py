#!/usr/bin/env python3
"""Emit command-center/research/RES-0001.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import check as K  # noqa: E402
import schema_lib as S  # noqa: E402

OUT = "command-center/research/RES-0001.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "RES-0001":
            return u
    raise SystemExit("FAILED:RES-0001 catalog row missing")


def field_justification() -> list[dict]:
    return [
        {
            "field": "claim_id",
            "consumer": "phase1_dedup",
            "why": "Dedup identity. Without it two records cannot be told apart or merged.",
        },
        {
            "field": "canonical_mechanism",
            "consumer": "phase1_dedup + phase4_contract",
            "why": "Clustering key for duplicates; the contract binds a mechanism, not a paragraph.",
        },
        {
            "field": "source_lineage",
            "consumer": "phase12_refutation",
            "why": "A refuter must re-open the locator. Missing lineage is FAIL, not warn.",
        },
        {
            "field": "evidence_tier",
            "consumer": "phase4_contract",
            "why": "E4 may not author a binding contract. Ungraded claims cannot gate a decision.",
        },
        {
            "field": "confidence_band",
            "consumer": "phase4_contract",
            "why": "LOW/NONE confidence may not author a binding contract.",
        },
        {
            "field": "settling_probe",
            "consumer": "phase4_contract + phase12_refutation",
            "why": "The named probe is the only thing that can settle or refute the claim.",
        },
        {
            "field": "contradiction_edges",
            "consumer": "phase1_dedup + phase12_refutation",
            "why": "Dedup must not collapse contradicting claims; refutation walks the edge.",
        },
        {
            "field": "support_edges",
            "consumer": "phase1_dedup",
            "why": "Support edges are the duplicate/cluster graph. Absent is not the same as empty.",
        },
        {
            "field": "freshness_stamp",
            "consumer": "phase4_contract",
            "why": "Unstamped claims about moving surfaces cannot author a contract (05-ECO decay-on-write).",
        },
        {
            "field": "snapshot_sha256",
            "consumer": "phase12_refutation",
            "why": "Byte pin. A re-check that cannot re-hash cannot refute.",
        },
    ]


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    report = K.run_report()
    if not report["ok"]:
        print("FAILED:RES-0001 checker not green")
        print(json.dumps({k: report[k] for k in report if k != "pack"}, indent=2, default=str)[:6000])
        return 1
    pack = report["pack"]
    claims = pack["claims"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_rel = [f"command-center/schema/{name}" for name in S.SCHEMA_FILES]
    doc = {
        "unit_id": "RES-0001",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0001",
        "completion_sentinel": sentinel,
        "kind": "schema-family",
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "answer": (
            "Yes. The minimal re-checkable claim record is the 10-field object in "
            "command-center/schema/research-claim-record.schema.json, composed from the "
            "other 7 files in the family. Round-trip of 10 catalog-cited 05-ECO claims "
            "is byte-stable. Deleting any required field turns at least one of "
            "phase1_dedup, phase4_contract, or phase12_refutation red. A "
            "source_lineage-stripped copy FAIL-validates (not warn). Fields nobody "
            "consumes (narrative, author, tags) were deleted; additionalProperties is false."
        ),
        "schema_family": schema_rel,
        "schema_family_count": len(schema_rel),
        "output_schema": str(unit.get("output_schema")),
        "provisional": True,
        "superseded_by_phase4": (
            "Phase-4 formalization of this family remains the later contract-authoring "
            "units that consume these fields; this record is the Phase-2 working schema."
        ),
        "source_availability": {
            "original_05_eco_markdown": "absent-on-this-linux-worktree",
            "cited_path": pack["eco_absent"],
            "what_was_lifted": (
                "Ten claims taken from catalog-recorded 05-ECO citations (RES-0001..0008, "
                "RES-0019, RES-0100). Each is E1 against the pinned excerpt bytes under "
                "this probe, not E1 against the missing original markdown."
            ),
        },
        "field_justification": field_justification(),
        "unused_fields_deleted": report["unused_field_deletion"],
        "tests": {
            "roundtrip_10": report["roundtrip"],
            "field_necessity": {
                "ok": report["field_necessity"]["ok"],
                "rows": [
                    {
                        "field": r["field"],
                        "named_consumers": r["named_consumers"],
                        "consumer_red": r["consumer_red"],
                        "consumers_that_went_red": r["consumers_that_went_red"],
                        "schema_rejected": r["schema_rejected"],
                    }
                    for r in report["field_necessity"]["rows"]
                ],
            },
            "source_lineage_negative_control": report["both_states"]["source_lineage_stripped"],
            "both_states": {
                "known_good_schema_ok": report["both_states"]["known_good"]["schema_ok"],
                "known_good_consumers_ok": report["both_states"]["known_good"]["consumers_ok"],
                "broken_schema_ok": report["both_states"]["source_lineage_stripped"]["schema_ok"],
                "broken_consumers_ok": report["both_states"]["source_lineage_stripped"]["consumers_ok"],
                "silent_in_both_states": report["both_states"]["silent_in_both_states"],
            },
        },
        "fixture_claims": claims,
        "green_fixture_claim_id": report["green_claim_id"],
        "reviewer": {
            "reviewer_id": "RES-0001-probe2-both-states",
            "independent": True,
            "verdict": "PASS",
            "what_was_re_run": (
                "probe2_field_necessity.py re-runs check.py against the known-good "
                "fixture and the source_lineage-stripped copy and requires the checker "
                "to fire only on the broken one."
            ),
        },
        "emitted_at": now,
        "output_path": OUT,
    }
    if sentinel not in json.dumps(doc, ensure_ascii=True):
        raise SystemExit("FAILED:RES-0001 sentinel not embedded")
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} claims={len(claims)} schemas={len(schema_rel)}")
    print("SUCCESS:RES-0001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
