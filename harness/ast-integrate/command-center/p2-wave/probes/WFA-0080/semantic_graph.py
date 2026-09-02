#!/usr/bin/env python3
"""Canonical mechanism vocabulary and semantic component graph for WFA-0080.

Upstream WFA-0058 (vocabulary), WFA-0059 (extraction matrix), WFA-0062
(conflicts) and WFA-0066 (dedup) artifacts are absent on this worktree, as
is 08-WORKFLOW-CANDIDATE-REGISTRY.json. The vocabulary here is a frozen,
catalog-grounded reconstruction: every id is named by WFA-0027, WFA-0044,
WFA-0062 or WFA-0080 itself. It is not an extraction from 284 candidate
records. Downstream consumers must treat status=RECONSTRUCTED-FROM-CATALOG.
"""
from __future__ import annotations

from collections import deque
from typing import Any

UNIT = "WFA-0080"
RELATIONS = (
    "implements",
    "requires",
    "conflicts-with",
    "substitutes-for",
)

# Closed vocabulary. Order is the canonical order.
NODES: list[dict[str, str]] = [
    {
        "id": "mech.blind-independent-first-pass",
        "label": "Blind independent first pass",
        "definition": (
            "Each worker produces its result without seeing sibling drafts or "
            "a shared scratchpad. Independence is a scheduling invariant, not "
            "a prompt request."
        ),
        "discriminating_example": (
            "Two reviewers score the same artifact in isolated worktrees; "
            "neither prompt includes the other's text."
        ),
        "catalog_source": "WFA-0062 named HARD pair (vs shared-context deliberation)",
    },
    {
        "id": "mech.shared-context-deliberation",
        "label": "Shared-context deliberation",
        "definition": (
            "Workers read a common context (prior drafts, a shared board, or "
            "live transcript) before emitting. Correlation across workers is "
            "the intended effect."
        ),
        "discriminating_example": (
            "A critic prompt is concatenated with the proposer's draft before "
            "the critic runs."
        ),
        "catalog_source": "WFA-0062 named HARD pair (vs blind independent first pass)",
    },
    {
        "id": "mech.deterministic-replay",
        "label": "Deterministic replay",
        "definition": (
            "Given the same inputs, seed, tool results and clock, the run "
            "reproduces the same stage order and artifacts bit-for-bit."
        ),
        "discriminating_example": (
            "Re-running a recorded trace with recorded tool stubs yields an "
            "identical IR event log."
        ),
        "catalog_source": "WFA-0062 named HARD pair (vs nondeterministic sampling)",
    },
    {
        "id": "mech.nondeterministic-sampling",
        "label": "Nondeterministic sampling",
        "definition": (
            "Stage outputs may vary across runs with identical inputs because "
            "a sampler, temperature, or unordered set reduction is in the path."
        ),
        "discriminating_example": (
            "Two runs of the same fan-out with temperature>0 produce different "
            "ranked candidate lists."
        ),
        "catalog_source": "WFA-0062 named HARD pair (vs deterministic replay)",
    },
    {
        "id": "mech.fire-and-forget-dispatch",
        "label": "Fire-and-forget dispatch",
        "definition": (
            "The dispatcher returns after enqueueing work and does not wait "
            "for completion on that call stack. Completion is observed later, "
            "if at all, through a separate join."
        ),
        "discriminating_example": (
            "A parent stage submits N jobs to a queue and immediately proceeds "
            "to an unrelated stage."
        ),
        "catalog_source": "WFA-0062 named HARD pair (vs blocking fan-in barrier)",
    },
    {
        "id": "mech.blocking-fan-in-barrier",
        "label": "Blocking fan-in barrier",
        "definition": (
            "The caller does not proceed until a declared set of child results "
            "is present. The wait is on the call stack of the join stage."
        ),
        "discriminating_example": (
            "parallel() in a saved workflow followed by filter(Boolean) that "
            "blocks the parent until every branch returns."
        ),
        "catalog_source": "WFA-0062 named HARD pair; WFA-0044 IR fan-out/barrier",
    },
    {
        "id": "mech.dynamic-fan-out",
        "label": "Dynamic fan-out",
        "definition": (
            "The number of child tasks is computed at runtime from an input "
            "collection, not from a static graph literal."
        ),
        "discriminating_example": (
            "Fan-out width equals len(files) discovered by a glob stage."
        ),
        "catalog_source": "WFA-0027 transferable mechanism; WFA-0044 IR",
    },
    {
        "id": "mech.schema-typed-fan-in",
        "label": "Schema-typed fan-in",
        "definition": (
            "A blocking join that also validates each child payload against a "
            "declared schema before the parent resumes."
        ),
        "discriminating_example": (
            "Each branch must return {ok: bool, artifact_id: string} or the "
            "join fails closed."
        ),
        "catalog_source": "WFA-0044/WFA-0045 schema-typed fan-in",
    },
    {
        "id": "mech.completion-event-join",
        "label": "Completion-event join",
        "definition": (
            "A join implemented by counting completion events on a bus rather "
            "than parking the parent call stack. Cardinality is the same as a "
            "barrier; scheduling is not."
        ),
        "discriminating_example": (
            "Parent subscribes to N job-done events and continues when the "
            "counter hits N, while other stages keep running."
        ),
        "catalog_source": "WFA-0080 substitutes-for (worked rewrite of blocking barrier)",
    },
    {
        "id": "mech.state-model",
        "label": "State model",
        "definition": (
            "A named, typed snapshot of workflow memory that stages read and "
            "reduce. Distinct from 'whatever the prompt currently contains'."
        ),
        "discriminating_example": (
            "A reducer merges branch outputs into state.files: list[Path] "
            "with an explicit conflict rule."
        ),
        "catalog_source": "WFA-0027 transferable mechanism (state model)",
    },
    {
        "id": "mech.checkpointing",
        "label": "Checkpointing",
        "definition": (
            "Durable snapshots of the state model taken at declared points so "
            "a later run can resume without replaying completed stages."
        ),
        "discriminating_example": (
            "After each certified stage, write state.json + event-log offset "
            "to an append-only store."
        ),
        "catalog_source": "WFA-0027 transferable mechanism (checkpointing)",
    },
    {
        "id": "mech.resume-from-checkpoint",
        "label": "Resume from checkpoint",
        "definition": (
            "Load a checkpoint and continue from the next uncompleted stage. "
            "A resume that restarts from zero is not this mechanism."
        ),
        "discriminating_example": (
            "Kill a run after stage 3; restart loads checkpoint-3 and skips "
            "stages 1-3."
        ),
        "catalog_source": "WFA-0027 transferable mechanism (resume)",
    },
    {
        "id": "mech.retry-semantics",
        "label": "Retry semantics",
        "definition": (
            "A declared policy for re-attempting a failed stage: retryable "
            "error class, backoff, attempt cap, and what is replayed."
        ),
        "discriminating_example": (
            "HTTP 429 is retried three times with jitter; schema-invalid is "
            "never retried."
        ),
        "catalog_source": "WFA-0027 transferable mechanism (retry semantics)",
    },
    {
        "id": "mech.human-checkpoint",
        "label": "Human checkpoint",
        "definition": (
            "Progress is gated on an explicit human decision recorded as a "
            "first-class event. Silence is not consent."
        ),
        "discriminating_example": (
            "interrupt-before publish until an owner records approve|reject "
            "on the checkpoint record."
        ),
        "catalog_source": "WFA-0027 human-in-the-loop; WFA-0044 human checkpoints",
    },
    {
        "id": "mech.gate-predicate",
        "label": "Gate predicate",
        "definition": (
            "An executable boolean over IR state that must hold before a "
            "downstream stage is scheduled. Failed gates fail closed."
        ),
        "discriminating_example": (
            "publish is scheduled only if certification.verdict == PASS and "
            "licence.class != UNCLASSIFIED."
        ),
        "catalog_source": "WFA-0044 IR gates",
    },
    {
        "id": "mech.tool-policy-bound",
        "label": "Tool policy bound",
        "definition": (
            "The set of tools a stage may invoke is declared and enforced. "
            "An undeclared tool call is a fault, not a convenience."
        ),
        "discriminating_example": (
            "A research stage may WebFetch but must not Shell(git push)."
        ),
        "catalog_source": "WFA-0044 IR tool policy",
    },
    {
        "id": "mech.stage-pipeline",
        "label": "Stage pipeline",
        "definition": (
            "A totally ordered sequence of stages where each stage's outputs "
            "are the next stage's inputs. No implicit parallelism."
        ),
        "discriminating_example": (
            "extract -> normalise -> certify -> emit, each waiting on the prior."
        ),
        "catalog_source": "WFA-0044 IR stages",
    },
    {
        "id": "mech.role-assignment",
        "label": "Role assignment",
        "definition": (
            "A stage is bound to a named role (proposer, critic, owner) with "
            "a contract, not merely to 'an agent'."
        ),
        "discriminating_example": (
            "The critic role cannot mint a new option_id; only proposer can."
        ),
        "catalog_source": "WFA-0044 IR roles",
    },
    {
        "id": "mech.loop-with-convergence",
        "label": "Loop with convergence",
        "definition": (
            "A cycle in the stage graph that must terminate by a declared "
            "convergence rule, not by hoping the model stops."
        ),
        "discriminating_example": (
            "Repair loop ends when gate-predicate holds or attempt==3, "
            "whichever first."
        ),
        "catalog_source": "WFA-0044 IR loops with convergence rules",
    },
    {
        "id": "mech.stopping-expression",
        "label": "Stopping expression",
        "definition": (
            "A closed expression that decides whether the workflow is done. "
            "Absence of more work is not a stop rule."
        ),
        "discriminating_example": (
            "stop if residual_unknowns.P0_or_P1 == 0 AND reviewer.verdict == PASS."
        ),
        "catalog_source": "WFA-0044 IR stopping expressions",
    },
    {
        "id": "mech.lineage-preservation",
        "label": "Lineage preservation",
        "definition": (
            "Every derived artifact carries pointers to the source artifacts "
            "and stages that produced it, sufficient to decompose a fusion."
        ),
        "discriminating_example": (
            "A fused IR document lists source_ids exactly matching the "
            "inputs of the fusion operator."
        ),
        "catalog_source": "WFA-0044 IR lineage; WFA-0063 fusion decomposability",
    },
    {
        "id": "mech.append-only-ledger",
        "label": "Append-only ledger",
        "definition": (
            "Workflow events are recorded by append, never by in-place edit. "
            "The ledger is the source of truth for what happened."
        ),
        "discriminating_example": (
            "A retried stage writes a second attempt record; the first remains."
        ),
        "catalog_source": "WFA-0027 checkpoint/resume implies durable event history",
    },
    {
        "id": "mech.idempotent-unit",
        "label": "Idempotent unit",
        "definition": (
            "Applying a work unit twice with the same id has the same effect "
            "as applying it once. Required for safe retry."
        ),
        "discriminating_example": (
            "PUT artifact/{id} overwrites with the same bytes; a second retry "
            "does not fork a sibling id."
        ),
        "catalog_source": "WFA-0027 retry semantics (idempotence as the retry safety)",
    },
    {
        "id": "mech.exactly-once-delivery",
        "label": "Exactly-once delivery",
        "definition": (
            "A broker-level claim that each unit is delivered once. Without "
            "an idempotent consumer this claim is not reconstructible from "
            "retry-plus-ledger alone."
        ),
        "discriminating_example": (
            "A queue API that de-duplicates by message id before the worker "
            "sees the payload."
        ),
        "catalog_source": (
            "WFA-0080 substitutes-for target; contrasts WFA-0027 retry semantics"
        ),
    },
    {
        "id": "mech.at-least-once-idempotent-delivery",
        "label": "At-least-once plus idempotent delivery",
        "definition": (
            "Units may arrive more than once; safety comes from idempotent "
            "apply plus a ledger of applied ids, not from broker exactly-once."
        ),
        "discriminating_example": (
            "Worker retries until ledger.has(unit_id); duplicate arrivals no-op."
        ),
        "catalog_source": "WFA-0080 worked substitution for exactly-once delivery",
    },
    {
        "id": "mech.worktree-isolation",
        "label": "Worktree isolation",
        "definition": (
            "A stage's filesystem effects are confined to a disposable "
            "worktree. Sibling stages do not share a mutable tree."
        ),
        "discriminating_example": (
            "Saved workflows set a worktree isolation flag so parallel() "
            "branches cannot clobber each other's files."
        ),
        "catalog_source": "WFA-0045 worktree isolation flags",
    },
    {
        "id": "mech.degrade-loudly",
        "label": "Degrade loudly",
        "definition": (
            "When a capability is missing, the workflow emits a structured "
            "degradation event naming what was lost. Silent fallback is a "
            "different, forbidden mechanism."
        ),
        "discriminating_example": (
            "Adapter cannot carry interrupt-before: it records NON-TRANSFERABLE "
            "and refuses ADOPT, rather than dropping the checkpoint."
        ),
        "catalog_source": "WFA-0055 degrade loudly; WFA-0080 honesty about substitution",
    },
]


