"""Asymmetric compat graph: census, per-pair adjudication, typed repair.

Two independent census paths:
  census_from_lists  — walk blueprints[].compat
  census_from_matrix — N×N adjacency, then count (must agree)

Adjudication is typed, never bulk:
  FEEDS / EXTENDS / SPECIALIZES / PRODUCES-FOR → DIRECTIONAL
  PEER / COMPATIBLE / FUSIBLE                 → MISSING-REVERSE

Bulk-symmetrise (add every missing reverse) is a distinct operation and is
rejected by repair_is_admissible whenever any DIRECTIONAL pair exists.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

DIRECTIONAL_RELATIONS = frozenset(
    {"FEEDS", "EXTENDS", "SPECIALIZES", "PRODUCES-FOR"}
)
PEER_RELATIONS = frozenset({"PEER", "COMPATIBLE", "FUSIBLE"})
VERDICTS = frozenset({"DIRECTIONAL", "MISSING-REVERSE"})

PUBLISHED = {
    "blueprints": 108,
    "declared": 390,
    "undirected": 265,
    "asymmetric": 140,
    "dangling": 0,
}

LIVE_LIBRARY_CANDIDATES = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/wfa/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)
LIVE_MAPS_CANDIDATES = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "command-center/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "command-center/sources/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
)


def ids_108() -> list[str]:
    return [f"BP-{i:03d}" for i in range(1, 109)]


def families() -> list[tuple[str, list[str]]]:
    ids = ids_108()
    out: list[tuple[str, list[str]]] = []
    i = 0
    sizes = [6] * 8 + [5] * 12
    for n, size in enumerate(sizes, start=1):
        out.append((f"FAM-{n:02d}", ids[i : i + size]))
        i += size
    if i != 108:
        raise RuntimeError(f"family partition does not cover 108 (i={i})")
    return out


def _norm_entry(raw: Any) -> dict[str, str] | None:
    if isinstance(raw, str) and raw.strip():
        return {"id": raw.strip(), "relation": "UNKNOWN"}
    if isinstance(raw, dict):
        tid = raw.get("id") or raw.get("target") or raw.get("blueprint")
        if not tid:
            return None
        rel = str(
            raw.get("relation") or raw.get("kind") or raw.get("type") or "UNKNOWN"
        )
        return {"id": str(tid), "relation": rel.upper()}
    return None


def blueprints_of(library: dict) -> list[dict]:
    raw = library.get("blueprints")
    if not isinstance(raw, list):
        return []
    out = []
    for bp in raw:
        if not isinstance(bp, dict) or not bp.get("id"):
            continue
        entries = []
        for item in bp.get("compat") or []:
            n = _norm_entry(item)
            if n:
                entries.append(n)
        out.append(
            {
                "id": str(bp["id"]),
                "family": str(bp.get("family") or ""),
                "title": str(bp.get("title") or bp["id"]),
                "compat": entries,
            }
        )
    return out


def by_id(blueprints: Iterable[dict]) -> dict[str, dict]:
    return {str(bp["id"]): bp for bp in blueprints}


def relation(src: dict, dst_id: str) -> str | None:
    for e in src.get("compat") or []:
        if e.get("id") == dst_id:
            return str(e.get("relation") or "UNKNOWN")
    return None


def directed_pairs(blueprints: list[dict]) -> list[tuple[str, str, str]]:
    rows = []
    for bp in blueprints:
        sid = str(bp["id"])
        for e in bp.get("compat") or []:
            rows.append((sid, str(e["id"]), str(e.get("relation") or "UNKNOWN")))
    rows.sort()
    return rows


def census_from_lists(blueprints: list[dict]) -> dict[str, int]:
    known = {str(bp["id"]) for bp in blueprints}
    declared = 0
    dangling = 0
    undirected: set[frozenset[str]] = set()
    asymmetric_ordered: set[tuple[str, str]] = set()
    adj: dict[str, set[str]] = {i: set() for i in known}
    for sid, tid, _rel in directed_pairs(blueprints):
        declared += 1
        if tid not in known:
            dangling += 1
            continue
        adj[sid].add(tid)
        undirected.add(frozenset({sid, tid}))
    for a, outs in adj.items():
        for b in outs:
            if a not in adj.get(b, set()):
                asymmetric_ordered.add((a, b))
    return {
        "blueprints": len(blueprints),
        "declared": declared,
        "undirected": len(undirected),
        "asymmetric": len(asymmetric_ordered),
        "dangling": dangling,
    }


def census_from_matrix(blueprints: list[dict]) -> dict[str, int]:
    ids = sorted(str(bp["id"]) for bp in blueprints)
    idx = {i: n for n, i in enumerate(ids)}
    n = len(ids)
    matrix = [[0] * n for _ in range(n)]
    dangling = 0
    declared = 0
    for sid, tid, _rel in directed_pairs(blueprints):
        declared += 1
        j = idx.get(tid)
        if j is None:
            dangling += 1
            continue
        matrix[idx[sid]][j] = 1
    undirected = 0
    asymmetric = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = matrix[i][j], matrix[j][i]
            if a or b:
                undirected += 1
            if a != b:
                asymmetric += 1
    return {
        "blueprints": n,
        "declared": declared,
        "undirected": undirected,
        "asymmetric": asymmetric,
        "dangling": dangling,
    }


def asymmetric_ordered(blueprints: list[dict]) -> list[tuple[str, str, str]]:
    known = {str(bp["id"]) for bp in blueprints}
    have: dict[str, set[str]] = {i: set() for i in known}
    rels: dict[tuple[str, str], str] = {}
    for sid, tid, rel in directed_pairs(blueprints):
        if tid not in known:
            continue
        have[sid].add(tid)
        rels[(sid, tid)] = rel
    rows = []
    for a, outs in have.items():
        for b in outs:
            if a not in have.get(b, set()):
                rows.append((a, b, rels.get((a, b), "UNKNOWN")))
    rows.sort()
    return rows


def adjudicate_pair(src: dict, dst_id: str) -> dict[str, str]:
    rel = relation(src, dst_id) or "UNKNOWN"
    if rel in DIRECTIONAL_RELATIONS:
        verdict = "DIRECTIONAL"
        reason = (
            f"{src['id']} {rel} {dst_id}: reverse declaration would invert a "
            "pipeline/specialisation arrow; the reverse is not a missing PEER"
        )
    elif rel in PEER_RELATIONS:
        verdict = "MISSING-REVERSE"
        reason = (
            f"{src['id']} declares {dst_id} as {rel} with no reciprocal; "
            "same-layer compatibility is undirected, so the reverse is omitted"
        )
    else:
        verdict = "UNRESOLVED"
        reason = (
            f"{src['id']} → {dst_id} has relation={rel}; no typed rule applies "
            "(refusing to bulk-symmetrise unknowns)"
        )
    return {
        "from": str(src["id"]),
        "to": dst_id,
        "relation": rel,
        "verdict": verdict,
        "reason": reason,
    }


def adjudicate_all(blueprints: list[dict]) -> list[dict[str, str]]:
    index = by_id(blueprints)
    out = []
    for a, b, _rel in asymmetric_ordered(blueprints):
        out.append(adjudicate_pair(index[a], b))
    return out


def _ensure_compat(bp: dict, target: str, rel: str) -> None:
    for e in bp["compat"]:
        if e["id"] == target:
            return
    bp["compat"].append({"id": target, "relation": rel})


def typed_repair(blueprints: list[dict], verdicts: list[dict]) -> list[dict]:
    repaired = deepcopy(blueprints)
    index = by_id(repaired)
    for v in verdicts:
        if v["verdict"] != "MISSING-REVERSE":
            continue
        dst = index[v["to"]]
        _ensure_compat(dst, v["from"], v["relation"])
    for bp in repaired:
        bp["compat"] = sorted(bp["compat"], key=lambda e: (e["id"], e["relation"]))
    return repaired


def bulk_symmetrise(blueprints: list[dict]) -> list[dict]:
    """Forbidden operation: add every missing reverse regardless of type."""
    repaired = deepcopy(blueprints)
    index = by_id(repaired)
    for a, b, rel in asymmetric_ordered(blueprints):
        _ensure_compat(index[b], a, rel)
    for bp in repaired:
        bp["compat"] = sorted(bp["compat"], key=lambda e: (e["id"], e["relation"]))
    return repaired


def repair_is_admissible(
    original: list[dict], repaired: list[dict], verdicts: list[dict]
) -> tuple[bool, str]:
    asy_orig = {(a, b) for a, b, _ in asymmetric_ordered(original)}
    asy_rep = {(a, b) for a, b, _ in asymmetric_ordered(repaired)}
    directional = {
        (v["from"], v["to"]) for v in verdicts if v["verdict"] == "DIRECTIONAL"
    }
    missing = {
        (v["from"], v["to"]) for v in verdicts if v["verdict"] == "MISSING-REVERSE"
    }
    unresolved = [v for v in verdicts if v["verdict"] not in VERDICTS]
    if unresolved:
        return False, f"unresolved-verdicts:{len(unresolved)}"
    if asy_orig != directional | missing:
        return False, "verdicts-do-not-cover-asymmetric-set"
    if not directional:
        return False, "zero-DIRECTIONAL-would-allow-bulk-symmetrise-to-look-honest"
    if not missing:
        return False, "zero-MISSING-REVERSE-repair-is-a-no-op"
    if not directional.issubset(asy_rep):
        lost = sorted(directional - asy_rep)
        return False, f"DIRECTIONAL-did-not-persist:{lost[:3]}"
    leftover = missing & asy_rep
    if leftover:
        return False, f"MISSING-REVERSE-still-asymmetric:{sorted(leftover)[:3]}"
    c0 = census_from_lists(original)
    c1 = census_from_lists(repaired)
    if c0["undirected"] != c1["undirected"]:
        return False, "undirected-count-changed"
    if c1["dangling"] != 0:
        return False, "dangling-after-repair"
    if c1["asymmetric"] == 0:
        return False, "asymmetry-driven-to-zero-bulk-symmetrise"
    if c1["asymmetric"] != len(directional):
        return False, "remaining-asymmetric-!=-DIRECTIONAL-count"
    extra = asy_rep - directional
    if extra:
        return False, f"new-asymmetric-pairs:{sorted(extra)[:3]}"
    return True, "ok"


def build_replica_library() -> dict[str, Any]:
    fams = families()
    fam_of = {bp: fam for fam, members in fams for bp in members}
    compat: dict[str, list[dict[str, str]]] = {i: [] for i in ids_108()}
    used: set[frozenset[str]] = set()

    feed_n = 0
    for _fam, members in fams:
        for a, b in zip(members, members[1:]):
            compat[a].append({"id": b, "relation": "FEEDS"})
            used.add(frozenset({a, b}))
            feed_n += 1

    peer_one: list[tuple[str, str]] = []
    ids = ids_108()
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            fs = frozenset({a, b})
            if fs in used:
                continue
            compat[a].append({"id": b, "relation": "PEER"})
            used.add(fs)
            peer_one.append((a, b))
            if len(peer_one) >= 52:
                break
        if len(peer_one) >= 52:
            break

    mutual: list[tuple[str, str]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            fs = frozenset({a, b})
            if fs in used:
                continue
            compat[a].append({"id": b, "relation": "PEER"})
            compat[b].append({"id": a, "relation": "PEER"})
            used.add(fs)
            mutual.append((a, b))
            if len(mutual) >= 125:
                break
        if len(mutual) >= 125:
            break

    if feed_n != 88 or len(peer_one) != 52 or len(mutual) != 125:
        raise RuntimeError(
            f"replica construction missed targets feed={feed_n} "
            f"peer_one={len(peer_one)} mutual={len(mutual)}"
        )

    blueprints = []
    for bp_id in ids:
        blueprints.append(
            {
                "id": bp_id,
                "family": fam_of[bp_id],
                "title": f"Census-replica blueprint {bp_id}",
                "compat": sorted(compat[bp_id], key=lambda e: e["id"]),
            }
        )
    decoy_counts = {
        "declared": 999,
        "undirected": 0,
        "asymmetric": 0,
        "dangling": 99,
        "note": "DECOY counts block — WFA-0149 must re-derive from blueprints[].compat",
    }
    return {
        "id": "09-WORKFLOW-BLUEPRINT-LIBRARY-CENSUS-REPLICA",
        "kind": "census-replica",
        "published_census": dict(PUBLISHED),
        "counts": decoy_counts,
        "construction": {
            "families": 20,
            "feed_pipeline_edges": feed_n,
            "peer_one_way": len(peer_one),
            "mutual_peer_pairs": len(mutual),
        },
        "blueprints": blueprints,
    }


def probe_live_paths(repo: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in LIVE_LIBRARY_CANDIDATES + LIVE_MAPS_CANDIDATES:
        p = Path(rel) if Path(rel).is_absolute() else repo / rel
        rows.append(
            {
                "path": rel,
                "absolute": str(p),
                "present": p.is_file() and p.stat().st_size > 0,
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return rows


def load_subject(repo: Path) -> tuple[dict[str, Any], str, bool]:
    """Return (library, source_label, live). Live wins only if it has blueprints."""
    for rel in LIVE_LIBRARY_CANDIDATES:
        p = Path(rel) if Path(rel).is_absolute() else repo / rel
        if not (p.is_file() and p.stat().st_size > 0):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not blueprints_of(data):
            continue
        return data, str(p).replace("\\", "/"), True
    replica = build_replica_library()
    return replica, "census-replica", False


def compact_graph(blueprints: list[dict]) -> list[dict]:
    return [
        {
            "id": bp["id"],
            "family": bp.get("family"),
            "compat": list(bp.get("compat") or []),
        }
        for bp in blueprints
    ]
