"""Three-way byte parity: git blob (cat-file), built package, deployed tree.

Line endings are normalised before content comparison. Two-directional
divergence is BLOCK, never a one-directional sync proposal.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

FOUR_WAY = (
    "identical",
    "package-only",
    "deployed-only",
    "divergent-both-ways",
)
BLOB_RECIPE = "git cat-file -p"
REJECTED_RECIPE = "git archive"
SKIP_GIT_PATHS = frozenset({".gitattributes", ".gitignore"})


def lf_norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def crlf_count(data: bytes) -> int:
    return data.count(b"\r\n")


def line_set(data: bytes) -> set[bytes]:
    return {ln for ln in lf_norm(data).split(b"\n") if ln}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_env(repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["HOME"] = str(repo)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=git_env(repo),
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {args} failed rc={proc.returncode}: {err}")
    return proc


def git_cat_file(repo: Path, path: str, rev: str = "HEAD") -> bytes:
    return run_git(repo, ["cat-file", "-p", f"{rev}:{path}"]).stdout


def git_archive_bytes(repo: Path, path: str, rev: str = "HEAD") -> bytes:
    with tempfile.TemporaryDirectory(prefix="rel0021-arch-") as td:
        tarp = Path(td) / "tree.tar"
        run_git(repo, ["archive", "-o", str(tarp), rev, "--", path])
        with tarfile.open(tarp) as tf:
            member = tf.extractfile(path)
            if member is None:
                raise RuntimeError(f"git archive missing member {path}")
            return member.read()


def git_ls_paths(repo: Path, rev: str = "HEAD") -> list[str]:
    text = run_git(repo, ["ls-tree", "-r", "--name-only", rev]).stdout.decode(
        "utf-8", "replace"
    )
    return [n for n in text.splitlines() if n and n not in SKIP_GIT_PATHS]


def measure_recipe(repo: Path, path: str, rev: str = "HEAD") -> dict[str, Any]:
    cat = git_cat_file(repo, path, rev)
    arch = git_archive_bytes(repo, path, rev)
    cat_crlf = crlf_count(cat)
    arch_crlf = crlf_count(arch)
    delta = arch_crlf - cat_crlf
    return {
        "retrieval_command": f"{BLOB_RECIPE} {rev}:{path}",
        "rejected_alternative": f"{REJECTED_RECIPE} -o <tmp.tar> {rev} -- {path}",
        "control_path": path,
        "rev": rev,
        "cat_file_crlf": cat_crlf,
        "archive_crlf": arch_crlf,
        "crlf_count_difference": delta,
        "cat_file_bytes": len(cat),
        "archive_bytes": len(arch),
        "cat_file_equals_archive": cat == arch,
        "chosen_recipe": BLOB_RECIPE,
        "justification": (
            f"Measured on this host: {BLOB_RECIPE} returned {cat_crlf} CRLF "
            f"pair(s) ({len(cat)} bytes); {REJECTED_RECIPE} returned "
            f"{arch_crlf} CRLF pair(s) ({len(arch)} bytes); difference "
            f"{delta}. Archive applies export/working-tree filters "
            f"(eol=crlf in .gitattributes) and is not the blob. The gate "
            f"therefore reads blobs with {BLOB_RECIPE}, never {REJECTED_RECIPE}."
        ),
    }


def read_package_zip(zip_path: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            out[name] = zf.read(info)
    return out


def read_deployed_tree(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = path.read_bytes()
    return out


def classify_path(
    git_b: Optional[bytes],
    pkg_b: Optional[bytes],
    dep_b: Optional[bytes],
) -> dict[str, Any]:
    present = {
        "git": git_b is not None,
        "package": pkg_b is not None,
        "deployed": dep_b is not None,
    }
    if dep_b is not None and git_b is None and pkg_b is None:
        return {
            "class": "deployed-only",
            "sync_proposal": None,
            "present": present,
            "note": "deployed-only, not missing",
        }
    if pkg_b is not None and git_b is None and dep_b is None:
        return {
            "class": "package-only",
            "sync_proposal": None,
            "present": present,
        }
    if git_b is not None and dep_b is not None:
        repo_only = line_set(git_b) - line_set(dep_b)
        dep_only = line_set(dep_b) - line_set(git_b)
        if repo_only and dep_only:
            return {
                "class": "divergent-both-ways",
                "sync_proposal": None,
                "verdict": "BLOCK",
                "present": present,
                "repo_only_line_count": len(repo_only),
                "deployed_only_line_count": len(dep_only),
                "note": (
                    "two-directional unique content; reconciling in either "
                    "direction destroys work; no one-directional sync proposal"
                ),
            }
        if lf_norm(git_b) == lf_norm(dep_b):
            if pkg_b is None:
                return {
                    "class": "other",
                    "subtype": "git-deployed-identical-package-absent",
                    "sync_proposal": None,
                    "present": present,
                }
            if lf_norm(pkg_b) == lf_norm(git_b):
                return {
                    "class": "identical",
                    "sync_proposal": None,
                    "present": present,
                    "raw_equal": git_b == pkg_b == dep_b,
                    "eol_only_difference": not (git_b == pkg_b == dep_b),
                }
            return {
                "class": "other",
                "subtype": "package-content-mismatch",
                "sync_proposal": None,
                "present": present,
            }
        if repo_only and not dep_only:
            return {
                "class": "other",
                "subtype": "repo-ahead",
                "sync_proposal": "repo-to-deployed",
                "present": present,
            }
        if dep_only and not repo_only:
            return {
                "class": "other",
                "subtype": "deployed-ahead",
                "sync_proposal": "deployed-to-repo",
                "present": present,
            }
    if git_b is not None and pkg_b is None and dep_b is None:
        return {
            "class": "other",
            "subtype": "git-only",
            "sync_proposal": None,
            "present": present,
        }
    return {
        "class": "other",
        "subtype": "unclassified",
        "sync_proposal": None,
        "present": present,
    }


def compare_copies(
    git_files: dict[str, bytes],
    package_files: dict[str, bytes],
    deployed_files: dict[str, bytes],
) -> dict[str, Any]:
    paths = sorted(set(git_files) | set(package_files) | set(deployed_files))
    rows: list[dict[str, Any]] = []
    four = {k: 0 for k in FOUR_WAY}
    proposals: list[dict[str, str]] = []
    extras = (
        "verdict",
        "note",
        "subtype",
        "eol_only_difference",
        "raw_equal",
        "repo_only_line_count",
        "deployed_only_line_count",
    )
    for path in paths:
        git_b = git_files.get(path)
        pkg_b = package_files.get(path)
        dep_b = deployed_files.get(path)
        cls = classify_path(git_b, pkg_b, dep_b)
        row: dict[str, Any] = {
            "path": path,
            "class": cls["class"],
            "sync_proposal": cls.get("sync_proposal"),
            "present": cls.get("present"),
            "git_sha256": sha256_bytes(git_b) if git_b is not None else None,
            "package_sha256": sha256_bytes(pkg_b) if pkg_b is not None else None,
            "deployed_sha256": sha256_bytes(dep_b) if dep_b is not None else None,
            "git_lf_sha256": sha256_bytes(lf_norm(git_b)) if git_b is not None else None,
            "package_lf_sha256": (
                sha256_bytes(lf_norm(pkg_b)) if pkg_b is not None else None
            ),
            "deployed_lf_sha256": (
                sha256_bytes(lf_norm(dep_b)) if dep_b is not None else None
            ),
        }
        for extra in extras:
            if extra in cls:
                row[extra] = cls[extra]
        rows.append(row)
        if cls["class"] in four:
            four[cls["class"]] += 1
        prop = cls.get("sync_proposal")
        if prop:
            proposals.append({"path": path, "proposal": str(prop)})

    two_way_paths = [r["path"] for r in rows if r["class"] == "divergent-both-ways"]
    deployed_only_paths = [r["path"] for r in rows if r["class"] == "deployed-only"]
    leaked = [p for p in proposals if p["path"] in two_way_paths]
    if leaked:
        raise RuntimeError(
            f"classifier emitted one-directional sync for two-way paths: {leaked}"
        )
    return {
        "files": rows,
        "four_way": four,
        "verdict": "BLOCK" if two_way_paths else "PROMOTE",
        "sync_proposals": proposals,
        "two_way_paths": two_way_paths,
        "deployed_only_paths": deployed_only_paths,
        "package_only_paths": [r["path"] for r in rows if r["class"] == "package-only"],
        "identical_paths": [r["path"] for r in rows if r["class"] == "identical"],
    }


def load_git_blobs(repo: Path, rev: str = "HEAD") -> dict[str, bytes]:
    return {path: git_cat_file(repo, path, rev) for path in git_ls_paths(repo, rev)}


def census_world(
    repo: Path, package_zip: Path, deployed: Path, rev: str = "HEAD"
) -> dict[str, Any]:
    result = compare_copies(
        load_git_blobs(repo, rev),
        read_package_zip(package_zip),
        read_deployed_tree(deployed),
    )
    result["blob_source"] = BLOB_RECIPE
    result["rev"] = rev
    return result


def overwrite_deployed_from_package(package_zip: Path, deployed: Path) -> None:
    if deployed.exists():
        for path in sorted(deployed.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    deployed.mkdir(parents=True, exist_ok=True)
    for rel, data in read_package_zip(package_zip).items():
        dest = deployed / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def oracle_allows_overwrite_deployed_from_package(census: dict[str, Any]) -> dict[str, Any]:
    destroy = list(census.get("deployed_only_paths") or []) + list(
        census.get("two_way_paths") or []
    )
    if destroy:
        return {
            "allowed": False,
            "reason": "would-destroy-owner-or-two-way-content",
            "protected_paths": destroy,
        }
    return {
        "allowed": True,
        "reason": "no-deployed-only-or-two-way",
        "protected_paths": [],
    }


def reviewer_destroy_attempt(
    package_zip: Path, deployed: Path, census: dict[str, Any]
) -> dict[str, Any]:
    owner_paths = list(census.get("deployed_only_paths") or [])
    before = {
        p: (deployed / p).read_bytes()
        for p in owner_paths
        if (deployed / p).is_file()
    }
    decision = oracle_allows_overwrite_deployed_from_package(census)
    destroyed = False
    if decision["allowed"]:
        overwrite_deployed_from_package(package_zip, deployed)
        destroyed = any(
            (not (deployed / p).is_file()) or (deployed / p).read_bytes() != before[p]
            for p in before
        )
    survived = {
        p: (deployed / p).is_file() and (deployed / p).read_bytes() == before[p]
        for p in before
    }
    caught = (not decision["allowed"]) and all(survived.values()) and bool(before)
    return {
        "attempted_path": "overwrite-deployed-from-package",
        "oracle_allowed": decision["allowed"],
        "oracle_reason": decision["reason"],
        "protected_paths": decision["protected_paths"],
        "owner_paths": owner_paths,
        "owner_survived": survived,
        "destroyed": destroyed,
        "caught_before_signoff": caught,
    }
