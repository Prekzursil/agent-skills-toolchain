"""Generate a workflow from a typed goal, returning incumbents when covered (IMP-0193).

Generation is gated by the estate library scout (``foundry.scout.scout``):
when an incumbent already covers the goal the generator REFUSES and returns
that incumbent unchanged (avoiding ``NAMED_FAILURE_11331``); otherwise it
BUILDs a schema-valid workflow with ``synthesize``.  ``gate=False`` is the
mutant path used by the both-states probe: it always rebuilds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from foundry.constants import GENERATOR_ID, NAMED_FAILURE_11331
from foundry.scout import ADOPT, BUILD, goal_is_discovery_only
from foundry.scout import load_library
from foundry.scout import scout as library_scout


@dataclass
class Scout:
    verdict: str
    adopted_id: str | None = None
    reason: str = ""


@dataclass
class Generation:
    action: str
    rebuilt: bool
    workflow: dict | None
    named_failure_avoided: str | None = None
    scout: Scout = field(default_factory=lambda: Scout(BUILD))


# Goal verbs (and their inflections) that become stages, mapped to a stage kind.
_STAGE_LEXICON: dict[str, tuple[str, str]] = {
    "discover": ("discover", "scan"),
    "discovers": ("discover", "scan"),
    "scan": ("scan", "scan"),
    "record": ("record", "write"),
    "records": ("record", "write"),
    "compose": ("compose", "compose"),
    "composes": ("compose", "compose"),
    "merge": ("merge", "merge"),
    "merges": ("merge", "merge"),
    "fuse": ("fuse", "fuse"),
    "fuses": ("fuse", "fuse"),
    "benchmark": ("benchmark", "benchmark"),
    "benchmarks": ("benchmark", "benchmark"),
    "certify": ("certify", "certify"),
    "certifies": ("certify", "certify"),
    "publish": ("publish", "publish"),
    "publishes": ("publish", "publish"),
    "verify": ("verify", "verify"),
    "verifies": ("verify", "verify"),
    "validate": ("validate", "verify"),
    "validates": ("validate", "verify"),
    "rank": ("rank", "rank"),
    "ranks": ("rank", "rank"),
    "run": ("run", "run"),
    "runs": ("run", "run"),
    "execute": ("run", "run"),
    "executes": ("run", "run"),
    "tournament": ("tournament", "tournament"),
    "summarise": ("summarise", "report"),
    "summarize": ("summarise", "report"),
    "report": ("report", "report"),
}
_PUNCT = ".,;:!?()[]{}\"'"


def _goal_parts(goal: Mapping[str, Any] | str) -> tuple[str, str, list[str]]:
    if isinstance(goal, str):
        text = goal
        goal_id = "goal.anonymous"
        tokens = [t.lower().strip(_PUNCT) for t in text.replace("/", " ").split()]
    else:
        text = str(goal.get("text") or "")
        goal_id = str(goal.get("id") or "goal.anonymous")
        tokens = [str(t).lower().strip(_PUNCT) for t in (goal.get("tokens") or [])]
        if not tokens:
            tokens = [t.lower().strip(_PUNCT) for t in text.replace("/", " ").split()]
    return goal_id, text, [t for t in tokens if t]


def _slug(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in value.lower())
    return out.strip("-") or "anon"


def synthesize(goal: Mapping[str, Any] | str) -> dict[str, Any]:
    """Build a schema-valid workflow from a typed goal, deterministically.

    Stage verbs are read from the goal text in order of appearance (deduplicated)
    and chained linearly: each stage depends on the previous one and consumes
    its output.  A goal without a recognised verb yields a single ``plan`` stage.
    """
    goal_id, text, tokens = _goal_parts(goal)
    stage_specs: list[tuple[str, str]] = []
    for tok in tokens:
        spec = _STAGE_LEXICON.get(tok)
        if spec and spec not in stage_specs:
            stage_specs.append(spec)
    if not stage_specs:
        stage_specs = [("plan", "plan")]
    stages: list[dict[str, Any]] = []
    previous_output = "goal.json"
    previous_id: str | None = None
    for stage_id, kind in stage_specs:
        output = f"{stage_id}.json"
        stages.append(
            {
                "depends_on": [previous_id] if previous_id else [],
                "id": stage_id,
                "inputs": [previous_output],
                "kind": kind,
                "outputs": [output],
            }
        )
        previous_output = output
        previous_id = stage_id
    discovery_only = goal_is_discovery_only(goal)
    return {
        "capabilities": [stage_id for stage_id, _ in stage_specs],
        "covers": {
            "constraints": {"discovery_only": discovery_only},
            "intents": [text] if text else [],
        },
        "discovery_only": discovery_only,
        "generated": True,
        "generator": GENERATOR_ID,
        "goal": text,
        "id": "wf.generated." + _slug(goal_id),
        "kind": "workflow",
        "params": {
            "schema": {"repo": {"type": "string", "required": True}},
            "values": {"repo": "."},
        },
        "quality": 0,
        "stages": stages,
        "stopping": {"max_stages": len(stages), "on_error": "halt"},
    }


def generate_from_goal(goal: Mapping[str, Any] | str, gate: bool = True) -> Generation:
    """REFUSE with the covering incumbent, or BUILD a fresh workflow.

    ``gate=False`` disables the scout gate (mutant path): the goal is rebuilt even
    when an incumbent covers it, under a distinct ``.ungated`` workflow id.
    """
    library = load_library()
    if gate:
        verdict = library_scout(goal, library=library)
        if verdict.verdict == ADOPT and verdict.adopted_id is not None:
            incumbent = next(w for w in library if w["id"] == verdict.adopted_id)
            return Generation(
                action="REFUSE",
                rebuilt=False,
                workflow=incumbent,
                named_failure_avoided=NAMED_FAILURE_11331,
                scout=Scout(ADOPT, verdict.adopted_id, verdict.reason),
            )
        scout_record = Scout(BUILD, None, verdict.reason)
        workflow = synthesize(goal)
    else:
        scout_record = Scout(BUILD, None, "gate disabled (mutant rebuild)")
        workflow = synthesize(goal)
        workflow["id"] = workflow["id"] + ".ungated"
    return Generation(action="BUILD", rebuilt=True, workflow=workflow, scout=scout_record)


__all__ = ["Generation", "Scout", "generate_from_goal", "synthesize"]
