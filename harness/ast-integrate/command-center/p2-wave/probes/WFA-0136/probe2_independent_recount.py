#!/usr/bin/env python3
"""Probe 2: independent pairwise recount vs the foundry artifact.

Re-derives IDF, cosine, and Jaccard from catalog.py + detector.py and
compares pair counts and planted scores to the artifact. Cosine is
recomputed with an intersect-keys loop that does not call scan.cosine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import detector as D  # noqa: E402
import planted as P  # noqa: E402

ART = (
    REPO
    / "command-center/foundry"
    / "WFA-0136-semantic-non-duplication-proof-for-the-96-entry-blue.json"
)


def cosine_intersect(u: dict[str, float], v: dict[str, float]) -> float:
    """Independent cosine: sum over key intersection, not the shorter-dict walk."""
    keys = set(u).intersection(v)
    return sum(u[k] * v[k] for k in keys)


def as_float(obj: dict, key: str) -> float:
    if key not in obj or obj[key] is None:
        raise KeyError(key)
    return float(obj[key])


def domain(doc: dict) -> dict:
    """Prefer report payload when the artifact is a receipt_core envelope."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "distinctness-proof" or "n_entries" in report
    ):
        return report
    return doc


def evidence_rows(doc: dict, payload: dict) -> list[dict]:
    rows = payload.get("evidence_anchors")
    if isinstance(rows, list) and len(rows) >= 2:
        return [r for r in rows if isinstance(r, dict)]
    out = []
    for row in doc.get("evidence") or []:
        if not isinstance(row, dict):
            continue
        if row.get("path"):
            out.append(row)
            continue
        anchor = str(row.get("anchor") or "")
        if ":" not in anchor:
            continue
        rel, _, rest = anchor.rpartition(":")
        try:
            line = int(rest)
        except ValueError:
            continue
        out.append(
            {
                "path": rel,
                "line": line,
                "snippet": str(row.get("snippet") or ""),
                "mechanism": str(row.get("mechanism") or ""),
            }
        )
    return out