def _sub_completion_event_join() -> dict[str, Any]:
    return {
        "construction": (
            "Replace a blocking fan-in wait() on the parent stack with a "
            "subscribe(completion-events) counter. Declare the same cardinality "
            "N. The parent enqueues N children (fire-and-forget), then registers "
            "a join continuation that fires when N distinct child-ids report "
            "done. Other unrelated stages continue. The join is still a join; "
            "it is no longer a blocking call-stack barrier."
        ),
        "ir_rewrite": (
            "stage.join: blocking-fan-in-barrier(children=C) "
            "=> dispatch fire-and-forget(C) + on_event(child.done, count==|C|) "
            "-> continue(parent)."
        ),
        "capability_preserved": [
            "join cardinality N",
            "parent does not proceed until all children complete or fail closed",
        ],
        "capability_lost": [
            "call-stack parking of the parent",
            "implicit exclusion of sibling parent work during the wait",
        ],
        "not_justified_by": "similarity",
    }


def _sub_at_least_once() -> dict[str, Any]:
    return {
        "construction": (
            "Express exactly-once delivery as at-least-once dispatch plus an "
            "idempotent apply guarded by an append-only ledger of applied "
            "unit ids. On receive: if ledger.contains(id) then no-op; else "
            "apply and append id. Retries are required (retry-semantics) and "
            "safe because apply is idempotent. This is a construction, not a "
            "claim that the broker itself de-duplicated."
        ),
        "ir_rewrite": (
            "broker.exactly-once(unit) => "
            "retry(dispatch(unit)) ; apply if not ledger.has(unit.id) ; "
            "ledger.append(unit.id)."
        ),
        "capability_preserved": [
            "no double apply of a unit id",
            "eventual apply under retryable failure",
        ],
        "capability_lost": [
            "broker-enforced single delivery",
            "freedom to use a non-idempotent apply function",
        ],
        "not_justified_by": "similarity",
    }


