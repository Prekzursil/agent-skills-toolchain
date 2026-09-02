"""Live CNF-0145 scenario: pack at tag, fresh-clone rebuild, controls."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from lib import (
    CONTROL_REL,
    HYGIENE_CLASSES,
    RELEASE_TAG,
    cat_file,
    clone_fresh,
    commit_one_byte,
    compare_packages,
    estate_facts,
    extract_tar_gz,
    init_release_repo,
    isolated_env,
    lf,
    mutate_member,
    normalize_archive,
    pack_from_git,
    pack_naive_from_worktree,
    plant_forbidden,
    read_archive,
    rmtree,
    scan_archive_hygiene,
    scan_forbidden,
    sha256_bytes,
    sha_set,
)


def _scratch() -> Path:
    return Path(tempfile.mkdtemp(prefix="cnf0145-"))


def run_scenario() -> dict[str, Any]:
    run_started = time.time()
    roots: list[Path] = []
    try:
        src = _scratch()
        roots.append(src)
        init_release_repo(src)

        released = pack_from_git(src, RELEASE_TAG)
        hygiene_clean = scan_archive_hygiene(released)

        empty_staging = _scratch()
        roots.append(empty_staging)
        empty_hits = scan_forbidden(empty_staging)

        planted = _scratch()
        roots.append(planted)
        plants = plant_forbidden(planted)
        planted_hits = scan_forbidden(planted)
        planted_classes = sorted({h["class"] for h in planted_hits})

        parent = _scratch()
        roots.append(parent)
        home = parent / "empty-home"
        # CNF-0145-FRESH-CLONE-CTIME
        dest = parent / "fresh-clone"
        clone_fresh(src, dest, home)
        clone_stat = dest.stat()
        isolated = isolated_env(home)
        home_entries = [p.name for p in home.iterdir()] if home.exists() else []

        rebuild = pack_from_git(dest, RELEASE_TAG)
        both = compare_packages(released, rebuild)

        reviewer_dest = parent / "reviewer-clone"
        clone_fresh(src, reviewer_dest, parent / "reviewer-home")
        reviewer_pkg = pack_from_git(reviewer_dest, RELEASE_TAG)
        reviewer_match = reviewer_pkg == released == rebuild

        mutated_pkg = mutate_member(rebuild, "README.md")
        known = compare_packages(released, mutated_pkg)

        commit_one_byte(dest, "README.md")
        committed_pkg = pack_from_git(dest, "HEAD")
        committed = compare_packages(released, committed_pkg)

        t_a = int(time.time())
        naive_a = pack_naive_from_worktree(src, mtime=t_a)
        naive_b = pack_naive_from_worktree(src, mtime=t_a + 7)
        naive_raw_differs = naive_a != naive_b
        naive_norm_same = normalize_archive(naive_a) == normalize_archive(naive_b)

        arch = read_archive(src, CONTROL_REL, RELEASE_TAG)
        blob = cat_file(src, CONTROL_REL, RELEASE_TAG)
        worktree = (src / CONTROL_REL).read_bytes()
        archive_trap = {
            "path": CONTROL_REL,
            "rev": RELEASE_TAG,
            "archive_bytes": len(arch),
            "archive_crlf": arch.count(b"\r\n"),
            "archive_sha256": sha256_bytes(arch),
            "cat_file_bytes": len(blob),
            "cat_file_crlf": blob.count(b"\r\n"),
            "cat_file_sha256": sha256_bytes(blob),
            "worktree_bytes": len(worktree),
            "worktree_crlf": worktree.count(b"\r\n"),
            "worktree_sha256": sha256_bytes(worktree),
            "archive_equals_cat_file": arch == blob,
            "identical_after_lf": lf(arch) == lf(blob) == lf(worktree),
        }

        member_blob_audit = []
        packed = extract_tar_gz(released)
        for rel, data in sorted(packed.items()):
            live_blob = cat_file(src, rel, RELEASE_TAG)
            member_blob_audit.append(
                {
                    "path": rel,
                    "packed_sha256": sha256_bytes(data),
                    "cat_file_sha256": sha256_bytes(live_blob),
                    "match": data == live_blob,
                }
            )

        created_during = clone_stat.st_ctime >= (run_started - 1.0)
        return {
            "run_started_unix": run_started,
            "release_tag": RELEASE_TAG,
            "estate": estate_facts(),
            "sha256_sets": {
                "released": sha_set(released),
                "rebuild": sha_set(rebuild),
            },
            "both_states": both,
            "known_present": {
                "fired": known["material_remaining"] > 0
                and not known["normalized_identical"],
                "class": "material-content",
                "material_remaining": known["material_remaining"],
                "path": "README.md",
            },
            "committed_mutation": {
                "fired": committed["material_remaining"] > 0,
                "material_remaining": committed["material_remaining"],
                "normalized_identical": committed["normalized_identical"],
            },
            "naive_timestamp": {
                "raw_differs": naive_raw_differs,
                "normalized_identical": naive_norm_same,
            },
            "package_hygiene": {
                "clean_archive": hygiene_clean == [],
                "empty_staging_clean": empty_hits == [],
                "planted_found": all(c in planted_classes for c in HYGIENE_CLASSES),
                "classes_found": planted_classes,
                "plants": plants,
                "archive_hits": hygiene_clean,
                "planted_hits": planted_hits,
            },
            "fresh_clone_proof": {
                "used": True,
                "created_during_this_run": created_during,
                "clone_ctime": clone_stat.st_ctime,
                "run_started_unix": run_started,
                "isolated_home": isolated["HOME"] == str(home),
                "home_cache_absent": ".cache" not in home_entries
                and "node_modules" not in home_entries,
                "second_clone_identical": reviewer_match,
                "method": "git clone --branch <tag> into a scratch path created this run",
            },
            "archive_trap": archive_trap,
            "member_blob_audit": member_blob_audit,
            "blob_audit_all_match": all(row["match"] for row in member_blob_audit),
            "reviewer": {
                "second_scratch_pack_sha256": sha256_bytes(reviewer_pkg),
                "matches_released": reviewer_match,
            },
            "isolated_env_home": isolated["HOME"],
        }
    finally:
        for root in roots:
            rmtree(root)


def assert_scenario(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    both = data["both_states"]
    if not both["raw_identical"] or not both["normalized_identical"]:
        errors.append("unmutated clone did not compare clean")
    if both["material_remaining"] != 0:
        errors.append("unmutated remaining material diffs")
    if data["sha256_sets"]["released"]["archive_sha256"] != data["sha256_sets"]["rebuild"][
        "archive_sha256"
    ]:
        errors.append("released/rebuild archive sha256 mismatch")
    if not data["known_present"]["fired"]:
        errors.append("one-byte mutation did not fire")
    if not data["committed_mutation"]["fired"]:
        errors.append("committed one-byte mutation did not fire")
    naive = data["naive_timestamp"]
    if not naive["raw_differs"] or not naive["normalized_identical"]:
        errors.append("timestamp normalizer inert or naive packs identical")
    hyg = data["package_hygiene"]
    if not hyg["clean_archive"] or not hyg["empty_staging_clean"] or not hyg["planted_found"]:
        errors.append(f"hygiene control failed {hyg}")
    missing = [c for c in HYGIENE_CLASSES if c not in hyg["classes_found"]]
    if missing:
        errors.append(f"hygiene classes missing {missing}")
    proof = data["fresh_clone_proof"]
    if not proof["created_during_this_run"] or not proof["isolated_home"]:
        errors.append("fresh-clone proof failed")
    if not proof["second_clone_identical"]:
        errors.append("reviewer second clone pack mismatch")
    trap = data["archive_trap"]
    if trap["archive_crlf"] <= 0:
        errors.append("git archive did not return CRLF on control-crlf.txt")
    if trap["cat_file_crlf"] != 0:
        errors.append("cat-file blob is not LF")
    if trap["archive_equals_cat_file"]:
        errors.append("archive unexpectedly equals cat-file")
    if not trap["identical_after_lf"]:
        errors.append("routes differ after LF normalisation")
    if not data["blob_audit_all_match"]:
        errors.append("packed member bytes != git cat-file blobs")
    return errors
