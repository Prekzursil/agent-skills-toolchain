#!/usr/bin/env python3
"""HEAD-tree sweep: git ls-tree + git cat-file -p, then reverse-join the registry.

Detector controls run and must pass BEFORE totals are computed. A file the
forward sweep missed surfaces on the reverse join as a registry row with no
tree match.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from classify import (
    AMBIGUOUS,
    NON_WORKFLOW,
    WORKFLOW,
    classify,
    is_candidate_path,
)
from gitutil import TreeEntry, cat_file_p, ls_tree, rev_parse

PROVENANCE_PREFIX = "git:"


@dataclass
class ControlResult:
    path: str
    expected: str
    got: str
    blob_sha: str
    ok: bool


@dataclass
class Classified:
    path: str
    blob_sha: str
    commit: str
    classification: str
    provenance_ref: str
    in_registry: bool
    bytes: int


@dataclass
class SweepResult:
    head_sha: str
    ls_tree_count: int
    controls: list[ControlResult]
    controls_completed_before_totals: bool
    classified: list[Classified]
    counts: dict[str, int]
    new_candidates: list[dict[str, Any]]
    already_enumerated: list[dict[str, Any]]
    ambiguous: list[dict[str, Any]]
    reverse_join: dict[str, Any]
    used_git_archive: bool = False
    cat_file_reads: int = 0


class DetectorControlFailure(RuntimeError):
    pass


def _record(item: Classified) -> dict[str, Any]:
    return {
        "path": item.path,
        "blob_sha": item.blob_sha,
        "commit": item.commit,
        "provenance_ref": item.provenance_ref,
        "classification": item.classification,
        "in_registry": item.in_registry,
        "bytes": item.bytes,
    }


def provenance_ref(commit: str, path: str) -> str:
    return f"{PROVENANCE_PREFIX}{commit}:{path}"


def provenance_is_commit_anchored(ref: str, commit: str, path: str) -> bool:
    if not isinstance(ref, str) or not ref.startswith(PROVENANCE_PREFIX):
        return False
    rest = ref[len(PROVENANCE_PREFIX) :]
    if ":" not in rest:
        return False
    sha, rel = rest.split(":", 1)
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        return False
    return sha == commit and rel == path


def normalize_registry_path(raw: Any) -> str | None:
    if isinstance(raw, dict):
        raw = raw.get("path") or raw.get("file") or raw.get("relpath") or raw.get("source")
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip().replace("\\", "/")
    for marker in ("/ast-integrate/", "ast-integrate/"):
        if marker in s:
            s = s.split(marker, 1)[-1]
            break
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/") or None


def registry_paths(registry: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Map normalized provenance path -> registry row."""
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(registry, dict):
        return out
    rows = registry.get("candidates")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = normalize_registry_path(row.get("provenance"))
        if not path:
            continue
        out[path] = row
    return out


def sweep_repo(
    repo: Path,
    registry: dict[str, Any] | None,
    controls: list[tuple[str, str]] | None = None,
) -> SweepResult:
    head = rev_parse(repo, "HEAD")
    entries = ls_tree(repo, "HEAD")
    by_path = {e.path: e for e in entries}
    tree_paths = set(by_path)
    cat_reads = 0

    control_results: list[ControlResult] = []
    for path, expected in controls or []:
        entry = by_path.get(path)
        if entry is None:
            control_results.append(
                ControlResult(path=path, expected=expected, got="ABSENT", blob_sha="", ok=False)
            )
            raise DetectorControlFailure(f"control path absent from HEAD tree: {path}")
        blob = cat_file_p(repo, entry.blob_sha)
        cat_reads += 1
        got = classify(path, blob)
        ok = got == expected
        control_results.append(
            ControlResult(path=path, expected=expected, got=got, blob_sha=entry.blob_sha, ok=ok)
        )
        if not ok:
            raise DetectorControlFailure(
                f"detector control failed for {path}: expected {expected} got {got}"
            )

    controls_done = True

    reg_map = registry_paths(registry)
    to_read: dict[str, TreeEntry] = {}
    for entry in entries:
        if is_candidate_path(entry.path) or entry.path in reg_map:
            to_read[entry.path] = entry
    for path, expected in controls or []:
        if path in by_path:
            to_read[path] = by_path[path]

    classified: list[Classified] = []
    for path, entry in sorted(to_read.items()):
        blob = cat_file_p(repo, entry.blob_sha)
        cat_reads += 1
        cls = classify(path, blob)
        classified.append(
            Classified(
                path=path,
                blob_sha=entry.blob_sha,
                commit=head,
                classification=cls,
                provenance_ref=provenance_ref(head, path),
                in_registry=path in reg_map,
                bytes=len(blob),
            )
        )

    new_candidates = [
        _record(c)
        for c in classified
        if c.classification == WORKFLOW and not c.in_registry
    ]
    already = [
        _record(c)
        for c in classified
        if c.classification == WORKFLOW and c.in_registry
    ]
    ambiguous = [_record(c) for c in classified if c.classification == AMBIGUOUS]

    unmatched: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    for path, row in sorted(reg_map.items()):
        rec = {
            "registry_id": row.get("id"),
            "registry_name": row.get("name"),
            "provenance_path": path,
            "tree_match": path in tree_paths,
        }
        if path in tree_paths:
            rec["blob_sha"] = by_path[path].blob_sha
            matched.append(rec)
        else:
            unmatched.append(rec)

    counts = {
        "ls_tree_entries": len(entries),
        "candidates_read_via_cat_file": len(to_read),
        "workflow": sum(1 for c in classified if c.classification == WORKFLOW),
        "non_workflow": sum(1 for c in classified if c.classification == NON_WORKFLOW),
        "ambiguous": len(ambiguous),
        "new_not_in_registry": len(new_candidates),
        "already_enumerated": len(already),
        "registry_without_tree_match": len(unmatched),
        "registry_with_tree_match": len(matched),
    }

    return SweepResult(
        head_sha=head,
        ls_tree_count=len(entries),
        controls=control_results,
        controls_completed_before_totals=controls_done,
        classified=classified,
        counts=counts,
        new_candidates=new_candidates,
        already_enumerated=already,
        ambiguous=ambiguous,
        reverse_join={
            "matched": matched,
            "no_tree_match": unmatched,
            "registry_rows": len(reg_map),
        },
        used_git_archive=False,
        cat_file_reads=cat_reads,
    )