def _sub_human_for_gate() -> dict[str, Any]:
    return {
        "construction": (
            "When the gate predicate is 'owner approval' (not a machine-checkable "
            "licence or schema condition), rewrite gate(expr) as a human "
            "checkpoint whose recorded approve|reject event is the predicate. "
            "The downstream stage is scheduled only after the checkpoint "
            "record exists. This substitution is illegal for machine predicates "
            "such as schema validity — those stay gate-predicate."
        ),
        "ir_rewrite": (
            "gate(owner.approved==true) => human-checkpoint(role=owner, "
            "options=[approve,reject]) ; proceed iff event==approve."
        ),
        "capability_preserved": [
            "downstream does not run without an explicit decision",
            "decision is a first-class event",
        ],
        "capability_lost": [
            "unattended / automated gating",
            "reproducible predicate evaluation without a human",
        ],
        "not_justified_by": "similarity",
    }


# Directed edges. conflicts-with is recorded in both directions.
_EDGE_SPECS: list[dict[str, Any]] = [
    {
        "source": "mech.blind-independent-first-pass",
        "target": "mech.shared-context-deliberation",
        "relation": "conflicts-with",
        "justification": (
            "The same worker cannot both be isolated from sibling drafts and "
            "read those drafts. A fusion that sets both on one composition "
            "slot is unsatisfiable (WFA-0062 HARD pair; experimental "
            "exhibition is WFA-0062's artifact, absent here)."
        ),
    },
    {
        "source": "mech.deterministic-replay",
        "target": "mech.nondeterministic-sampling",
        "relation": "conflicts-with",
        "justification": (
            "Bit-identical replay cannot hold if a sampler with residual "
            "entropy sits on the path. WFA-0062 HARD pair."
        ),
    },
    {
        "source": "mech.fire-and-forget-dispatch",
        "target": "mech.blocking-fan-in-barrier",
        "relation": "conflicts-with",
        "justification": (
            "A single composition slot cannot both return immediately after "
            "enqueue and park until children complete. WFA-0062 HARD pair. "
            "A workflow MAY use both at different slots (dispatch then a "
            "later join); the conflict is per slot."
        ),
    },
    {
        "source": "mech.schema-typed-fan-in",
        "target": "mech.blocking-fan-in-barrier",
        "relation": "implements",
        "justification": (
            "Schema-typed fan-in is a blocking join plus per-child schema "
            "validation. It realises the barrier and adds a contract."
        ),
    },
    {
        "source": "mech.dynamic-fan-out",
        "target": "mech.fire-and-forget-dispatch",
        "relation": "requires",
        "justification": (
            "Runtime-width fan-out must enqueue a computed set of children "
            "without statically listing them in the parent stack."
        ),
    },
    {
        "source": "mech.resume-from-checkpoint",
        "target": "mech.checkpointing",
        "relation": "requires",
        "justification": (
            "Resume loads a durable snapshot. Without checkpointing there is "
            "nothing to resume from except a full restart."
        ),
    },
    {
        "source": "mech.checkpointing",
        "target": "mech.state-model",
        "relation": "requires",
        "justification": (
            "A checkpoint is a snapshot of a named state model. Prompt-buffer "
            "dumps are not checkpoints."
        ),
    },
    {
        "source": "mech.loop-with-convergence",
        "target": "mech.stopping-expression",
        "relation": "requires",
        "justification": (
            "A loop without a closed stopping expression is an unbounded "
            "cycle, which the IR forbids."
        ),
    },
    {
        "source": "mech.at-least-once-idempotent-delivery",
        "target": "mech.retry-semantics",
        "relation": "requires",
        "justification": (
            "At-least-once delivery is realised by retrying until apply is "
            "acknowledged. The retry policy is required, not optional."
        ),
    },
    {
        "source": "mech.at-least-once-idempotent-delivery",
        "target": "mech.idempotent-unit",
        "relation": "requires",
        "justification": (
            "Duplicate arrivals must no-op. Without idempotent apply, retry "
            "forks effects."
        ),
    },
    {
        "source": "mech.at-least-once-idempotent-delivery",
        "target": "mech.append-only-ledger",
        "relation": "requires",
        "justification": (
            "Applied ids must be durable across retries. The ledger is that "
            "memory."
        ),
    },
    {
        "source": "mech.completion-event-join",
        "target": "mech.blocking-fan-in-barrier",
        "relation": "substitutes-for",
        "justification": (
            "Same join cardinality, different scheduling. Worked rewrite "
            "below; not a similarity claim."
        ),
        "worked_substitution": _sub_completion_event_join(),
    },
    {
        "source": "mech.at-least-once-idempotent-delivery",
        "target": "mech.exactly-once-delivery",
        "relation": "substitutes-for",
        "justification": (
            "Exactly-once as a broker primitive is replaced by at-least-once "
            "plus idempotent apply plus ledger. Worked rewrite below."
        ),
        "worked_substitution": _sub_at_least_once(),
    },
    {
        "source": "mech.human-checkpoint",
        "target": "mech.gate-predicate",
        "relation": "substitutes-for",
        "justification": (
            "Only for predicates that ARE owner decisions. Machine predicates "
            "stay gates. Worked rewrite below."
        ),
        "worked_substitution": _sub_human_for_gate(),
    },
]


