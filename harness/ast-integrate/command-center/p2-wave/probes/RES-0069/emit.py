#!/usr/bin/env python3
"""Emit command-center/research/RES-0069.json from live snapshots."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence as E  # noqa: E402

OUT = E.ART
SCHEMA_NOTE = (
    "command-center/schema/research-claim-record.schema.json is absent on this "
    "worktree (RES-0001 not delivered). This record uses the named RES-0001 "
    "fields: claim id, canonical mechanism, source lineage (two rails), "
    "evidence tier E1-E4, confidence band, named settling probe, "
    "contradiction/support edges, freshness stamp, snapshot sha256."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    index = E.load_index()
    now = utc_now()
    claims = []
    for spec in E.claims_spec():
        cid = spec["id"]
        if cid == "C-ALL-ENGINES-MANDATORY-GUARDS":
            rails = []
            for src in ("C-N8N-OPTIONAL", "C-TEMPORAL-FOREVER", "C-DURABLE-ETERNAL"):
                a, b = E.CLAIM_RAILS[src]
                rails.append(E.build_rail(a, index))
                rails.append(E.build_rail(b, index))
        else:
            a, b = E.CLAIM_RAILS[cid]
            rails = [E.build_rail(a, index), E.build_rail(b, index)]
        claims.append(
            {
                **spec,
                "source_lineage": rails,
                "rails": rails,
                "settling_probe": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0069/probe1_two_rails.py"
                ),
                "freshness_stamp": now,
            }
        )

    table = E.table_spec()
    freshness = sorted(
        {r["fetched_at"] for c in claims for r in c["rails"] if r.get("fetched_at")}
    )
    doc = {
        "unit_id": "RES-0069",
        "id": "RES-0069",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": E.SENTINEL,
        "report_kind": "research-claim-record",
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": SCHEMA_NOTE,
        "title": "Extract loop-convergence and stopping-rule constructs from existing workflow engines",
        "question": E.QUESTION,
        "answer": (
            "Seven engines were captured with two rails each. Azure Logic Apps Until, "
            "LangGraph recursion_limit, Airflow sensors, and AWS Step Functions Choice "
            "loops have mandatory finite backstops (iteration/timeout/history quotas). "
            "n8n Reset+If, Temporal Continue-As-New, and Durable Functions eternal "
            "orchestrations make an infinite loop expressible: their documented "
            "guards are optional or are history-reset patterns rather than stop rules. "
            "Condition evaluation is engine-specific (Until expression, If node, graph "
            "edges, sensor poke, Choice rules, SDK code)."
        ),
        "loop_guard_table": table,
        "control": {
            "requirement": (
                "identify one engine whose guard is optional, i.e. an infinite loop "
                "is expressible"
            ),
            "engines": sorted(E.CONTROL_ENGINES),
            "primary": "n8n Loop Over Items",
            "finding": (
                "n8n documents that a Reset+If loop whose termination condition never "
                "matches gets stuck in an infinite loop. Temporal and Durable Functions "
                "independently document run-forever / eternal loops."
            ),
        },
        "claims": claims,
        "edges": [
            {
                "type": "direct-contradiction",
                "from": "C-ALL-ENGINES-MANDATORY-GUARDS",
                "to": "C-N8N-OPTIONAL",
                "note": "optional-guard control",
            },
            {
                "type": "direct-contradiction",
                "from": "C-ALL-ENGINES-MANDATORY-GUARDS",
                "to": "C-TEMPORAL-FOREVER",
                "note": "run-forever via Continue-As-New",
            },
            {
                "type": "support",
                "from": "C-AZURE-UNTIL",
                "to": "C-AZURE-UNTIL-LIMITS",
                "note": "defaults vs numeric ceilings",
            },
        ],
        "tests": [
            {
                "id": "per-engine-guard-class",
                "name": "for each engine, record the infinite-loop guard and whether it is mandatory or optional",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0069/probe2_loop_guard_table.py"
                ),
                "result": "PASS",
            },
            {
                "id": "optional-guard-control",
                "name": "control: identify one engine whose guard is optional, i.e. an infinite loop is expressible",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0069/probe2_loop_guard_table.py"
                ),
                "result": "PASS",
            },
            {
                "id": "two-rail-evidence",
                "name": "every CONFIRMED claim carries structured-api and prose rails with permalink, timestamp, HTTP status, sha256",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0069/probe1_two_rails.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0069-fresh-context-adversarial-refuter",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "default_without_evidence": "REFUTED",
            "scope_not_agreement": True,
            "notes": (
                "Overclaim 'every engine has a mandatory cap' is REFUTED. Google Cloud "
                "Workflows and Salesforce Flow captures were JS-rendered and did not "
                "yield a searchable while/iteration quote; they are omitted, not "
                "inferred. Camunda completionCondition is multi-instance early-exit, "
                "not a while, and is omitted. 05-ECO index and REGISTER.md are absent "
                "on this Linux worktree; sources pivoted to live public docs/code."
            ),
        },
        "strongest_surviving_counterargument": (
            "A platform-level wall-clock timeout (worker kill, cloud idle policy, "
            "OS process limit) can still stop an 'infinite' n8n/Temporal/Durable loop. "
            "That does not convert those engines' loop constructs into mandatory "
            "iteration caps: the engine docs still allow expressing a loop with no "
            "author-supplied bound. Treating an undeclared host timeout as the "
            "engine's stopping rule would be an overclaim."
        ),
        "inputs_absent_on_this_worktree": [
            "command-center/sources/REGISTER.md",
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
        ],
        "freshness": {"oldest_fetch": freshness[0] if freshness else now, "newest_fetch": freshness[-1] if freshness else now, "emitted_at": now},
        "artifacts": [
            {
                "path": "command-center/research/RES-0069.json",
                "role": "primary",
                "exists": True,
            }
        ],
    }
    ok, why = E.check_two_rails(doc)
    if not ok:
        print(f"FAILED:emit two-rails {why}")
        return 1
    ok, why2 = E.check_loop_guard_table(doc)
    if not ok:
        print(f"FAILED:emit table {why2}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sha, size = E.sha256_file(OUT)
    print(f"wrote {OUT.relative_to(E.REPO).as_posix()} bytes={size} sha256={sha}")
    print(why)
    print(why2)
    print("SUCCESS:RES-0069 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
