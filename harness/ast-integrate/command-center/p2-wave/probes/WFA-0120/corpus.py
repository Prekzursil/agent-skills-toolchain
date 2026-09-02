#!/usr/bin/env python3
"""Pinned WFA-0120 control corpus.

The Windows harness-restore 09-WORKFLOW-BLUEPRINT-LIBRARY.json (108 records,
by_route BUILD-NEW n=26, by_state NEW n=32) is not on this Linux worktree.
This corpus reconstructs those *cardinalities* as a gate-control fixture:
26 BUILD-NEW + 6 other-route NEW = 32 NEW, plus a registry of incumbents
the gate must consult. It does not claim recovery of the original 108/284.
Counts are len() over constructed lists.
"""
from __future__ import annotations

from typing import Any

from gate import VOCAB

M = {
    "blind": "mech.blind-independent-first-pass",
    "shared": "mech.shared-context-deliberation",
    "replay": "mech.deterministic-replay",
    "sample": "mech.nondeterministic-sampling",
    "ff": "mech.fire-and-forget-dispatch",
    "fanin": "mech.blocking-fan-in-barrier",
    "cite": "mech.citation-grounding",
    "contra": "mech.contradiction-hunt",
    "lic": "mech.licence-verify",
    "prior": "mech.prior-art-search",
    "scan": "mech.static-scan",
    "bench": "mech.benchmark-harness",
    "human": "mech.human-checkpoint",
    "prov": "mech.provenance-carry",
    "fusion": "mech.fusion-collapse",
    "schema": "mech.schema-validate",
    "inject": "mech.injection-neutralise",
    "bucket": "mech.token-bucket",
    "lattice": "mech.lattice-surgery-schedule",
    "qec": "mech.quantum-error-surface",
    "zk": "mech.zk-circuit-arithmetization",
    "hom": "mech.homomorphic-eval-schedule",
    "sat": "mech.incremental-sat-cone",
    "diffgeo": "mech.discrete-diffgeo-remesh",
    "crdt": "mech.crdt-frontier",
}


def _cand(
    cid: str,
    mechs: list[str],
    *,
    tier: str,
    sources: int,
    quality: int,
    self_described: list[str] | None = None,
) -> dict[str, Any]:
    ms = sorted(mechs)
    return {
        "id": cid,
        "kind": "candidate",
        "mechanisms_from_definition": ms,
        "mechanisms_self_described": sorted(self_described or ms),
        "evidence_tier": tier,
        "independent_source_count": sources,
        "quality": quality,
        "disposition": "ADOPT",
    }


def _bp(
    bid: str,
    mechs: list[str],
    *,
    route: str,
    state: str,
    tier: str,
    sources: int,
    quality: int,
    title: str,
    self_described: list[str] | None = None,
) -> dict[str, Any]:
    ms = sorted(mechs)
    return {
        "id": bid,
        "kind": "blueprint",
        "route": route,
        "state": state,
        "title": title,
        "mechanisms_from_definition": ms,
        "mechanisms_self_described": sorted(self_described or ms),
        "evidence_tier": tier,
        "independent_source_count": sources,
        "quality": quality,
        "discovery_only": True,
    }


def registry() -> list[dict[str, Any]]:
    return [
        _cand("cand.lit-review", [M["cite"], M["contra"], M["prior"]], tier="E1", sources=3, quality=90),
        _cand("cand.council", [M["shared"], M["fanin"]], tier="E1", sources=2, quality=88),
        _cand("cand.scout", [M["scan"], M["lic"], M["prov"]], tier="E2", sources=2, quality=80),
        _cand("cand.fusion", [M["fusion"], M["schema"]], tier="E2", sources=2, quality=75),
        _cand("cand.injection", [M["inject"], M["schema"]], tier="E1", sources=2, quality=85),
        _cand("cand.replay", [M["replay"], M["prov"]], tier="E1", sources=2, quality=82),
        _cand("cand.sampling", [M["sample"], M["human"]], tier="E3", sources=1, quality=60),
        _cand("cand.dispatch", [M["ff"], M["bucket"]], tier="E2", sources=1, quality=70),
        _cand("cand.bench", [M["bench"], M["schema"]], tier="E1", sources=2, quality=84),
        _cand("cand.blind", [M["blind"], M["cite"]], tier="E1", sources=2, quality=86),
        _cand(
            "cand.full-research",
            [M["cite"], M["contra"], M["prior"], M["scan"], M["lic"]],
            tier="E1",
            sources=4,
            quality=95,
        ),
        _cand("cand.compose-pipe", [M["fusion"], M["schema"], M["bench"]], tier="E2", sources=2, quality=78),
    ]