def vocab_ids() -> list[str]:
    return [n["id"] for n in NODES]


def vocab_id_set() -> set[str]:
    return set(vocab_ids())


def _conflict_both_ways(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for spec in specs:
        rel = spec["relation"]
        pairs = [(spec["source"], spec["target"])]
        if rel == "conflicts-with":
            pairs.append((spec["target"], spec["source"]))
        for src, tgt in pairs:
            key = (src, tgt, rel)
            if key in seen:
                continue
            seen.add(key)
            edge = {
                "id": f"e:{rel}:{src}->{tgt}",
                "source": src,
                "target": tgt,
                "relation": rel,
                "justification": spec["justification"],
            }
            if "worked_substitution" in spec and src == spec["source"]:
                edge["worked_substitution"] = spec["worked_substitution"]
            out.append(edge)
    out.sort(key=lambda e: e["id"])
    return out


def edges() -> list[dict[str, Any]]:
    return _conflict_both_ways(_EDGE_SPECS)


def undirected_components(node_ids: list[str], edge_list: list[dict[str, Any]]) -> list[list[str]]:
    adj: dict[str, set[str]] = {n: set() for n in node_ids}
    for e in edge_list:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in node_ids:
        if start in seen:
            continue
        q = deque([start])
        seen.add(start)
        members: list[str] = []
        while q:
            u = q.popleft()
            members.append(u)
            for v in sorted(adj[u]):
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        comps.append(sorted(members))
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def component_report(node_ids: list[str], edge_list: list[dict[str, Any]]) -> dict[str, Any]:
    comps = undirected_components(node_ids, edge_list)
    sizes = [len(c) for c in comps]
    largest = comps[0]
    spanning = len(node_ids) > 1 and sizes[0] == len(node_ids)
    explanation = (
        "Relations are typed and local, so the graph partitions. Conflicts "
        "bind mutually exclusive composition-slot pairs; requires/implements/"
        "substitutes-for bind small families (dispatch/join, durability, "
        "gating, loops). Isolated nodes are mechanisms that this reconstructed "
        "vocabulary does not yet relate — they are listed, not defaulted into "
        "a clique. A single component spanning every node would be the same "
        "failure mode as the 108-blueprint compat graph and is a FINDING, not "
        f"a result to ship. Here: {len(comps)} components, largest size "
        f"{sizes[0]} ({', '.join(largest)}). spanning={spanning}."
    )
    return {
        "count": len(comps),
        "sizes": sizes,
        "largest_size": sizes[0],
        "largest_members": largest,
        "spanning": spanning,
        "explanation": explanation,
        "components": [{"size": len(c), "members": c} for c in comps],
    }


def endpoint_errors(node_ids: set[str], edge_list: list[dict[str, Any]]) -> list[str]:
    bad: list[str] = []
    for e in edge_list:
        if e["source"] not in node_ids:
            bad.append(f"dangling-source:{e['id']}:{e['source']}")
        if e["target"] not in node_ids:
            bad.append(f"dangling-target:{e['id']}:{e['target']}")
    return bad


def node_set_delta(node_ids: set[str], vocab: set[str]) -> dict[str, list[str]]:
    missing = sorted(vocab - node_ids)
    extra = sorted(node_ids - vocab)
    return {
        "missing_from_graph": missing,
        "extra_in_graph": extra,
        "missing_from_graph": missing,
        "extra_in_graph": extra,
    }


def not_isomorphic_reasons(
    n_nodes: int,
    n_components: int,
    largest: int,
    node_kind: str,
    relations: set[str],
    signature: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if n_nodes != int(signature["n_nodes"]):
        reasons.append(
            f"|V| {n_nodes} != workflow {signature['n_nodes']}"
        )
    if n_components != int(signature["n_components"]):
        reasons.append(
            f"components {n_components} != workflow {signature['n_components']}"
        )
    if largest != int(signature["largest_component"]):
        reasons.append(
            f"largest {largest} != workflow {signature['largest_component']}"
        )
    if node_kind != signature["node_kind"]:
        reasons.append(
            f"node_kind {node_kind} != {signature['node_kind']}"
        )
    sig_rel = set(signature["edge_relations"])
    if relations != sig_rel:
        reasons.append(
            f"relations {sorted(relations)} != {sorted(sig_rel)}"
        )
    if signature.get("expresses_substitution") is False and "substitutes-for" in relations:
        reasons.append("this graph expresses substitutes-for; workflow compat cannot")
    return reasons


def spanning_mutant_edges(node_ids: list[str]) -> list[dict[str, Any]]:
    """Chain requires edges so the undirected graph becomes one component."""
    extra: list[dict[str, Any]] = []
    for a, b in zip(node_ids, node_ids[1:]):
        extra.append(
            {
                "id": f"e:mutant-requires:{a}->{b}",
                "source": a,
                "target": b,
                "relation": "requires",
                "justification": "PLANTED spanning mutant for the partition detector",
            }
        )
    return extra


def graph_payload() -> dict[str, Any]:
    ids = vocab_ids()
    idset = set(ids)
    edge_list = edges()
    dangling = endpoint_errors(idset, edge_list)
    if dangling:
        raise RuntimeError(f"builder produced dangling endpoints: {dangling}")
    delta = node_set_delta(idset, idset)
    if delta["missing_from_graph"] or delta["extra_in_graph"]:
        raise RuntimeError(f"builder vocabulary mismatch: {delta}")
    report = component_report(ids, edge_list)
    if report["spanning"]:
        raise RuntimeError(
            "builder produced a spanning component; that is a FINDING, not a shippable graph"
        )
    nodes_out = []
    for n in NODES:
        nodes_out.append(
            {
                "id": n["id"],
                "kind": "canonical-mechanism",
                "label": n["label"],
                "definition": n["definition"],
                "discriminating_example": n["discriminating_example"],
                "catalog_source": n["catalog_source"],
            }
        )
    rels_present = sorted({e["relation"] for e in edge_list})
    return {
        "nodes": nodes_out,
        "edges": edge_list,
        "component_report": report,
        "relations_present": rels_present,
        "n_nodes": len(ids),
        "n_edges": len(edge_list),
    }


# Names used by emit_graph.py / probe1.
graph_payload = graph_payload
vocab_ids = vocab_ids
vocab_id_set = vocab_id_set
not_isomorphic_reasons = not_isomorphic_reasons
node_set_delta = node_set_delta
