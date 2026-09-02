#!/usr/bin/env python3
"""Uniform operator-item inventory and counting rule for ARC-0060.

Same rule, same records, all nine designs. Hybrid membership is an attribute
on the record (A9 in member_of), not a second counter.
"""
from __future__ import annotations

import json
from typing import Iterable

KINDS = ("concept", "config_surface", "runtime_component")
ARCHS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")

# Estate payload kinds every architecture must already handle. Counted once
# in estate_shared; excluded from architecture-specific understandability
# budgets so the comparison is not "who remembered skills exist".
ESTATE_SHARED = [
    {
        "id": "skill",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
    {
        "id": "hook",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
    {
        "id": "rule",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
    {
        "id": "workflow-blueprint",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
    {
        "id": "council-protocol",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
    {
        "id": "council-preset",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
    {
        "id": "mcp-mount",
        "kind": "concept",
        "note": "Capability class shared across A1-A9; not architecture-distinguishing.",
    },
]

# Each row is one operator-facing item a new contributor must learn to operate
# that architecture. member_of is the architectures whose operator kit includes
# the item. A9 is present only for the strongest compatible mechanism taken
# from that class (singular control planes: A3 registry-as-control-plane is
# NOT in A9 because A2 already owns capability identity).
ITEMS: list[dict] = [
    # --- A1 config-first (ARC-0003 DESIGN question) ---
    {
        "id": "load-order-manifest",
        "kind": "config_surface",
        "member_of": ["A1"],
        "source_unit": "ARC-0003",
        "excerpt": "specify the exact file set, the load order",
        "hybrid_from": None,
    },
    {
        "id": "static-json-per-id",
        "kind": "config_surface",
        "member_of": ["A1"],
        "source_unit": "ARC-0003",
        "excerpt": "every capability is declared in versioned STATIC config with no generated layer",
        "hybrid_from": None,
    },
    {
        "id": "whole-object-replacement",
        "kind": "concept",
        "member_of": ["A1"],
        "source_unit": "ARC-0003",
        "excerpt": "the precedence rule when two files declare the same capability id",
        "hybrid_from": None,
    },
    {
        "id": "overlay-closed-world",
        "kind": "concept",
        "member_of": ["A1", "A9"],
        "source_unit": "ARC-0003",
        "excerpt": "unlisted file is not loaded; overlay may not introduce a new id",
        "hybrid_from": "A1",
        "hybrid_why": "Strongest A1 mechanism that does not duplicate A2 SSOT identity: closed-world load.",
    },
    # --- A2 generated SSOT (ARC-0010 DESIGN question) ---
    {
        "id": "typed-registry",
        "kind": "config_surface",
        "member_of": ["A2", "A9"],
        "source_unit": "ARC-0010",
        "excerpt": "one typed registry from which plugin manifest, marketplace, skill/hook/rule, docs, workflow and council catalogs are ALL generated",
        "hybrid_from": "A2",
        "hybrid_why": "SSOT for capability identity and bytes.",
    },
    {
        "id": "registry-schema",
        "kind": "config_surface",
        "member_of": ["A2", "A9"],
        "source_unit": "ARC-0010",
        "excerpt": "Define the registry schema",
        "hybrid_from": "A2",
    },
    {
        "id": "generated-artifact-tree",
        "kind": "config_surface",
        "member_of": ["A2", "A9"],
        "source_unit": "ARC-0010",
        "excerpt": "hand-edit of a generated artifact both detectable and reversible",
        "hybrid_from": "A2",
    },
    {
        "id": "deterministic-generator",
        "kind": "runtime_component",
        "member_of": ["A2", "A9"],
        "source_unit": "ARC-0010",
        "excerpt": "the generator's determinism contract (same input yields byte-identical output)",
        "hybrid_from": "A2",
    },
    {
        "id": "provenance-header",
        "kind": "concept",
        "member_of": ["A2", "A9"],
        "source_unit": "ARC-0010",
        "excerpt": "every generated file carries a machine-readable provenance header",
        "hybrid_from": "A2",
    },
    {
        "id": "tamper-vs-stale",
        "kind": "concept",
        "member_of": ["A2", "A9"],
        "source_unit": "ARC-0010",
        "excerpt": "hand-edit is TAMPERED when bytes differ while registry digest still matches; STALE when the registry entry changed",
        "hybrid_from": "A2",
    },
    # --- A3 marketplace-first (ARC-0017 DESIGN question) ---
    {
        "id": "package-unit-boundary",
        "kind": "concept",
        "member_of": ["A3"],
        "source_unit": "ARC-0017",
        "excerpt": "define the package unit and its boundary",
        "hybrid_from": None,
        "hybrid_why_excluded": "Capability identity is the A2 registry entry, not a second package unit.",
    },
    {
        "id": "registry-index-as-control-plane",
        "kind": "config_surface",
        "member_of": ["A3"],
        "source_unit": "ARC-0017",
        "excerpt": "the canonical registry index IS the control plane",
        "hybrid_from": None,
        "hybrid_why_excluded": "Duplicate control plane versus A2 typed-registry. Singularity forbids both.",
    },
    {
        "id": "lockfile-pin",
        "kind": "config_surface",
        "member_of": ["A3", "A9"],
        "source_unit": "ARC-0017",
        "excerpt": "every local capability arrives as an installed, versioned, lockfile-pinned package",
        "hybrid_from": "A3",
        "hybrid_why": "Pins SSOT entry versions; does not own identity.",
    },
    {
        "id": "release-channels",
        "kind": "concept",
        "member_of": ["A3"],
        "source_unit": "ARC-0017",
        "excerpt": "release channels",
        "hybrid_from": None,
        "hybrid_why_excluded": "Binding release mode on this estate is PR-ONLY; public channels are not selected.",
    },
    {
        "id": "install-update-rollback-sm",
        "kind": "concept",
        "member_of": ["A3", "A9"],
        "source_unit": "ARC-0017",
        "excerpt": "the install/update/rollback state machine",
        "hybrid_from": "A3",
    },
    {
        "id": "cache-invalidation-rule",
        "kind": "concept",
        "member_of": ["A3", "A9"],
        "source_unit": "ARC-0017",
        "excerpt": "the cache-invalidation rule that prevents a stale cache from masking a fixed package",
        "hybrid_from": "A3",
    },
    {
        "id": "package-cache",
        "kind": "runtime_component",
        "member_of": ["A3", "A9"],
        "source_unit": "ARC-0017",
        "excerpt": "stale cache masking a fixed package",
        "hybrid_from": "A3",
    },
    # --- A4 gateway / lazy-activation (ARC-0024 DESIGN question) ---
    {
        "id": "gateway-capability-index",
        "kind": "config_surface",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "one mediating entry point that INDEXES all capabilities but materializes only what a task selects",
        "hybrid_from": "A4",
    },
    {
        "id": "selection-interface",
        "kind": "concept",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "Define the index format, the selection interface",
        "hybrid_from": "A4",
    },
    {
        "id": "activation-lifecycle",
        "kind": "concept",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "the activation and DEACTIVATION lifecycle",
        "hybrid_from": "A4",
    },
    {
        "id": "deactivation-lifecycle",
        "kind": "concept",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "the activation and DEACTIVATION lifecycle",
        "hybrid_from": "A4",
    },
    {
        "id": "per-session-budget",
        "kind": "concept",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "the per-session budget it enforces",
        "hybrid_from": "A4",
    },
    {
        "id": "resident-set-floor",
        "kind": "concept",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "exactly what remains resident when nothing is selected",
        "hybrid_from": "A4",
    },
    {
        "id": "gateway-process",
        "kind": "runtime_component",
        "member_of": ["A4", "A9"],
        "source_unit": "ARC-0024",
        "excerpt": "one mediating entry point",
        "hybrid_from": "A4",
    },
    # --- A5 distributed workflow-runtime (ARC-0031 DESIGN question) ---
    {
        "id": "work-unit-queue",
        "kind": "config_surface",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "a typed work-unit queue with an append-only resumable ledger",
        "hybrid_from": "A5",
    },
    {
        "id": "append-only-ledger",
        "kind": "config_surface",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "append-only resumable ledger",
        "hybrid_from": "A5",
    },
    {
        "id": "dispatcher-substrates",
        "kind": "runtime_component",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "dispatchers for local / worktree / cloud substrates",
        "hybrid_from": "A5",
    },
    {
        "id": "barrier-and-fanout",
        "kind": "concept",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "barriers, dynamic fan-out",
        "hybrid_from": "A5",
    },
    {
        "id": "shared-completion-reducer",
        "kind": "runtime_component",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "ONE shared completion reducer",
        "hybrid_from": "A5",
    },
    {
        "id": "unit-lifecycle-states",
        "kind": "concept",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "Define the unit lifecycle states, the ledger record",
        "hybrid_from": "A5",
    },
    {
        "id": "delivery-guarantee-idempotence",
        "kind": "concept",
        "member_of": ["A5", "A9"],
        "source_unit": "ARC-0031",
        "excerpt": "exactly-once, or at-least-once plus idempotent units",
        "hybrid_from": "A5",
    },
    # --- A6 cross-vendor adapter (ARC-0038 DESIGN question) ---
    {
        "id": "work-unit-artifact-contract",
        "kind": "concept",
        "member_of": ["A6", "A9"],
        "source_unit": "ARC-0038",
        "excerpt": "one work-unit and artifact contract with per-vendor adapters",
        "hybrid_from": "A6",
    },
    {
        "id": "per-vendor-adapter",
        "kind": "runtime_component",
        "member_of": ["A6", "A9"],
        "source_unit": "ARC-0038",
        "excerpt": "per-vendor adapters, capability negotiation",
        "hybrid_from": "A6",
    },
    {
        "id": "capability-negotiation",
        "kind": "concept",
        "member_of": ["A6", "A9"],
        "source_unit": "ARC-0038",
        "excerpt": "capability negotiation, and EXPLICIT abstraction-leak documentation",
        "hybrid_from": "A6",
    },
    {
        "id": "three-tier-contract",
        "kind": "concept",
        "member_of": ["A6", "A9"],
        "source_unit": "ARC-0038",
        "excerpt": "three tiers - what is guaranteed identical across vendors, what is best-effort, and what is vendor-only",
        "hybrid_from": "A6",
    },
    {
        "id": "min-tier-declaration",
        "kind": "concept",
        "member_of": ["A6", "A9"],
        "source_unit": "ARC-0038",
        "excerpt": "every work unit to declare the minimum tier it needs so a unit is never silently downgraded",
        "hybrid_from": "A6",
    },
    {
        "id": "abstraction-leak-doc",
        "kind": "config_surface",
        "member_of": ["A6", "A9"],
        "source_unit": "ARC-0038",
        "excerpt": "EXPLICIT abstraction-leak documentation",
        "hybrid_from": "A6",
    },
    # --- A7 security-first (ARC-0045 DESIGN question) ---
    {
        "id": "least-privilege-grants",
        "kind": "concept",
        "member_of": ["A7", "A9"],
        "source_unit": "ARC-0045",
        "excerpt": "least-privilege capability grants",
        "hybrid_from": "A7",
    },
    {
        "id": "signed-provenance-artifacts",
        "kind": "concept",
        "member_of": ["A7", "A9"],
        "source_unit": "ARC-0045",
        "excerpt": "signed provenance-bearing artifacts",
        "hybrid_from": "A7",
    },
    {
        "id": "permission-choke-point",
        "kind": "runtime_component",
        "member_of": ["A7", "A9"],
        "source_unit": "ARC-0045",
        "excerpt": "an explicit permission model evaluated at a SINGLE choke point",
        "hybrid_from": "A7",
    },
    {
        "id": "permission-model",
        "kind": "config_surface",
        "member_of": ["A7", "A9"],
        "source_unit": "ARC-0045",
        "excerpt": "an explicit permission model evaluated at a SINGLE choke point",
        "hybrid_from": "A7",
    },
    {
        "id": "secret-free-bundles",
        "kind": "concept",
        "member_of": ["A7", "A9"],
        "source_unit": "ARC-0045",
        "excerpt": "secret-free artifact bundles",
        "hybrid_from": "A7",
    },
    {
        "id": "injection-resistant-boundaries",
        "kind": "concept",
        "member_of": ["A7", "A9"],
        "source_unit": "ARC-0045",
        "excerpt": "injection-resistant boundaries for workflow and council content",
        "hybrid_from": "A7",
    },
    # --- A8 UX / product-first (ARC-0052 DESIGN question) ---
    {
        "id": "jobs-to-be-done-map",
        "kind": "concept",
        "member_of": ["A8", "A9"],
        "source_unit": "ARC-0052",
        "excerpt": "organized around the owner's actual jobs-to-be-done rather than around subsystems",
        "hybrid_from": "A8",
    },
    {
        "id": "owner-command",
        "kind": "config_surface",
        "member_of": ["A8", "A9"],
        "source_unit": "ARC-0052",
        "excerpt": "the top-level surfaces (one command, one cockpit, one catalog)",
        "hybrid_from": "A8",
    },
    {
        "id": "cockpit",
        "kind": "runtime_component",
        "member_of": ["A8", "A9"],
        "source_unit": "ARC-0052",
        "excerpt": "one command, one cockpit, one catalog",
        "hybrid_from": "A8",
    },
    {
        "id": "catalog-browser",
        "kind": "config_surface",
        "member_of": ["A8", "A9"],
        "source_unit": "ARC-0052",
        "excerpt": "one command, one cockpit, one catalog",
        "hybrid_from": "A8",
    },
    {
        "id": "naming-discovery-model",
        "kind": "concept",
        "member_of": ["A8", "A9"],
        "source_unit": "ARC-0052",
        "excerpt": "the naming and discovery model for 96 workflows plus 64 presets",
        "hybrid_from": "A8",
    },
    {
        "id": "single-error-message-contract",
        "kind": "concept",
        "member_of": ["A8", "A9"],
        "source_unit": "ARC-0052",
        "excerpt": "the SINGLE error-message contract every failure path must satisfy",
        "hybrid_from": "A8",
    },
    # --- A9 composition glue (ARC-0059 DESIGN question; DESIGN.json absent) ---
    {
        "id": "capability-to-authority-table",
        "kind": "concept",
        "member_of": ["A9"],
        "source_unit": "ARC-0059",
        "excerpt": "capability-to-authority table with exactly one authority per row",
        "hybrid_from": "A9",
    },
    {
        "id": "singularity-invariant",
        "kind": "concept",
        "member_of": ["A9"],
        "source_unit": "ARC-0059",
        "excerpt": "keeping every control plane SINGULAR (the spec forbids duplicate control planes)",
        "hybrid_from": "A9",
    },
]


def _validate_items(items: Iterable[dict]) -> None:
    seen: set[str] = set()
    for it in items:
        iid = it["id"]
        if iid in seen:
            raise ValueError(f"duplicate inventory id {iid}")
        seen.add(iid)
        if it["kind"] not in KINDS:
            raise ValueError(f"bad kind {it['kind']} on {iid}")
        extra = set(it["member_of"]) - set(ARCHS)
        if extra:
            raise ValueError(f"bad member_of {extra} on {iid}")


_validate_items(ITEMS)


def items_for(arch: str, items: Iterable[dict] | None = None) -> list[dict]:
    pool = list(ITEMS if items is None else items)
    return [it for it in pool if arch in it["member_of"]]


def count_ids_forward(arch: str, items: Iterable[dict] | None = None) -> int:
    """Headline counter: cardinality of unique ids whose member_of contains arch."""
    return len({it["id"] for it in items_for(arch, items)})


def count_ids_by_kind_sum(arch: str, items: Iterable[dict] | None = None) -> int:
    """Second counter: reverse walk, bucket by kind, sum bucket sizes.

    Must match count_ids_forward because kinds partition the id set.
    """
    buckets = {k: set() for k in KINDS}
    for it in reversed(list(items_for(arch, items))):
        buckets[it["kind"]].add(it["id"])
    return sum(len(s) for s in buckets.values())


def kind_breakdown(arch: str, items: Iterable[dict] | None = None) -> dict[str, int]:
    buckets = {k: set() for k in KINDS}
    for it in items_for(arch, items):
        buckets[it["kind"]].add(it["id"])
    return {k: len(s) for k, s in buckets.items()}


def item_ids(arch: str, items: Iterable[dict] | None = None) -> list[str]:
    return sorted({it["id"] for it in items_for(arch, items)})


def cost_payload(doc: dict) -> dict:
    """Domain payload lives under report (receipt_core additionalProperties=false)."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        "designs" in report or "headline" in report or "threshold" in report
    ):
        return report
    return doc


def load_cost(path) -> dict:
    from pathlib import Path as _Path

    doc = json.loads(_Path(path).read_text(encoding="utf-8"))
    return cost_payload(doc)


COUNTING_RULE = {
    "id": "unique-operator-item-id",
    "statement": (
        "An operator-facing item is a record with a stable id, a kind in "
        "{concept, config_surface, runtime_component}, and a member_of set. "
        "The count for architecture X is the cardinality of {id | X in member_of}. "
        "The same records and the same cardinality rule are applied to A1-A9. "
        "Estate payload classes (skill/hook/rule/workflow/council/mcp) are listed "
        "once as estate_shared and are excluded from architecture-specific counts. "
        "A9 membership is the strongest compatible mechanism from each of A1-A8 "
        "plus two composition-glue concepts; a mechanism that would create a "
        "second identity or permission plane is omitted, not summed."
    ),
    "duplicate_ids": "A second record with the same id does not increment the count.",
    "hybrid_composition": (
        "Maximal hybrid under singularity: A2 owns capability identity; A3 "
        "registry-as-control-plane is excluded; A1 contributes closed-world "
        "load only; A4 activation, A5 dispatch, A6 vendor transport, A7 "
        "permission choke, A8 presentation. A9 DESIGN.json is absent on this "
        "tree; this composition is taken from catalog DESIGN questions, not "
        "from a delivered dossier."
    ),
    "error_band": 1,
}
