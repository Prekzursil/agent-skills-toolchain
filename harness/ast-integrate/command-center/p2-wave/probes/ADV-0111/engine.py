#!/usr/bin/env python3
"""ADV-0111: bidirectional manifest/disk reconcile + blob-not-archive hashing.

Probe 1 uses set difference plus size/hash on the intersection.
Probe 2 hashes the committed blob via `git cat-file -p` after CRLF
normalisation and never treats `git archive` as the authority (that
route manufactured CRLF false mismatches on the Windows box).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0111"
LIVE_MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"
LIVE_ROOTS = ("receipts", "adversarial", "audit")
INDEX_NAMES = frozenset({"ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"})
CAT_FILE = "cat-file"
ARCHIVE = "archive"
LISTED_BODY = b"ADV-0111 listed-and-present control\n"
UNLISTED_BODY = b"ADV-0111 deliberately-unlisted control\n"
BLOB_LF = b"ADV-0111 blob line one\nADV-0111 blob line two\n"
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0111 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0111 <reason>."
)


class RecipeError(RuntimeError):
    """Raised when a caller asks to hash via git archive."""


def lf_digest(payload: bytes) -> tuple[str, int, int]:
    raw = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), payload.count(b"\r\n")


def measure_bytes(payload: bytes, recipe: str) -> dict[str, Any]:
    digest, nbytes, crlf = lf_digest(payload)
    return {
        "recipe": recipe,
        "sha256": digest,
        "bytes": nbytes,
        "crlf_count": crlf,
        "raw_bytes": len(payload),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _git_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "ADV-0111"
    env["GIT_AUTHOR_EMAIL"] = "adv-0111@local"
    env["GIT_COMMITTER_NAME"] = "ADV-0111"
    env["GIT_COMMITTER_EMAIL"] = "adv-0111@local"
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=_git_env(repo),
        check=False,
    )


def refuse_archive_recipe(recipe: str) -> None:
    token = str(recipe or "").strip().lower().replace("_", "-")
    if ARCHIVE in token:
        raise RecipeError(
            "git archive is forbidden as a hash authority (CRLF export on "
            "the Windows box; CI judges git cat-file -p bytes)"
        )


def blob_bytes(repo: Path, rev: str, path: str) -> bytes:
    spec = f"{rev}:{path.replace(chr(92), '/')}"
    proc = git(repo, CAT_FILE, "-p", spec)
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode("utf-8", errors="replace") or f"cat-file failed {spec}"
        )
    return proc.stdout


def archive_bytes(repo: Path, rev: str, path: str) -> bytes:
    """Measurement-only. Never used as the mismatch authority."""
    proc = git(repo, ARCHIVE, "--format=tar", rev, path)
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode("utf-8", errors="replace") or "git archive failed"
        )
    buf = io.BytesIO(proc.stdout)
    with tarfile.open(fileobj=buf, mode="r:") as tf:
        names = [m.name for m in tf.getmembers() if m.isfile()]
        want = path.replace("\\", "/")
        member = None
        for name in names:
            if name.replace("\\", "/") in {want, f"./{want}"}:
                member = tf.extractfile(name)
                break
        if member is None and names:
            member = tf.extractfile(names[0])
        if member is None:
            raise RuntimeError(f"git archive tar had no file member for {path}")
        return member.read()


def _is_scratch(path: Path, corpus: Path) -> bool:
    return any(part.startswith("_") for part in path.relative_to(corpus).parts)


def list_disk_files(disk_root: Path, *, skip_index: bool = True) -> list[str]:
    files: list[str] = []
    if not disk_root.is_dir():
        return files
    for path in sorted(disk_root.rglob("*")):
        if not path.is_file():
            continue
        if _is_scratch(path, disk_root):
            continue
        if skip_index and path.name in INDEX_NAMES:
            continue
        files.append(path.relative_to(disk_root).as_posix())
    return files


def load_manifest_entries(path: Path) -> tuple[bool, str, list[dict[str, Any]]]:
    if not path.is_file() or path.stat().st_size <= 0:
        return False, "absent", []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return True, f"unparseable:{type(exc).__name__}", []
    rows: list[Any]
    if isinstance(data, dict) and isinstance(data.get("artifacts"), list):
        rows = data["artifacts"]
    elif isinstance(data, list):
        rows = data
    else:
        return True, "unrecognized-shape", []
    entries: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        entries.append(item)
    return True, "ok", entries


def _entry_map(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in entries:
        rel = str(item.get("path") or "").replace("\\", "/").lstrip("./")
        if rel:
            out[rel] = item
    return out


def reconcile(manifest_path: Path, disk_root: Path) -> dict[str, Any]:
    exists, reason, entries = load_manifest_entries(manifest_path)
    listed = _entry_map(entries)
    disk = list_disk_files(disk_root)
    listed_set = set(listed)
    disk_set = set(disk)
    manifest_only = sorted(listed_set - disk_set)
    disk_only = sorted(disk_set - listed_set)
    intersection = sorted(listed_set & disk_set)
    verified: list[dict[str, Any]] = []
    hash_mismatches: list[dict[str, Any]] = []
    size_mismatches: list[dict[str, Any]] = []
    for rel in intersection:
        target = disk_root / rel
        payload = target.read_bytes()
        obs = measure_bytes(payload, "worktree-lf-normalized")
        claimed_sha = str(listed[rel].get("sha256") or "")
        claimed_bytes = listed[rel].get("bytes")
        row = {
            "path": rel,
            "claimed_sha256": claimed_sha,
            "claimed_bytes": claimed_bytes,
            "disk_sha256": obs["sha256"],
            "disk_bytes": obs["bytes"],
            "disk_crlf_count": obs["crlf_count"],
            "sha_match": claimed_sha == obs["sha256"],
            "size_match": claimed_bytes == obs["bytes"] if claimed_bytes is not None else None,
        }
        if not row["sha_match"]:
            hash_mismatches.append(row)
        elif row["size_match"] is False:
            size_mismatches.append(row)
        else:
            verified.append(row)
    one_way_ok = not manifest_only and not hash_mismatches and not size_mismatches
    both_ways_ok = one_way_ok and not disk_only
    return {
        "manifest_path": manifest_path.as_posix(),
        "manifest_exists": exists,
        "manifest_reason": reason,
        "listed_count": len(listed_set),
        "disk_count": len(disk_set),
        "manifest_only": manifest_only,
        "disk_only": disk_only,
        "intersection": intersection,
        "verified": verified,
        "hash_mismatches": hash_mismatches,
        "size_mismatches": size_mismatches,
        "one_way_manifest_to_disk_ok": one_way_ok,
        "bidirectional_ok": both_ways_ok,
    }


def plant_control_estate(root: Path) -> dict[str, Any]:
    """Listed+present file plus a deliberately unlisted file."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "listed.txt").write_bytes(LISTED_BODY)
    (root / "unlisted.txt").write_bytes(UNLISTED_BODY)
    sha, nbytes, _ = lf_digest(LISTED_BODY)
    man = {
        "schema_version": 1,
        "artifacts": [
            {
                "path": "listed.txt",
                "sha256": sha,
                "bytes": nbytes,
                "present": True,
            }
        ],
    }
    (root / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    good = reconcile(root / "ARTIFACT-MANIFEST.json", root)
    missing_root = root / "missing-listed"
    missing_root.mkdir(exist_ok=True)
    (missing_root / "unlisted.txt").write_bytes(UNLISTED_BODY)
    (missing_root / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    missing = reconcile(missing_root / "ARTIFACT-MANIFEST.json", missing_root)
    return {
        "listed_sha256": sha,
        "listed_bytes": nbytes,
        "good": good,
        "missing_listed": missing,
        "unlisted_in_good_disk_only": "unlisted.txt" in good["disk_only"],
        "listed_verified_in_good": any(
            row["path"] == "listed.txt" for row in good["verified"]
        ),
        "one_way_silent_on_unlisted": bool(good["one_way_manifest_to_disk_ok"]),
        "bidirectional_catches_unlisted": not good["bidirectional_ok"],
        "missing_listed_in_manifest_only": "listed.txt" in missing["manifest_only"],
    }


def plant_blob_crlf_repo(root: Path, *, rel: str = "control.txt") -> dict[str, Any]:
    """LF blob, dirty CRLF worktree. Hash authority is git cat-file -p."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    crlf = BLOB_LF.replace(b"\n", b"\r\n")
    git(root, "init", "-b", "main")
    git(root, "-c", "core.autocrlf=false", "config", "core.autocrlf", "false")
    git(root, "config", "commit.gpgsign", "false")
    (root / rel).write_bytes(BLOB_LF)
    git(root, "add", "--", rel)
    proc = git(
        root,
        "-c",
        "core.autocrlf=false",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "ADV-0111 LF control blob",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode("utf-8", errors="replace") or "git commit failed"
        )
    (root / rel).write_bytes(crlf)
    blob = blob_bytes(root, "HEAD", rel)
    tree = (root / rel).read_bytes()
    try:
        archived = archive_bytes(root, "HEAD", rel)
        archive_error = ""
    except Exception as exc:  # noqa: BLE001 — measurement, not authority
        archived = b""
        archive_error = f"{type(exc).__name__}:{exc}"
    blob_m = measure_bytes(blob, "git cat-file -p")
    tree_m = measure_bytes(tree, "worktree")
    arch_m = measure_bytes(archived, "git archive (measurement only)") if archived else None
    worktree_raw_mismatch = tree_m["raw_sha256"] != blob_m["raw_sha256"]
    after_normalize_match = tree_m["sha256"] == blob_m["sha256"]
    return {
        "path": rel,
        "rev": "HEAD",
        "hash_authority": "git cat-file -p",
        "archive_used_as_authority": False,
        "blob": blob_m,
        "worktree": tree_m,
        "archive": arch_m,
        "archive_error": archive_error,
        "blob_equals_lf": blob == BLOB_LF,
        "blob_equals_worktree": blob == tree,
        "worktree_is_crlf": tree == crlf and tree != BLOB_LF,
        "worktree_raw_would_false_mismatch": worktree_raw_mismatch,
        "crlf_normalized_matches_blob": after_normalize_match,
        "archive_equals_blob": archived == blob if archived else None,
        "archive_equals_worktree": archived == tree if archived else None,
    }


def live_census(repo: Path | None = None) -> dict[str, Any]:
    repo = Path(repo or REPO)
    manifest = repo / LIVE_MANIFEST_REL
    disk_root = repo / "command-center"
    exists, reason, entries = load_manifest_entries(manifest)
    listed = _entry_map(entries)
    disk: list[str] = []
    corpus = disk_root
    for dirname in LIVE_ROOTS:
        base = disk_root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or _is_scratch(path, corpus):
                continue
            if path.name in INDEX_NAMES:
                continue
            disk.append(path.relative_to(repo).as_posix())
    disk_set = set(disk)
    # Compare using repo-relative forms.
    listed_as_repo = set()
    for rel in listed:
        rel = rel.replace("\\", "/")
        listed_as_repo.add(
            rel if rel.startswith("command-center/") else f"command-center/{rel}"
        )
    rec = {
        "manifest_path": LIVE_MANIFEST_REL,
        "manifest_exists": exists,
        "manifest_reason": reason,
        "listed_count": len(listed),
        "disk_count": len(disk_set),
        "manifest_only": sorted(listed_as_repo - disk_set),
        "disk_only": sorted(disk_set - listed_as_repo),
        "intersection": sorted(listed_as_repo & disk_set),
    }
    hash_mismatches: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    for rel in rec["intersection"]:
        key = rel
        entry = listed.get(rel) or listed.get(rel.split("command-center/", 1)[-1])
        payload = (repo / rel).read_bytes()
        obs = measure_bytes(payload, "worktree-lf-normalized")
        claimed_sha = str((entry or {}).get("sha256") or "")
        claimed_bytes = (entry or {}).get("bytes")
        row = {
            "path": key,
            "claimed_sha256": claimed_sha,
            "disk_sha256": obs["sha256"],
            "sha_match": claimed_sha == obs["sha256"] if claimed_sha else False,
            "size_match": claimed_bytes == obs["bytes"] if claimed_bytes is not None else None,
        }
        if row["sha_match"] and row["size_match"] is not False:
            verified.append(row)
        else:
            hash_mismatches.append(row)
    rec["verified_count"] = len(verified)
    rec["hash_mismatch_count"] = len(hash_mismatches)
    rec["hash_mismatches_head"] = hash_mismatches[:12]
    rec["disk_only_head"] = rec["disk_only"][:24]
    rec["global_unit_manifest_exists"] = (
        repo / "command-center" / "UNIT-ARTIFACT-MANIFEST.json"
    ).is_file()
    rec["bidirectional_ok"] = (
        exists
        and reason == "ok"
        and not rec["manifest_only"]
        and not rec["disk_only"]
        and not hash_mismatches
    )
    rec["one_way_manifest_to_disk_ok"] = (
        exists and reason == "ok" and not rec["manifest_only"] and not hash_mismatches
    )
    return rec


def live_verdict(rec: dict[str, Any]) -> str:
    if not rec.get("manifest_exists"):
        return "REFUTED"
    if rec.get("bidirectional_ok"):
        return "CONFIRMED"
    if rec.get("listed_count") or rec.get("disk_count"):
        return "REFUTED"
    return "NOT-CHECKED"


def probe1_payload() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv0111-p1-") as tmp:
        planted = plant_control_estate(Path(tmp) / "estate")
    live = live_census()
    return {
        "probe": "probe1-bidirectional-set-diff",
        "listed_verified": planted["listed_verified_in_good"],
        "unlisted_in_disk_only": planted["unlisted_in_good_disk_only"],
        "good_disk_only": planted["good"]["disk_only"],
        "good_manifest_only": planted["good"]["manifest_only"],
        "good_verified_paths": [r["path"] for r in planted["good"]["verified"]],
        "one_way_silent_on_unlisted": planted["one_way_silent_on_unlisted"],
        "bidirectional_catches_unlisted": planted["bidirectional_catches_unlisted"],
        "missing_listed_in_manifest_only": planted["missing_listed_in_manifest_only"],
        "live": {
            "manifest_exists": live["manifest_exists"],
            "manifest_reason": live["manifest_reason"],
            "listed_count": live["listed_count"],
            "disk_count": live["disk_count"],
            "manifest_only_count": len(live["manifest_only"]),
            "disk_only_count": len(live["disk_only"]),
            "disk_only_head": live["disk_only_head"],
            "hash_mismatch_count": live["hash_mismatch_count"],
            "bidirectional_ok": live["bidirectional_ok"],
            "global_unit_manifest_exists": live["global_unit_manifest_exists"],
            "verdict": live_verdict(live),
        },
        "pass": bool(
            planted["listed_verified_in_good"]
            and planted["unlisted_in_good_disk_only"]
            and planted["one_way_silent_on_unlisted"]
            and planted["bidirectional_catches_unlisted"]
            and planted["missing_listed_in_manifest_only"]
        ),
    }


def probe2_payload() -> dict[str, Any]:
    archive_refused = False
    try:
        refuse_archive_recipe("git archive")
    except RecipeError:
        archive_refused = True
    with tempfile.TemporaryDirectory(prefix="adv0111-p2-") as tmp:
        planted = plant_blob_crlf_repo(Path(tmp) / "repo")
    return {
        "probe": "probe2-blob-not-archive",
        "hash_authority": planted["hash_authority"],
        "archive_used_as_authority": planted["archive_used_as_authority"],
        "archive_recipe_refused": archive_refused,
        "blob_equals_lf": planted["blob_equals_lf"],
        "blob_equals_worktree": planted["blob_equals_worktree"],
        "worktree_is_crlf": planted["worktree_is_crlf"],
        "worktree_raw_would_false_mismatch": planted["worktree_raw_would_false_mismatch"],
        "crlf_normalized_matches_blob": planted["crlf_normalized_matches_blob"],
        "blob_sha256": planted["blob"]["sha256"],
        "blob_bytes": planted["blob"]["bytes"],
        "blob_crlf_count": planted["blob"]["crlf_count"],
        "worktree_raw_sha256": planted["worktree"]["raw_sha256"],
        "worktree_raw_bytes": planted["worktree"]["raw_bytes"],
        "worktree_crlf_count": planted["worktree"]["crlf_count"],
        "archive_equals_blob": planted["archive_equals_blob"],
        "archive_equals_worktree": planted["archive_equals_worktree"],
        "archive_error": planted["archive_error"],
        "linux_host_archive_may_agree_with_blob": planted["archive_equals_blob"] is True,
        "pass": bool(
            archive_refused
            and planted["hash_authority"] == "git cat-file -p"
            and planted["archive_used_as_authority"] is False
            and planted["blob_equals_lf"]
            and not planted["blob_equals_worktree"]
            and planted["worktree_is_crlf"]
            and planted["worktree_raw_would_false_mismatch"]
            and planted["crlf_normalized_matches_blob"]
            and planted["blob"]["crlf_count"] == 0
            and planted["worktree"]["crlf_count"] >= 1
        ),
    }
