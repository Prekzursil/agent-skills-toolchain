#!/usr/bin/env python3
"""Shared two-rail evidence helpers for RES-0069.

R1 is a GitHub Contents API JSON envelope (structured).
R2 is a prose capture (raw markdown or rendered docs HTML).
A CONFIRMED claim may not rest on a single rail (05-ECO E3 rule).
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
INDEX = SNAP / "_index.json"
ART = REPO / "command-center" / "research" / "RES-0069.json"
SENTINEL = (
    "SUCCESS:RES-0069 in the receipt AND a per-engine loop-guard table "
    "distinguishing mandatory from optional guards"
)
QUESTION = (
    "Which engines express a loop that terminates on a CONDITION rather "
    "than a fixed count, how is the condition evaluated, and how does each "
    "prevent an infinite loop when the condition never becomes true?"
)
GUARD_CLASSES = frozenset({"MANDATORY", "OPTIONAL"})

# Load-bearing snippet per snapshot. Snippets must occur in the *searchable*
# body (decoded GitHub Contents payload, or raw/HTML bytes).
SNIPPETS: dict[str, str] = {
    "gh_azure_docs_until": 'To prevent endless loops, an "Until" loop',
    "learn_azure_until": "To prevent endless loops",
    "gh_azure_limits": "Default: 60",
    "learn_azure_limits": "Default: 60",
    "gh_n8n_split": "stuck in an infinite loop",
    "raw_n8n_split": "If your termination condition never matches, your workflow execution will get stuck in an infinite loop.",
    "gh_langgraph_errors": "This prevents infinite loops.",
    "docs_langgraph_errors": "This is often due to an infinite loop caused by code",
    "gh_airflow_sensor_tasksdk": "timeout: timedelta | float | None = None",
    "raw_airflow_docs_sensors": "Maximum time in seconds the sensor is allowed to run before failing.",
    "gh_airflow_config_yml": "Sensor default timeout, 7 days by default",
    "raw_airflow_config_yml": 'default: "604800"',
    "gh_cdk_choice": "A choice state can be used to make decisions based on the execution",
    "raw_sfn_quotas_md": "25,000 events in a single state machine execution history",
    "gh_temporal_continue_encyc": "your Workflow can run forever",
    "raw_temporal_timeouts": "we generally do not recommend setting Workflow Timeouts",
    "gh_durable_md": "run indefinitely by periodically resetting their own history",
    "learn_durable_eternal": "scenario that requires an infinite loop without unbounded history growth",
}

# claim_id -> (rail_a snapshot, rail_b snapshot)
CLAIM_RAILS: dict[str, tuple[str, str]] = {
    "C-AZURE-UNTIL": ("gh_azure_docs_until", "learn_azure_until"),
    "C-AZURE-UNTIL-LIMITS": ("gh_azure_limits", "learn_azure_limits"),
    "C-N8N-OPTIONAL": ("gh_n8n_split", "raw_n8n_split"),
    "C-LANGGRAPH-RECURSION": ("gh_langgraph_errors", "docs_langgraph_errors"),
    "C-AIRFLOW-SENSOR": ("gh_airflow_sensor_tasksdk", "raw_airflow_docs_sensors"),
    "C-AIRFLOW-DEFAULT-TIMEOUT": ("gh_airflow_config_yml", "raw_airflow_config_yml"),
    "C-SFN-CHOICE-QUOTA": ("gh_cdk_choice", "raw_sfn_quotas_md"),
    "C-TEMPORAL-FOREVER": ("gh_temporal_continue_encyc", "raw_temporal_timeouts"),
    "C-DURABLE-ETERNAL": ("gh_durable_md", "learn_durable_eternal"),
}

CONTROL_ENGINES = frozenset(
    {"n8n Loop Over Items", "Temporal Workflow", "Azure Durable Functions"}
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def load_index() -> dict[str, Any]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def snapshot_path(name: str) -> Path:
    return SNAP / f"{name}.bin"


def is_github_contents(raw: bytes) -> bool:
    if not raw.lstrip().startswith(b"{"):
        return False
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and doc.get("encoding") == "base64" and "content" in doc


def searchable_text(raw: bytes) -> str:
    """Plaintext a snippet checker can search.

    GitHub Contents API JSON stores the file as base64; search the decoded
    payload, not the envelope.
    """
    if is_github_contents(raw):
        doc = json.loads(raw.decode("utf-8"))
        blob = base64.b64decode(doc["content"])
        return blob.decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def github_meta(raw: bytes) -> dict[str, Any] | None:
    if not is_github_contents(raw):
        return None
    doc = json.loads(raw.decode("utf-8"))
    return {
        "blob_sha": doc.get("sha"),
        "html_url": doc.get("html_url"),
        "git_url": doc.get("git_url"),
        "download_url": doc.get("download_url"),
        "size": doc.get("size"),
        "path": doc.get("path"),
        "encoding": doc.get("encoding"),
    }


def rail_kind_for(name: str, raw: bytes) -> str:
    if name.startswith("gh_") or is_github_contents(raw):
        return "structured-api"
    return "prose"


def build_rail(name: str, index: dict[str, Any]) -> dict[str, Any]:
    rec = index.get(name) or {}
    path = snapshot_path(name)
    raw = path.read_bytes()
    live_sha, live_bytes = sha256_file(path)
    meta = github_meta(raw)
    kind = rail_kind_for(name, raw)
    permalink = None
    if meta and meta.get("git_url"):
        permalink = meta["git_url"]
    else:
        permalink = rec.get("final_url") or rec.get("request_url")
    snippet = SNIPPETS[name]
    body = searchable_text(raw)
    if snippet not in body:
        raise ValueError(f"snippet missing in {name}: {snippet!r}")
    status = rec.get("http_status")
    if status != 200:
        raise ValueError(f"snapshot {name} http_status={status}")
    rail: dict[str, Any] = {
        "id": name,
        "kind": kind,
        "request_url": rec.get("request_url"),
        "final_url": rec.get("final_url") or rec.get("request_url"),
        "permalink": permalink,
        "fetched_at": rec.get("fetched_at"),
        "http_status": status,
        "sha256": live_sha,
        "bytes": live_bytes,
        "snapshot": f"command-center/p2-wave/probes/RES-0069/snapshots/{name}.bin",
        "snippet": snippet,
        "content_type": rec.get("content_type"),
    }
    if meta:
        rail["github_contents"] = meta
    return rail


def claims_spec() -> list[dict[str, Any]]:
    return [
        {
            "id": "C-AZURE-UNTIL",
            "engine": "Azure Logic Apps",
            "canonical_mechanism": "Until-loop-with-expression-and-default-limits",
            "claim": (
                "Azure Logic Apps Until is a condition-terminated loop: the workflow "
                "runs inner actions, then evaluates an expression; the loop stops when "
                "the expression is true. The engine documents default limits that stop "
                "the loop to prevent endless loops."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C2-probable",
            "strongest_caveat": (
                "Count and Timeout are described as optional parameters in one table, "
                "but the JSON definition ships default count=60 and timeout=PT1H and "
                "the limits page records those as engine defaults with a hard max of "
                "5,000 iterations. This unit treats the defaults as a mandatory finite "
                "bound, not as a bound the author can omit."
            ),
        },
        {
            "id": "C-AZURE-UNTIL-LIMITS",
            "engine": "Azure Logic Apps",
            "canonical_mechanism": "Until-iteration-and-timeout-ceilings",
            "claim": (
                "Until-loop iteration default is 60 (min 1, max 5,000) and timeout "
                "default is PT1H on multitenant / stateful single-tenant; stateless "
                "single-tenant timeout default is PT5M."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "Limits are versioned product quotas; a later Azure revision can "
                "change the numbers. The captured Learn page and GitHub markdown "
                "agreed on this fetch."
            ),
        },
        {
            "id": "C-N8N-OPTIONAL",
            "engine": "n8n Loop Over Items",
            "canonical_mechanism": "reset-loop-plus-If-exit-condition",
            "claim": (
                "n8n Loop Over Items with Reset plus an If node evaluates an exit "
                "condition per iteration. The docs warn that if the termination "
                "condition never matches, the workflow execution gets stuck in an "
                "infinite loop. The infinite-loop guard is optional: an infinite "
                "loop is expressible."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "This is the Reset+If pagination pattern, not the default "
                "item-count batch loop. A host-level execution timeout may still "
                "kill the process; n8n's own node docs do not install a mandatory "
                "iteration cap on that pattern."
            ),
        },
        {
            "id": "C-LANGGRAPH-RECURSION",
            "engine": "LangGraph",
            "canonical_mechanism": "recursion_limit-GraphRecursionError",
            "claim": (
                "LangGraph cyclic graphs stop on a stop-condition edge or when "
                "recursion_limit is exhausted. Exhaustion raises GraphRecursionError, "
                "documented as preventing infinite loops. The limit is always present "
                "(must be >= 1) and is raisable via config."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "The numeric default 25 lives in langchain_core RunnableConfig "
                "(DEFAULT_RECURSION_LIMIT), a different repository than langgraph. "
                "A caller can set recursion_limit to a very large integer, which "
                "makes the guard ineffective in practice while remaining present."
            ),
        },
        {
            "id": "C-AIRFLOW-SENSOR",
            "engine": "Apache Airflow",
            "canonical_mechanism": "BaseSensorOperator-poke-until-criteria",
            "claim": (
                "Airflow sensors are a condition-terminated wait: they poke until a "
                "criteria is met and fail when they time out. timeout is a "
                "BaseSensorOperator parameter documented on all sensors."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "A DAG-level while-loop in a PythonOperator is ordinary Python and "
                "is not this sensor construct. This claim is about sensors only."
            ),
        },
        {
            "id": "C-AIRFLOW-DEFAULT-TIMEOUT",
            "engine": "Apache Airflow",
            "canonical_mechanism": "sensors.default_timeout-604800",
            "claim": (
                "When BaseSensorOperator.timeout is None, Airflow reads "
                "sensors.default_timeout from config. The config template default "
                "is 604800 seconds (7 days)."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "Operators may pass an explicit timeout that overrides the default. "
                "A deployment can change sensors.default_timeout. The bound is "
                "mandatory in the sense the constructor always assigns self.timeout, "
                "not in the sense the number 7 days is unchangeable."
            ),
        },
        {
            "id": "C-SFN-CHOICE-QUOTA",
            "engine": "AWS Step Functions",
            "canonical_mechanism": "Choice-state-plus-25000-history-quota",
            "claim": (
                "Step Functions has no native Until/While. Condition-terminated "
                "iteration is expressed by a Choice state (JSONPath/JSONata rules) "
                "looping via Next. Standard executions have a hard quota of 25,000 "
                "events in a single execution history; reaching it fails the "
                "execution. Maximum execution time is 1 year (Standard) or 5 minutes "
                "(Express)."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "The 25,000-event quota is a history-size backstop, not a loop "
                "iteration counter. A sparse loop might run a long time before "
                "hitting 25,000 events; the 1-year Standard ceiling is the other "
                "hard bound. Continue-via-StartExecution is a recommended escape, "
                "not an iteration cap."
            ),
        },
        {
            "id": "C-TEMPORAL-FOREVER",
            "engine": "Temporal Workflow",
            "canonical_mechanism": "continue-as-new-optional-execution-timeout",
            "claim": (
                "Temporal Workflows may loop on arbitrary conditions in code. "
                "Continue-As-New resets Event History so a Workflow can run forever. "
                "Workflow Execution Timeout exists but Temporal's Python SDK docs "
                "generally do not recommend setting Workflow Timeouts. The "
                "iteration/stop guard is optional: an infinite loop is expressible."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "Event History limits can still fail a single run if Continue-As-New "
                "is not used. That is a history-size failure, not a condition-loop "
                "iteration cap the author must set. Cluster-level retention is out "
                "of scope."
            ),
        },
        {
            "id": "C-DURABLE-ETERNAL",
            "engine": "Azure Durable Functions",
            "canonical_mechanism": "eternal-orchestration-continue-as-new",
            "claim": (
                "Durable Task eternal orchestrations are documented as running "
                "indefinitely. continue-as-new resets orchestration history so an "
                "infinite loop can run without unbounded history growth. That API "
                "is a history-management pattern, not a mandatory stop rule. An "
                "infinite loop is expressible and first-class."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "PowerShell is documented as not supporting continue-as-new. "
                "Host/platform idle timeouts may still exist outside this article."
            ),
        },
        {
            "id": "C-ALL-ENGINES-MANDATORY-GUARDS",
            "engine": "cross-engine overclaim",
            "canonical_mechanism": "none",
            "claim": (
                "Every surveyed engine that can express a condition-terminated loop "
                "also installs a mandatory finite iteration cap, so an infinite loop "
                "is never expressible."
            ),
            "verdict": "REFUTED",
            "evidence_tier": "E2",
            "confidence": "C1-high",
            "strongest_caveat": (
                "Refuted by n8n Reset+If, Temporal Continue-As-New, and Durable "
                "Functions eternal orchestrations, each on two rails."
            ),
        },
    ]


def table_spec() -> list[dict[str, Any]]:
    return [
        {
            "engine": "Azure Logic Apps",
            "loop_construct": "Until",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "Post-iteration: the Until expression is evaluated after inner "
                "actions run; true stops the loop."
            ),
            "infinite_loop_guard": (
                "limit.count default 60 (max 5,000) AND limit.timeout default PT1H "
                "(PT5M stateless single-tenant)"
            ),
            "guard_class": "MANDATORY",
            "infinite_loop_expressible": False,
            "claim_ids": ["C-AZURE-UNTIL", "C-AZURE-UNTIL-LIMITS"],
        },
        {
            "engine": "n8n Loop Over Items",
            "loop_construct": "Loop Over Items (Reset) + If",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "If node evaluates an exit condition each iteration while Reset "
                "treats incoming data as a new set (pagination)."
            ),
            "infinite_loop_guard": (
                "Author-supplied termination condition only; docs warn an unmatched "
                "condition yields an infinite loop"
            ),
            "guard_class": "OPTIONAL",
            "infinite_loop_expressible": True,
            "claim_ids": ["C-N8N-OPTIONAL"],
        },
        {
            "engine": "LangGraph",
            "loop_construct": "cyclic graph / conditional edges",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "Routing edges / stop condition; superstep count compared to "
                "config.recursion_limit."
            ),
            "infinite_loop_guard": (
                "recursion_limit (always >= 1; GraphRecursionError on exhaustion; "
                "value is raisable)"
            ),
            "guard_class": "MANDATORY",
            "infinite_loop_expressible": False,
            "claim_ids": ["C-LANGGRAPH-RECURSION"],
        },
        {
            "engine": "Apache Airflow",
            "loop_construct": "BaseSensorOperator poke loop",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "poke() until criteria is met; timeout measured from first attempt."
            ),
            "infinite_loop_guard": (
                "timeout always assigned; None becomes sensors.default_timeout "
                "(config default 604800s / 7 days)"
            ),
            "guard_class": "MANDATORY",
            "infinite_loop_expressible": False,
            "claim_ids": ["C-AIRFLOW-SENSOR", "C-AIRFLOW-DEFAULT-TIMEOUT"],
        },
        {
            "engine": "AWS Step Functions",
            "loop_construct": "Choice + Next (no native While)",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "Choice rules (JSONPath or JSONata) evaluated against execution "
                "state; first true rule transitions via Next."
            ),
            "infinite_loop_guard": (
                "Hard quota 25,000 execution-history events (fails the execution) "
                "and max execution time 1 year Standard / 5 minutes Express"
            ),
            "guard_class": "MANDATORY",
            "infinite_loop_expressible": False,
            "claim_ids": ["C-SFN-CHOICE-QUOTA"],
        },
        {
            "engine": "Temporal Workflow",
            "loop_construct": "Workflow code loop + Continue-As-New",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "Ordinary SDK code evaluates any condition; Continue-As-New starts "
                "a fresh Event History in the same Workflow Id chain."
            ),
            "infinite_loop_guard": (
                "Workflow Execution/Run Timeout exists but is not recommended; "
                "Continue-As-New is a history reset, not a stop rule"
            ),
            "guard_class": "OPTIONAL",
            "infinite_loop_expressible": True,
            "claim_ids": ["C-TEMPORAL-FOREVER"],
        },
        {
            "engine": "Azure Durable Functions",
            "loop_construct": "eternal orchestration",
            "terminates_on": "CONDITION",
            "condition_evaluation": (
                "Orchestrator code decides when to continue; continue-as-new "
                "replays with new input and empty history."
            ),
            "infinite_loop_guard": (
                "continue-as-new prevents unbounded history; it does not terminate "
                "the loop. Eternal orchestrations are designed to run indefinitely."
            ),
            "guard_class": "OPTIONAL",
            "infinite_loop_expressible": True,
            "claim_ids": ["C-DURABLE-ETERNAL"],
        },
    ]


def check_two_rails(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims") or []
    if len(claims) < 8:
        return False, f"too-few-claims:{len(claims)}"
    confirmed = 0
    for claim in claims:
        cid = claim.get("id")
        verdict = claim.get("verdict")
        rails = claim.get("rails") or claim.get("source_lineage") or []
        if verdict == "CONFIRMED":
            confirmed += 1
            if len(rails) < 2:
                return False, f"single-rail:{cid}"
            kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
            if "structured-api" not in kinds or "prose" not in kinds:
                return False, f"rails-not-independent:{cid}:{sorted(kinds)}"
            urls = [r.get("request_url") for r in rails if isinstance(r, dict)]
            if len(set(urls)) < 2:
                return False, f"same-url-rails:{cid}"
            for i, rail in enumerate(rails):
                for field in ("permalink", "fetched_at", "http_status", "sha256", "snippet"):
                    if not rail.get(field) and rail.get(field) != 0:
                        return False, f"missing-{field}:{cid}:{i}"
                if rail.get("http_status") != 200:
                    return False, f"http:{cid}:{rail.get('http_status')}"
                rel = str(rail.get("snapshot") or "")
                path = REPO / rel
                if not path.is_file():
                    return False, f"snapshot-absent:{rel}"
                live, _ = sha256_file(path)
                if live != rail.get("sha256"):
                    return False, f"sha-mismatch:{cid}:{rel}"
                body = searchable_text(path.read_bytes())
                snippet = str(rail.get("snippet") or "")
                if snippet not in body:
                    return False, f"snippet-absent:{cid}:{rel}"
        elif verdict == "REFUTED":
            if not claim.get("strongest_caveat"):
                return False, f"refuted-without-caveat:{cid}"
        else:
            return False, f"bad-verdict:{cid}:{verdict}"
    if confirmed < 7:
        return False, f"too-few-confirmed:{confirmed}"
    return True, f"claims={len(claims)} confirmed={confirmed}"


def check_loop_guard_table(doc: dict[str, Any]) -> tuple[bool, str]:
    table = doc.get("loop_guard_table") or []
    if len(table) < 6:
        return False, f"table-too-small:{len(table)}"
    optional = []
    mandatory = []
    for row in table:
        engine = row.get("engine")
        gc = row.get("guard_class")
        if gc not in GUARD_CLASSES:
            return False, f"bad-guard-class:{engine}:{gc}"
        if row.get("terminates_on") != "CONDITION":
            return False, f"not-condition:{engine}"
        flag = row.get("infinite_loop_expressible")
        if not isinstance(flag, bool):
            return False, f"missing-expressible:{engine}"
        if gc == "OPTIONAL":
            if flag is not True:
                return False, f"optional-not-expressible:{engine}"
            optional.append(engine)
        else:
            if flag is not False:
                return False, f"mandatory-marked-expressible:{engine}"
            mandatory.append(engine)
        if not row.get("infinite_loop_guard"):
            return False, f"missing-guard:{engine}"
        if not row.get("condition_evaluation"):
            return False, f"missing-eval:{engine}"
    if len(optional) < 1:
        return False, "control-absent-no-optional-guard"
    if len(mandatory) < 1:
        return False, "no-mandatory-row"
    text = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in text:
        return False, "sentinel-absent"
    refuted = [
        c
        for c in (doc.get("claims") or [])
        if c.get("id") == "C-ALL-ENGINES-MANDATORY-GUARDS"
        and c.get("verdict") == "REFUTED"
    ]
    if not refuted:
        return False, "overclaim-not-refuted"
    return True, f"mandatory={len(mandatory)} optional={len(optional)} control={optional}"
