"""Catalog-reconstructed 7-rule seed: 45-row risk register and 30 merge_units.

The live 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json (documented 344,197 B)
and 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json (documented 161,920 B) are not
on this Linux worktree. Histogram counts come from WORK-UNIT-CATALOG.json
WFA-0033 (26 THIRD-PARTY, 11 OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY,
2 ATTRIBUTION-REQUIRED, 1 RIDER-RESTRICTED, 1 UNCLASSIFIED). Four extra rows
bring the register to the contracted 45. Merge units use the documented field
names (sources_declared, sources_unresolved, sources_resolved_in_registry).
"""
from __future__ import annotations

from typing import Any

from lattice import RULES

THIRD_PARTY_SPDX = (
    ["MIT"] * 8
    + ["Apache-2.0"] * 4
    + ["BSD-3-Clause"] * 3
    + ["GPL-3.0-only"] * 3
    + ["MPL-2.0"] * 2
    + ["AGPL-3.0-only"] * 2
    + ["CC0-1.0", "LGPL-3.0-only", "ISC", "ALL-RIGHTS-RESERVED"]
)

OWNER_DEPS = [
    ["LR-01"],
    ["LR-16"],
    ["LR-21"],
    ["LR-19"],
    ["LR-09"],
    ["LR-26"],
    ["LR-01", "LR-16"],
    ["LR-23"],
    ["LR-24"],
    ["LR-13"],
    ["LR-18", "LR-09"],
]


def _row(
    idx: int,
    *,
    origin: str,
    spdx: str,
    name: str,
    rider: str | None = None,
    attribution: bool = False,
    credits: list[dict[str, Any]] | None = None,
    deps: list[str] | None = None,
    unresolved: bool = False,
) -> dict[str, Any]:
    rid = f"LR-{idx:02d}"
    return {
        "id": rid,
        "name": name,
        "origin_class": origin,
        "spdx": spdx,
        "rider": rider,
        "attribution_required": attribution,
        "credits": list(credits or []),
        "external_deps": list(deps or []),
        "unresolved_license": unresolved,
    }


def risk_register() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    assert len(THIRD_PARTY_SPDX) == 26
    for i, spdx in enumerate(THIRD_PARTY_SPDX, start=1):
        rows.append(
            _row(
                i,
                origin="THIRD-PARTY",
                spdx=spdx,
                name=f"third-party-{i:02d}-{spdx.lower().replace('.', '-')}",
            )
        )
    assert len(OWNER_DEPS) == 11
    for j, deps in enumerate(OWNER_DEPS):
        idx = 27 + j
        rows.append(
            _row(
                idx,
                origin="OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY",
                spdx="OWNER",
                name=f"owner-with-deps-{idx:02d}",
                deps=deps,
            )
        )
    rows.append(
        _row(
            38,
            origin="ATTRIBUTION-REQUIRED",
            spdx="CC-BY-4.0",
            name="attribution-alice",
            attribution=True,
            credits=[
                {
                    "id": "credit-LR-38",
                    "holder": "Alice Example",
                    "notice": "Copyright Alice Example. CC-BY-4.0 attribution required.",
                    "source_id": "LR-38",
                }
            ],
        )
    )
    rows.append(
        _row(
            39,
            origin="ATTRIBUTION-REQUIRED",
            spdx="CC-BY-4.0",
            name="attribution-bob",
            attribution=True,
            credits=[
                {
                    "id": "credit-LR-39",
                    "holder": "Bob Example",
                    "notice": "Copyright Bob Example. CC-BY-4.0 attribution required.",
                    "source_id": "LR-39",
                }
            ],
        )
    )
    rows.append(
        _row(
            40,
            origin="RIDER-RESTRICTED",
            spdx="MIT",
            name="rider-no-eval-folding",
            rider="no-eval-folding / no-ML-training",
        )
    )
    rows.append(
        _row(
            41,
            origin="UNCLASSIFIED",
            spdx="",
            name="unclassified-missing-license",
            unresolved=True,
        )
    )
    rows.append(
        _row(
            42,
            origin="OWNER-AUTHORED",
            spdx="OWNER",
            name="owner-first-party-alpha",
        )
    )
    rows.append(
        _row(
            43,
            origin="OWNER-AUTHORED",
            spdx="OWNER",
            name="owner-first-party-beta",
        )
    )
    rows.append(
        _row(
            44,
            origin="SEED-EXTENSION",
            spdx="CC-BY-SA-4.0",
            name="sharealike-carol",
            attribution=True,
            credits=[
                {
                    "id": "credit-LR-44",
                    "holder": "Carol Example",
                    "notice": "Copyright Carol Example. CC-BY-SA-4.0 share-alike attribution required.",
                    "source_id": "LR-44",
                }
            ],
        )
    )
    rows.append(
        _row(
            45,
            origin="SEED-EXTENSION",
            spdx="GPL-2.0-only",
            name="third-party-gpl2",
        )
    )
    if len(rows) != 45:
        raise RuntimeError(f"risk register length {len(rows)} != 45")
    return rows


