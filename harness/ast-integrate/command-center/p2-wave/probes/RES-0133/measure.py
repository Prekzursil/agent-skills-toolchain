"""Shared measurement: materialize corpus, scan, score. Never prints secret values."""
from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from corpus import (
    assert_text_has_no_secrets,
    drop_values,
    materialize,
    secret_values,
)
from metric import detection_bits, load_prereg, precision_recall, score_yields
from scan import (
    hit_relpaths,
    run_gitleaks,
    run_github_local,
    run_trufflehog,
    scanner_versions,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def lineage(rel: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "resolved_url": path.resolve().as_uri(),
        "fetch_timestamp": ts,
        "sha256": digest,
        "path": rel,
        "bytes": size,
    }


def _filter(hits: list[dict], prefix: str) -> set[str]:
    return {h["relpath"] for h in hits if str(h.get("relpath") or "").startswith(prefix)}


def run_bundle() -> dict:
    prereg = load_prereg()
    tmp = Path(tempfile.mkdtemp(prefix="res0133-corpus-"))
    index = materialize(tmp, include_controls=True)
    g_hits = run_gitleaks(tmp)
    t_hits = run_trufflehog(tmp)
    h_hits = run_github_local(tmp)

    plants = index["plants"]
    decoys = index["decoys"]
    near = index["near"]
    diverse = index["diverse"]

    g_plant = _filter(g_hits, "plants/")
    t_plant = _filter(t_hits, "plants/")
    h_plant = _filter(h_hits, "plants/")
    union_plant = g_plant | t_plant | h_plant
    agree_plant = g_plant & t_plant

    g_bits = detection_bits(plants, g_plant)
    t_bits = detection_bits(plants, t_plant)
    h_bits = detection_bits(plants, h_plant)
    u_bits = detection_bits(plants, union_plant)
    a_bits = detection_bits(plants, agree_plant)

    g_score = score_yields(g_bits, prereg)
    t_score = score_yields(t_bits, prereg)
    h_score = score_yields(h_bits, prereg)
    u_score = score_yields(u_bits, prereg)
    a_score = score_yields(a_bits, prereg)

    g_pr = precision_recall(plants, decoys, hit_relpaths(g_hits) & (g_plant | _filter(g_hits, "decoys/")))
    # precision_recall should use scanner hits on plants+decoys only
    def pr_for(hits: list[dict]) -> dict:
        rels = _filter(hits, "plants/") | _filter(hits, "decoys/")
        return precision_recall(plants, decoys, rels)

    g_pr = pr_for(g_hits)
    t_pr = pr_for(t_hits)
    h_pr = pr_for(h_hits)
    u_pr = pr_for(
        [{"relpath": r} for r in (_filter(g_hits, "plants/") | _filter(t_hits, "plants/") | _filter(h_hits, "plants/") | _filter(g_hits, "decoys/") | _filter(t_hits, "decoys/") | _filter(h_hits, "decoys/"))]
    )

    def surface_recall(bits_by_rel: set[str]) -> dict:
        out: dict[str, dict] = {}
        for surface in ("markdown-prose", "jsonl-transcript", "fenced-code-block"):
            rows = [p for p in plants if p["surface"] == surface]
            tp = sum(1 for p in rows if p["relpath"] in bits_by_rel)
            out[surface] = {"n": len(rows), "detected": tp, "recall": (tp / len(rows) if rows else 0.0)}
        return out

    def format_recall(bits_by_rel: set[str]) -> list[dict]:
        rows = []
        for fmt in sorted({p["format"] for p in plants}):
            grp = [p for p in plants if p["format"] == fmt]
            tp = sum(1 for p in grp if p["relpath"] in bits_by_rel)
            rows.append({"format": fmt, "n": len(grp), "detected": tp, "recall": tp / len(grp)})
        return rows

    near_g = detection_bits(near, _filter(g_hits, "near/") | _filter(t_hits, "near/") | _filter(h_hits, "near/"))
    # both-states uses UNION of scanners on near (format-valid) vs diverse
    near_union = _filter(g_hits, "near/") | _filter(t_hits, "near/") | _filter(h_hits, "near/")
    div_union = _filter(g_hits, "diverse/") | _filter(t_hits, "diverse/") | _filter(h_hits, "diverse/")
    near_bits = detection_bits(near, near_union)
    div_bits = detection_bits(diverse, div_union)
    near_score = score_yields(near_bits, prereg)
    div_score = score_yields(div_bits, prereg)

    public_index = drop_values(index)
    bundle = {
        "tmp": str(tmp),
        "index": public_index,
        "secret_index": index,
        "versions": scanner_versions(),
        "prereg": prereg,
        "scanners": {
            "gitleaks": {"score": g_score, "precision_recall": g_pr, "by_surface": surface_recall(g_plant), "by_format": format_recall(g_plant)},
            "trufflehog": {"score": t_score, "precision_recall": t_pr, "by_surface": surface_recall(t_plant), "by_format": format_recall(t_plant)},
            "github_docs_local": {"score": h_score, "precision_recall": h_pr, "by_surface": surface_recall(h_plant), "by_format": format_recall(h_plant)},
            "union": {"score": u_score, "precision_recall": u_pr, "by_surface": surface_recall(union_plant), "by_format": format_recall(union_plant)},
            "gitleaks_and_trufflehog": {"score": a_score},
        },
        "negative_controls": {
            "near_identical": near_score,
            "diverse": div_score,
        },
        "hit_counts": {
            "gitleaks_plants": len(g_plant),
            "trufflehog_plants": len(t_plant),
            "github_docs_local_plants": len(h_plant),
            "union_plants": len(union_plant),
            "gitleaks_decoys": len(_filter(g_hits, "decoys/")),
            "trufflehog_decoys": len(_filter(t_hits, "decoys/")),
            "github_docs_local_decoys": len(_filter(h_hits, "decoys/")),
        },
    }
    return bundle


def historical_replays(bundle: dict) -> list[dict]:
    gen = "command-center/p2-wave/probes/RES-0133/corpus.py"
    lin = lineage(gen)
    rows = []
    mapping = [
        ("gitleaks-filesystem", "gitleaks"),
        ("trufflehog-filesystem-no-verification", "trufflehog"),
        ("github-docs-local-prefix-regex", "github_docs_local"),
        ("union-three-scanners", "union"),
        ("gitleaks-and-trufflehog-agreement", "gitleaks_and_trufflehog"),
    ]
    for run_id, key in mapping:
        sc = bundle["scanners"][key]["score"]
        rows.append(
            {
                "run_id": run_id,
                "path": gen,
                "resolved_url": lin["resolved_url"],
                "fetch_timestamp": lin["fetch_timestamp"],
                "sha256": lin["sha256"],
                "file_sha256": lin["sha256"],
                "n_sources": sc["n_sources"],
                "fired": sc["fired"],
                "fire_index": sc["fire_index"],
                "yields": sc["yields"],
                "miss_count": sc["miss_count"],
                "miss_rate": sc["miss_rate"],
                "recall": sc["recall"],
                "scanner": key,
            }
        )
    return rows
