"""AUD-0092 rollback backup + restore rehearsal.

Creates a restorable backup of the live mutation tree on this host
(/opt/p2/ast-integrate), writes it OUTSIDE the program corpus, excludes
secret-named files, then restores into a scratch path and byte-compares.

Never returns or prints secret file contents or the planted canary value.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import secrets as secretslib
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0092"
LIVE_TREE_ID = "ast-integrate"
CANARY_TREE_ID = "planted-secret-control"
KEEP_ME_REL = "command-center/p2-wave/probes/AUD-0092/fixtures/keep-me.txt"
SKIP_DIR_NAMES = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".pytest_cache",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        ".eggs",
    }
)
PROBES_REL = "command-center/p2-wave/probes"
SECRET_EXACT = frozenset(
    {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "credentials.csv",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)
SECRET_SUFFIXES = (".pem", ".p12", ".pfx")


def default_outside_root() -> Path:
    for candidate in (Path("/var/tmp"), Path("/tmp")):
        try:
            if candidate.is_dir() and os.access(candidate, os.W_OK):
                return candidate
        except OSError:
            continue
    raise RuntimeError("no writable /var/tmp or /tmp for outside-corpus backup")


def backup_root() -> Path:
    override = os.environ.get("AUD0092_BACKUP_ROOT", "").strip()
    if override:
        return Path(override)
    return default_outside_root() / "p2-aud-0092-rollback"


def restore_root() -> Path:
    override = os.environ.get("AUD0092_RESTORE_ROOT", "").strip()
    if override:
        return Path(override)
    return default_outside_root() / "p2-aud-0092-restore-scratch"


def canary_root() -> Path:
    override = os.environ.get("AUD0092_CANARY_ROOT", "").strip()
    if override:
        return Path(override)
    return Path("/tmp") / "p2-aud-0092-canary-tree"


def assert_outside_corpus(path: Path, repo: Path = REPO) -> None:
    resolved = path.resolve()
    repo_res = repo.resolve()
    try:
        resolved.relative_to(repo_res)
    except ValueError:
        return
    raise RuntimeError(f"path is inside the program corpus: {resolved}")


def is_secret_name(name: str) -> bool:
    lower = name.lower()
    if lower in SECRET_EXACT:
        return True
    if lower.startswith(".env.") and lower != ".env.example":
        return True
    if lower.endswith(SECRET_SUFFIXES):
        return True
    return False


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw)


def prune_dirnames(dirpath: str, dirnames: list[str], root: Path) -> None:
    """Drop VCS/cache dirs. Sibling unit probe scratch is not this unit's mutation set."""
    dirnames[:] = sorted(
        d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".git")
    )
    try:
        rel = Path(dirpath).relative_to(root).as_posix()
    except ValueError:
        return
    if rel == PROBES_REL:
        dirnames[:] = [d for d in dirnames if d == UNIT]


def iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        prune_dirnames(dirpath, dirnames, root)
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink() or not p.is_file():
                continue
            yield p


