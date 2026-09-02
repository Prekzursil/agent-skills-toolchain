"""Both-states measurements for RES-0052.

Known-good: two installs from the same lockfile match per-file blob hashes.
Known-broken: mutate one installed file; comparison reports a mismatch.
CRLF control: git archive differs from git cat-file on the same path.
A probe silent in both states is rejected (always-match comparator).
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fixture import PACKAGE_FILES, PACKAGE_NAME, PACKAGE_VERSION, build_package_repo
from lockfile import (
    build_lockfile,
    compare_install,
    install_from_lockfile,
    sha256_hex,
    three_route,
    tree_hashes,
)


def _silent_always_match(_lock: dict[str, Any], _dest: Path) -> dict[str, Any]:
    """Detector that cannot fail — silent in both states."""
    return {"match": True, "mismatch_count": 0, "mismatches": [], "silent": True}


def run_suite() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="res0052-suite-"))
    try:
        return _run_suite(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run_suite(tmp: Path) -> dict[str, Any]:
    repo = tmp / "pkg"
    meta = build_package_repo(repo)
    repo = Path(meta["repo"])
    rev = meta["commit"]
    lock = build_lockfile(repo, rev, PACKAGE_NAME, PACKAGE_VERSION)

    dest_a = tmp / "install-a"
    dest_b = tmp / "install-b"
    written_a = install_from_lockfile(lock, repo, dest_a)
    written_b = install_from_lockfile(lock, repo, dest_b)
    hashes_a = tree_hashes(dest_a)
    hashes_b = tree_hashes(dest_b)
    cmp_a = compare_install(lock, dest_a)
    cmp_b = compare_install(lock, dest_b)
    identity = {
        "install_a": written_a,
        "install_b": written_b,
        "hashes_a": hashes_a,
        "hashes_b": hashes_b,
        "trees_identical": hashes_a == hashes_b,
        "compare_a_match": cmp_a["match"],
        "compare_b_match": cmp_b["match"],
        "per_file_blob_hashes_match": hashes_a == hashes_b
        and cmp_a["match"]
        and cmp_b["match"]
        and len(hashes_a) == len(lock["files"]),
        "file_count": len(lock["files"]),
    }

    routes = [three_route(repo, rev, entry["path"]) for entry in lock["files"]]
    archive_differs = [r for r in routes if r["archive_differs_from_blob"]]
    crlf_control = {
        "routes": routes,
        "archive_differs_on_any_file": bool(archive_differs),
        "files_where_archive_differs": [r["path"] for r in archive_differs],
        "cat_file_equals_show_all": all(r["cat_file_equals_show"] for r in routes),
        "any_archive_has_crlf": any(r["archive_has_crlf"] for r in routes),
        "any_blob_has_crlf": any(r["blob_has_crlf"] for r in routes),
        "method": "git cat-file -p (blob); git archive is the forbidden control",
    }

    dest_m = tmp / "install-mut"
    install_from_lockfile(lock, repo, dest_m)
    cmp_before = compare_install(lock, dest_m)
    target_rel = next(
        e["path"] for e in lock["files"] if e["path"].endswith(".sh")
    )
    target = dest_m / target_rel
    before = target.read_bytes()
    target.write_bytes(before + b"\nMUTATED\n")
    cmp_after = compare_install(lock, dest_m)
    silent_before = _silent_always_match(lock, dest_m)
    silent_after = _silent_always_match(lock, dest_m)
    mutation = {
        "mutated_path": target_rel,
        "before_match": cmp_before["match"],
        "after_match": cmp_after["match"],
        "after_mismatch_count": cmp_after["mismatch_count"],
        "after_mismatches": cmp_after["mismatches"],
        "demonstrated_mismatch_on_mutation": (
            cmp_before["match"] is True
            and cmp_after["match"] is False
            and cmp_after["mismatch_count"] >= 1
        ),
        "silent_detector_before_match": silent_before["match"],
        "silent_detector_after_match": silent_after["match"],
        "silent_detector_cannot_discriminate": silent_before["match"]
        is True
        and silent_after["match"] is True,
        "real_detector_discriminates": cmp_before["match"] is True
        and cmp_after["match"] is False,
    }

    expected_content = {
        rel: sha256_hex(body) for rel, body in sorted(PACKAGE_FILES.items())
    }
    lock_content = {e["path"]: e["sha256"] for e in lock["files"]}
    content_hashes_match_sources = lock_content == expected_content

    ok = (
        identity["per_file_blob_hashes_match"]
        and crlf_control["archive_differs_on_any_file"]
        and crlf_control["any_archive_has_crlf"]
        and not crlf_control["any_blob_has_crlf"]
        and crlf_control["cat_file_equals_show_all"]
        and mutation["demonstrated_mismatch_on_mutation"]
        and mutation["real_detector_discriminates"]
        and mutation["silent_detector_cannot_discriminate"]
        and content_hashes_match_sources
        and lock["resolution_order"] == sorted(PACKAGE_FILES)
    )
    return {
        "ok": ok,
        "lockfile": lock,
        "identity": identity,
        "crlf_control": crlf_control,
        "mutation": mutation,
        "content_hashes_match_sources": content_hashes_match_sources,
        "source_commit": rev,
        "package": {"name": PACKAGE_NAME, "version": PACKAGE_VERSION},
    }
