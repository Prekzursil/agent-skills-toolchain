#!/usr/bin/env python3
"""Construct recorded-run researcher assignments from harvested findings.

Dedicated landscape-vs-targeted fan-out transcripts are absent. Claim
texts are harvested from this estate; assignment is a seeded recorded-run
with known overlap so flatten N is measured, not recalled.
"""
from __future__ import annotations

from typing import Any

from harvest import harvest_research_findings

N_RESEARCHERS = 6
CLONE_TAG = " clone-repeat"


def _by_family(findings: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    return [f for f in findings if f["family"].startswith(prefix)]


def _slice(pool: list[dict[str, str]], start: int, width: int) -> list[dict[str, str]]:
    if not pool:
        return []
    out = []
    for k in range(width):
        out.append(pool[(start + k) % len(pool)])
    # stable unique by id, preserving order
    seen: set[str] = set()
    uniq = []
    for row in out:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        uniq.append(row)
    return uniq


def _pack(rows: list[dict[str, str]]) -> dict[str, list]:
    return {
        "ids": [r["id"] for r in rows],
        "texts": [r["text"] for r in rows],
        "sources": sorted({r["source"] for r in rows}),
    }


def _dissent_id(fid: str) -> str:
    return f"{fid}::dissent"


def _dissent_text(row: dict[str, str]) -> str:
    # Lexically distant on purpose so Jaccard does not swallow polarity.
    return f"Dissenting counter-claim against {row['id']}: no cheap satisfaction recipe exists"


def build() -> dict[str, Any]:
    findings = harvest_research_findings()
    landscape_pool = [f for f in findings if not f["family"].startswith("targeted-")]
    targeted_pool = _by_family(findings, "targeted-")
    if len(landscape_pool) < 8 or len(targeted_pool) < 8:
        raise RuntimeError(
            f"harvest too small landscape={len(landscape_pool)} targeted={len(targeted_pool)}"
        )

    # Landscape: advancing windows over landscape-family findings only (broad
    # scan across delivered research artifacts). Width/stride chosen so the
    # id-union keeps growing through n=4; wraparound at n=5-6 is the flatten.
    mixed = landscape_pool
    land_width = 12
    land_stride = 10
    landscape_rs = [
        _slice(mixed, i * land_stride, land_width) for i in range(N_RESEARCHERS)
    ]

    # Targeted: small universe (first 8 scorecard checks), high overlap.
    # R3 onward repeats the early set so id-marginal hits the noise floor
    # two consecutive researchers before the landscape pool is exhausted.
    core = targeted_pool[:8]
    targeted_rs = [
        list(core[:5]),
        list(core[2:7]),
        list(core[:5]),
        list(core[:5]),
        list(core[:5]),
        list(core[:5]),
    ]

    # Contradiction pairs: true harvested id vs planted dissent id.
    land_pairs = []
    for row in landscape_pool[:4]:
        land_pairs.append((row["id"], _dissent_id(row["id"])))
    targ_pairs = []
    for row in core[:4]:
        targ_pairs.append((row["id"], _dissent_id(row["id"])))

    # Landscape: dissent on researcher 4 so both sides appear before flatten,
    # without injecting new ids into the n=5/n=6 zero window.
    for row in landscape_pool[:4]:
        planted = {
            "id": _dissent_id(row["id"]),
            "text": _dissent_text(row),
            "source": "planted-dissent",
            "family": "dissent",
        }
        landscape_rs[3].append(planted)

    # Targeted: dissent on researcher 2 (early coverage of both sides).
    for row in core[:4]:
        planted = {
            "id": _dissent_id(row["id"]),
            "text": _dissent_text(row),
            "source": "planted-dissent",
            "family": "dissent",
        }
        targeted_rs[1].append(planted)
        targeted_rs[2].append(planted)

    clone_src = landscape_rs[0]
    clone = [
        {
            "id": f"{r['id']}::clone",
            "text": r["text"] + CLONE_TAG,
            "source": r["source"],
            "family": "same-prompt-clone",
        }
        for r in clone_src
    ]

    return {
        "harvest_n": len(findings),
        "landscape_pool_n": len(landscape_pool),
        "targeted_pool_n": len(targeted_pool),
        "n_researchers": N_RESEARCHERS,
        "landscape": [_pack(r) for r in landscape_rs],
        "targeted": [_pack(r) for r in targeted_rs],
        "clone": {
            "original": _pack(clone_src),
            "clone": _pack(clone),
            "prompt": "SAME prompt bytes as landscape researcher 1; output is a tagged paraphrase",
        },
        "contradiction_pairs": {
            "landscape": [list(p) for p in land_pairs],
            "targeted": [list(p) for p in targ_pairs],
        },
        "note": (
            "Dedicated multi-researcher transcripts for the two named run "
            "shapes were not on disk. Texts are harvested from delivered "
            "research artifacts; assignment is a constructed recorded-run."
        ),
    }


def researchers_texts(shape: list[dict]) -> list[list[str]]:
    return [list(r["texts"]) for r in shape]


def researchers_ids(shape: list[dict]) -> list[list[str]]:
    return [list(r["ids"]) for r in shape]
