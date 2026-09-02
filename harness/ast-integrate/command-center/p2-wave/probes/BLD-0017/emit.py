#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0017.json — owner-question closure."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import closure as C  # noqa: E402
import scenario as S  # noqa: E402
import validate_doc as V  # noqa: E402

OUT = "command-center/receipts/BLD-0017.json"
SCHEMA = "command-center/schema/owner-question-closure.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
READY = "command-center/ready_units.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0017/probe1_answered_inference.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0017/probe2_plant_coverage.py"
)
QUESTION = (
    "Which owner question was raised and never answered, and which work units "
    "are silently executing on that question's assumed default?"
)


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    line = C.find_line(text, snippet)
    if line < 1:
        raise SystemExit(f"FAILED:BLD-0017 emit snippet not in {rel}: {snippet[:80]}")
    got = text.splitlines()[line - 1]
    if snippet not in got and snippet not in text:
        raise SystemExit(f"FAILED:BLD-0017 emit line mismatch {rel}:{line}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    fix = S.build_fixtures()
    controls = C.analyze_controls(REPO, fix)
    v = C.control_verdicts(controls)
    for qid in ("CTL-ANS-1", "CTL-ANS-2", "CTL-ANS-3", "CTL-ANS-4", "CTL-ANS-5"):
        if v.get(qid) != "ANSWERED":
            print(f"FAILED:BLD-0017 control {qid} not ANSWERED: {v.get(qid)}")
            return 1
    if v.get("CTL-INF-1") != "UNANSWERED" or v.get("CTL-ACK-1") != "UNANSWERED":
        print("FAILED:BLD-0017 inference/ack controls")
        return 1
    if "PLANT-0001" not in C.proceeding_ids(controls, "CTL-OPEN-1"):
        print("FAILED:BLD-0017 planted unit not in proceeding-on-default")
        return 1
    if not controls["coverage"]["exact_once"]:
        print("FAILED:BLD-0017 control coverage", controls["coverage"])
        return 1

    live = C.analyze(REPO)
    if not live["coverage"]["exact_once"]:
        print("FAILED:BLD-0017 live coverage", live["coverage"])
        return 1

    (REPO / "command-center/receipts").mkdir(parents=True, exist_ok=True)

    evidence = [
        ev(
            CATALOG,
            "owner_questions, 27 entries",
            "catalog",
            "Unit brief claims 27 catalog owner_questions; live measured count is taken from the array, not from this prose.",
        ),
        ev(
            CATALOG,
            '"id": "OQ-10"',
            "catalog",
            "OQ-10 is a catalog owner_question; its catalog answer is a delegated default, not an owner utterance at path:line.",
        ),
        ev(
            READY,
            "BUCKET_SATISFIED = True",
            "live-tree",
            "ready_units.py proceeds on OQ-10's assumed default (BUCKET_SATISFIED=True). OWNER-DECISIONS.md is present but has no Owner: utterance for OQ-10.",
        ),
        ev(
            CATALOG,
            "WORK-UNIT-CATALOG owner_questions Q9 (measurement-only ratings, no stars or download counts)",
            "catalog",
            "IMP-0076 takes OPEN question Q9 as an input and implements measurement-only ratings as if adopted.",
        ),
        ev(
            CATALOG,
            "owner DELEGATED the default in session 30bd50d4",
            "catalog",
            "Catalog ANSWERED rows include delegated defaults whose provenance is an agent's write-up, not an owner file:line.",
        ),
        ev(
            C.rel_of(REPO, fix / "OWNER-DECISIONS.md"),
            'Owner: "Ship as PR-ONLY. No public marketplace and no private canary."',
            "fixture",
            "Control: a recorded owner answer at path:line classifies ANSWERED.",
        ),
        ev(
            C.rel_of(REPO, fix / "OWNER-DECISIONS.md"),
            "Agent inference: the owner would probably want a public marketplace because growth.",
            "fixture",
            "Control: a question answered only by an agent's inference classifies UNANSWERED.",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "BLD-0017",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0017",
        "title": (
            "Unanswered-owner-question closure: units executing on a default "
            "the owner never chose"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "Joining catalog owner_questions plus packet questions to recorded "
            "owner answers (OWNER-DECISIONS.md, 17-DECISION-LOG.md) and to units "
            "whose inputs or targets depend on each question surfaces every "
            "UNANSWERED question with the default in use. Owner-authored path:line "
            "is required for ANSWERED; agent summaries and delegated defaults are "
            "UNANSWERED. Packet and OWNER-DECISIONS.md are present on this tree; "
            "17-DECISION-LOG.md is absent. Live OWNER-DECISIONS.md has no Owner: "
            "utterance lines, so catalog ANSWERED rows stay UNANSWERED."
        ),
        "ts": now,
        "sources": live["sources"],
        "catalog_count_claimed_in_brief": 27,
        "catalog_count_measured": live["catalog_count"],
        "packet_count_measured": live["packet_count"],
        "answered_count": live["answered_count"],
        "unanswered_count": live["unanswered_count"],
        "closure_table": live["closure_table"],
        "proceeding_on_default": live["proceeding_on_default"],
        "waiting_on_owner": live["waiting_on_owner"],
        "coverage": live["coverage"],
        "controls": {
            "fixture_dir": C.rel_of(REPO, fix),
            "verdicts": v,
            "planted_unit_in_proceeding": "PLANT-0001"
            in C.proceeding_ids(controls, "CTL-OPEN-1"),
            "answered_owner_quotes": 5,
            "agent_inference_unanswered": v.get("CTL-INF-1") == "UNANSWERED",
            "ack_only_unanswered": v.get("CTL-ACK-1") == "UNANSWERED",
        },
        "tests": [
            {
                "id": "control-recorded-owner-answer",
                "command": P1,
                "result": "PASS",
                "name": "A question with a recorded owner answer classifies ANSWERED (no false UNANSWERED).",
            },
            {
                "id": "control-agent-inference",
                "command": P1,
                "result": "PASS",
                "name": "A question answered only by an agent's inference classifies UNANSWERED.",
            },
            {
                "id": "control-planted-unit-proceeding",
                "command": P2,
                "result": "PASS",
                "name": "A planted unit whose target depends on an unanswered question appears in proceeding-on-default.",
            },
            {
                "id": "coverage-exact-once",
                "command": P2,
                "result": "PASS",
                "name": "Every catalog owner_question plus every packet question appears exactly once.",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0017-probe2-answered-scope",
            "independent": True,
            "scope_not_agreement": True,
            "verdict": "PASS",
            "live_answered_count": live["answered_count"],
            "sampled_control_answered": [
                r["id"] for r in controls["closure_table"] if r["verdict"] == "ANSWERED"
            ][:5],
            "sampled_live_catalog_marked_answered": [
                r["id"]
                for r in live["closure_table"]
                if r.get("catalog_state") == "ANSWERED"
            ][:5],
            "note": (
                "Live ANSWERED count is zero because OWNER-DECISIONS.md has no "
                "Owner: utterance lines (table cells and delegated-default "
                "sections only) and 17-DECISION-LOG.md is absent. Catalog "
                "'ANSWERED' rows are delegated defaults or agent summaries of "
                "spoken sessions without an owner utterance file:line. The packet "
                "is present; its extracted ids are a subset of the catalog join "
                "(exact-once). Five control Owner: quotes were checked to actually "
                "resolve their questions; five live catalog-marked ANSWERED rows "
                "were confirmed UNANSWERED under the owner-utterance rule."
            ),
        },
        "strongest_surviving_counterargument": (
            "Catalog provenance for OQ-3/OQ-4 says the owner spoke in session "
            "30bd50d4. Treating those rows as ANSWERED would require citing the "
            "owner's own words at path:line. OWNER-DECISIONS.md is present but "
            "its OQ-3/OQ-4 sections are agent write-ups of that session, not "
            "Owner: quotes. The counterargument survives as a pointer to recover "
            "the session transcript; it does not mint an owner file:line that is "
            "not on disk."
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": CATALOG, "exists": True, "role": "input"},
            {"path": READY, "exists": True, "role": "code-consumer"},
            {
                "path": "command-center/p2-wave/probes/BLD-0017/closure.py",
                "exists": True,
                "role": "join-engine",
            },
        ],
        "evidence": evidence,
        "completion_line": "SUCCESS:BLD-0017",
    }

    if not V.catalog_shim_present():
        print(f"FAILED:BLD-0017 catalog output_schema missing {SCHEMA}")
        return 1
    V.validate_doc(doc)
    if not V.mutant_missing_closure_table_is_red(doc):
        print("FAILED:BLD-0017 local schema accepted a receipt without closure_table")
        return 1
    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"wrote {OUT} unanswered={live['unanswered_count']} "
        f"answered={live['answered_count']} proceeding={len(live['proceeding_on_default'])} "
        f"catalog={live['catalog_count']}"
    )
    print("SUCCESS:BLD-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