def register_by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in risk_register()}


def histogram(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        origin = str(row["origin_class"])
        counts[origin] = counts.get(origin, 0) + 1
    return counts


def _mu(
    n: int,
    sources: list[str],
    *,
    unresolved: list[str] | None = None,
    carried_credits: list[dict[str, Any]] | object = ...,
) -> dict[str, Any]:
    unresolved = list(unresolved or [])
    unit: dict[str, Any] = {
        "id": f"MU-{n:02d}",
        "sources_declared": list(sources),
        "sources_unresolved": unresolved,
        "sources_resolved_in_registry": [
            s for s in sources if s not in unresolved and s.startswith("LR-")
        ],
    }
    if carried_credits is not ...:
        unit["carried_credits"] = carried_credits
    return unit


def merge_units() -> list[dict[str, Any]]:
    units = [
        _mu(1, ["LR-01", "LR-02"]),
        _mu(2, ["LR-01", "LR-09"]),
        _mu(3, ["LR-01", "LR-16"]),  # copyleft + permissive
        _mu(4, ["LR-09", "LR-21"]),
        _mu(5, ["LR-01", "LR-19"]),
        _mu(6, ["LR-16", "LR-26"]),  # GPL + proprietary
        _mu(7, ["LR-21", "LR-26"]),
        _mu(8, ["LR-01", "LR-40"]),  # rider
        _mu(9, ["LR-01", "LR-41"]),  # unknown
        _mu(10, ["LR-16", "LR-41"]),
        _mu(11, ["LR-01", "LR-38"]),  # credits carried
        _mu(12, ["LR-38", "LR-16"]),
        _mu(13, ["LR-28", "LR-01"]),  # owner inherits GPL
        _mu(14, ["LR-27", "LR-31"]),
        _mu(15, ["LR-01", "LR-09", "LR-13"]),
        _mu(16, ["LR-38", "LR-44"]),
        _mu(17, ["LR-19", "LR-16"]),
        _mu(18, ["LR-24", "LR-01"]),
        _mu(19, ["LR-23", "LR-16"]),
        _mu(20, ["LR-01", "LR-16", "LR-21"]),
        _mu(21, ["LR-01", "LR-99"], unresolved=["LR-99"]),
        _mu(22, ["LR-01", "LR-38"], carried_credits=[]),  # credit drop
        _mu(23, ["LR-40", "LR-16"]),
        _mu(24, ["LR-42", "LR-43"]),
        _mu(25, ["LR-38", "LR-01", "LR-09"]),
        _mu(26, ["LR-26", "LR-32"]),
        _mu(27, ["LR-19", "LR-09"]),
        _mu(28, ["LR-21", "LR-01", "LR-38"]),
        _mu(29, ["LR-21", "LR-01", "LR-38"], carried_credits=[]),
        _mu(30, ["LR-13", "LR-25", "LR-01"]),
    ]
    if len(units) != 30:
        raise RuntimeError(f"merge_units length {len(units)} != 30")
    return units


def classification_rules() -> list[dict[str, Any]]:
    if len(RULES) != 7:
        raise RuntimeError(f"rules length {len(RULES)} != 7")
    return list(RULES)
