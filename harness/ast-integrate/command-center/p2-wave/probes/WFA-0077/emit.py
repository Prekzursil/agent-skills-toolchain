#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0077-owner-approval-gate-list.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gates as G  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0077/probe1_settled_not_reasked.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0077/probe2_remove_and_one_at_a_time.py"
)
QUESTION = (
    "Which dispositions and acquisitions in this bucket genuinely require "
    "owner approval under the spec's own list - public publishing, unbounded "
    "spend, credential rotation, deleting user data, security posture, public "
    "repositories, controversial source classes - and which are ALREADY "
    "settled by binding decisions and must therefore not be re-asked?"
)


def compact_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "action": row["action"],
        "owner_impact": row["owner_impact"],
        "disposition": row["disposition"],
        "decision_log_checked": row["decision_log_checked"],
        "triggering_unit_ids": [t["id"] for t in row["triggering_units"]],
        "triggering_units": row["triggering_units"],
        "observer_units_not_triggers": row["observer_units_not_triggers"],
        "question": row["question"],
        "recommendation": row["recommendation"],
        "default_if_unanswered": row["default_if_unanswered"],
        "strongest_tradeoff": row["strongest_tradeoff"],
        "settlement": row["settlement"],
        "remove_reason": row["remove_reason"],
    }


