#!/usr/bin/env python3
"""Live mutation controls for REL-0009. Shared by emit and named probes."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "release"))
sys.path.insert(0, str(HERE))

from archive_gate import evaluate_archive, load_policy  # noqa: E402
from scenario import (  # noqa: E402
    BLOB_ARCNAME,
    BLOB_SIZE,
    GITIGNORED_NAME,
    gitignore_walk,
    pack_blob,
    pack_clean,
    pack_dotgit,
    pack_gitignored,
)


def _policy():
    return load_policy(REPO / "tools/release/payload-allowlist.json")


def control_clean(work: Path) -> dict:
    archive = pack_clean(work / "clean.zip", work)
    result = evaluate_archive(archive, _policy())
    d = result.to_dict()
    d["archive"] = str(archive)
    if not result.ok:
        raise AssertionError(f"clean archive rejected: {d}")
    if result.byte_headroom <= 0 or result.file_count_headroom <= 0:
        raise AssertionError(f"clean archive has no headroom: {d}")
    if result.entry_count < 1 or result.total_bytes < 1:
        raise AssertionError(f"clean archive empty listing: {d}")
    return d


def control_dotgit(work: Path) -> dict:
    archive = pack_dotgit(work / "dotgit.zip", work)
    result = evaluate_archive(archive, _policy())
    d = result.to_dict()
    d["archive"] = str(archive)
    if result.ok:
        raise AssertionError("dotgit plant was accepted")
    paths = {v["path"] for v in result.allowlist_violations}
    if not any(p == ".git/HEAD" or p.startswith(".git/") for p in paths):
        raise AssertionError(f"allowlist did not name .git member: {paths}")
    return d


def control_blob(work: Path) -> dict:
    archive = pack_blob(work / "blob.zip", work)
    result = evaluate_archive(archive, _policy())
    d = result.to_dict()
    d["archive"] = str(archive)
    hits = [h for h in result.ceiling_hits if h.get("reason") == "byte-ceiling"]
    if result.ok or not hits:
        raise AssertionError(f"200MiB blob did not fire byte ceiling: {d}")
    hit = hits[0]
    if hit.get("offending_entry") != BLOB_ARCNAME:
        raise AssertionError(f"byte ceiling did not name {BLOB_ARCNAME}: {hit}")
    if int(hit.get("offending_entry_bytes") or 0) != BLOB_SIZE:
        raise AssertionError(f"named entry size mismatch: {hit}")
    if result.total_bytes < BLOB_SIZE:
        raise AssertionError("archive listing total smaller than planted blob")
    return d


def control_gitignored(work: Path) -> dict:
    archive, tree = pack_gitignored(work / "gitignored.zip", work)
    result = evaluate_archive(archive, _policy())
    d = result.to_dict()
    d["archive"] = str(archive)
    d["tree"] = str(tree)
    names = {e["path"] for e in result.entries}
    if GITIGNORED_NAME not in names:
        raise AssertionError("archive listing missing gitignored member")
    tree_names = gitignore_walk(tree)
    d["tree_gitignore_walk"] = tree_names
    if GITIGNORED_NAME in tree_names:
        raise AssertionError("gitignore walk unexpectedly saw packed file")
    if result.ok:
        raise AssertionError("gitignored packed file was not detected")
    viol = {v["path"] for v in result.allowlist_violations}
    if GITIGNORED_NAME not in viol:
        raise AssertionError(f"gate did not name gitignored member: {viol}")
    return d


def run_all_controls(work: Path) -> dict:
    return {
        "clean": control_clean(work / "c-clean"),
        "dotgit": control_dotgit(work / "c-dotgit"),
        "blob": control_blob(work / "c-blob"),
        "gitignored": control_gitignored(work / "c-gitignored"),
    }


def receipt_view(doc: dict) -> dict:
    """Envelope receipts nest domain fields under report; probes read the merge."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "clean_archive" in report or "evaluation_surface" in report
    ):
        view = dict(doc)
        view.update(report)
        return view
    return doc
