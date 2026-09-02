"""Two independent reviewers plus a constant-verdict strawman."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from taxonomy import (
    EXEMPLARS,
    STABILITY_CLASS_IDS,
    VERDICTS,
    classify_body,
    classify_path,
    load_text,
    snippet_at,
    verdict_for,
)


def cohen_kappa(a: list[str], b: list[str], labels: tuple[str, ...] = VERDICTS) -> dict:
    if len(a) != len(b) or not a:
        raise ValueError("rater length")
    n = len(a)
    agree = sum(1 for x, y in zip(a, b) if x == y)
    po = agree / n
    ca = Counter(a)
    cb = Counter(b)
    pe = 0.0
    for lab in labels:
        pe += (ca[lab] / n) * (cb[lab] / n)
    if math.isclose(pe, 1.0):
        kappa = 1.0 if math.isclose(po, 1.0) else 0.0
    else:
        kappa = (po - pe) / (1.0 - pe)
    return {
        "n": n,
        "po": po,
        "pe": pe,
        "kappa": kappa,
        "agreements": agree,
        "method": "pairwise-marginals-four-verdicts",
        "labels": list(labels),
    }


def load_exemplars(repo: Path) -> list[dict]:
    rows = []
    for i, spec in enumerate(EXEMPLARS, 1):
        rel = spec["path"]
        text, line = load_text(repo, rel)
        rows.append(
            {
                "row_id": f"R{i:02d}",
                "class_id": spec["class_id"],
                "path": rel,
                "line": line,
                "snippet": snippet_at(text, line),
                "text": text,
            }
        )
    if len(rows) != 10:
        raise RuntimeError(f"expected 10 exemplars, got {len(rows)}")
    if [r["class_id"] for r in rows] != list(STABILITY_CLASS_IDS):
        raise RuntimeError("exemplar class_id order drifted from STABILITY_CLASS_IDS")
    return rows


def reviewer_a_path(row: dict) -> dict:
    cid = classify_path(row["path"])
    if cid is None:
        return {"reviewer": "A-path", "class_id": None, "verdict": None}
    return {
        "reviewer": "A-path",
        "class_id": cid,
        "verdict": verdict_for(cid),
        "source_probe": "classify_path",
    }


def reviewer_b_body(row: dict) -> dict:
    cid = classify_body(row["text"])
    if cid is None:
        return {"reviewer": "B-body", "class_id": None, "verdict": None}
    return {
        "reviewer": "B-body",
        "class_id": cid,
        "verdict": verdict_for(cid),
        "verifier_probe": "classify_body",
    }


def reviewer_naive_constant(row: dict) -> dict:
    return {
        "reviewer": "naive-always-REDISTRIBUTABLE",
        "class_id": row["class_id"],
        "verdict": "REDISTRIBUTABLE",
    }


def adjudicate(repo: Path) -> dict:
    rows = load_exemplars(repo)
    a_verdicts = []
    b_verdicts = []
    naive_verdicts = []
    table = []
    for row in rows:
        a = reviewer_a_path(row)
        b = reviewer_b_body(row)
        naive = reviewer_naive_constant(row)
        a_verdicts.append(a["verdict"])
        b_verdicts.append(b["verdict"])
        naive_verdicts.append(naive["verdict"])
        table.append(
            {
                "row_id": row["row_id"],
                "path": row["path"],
                "line": row["line"],
                "snippet": row["snippet"],
                "intended_class": row["class_id"],
                "reviewer_a": a,
                "reviewer_b": b,
                "agree": a["verdict"] is not None
                and a["verdict"] == b["verdict"],
            }
        )
    if any(v is None for v in a_verdicts + b_verdicts):
        missing = [
            t["row_id"]
            for t in table
            if t["reviewer_a"]["verdict"] is None or t["reviewer_b"]["verdict"] is None
        ]
        raise RuntimeError(f"reviewer produced no verdict: {missing}")
    live = cohen_kappa(a_verdicts, b_verdicts)
    naive = cohen_kappa(a_verdicts, naive_verdicts)
    agree_n = sum(1 for t in table if t["agree"])
    return {
        "rows": table,
        "reviewer_a_verdicts": a_verdicts,
        "reviewer_b_verdicts": b_verdicts,
        "naive_verdicts": naive_verdicts,
        "agreement_rate": agree_n / len(table),
        "agreements": agree_n,
        "n": len(table),
        "kappa_live": live,
        "kappa_naive": naive,
        "naive_agreement_rate": sum(
            1 for x, y in zip(a_verdicts, naive_verdicts) if x == y
        )
        / len(table),
        "source_probe": "classify_path",
        "verifier_probe": "classify_body",
    }
