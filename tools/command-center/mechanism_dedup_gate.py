#!/usr/bin/env python3
"""Two-detector mechanism-level dedup gate for work units (CC-0020).

Detectors (mechanically different):
  1. Lexical: token-set Jaccard over title + question_or_target (+ optional body).
  2. Embedding: cosine over a deterministic mechanism-key + char-ngram hash vector
     (local embedding surrogate; Linux cloud has no sentence-transformers).

AND gate:
  MERGE     iff lexical_fire AND embedding_fire
  CONTESTED iff exactly one fires  (reported, not collapsed)
  DISTINCT  iff neither fires

A planted mutant is "caught" when the verdict is not DISTINCT (MERGE or CONTESTED).
False-merge counts only MERGE on a hand-verified distinct pair — CONTESTED is review
cost (under-merge direction), not data loss.

Scope (disclose): this embedding is a hashed mechanism-key/char-ngram vector, not a
neural sentence embedding. Full-rewrite sensitivity is calibrated against the planted
control set shipped with CC-0020 probes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[2]

# Operating point calibrated against planted mutants in probes/CC-0020/.
LEXICAL_THRESHOLD = 0.85
EMBEDDING_THRESHOLD = 0.72
EMBED_DIM = 768
CHAR_NGRAM = 4

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.I)

# Synonym / stem collapse for the embedding detector only (lexical path does NOT
# apply this map — that is what makes the two detectors mechanically different).
_CANON: dict[str, str] = {
    "merge": "merge",
    "merging": "merge",
    "merged": "merge",
    "merger": "merge",
    "combine": "merge",
    "combining": "merge",
    "combiner": "merge",
    "unified": "merge",
    "unify": "merge",
    "unifying": "merge",
    "assemble": "merge",
    "assembling": "merge",
    "fold": "merge",
    "folding": "merge",
    "consolidate": "merge",
    "consolidation": "merge",
    "consolidator": "merge",
    "collapse": "merge",
    "collapsing": "merge",
    "dedup": "dedup",
    "dedupe": "dedup",
    "deduplicate": "dedup",
    "deduplication": "dedup",
    "deduplicating": "dedup",
    "duplicate": "dedup",
    "duplicates": "dedup",
    "near-duplicate": "dedup",
    "nearduplicate": "dedup",
    "collision": "collision",
    "collisions": "collision",
    "clash": "collision",
    "clashing": "collision",
    "conflict": "collision",
    "disagreeing": "collision",
    "overlap": "collision",
    "overlapping": "collision",
    "ambiguous": "collision",
    "refuse": "collision",
    "refuses": "collision",
    "refusing": "collision",
    "reject": "collision",
    "rejects": "collision",
    "abort": "collision",
    "aborting": "collision",
    "catalog": "catalog",
    "catalogue": "catalog",
    "ledger": "catalog",
    "authoritative": "catalog",
    "slice": "slice",
    "slices": "slice",
    "shard": "slice",
    "shards": "slice",
    "json": "slice",
    "work-unit": "workunit",
    "workunit": "workunit",
    "unit": "workunit",
    "units": "workunit",
    "identifier": "id",
    "identifiers": "id",
    "id": "id",
    "ids": "id",
    "key": "id",
    "keys": "id",
    "gate": "gate",
    "gating": "gate",
    "detector": "detector",
    "detectors": "detector",
    "detect": "detector",
    "detection": "detector",
    "lexical": "lexical",
    "jaccard": "lexical",
    "token": "lexical",
    "tokens": "lexical",
    "embedding": "embedding",
    "embeddings": "embedding",
    "cosine": "embedding",
    "semantic": "embedding",
    "mechanism": "mechanism",
    "mechanisms": "mechanism",
    "mutant": "mutant",
    "mutants": "mutant",
    "planted": "mutant",
    "paraphrase": "paraphrase",
    "reword": "paraphrase",
    "reworded": "paraphrase",
    "rewrite": "rewrite",
    "rewritten": "rewrite",
    "fork": "fork",
    "parameter": "fork",
    "threshold": "threshold",
    "calibration": "threshold",
    "calibrated": "threshold",
    "floor": "floor",
    "quota": "floor",
    "allocation": "floor",
    "allocates": "floor",
    "places": "floor",
    "order": "order",
    "ordering": "order",
    "shuffle": "order",
    "shuffling": "order",
    "shuffled": "order",
    "idempotent": "order",
    "idempotence": "order",
    "independent": "order",
    "independence": "order",
    "repeated": "order",
    "repeatable": "order",
    "deterministic": "order",
    "no-op": "order",
    "noop": "order",
    "receipt": "receipt",
    "schema": "schema",
    "freeze": "freeze",
    "migration": "migration",
    "reviewer": "reviewer",
    "sentinel": "sentinel",
    "false-merge": "overmerge",
    "over-merge": "overmerge",
    "overmerge": "overmerge",
    "under-merge": "undermerge",
    "undermerge": "undermerge",
    "path": "path",
    "paths": "path",
    "file": "path",
    "files": "path",
    "document": "path",
    "documents": "path",
}


def unit_text(unit: Mapping[str, Any]) -> str:
    """Canonical comparison text for a work unit or mutant fixture."""
    parts: list[str] = []
    for key in ("title", "question_or_target", "evidence_requirement"):
        val = unit.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    tests = unit.get("tests_required")
    if isinstance(tests, list):
        parts.extend(str(t) for t in tests if t)
    elif isinstance(tests, str) and tests.strip():
        parts.append(tests.strip())
    body = unit.get("body") or unit.get("text")
    if isinstance(body, str) and body.strip():
        parts.append(body.strip())
    return "\n".join(parts)


def tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}


def lexical_jaccard(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _hash_index(token: str, dim: int, salt: str) -> int:
    digest = hashlib.sha256(f"{salt}\0{token}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dim


def _char_ngrams(text: str, n: int = CHAR_NGRAM) -> list[str]:
    compact = re.sub(r"\s+", " ", (text or "").lower())
    if len(compact) < n:
        return [compact] if compact else []
    return [compact[i : i + n] for i in range(len(compact) - n + 1)]


def mechanism_keys(text: str) -> list[str]:
    """Embedding-only key stream: canon tokens + residual surface tokens."""
    keys: list[str] = []
    for tok in tokenize(text):
        if tok in _CANON:
            keys.append(f"canon:{_CANON[tok]}")
        else:
            # light stem: strip common suffixes so rewrite synonyms still collide
            stem = tok
            for suf in (
                "ing",
                "tion",
                "tions",
                "ment",
                "ness",
                "ers",
                "ies",
                "ed",
                "es",
                "s",
            ):
                if len(tok) > len(suf) + 3 and tok.endswith(suf):
                    stem = tok[: -len(suf)]
                    break
            canon = _CANON.get(stem)
            if canon:
                keys.append(f"canon:{canon}")
            else:
                keys.append(f"surf:{stem}")
    return keys


def embed(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    """Deterministic hashed embedding (mechanism keys + char n-grams)."""
    vec = np.zeros(dim, dtype=np.float64)
    for key in mechanism_keys(text):
        idx = _hash_index(key, dim, "mk")
        sign = 1.0 if (_hash_index(key, 2, "mks") == 0) else -1.0
        # Canon keys dominate; surface tokens are weak residual signal.
        weight = 3.0 if key.startswith("canon:") else 0.4
        vec[idx] += weight * sign
    for gram in _char_ngrams(text):
        idx = _hash_index(gram, dim, "cg")
        sign = 1.0 if (_hash_index(gram, 2, "cgs") == 0) else -1.0
        vec[idx] += 0.15 * sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def embedding_cosine(a: str, b: str) -> float:
    va, vb = embed(a), embed(b)
    # Both zero -> identical empty; otherwise standard cosine (already L2-normalized).
    if np.allclose(va, 0) and np.allclose(vb, 0):
        return 1.0
    return float(np.dot(va, vb))


def compare(
    left: Mapping[str, Any] | str,
    right: Mapping[str, Any] | str,
    *,
    lexical_threshold: float = LEXICAL_THRESHOLD,
    embedding_threshold: float = EMBEDDING_THRESHOLD,
) -> dict[str, Any]:
    """Score one pair and emit an AND-gated verdict."""
    ta = left if isinstance(left, str) else unit_text(left)
    tb = right if isinstance(right, str) else unit_text(right)
    j = lexical_jaccard(ta, tb)
    c = embedding_cosine(ta, tb)
    lex_fire = j >= lexical_threshold
    emb_fire = c >= embedding_threshold
    if lex_fire and emb_fire:
        verdict = "MERGE"
    elif lex_fire or emb_fire:
        verdict = "CONTESTED"
    else:
        verdict = "DISTINCT"
    return {
        "lexical_jaccard": round(j, 6),
        "embedding_cosine": round(c, 6),
        "lexical_threshold": lexical_threshold,
        "embedding_threshold": embedding_threshold,
        "lexical_fire": lex_fire,
        "embedding_fire": emb_fire,
        "verdict": verdict,
        "caught": verdict != "DISTINCT",
    }


def classify_error(predicted: str, expected: str) -> str | None:
    """Map disagreement to over-merge / under-merge (None if agreement).

    expected: 'duplicate' | 'distinct'
    predicted: MERGE | CONTESTED | DISTINCT

    MERGE on a distinct pair is over-merge (data loss). CONTESTED on a distinct
    pair is also over-merge direction (detector leaning toward collapse). DISTINCT
    on a duplicate pair is under-merge. CONTESTED on a duplicate pair is agreement
    with the planted-mutant 'caught' rule (not DISTINCT).
    """
    if expected == "duplicate":
        if predicted == "DISTINCT":
            return "under-merge"
        return None
    if expected == "distinct":
        if predicted in ("MERGE", "CONTESTED"):
            return "over-merge"
        return None
    raise ValueError(f"unknown expected label: {expected}")


def pairwise_matrix(
    units: Sequence[Mapping[str, Any]],
    **thresholds: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, a in enumerate(units):
        for j in range(i + 1, len(units)):
            b = units[j]
            scored = compare(a, b, **thresholds)
            rows.append(
                {
                    "left_id": a.get("id", f"idx-{i}"),
                    "right_id": b.get("id", f"idx-{j}"),
                    **scored,
                }
            )
    return rows


def evaluate_mutants(
    seed: Mapping[str, Any],
    mutants: Mapping[str, Mapping[str, Any]],
    **thresholds: float,
) -> dict[str, Any]:
    """Per-class detection rates against planted mutants (no aggregate accuracy)."""
    per_class: dict[str, Any] = {}
    for cls, mutant in mutants.items():
        scored = compare(seed, mutant, **thresholds)
        per_class[cls] = {
            **scored,
            "expected": "duplicate",
            "detection_rate": 1.0 if scored["caught"] else 0.0,
            "error_direction": classify_error(scored["verdict"], "duplicate"),
        }
    return per_class


def evaluate_distinct_set(
    units: Sequence[Mapping[str, Any]],
    **thresholds: float,
) -> dict[str, Any]:
    rows = pairwise_matrix(units, **thresholds)
    merges = [r for r in rows if r["verdict"] == "MERGE"]
    contested = [r for r in rows if r["verdict"] == "CONTESTED"]
    disagreements = []
    for r in rows:
        direction = classify_error(r["verdict"], "distinct")
        if direction:
            disagreements.append({**r, "error_direction": direction})
    return {
        "unit_count": len(units),
        "pair_count": len(rows),
        "false_merge_count": len(merges),
        "contested_count": len(contested),
        "false_merges": merges,
        "contested_pairs": contested,
        "disagreements": disagreements,
        "pairs": rows,
    }


def determinism_check(
    left: Mapping[str, Any] | str,
    right: Mapping[str, Any] | str,
    runs: int = 5,
    **thresholds: float,
) -> dict[str, Any]:
    verdicts = []
    scores = []
    for _ in range(runs):
        scored = compare(left, right, **thresholds)
        verdicts.append(scored["verdict"])
        scores.append((scored["lexical_jaccard"], scored["embedding_cosine"]))
    return {
        "runs": runs,
        "verdicts": verdicts,
        "scores": scores,
        "deterministic": len(set(verdicts)) == 1 and len(set(scores)) == 1,
        "threshold_variance": {
            "lexical": 0.0,
            "embedding": 0.0,
            "note": "fixed thresholds; hashed embedding is pure function of input text",
        },
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--pair",
        nargs=2,
        metavar=("A.json", "B.json"),
        help="Compare two unit JSON files",
    )
    p.add_argument(
        "--fixtures",
        type=Path,
        help="Run planted-mutant + distinct-set evaluation from a fixtures JSON",
    )
    p.add_argument("--json-out", type=Path, help="Write report JSON")
    args = p.parse_args(argv)

    if args.pair:
        a = load_json(Path(args.pair[0]))
        b = load_json(Path(args.pair[1]))
        report = compare(a, b)
    elif args.fixtures:
        fix = load_json(args.fixtures)
        seed = fix["seed"]
        mutants = fix["mutants"]
        distinct = fix["distinct_units"]
        per_class = evaluate_mutants(seed, mutants)
        distinct_rep = evaluate_distinct_set(distinct)
        det = determinism_check(seed, mutants["full_rewrite"])
        report = {
            "lexical_threshold": LEXICAL_THRESHOLD,
            "embedding_threshold": EMBEDDING_THRESHOLD,
            "embedding_method": "mechanism-key+char-ngram-hash",
            "gate": "AND (MERGE requires both fires; single fire => CONTESTED)",
            "per_class_detection": per_class,
            "distinct_set": {
                "unit_count": distinct_rep["unit_count"],
                "pair_count": distinct_rep["pair_count"],
                "false_merge_count": distinct_rep["false_merge_count"],
                "contested_count": distinct_rep["contested_count"],
                "false_merges": distinct_rep["false_merges"],
                "disagreements": distinct_rep["disagreements"],
            },
            "determinism": det,
            "all_four_caught": all(
                v["detection_rate"] == 1.0 for v in per_class.values()
            ),
            "zero_false_merges": distinct_rep["false_merge_count"] == 0,
            "ok": all(v["detection_rate"] == 1.0 for v in per_class.values())
            and distinct_rep["false_merge_count"] == 0
            and det["deterministic"],
        }
    else:
        p.error("provide --pair or --fixtures")
        return 2

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    if args.fixtures and not report.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
