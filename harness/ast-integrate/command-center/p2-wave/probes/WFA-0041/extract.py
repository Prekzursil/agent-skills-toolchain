"""Extract benchmark-evidence rows from candidate and blueprint documents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from classify import classify_row
from run_records import digest_file
from sources import (
    REPO,
    find_blueprint_library,
    find_registry_shaped,
    load_json,
    looks_like_candidate_registry,
    source_probe,
)

HERE = Path(__file__).resolve().parent

LIVE_BLUEPRINT_RELS = (
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0014/fixtures/live/workflows/wf.catalog-class.discovery-only.json",
    "command-center/p2-wave/probes/ARC-0014/fixtures/generated/workflows/wf.catalog-class.discovery-only.json",
    "command-center/p2-wave/probes/ARC-0014/fixtures/deploy/workflows/wf.catalog-class.discovery-only.json",
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/hatch/workflows/wf.catalog-class.discovery-only.json",
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/workflows/wf.catalog-class.discovery-only.json",
)


def _candidates_from(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "records", "entries"):
        rows = doc.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _blueprints_from(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    if doc.get("kind") == "workflow_blueprint" or "bench" in doc:
        return [doc]
    out: list[dict[str, Any]] = []
    for key in ("blueprints", "records", "workflows", "entries"):
        rows = doc.get(key)
        if isinstance(rows, list):
            for r in rows:
                if not isinstance(r, dict):
                    continue
                if r.get("kind") == "workflow_blueprint" or "bench" in r:
                    out.append(r)
    return out


def row_from_candidate(
    rec: dict[str, Any], *, origin: str, roots: list[Path]
) -> dict[str, Any]:
    cid = str(rec.get("id") or rec.get("candidate_id") or rec.get("name") or "")
    return classify_row(
        candidate_id=cid or "UNKNOWN",
        evidence=rec.get("evidence"),
        bench=rec.get("bench"),
        roots=roots,
        extra={
            "family": rec.get("family"),
            "discovery_only": rec.get("discovery_only"),
            "origin": origin,
            "role": "candidate",
        },
    )


def row_from_blueprint(
    rec: dict[str, Any], *, origin: str, roots: list[Path]
) -> dict[str, Any]:
    cid = str(rec.get("id") or rec.get("name") or "")
    return classify_row(
        candidate_id=cid or "UNKNOWN",
        evidence=rec.get("evidence"),
        bench=rec.get("bench"),
        roots=roots,
        extra={
            "discovery_only": rec.get("discovery_only"),
            "origin": origin,
            "role": "blueprint",
        },
    )


def extract_document(
    doc: Any, *, origin: str, roots: list[Path], kind: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if kind == "registry" or looks_like_candidate_registry(doc):
        for rec in _candidates_from(doc):
            rows.append(row_from_candidate(rec, origin=origin, roots=roots))
        return rows
    for rec in _blueprints_from(doc):
        rows.append(row_from_blueprint(rec, origin=origin, roots=roots))
    return rows


def load_fixture_corpus(corpus_dir: Path | None = None) -> dict[str, Any]:
    """Both-states fixture corpus used by probes; never mixed into live rows."""
    root = corpus_dir or (HERE / "fixtures" / "corpus")
    run_root = HERE / "fixtures"
    roots = [REPO, HERE, run_root, root]
    rows = []
    for path in sorted(root.glob("*.json")):
        doc = load_json(path)
        rec = doc if isinstance(doc, dict) else {}
        origin = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
        rows.append(
            row_from_candidate(
                rec,
                origin=origin,
                roots=roots,
            )
        )
    return {"rows": rows, "corpus": str(root)}


def live_extract(repo: Path = REPO) -> dict[str, Any]:
    from expectation import CATALOG_EXPECTED_N, NEAR_ZERO_CEILING, NEAR_ZERO_EXPECTED

    registry_path = find_registry_shaped(repo)
    blueprint_path = find_blueprint_library(repo)
    roots = [repo, HERE]
    rows: list[dict[str, Any]] = []
    catalog_rows = 0
    if registry_path is not None:
        doc = load_json(registry_path)
        origin = _rel(registry_path)
        got = extract_document(doc, origin=origin, roots=roots, kind="registry")
        rows.extend(got)
        catalog_rows = len(got)
    blueprint_rows = 0
    if blueprint_path is not None:
        doc = load_json(blueprint_path)
        origin = _rel(blueprint_path)
        got = extract_document(doc, origin=origin, roots=roots, kind="library")
        rows.extend(got)
        blueprint_rows = len(got)

    supplementary: list[dict[str, Any]] = []
    seen_ids: set[str] = {r["id"] for r in rows}
    for rel in LIVE_BLUEPRINT_RELS:
        path = repo / rel
        if not path.is_file():
            continue
        doc = load_json(path)
        got = extract_document(doc, origin=rel, roots=roots, kind="library")
        for row in got:
            if row["id"] in seen_ids:
                continue
            seen_ids.add(row["id"])
            row["origin_class"] = "worktree-live-supplement"
            supplementary.append(row)
    live_rows = rows + supplementary
    counts = _counts(live_rows)
    catalog_counts = _counts(rows)
    return {
        "registry": source_probe(registry_path),
        "blueprint_library": source_probe(blueprint_path),
        "catalog_expected_n": CATALOG_EXPECTED_N,
        "catalog_rows_loaded": catalog_rows,
        "blueprint_rows_loaded": blueprint_rows,
        "supplementary_rows_loaded": len(supplementary),
        "near_zero_expected": NEAR_ZERO_EXPECTED,
        "near_zero_ceiling": NEAR_ZERO_CEILING,
        "counts": counts,
        "catalog_source_counts": catalog_counts,
        "rows": live_rows,
        "catalog_source_rows": rows,
        "supplementary_rows": supplementary,
    }


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {"CITABLE": 0, "CLAIMED-NOT-FOUND": 0, "HONEST-NULL": 0, "total": len(rows)}
    for row in rows:
        st = str(row.get("status") or "")
        if st in out:
            out[st] += 1
    return out


def file_digest(path: Path) -> str:
    return digest_file(path)
