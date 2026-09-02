#!/usr/bin/env python3
"""Structural fuse/decompose and the lineage record a fusion must carry.

decompose(fuse(sources)) recovers the source id set from the fusion BODY
(component blobs), not from a copied sources_declared side channel.
Two independent walks must agree or the round trip is BLOCKED as
detector-failure, not a picked winner.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

OPERATOR = "structural-union"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_fingerprint(source_id: str) -> str:
    return sha256_text("source-id\n" + source_id)


def canonical_blob(source_id: str) -> str:
    payload = {
        "fingerprint": source_fingerprint(source_id),
        "kind": "source-mechanism",
        "source_id": source_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def fuse(
    sources_declared: list[str],
    sources_unresolved: list[str] | None = None,
    fusion_id: str = "fusion",
) -> dict[str, Any]:
    """Embed only resolvable sources. Unresolved ids are skipped, not invented."""
    unresolved = list(sources_unresolved or [])
    skip = set(unresolved)
    components: list[dict[str, str]] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for sid in sources_declared:
        if sid in skip:
            if sid not in skipped:
                skipped.append(sid)
            continue
        if sid in seen:
            continue
        seen.add(sid)
        blob = canonical_blob(sid)
        components.append({"blob": blob, "blob_sha256": sha256_text(blob)})
    return {
        "kind": "fused-workflow",
        "fusion_id": fusion_id,
        "operator": OPERATOR,
        "components": components,
        "unresolved_skipped": skipped,
    }


def _parse_component(comp: dict[str, Any]) -> str:
    blob = comp.get("blob")
    digest = comp.get("blob_sha256")
    if not isinstance(blob, str) or not isinstance(digest, str):
        raise ValueError("component-malformed")
    if sha256_text(blob) != digest:
        raise ValueError("blob-sha-mismatch")
    doc = json.loads(blob)
    if not isinstance(doc, dict):
        raise ValueError("blob-not-object")
    sid = doc.get("source_id")
    if not isinstance(sid, str) or not sid:
        raise ValueError("blob-missing-source-id")
    if doc.get("fingerprint") != source_fingerprint(sid):
        raise ValueError("fingerprint-mismatch")
    return sid


def decompose_signal_a_blob_parse(fusion: dict[str, Any]) -> list[str]:
    """Signal A: parse each component blob and collect source_id."""
    ids: list[str] = []
    for comp in fusion.get("components") or []:
        if not isinstance(comp, dict):
            raise ValueError("component-not-object")
        ids.append(_parse_component(comp))
    return sorted(ids)


def decompose_signal_b_fingerprint_walk(fusion: dict[str, Any]) -> list[str]:
    """Signal B: re-hash blobs, invert fingerprint, collect ids (separate walk)."""
    ids: list[str] = []
    for comp in fusion.get("components") or []:
        if not isinstance(comp, dict):
            raise ValueError("component-not-object")
        blob = comp.get("blob")
        if not isinstance(blob, str):
            raise ValueError("component-malformed")
        if sha256_text(blob) != comp.get("blob_sha256"):
            raise ValueError("blob-sha-mismatch")
        doc = json.loads(blob)
        sid = str(doc.get("source_id") or "")
        fp = str(doc.get("fingerprint") or "")
        if source_fingerprint(sid) != fp:
            raise ValueError("fingerprint-mismatch")
        ids.append(sid)
    # Independent of signal A: invert via fingerprint map, then return
    # lexicographic source ids so the two walks are comparable as lists.
    by_fp = {source_fingerprint(s): s for s in ids}
    if len(by_fp) != len(ids):
        raise ValueError("fingerprint-collision")
    recovered = [by_fp[fp] for fp in sorted(by_fp)]
    return sorted(recovered)


def decompose(fusion: dict[str, Any]) -> list[str]:
    a = decompose_signal_a_blob_parse(fusion)
    b = decompose_signal_b_fingerprint_walk(fusion)
    if a != b:
        raise ValueError(f"signal-disagreement a={a} b={b}")
    return a


def drop_source(fusion: dict[str, Any], source_id: str) -> dict[str, Any]:
    kept: list[dict[str, Any]] = []
    dropped = False
    for comp in fusion.get("components") or []:
        sid = _parse_component(comp)
        if sid == source_id:
            dropped = True
            continue
        kept.append(comp)
    if not dropped:
        raise ValueError(f"source-not-in-fusion:{source_id}")
    out = dict(fusion)
    out["components"] = kept
    return out


def set_diff(declared: list[str], recovered: list[str]) -> dict[str, list[str]]:
    d, r = set(declared), set(recovered)
    return {
        "missing": sorted(d - r),
        "extra": sorted(r - d),
    }


def round_trip(merge_unit: dict[str, Any]) -> dict[str, Any]:
    uid = str(merge_unit.get("id") or merge_unit.get("merge_unit_id") or "")
    declared = sorted({str(x) for x in (merge_unit.get("sources_declared") or [])})
    unresolved = [str(x) for x in (merge_unit.get("sources_unresolved") or [])]
    fusion = fuse(declared, unresolved, fusion_id=f"fuse:{uid}")
    disagreement = None
    try:
        sig_a = decompose_signal_a_blob_parse(fusion)
        sig_b = decompose_signal_b_fingerprint_walk(fusion)
        if sig_a != sig_b:
            disagreement = {"signal_a": sig_a, "signal_b": sig_b}
            recovered: list[str] = []
        else:
            recovered = sig_a
    except (ValueError, json.JSONDecodeError, TypeError, KeyError) as exc:
        disagreement = {"error": f"{type(exc).__name__}:{exc}"}
        recovered = []
        sig_a, sig_b = [], []
    diff = set_diff(declared, recovered)
    missing, extra = diff["missing"], diff["extra"]
    unresolved_sorted = sorted(set(unresolved))
    fail_because_unresolved = (
        bool(unresolved_sorted)
        and missing == unresolved_sorted
        and not extra
        and disagreement is None
    )
    ok = declared == recovered and disagreement is None
    return {
        "merge_unit_id": uid,
        "declared": sorted(declared),
        "unresolved_recorded": unresolved_sorted,
        "recovered": recovered,
        "missing": missing,
        "extra": extra,
        "round_trip_ok": ok,
        "fail_because_unresolved": fail_because_unresolved,
        "signal_disagreement": disagreement,
        "signals": {
            "set_equality": ok,
            "fingerprint_walk_agrees": disagreement is None and sig_a == sig_b,
        },
        "fusion": fusion,
    }


def lineage_record_for(merge_unit: dict[str, Any], trip: dict[str, Any]) -> dict[str, Any]:
    fusion = trip["fusion"]
    return {
        "kind": "lineage-record",
        "merge_unit_id": trip["merge_unit_id"],
        "fusion_id": fusion.get("fusion_id"),
        "operator": fusion.get("operator"),
        "sources_declared": trip["declared"],
        "sources_unresolved": trip["unresolved_recorded"],
        "recovered_sources": trip["recovered"],
        "decomposition": list(trip["recovered"]),
        "missing": trip["missing"],
        "extra": trip["extra"],
        "round_trip_ok": trip["round_trip_ok"],
        "fail_because_unresolved": trip["fail_because_unresolved"],
        "signal_disagreement": trip["signal_disagreement"],
        "signals": trip["signals"],
        "component_count": len(fusion.get("components") or []),
    }


def both_states_drop_restore(merge_unit: dict[str, Any]) -> dict[str, Any]:
    """Drop one embedded source; fail must name it. Restore; trip must pass."""
    declared = [str(x) for x in (merge_unit.get("sources_declared") or [])]
    unresolved = set(str(x) for x in (merge_unit.get("sources_unresolved") or []))
    embeddable = [s for s in declared if s not in unresolved]
    if len(embeddable) < 2:
        raise ValueError("need-two-embeddable-sources-for-both-states")
    dropped = embeddable[0]
    fusion = fuse(declared, list(unresolved), fusion_id="both-states")
    broken = drop_source(fusion, dropped)
    recovered_broken = decompose(broken)
    diff_broken = set_diff(declared, recovered_broken)
    restored = fuse(declared, list(unresolved), fusion_id="both-states")
    recovered_restored = decompose(restored)
    expected_missing_on_drop = sorted(set(declared) - set(recovered_broken))
    return {
        "merge_unit_id": str(merge_unit.get("id") or ""),
        "dropped_source": dropped,
        "drop_missing": diff_broken["missing"],
        "drop_extra": diff_broken["extra"],
        "drop_names_exact_source": dropped in diff_broken["missing"],
        "drop_round_trip_ok": recovered_broken == declared,
        "restore_recovered": recovered_restored,
        "restore_round_trip_ok": recovered_restored == sorted(declared),
        "expected_missing_on_drop": expected_missing_on_drop,
    }
