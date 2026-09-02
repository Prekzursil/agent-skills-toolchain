#!/usr/bin/env python3
"""Stratified sampling frame over a claim registry.

Strata = severity × subsystem × author-vendor × claim-type.
The frame must PARTITION the registry: every claim in exactly one stratum,
counts sum to n, pairwise intersections empty.

Missing severity fails loudly (never defaults to low).
A novel subsystem value opens a new stratum (never buckets into 'other').
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

AXES = ("severity", "subsystem", "author_vendor", "claim_type")


class FrameBuildError(Exception):
    """Loud failure: do not emit a frame that defaulted or dropped claims."""


@dataclass(frozen=True)
class NormalizedClaim:
    id: str
    severity: str
    subsystem: str
    author_vendor: str
    claim_type: str
    raw: Mapping[str, Any] = field(repr=False)

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.severity, self.subsystem, self.author_vendor, self.claim_type)

    @property
    def stratum_id(self) -> str:
        return "|".join(self.key)


@dataclass
class Frame:
    claims: list[NormalizedClaim]
    strata: dict[tuple[str, str, str, str], list[str]]
    proof: dict[str, Any]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _first(raw: Mapping[str, Any], names: Iterable[str]) -> str:
    for name in names:
        if name in raw:
            t = _text(raw.get(name))
            if t:
                return t
    return ""


def catalog_vendor_map(catalog: Mapping[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(catalog, Mapping):
        return out
    units = catalog.get("work_units")
    if not isinstance(units, list):
        return out
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = _text(unit.get("id"))
        role = unit.get("assigned_model_vendor_role")
        if not isinstance(role, dict):
            role = {}
        vendor = _text(role.get("vendor"))
        if uid and vendor:
            out[uid] = vendor
    return out


def extract_claim_list(doc: Any) -> list[dict]:
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = None
        for key in ("claims", "entries", "records"):
            val = doc.get(key)
            if isinstance(val, list):
                rows = val
                break
        if rows is None:
            raise FrameBuildError(
                "registry has no claims/entries/records list; refusing empty-set pass"
            )
    else:
        raise FrameBuildError(f"registry is {type(doc).__name__}, not a claims document")
    out: list[dict] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise FrameBuildError(f"claims[{i}] is not an object")
        out.append(row)
    if not out:
        raise FrameBuildError(
            "registry claims list is empty; refusing empty-set pass over the wrong denominator"
        )
    return out


def normalize_claim(
    raw: Mapping[str, Any],
    catalog_vendors: Mapping[str, str] | None = None,
) -> NormalizedClaim:
    cid = _first(raw, ("id", "claim_id"))
    if not cid:
        raise FrameBuildError("claim missing id/claim_id")

    severity = _first(raw, ("severity",))
    if not severity:
        raise FrameBuildError(
            f"claim {cid} missing required field severity; "
            "refusing to default to low"
        )

    subsystem = _first(raw, ("subsystem",))
    if not subsystem:
        raise FrameBuildError(
            f"claim {cid} missing required field subsystem; "
            "refusing to bucket into 'other'"
        )

    vendor = _first(raw, ("author_vendor", "author-vendor"))
    if not vendor:
        unit = _first(raw, ("source_unit_id", "unit_id", "source_unit"))
        if unit and catalog_vendors:
            vendor = _text(catalog_vendors.get(unit))
    if not vendor:
        raise FrameBuildError(
            f"claim {cid} missing author-vendor and no catalog join; "
            "refusing to bucket into 'other'"
        )

    ctype = _first(raw, ("claim_type", "claim-type", "kind", "check_type"))
    if not ctype:
        raise FrameBuildError(
            f"claim {cid} missing claim-type; refusing to bucket into 'other'"
        )

    return NormalizedClaim(
        id=cid,
        severity=severity,
        subsystem=subsystem,
        author_vendor=vendor,
        claim_type=ctype,
        raw=dict(raw),
    )


def prove_partition(claims: list[NormalizedClaim], strata: dict) -> dict[str, Any]:
    ids = [c.id for c in claims]
    n = len(ids)
    if len(set(ids)) != n:
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise FrameBuildError(f"duplicate claim ids: {dup}")

    placed: list[str] = []
    for members in strata.values():
        placed.extend(members)
    if len(placed) != n or set(placed) != set(ids):
        missing = sorted(set(ids) - set(placed))
        extra = sorted(set(placed) - set(ids))
        raise FrameBuildError(
            f"placement is not a cover: missing={missing} extra={extra}"
        )

    keys = list(strata)
    for i, ka in enumerate(keys):
        sa = set(strata[ka])
        for kb in keys[i + 1 :]:
            inter = sa & set(strata[kb])
            if inter:
                raise FrameBuildError(
                    f"pairwise intersection not empty: {ka} ∩ {kb} = {sorted(inter)}"
                )

    sum_counts = sum(len(v) for v in strata.values())
    if sum_counts != n:
        raise FrameBuildError(
            f"sum(stratum counts)={sum_counts} != registry_n={n}"
        )
    return {
        "registry_n": n,
        "sum_stratum_counts": sum_counts,
        "stratum_count": len(strata),
        "equal": True,
        "pairwise_intersections_empty": True,
        "every_claim_exactly_one": True,
        "dropped_claim_ids": [],
    }


def build_frame(
    claims_raw: Iterable[Mapping[str, Any]],
    catalog_vendors: Mapping[str, str] | None = None,
) -> Frame:
    claims = [normalize_claim(row, catalog_vendors) for row in claims_raw]
    if not claims:
        raise FrameBuildError("no claims after normalize; refusing empty-set pass")
    strata: dict[tuple[str, str, str, str], list[str]] = {}
    for claim in claims:
        strata.setdefault(claim.key, []).append(claim.id)
    proof = prove_partition(claims, strata)
    return Frame(claims=claims, strata=strata, proof=proof)


def stratum_rows(frame: Frame) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(frame.strata):
        ids = list(frame.strata[key])
        rows.append(
            {
                "stratum_id": "|".join(key),
                "severity": key[0],
                "subsystem": key[1],
                "author_vendor": key[2],
                "claim_type": key[3],
                "count": len(ids),
                "claim_ids": ids,
            }
        )
    return rows


def locate_claim(frame: Frame, claim_id: str) -> tuple[tuple[str, str, str, str], list[str]]:
    found: list[tuple[str, str, str, str]] = []
    for key, members in frame.strata.items():
        if claim_id in members:
            found.append(key)
    if not found:
        raise FrameBuildError(f"claim {claim_id} not in any stratum")
    if len(found) != 1:
        raise FrameBuildError(f"claim {claim_id} in multiple strata: {found}")
    return found[0], frame.strata[found[0]]


def recompute_table_sum(published_strata: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Independent arithmetic over a published stratum table (reviewer signal)."""
    counts = []
    id_sets: list[set[str]] = []
    for row in published_strata:
        n = int(row["count"])
        ids = [str(x) for x in (row.get("claim_ids") or [])]
        if n != len(ids):
            raise FrameBuildError(
                f"published row {row.get('stratum_id')} count={n} != len(claim_ids)={len(ids)}"
            )
        counts.append(n)
        id_sets.append(set(ids))
    total = sum(counts)
    for i, a in enumerate(id_sets):
        for b in id_sets[i + 1 :]:
            inter = a & b
            if inter:
                raise FrameBuildError(
                    f"published pairwise intersection not empty: {sorted(inter)}"
                )
    union = set().union(*id_sets) if id_sets else set()
    if len(union) != total:
        raise FrameBuildError("published union size != sum of counts")
    return {
        "sum_stratum_counts": total,
        "union_n": len(union),
        "pairwise_intersections_empty": True,
    }
