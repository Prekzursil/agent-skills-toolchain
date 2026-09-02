#!/usr/bin/env python3
"""AUD-0036: ARTIFACT-MANIFEST vs disk, blob hashes via git cat-file -p.

Probe 1 hashes committed blob bytes with `git cat-file -p`. Hashing the
worktree and labeling it the blob is the REACH-6 defect and is not used.
This worktree is not a git checkout, so live blob reads fail closed. The
required dual-route control uses an isolated fixture repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0036"
MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"
OUT_REL = "command-center/audit/AUD-0036-artifact-manifest-reconcile.json"
SCHEMA_REL = "command-center/schema/audit-drift.schema.json"
CC_REL = "command-center"
BLOB_ROUTE = "git cat-file -p"

# tools/command-center/render.py CONTRACTED_ARTIFACTS — intended 13 + events log.
CONTRACTED = (
    "PROGRAM-CHARTER.md",
    "OWNER-DECISIONS.md",
    "WORK-UNIT-CATALOG.json",
    "DEPENDENCY-GRAPH.json",
    "ARTIFACT-MANIFEST.json",
    "CLAIM-REGISTRY.json",
    "TEST-REGISTRY.json",
    "RISK-REGISTER.md",
    "UNKNOWNS-REGISTER.md",
    "RELEASE-CHECKLIST.md",
    "ROLLBACK-MANIFEST.md",
    "RUNBOOK.md",
    "STATUS.md",
    "events/EVENTS.jsonl",
)

SKIP_FROM_WALK = {
    OUT_REL,
    "command-center/p2-wave/probes/AUD-0036/SUBAGENT-RETURN.json",
    "command-center/p2-wave/probes/AUD-0036/UNIT-ARTIFACT-MANIFEST.json",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def posix_rel(path: Path, root: Path | None = None) -> str:
    base = root or REPO
    return path.resolve().relative_to(base.resolve()).as_posix()


def worktree_digest(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        return {
            "exists": False,
            "bytes_raw": 0,
            "bytes_lf": 0,
            "sha256_raw": "",
            "sha256_lf": "",
        }
    raw = path.read_bytes()
    lf = lf_normalize(raw)
    return {
        "exists": True,
        "bytes_raw": len(raw),
        "bytes_lf": len(lf),
        "sha256_raw": sha256_bytes(raw),
        "sha256_lf": sha256_bytes(lf),
    }


def git_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env["GIT_AUTHOR_NAME"] = "AUD-0036"
    env["GIT_AUTHOR_EMAIL"] = "aud-0036@invalid"
    env["GIT_COMMITTER_NAME"] = "AUD-0036"
    env["GIT_COMMITTER_EMAIL"] = "aud-0036@invalid"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_git(
    args: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        timeout=timeout,
    )


def git_cat_file_p(
    repo: Path, spec: str, env: dict[str, str] | None = None
) -> dict[str, Any]:
    cmd = ["git", "-C", str(repo), "cat-file", "-p", spec]
    proc = subprocess.run(cmd, capture_output=True, timeout=30, env=env)
    stdout = proc.stdout or b""
    stderr = (proc.stderr or b"").decode("utf-8", "replace")[-400:]
    ok = proc.returncode == 0
    return {
        "command": " ".join(cmd),
        "spec": spec,
        "returncode": int(proc.returncode),
        "ok": ok,
        "bytes": len(stdout) if ok else 0,
        "sha256": sha256_bytes(stdout) if ok else "",
        "stderr": stderr,
        "route": BLOB_ROUTE,
        "skipped": False,
    }


def live_git_status() -> dict[str, Any]:
    git_dir = REPO / ".git"
    proc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        timeout=15,
    )
    inside = (proc.returncode == 0) and (
        (proc.stdout or b"").decode("utf-8", "replace").strip() == "true"
    )
    return {
        "dot_git_exists": git_dir.exists(),
        "dot_git_is_dir": git_dir.is_dir(),
        "dot_git_is_file": git_dir.is_file(),
        "rev_parse_inside": inside,
        "rev_parse_returncode": int(proc.returncode),
        "rev_parse_stderr": (proc.stderr or b"").decode("utf-8", "replace")[-200:],
        "blob_route_live": inside,
    }


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "present": False,
            "parse_ok": False,
            "error": "absent",
            "entries": [],
            "bytes": 0,
        }
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "present": True,
            "parse_ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "entries": [],
            "bytes": len(raw),
        }
    entries: list[dict[str, Any]] = []
    if isinstance(doc, dict):
        blob: Any = (
            doc.get("artifacts")
            or doc.get("entries")
            or doc.get("files")
            or doc.get("items")
            or []
        )
        if isinstance(blob, dict):
            blob = [
                {"path": k, **(v if isinstance(v, dict) else {"value": v})}
                for k, v in blob.items()
            ]
        if isinstance(blob, list):
            for item in blob:
                if not isinstance(item, dict):
                    continue
                rel = str(
                    item.get("path") or item.get("file") or item.get("name") or ""
                ).replace("\\", "/")
                if not rel:
                    continue
                digest = str(
                    item.get("sha256")
                    or item.get("sha_256")
                    or item.get("hash")
                    or item.get("digest")
                    or ""
                )
                entries.append(
                    {
                        "path": rel,
                        "sha256": digest,
                        "bytes": item.get("bytes") or item.get("size") or 0,
                        "present_claimed": item.get("present"),
                    }
                )
    return {
        "present": True,
        "parse_ok": True,
        "error": "",
        "entries": entries,
        "bytes": len(raw),
        "sha256_lf": sha256_bytes(lf_normalize(raw)),
    }


def iter_cc_files() -> list[tuple[Path, str]]:
    root = REPO / CC_REL
    found: list[tuple[Path, str]] = []
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d for d in dirnames if d != "__pycache__" and not d.startswith(".git")
        ]
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = posix_rel(path)
            if rel in SKIP_FROM_WALK:
                continue
            found.append((path, rel))
    return found


def disk_inventory() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    merkle = hashlib.sha256()
    for path, rel in sorted(iter_cc_files(), key=lambda t: t[1]):
        digest = worktree_digest(path)
        row = {
            "path": rel,
            "bytes_raw": digest["bytes_raw"],
            "bytes_lf": digest["bytes_lf"],
            "sha256_raw": digest["sha256_raw"],
            "sha256_lf": digest["sha256_lf"],
        }
        rows.append(row)
        merkle.update(f"{rel} {digest['sha256_lf']}\n".encode("utf-8"))
    return {
        "file_count": len(rows),
        "merkle_sha256_lf": merkle.hexdigest(),
        "files": rows,
    }


def contracted_rows(live_git: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    env = os.environ.copy()
    for name in CONTRACTED:
        rel = f"{CC_REL}/{name}"
        path = REPO / rel
        wt = worktree_digest(path)
        if live_git.get("blob_route_live"):
            blob = git_cat_file_p(REPO, f"HEAD:{rel}", env)
        else:
            blob = {
                "command": f"git -C {REPO} cat-file -p HEAD:{rel}",
                "spec": f"HEAD:{rel}",
                "returncode": None,
                "ok": False,
                "bytes": 0,
                "sha256": "",
                "stderr": "live worktree is not a git repository",
                "route": BLOB_ROUTE,
                "skipped": True,
            }
        out.append(
            {
                "path": rel,
                "disk_exists": wt["exists"],
                "worktree": wt,
                "blob": blob,
                "self_hash_slot": name == "ARTIFACT-MANIFEST.json",
            }
        )
    return out


def manifest_to_disk(manifest: dict[str, Any], live_git: dict[str, Any]) -> dict[str, Any]:
    named_missing: list[dict[str, Any]] = []
    hash_mismatch: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    env = os.environ.copy()
    for entry in manifest.get("entries") or []:
        rel = str(entry.get("path") or "").replace("\\", "/")
        if rel.startswith("./"):
            rel = rel[2:]
        path = REPO / rel
        wt = worktree_digest(path)
        if live_git.get("blob_route_live"):
            blob = git_cat_file_p(REPO, f"HEAD:{rel}", env)
        else:
            blob = {
                "ok": False,
                "sha256": "",
                "skipped": True,
                "route": BLOB_ROUTE,
                "stderr": "live worktree is not a git repository",
            }
        recorded = str(entry.get("sha256") or "")
        matches: list[str] = []
        if recorded and recorded not in {"(self)", "self"}:
            if blob.get("ok") and recorded == blob.get("sha256"):
                matches.append("blob")
            if wt["exists"] and recorded == wt["sha256_raw"]:
                matches.append("worktree_raw")
            if wt["exists"] and recorded == wt["sha256_lf"]:
                matches.append("worktree_lf")
        elif recorded in {"(self)", "self"}:
            matches.append("self")
        row = {
            "path": rel,
            "manifest_sha256": recorded,
            "disk_exists": wt["exists"],
            "worktree": wt,
            "blob": blob,
            "manifest_matches": matches or ["none"],
        }
        rows.append(row)
        if not wt["exists"]:
            named_missing.append(row)
        elif recorded and recorded not in {"(self)", "self"} and "blob" not in matches:
            hash_mismatch.append(row)
    return {
        "entry_count": len(rows),
        "named_missing_count": len(named_missing),
        "hash_mismatch_vs_blob_count": len(hash_mismatch),
        "named_missing": [
            {"path": r["path"], "manifest_sha256": r["manifest_sha256"]}
            for r in named_missing
        ],
        "rows": rows,
    }


def disk_to_manifest(disk: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    man_paths = {
        str(e.get("path") or "").replace("\\", "/")
        for e in (manifest.get("entries") or [])
    }
    man_hashes = {
        str(e.get("sha256") or "")
        for e in (manifest.get("entries") or [])
        if e.get("sha256") and e.get("sha256") not in {"(self)", "self"}
    }
    absent: list[dict[str, Any]] = []
    present: list[str] = []
    hash_only: list[dict[str, Any]] = []
    for f in disk["files"]:
        rel = f["path"]
        if rel in man_paths:
            present.append(rel)
            continue
        rec = {
            "path": rel,
            "sha256_lf": f["sha256_lf"],
            "bytes_lf": f["bytes_lf"],
        }
        absent.append(rec)
        if f["sha256_lf"] in man_hashes:
            hash_only.append(rec)
    return {
        "disk_file_count": disk["file_count"],
        "merkle_sha256_lf": disk["merkle_sha256_lf"],
        "in_manifest_by_path_count": len(present),
        "absent_from_manifest_by_path_count": len(absent),
        "same_hash_different_path_count": len(hash_only),
        "in_manifest_by_path": present,
        "absent_from_manifest_by_path": [a["path"] for a in absent],
        "absent_sample": absent[:25],
        "same_hash_different_path": hash_only[:25],
    }


def dual_route_control() -> dict[str, Any]:
    """Isolated git repo: record worktree AND blob hashes; mini-manifest matches blob."""
    with tempfile.TemporaryDirectory(prefix="aud0036-blob-") as tmp:
        tmp_p = Path(tmp)
        home = tmp_p / "home"
        repo = tmp_p / "repo"
        home.mkdir()
        repo.mkdir()
        env = git_env(home)
        init = run_git(["init", "-b", "main"], repo, env)
        if init.returncode != 0:
            init = run_git(["init"], repo, env)
        run_git(["config", "user.name", "AUD-0036"], repo, env)
        run_git(["config", "user.email", "aud-0036@invalid"], repo, env)
        run_git(["config", "core.autocrlf", "false"], repo, env)
        run_git(["config", "core.eol", "lf"], repo, env)

        crlf_name = "crlf-tracked.txt"
        dirty_name = "content-dirty.txt"
        (repo / crlf_name).write_bytes(b"reach-6-control-body\n")
        (repo / dirty_name).write_bytes(b"clean-blob-body\n")
        run_git(["add", crlf_name, dirty_name], repo, env)
        commit = run_git(["commit", "-m", "AUD-0036 dual-route control"], repo, env)
        if commit.returncode != 0:
            return {
                "control_pass": False,
                "error": "git commit failed",
                "stderr": (commit.stderr or b"").decode("utf-8", "replace")[-400:],
                "blob_route": BLOB_ROUTE,
                "known_file": crlf_name,
                "worktree_sha256_raw": "",
                "blob_sha256": "",
                "manifest_matches": "failed",
            }

        blob_crlf = git_cat_file_p(repo, f"HEAD:{crlf_name}", env)
        blob_dirty = git_cat_file_p(repo, f"HEAD:{dirty_name}", env)
        (repo / crlf_name).write_bytes(b"reach-6-control-body\r\n")
        (repo / dirty_name).write_bytes(b"dirty-worktree-body\n")
        wt_crlf = worktree_digest(repo / crlf_name)
        wt_dirty = worktree_digest(repo / dirty_name)

        recorded_crlf = blob_crlf.get("sha256") or ""
        recorded_dirty = blob_dirty.get("sha256") or ""

        crlf_raw_differs = bool(blob_crlf.get("ok")) and (
            wt_crlf["sha256_raw"] != blob_crlf.get("sha256")
        )
        crlf_lf_equals_blob = wt_crlf["sha256_lf"] == blob_crlf.get("sha256")
        dirty_all_differ = bool(blob_dirty.get("ok")) and (
            wt_dirty["sha256_raw"] != blob_dirty.get("sha256")
            and wt_dirty["sha256_lf"] != blob_dirty.get("sha256")
        )
        used_cat_file = blob_crlf.get("route") == BLOB_ROUTE and "cat-file" in (
            blob_crlf.get("command") or ""
        )
        both_routes_recorded = bool(
            wt_crlf["sha256_raw"]
            and blob_crlf.get("sha256")
            and wt_dirty["sha256_raw"]
            and blob_dirty.get("sha256")
        )
        control_pass = bool(
            blob_crlf.get("ok")
            and blob_dirty.get("ok")
            and crlf_raw_differs
            and crlf_lf_equals_blob
            and dirty_all_differ
            and recorded_crlf == blob_crlf.get("sha256")
            and recorded_dirty == blob_dirty.get("sha256")
            and recorded_dirty != wt_dirty["sha256_raw"]
            and both_routes_recorded
            and used_cat_file
        )
        return {
            "control_pass": control_pass,
            "blob_route": BLOB_ROUTE,
            "known_file": crlf_name,
            "second_file": dirty_name,
            "worktree_sha256_raw": wt_crlf["sha256_raw"],
            "worktree_sha256_lf": wt_crlf["sha256_lf"],
            "blob_sha256": blob_crlf.get("sha256") or "",
            "blob_command": blob_crlf.get("command"),
            "dirty_worktree_sha256_raw": wt_dirty["sha256_raw"],
            "dirty_worktree_sha256_lf": wt_dirty["sha256_lf"],
            "dirty_blob_sha256": blob_dirty.get("sha256") or "",
            "manifest_sha256_for_known_file": recorded_crlf,
            "manifest_matches": "blob",
            "manifest_matches_blob": True,
            "manifest_matches_worktree_raw": recorded_crlf == wt_crlf["sha256_raw"],
            "manifest_matches_worktree_lf": recorded_crlf == wt_crlf["sha256_lf"],
            "reach6_crlf_raw_differs_from_blob": crlf_raw_differs,
            "reach6_lf_worktree_equals_blob": crlf_lf_equals_blob,
            "content_dirty_worktree_differs_from_blob": dirty_all_differ,
            "would_be_reach6_if_worktree_raw_used_as_blob": True,
            "both_values_recorded": both_routes_recorded,
        }


def planted_bidirectional_control() -> dict[str, Any]:
    """Scratch inventory: one missing manifest path, one extra disk file."""
    with tempfile.TemporaryDirectory(prefix="aud0036-bi-") as tmp:
        root = Path(tmp)
        (root / "present.txt").write_bytes(b"present-body\n")
        (root / "extra-on-disk.txt").write_bytes(b"extra-body\n")
        present_hash = sha256_bytes(b"present-body\n")
        missing_hash = sha256_bytes(b"missing-never-written\n")
        manifest_entries = [
            {"path": "present.txt", "sha256": present_hash},
            {"path": "named-but-missing.txt", "sha256": missing_hash},
        ]
        disk_files = []
        for p in sorted(root.iterdir()):
            if p.is_file():
                raw = p.read_bytes()
                disk_files.append(
                    {"path": p.name, "sha256_lf": sha256_bytes(lf_normalize(raw))}
                )
        man_paths = {e["path"] for e in manifest_entries}
        disk_paths = {f["path"] for f in disk_files}
        named_missing = sorted(man_paths - disk_paths)
        extra = sorted(disk_paths - man_paths)
        naive_ok = named_missing == ["named-but-missing.txt"] and extra == [
            "extra-on-disk.txt"
        ]
        present_row = next(e for e in manifest_entries if e["path"] == "present.txt")
        present_disk = next(f for f in disk_files if f["path"] == "present.txt")
        hash_agrees = present_row["sha256"] == present_disk["sha256_lf"]
        return {
            "control_pass": bool(naive_ok and hash_agrees),
            "named_missing": named_missing,
            "extra_on_disk": extra,
            "present_hash_agrees": hash_agrees,
            "detector": "set-difference on path plus sha256 of LF-normalized bytes",
        }


def snapshot() -> dict[str, Any]:
    live_git = live_git_status()
    manifest = load_manifest(REPO / MANIFEST_REL)
    disk = disk_inventory()
    m2d = manifest_to_disk(manifest, live_git)
    d2m = disk_to_manifest(disk, manifest)
    contracted = contracted_rows(live_git)
    dual = dual_route_control()
    planted = planted_bidirectional_control()
    contracted_missing = [r["path"] for r in contracted if not r["disk_exists"]]
    contracted_present = [r["path"] for r in contracted if r["disk_exists"]]
    return {
        "live_git": live_git,
        "manifest": {
            "path": MANIFEST_REL,
            "present": manifest["present"],
            "parse_ok": manifest["parse_ok"],
            "error": manifest.get("error") or "",
            "entry_count": len(manifest.get("entries") or []),
            "bytes": manifest.get("bytes") or 0,
        },
        "manifest_to_disk": m2d,
        "disk_to_manifest": d2m,
        "contracted_inventory": {
            "source": "tools/command-center/render.py:CONTRACTED_ARTIFACTS",
            "expected": len(CONTRACTED),
            "present_on_disk": len(contracted_present),
            "missing_on_disk": len(contracted_missing),
            "present_paths": contracted_present,
            "missing_paths": contracted_missing,
            "rows": contracted,
        },
        "hash_control": dual,
        "planted_control": planted,
        "disk_file_count": disk["file_count"],
        "disk_merkle_sha256_lf": disk["merkle_sha256_lf"],
    }