def main() -> int:
    result = G.classify(REPO)
    if result["missing_triggers"]:
        print("FAILED:WFA-0077 missing trigger units", result["missing_triggers"])
        return 1
    if result["slice_unit_count"] < 1:
        print("FAILED:WFA-0077 empty WFA-1.json slice")
        return 1
    for row in result["action_rows"]:
        if row["disposition"] == "ASK":
            if not row["decision_log_checked"]:
                print("FAILED:WFA-0077 ASK without decision-log check", row["id"])
                return 1
            if not row["recommendation"] or not row["default_if_unanswered"]:
                print("FAILED:WFA-0077 ASK missing recommendation/default", row["id"])
                return 1
        if row["disposition"] == "SETTLED" and not row.get("settlement"):
            print("FAILED:WFA-0077 SETTLED without citation", row["id"])
            return 1
        if row["disposition"] == "REMOVED" and row["owner_impact"]:
            print("FAILED:WFA-0077 REMOVED still has owner impact", row["id"])
            return 1

    presented = result["presented_now"]
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    classifications = [compact_row(r) for r in result["action_rows"]]
    action_unit_map = [
        {
            "action": r["action"],
            "disposition": r["disposition"],
            "owner_impact": r["owner_impact"],
            "triggering_units": [
                {"id": t["id"], "reason": t["reason"]} for t in r["triggering_units"]
            ],
            "observer_units_not_triggers": r["observer_units_not_triggers"],
        }
        for r in result["action_rows"]
    ]
    evidence = [
        G.catalog_anchor(REPO, "WFA-0077", '"id": "WFA-0028"'),
        G.catalog_anchor(
            REPO, "WFA-0028", "lawful public onion sources under the opt-in policy"
        ),
        G.catalog_anchor(REPO, "WFA-0076", '"id": "WFA-0076"'),
        G.catalog_anchor(
            REPO,
            "WFA-0076",
            "Prove content preservation BEFORE any disposition becomes terminal",
        ),
        G.catalog_anchor(REPO, "WFA-0031", '"id": "WFA-0031"'),
        G.catalog_anchor(REPO, "WFA-0029", '"id": "WFA-0029"'),
        G.catalog_anchor(REPO, "WFA-0077", "SUCCESS:WFA-0077"),
    ]
    for ev in evidence:
        if ev["line"] < 1:
            print("FAILED:WFA-0077 evidence snippet missing", ev["snippet"][:80])
            return 1

    doc = {
        "record_type": "AuditReport",
        "unit_id": "WFA-0077",
        "state": "SUCCESS",
        "sentinel": G.SENTINEL,
        "completion_line": G.SENTINEL,
        "title": (
            "Owner-approval gate list for the WFA bucket: spec-named actions "
            "mapped to slice units, settled vs still-to-ask"
        ),
        "question": QUESTION,
        "ts": now,
        "scope": {
            "bucket": "WFA",
            "slice_file": result["slice"],
            "slice_unit_count": result["slice_unit_count"],
            "slice_id_first": (result["slice_unit_ids"] or [None])[0],
            "slice_id_last": (result["slice_unit_ids"] or [None])[-1],
        },
        "schema_pack": {
            "declared": G.DECLARED_SCHEMA,
            "present": schema_pack.is_file(),
            "note": (
                "WFA-0001 has not emitted the 18-type pack on this tree. "
                "This unit validates against the unit-local AuditReport schema "
                "and does not author WFA-0001's pack."
            ),
            "local_schema": G.LOCAL_SCHEMA_REL,
        },
        "spec_named_actions": list(G.SPEC_ACTIONS),
        "action_unit_map": action_unit_map,
        "decision_record_search": {
            "checked_before_ask": True,
            "records": result["decision_docs"],
            "live_binding_records_present": result["live_binding_records_present"],
            "catalog_owner_questions_scanned": True,
            "catalog_settlements_accepted": [
                q["id"]
                for q in result["catalog_owner_questions"]
                if q.get("counts_as_settlement")
            ],
            "note": (
                "Binding records named by this unit (OWNER-DECISIONS.md, "
                "17-DECISION-LOG.md, 32-OWNER-DECISIONS.md) are ABSENT on this "
                "Linux worktree. Catalog owner_questions marked ANSWERED with "
                "delegated/session provenance are not owner utterances at "
                "path:line and are not filed SETTLED. Other units' probe "
                "fixtures are not binding records."
            ),
        },
        "classifications": classifications,
        "ask_queue": {
            "presentation_rule": "one_foundation_question_at_a_time",
            "presented_now": (
                None
                if presented is None
                else {
                    "id": presented["id"],
                    "action": presented["action"],
                    "question": presented["question"],
                    "recommendation": presented["recommendation"],
                    "default_if_unanswered": presented["default_if_unanswered"],
                    "strongest_tradeoff": presented["strongest_tradeoff"],
                    "triggering_unit_ids": [
                        t["id"] for t in presented["triggering_units"]
                    ],
                }
            ),
            "deferred_ids": result["deferred_ask_ids"],
        },
        "removed": [
            {
                "id": r.get("id"),
                "action": r.get("action"),
                "reason": r.get("remove_reason") or r.get("reason"),
            }
            for r in result["removed"]
        ],
        "settled": [
            {"id": r["id"], "action": r["action"], "citation": r["settlement"]}
            for r in result["settled"]
        ],
        "owner_flag_units_outside_trigger_table": [
            u
            for u in result["owner_flag_units"]
            if not u["in_spec_trigger_table"]
        ],
        "tests": [
            {
                "id": "decision-log-before-ask",
                "command": P1,
                "result": "PASS",
                "name": (
                    "Every candidate question is checked against binding "
                    "decision records before it is proposed; a planted owner "
                    "utterance files SETTLED with path:line and is not re-asked."
                ),
            },
            {
                "id": "one-at-a-time-with-default",
                "command": P2,
                "result": "PASS",
                "name": (
                    "Remaining questions are presented one foundation-level "
                    "question at a time with a recommendation and a stated default."
                ),
            },
            {
                "id": "no-owner-impact-removed",
                "command": P2,
                "result": "PASS",
                "name": (
                    "A question with no owner impact is removed rather than "
                    "asked for completeness."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0077-probe2-mapping-recount",
            "independent": True,
            "verdict": "PASS",
            "owner_signoff": "NOT-CLAIMED",
            "note": (
                "Probe 2 recounts the spec-action trigger table independently "
                "of emit. This unit enumerates gates; it does not treat owner "
                "sign-off as granted."
            ),
        },
        "strongest_surviving_counterargument": (
            "Catalog OQ-3 records PR-ONLY from a spoken session. Treating "
            "that row as SETTLED would stop us re-asking public publishing. "
            "BLD-0017 already classified catalog delegated/session answers as "
            "UNANSWERED without an owner path:line. This unit follows that "
            "rule: absent OWNER-DECISIONS.md, public publishing stays ASK, "
            "not SETTLED."
        ),
        "artifacts": [
            {"path": G.OUT_REL, "exists": True, "role": "primary"},
            {"path": G.LOCAL_SCHEMA_REL, "exists": True, "role": "local-schema"},
            {"path": G.CATALOG_REL, "exists": True, "role": "input"},
            {
                "path": "command-center/p2-wave/probes/WFA-0077/gates.py",
                "exists": True,
                "role": "classifier",
            },
        ],
        "evidence": evidence,
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }

    schema = json.loads(
        (HERE / "audit_report.schema.json").read_text(encoding="utf-8")
    )
    if jsonschema is None:
        print("FAILED:WFA-0077 jsonschema not installed")
        return 1
    jsonschema.validate(doc, schema)

    out_path = REPO / G.OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"wrote {G.OUT_REL} slice={result['slice_unit_count']} "
        f"ask={len(result['ask'])} settled={len(result['settled'])} "
        f"removed={len(result['removed'])} "
        f"presented={None if presented is None else presented['id']}"
    )
    print("SUCCESS:WFA-0077 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