def _rebuilds() -> list[dict[str, Any]]:
    """18 BUILD-NEW items that a covering incumbent should block."""
    weak = dict(tier="E4", sources=0, quality=0, state="NEW", route="BUILD-NEW")
    return [
        _bp("bp.build-new-01", [M["cite"], M["contra"], M["prior"]], title="rebuild lit-review exact", **weak),
        _bp("bp.build-new-02", [M["cite"], M["contra"]], title="rebuild lit-review subset", **weak),
        _bp("bp.build-new-03", [M["cite"]], title="rebuild citation-only subset", **weak),
        _bp("bp.build-new-04", [M["shared"], M["fanin"]], title="rebuild council exact", **weak),
        _bp("bp.build-new-05", [M["shared"]], title="rebuild council subset", **weak),
        _bp("bp.build-new-06", [M["scan"], M["lic"], M["prov"]], title="rebuild scout exact", **weak),
        _bp("bp.build-new-07", [M["scan"], M["lic"]], title="rebuild scout subset", **weak),
        _bp("bp.build-new-08", [M["fusion"], M["schema"]], title="rebuild fusion exact", **weak),
        _bp("bp.build-new-09", [M["inject"], M["schema"]], title="rebuild injection exact", **weak),
        _bp("bp.build-new-10", [M["replay"], M["prov"]], title="rebuild replay exact", **weak),
        _bp("bp.build-new-11", [M["sample"], M["human"]], title="rebuild sampling exact", **weak),
        _bp("bp.build-new-12", [M["ff"], M["bucket"]], title="rebuild dispatch exact", **weak),
        _bp("bp.build-new-13", [M["bench"], M["schema"]], title="rebuild bench exact", **weak),
        _bp("bp.build-new-14", [M["blind"], M["cite"]], title="rebuild blind exact", **weak),
        _bp("bp.build-new-15", [M["fusion"]], title="rebuild fusion subset", **weak),
        _bp("bp.build-new-16", [M["inject"]], title="rebuild injection subset", **weak),
        _bp("bp.build-new-17", [M["cite"], M["scan"]], title="rebuild full-research subset", **weak),
        _bp("bp.build-new-18", [M["fusion"], M["schema"], M["bench"]], title="rebuild compose-pipe exact", **weak),
    ]


def _legitimate() -> list[dict[str, Any]]:
    """8 BUILD-NEW items the gate must allow (novel or strictly better evidence)."""
    novel = dict(tier="E4", sources=0, quality=0, state="NEW", route="BUILD-NEW")
    return [
        _bp("bp.build-new-19", [M["lattice"], M["qec"]], title="novel lattice+qec", **novel),
        _bp("bp.build-new-20", [M["zk"]], title="novel zk arithmetization", **novel),
        _bp("bp.build-new-21", [M["hom"]], title="novel homomorphic schedule", **novel),
        _bp("bp.build-new-22", [M["sat"]], title="novel incremental SAT cone", **novel),
        _bp("bp.build-new-23", [M["diffgeo"]], title="novel discrete remesh", **novel),
        _bp("bp.build-new-24", [M["lattice"], M["zk"]], title="novel lattice+zk", **novel),
        _bp(
            "bp.build-new-25",
            [M["cite"], M["contra"], M["prior"]],
            title="supersede lit-review with stronger evidence",
            route="BUILD-NEW",
            state="NEW",
            tier="E1",
            sources=5,
            quality=99,
        ),
        _bp("bp.build-new-26", [M["crdt"]], title="novel crdt frontier", **novel),
    ]


def _other_new() -> list[dict[str, Any]]:
    """6 NEW blueprints that are not BUILD-NEW — gate must SKIP them."""
    return [
        _bp("bp.new-adapt", [M["shared"], M["fanin"]], title="adapt council", route="ADAPT", state="NEW", tier="E3", sources=1, quality=40),
        _bp("bp.new-merge", [M["fusion"], M["schema"]], title="merge fusion", route="MERGE", state="NEW", tier="E3", sources=1, quality=40),
        _bp("bp.new-compose", [M["fusion"], M["bench"]], title="compose pipe", route="COMPOSE", state="NEW", tier="E3", sources=1, quality=40),
        _bp("bp.new-adopt", [M["cite"], M["contra"], M["prior"]], title="adopt lit-review", route="ADOPT", state="NEW", tier="E1", sources=3, quality=90),
        _bp("bp.new-translate", [M["replay"], M["prov"]], title="translate replay", route="TRANSLATE", state="NEW", tier="E3", sources=1, quality=40),
        _bp("bp.new-certify", [M["bench"], M["schema"]], title="certify bench", route="CERTIFY", state="NEW", tier="E3", sources=1, quality=40),
    ]


def blueprints() -> list[dict[str, Any]]:
    rows = _rebuilds() + _legitimate() + _other_new()
    return rows


def build() -> dict[str, Any]:
    bps = blueprints()
    reg = registry()
    build_new = [b for b in bps if b["route"] == "BUILD-NEW"]
    new_state = [b for b in bps if b["state"] == "NEW"]
    used = {m for row in reg + bps for m in row["mechanisms_from_definition"]}
    return {
        "corpus_id": "wfa-0120-control-corpus-v1",
        "origin": (
            "Pinned control corpus. Original 09-WORKFLOW-BLUEPRINT-LIBRARY.json "
            "and 08-WORKFLOW-CANDIDATE-REGISTRY.json are absent on this Linux "
            "worktree. Cardinalities match the catalog claim (BUILD-NEW n=26, "
            "NEW n=32) so the gate is exercised at that scale; records are "
            "not claimed to be the original 108/284."
        ),
        "original_library_present": False,
        "vocabulary": sorted(VOCAB),
        "vocabulary_used": sorted(used),
        "registry": reg,
        "blueprints": bps,
        "census": {
            "n_registry": len(reg),
            "n_blueprints": len(bps),
            "n_build_new": len(build_new),
            "n_new": len(new_state),
            "n_other_new": len(new_state) - len(build_new),
        },
    }
