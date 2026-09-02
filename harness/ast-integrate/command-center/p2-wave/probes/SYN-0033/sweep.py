"""Cross-phase contradiction sweep for SYN-0033.

Phase-1 contradiction-edge semantics, applied only across phase
boundaries. Intra-phase pairs are counted as excluded (Phase 1 dedup
owns them). Already-adjudicated pairs are SETTLED, not reopened.
A zero finding always publishes the examined-pair denominator.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LIVE_REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
LIVE_ADJ_REL = "command-center/synthesis/SYN-0011.adjudications.json"
B08_CANDIDATES = (
    "command-center/receipts/B08.json",
    "command-center/TEST-REGISTRY.json",
    "command-center/phase10",
)
B09_CANDIDATES = (
    "command-center/receipts/B09.json",
    "command-center/confirmation/records",
    "command-center/confirmation/B09",
)

PAIR_FORMULA = (
    "unordered pairs (i,j) among phased claims with phase(i) != phase(j); "
    "intra-phase pairs are excluded (Phase 1 dedup); unphased claims are "
    "counted separately and never enter the denominator"
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def claim_id_of(row: dict[str, Any]) -> str | None:
    for key in ("id", "claim_id", "claimId"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def claim_text(row: dict[str, Any]) -> str:
    for key in ("text", "statement", "canonical_mechanism", "claim", "proposition"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def phase_of(row: dict[str, Any]) -> int | None:
    raw = row.get("phase")
    if raw is None:
        raw = row.get("phase_id")
    if raw is None:
        raw = row.get("phase_number")
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    match = re.search(r"(\d+)", str(raw).strip())
    return int(match.group(1)) if match else None


def _as_id_list(raw: Any) -> list[str]:
    out: list[str] = []
    if isinstance(raw, str) and raw.strip():
        out.append(raw.strip())
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                cid = claim_id_of(item)
                if cid:
                    out.append(cid)
    return out


def as_claim_list(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("claims", "records", "items", "entries"):
        block = doc.get(key)
        if isinstance(block, list):
            return [x for x in block if isinstance(x, dict)]
    out: list[dict[str, Any]] = []
    for key, val in doc.items():
        if key.startswith("_") or key in {"schema_version", "meta", "contradiction_edges"}:
            continue
        if isinstance(val, dict) and (val.get("text") or val.get("id") or val.get("phase") is not None):
            row = dict(val)
            row.setdefault("id", str(key))
            out.append(row)
    return out


def normalize_claim(row: dict[str, Any], source: str) -> dict[str, Any] | None:
    cid = claim_id_of(row)
    if not cid:
        return None
    anchor = row.get("anchor") or row.get("source_anchor")
    if not isinstance(anchor, str) or not anchor.strip():
        lineage = row.get("source_lineage")
        if isinstance(lineage, dict):
            path = lineage.get("path") or lineage.get("url") or ""
            line = lineage.get("line") or lineage.get("lineno") or ""
            if path:
                anchor = f"{path}:{line}" if line != "" else str(path)
        elif isinstance(lineage, str) and lineage.strip():
            anchor = lineage.strip()
    if not isinstance(anchor, str) or not anchor.strip():
        anchor = f"{source}:{cid}"
    settling = row.get("settling_probe") or row.get("settlingProbe") or ""
    if not isinstance(settling, str):
        settling = str(settling) if settling else ""
    return {
        "id": cid,
        "phase": phase_of(row),
        "text": claim_text(row) or cid,
        "anchor": str(anchor).strip(),
        "subject": (str(row["subject"]).strip() if row.get("subject") not in (None, "") else None),
        "predicate": (
            str(row["predicate"]).strip() if row.get("predicate") not in (None, "") else None
        ),
        "value": row.get("value"),
        "exists": row.get("exists") if "exists" in row else None,
        "scope": (str(row["scope"]).strip() if row.get("scope") not in (None, "") else None),
        "denominator": (
            str(row["denominator"]).strip() if row.get("denominator") not in (None, "") else None
        ),
        "contradicts": _as_id_list(row.get("contradicts") or row.get("contradiction")),
        "settling_probe": settling.strip(),
        "raw": row,
    }


def load_claims(registry_path: Path) -> tuple[list[dict[str, Any]], list[tuple[str, str]], str | None]:
    if not registry_path.is_file():
        return [], [], "absent"
    try:
        doc = _read_json(registry_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [], [], type(exc).__name__
    source = str(registry_path).replace("\\", "/")
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in as_claim_list(doc):
        norm = normalize_claim(row, source)
        if norm is None or norm["id"] in seen:
            continue
        seen.add(norm["id"])
        claims.append(norm)
    edges: list[tuple[str, str]] = []
    if isinstance(doc, dict):
        raw_edges = doc.get("contradiction_edges") or doc.get("contradictions") or []
        if isinstance(raw_edges, list):
            for item in raw_edges:
                if not isinstance(item, dict):
                    continue
                a = item.get("a") or item.get("left") or item.get("from")
                b = item.get("b") or item.get("right") or item.get("to")
                if isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip():
                    pair = tuple(sorted((a.strip(), b.strip())))
                    edges.append((pair[0], pair[1]))
    return claims, edges, None


def _adj_pair(row: dict[str, Any]) -> tuple[str, str] | None:
    ids = _as_id_list(row.get("claim_ids") or row.get("claims") or row.get("pair"))
    if len(ids) >= 2:
        pair = tuple(sorted((ids[0], ids[1])))
        return (pair[0], pair[1])
    a = row.get("left_id") or row.get("a") or row.get("left")
    b = row.get("right_id") or row.get("b") or row.get("right")
    if isinstance(a, dict):
        a = claim_id_of(a)
    if isinstance(b, dict):
        b = claim_id_of(b)
    if isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip():
        pair = tuple(sorted((a.strip(), b.strip())))
        return (pair[0], pair[1])
    return None


def load_adjudications(path: Path) -> tuple[set[tuple[str, str]], str | None]:
    if not path.is_file():
        return set(), "absent"
    try:
        doc = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return set(), type(exc).__name__
    rows: list[dict[str, Any]]
    if isinstance(doc, list):
        rows = [x for x in doc if isinstance(x, dict)]
    elif isinstance(doc, dict):
        block = None
        for key in ("adjudications", "records", "items", "entries"):
            if isinstance(doc.get(key), list):
                block = doc[key]
                break
        rows = [x for x in (block or []) if isinstance(x, dict)]
    else:
        rows = []
    settled: set[tuple[str, str]] = set()
    for row in rows:
        pair = _adj_pair(row)
        if pair:
            settled.add(pair)
    return settled, None


def _both_numeric(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return False
    try:
        float(a)
        float(b)
        return True
    except (TypeError, ValueError):
        return False


def _norm_token(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return str(value).strip().lower()


def scoped_differently(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("scope") and b.get("scope") and a["scope"] != b["scope"]:
        return True
    if a.get("denominator") and b.get("denominator") and a["denominator"] != b["denominator"]:
        return True
    return False


def exclusive(a: dict[str, Any], b: dict[str, Any], explicit_edges: set[tuple[str, str]]) -> tuple[bool, str]:
    pair = tuple(sorted((a["id"], b["id"])))
    if pair in explicit_edges or b["id"] in a["contradicts"] or a["id"] in b["contradicts"]:
        if scoped_differently(a, b):
            return False, "explicit-edge-but-scoped-differently"
        return True, "explicit-contradiction-edge"
    if scoped_differently(a, b):
        return False, "scoped-differently"
    if a.get("exists") is not None and b.get("exists") is not None:
        same_subject = a.get("subject") and a["subject"] == b.get("subject")
        if same_subject and bool(a["exists"]) != bool(b["exists"]):
            return True, "existence-versus-absence"
    if a.get("subject") and a["subject"] == b.get("subject"):
        if a.get("predicate") and a["predicate"] == b.get("predicate"):
            va, vb = a.get("value"), b.get("value")
            if va is None or vb is None:
                return False, "same-slot-missing-value"
            if _both_numeric(va, vb):
                if float(va) != float(vb):
                    return True, "numeric-mismatch"
                return False, "numeric-equal"
            if _norm_token(va) != _norm_token(vb):
                return True, "incompatible-tokens"
    return False, "not-exclusive"


def pair_id(a_id: str, b_id: str) -> str:
    lo, hi = sorted((a_id, b_id))
    return f"{lo}::{hi}"


def settling_probe_for(a: dict[str, Any], b: dict[str, Any]) -> str:
    for probe in (a.get("settling_probe"), b.get("settling_probe")):
        if isinstance(probe, str) and len(probe.strip()) >= 8:
            return probe.strip()
    return f"re-read raw anchors {a['anchor']} vs {b['anchor']}"


def side(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": claim["id"],
        "text": claim["text"],
        "anchor": claim["anchor"],
        "phase": claim["phase"],
    }


def sweep(
    registry_path: Path,
    adj_path: Path,
) -> dict[str, Any]:
    claims, edge_list, registry_err = load_claims(registry_path)
    settled_pairs, adj_err = load_adjudications(adj_path)
    explicit = set(edge_list)
    phased = [c for c in claims if c["phase"] is not None]
    unphased = [c for c in claims if c["phase"] is None]
    phases = sorted({c["phase"] for c in phased})
    examined = 0
    intra_excluded = 0
    intra_exclusive_skipped: list[str] = []
    contradictions: list[dict[str, Any]] = []
    scoped_skip = 0
    for i, left in enumerate(phased):
        for right in phased[i + 1 :]:
            if left["phase"] == right["phase"]:
                intra_excluded += 1
                hit, why = exclusive(left, right, explicit)
                if hit:
                    intra_exclusive_skipped.append(pair_id(left["id"], right["id"]))
                continue
            examined += 1
            hit, why = exclusive(left, right, explicit)
            if why == "scoped-differently":
                scoped_skip += 1
            if not hit:
                continue
            key = tuple(sorted((left["id"], right["id"])))
            already = key in settled_pairs
            status = "SETTLED" if already else "OPEN"
            contradictions.append(
                {
                    "id": pair_id(left["id"], right["id"]),
                    "left": side(left),
                    "right": side(right),
                    "phases": [left["phase"], right["phase"]],
                    "already_adjudicated": already,
                    "status": status,
                    "settling_probe": settling_probe_for(left, right),
                    "reason": why,
                }
            )
    open_rows = [r for r in contradictions if r["status"] == "OPEN"]
    settled_rows = [r for r in contradictions if r["status"] == "SETTLED"]
    open_named = all(len(str(r.get("settling_probe") or "")) >= 8 for r in open_rows)
    counts = {
        "claims_loaded": len(claims),
        "phased_claim_count": len(phased),
        "unphased_claim_count": len(unphased),
        "distinct_phase_count": len(phases),
        "examined_pair_count": examined,
        "intra_phase_pairs_excluded": intra_excluded,
        "intra_phase_exclusive_skipped": len(intra_exclusive_skipped),
        "scoped_differently_skipped": scoped_skip,
        "open_count": len(open_rows),
        "settled_count": len(settled_rows),
        "contradiction_count": len(contradictions),
        "adjudication_pairs_loaded": len(settled_pairs),
    }
    return {
        "registry_path": str(registry_path).replace("\\", "/"),
        "registry_present": registry_path.is_file(),
        "registry_error": registry_err,
        "adjudications_path": str(adj_path).replace("\\", "/"),
        "adjudications_present": adj_path.is_file(),
        "adjudications_error": adj_err,
        "phases": phases,
        "counts": counts,
        "examined_pair_count": examined,
        "pair_formula": PAIR_FORMULA,
        "contradictions": contradictions,
        "open_ids": [r["id"] for r in open_rows],
        "settled_ids": [r["id"] for r in settled_rows],
        "intra_exclusive_skipped": intra_exclusive_skipped,
        "open_contradictions_all_named_settling_probe": bool(open_named),
        "unphased_ids": [c["id"] for c in unphased],
    }


def live_input_presence(repo: Path) -> dict[str, Any]:
    def check(rel: str) -> bool:
        p = repo / rel
        return p.is_file() or p.is_dir()

    b08_present = any(check(p) for p in B08_CANDIDATES)
    b09_present = any(check(p) for p in B09_CANDIDATES)
    return {
        "claim_registry": {
            "path": LIVE_REGISTRY_REL,
            "present": (repo / LIVE_REGISTRY_REL).is_file(),
        },
        "adjudications": {
            "path": LIVE_ADJ_REL,
            "present": (repo / LIVE_ADJ_REL).is_file(),
        },
        "b08_phase10": {
            "paths_checked": list(B08_CANDIDATES),
            "present": b08_present,
        },
        "b09_phase11": {
            "paths_checked": list(B09_CANDIDATES),
            "present": b09_present,
        },
    }


def live_sweep(repo: Path) -> dict[str, Any]:
    result = sweep(repo / LIVE_REGISTRY_REL, repo / LIVE_ADJ_REL)
    result["inputs_on_disk"] = live_input_presence(repo)
    return result


def verdict_for(result: dict[str, Any]) -> str:
    if not result.get("registry_present"):
        return "NOT-CHECKED"
    if int(result["examined_pair_count"]) == 0:
        return "NOT-CHECKED"
    if int(result["counts"]["open_count"]) > 0:
        return "REFUTED"
    return "CONFIRMED"
