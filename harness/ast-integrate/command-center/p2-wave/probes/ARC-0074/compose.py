#!/usr/bin/env python3
"""Compose a lineage-bearing fusion and prove it decomposes.

Decomposability is a set operation: split fusion rows by source_architecture,
match each borrowed id against that architecture's extracted mechanism set,
recompose by union. Orphans and round-trip drift fail.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from extract import extract_mechanisms, index_by_id

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Catalog paths for A1/A2/A6 are command-center/phase3/A{n}/DESIGN.json.
# A concurrent ARC-0065 stub writer clobbers those files, so this unit
# extracts from snapshots produced by those units' own emit_design.py.
DESIGN_REL = {
    f"A{i}": f"command-center/phase3/A{i}/DESIGN.json" for i in range(1, 10)
}
DESIGN_REL.update(
    {
        "A1": "command-center/p2-wave/probes/ARC-0074/dossiers/A1/DESIGN.json",
        "A2": "command-center/p2-wave/probes/ARC-0074/dossiers/A2/DESIGN.json",
        "A6": "command-center/p2-wave/probes/ARC-0074/dossiers/A6/DESIGN.json",
    }
)
RANKING_REL = "command-center/phase3/AGGREGATE-RANKING.json"
SINGULARITY_REL = "command-center/phase3/CONTROL-PLANE-SINGULARITY.json"
SIMILARITY_REL = "command-center/phase3/ARCH-SIMILARITY.json"
SCHEMA_REL = "command-center/schema/architecture-dossier.schema.json"
OUT_REL = "command-center/phase3/WINNING-ARCHITECTURE.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"

HYBRID_ID = "H-A1-A2-A6"
NEW_ID = f"{HYBRID_ID}:lineage-required"

# One chosen mechanism per control-plane slot. Ids must be extractable from
# the named live dossier. Alternatives are recorded even when rejected.
SLOTS: list[dict[str, Any]] = [
    {
        "slot": "capability-ssot",
        "choose": "A2:precedence.rule",
        "alternatives": ["A1:precedence.rule", "A6:precedence.rule"],
        "reason": (
            "A2 registry is the only SSOT; generated files are projections "
            "and never override a registry entry. A1's load-order replace is "
            "a static-tree SSOT without a tamper detector. A6 min_tier is a "
            "vendor floor, not a capability registry."
        ),
    },
    {
        "slot": "generated-lifecycle",
        "choose": "A2:hand_edit_rule",
        "alternatives": ["A1:precedence.no_generated_layer"],
        "reason": (
            "A2 classifies a hand-edit as TAMPERED vs STALE and restore is "
            "regenerate. A1's no_generated_layer cannot offer that lifecycle; "
            "keeping both would duplicate the generated-artifact plane."
        ),
    },
    {
        "slot": "generator-determinism",
        "choose": "A2:determinism_contract",
        "alternatives": [],
        "reason": (
            "A2 states generate(registry) as a pure function of registry bytes "
            "and generator_version. A1 and A6 have no generator."
        ),
    },
    {
        "slot": "overlay-replacement",
        "choose": "A1:precedence.merge",
        "alternatives": ["A2:precedence.merge", "A6:precedence.merge"],
        "reason": (
            "Non-registry overlays stay A1 whole-object replacement. A2 merge "
            "discards generated hand-edits (already taken as generated-lifecycle). "
            "A6 forbids merging vendor descriptors into a fake common vocabulary."
        ),
    },
    {
        "slot": "overlay-closed-ids",
        "choose": "A1:precedence.new_id_in_overlay",
        "alternatives": ["A2:precedence.unlisted_generated_file"],
        "reason": (
            "A1 overlays may retarget an existing id and must not introduce a "
            "new one. That is the rollback-safe overlay gate beside A2 SSOT."
        ),
    },
    {
        "slot": "vendor-negotiation",
        "choose": "A6:downgrade_refusal",
        "alternatives": ["A1:class", "A2:class"],
        "reason": (
            "A6 is the only live dossier with capability negotiation and "
            "DOWNGRADE-REFUSED. A1/A2 do not address vendors; using either as "
            "a silent adapter would be the interchangeability lie A6 refutes."
        ),
    },
    {
        "slot": "vendor-tier-map",
        "choose": "A6:tier_map",
        "alternatives": ["A6:capability_tiers"],
        "reason": (
            "Exactly-one-tier assignment of catalog work-unit fields exists "
            "only on A6. capability_tiers is the related capability map; the "
            "slot takes the contract-field partition so the plane stays singular."
        ),
    },
    {
        "slot": "constraint-a1-inexpressible",
        "choose": "A1:expressibility.first_non_expressible_construct",
        "alternatives": [],
        "reason": (
            "Keep A1's first inexpressible (runtime stopping predicate) as a "
            "hard stop. Dropping it would overclaim that the fusion is more "
            "expressive than A1 on that construct."
        ),
    },
    {
        "slot": "constraint-a2-inexpressible",
        "choose": "A2:expressibility.first_non_expressible_construct",
        "alternatives": [],
        "reason": (
            "Keep A2's first inexpressible (opaque passthrough) as a hard stop. "
            "A hybrid must not reintroduce the escape hatch A2 forbids."
        ),
    },
    {
        "slot": "constraint-a6-inexpressible",
        "choose": "A6:expressibility.first_non_expressible_construct",
        "alternatives": [],
        "reason": (
            "Keep A6's first inexpressible (GUARANTEED-identical tool_permissions "
            "vocabulary). Vendors stay non-interchangeable in the fusion."
        ),
    },
]

NEW_MECHANISM = {
    "id": NEW_ID,
    "kind": "new",
    "architecture_id": HYBRID_ID,
    "source_architecture": "NEW",
    "source_section": (
        "command-center/WORK-UNIT-CATALOG.json "
        "work_units[id=ARC-0074].evidence_requirement"
    ),
    "source_path": CATALOG_REL,
    "source_unit": "ARC-0074",
    "statement": (
        "Every borrowed mechanism records source architecture, source section, "
        "reason chosen over alternatives, and a rollback target; the fusion "
        "must decompose into per-source sets that match the source dossiers."
    ),
    "justification": (
        "No live A1/A2/A6 dossier encodes a fusion operator with per-mechanism "
        "lineage and a decomposition round-trip. Reconstructing A9 (maximal "
        "hybrid) from catalog titles without A9/DESIGN.json would be an ADV "
        "rebuild circle. The operator is therefore NEW, justified from the "
        "ARC-0074 evidence_requirement, with rollback = drop the fusion and "
        "revert to a single source dossier."
    ),
    "reason_chosen": (
        "Without lineage a hybrid cannot name an owner or a rollback target "
        "per mechanism."
    ),
    "alternatives_considered": [
        {
            "id": "A9:maximal-hybrid",
            "rejected_because": (
                "command-center/phase3/A9/DESIGN.json is absent; inventing A9 "
                "mechanisms from catalog prose is not a source-dossier match."
            ),
        }
    ],
    "rollback_target": "drop fusion; use one of A1/A2/A6 DESIGN.json unchanged",
    "slot": "fusion-lineage-operator",
}

BORROWED_REQUIRED = (
    "source_architecture",
    "source_section",
    "reason_chosen",
    "rollback_target",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def input_presence() -> dict[str, Any]:
    designs = {}
    for arch, rel in DESIGN_REL.items():
        designs[arch] = {"path": rel, "present": present(rel)}
    return {
        "aggregate_ranking": {"path": RANKING_REL, "present": present(RANKING_REL)},
        "control_plane_singularity": {
            "path": SINGULARITY_REL,
            "present": present(SINGULARITY_REL),
        },
        "arch_similarity": {"path": SIMILARITY_REL, "present": present(SIMILARITY_REL)},
        "designs": designs,
    }


def load_live_dossiers() -> dict[str, dict[str, Any]]:
    """architecture_id -> {path, doc, mechanisms}."""
    out: dict[str, dict[str, Any]] = {}
    for arch, rel in DESIGN_REL.items():
        path = REPO / rel
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        try:
            doc = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        if str(doc.get("architecture_id") or "") != arch:
            # Still accept if architecture_id matches the folder.
            if str(doc.get("architecture_id") or "") not in {arch, ""}:
                continue
        mechs = extract_mechanisms(doc, rel)
        out[arch] = {"path": rel, "doc": doc, "mechanisms": mechs}
    return out


def borrow(
    extracted: dict[str, Any],
    *,
    slot: str,
    reason: str,
    alternatives: list[dict[str, Any]],
) -> dict[str, Any]:
    arch = str(extracted.get("architecture_id") or "")
    return {
        "id": extracted["id"],
        "kind": "borrowed",
        "architecture_id": arch,
        "source_architecture": arch,
        "source_section": extracted["section"],
        "source_path": extracted["source_path"],
        "source_unit": extracted.get("source_unit") or "",
        "statement": extracted["statement"],
        "justification": "",
        "reason_chosen": reason,
        "alternatives_considered": alternatives,
        "rollback_target": extracted["source_path"],
        "slot": slot,
    }


def _alt_row(mid: str, by_id: dict[str, dict[str, Any]], reason: str) -> dict[str, Any]:
    hit = by_id.get(mid)
    if hit:
        return {
            "id": mid,
            "present_in_source": True,
            "statement": hit["statement"],
            "rejected_because": reason,
        }
    return {
        "id": mid,
        "present_in_source": False,
        "statement": "",
        "rejected_because": reason + " (id not extracted from a live dossier)",
    }


def compose_from_slots(
    live: dict[str, dict[str, Any]], slots: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for pack in live.values():
        by_id.update(index_by_id(pack["mechanisms"]))
    fusion: list[dict[str, Any]] = []
    used_slots: set[str] = set()
    for spec in slots:
        slot = spec["slot"]
        if slot in used_slots:
            raise ValueError(f"duplicate slot {slot}")
        used_slots.add(slot)
        chosen = spec["choose"]
        extracted = by_id.get(chosen)
        if extracted is None:
            raise KeyError(f"chosen mechanism not in live extracts: {chosen}")
        alts = [
            _alt_row(mid, by_id, spec["reason"]) for mid in spec.get("alternatives") or []
        ]
        fusion.append(
            borrow(
                extracted,
                slot=slot,
                reason=spec["reason"],
                alternatives=alts,
            )
        )
    fusion.append(dict(NEW_MECHANISM))
    ids = [row["id"] for row in fusion]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate mechanism id in fusion: {ids}")
    return fusion


def lineage_check(
    fusion: list[dict[str, Any]],
    source_rows_by_arch: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    src_ids = {
        arch: {m["id"] for m in rows if m.get("id")}
        for arch, rows in source_rows_by_arch.items()
    }
    orphans: list[dict[str, Any]] = []
    unjustified_new: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    borrowed = 0
    new = 0
    for row in fusion:
        kind = str(row.get("kind") or "borrowed")
        mid = str(row.get("id") or "")
        if kind == "new":
            new += 1
            just = str(row.get("justification") or "").strip()
            if len(just) < 8:
                unjustified_new.append({"id": mid, "reason": "new-without-justification"})
            continue
        borrowed += 1
        missing = [k for k in BORROWED_REQUIRED if not str(row.get(k) or "").strip()]
        if missing:
            incomplete.append({"id": mid, "missing": missing})
        arch = str(row.get("source_architecture") or "")
        if mid not in src_ids.get(arch, set()):
            orphans.append(
                {
                    "id": mid,
                    "source_architecture": arch,
                    "reason": "unmatched-in-source-extract",
                }
            )
    ok = not orphans and not unjustified_new and not incomplete
    return {
        "ok": ok,
        "borrowed": borrowed,
        "new": new,
        "orphan_count": len(orphans),
        "orphans": orphans,
        "unjustified_new": unjustified_new,
        "incomplete": incomplete,
    }


def decompose(fusion: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for row in fusion:
        kind = str(row.get("kind") or "borrowed")
        arch = "NEW" if kind == "new" else str(row.get("source_architecture") or "")
        if not arch:
            arch = "UNKNOWN"
        buckets.setdefault(arch, [])
        mid = str(row.get("id") or "")
        if mid and mid not in buckets[arch]:
            buckets[arch].append(mid)
    for arch in buckets:
        buckets[arch] = sorted(buckets[arch])
    return dict(sorted(buckets.items()))


def recompose(decomposed: dict[str, list[str]]) -> set[str]:
    ids: set[str] = set()
    for arch_ids in decomposed.values():
        ids.update(str(x) for x in arch_ids)
    return ids


def roundtrip(fusion: list[dict[str, Any]]) -> dict[str, Any]:
    original = {str(r["id"]) for r in fusion if r.get("id")}
    decomposed = decompose(fusion)
    recomposed = recompose(decomposed)
    return {
        "ok": original == recomposed,
        "original": sorted(original),
        "recomposed": sorted(recomposed),
        "missing_on_recompose": sorted(original - recomposed),
        "extra_on_recompose": sorted(recomposed - original),
        "decomposed": decomposed,
    }


def match_decomposed_to_sources(
    decomposed: dict[str, list[str]],
    source_rows_by_arch: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    unmatched: list[dict[str, Any]] = []
    src_ids = {
        arch: {m["id"] for m in rows if m.get("id")}
        for arch, rows in source_rows_by_arch.items()
    }
    for arch, ids in decomposed.items():
        if arch == "NEW":
            continue
        have = src_ids.get(arch, set())
        for mid in ids:
            if mid not in have:
                unmatched.append({"id": mid, "architecture": arch})
    return unmatched


def source_rows_from_live(live: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {arch: pack["mechanisms"] for arch, pack in live.items()}


FIXTURE_SA_REL = "command-center/p2-wave/probes/ARC-0074/fixtures/SA.json"
FIXTURE_SB_REL = "command-center/p2-wave/probes/ARC-0074/fixtures/SB.json"


def load_fixture_sources() -> dict[str, list[dict[str, Any]]]:
    sa = load_json(REPO / FIXTURE_SA_REL)
    sb = load_json(REPO / FIXTURE_SB_REL)
    return {
        "SA": extract_mechanisms(sa, FIXTURE_SA_REL),
        "SB": extract_mechanisms(sb, FIXTURE_SB_REL),
    }


def fixture_fusion_good() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    sources = load_fixture_sources()
    by_id: dict[str, dict[str, Any]] = {}
    for rows in sources.values():
        by_id.update(index_by_id(rows))
    specs = [
        (
            "generator-determinism",
            "SB:determinism_contract",
            "SB is the only fixture with a generator determinism contract.",
            ["SA:precedence.no_generated_layer"],
        ),
        (
            "overlay-replacement",
            "SA:precedence.merge",
            "SA whole-object overlay stays beside the SB registry SSOT.",
            ["SB:precedence.merge"],
        ),
        (
            "constraint-sa-stop",
            "SA:expressibility.first_non_expressible_construct",
            "Keep SA's first inexpressible as a hard stop.",
            [],
        ),
    ]
    fusion: list[dict[str, Any]] = []
    for slot, choose, reason, alts in specs:
        fusion.append(
            borrow(
                by_id[choose],
                slot=slot,
                reason=reason,
                alternatives=[_alt_row(a, by_id, reason) for a in alts],
            )
        )
    new = dict(NEW_MECHANISM)
    new["id"] = "H-SA-SB:lineage-required"
    fusion.append(new)
    return fusion, sources


def fixture_fusion_orphan() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    fusion, sources = fixture_fusion_good()
    fusion = list(fusion)
    fusion.append(
        {
            "id": "SA:ghost-not-extracted",
            "kind": "borrowed",
            "architecture_id": "SA",
            "source_architecture": "SA",
            "source_section": "ghost",
            "source_path": FIXTURE_SA_REL,
            "source_unit": "ARC-0074",
            "statement": "planted orphan mechanism absent from SA extract",
            "justification": "",
            "reason_chosen": "planted both-states bad row",
            "alternatives_considered": [],
            "rollback_target": FIXTURE_SA_REL,
            "slot": "planted-orphan",
        }
    )
    return fusion, sources


def fixture_fusion_unjustified_new() -> tuple[
    list[dict[str, Any]], dict[str, list[dict[str, Any]]]
]:
    fusion, sources = fixture_fusion_good()
    fusion = list(fusion)
    fusion.append(
        {
            "id": "H-SA-SB:unjustified",
            "kind": "new",
            "architecture_id": "H-SA-SB",
            "source_architecture": "NEW",
            "source_section": "none",
            "source_path": FIXTURE_SA_REL,
            "source_unit": "ARC-0074",
            "statement": "planted new mechanism with empty justification",
            "justification": "",
            "reason_chosen": "planted",
            "alternatives_considered": [],
            "rollback_target": FIXTURE_SA_REL,
            "slot": "planted-unjustified-new",
        }
    )
    return fusion, sources


def compose_live() -> dict[str, Any]:
    live = load_live_dossiers()
    fusion = compose_from_slots(live, SLOTS)
    sources = source_rows_from_live(live)
    lin = lineage_check(fusion, sources)
    rt = roundtrip(fusion)
    unmatched = match_decomposed_to_sources(rt["decomposed"], sources)
    return {
        "live_architectures": sorted(live),
        "fusion": fusion,
        "lineage": lin,
        "roundtrip": rt,
        "unmatched_after_decompose": unmatched,
        "ok": bool(lin["ok"] and rt["ok"] and not unmatched),
        "presence": input_presence(),
        "live": live,
    }