def resolve_anchor(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"{rel}:{line} out of range n={len(lines)}"
    got = lines[line - 1]
    if snippet and snippet not in got:
        return False, f"{rel}:{line} snippet mismatch: {got[:80]!r}"
    return True, f"{rel}:{line}"


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0136-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:WFA-0136-probe2 unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:WFA-0136-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0136" not in text:
        print("FAILED:WFA-0136-probe2 sentinel absent")
        return 1

    payload = domain(doc)
    entries = C.load_entries(REPO)
    if len(entries) < C.FLOOR:
        print(f"FAILED:WFA-0136-probe2 n_entries {len(entries)} < floor {C.FLOOR}")
        return 1
    if int(payload.get("n_entries") or 0) != len(entries):
        print(
            "FAILED:WFA-0136-probe2 n_entries mismatch "
            f"artifact={payload.get('n_entries')} live={len(entries)}"
        )
        return 1
    expected_pairs = len(entries) * (len(entries) - 1) // 2
    if int(payload.get("n_pairs") or 0) != expected_pairs:
        print(
            "FAILED:WFA-0136-probe2 n_pairs mismatch "
            f"artifact={payload.get('n_pairs')} live={expected_pairs}"
        )
        return 1

    by_id = {e["id"]: e for e in entries}
    anchor = by_id[P.ANCHOR_ID]
    para, dist = P.plants_from_anchor(anchor)
    n_docs = len(entries)
    idf = D.fit_idf(C.prose_of(e) for e in entries)

    def score(a: dict, b: dict) -> tuple[float, float]:
        pa, pb = C.prose_of(a), C.prose_of(b)
        jac = D.jaccard(pa, pb)
        ea = D.embed(pa, str(a.get("mechanism") or ""), idf, n_docs)
        eb = D.embed(pb, str(b.get("mechanism") or ""), idf, n_docs)
        return jac, cosine_intersect(ea, eb)

    p_jac, p_cos = score(anchor, para)
    d_jac, d_cos = score(anchor, dist)
    planted = payload.get("planted_mutant_control") or {}
    art_p = planted.get("paraphrase") or {}
    art_d = planted.get("distinct") or {}
    if abs(as_float(art_p, "cosine") - p_cos) > 1e-6:
        print("FAILED:WFA-0136-probe2 paraphrase cosine disagreement")
        return 1
    if abs(as_float(art_d, "cosine") - d_cos) > 1e-6:
        print("FAILED:WFA-0136-probe2 distinct cosine disagreement")
        return 1
    if abs(as_float(art_p, "jaccard") - p_jac) > 1e-6:
        print("FAILED:WFA-0136-probe2 paraphrase jaccard disagreement")
        return 1
    if abs(as_float(art_d, "jaccard") - d_jac) > 1e-6:
        print("FAILED:WFA-0136-probe2 distinct jaccard disagreement")
        return 1

    cos_th = float(payload.get("cosine_threshold") or -1)
    jac_th = float(payload.get("jaccard_threshold") or -1)
    if not D.semantic_flag(p_cos, cos_th) or D.semantic_flag(d_cos, cos_th):
        print("FAILED:WFA-0136-probe2 planted flags do not match thresholds")
        return 1

    live_near = []
    max_cos = 0.0
    max_jac = 0.0
    n_sem = 0
    n_lex = 0
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            jac, cos = score(a, b)
            max_cos = max(max_cos, cos)
            max_jac = max(max_jac, jac)
            lex = D.lexical_flag(jac, jac_th)
            sem = D.semantic_flag(cos, cos_th)
            n_lex += int(lex)
            n_sem += int(sem)
            if sem and not lex:
                live_near.append((a["id"], b["id"]))
    live_near.sort()
    art_near = sorted(
        (str(r.get("a")), str(r.get("b")))
        for r in (payload.get("cosine_near_jaccard_distinct") or [])
    )
    if live_near != art_near:
        print("FAILED:WFA-0136-probe2 cosine-near/Jaccard-distinct set disagreement")
        print("live", live_near[:12], "artifact", art_near[:12])
        return 1
    if abs(as_float(payload, "max_cosine") - max_cos) > 1e-6:
        print("FAILED:WFA-0136-probe2 max_cosine disagreement")
        return 1
    if abs(as_float(payload, "max_jaccard") - max_jac) > 1e-6:
        print("FAILED:WFA-0136-probe2 max_jaccard disagreement")
        return 1

    for row in payload.get("survivors") or []:
        if row.get("mechanism_difference_named") is not True:
            print(
                "FAILED:WFA-0136-probe2 survivor lacks mechanism-difference "
                f"{row.get('a')}/{row.get('b')}"
            )
            return 1

    evidence = evidence_rows(doc, payload)
    if len(evidence) < 2:
        print("FAILED:WFA-0136-probe2 need >=2 evidence anchors")
        return 1
    mechs = set()
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        ok, why = resolve_anchor(rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:WFA-0136-probe2 unresolved anchor")
            return 1
        mechs.add(str(row.get("mechanism") or ""))
    if "token-jaccard" not in mechs or "embedding-cosine" not in mechs:
        print(f"FAILED:WFA-0136-probe2 evidence mechanisms {sorted(mechs)}")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-independent-recount",
                "unit_id": "WFA-0136",
                "n_entries": len(entries),
                "n_pairs": expected_pairs,
                "max_cosine": max_cos,
                "max_jaccard": max_jac,
                "n_lexical_flags": n_lex,
                "n_semantic_flags": n_sem,
                "n_cosine_near_jaccard_distinct": len(live_near),
                "paraphrase_cosine": p_cos,
                "distinct_cosine": d_cos,
                "pass": True,
            },
            indent=2,
        )
    )
    print(
        f"recount n={len(entries)} pairs={expected_pairs} "
        f"near={len(live_near)} max_cos={max_cos:.4f} max_jac={max_jac:.4f}"
    )
    print("SUCCESS:WFA-0136-probe2 independent recount matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
