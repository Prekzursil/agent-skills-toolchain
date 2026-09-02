"""Three-council meta aggregation that preserves disagreement (IMP-0289)."""
from __future__ import annotations

import copy
from typing import Any

DISAGREEMENT = "DISAGREEMENT"
ADOPT = "ADOPT"


def three_council_fixture() -> list[dict[str, Any]]:
    return [
        {
            "council_id": "c-alpha",
            "verdict": "ADOPT",
            "minority_reports": [{"id": "mr-a1", "claim": "hold-alpha"}],
            "dissents": [{"id": "ds-a1", "seat": "critic-a"}],
        },
        {
            "council_id": "c-beta",
            "verdict": "HOLD",
            "minority_reports": [{"id": "mr-b1", "claim": "ship-beta"}],
            "dissents": [{"id": "ds-b1", "seat": "critic-b"}],
        },
        {
            "council_id": "c-gamma",
            "verdict": "ADOPT",
            "minority_reports": [{"id": "mr-g1", "claim": "rewrite-gamma"}],
            "dissents": [{"id": "ds-g1", "seat": "critic-g"}],
        },
    ]


def collect_minority_ids(councils: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for c in councils:
        for row in c.get("minority_reports") or []:
            i = str(row.get("id") or "")
            if i:
                out.append(i)
    return out


def collect_dissent_ids(councils: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for c in councils:
        for row in c.get("dissents") or []:
            i = str(row.get("id") or "")
            if i:
                out.append(i)
    return out


def aggregate(councils: list[dict[str, Any]]) -> dict[str, Any]:
    hist: dict[str, int] = {}
    for c in councils:
        v = str(c.get("verdict") or "")
        hist[v] = hist.get(v, 0) + 1
    mr = collect_minority_ids(councils)
    ds = collect_dissent_ids(councils)
    disagreement = len(hist) > 1 or bool(mr) or bool(ds)
    return {
        "councils": councils,
        "verdict_histogram": hist,
        "meta_verdict": DISAGREEMENT if disagreement else ADOPT,
        "irreducible_disagreement": bool(disagreement),
        "minority_reports": [{"id": i} for i in mr],
        "dissents": [{"id": i} for i in ds],
        "reachable_ids": list(mr),
        "minority_ids": list(mr),
    }


def drop_minority_report(meta: dict[str, Any], report_id: str) -> dict[str, Any]:
    """Negative-control mutant: a copy of ``meta`` that has lost one minority report.

    The report is removed from every meta-level surface (``minority_reports``,
    ``reachable_ids``, ``minority_ids``) so the artifact genuinely no longer
    reaches it; the source ``councils`` are left untouched, which is exactly
    the dissent-loss class a reachability check must catch. ``meta`` itself is
    not mutated.
    """
    mutated = copy.deepcopy(meta)
    rid = str(report_id)
    mutated["minority_reports"] = [
        x for x in (mutated.get("minority_reports") or []) if str(x.get("id") if isinstance(x, dict) else x) != rid
    ]
    for key in ("reachable_ids", "minority_ids"):
        if key in mutated:
            mutated[key] = [x for x in (mutated.get(key) or []) if str(x) != rid]
    mutated.setdefault("mutations", []).append({"kind": "drop-minority-report", "id": rid})
    return mutated


def check_reachability(meta: dict[str, Any], expected: list[str]) -> dict[str, Any]:
    have = {str(x.get("id") or x) for x in (meta.get("minority_reports") or [])}
    have |= {str(x) for x in (meta.get("reachable_ids") or [])}
    have |= {str(x) for x in (meta.get("minority_ids") or [])}
    missing = [i for i in expected if i not in have]
    return {
        "ok": not missing,
        "reachable_ids": sorted(have),
        "missing_ids": missing,
    }


def compare_dissent_counts(meta: dict[str, Any], councils: list[dict[str, Any]]) -> dict[str, Any]:
    ds_in = collect_dissent_ids(councils)
    mr_in = collect_minority_ids(councils)
    ds_out = [str(x.get("id") or x) for x in (meta.get("dissents") or [])]
    mr_out = [str(x.get("id") or x) for x in (meta.get("minority_reports") or [])]
    ds_lost = sorted(set(ds_in) - set(ds_out))
    mr_lost = sorted(set(mr_in) - set(mr_out))
    # Census: the counts are integers (in == out is the invariant); the id lists
    # ride alongside so a drift names exactly what was lost or invented.
    return {
        "ok": sorted(ds_in) == sorted(ds_out) and sorted(mr_in) == sorted(mr_out),
        "dissents_in": len(ds_in),
        "dissents_out": len(ds_out),
        "minority_in": len(mr_in),
        "minority_out": len(mr_out),
        "dissents_only_in": ds_lost,
        "dissents_only_out": sorted(set(ds_out) - set(ds_in)),
        "minority_only_in": mr_lost,
        "minority_only_out": sorted(set(mr_out) - set(mr_in)),
        "dissent_ids_in": ds_in,
        "dissent_ids_out": ds_out,
        "minority_ids_in": mr_in,
        "minority_ids_out": mr_out,
    }
