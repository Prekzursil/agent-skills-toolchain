"""Workflow foundry: scout, forge, fuse, certify and run typed workflows.

Every capability is a real submodule imported by dotted path
(``foundry.candidate_registry``, ``tools.foundry.completion_predicate`` ...).
The package module re-exports only the typed-workflow runtime entry points so
``from foundry import execute`` keeps working for callers that treat the
package as the runtime facade.

Submodules
----------
candidate_registry    hash-chained JSONL ledger of imported candidates (IMP-0154)
certification_gate    certify a forged workflow against the completion predicate
compat_map            capability compatibility map (IMP-0175)
completion_predicate  the single completion reducer + condition checkers (WFA-0134)
constants             generator id, violation ids, named failures
consumer              consumer-side workflow intake
counters              process-local engine counters (IMP-0254)
forge                 workflow forge (adopt / mutate / fuse)
fusion_ops            fusion operators with contract checks
generate              goal-driven workflow generation (IMP-0193)
local_runner          local runner reading the completion predicate
oracle                runtime-receipt oracle
provenance            refetch + provenance verification (IMP-0155)
runtime               typed workflow loader / executor (ADV-0031, IMP-0209)
scout                 library coverage scout
stage_extract         stage projection for extracted workflows (IMP-0164)
tournament            pairwise tournament ranking
tournament_runner     tournament driver
typed_goal            typed goal parser
"""
from __future__ import annotations

from .runtime import TypedWorkflowError, execute, load_workflow

__all__ = [
    "TypedWorkflowError",
    "execute",
    "load_workflow",
    "candidate_registry",
    "certification_gate",
    "compat_map",
    "completion_predicate",
    "constants",
    "consumer",
    "counters",
    "forge",
    "fusion_ops",
    "generate",
    "local_runner",
    "oracle",
    "provenance",
    "runtime",
    "scout",
    "stage_extract",
    "tournament",
    "tournament_runner",
    "typed_goal",
]
