"""Fixture dossier sets for architectures whose live phase3 trees are absent.

These are pipeline fixtures, not ADV DESIGN rebuilds. They carry the
catalog identity tokens (so the stripper has something to remove) plus
distinctive mechanism phrases (so residual identifiability is measurable).
"""
from __future__ import annotations

import json
from pathlib import Path

from identities import ARCHITECTURES

HERE = Path(__file__).resolve().parent
FIX_ROOT = HERE / "fixtures" / "dossiers"

# Distinctive mechanism phrases retained after name/author redaction.
MECHANISMS: dict[str, dict] = {
    "A1": {
        "mechanism": (
            "Capabilities live as a versioned static JSON tree. Replacement is "
            "whole-object. There is no generated layer. A file absent from the "
            "manifest is not loaded. Form tag static-config/v1."
        ),
        "cost_note": "Whole-object replacement has no field merge and no generator.",
        "failure_note": "Unlisted files are silently not loaded.",
    },
    "A2": {
        "mechanism": (
            "A typed registry is the only hand-authored source. generate() is a "
            "pure function of registry bytes and generator_version. Two runs are "
            "byte-identical. Each generated file carries a provenance header with "
            "registry_entry_sha256."
        ),
        "cost_note": "Restore is regenerate; hand-edits are TAMPERED or STALE.",
        "failure_note": "An opaque passthrough field would reintroduce drift.",
    },
    "A3": {
        "mechanism": (
            "The package index is the control plane. Every local capability is a "
            "lockfile-pinned package. Cache-invalidation must make a "
            "stale-cache-masks-fixed-package state unreachable."
        ),
        "cost_note": "Lockfile-pinned installs plus cache-invalidation walks.",
        "failure_note": "A stale cache that masks a fixed package is a P0 miss.",
    },
    "A4": {
        "mechanism": (
            "One mediating entry indexes capabilities and materializes only what "
            "a task selects. Every class has a deactivation path. When the "
            "resident-set budget is exhausted the activator refuses an activation."
        ),
        "cost_note": "Resident-set floor plus refuse-on-exhaust, not warn-on-exhaust.",
        "failure_note": "A class without a deactivation path leaks residency.",
    },
    "A5": {
        "mechanism": (
            "A typed work-unit queue with an append-only ledger. Delivery is "
            "at-least-once plus idempotent units, not exactly-once magic. A "
            "duplicate-dispatch against the ledger yields exactly one winner."
        ),
        "cost_note": "Append-only ledger plus idempotent units.",
        "failure_note": "Non-idempotent units corrupt artifacts on replay.",
    },
    "A6": {
        "mechanism": (
            "Every contract field is GUARANTEED, best-effort, or vendor-only. A "
            "unit that declares GUARANTEED against a vendor that lacks it must "
            "FAIL LOUDLY. Capabilities are never silently downgraded."
        ),
        "cost_note": "Tier table is exhaustive; silent downgrade is forbidden.",
        "failure_note": "A missing GUARANTEED field that degrades quietly is a miss.",
    },
    "A7": {
        "mechanism": (
            "Least-privilege grants evaluate at a single choke point. Every "
            "capability path must cross it. A planted bypass path must be found "
            "before a zero-bypass claim is accepted."
        ),
        "cost_note": "One choke point; no side door.",
        "failure_note": "Gate density can block legitimate local work.",
    },
    "A8": {
        "mechanism": (
            "Surfaces follow jobs-to-be-done, not subsystem maps. Every failure "
            "path uses one error-message contract: what happened, what it means, "
            "and the exact next action."
        ),
        "cost_note": "One command, one cockpit, one catalog.",
        "failure_note": "An unmapped job is a design gap, not a footnote.",
    },
    "A9": {
        "mechanism": (
            "The composed system keeps a singular control plane. Each borrowed "
            "mechanism is cited. The capability-to-authority table has exactly "
            "one authority per row."
        ),
        "cost_note": "Singularity over maximal concatenation.",
        "failure_note": "Two authorities on one capability is a P0 design defect.",
    },
}


def dossier_doc(arch_id: str, kind: str) -> dict:
    meta = next(row for row in ARCHITECTURES if row["id"] == arch_id)
    mech = MECHANISMS[arch_id]
    vendor = "anthropic" if arch_id in {"A1", "A3", "A5", "A7", "A9"} else "cursor"
    model = "opus" if vendor == "anthropic" else "grok-4.6"
    if kind == "DESIGN":
        return {
            "architecture_id": arch_id,
            "architecture_name": meta["name"],
            "unit_id": meta["design_unit"],
            "kind": "DESIGN",
            "produced_by": {
                "vendor": vendor,
                "model": model,
                "path": f"C:/Users/Prekzursil/.claude/harness/{arch_id}.md",
            },
            "answer": (
                f"{arch_id} ({meta['name']}) is described here as a pipeline "
                f"fixture, not as a live ADV dossier. {mech['mechanism']}"
            ),
            "mechanism": mech["mechanism"],
            "file_set": [
                {
                    "path": f"command-center/control-plane/{arch_id}/MANIFEST.json",
                    "role": "index",
                },
                {
                    "path": f"command-center/control-plane/{arch_id}/capabilities/",
                    "role": "capabilities",
                },
                {
                    "path": f"command-center/phase3/{arch_id}/DESIGN.json",
                    "role": "dossier",
                },
            ],
        }
    if kind == "COST":
        return {
            "architecture_id": arch_id,
            "architecture_name": meta["name"],
            "kind": "COST",
            "produced_by": {"vendor": vendor, "model": model},
            "note": mech["cost_note"],
            "mechanism": mech["mechanism"],
        }
    return {
        "architecture_id": arch_id,
        "architecture_name": meta["name"],
        "kind": "FAILURE-MODES",
        "produced_by": {"vendor": vendor, "model": model},
        "note": mech["failure_note"],
        "mechanism": mech["mechanism"],
    }


def ensure_fixtures() -> list[str]:
    written: list[str] = []
    for row in ARCHITECTURES:
        dest = FIX_ROOT / row["id"]
        dest.mkdir(parents=True, exist_ok=True)
        for kind in ("DESIGN", "COST", "FAILURE-MODES"):
            path = dest / f"{kind}.json"
            doc = dossier_doc(row["id"], kind)
            path.write_text(
                json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            written.append(str(path.relative_to(HERE.parents[3])))
    return written