def artifact_backup(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    for src in (doc, report, ext):
        block = src.get("backup")
        if isinstance(block, dict):
            return block
    return {}


def artifact_restore(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    for src in (doc, report, ext):
        block = src.get("restore")
        if isinstance(block, dict):
            return block
    return {}


def artifact_both_states(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    for src in (doc, report, ext):
        block = src.get("both_states")
        if isinstance(block, dict):
            return block
    return {}


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_canary_tree(root: Path, canary: str) -> Path:
    assert_outside_corpus(root)
    reset_dir(root)
    env_path = root / ".env"
    env_path.write_text(
        f"# planted AUD-0092 secret-pattern canary; must not enter corpus or backup\n"
        f"PLANTED={canary}\n",
        encoding="utf-8",
    )
    return env_path


def scan_for_token(root: Path, token: str) -> list[str]:
    """Return relative paths under root whose bytes contain token. Never logs token."""
    hits: list[str] = []
    needle = token.encode("utf-8")
    if not root.exists():
        return hits
    for p in iter_files(root):
        try:
            if needle in p.read_bytes():
                hits.append(rel_posix(p, root))
        except OSError:
            continue
    return hits


def compare_restore_to_snapshot(restore_tree: Path, expected: list[dict]) -> dict:
    """Byte-compare a restore against the backup snapshot (source-at-capture).

    Re-hashing the live worktree after the copy is not a restore proof: sibling
    units rewrite files under /opt/p2/ast-integrate during this wave. The
    snapshot hashes are the source bytes actually captured.
    """
    missing: list[str] = []
    mismatch: list[str] = []
    expected_map = {str(row["path"]): str(row["sha256"]) for row in expected}
    for rel, sha in expected_map.items():
        dst = restore_tree / rel
        if not dst.is_file():
            missing.append(rel)
            continue
        if digest_file(dst)[0] != sha:
            mismatch.append(rel)
    extra: list[str] = []
    if restore_tree.is_dir():
        for p in iter_files(restore_tree):
            rel = rel_posix(p, restore_tree)
            if rel not in expected_map:
                extra.append(rel)
    equal = not missing and not mismatch and not extra
    return {
        "equal": equal,
        "missing_n": len(missing),
        "mismatch_n": len(mismatch),
        "extra_n": len(extra),
        "missing_head": missing[:8],
        "mismatch_head": mismatch[:8],
        "extra_head": extra[:8],
        "exit_code": 0 if equal else 1,
        "blocked": not equal,
    }


def mutant_always_green(restore_tree: Path, expected: list[dict]) -> dict:
    del restore_tree, expected
    return {
        "equal": True,
        "missing_n": 0,
        "mismatch_n": 0,
        "extra_n": 0,
        "exit_code": 0,
        "blocked": False,
        "mutant": True,
    }


def backup_tree(tree_id: str, source: Path, dest_trees: Path) -> dict:
    dest = dest_trees / tree_id
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[dict] = []
    excluded: list[dict] = []
    for src in iter_files(source):
        rel = rel_posix(src, source)
        name = src.name
        if is_secret_name(name):
            excluded.append({"tree_id": tree_id, "path": rel, "reason": "secret-name"})
            continue
        dst = dest / rel
        copy_file(src, dst)
        src_sha, src_size = digest_file(src)
        sha, size = digest_file(dst)
        if sha != src_sha:
            copy_file(src, dst)
            src_sha, src_size = digest_file(src)
            sha, size = digest_file(dst)
        copied.append(
            {
                "tree_id": tree_id,
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "source_matched_at_copy": sha == src_sha,
                "source_bytes_at_copy": src_size,
            }
        )
    return {"copied": copied, "excluded": excluded}


def restore_tree(tree_id: str, dest_trees: Path, scratch: Path) -> Path:
    src = dest_trees / tree_id
    dst = scratch / tree_id
    reset_dir(dst)
    if src.is_dir():
        for p in iter_files(src):
            rel = rel_posix(p, src)
            copy_file(p, dst / rel)
    return dst


def run_rehearsal() -> dict:
    backup_dest = backup_root()
    scratch = restore_root()
    canary_tree = canary_root()
    assert_outside_corpus(backup_dest)
    assert_outside_corpus(scratch)
    assert_outside_corpus(canary_tree)
    if not REPO.is_dir():
        raise RuntimeError(f"live mutation tree missing: {REPO}")

    keep_me = REPO / KEEP_ME_REL
    if not keep_me.is_file():
        raise RuntimeError(f"keep-me fixture missing: {KEEP_ME_REL}")
    keep_sha, keep_bytes = digest_file(keep_me)

    canary = "AUD0092CANARY_" + secretslib.token_hex(24)
    write_canary_tree(canary_tree, canary)

    reset_dir(backup_dest)
    dest_trees = backup_dest / "trees"
    dest_trees.mkdir(parents=True, exist_ok=True)

    live_pack = backup_tree(LIVE_TREE_ID, REPO, dest_trees)
    canary_pack = backup_tree(CANARY_TREE_ID, canary_tree, dest_trees)
    copied = live_pack["copied"] + canary_pack["copied"]
    excluded = live_pack["excluded"] + canary_pack["excluded"]

    manifest_path = backup_dest / "MANIFEST.json"
    manifest_doc = {
        "unit_id": UNIT,
        "source_tree": str(REPO),
        "backup_destination": str(backup_dest),
        "outside_corpus": True,
        "files": copied,
        "excluded_secret_paths": [e["path"] for e in excluded],
        "excluded": excluded,
    }
    manifest_bytes = (json.dumps(manifest_doc, indent=1, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha = digest_bytes(manifest_bytes)

    canary_leaked_in_backup = scan_for_token(backup_dest, canary)
    secret_named_in_backup = [
        rel_posix(p, backup_dest)
        for p in iter_files(backup_dest)
        if is_secret_name(p.name)
    ]
    canary_files_copied = [f for f in copied if f["tree_id"] == CANARY_TREE_ID]
    planted_excluded = any(
        e["tree_id"] == CANARY_TREE_ID and Path(e["path"]).name == ".env"
        for e in excluded
    )

    reset_dir(scratch)
    restored_live = restore_tree(LIVE_TREE_ID, dest_trees, scratch)
    live_expected = live_pack["copied"]
    good = compare_restore_to_snapshot(restored_live, live_expected)

    damaged_rel = KEEP_ME_REL
    damaged_path = restored_live / damaged_rel
    if not damaged_path.is_file():
        raise RuntimeError("keep-me missing from restore; comparison would be vacuous")
    damaged_path.unlink()
    broken = compare_restore_to_snapshot(restored_live, live_expected)
    mutant_on_broken = mutant_always_green(restored_live, live_expected)
    copy_races = sum(1 for f in copied if not f.get("source_matched_at_copy", True))

    keep_in_backup = next(
        (
            f
            for f in copied
            if f["tree_id"] == LIVE_TREE_ID and f["path"] == KEEP_ME_REL
        ),
        None,
    )
    live_env_excluded = [
        e["path"]
        for e in live_pack["excluded"]
        if Path(e["path"]).name == ".env" or Path(e["path"]).name.startswith(".env.")
    ]

    # Recreate keep-me on disk is not needed; we deleted it only in scratch.
    discriminates = (good["equal"] is True) and (broken["equal"] is False)
    mutant_fails_to_discriminate = mutant_on_broken["equal"] is True
    secrets_not_in_backup = (
        not canary_leaked_in_backup
        and not secret_named_in_backup
        and not canary_files_copied
        and planted_excluded
    )

    ok = (
        discriminates
        and secrets_not_in_backup
        and keep_in_backup is not None
        and keep_in_backup["sha256"] == keep_sha
        and mutant_fails_to_discriminate
        and len(copied) >= 1
        and good["exit_code"] == 0
        and broken["exit_code"] != 0
    )

    return {
        "ok": ok,
        "unit_id": UNIT,
        "live_tree": str(REPO),
        "backup_destination": str(backup_dest),
        "restore_scratch": str(scratch),
        "canary_tree": str(canary_tree),
        "backup_outside_corpus": True,
        "restore_outside_corpus": True,
        "file_count": len(copied),
        "live_file_count": len(live_pack["copied"]),
        "excluded_count": len(excluded),
        "excluded_secret_paths": [e["path"] for e in excluded],
        "live_env_excluded": live_env_excluded,
        "files": copied,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "manifest_bytes": len(manifest_bytes),
        "keep_me": {
            "path": KEEP_ME_REL,
            "sha256": keep_sha,
            "bytes": keep_bytes,
            "in_backup": keep_in_backup is not None,
        },
        "known_good": good,
        "known_broken": broken,
        "damaged_rel": damaged_rel,
        "mutant_always_green_on_damaged": mutant_on_broken,
        "discriminates": discriminates,
        "mutant_fails_to_discriminate": mutant_fails_to_discriminate,
        "secrets_not_in_backup": secrets_not_in_backup,
        "planted_secret_excluded": planted_excluded,
        "canary_leaked_in_backup_n": len(canary_leaked_in_backup),
        "secret_named_in_backup_n": len(secret_named_in_backup),
        "canary_files_copied_n": len(canary_files_copied),
        "copy_races": copy_races,
        "sibling_worktrees": "NOT-CHECKED",
        "skipped_sibling_probe_scratch": True,
        "residual": (
            "This host's mutation tree is /opt/p2/ast-integrate. "
            "Sibling owner worktrees (~/Documents/GitHub, ~/.claude/agent-worktrees) "
            "are not present here and were not backed up. "
            "command-center/p2-wave/probes/* except AUD-0092 is sibling-unit "
            "scratch (~3.5GiB) and is not this unit's mutation set; copying it "
            "would miss the 180s named-probe budget. Restore is byte-compared "
            "to the backup snapshot (source-at-capture), not re-hashed against a "
            "live tree sibling units are rewriting. Full per-file sha256 lives in "
            "the outside-corpus MANIFEST.json, not in the catalog artifact."
        ),
    }
