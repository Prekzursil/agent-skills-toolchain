#!/usr/bin/env python3
"""Fixture world for WFA-0107.

Live WFA-0081 / WFA-0079 / WFA-0062 artifacts are absent on this worktree.
The reconstructed graphs encode the catalog-named rules those units would
supply: a symmetrised undirected compat relation (same wire bus), the three
mechanism mutex pairs named in WFA-0062, and a fail-closed licence matrix
(Proprietary mixed with anything else is forbidden; UNKNOWN never defaults
to permissive).
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

OPERATORS = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
)

LIVE_UPSTREAM = (
    "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json",
    "command-center/wfa/WFA-0062-mechanism-conflicts.json",
    "command-center/wfa/WFA-0079-provenance-license-graph-v2.json",
)

# WFA-0062 named mutex pairs. Fusion-attempt code duplicates these as a
# hard-coded set and must not import this tuple.
CONFLICT_PAIRS = (
    ("mech.blind-independent-first-pass", "mech.shared-context-deliberation"),
    ("mech.deterministic-replay", "mech.nondeterministic-sampling"),
    ("mech.fire-and-forget-dispatch", "mech.blocking-fan-in-barrier"),
)

LICENCE_UNIVERSE = (
    "MIT",
    "Apache-2.0",
    "GPL-3.0",
    "Proprietary",
    "UNKNOWN",
)

BLUEPRINTS: list[dict[str, Any]] = [
    {
        "id": "wf-review-a",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "MIT",
        "mechanisms": ["mech.deterministic-replay"],
        "stages": ["intake", "score", "emit"],
        "input_type": "Document",
        "output_type": "ScoreCard",
        "insertions": ["Document", "ScoreCard"],
        "benchmarks": {"intake": 0.91, "score": 0.72, "emit": 0.80},
        "predicates": ["input.lang == 'en'"],
        "default_branch": False,
        "cost": 1,
    },
    {
        "id": "wf-review-b",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "Apache-2.0",
        "mechanisms": ["mech.deterministic-replay"],
        "stages": ["intake", "score", "emit"],
        "input_type": "Document",
        "output_type": "ScoreCard",
        "insertions": ["Document", "ScoreCard"],
        "benchmarks": {"intake": 0.64, "score": 0.95, "emit": 0.71},
        "predicates": ["input.lang == 'fr'"],
        "default_branch": True,
        "cost": 4,
    },
    {
        "id": "wf-review-gpl",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "GPL-3.0",
        "mechanisms": ["mech.deterministic-replay"],
        "stages": ["intake", "score", "emit"],
        "input_type": "Document",
        "output_type": "ScoreCard",
        "insertions": ["Document", "ScoreCard"],
        "benchmarks": {"intake": 0.70, "score": 0.81, "emit": 0.77},
        "predicates": ["input.lang == 'de'"],
        "default_branch": False,
        "cost": 3,
    },
    {
        "id": "wf-review-sample",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "MIT",
        "mechanisms": ["mech.nondeterministic-sampling"],
        "stages": ["intake", "sample", "emit"],
        "input_type": "Document",
        "output_type": "ScoreCard",
        "insertions": ["Document", "ScoreCard"],
        "benchmarks": {"intake": 0.60, "sample": 0.88, "emit": 0.66},
        "predicates": ["input.mode == 'sample'"],
        "default_branch": False,
        "cost": 2,
    },
    {
        "id": "wf-review-prop",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "Proprietary",
        "mechanisms": ["mech.deterministic-replay"],
        "stages": ["intake", "score", "emit"],
        "input_type": "Document",
        "output_type": "ScoreCard",
        "insertions": ["Document", "ScoreCard"],
        "benchmarks": {"intake": 0.85, "score": 0.85, "emit": 0.85},
        "predicates": ["input.tenant == 'acme'"],
        "default_branch": False,
        "cost": 5,
    },
    {
        "id": "wf-review-unknown",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "UNKNOWN",
        "mechanisms": ["mech.deterministic-replay"],
        "stages": ["intake", "score", "emit"],
        "input_type": "Document",
        "output_type": "ScoreCard",
        "insertions": ["Document", "ScoreCard"],
        "benchmarks": {"intake": 0.50, "score": 0.50, "emit": 0.50},
        "predicates": ["input.lang == 'und'"],
        "default_branch": False,
        "cost": 2,
    },
    {
        "id": "wf-review-audio",
        "family": "review",
        "wire_bus": "review.v1",
        "licence": "MIT",
        "mechanisms": ["mech.deterministic-replay"],
        "stages": ["transcribe"],
        "input_type": "Audio",
        "output_type": "Transcript",
        "insertions": ["Audio"],
        "benchmarks": {"transcribe": 0.88},
        "predicates": ["input.kind == 'audio'"],
        "default_branch": True,
        "cost": 2,
    },
    {
        "id": "wf-council-blind",
        "family": "council",
        "wire_bus": "council.v1",
        "licence": "MIT",
        "mechanisms": ["mech.blind-independent-first-pass"],
        "stages": ["score", "tally"],
        "input_type": "Document",
        "output_type": "Verdict",
        "insertions": ["Document", "Verdict"],
        "benchmarks": {"score": 0.73, "tally": 0.90},
        "predicates": ["input.round == 1"],
        "default_branch": False,
        "cost": 1,
    },
    {
        "id": "wf-council-shared",
        "family": "council",
        "wire_bus": "council.v1",
        "licence": "MIT",
        "mechanisms": ["mech.shared-context-deliberation"],
        "stages": ["deliberate", "tally"],
        "input_type": "Document",
        "output_type": "Verdict",
        "insertions": ["Document", "Verdict"],
        "benchmarks": {"deliberate": 0.81, "tally": 0.90},
        "predicates": ["input.round >= 1"],
        "default_branch": True,
        "cost": 3,
    },
    {
        "id": "wf-dispatch-ff",
        "family": "dispatch",
        "wire_bus": "dispatch.v1",
        "licence": "MIT",
        "mechanisms": ["mech.fire-and-forget-dispatch"],
        "stages": ["launch"],
        "input_type": "Job",
        "output_type": "Ack",
        "insertions": ["Job"],
        "benchmarks": {"launch": 0.99},
        "predicates": ["input.async == true"],
        "default_branch": False,
        "cost": 1,
    },
    {
        "id": "wf-dispatch-barrier",
        "family": "dispatch",
        "wire_bus": "dispatch.v1",
        "licence": "MIT",
        "mechanisms": ["mech.blocking-fan-in-barrier"],
        "stages": ["join"],
        "input_type": "Job",
        "output_type": "Ack",
        "insertions": ["Job", "Ack"],
        "benchmarks": {"join": 0.92},
        "predicates": ["input.async == false"],
        "default_branch": True,
        "cost": 2,
    },
]


def edge_key(kind: str, left: str, right: str) -> str:
    a, b = sorted((left, right))
    return f"{kind}:{a}|{b}"


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def licence_cell(a: str, b: str) -> dict[str, str]:
    """Checker-side matrix. Fusion-attempt uses a separate lattice in fusion.py."""
    left, right = sorted((a, b))
    if a == "UNKNOWN" or b == "UNKNOWN":
        verdict = "FORBID"
        note = "UNKNOWN is fail-closed; never defaulted to permissive"
    elif (a == "Proprietary") ^ (b == "Proprietary"):
        verdict = "FORBID"
        note = "Proprietary mixed with a non-Proprietary licence is forbidden at fusion"
    else:
        verdict = "ALLOW"
        if "GPL-3.0" in (a, b) and a != b:
            note = "copyleft+permissive allowed; result carries GPL-3.0"
        else:
            note = "compatible"
    return {
        "left": left,
        "right": right,
        "verdict": verdict,
        "note": note,
        "edge": edge_key("licence", a, b),
    }


def materialize() -> dict[str, Any]:
    bps = [json.loads(json.dumps(b, sort_keys=True)) for b in BLUEPRINTS]
    ids = [b["id"] for b in bps]
    by_id = {b["id"]: b for b in bps}
    compat = []
    for x, y in combinations(ids, 2):
        if by_id[x]["wire_bus"] == by_id[y]["wire_bus"]:
            a, b = sorted((x, y))
            compat.append(
                {
                    "source": a,
                    "target": b,
                    "undirected": True,
                    "edge": edge_key("compat", a, b),
                    "wire_bus": by_id[x]["wire_bus"],
                }
            )
    conflicts = []
    for m1, m2 in CONFLICT_PAIRS:
        a, b = sorted((m1, m2))
        conflicts.append(
            {
                "left": a,
                "right": b,
                "grade": "HARD",
                "edge": edge_key("mechanism-conflict", a, b),
                "argument": (
                    f"{a} and {b} are mutually exclusive canonical mechanisms "
                    "(WFA-0062 named pair); co-locating them in one fused "
                    "workflow is a contradiction."
                ),
            }
        )
    matrix = []
    for a, b in combinations(LICENCE_UNIVERSE, 2):
        matrix.append(licence_cell(a, b))
    for lic in LICENCE_UNIVERSE:
        matrix.append(licence_cell(lic, lic))
    matrix.sort(key=lambda c: (c["left"], c["right"]))
    return {
        "blueprints": bps,
        "compat_relation": {
            "kind": "symmetrised-undirected-compat",
            "source": "reconstructed-fixture",
            "rule": "undirected edge iff both endpoints share wire_bus",
            "asymmetric": 0,
            "edges": sorted(compat, key=lambda e: (e["source"], e["target"])),
        },
        "mechanism_conflicts": {
            "kind": "hard-mutex",
            "source": "reconstructed-fixture",
            "named_in": "WFA-0062 question_or_target",
            "edges": sorted(conflicts, key=lambda e: (e["left"], e["right"])),
        },
        "licence_matrix": {
            "kind": "fusion-licence-compatibility",
            "source": "reconstructed-fixture",
            "fail_closed_unknown": True,
            "cells": matrix,
        },
        "operators": list(OPERATORS),
    }


def write_fixtures() -> dict[str, Any]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    data = materialize()
    (FIXTURES / "blueprints.json").write_text(
        dump({"source": "reconstructed-fixture", "blueprints": data["blueprints"]}),
        encoding="utf-8",
    )
    (FIXTURES / "compat_relation.json").write_text(
        dump(data["compat_relation"]), encoding="utf-8"
    )
    (FIXTURES / "mechanism_conflicts.json").write_text(
        dump(data["mechanism_conflicts"]), encoding="utf-8"
    )
    (FIXTURES / "licence_matrix.json").write_text(
        dump(data["licence_matrix"]), encoding="utf-8"
    )
    return data


def live_upstream_status() -> list[dict[str, Any]]:
    rows = []
    for rel in LIVE_UPSTREAM:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file() and path.stat().st_size > 0,
            }
        )
    return rows


class World:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        if data is None:
            data = {
                "blueprints": json.loads(
                    (FIXTURES / "blueprints.json").read_text(encoding="utf-8")
                )["blueprints"],
                "compat_relation": json.loads(
                    (FIXTURES / "compat_relation.json").read_text(encoding="utf-8")
                ),
                "mechanism_conflicts": json.loads(
                    (FIXTURES / "mechanism_conflicts.json").read_text(encoding="utf-8")
                ),
                "licence_matrix": json.loads(
                    (FIXTURES / "licence_matrix.json").read_text(encoding="utf-8")
                ),
                "operators": list(OPERATORS),
            }
        self.blueprints = {b["id"]: b for b in data["blueprints"]}
        self.operators = list(data.get("operators") or OPERATORS)
        self.compat = {
            frozenset((e["source"], e["target"]))
            for e in data["compat_relation"]["edges"]
        }
        self.conflicts = {
            frozenset((e["left"], e["right"]))
            for e in data["mechanism_conflicts"]["edges"]
        }
        self.licence = {}
        for cell in data["licence_matrix"]["cells"]:
            self.licence[frozenset((cell["left"], cell["right"]))] = cell
        self.upstream = live_upstream_status()
        self.fixture_source = "reconstructed-fixture"

    def has_compat(self, a: str, b: str) -> bool:
        if a == b:
            return False
        return frozenset((a, b)) in self.compat

    def conflict_edge(self, mechs_a: list[str], mechs_b: list[str]) -> str | None:
        for ma in mechs_a:
            for mb in mechs_b:
                key = frozenset((ma, mb))
                if len(key) == 2 and key in self.conflicts:
                    x, y = sorted((ma, mb))
                    return edge_key("mechanism-conflict", x, y)
        return None

    def licence_cell(self, la: str, lb: str) -> dict[str, str]:
        cell = self.licence.get(frozenset((la, lb)))
        if cell is None:
            return {
                "verdict": "FORBID",
                "edge": edge_key("licence", la, lb),
                "note": "pair absent from matrix; fail-closed",
                "left": min(la, lb),
                "right": max(la, lb),
            }
        return cell

    def pairs(self) -> list[tuple[str, str]]:
        ids = sorted(self.blueprints)
        return [(a, b) for a, b in combinations(ids, 2)]


def load_world(*, refresh: bool = False) -> World:
    if refresh or not (FIXTURES / "compat_relation.json").is_file():
        data = write_fixtures()
        return World(data)
    return World()
