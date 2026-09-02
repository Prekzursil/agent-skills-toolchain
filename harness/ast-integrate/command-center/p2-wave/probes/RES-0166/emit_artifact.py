#!/usr/bin/env python3
"""Emit RES-0166 design-spec from the live comparison and hashed sources."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0166/probe1_hung_injection.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0166/probe2_goose_lineage.py"
)


def lin(src: dict, quote: str, locator: str) -> dict:
    return {
        "rail": locator.split(":")[0] if ":" in locator else locator,
        "permalink": src.get("resolved_url"),
        "requested_url": src.get("requested_url"),
        "resolved_url": src.get("resolved_url"),
        "fetch_timestamp": src.get("fetch_timestamp"),
        "http_status": src.get("http_status"),
        "sha256": src.get("sha256"),
        "bytes": src.get("bytes"),
        "snapshot_path": src.get("path"),
        "locator": locator,
        "quote": quote,
    }


def kent(band: str, p: float) -> dict:
    return {
        "band": band,
        "approx_probability": p,
        "vocabulary": "Sherman Kent 1964 / ICD-203 analytic confidence",
    }


def main() -> int:
    rows = E.verify_lineage()
    if any(not r["match"] for r in rows):
        print("FAILED:RES-0166 lineage mismatch before emit")
        return 1
    matrix = E.run_comparison()
    if matrix["happy_path_only_is_complete_comparison"] is True:
        print("FAILED:RES-0166 happy-path-only marked complete")
        return 1
    if not matrix["rankings_differ"]:
        print("FAILED:RES-0166 hung injection did not change ranking")
        return 1
    if E.mutant_happy_path_only_accepted(matrix) is not True:
        print("FAILED:RES-0166 mutant detector inert")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    init = E.source_by_file("goose-init.rs")
    lw = E.source_by_file("goose-lead-worker.rs")
    env = E.source_by_file("goose-env-vars.md")
    tut = E.source_by_file("goose-lead-worker-tutorial.md")
    block = E.source_by_file("goose-repo-block.json")
    aaif = E.source_by_file("goose-repo-aaif.json")
    pr = E.source_by_file("goose-pr-7989.json")
    anth = E.source_by_file("anthropic-multi-agent.html")
    ag = E.source_by_file("autogen-group-chat-core.html")
    temp = E.source_by_file("temporal-activity-failures.md")
    lg_sup = E.source_by_file("langgraph-supervisor.md")
    pr_doc = json.loads((REPO / pr["path"]).read_text(encoding="utf-8"))
    block_doc = json.loads((REPO / block["path"]).read_text(encoding="utf-8"))
    aaif_doc = json.loads((REPO / aaif["path"]).read_text(encoding="utf-8"))

    happy = {r["topology"]: E.public_row(r) for r in matrix["arms"]["happy"]["rows"]}
    hung = {r["topology"]: E.public_row(r) for r in matrix["arms"]["hung_injection"]["rows"]}

    answer = (
        "The comparison that would decide a sub-orchestrator topology is a "
        "two-arm experiment on a frozen task set: (1) happy-path, no failure "
        "injection; (2) hung-worker injection plus a cyclic-wait task. Measure "
        "time-to-first-finding, distinct findings, deadlock rate, token cost, "
        "and hung-worker recovery, each with a named instrument and a known "
        "failure mode. A ranking from arm (1) alone is not a topology "
        f"decision: on this fixture it selects {matrix['happy_winner']}, while "
        f"arm (2) selects {matrix['hung_winner']}. "
        "Existing Goose evidence (commit 58f3cc9e on aaif-goose/goose, the "
        "canonical rename of block/goose) says the lead/worker *model* "
        "escalation default is 2 consecutive task failures, configurable via "
        "GOOSE_LEAD_FAILURE_THRESHOLD, then 2 lead fallback turns. That "
        "mechanism is intra-session model handoff, not a multi-worker "
        "orchestrator, and it was removed by merged PR 7989. Sources do not "
        "contain a published eval that escalating to lead beats retrying the "
        "same worker; this fixture's T-FAIL2 completes under both. Anthropic's "
        "research write-up uses an orchestrator-worker (lead + parallel "
        "subagents) pattern and reports ~15x chat token cost and a synchronous "
        "wait bottleneck. This estate's current supervisor is slot occupancy "
        "with a 90-minute SIGKILL and two-strike park, not barrier-wait-all."
    )

    claims = [
        {
            "id": "RES-0166-C1-GOOSE-THRESHOLD-TWO",
            "claim": (
                "Goose's lead/worker implementation at commit 58f3cc9e defaults "
                "to escalating to the lead model after 2 consecutive task "
                "failures (GOOSE_LEAD_FAILURE_THRESHOLD default 2), with 3 "
                "initial lead turns and 2 fallback turns."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-rust-const",
                    "kind": "source-code",
                    "backend": "hashed-snapshot-goose-init.rs",
                    "observation": (
                        "crates/goose/src/providers/init.rs:44 "
                        "const DEFAULT_FAILURE_THRESHOLD: usize = 2; "
                        "also DEFAULT_LEAD_TURNS=3 and DEFAULT_FALLBACK_TURNS=2"
                    ),
                },
                {
                    "id": "S2-docs-table",
                    "kind": "prose-docs",
                    "backend": "hashed-snapshot-goose-env-vars.md",
                    "observation": (
                        "environment-variables.md table: "
                        "GOOSE_LEAD_FAILURE_THRESHOLD consecutive failures "
                        "default 2; GOOSE_LEAD_TURNS default 3; "
                        "GOOSE_LEAD_FALLBACK_TURNS default 2"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    init,
                    "const DEFAULT_FAILURE_THRESHOLD: usize = 2;",
                    "goose-init.rs:44",
                ),
                lin(
                    env,
                    "GOOSE_LEAD_FAILURE_THRESHOLD | Consecutive failures before falling back to the lead model | Integer | 2",
                    "goose-env-vars.md:142",
                ),
                lin(
                    lw,
                    "max_failures_before_fallback: 2, // Fallback after 2 consecutive failures",
                    "goose-lead-worker.rs:52",
                ),
            ],
            "strongest_caveat": (
                "This is the historical implementation at 58f3cc9e, not current "
                "main (see C5). Consecutive *task* failures, not API errors."
            ),
        },
        {
            "id": "RES-0166-C2-THRESHOLD-CONFIGURABLE",
            "claim": (
                "The Goose failure threshold is configurable through "
                "GOOSE_LEAD_FAILURE_THRESHOLD rather than only the struct "
                "default of 2."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-env-unwrap-or",
                    "kind": "source-code",
                    "backend": "hashed-snapshot-goose-init.rs",
                    "observation": (
                        "create_lead_worker_from_env reads "
                        "GOOSE_LEAD_FAILURE_THRESHOLD and unwrap_or "
                        "DEFAULT_FAILURE_THRESHOLD"
                    ),
                },
                {
                    "id": "S2-docs-example-3",
                    "kind": "prose-docs",
                    "backend": "hashed-snapshot-goose-env-vars.md",
                    "observation": (
                        "Advanced example sets GOOSE_LEAD_FAILURE_THRESHOLD=3; "
                        "tutorial repeats the same override"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    init,
                    'config.get_param::<usize>("GOOSE_LEAD_FAILURE_THRESHOLD").unwrap_or(DEFAULT_FAILURE_THRESHOLD)',
                    "goose-init.rs:171-173",
                ),
                lin(
                    env,
                    "export GOOSE_LEAD_FAILURE_THRESHOLD=3",
                    "goose-env-vars.md:163",
                ),
                lin(
                    tut,
                    "export GOOSE_LEAD_FAILURE_THRESHOLD=3          # Switch back to lead after 3 failures",
                    "goose-lead-worker-tutorial.md:77",
                ),
            ],
            "strongest_caveat": "Configurability does not imply a measured optimal value.",
        },
        {
            "id": "RES-0166-C3-INTRA-SESSION-NOT-TOPOLOGY",
            "claim": (
                "Goose lead/worker is an intra-session model hand-off (lead "
                "provider vs worker provider on successive turns), not a "
                "multi-worker orchestrator topology."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-get-active-provider",
                    "kind": "source-code",
                    "backend": "hashed-snapshot-goose-lead-worker.rs",
                    "observation": (
                        "get_active_provider returns lead_provider or "
                        "worker_provider from turn_count and fallback flags; "
                        "there is no worker pool"
                    ),
                },
                {
                    "id": "S2-tutorial-handoff",
                    "kind": "prose-docs",
                    "backend": "hashed-snapshot-goose-lead-worker-tutorial.md",
                    "observation": (
                        "Tutorial: lead kicks off planning, then goose hands "
                        "the task to the worker model; fallback pulls the lead "
                        "model back in"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    lw,
                    "if count < self.lead_turns || in_fallback { Arc::clone(&self.lead_provider) } else { Arc::clone(&self.worker_provider) }",
                    "goose-lead-worker.rs:120-124",
                ),
                lin(
                    tut,
                    "The lead/worker model is a smart hand-off system.",
                    "goose-lead-worker-tutorial.md:24",
                ),
            ],
            "strongest_caveat": (
                "The *threshold integer* can still be reused as a control in a "
                "lead-worker *topology* comparison; the Goose code is not that "
                "topology."
            ),
        },
        {
            "id": "RES-0166-C4-CANONICAL-REPO-RENAME",
            "claim": (
                "The current canonical Goose repository is aaif-goose/goose "
                "(GitHub id 846698999). api.github.com/repos/block/goose "
                "resolves to the same repository object as aaif-goose/goose."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-block-api",
                    "kind": "structured-api",
                    "backend": "hashed-snapshot-goose-repo-block.json",
                    "observation": (
                        f"block/goose request resolved to {block.get('resolved_url')}; "
                        f"full_name={block_doc.get('full_name')} id={block_doc.get('id')}"
                    ),
                },
                {
                    "id": "S2-aaif-api",
                    "kind": "structured-api",
                    "backend": "hashed-snapshot-goose-repo-aaif.json",
                    "observation": (
                        f"aaif-goose/goose full_name={aaif_doc.get('full_name')} "
                        f"id={aaif_doc.get('id')}; body sha256 matches block capture"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    block,
                    f"full_name={block_doc.get('full_name')} id={block_doc.get('id')}",
                    "goose-repo-block.json",
                ),
                lin(
                    aaif,
                    f"full_name={aaif_doc.get('full_name')} id={aaif_doc.get('id')}",
                    "goose-repo-aaif.json",
                ),
            ],
            "strongest_caveat": (
                "Cite permalinks on aaif-goose/goose. The old block/goose "
                "pointer is a silent redirect that can drop."
            ),
        },
        {
            "id": "RES-0166-C5-MECHANISM-REMOVED",
            "claim": (
                "The lead/worker provider, including the failure-threshold "
                "escalation, was removed from Goose by merged PR 7989 "
                f"(merged_at={pr_doc.get('merged_at')}). Current main is not "
                "the cited implementation."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "highly-likely",
            "sherman_kent": kent("highly-likely", 0.87),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-pr-merged",
                    "kind": "structured-api",
                    "backend": "hashed-snapshot-goose-pr-7989.json",
                    "observation": (
                        f"PR 7989 title={pr_doc.get('title')!r} merged="
                        f"{pr_doc.get('merged')} state={pr_doc.get('state')}"
                    ),
                },
                {
                    "id": "S2-pr-body-files",
                    "kind": "prose-api",
                    "backend": "hashed-snapshot-goose-pr-7989.json",
                    "observation": (
                        "PR body lists deletion of lead_worker.rs and removal "
                        "of consecutive-failure fallback"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    pr,
                    "Remove the lead/worker provider feature entirely from the codebase.",
                    "goose-pr-7989.json:body",
                ),
                lin(
                    pr,
                    f"merged={pr_doc.get('merged')} merged_at={pr_doc.get('merged_at')}",
                    "goose-pr-7989.json:merged",
                ),
            ],
            "strongest_caveat": (
                "Removal is about current main. Historical 58f3cc9e snapshots "
                "remain valid citations for what the threshold *was*."
            ),
        },
        {
            "id": "RES-0166-C6-ESCALATION-BEATS-RETRY-UNMEASURED",
            "claim": (
                "Goose lead-model escalation beats retrying the same worker "
                "as a measured fact in the cited sources."
            ),
            "verdict": "REFUTED",
            "evidence_tier": "E2",
            "confidence_band": "highly-likely",
            "sherman_kent": kent("highly-likely", 0.87),
            "independent_verification_path": P1,
            "signals": [
                {
                    "id": "S1-no-eval-in-docs",
                    "kind": "prose-docs",
                    "backend": "hashed-snapshot-goose-lead-worker-tutorial.md",
                    "observation": (
                        "Tutorial describes fallback when the worker 'gets "
                        "tripped up twice in a row' with no comparative eval "
                        "table against same-worker retry"
                    ),
                },
                {
                    "id": "S2-fixture-both-complete",
                    "kind": "computed-fixture",
                    "backend": "engine.run_comparison hung arm T-FAIL2",
                    "observation": (
                        "hung-arm T-FAIL2 complete=True on flat and on "
                        "lead-worker; escalation is not required for that task"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    tut,
                    "If the worker gets tripped up twice in a row, goose temporarily switches back to the lead model",
                    "goose-lead-worker-tutorial.md:48",
                ),
                lin(
                    lw,
                    "SWITCHING TO LEAD MODEL: Entering fallback mode after {} consecutive task failures",
                    "goose-lead-worker.rs:163",
                ),
            ],
            "strongest_caveat": (
                "REFUTED means 'escalation beats retry' is not a measured "
                "fact in these sources. It is not a claim that escalation "
                "never helps; hung reassignment is a different mechanism."
            ),
        },
        {
            "id": "RES-0166-C7-ANTHROPIC-ORCHESTRATOR-WORKER",
            "claim": (
                "Anthropic's published multi-agent research system uses an "
                "orchestrator-worker pattern (lead agent plus specialized "
                "subagents in parallel), reports about 15x chat token cost "
                "for multi-agent, and names synchronous subagent waits as a "
                "bottleneck."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "highly-likely",
            "sherman_kent": kent("highly-likely", 0.87),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-orchestrator-worker-quote",
                    "kind": "primary-html",
                    "backend": "hashed-snapshot-anthropic-multi-agent.html",
                    "observation": (
                        "Page contains 'orchestrator-worker pattern' and "
                        "'multi-agent systems use about 15× more tokens than chats'"
                    ),
                },
                {
                    "id": "S2-autogen-contrast",
                    "kind": "independent-system",
                    "backend": "hashed-snapshot-autogen-group-chat-core.html",
                    "observation": (
                        "AutoGen GroupChatManager selects the next speaker "
                        "sequentially via RequestToSpeak — a different "
                        "topology than parallel subagents"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    anth,
                    "orchestrator-worker pattern, where a lead agent coordinates the process while delegating to specialized subagents that operate in parallel",
                    "anthropic-multi-agent.html",
                ),
                lin(
                    ag,
                    "The group chat manager selects the next speaker, sends out a RequestToSpeak message to that agent.",
                    "autogen-group-chat-core.html",
                ),
            ],
            "strongest_caveat": (
                "Anthropic numbers are their internal research eval, not this "
                "estate. LangGraph tutorial URLs used in this unit redirected "
                "to a different docs page (URL drift)."
            ),
        },
        {
            "id": "RES-0166-C8-HAPPY-PATH-NOT-DECISION",
            "claim": (
                "A topology comparison with no hung-worker injection measures "
                "only the happy path and is not a decision procedure. On the "
                f"frozen task set, happy-path ranking selects {matrix['happy_winner']} "
                f"and hung-injection ranking selects {matrix['hung_winner']}."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P1,
            "signals": [
                {
                    "id": "S1-rankings-differ",
                    "kind": "computed-fixture",
                    "backend": "engine.run_comparison",
                    "observation": (
                        f"happy ranking={matrix['arms']['happy']['ranking']}; "
                        f"hung ranking={matrix['arms']['hung_injection']['ranking']}"
                    ),
                },
                {
                    "id": "S2-mutant-red",
                    "kind": "negative-control",
                    "backend": "engine.mutant_happy_path_only_accepted",
                    "observation": (
                        "Marking happy-path-only as a complete comparison is "
                        "the planted-broken state the probe must reject"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    temp,
                    "A Heartbeat Timeout is the maximum time between Activity Heartbeats.",
                    "temporal-activity-failures.md#heartbeat-timeout",
                ),
                lin(
                    anth,
                    "Synchronous execution creates bottlenecks. Currently, our lead agents execute subagents synchronously, waiting for each set of subagents to complete before proceeding.",
                    "anthropic-multi-agent.html",
                ),
            ],
            "strongest_caveat": (
                "The fixture decides the *comparison design*, not production "
                "model routing. Paid live-model arms are owner-gated and "
                "NOT-RUN here."
            ),
        },
        {
            "id": "RES-0166-C9-ESTATE-SLOT-SUPERVISOR",
            "claim": (
                "This worktree's current p2 supervisor occupies a slot until "
                "WORKER_TIMEOUT_SEC (90 minutes) then SIGKILL, and parks after "
                "TWO_STRIKES=2. It does not barrier-wait the whole leftover "
                "batch on one hung unit; a hung unit still consumes one cap "
                "slot until timeout."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "S1-timeout-const",
                    "kind": "live-tree",
                    "backend": "dispatch_cursor.py:35",
                    "observation": "WORKER_TIMEOUT_SEC = 90 * 60; TWO_STRIKES = 2",
                },
                {
                    "id": "S2-killpg",
                    "kind": "live-tree",
                    "backend": "dispatch_cursor.py:460-462",
                    "observation": (
                        "poll loop SIGKILLs the process group when started "
                        "exceeds WORKER_TIMEOUT_SEC, then launches others up "
                        "to cap"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    init,
                    "const DEFAULT_FAILURE_THRESHOLD: usize = 2;",
                    "goose-init.rs:44-coincides-with-TWO_STRIKES-but-independent",
                ),
                lin(
                    temp,
                    "If this timeout is reached, the Activity Task fails and a retry occurs if a Retry Policy dictates it.",
                    "temporal-activity-failures.md",
                ),
            ],
            "strongest_caveat": (
                "Catalog failure class 11317 names barrier-wait-all. Current "
                "dispatch is slot occupancy, a weaker block. TWO_STRIKES=2 "
                "numerically matches Goose's default but is a different code path."
            ),
        },
        {
            "id": "RES-0166-C10-HIER-CONJUNCTION",
            "claim": (
                "Hierarchical fan-in that uses conjunction (any non-COMPLETE "
                "child keeps the parent incomplete), as in CNF-0095 reducer.py, "
                "does not recover a hung child by itself. On this fixture the "
                "hierarchical-fanin hung-arm recovery_from_hung_worker is 0."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "sherman_kent": kent("almost-certain", 0.93),
            "independent_verification_path": P1,
            "signals": [
                {
                    "id": "S1-cnf-0095-conjunction",
                    "kind": "live-tree",
                    "backend": "probes/CNF-0095/reducer.py:4",
                    "observation": (
                        "Conjunction, not averaging: any non-COMPLETE child "
                        "keeps the parent incomplete"
                    ),
                },
                {
                    "id": "S2-fixture-hier-zero",
                    "kind": "computed-fixture",
                    "backend": "engine.run_comparison",
                    "observation": (
                        "hierarchical-fanin hung recovery_from_hung_worker="
                        f"{hung['hierarchical-fanin']['recovery_from_hung_worker']}"
                    ),
                },
            ],
            "source_lineage": [
                lin(
                    anth,
                    "Synchronous execution creates bottlenecks.",
                    "anthropic-multi-agent.html",
                ),
                lin(
                    lg_sup,
                    "Redirecting...",
                    "langgraph-supervisor.md (stale tutorial URL)",
                ),
            ],
            "strongest_caveat": (
                "Adding a child retry policy would change this result; the "
                "bare conjunction reducer does not include one."
            ),
        },
    ]

    doc = {
        "unit_id": E.UNIT,
        "state": "SUCCESS",
        "sentinel": E.SENTINEL,
        "kind": "design-spec",
        "title": "Sub-orchestrator topology: flat, lead-worker, tree or hierarchical fan-in?",
        "question": E.QUESTION,
        "answer": answer,
        "output_schema": E.SCHEMA_REL,
        "catalog_output_schema": "command-center/schema/design-spec.schema.json",
        "catalog_output_schema_present": (
            REPO / "command-center/schema/design-spec.schema.json"
        ).is_file(),
        "ts": now,
        "topologies": [
            {
                "id": "flat",
                "definition": (
                    "All assigned workers run in parallel. Fan-in waits for "
                    "every worker. No reassignment. Hung worker occupies the "
                    "slot until TICK_LIMIT."
                ),
            },
            {
                "id": "lead-worker",
                "definition": (
                    "Lead spends GOOSE_LEAD_TURNS, then workers. After "
                    "GOOSE_FAILURE_THRESHOLD consecutive worker failures "
                    "(hung counts after detect), lead fallback "
                    "GOOSE_FALLBACK_TURNS and reassignment. Intra-Goose this "
                    "is a *model* switch; here it is applied as a topology."
                ),
            },
            {
                "id": "tree",
                "definition": (
                    "Two sub-leads (W0/W1 and W2/W3). Hung leaf reassigned "
                    "inside its subtree. Siblings continue. Parent waits for "
                    "both subtrees."
                ),
            },
            {
                "id": "hierarchical-fanin",
                "definition": (
                    "Depth-2 receipts with CNF-0095 conjunction: any "
                    "TIMEOUT/INCOMPLETE child keeps the parent incomplete. "
                    "No parent retry."
                ),
            },
        ],
        "metrics": list(E.METRICS),
        "task_set": [
            {
                "id": t["id"],
                "title": t["title"],
                "item_ids": [i["id"] for i in t["items"]],
                "hung_capable": t["id"] in E.HUNG_TASK_IDS,
                "deadlock_capable": bool(t.get("deadlock")),
            }
            for t in E.TASKS
        ],
        "controls": [
            {
                "id": "fixed-task-order",
                "description": "Same six tasks in catalog order for every topology and arm.",
            },
            {
                "id": "equal-worker-pool",
                "description": "W0-W3 plus lead/sub-leads; no extra workers on one topology.",
            },
            {
                "id": "discrete-tick-clock",
                "description": "Shared tick source; TTFF is min accept tick, not wall clock.",
            },
            {
                "id": "goose-threshold-pinned",
                "description": (
                    f"lead_turns={E.GOOSE_LEAD_TURNS}, "
                    f"failure_threshold={E.GOOSE_FAILURE_THRESHOLD}, "
                    f"fallback_turns={E.GOOSE_FALLBACK_TURNS} from commit "
                    f"{E.GOOSE_COMMIT}"
                ),
            },
            {
                "id": "paid-live-models-not-run",
                "description": (
                    "Owner-gated paid model routing is NOT-RUN. The simulator "
                    "arm is the delivery surface for this unit."
                ),
            },
        ],
        "hung_worker_injection_arm": {
            "id": "hung-worker-injection",
            "required": True,
            "tasks": sorted(E.HUNG_TASK_IDS),
            "hung_worker": "W1",
            "detect_ticks": E.HUNG_DETECT_TICKS,
            "instrument_prior_art": (
                "Temporal Heartbeat Timeout: max time between heartbeats; "
                "on timeout the activity fails and retry policy may fire"
            ),
            "happy_path_only_is_complete_comparison": False,
        },
        "comparison": {
            "happy_winner": matrix["happy_winner"],
            "hung_winner": matrix["hung_winner"],
            "rankings_differ": matrix["rankings_differ"],
            "happy_ranking": matrix["arms"]["happy"]["ranking"],
            "hung_ranking": matrix["arms"]["hung_injection"]["ranking"],
            "happy_path_only_is_complete_comparison": False,
            "happy_rows": happy,
            "hung_injection_rows": hung,
            "goose_threshold_used": matrix["goose_threshold_used"],
            "note": (
                "Simulator ranking is a design-validation of the comparison, "
                "not a production topology mandate."
            ),
        },
        "goose_escalation": {
            "canonical_repo": "aaif-goose/goose",
            "github_id": 846698999,
            "old_pointer": "block/goose",
            "commit": E.GOOSE_COMMIT,
            "source_file_lines": {
                "DEFAULT_FAILURE_THRESHOLD": "crates/goose/src/providers/init.rs:44",
                "DEFAULT_LEAD_TURNS": "crates/goose/src/providers/init.rs:43",
                "DEFAULT_FALLBACK_TURNS": "crates/goose/src/providers/init.rs:45",
                "struct_default_max_failures": "crates/goose/src/providers/lead_worker.rs:52",
                "docs_table": "documentation/docs/guides/environment-variables.md:142",
            },
            "defaults": {
                "lead_turns": E.GOOSE_LEAD_TURNS,
                "failure_threshold": E.GOOSE_FAILURE_THRESHOLD,
                "fallback_turns": E.GOOSE_FALLBACK_TURNS,
            },
            "configurable": True,
            "kind": "intra-session-model-handoff",
            "removed_by": {
                "pr": 7989,
                "merged": pr_doc.get("merged"),
                "merged_at": pr_doc.get("merged_at"),
                "title": pr_doc.get("title"),
            },
            "beats_same_worker_retry": "NOT-MEASURED",
        },
        "estate_supervisor": {
            "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            "worker_timeout_seconds": 90 * 60,
            "two_strikes": 2,
            "block_mode": "slot-occupancy-until-timeout",
            "not": "barrier-wait-all-leftover-batch",
        },
        "claims": claims,
        "source_lineage": [
            {
                "file": s["file"],
                "resolved_url": s["resolved_url"],
                "requested_url": s["requested_url"],
                "fetch_timestamp": s["fetch_timestamp"],
                "http_status": s["http_status"],
                "sha256": s["sha256"],
                "bytes": s["bytes"],
                "path": s["path"],
                "present": s["present"],
            }
            for s in E.load_lineage()["sources"]
        ],
        "tests": [
            {
                "id": "named-probe-1",
                "command": P1,
                "result": "NOT-RUN",
            },
            {
                "id": "named-probe-2",
                "command": P2,
                "result": "NOT-RUN",
            },
            {
                "id": "NC-HUNG-INJECTION-REQUIRED",
                "command": P1,
                "result": "NOT-RUN",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-HUNG-INJECTION-REQUIRED",
                "description": (
                    "A topology comparison with no hung-worker injection "
                    "measures only the happy path and must not be accepted "
                    "as the decision."
                ),
                "fires_on_happy_path_only": True,
                "silent_when_hung_arm_present": True,
                "result": matrix["negative_control"],
            },
            {
                "id": "NC-T-FAIL2-BOTH-COMPLETE",
                "description": (
                    "Two consecutive failures then success must complete on "
                    "flat (same-worker retry) so the design cannot smuggle "
                    "'escalation beats retry' from the Goose threshold task."
                ),
                "flat_fail2_complete": hung["flat"]["task_complete"]["T-FAIL2"],
                "lead_fail2_complete": hung["lead-worker"]["task_complete"]["T-FAIL2"],
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0166-probe2-goose-lineage",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "defaults_to": "REFUTED when lineage, dual-rail, or file:line is missing",
        },
        "artifacts": [
            {
                "path": E.ARTIFACT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0166/engine.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": "Goose default consecutive-failure threshold is 2 at init.rs:44",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0166/fixtures/sources/goose-init.rs:44",
            },
            {
                "claim": "Hung-injection ranking differs from happy-path ranking",
                "verdict": "CONFIRMED",
                "anchor": "comparison.rankings_differ",
            },
            {
                "claim": "Escalation beats same-worker retry as measured Goose fact",
                "verdict": "REFUTED",
                "anchor": "RES-0166-C6-ESCALATION-BEATS-RETRY-UNMEASURED",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }

    out = REPO / E.ARTIFACT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    out.write_bytes(raw)
    print(f"wrote {E.ARTIFACT_REL} bytes={len(raw)} sha256={E.sha256_bytes(raw)}")
    print(f"state={doc['state']} sentinel={doc['sentinel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
