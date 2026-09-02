#!/usr/bin/env python3
"""WFA-0016 sweep engine: published releases vs tag trees vs candidate registry.

Evidence A: release-asset inventory (size + digest per asset).
Evidence B: tag tree via `git rev-list -n 1 <tag>` + `git cat-file -p` /
`git ls-tree` (never `tag^{commit}`, never `git archive`).

An empty asset is classified EMPTY (not skipped). A repo with zero releases
is an explicit ZERO_RELEASES row (not a silent pass).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import posixpath
import re
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARET_REF = re.compile(r"\^")
WORKFLOW_NAME_RE = re.compile(
    r"(workflow|preset|blueprint|skill\.md|\.github/workflows)",
    re.IGNORECASE,
)
WORKFLOW_ID_RE = re.compile(
    r'"(?:id|name|workflow_id)"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def powershell_caret_mangle(ref: str) -> str:
    """Approximate PowerShell `^` escape: `tag^{commit}` becomes `tag{commit}`."""
    out: list[str] = []
    i = 0
    while i < len(ref):
        if ref[i] == "^" and i + 1 < len(ref):
            out.append(ref[i + 1])
            i += 2
            continue
        out.append(ref[i])
        i += 1
    return "".join(out)


def assert_no_caret(ref: str) -> str:
    if CARET_REF.search(ref or ""):
        raise ValueError(
            f"caret-ref-forbidden: {ref!r} is a PowerShell data-corruption class; "
            "use git rev-list -n 1 <tag>"
        )
    return ref


def run_git(repo: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    for a in args:
        if "^" in str(a):
            raise ValueError(f"caret-ref-forbidden in git argv: {args!r}")
    env = os.environ.copy()
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    p = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        raise RuntimeError(f"git {args} rc={p.returncode} {err[:400]}")
    return p


def deref_tag(repo: Path, tag: str) -> str:
    """Commit SHA for tag. Never uses the caret peel form."""
    tag = assert_no_caret(tag)
    p = run_git(repo, ["rev-list", "-n", "1", tag])
    sha = (p.stdout or "").strip().splitlines()[0] if p.stdout else ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError(f"deref failed for {tag}: {sha!r}")
    return sha


def ls_tree(repo: Path, commit: str) -> list[dict]:
    commit = assert_no_caret(commit)
    p = run_git(repo, ["ls-tree", "-r", "--full-tree", commit])
    rows: list[dict] = []
    for line in (p.stdout or "").splitlines():
        # <mode> <type> <sha>\t<path>
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3:
            continue
        rows.append(
            {
                "mode": parts[0],
                "type": parts[1],
                "object": parts[2],
                "path": path,
            }
        )
    return rows


def cat_file(repo: Path, commit: str, path: str) -> bytes:
    commit = assert_no_caret(commit)
    spec = f"{commit}:{path}"
    env = os.environ.copy()
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    p = subprocess.run(
        ["git", "cat-file", "-p", spec],
        cwd=str(repo),
        capture_output=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"cat-file {spec} rc={p.returncode} {err[:300]}")
    return p.stdout


def is_workflowish_path(path: str) -> bool:
    n = path.replace("\\", "/")
    if WORKFLOW_NAME_RE.search(n):
        return True
    return n.endswith((".json", ".yml", ".yaml", ".md")) and any(
        part in n.lower()
        for part in ("wf-", "workflow", "preset", "blueprint", "skill")
    )


def extract_ids_from_bytes(raw: bytes) -> list[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return []
    ids = list(dict.fromkeys(WORKFLOW_ID_RE.findall(text)))
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return ids
    if isinstance(doc, dict):
        for key in ("id", "name", "workflow_id"):
            v = doc.get(key)
            if isinstance(v, str) and v and v not in ids:
                ids.append(v)
        recs = doc.get("candidates") or doc.get("workflows") or doc.get("records")
        if isinstance(recs, list):
            for rec in recs:
                if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                    if rec["id"] not in ids:
                        ids.append(rec["id"])
    return ids


def tree_workflow_map(repo: Path, commit: str) -> dict[str, dict]:
    out: dict[str, dict] = []
    mapping: dict[str, dict] = {}
    for row in ls_tree(repo, commit):
        if row["type"] != "blob":
            continue
        path = row["path"]
        if not is_workflowish_path(path):
            continue
        raw = cat_file(repo, commit, path)
        mapping[path] = {
            "path": path,
            "bytes": len(raw.replace(b"\r\n", b"\n")),
            "sha256": sha256_bytes(raw),
            "ids": extract_ids_from_bytes(raw),
        }
    return mapping


def unpack_asset(name: str, raw: bytes) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    lower = name.lower()
    if lower.endswith(".zip") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                files[info.filename.replace("\\", "/")] = zf.read(info)
        return files
    files[posixpath.basename(name) or "asset.bin"] = raw
    return files


def classify_asset(name: str, raw: bytes | None, size: int | None = None) -> dict:
    nbytes = 0 if raw is None else len(raw)
    if size is not None:
        nbytes = int(size)
    if raw is None or nbytes == 0 or len(raw or b"") == 0:
        return {
            "name": name,
            "classification": "EMPTY",
            "bytes": 0,
            "sha256": sha256_bytes(b""),
            "workflow_ids": [],
            "files": [],
            "skipped": False,
        }
    files = unpack_asset(name, raw)
    wf_files = []
    ids: list[str] = []
    for path, blob in sorted(files.items()):
        if not is_workflowish_path(path) and not path.endswith(".json"):
            continue
        rec = {
            "path": path,
            "bytes": len(blob.replace(b"\r\n", b"\n")),
            "sha256": sha256_bytes(blob),
            "ids": extract_ids_from_bytes(blob),
        }
        wf_files.append(rec)
        for i in rec["ids"]:
            if i not in ids:
                ids.append(i)
    return {
        "name": name,
        "classification": "PRESENT",
        "bytes": len(raw.replace(b"\r\n", b"\n")),
        "sha256": sha256_bytes(raw),
        "workflow_ids": ids,
        "files": wf_files,
        "skipped": False,
        "unpacked_file_count": len(files),
    }


def compare_asset_to_tree(asset: dict, tree: dict[str, dict]) -> dict:
    if asset.get("classification") == "EMPTY":
        return {
            "verdict": "EMPTY",
            "mismatches": [],
            "matched": [],
            "packaging_finding": False,
        }
    mismatches: list[dict] = []
    matched: list[str] = []
    asset_files = {f["path"]: f for f in (asset.get("files") or []) if isinstance(f, dict)}
    # Match on basename if zip uses a prefix.
    tree_by_base = {posixpath.basename(p): (p, rec) for p, rec in tree.items()}
    for path, rec in asset_files.items():
        tree_rec = tree.get(path)
        if tree_rec is None:
            base = posixpath.basename(path)
            if base in tree_by_base:
                tpath, tree_rec = tree_by_base[base]
            else:
                mismatches.append(
                    {
                        "path": path,
                        "reason": "asset-file-absent-from-tag-tree",
                        "asset_sha256": rec.get("sha256"),
                    }
                )
                continue
        if rec.get("sha256") != tree_rec.get("sha256"):
            mismatches.append(
                {
                    "path": path,
                    "reason": "asset-bytes-differ-from-tag-tree",
                    "asset_sha256": rec.get("sha256"),
                    "tree_sha256": tree_rec.get("sha256"),
                }
            )
        else:
            matched.append(path)
    verdict = "PACKAGING_MISMATCH" if mismatches else "MATCH"
    return {
        "verdict": verdict,
        "mismatches": mismatches,
        "matched": matched,
        "packaging_finding": bool(mismatches),
    }


def load_registry(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {
            "status": "ABSENT",
            "path": str(path) if path else None,
            "ids": [],
            "n": 0,
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    recs = []
    if isinstance(doc, dict):
        recs = doc.get("candidates") or doc.get("records") or doc.get("workflows") or []
        if not recs and isinstance(doc.get("id"), str):
            recs = [doc]
    elif isinstance(doc, list):
        recs = doc
    ids = []
    names = []
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id") or rec.get("name")
        if isinstance(rid, str) and rid:
            ids.append(rid)
        nm = rec.get("name")
        if isinstance(nm, str) and nm:
            names.append(nm)
    return {
        "status": "LOADED",
        "path": str(path).replace("\\", "/"),
        "ids": ids,
        "names": names,
        "n": len(ids),
        "sha256": sha256_bytes(path.read_bytes()),
        "bytes": path.stat().st_size,
    }


def join_registry(workflow_ids: list[str], registry: dict) -> dict:
    known = set(registry.get("ids") or []) | set(registry.get("names") or [])
    omitted = [i for i in workflow_ids if i not in known]
    listed = [i for i in workflow_ids if i in known]
    return {
        "shipped_ids": list(workflow_ids),
        "listed_in_registry": listed,
        "omitted_from_registry": omitted,
        "registry_n": registry.get("n") or 0,
        "registry_status": registry.get("status"),
    }


def sweep_repo(spec: dict, registry: dict) -> dict:
    """spec keys: name, git_dir, releases[{tag, assets[{name, bytes}]}], tags[str]."""
    git_dir = Path(spec["git_dir"])
    name = spec["name"]
    releases = list(spec.get("releases") or [])
    tags = list(spec.get("tags") or [])
    tag_rows = []
    for tag in tags:
        sha = deref_tag(git_dir, tag)
        tree = tree_workflow_map(git_dir, sha)
        tag_rows.append(
            {
                "tag": tag,
                "commit": sha,
                "deref_command": ["git", "rev-list", "-n", "1", tag],
                "caret_form_used": False,
                "workflow_files": list(tree.values()),
            }
        )
    tree_by_tag = {}
    for row in tag_rows:
        tree_by_tag[row["tag"]] = {
            f["path"]: f for f in row["workflow_files"]
        }
        for f in row["workflow_files"]:
            base = posixpath.basename(f["path"])
            tree_by_tag[row["tag"]].setdefault(base, f)

    release_rows = []
    all_ids: list[str] = []
    empty_assets = 0
    packaging = 0
    omitted: list[dict] = []
    if not releases:
        repo_class = "ZERO_RELEASES"
    else:
        repo_class = "HAS_RELEASES"
    for rel in releases:
        tag = rel.get("tag") or rel.get("tag_name") or ""
        assets_out = []
        tree = tree_by_tag.get(tag) or {}
        for asset in rel.get("assets") or []:
            raw = asset.get("bytes_payload")
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            classified = classify_asset(
                str(asset.get("name") or "unnamed"),
                raw,
                size=asset.get("size"),
            )
            if classified["classification"] == "EMPTY":
                empty_assets += 1
            cmp = compare_asset_to_tree(classified, tree) if tag else {
                "verdict": "NO_TAG",
                "mismatches": [],
                "matched": [],
                "packaging_finding": False,
            }
            if cmp.get("packaging_finding"):
                packaging += 1
            join = join_registry(classified.get("workflow_ids") or [], registry)
            for oid in join["omitted_from_registry"]:
                omitted.append(
                    {
                        "repo": name,
                        "tag": tag,
                        "asset": classified["name"],
                        "id": oid,
                    }
                )
            for i in classified.get("workflow_ids") or []:
                if i not in all_ids:
                    all_ids.append(i)
            assets_out.append(
                {
                    "name": classified["name"],
                    "classification": classified["classification"],
                    "bytes": classified["bytes"],
                    "sha256": classified["sha256"],
                    "workflow_ids": classified.get("workflow_ids") or [],
                    "files": classified.get("files") or [],
                    "tag_compare": cmp,
                    "registry_join": join,
                    "skipped": False,
                }
            )
        release_rows.append(
            {
                "tag": tag,
                "name": rel.get("name") or tag,
                "asset_count": len(assets_out),
                "assets": assets_out,
            }
        )
    return {
        "name": name,
        "classification": repo_class,
        "release_count": len(releases),
        "tag_count": len(tags),
        "empty_asset_count": empty_assets,
        "packaging_finding_count": packaging,
        "shipped_workflow_ids": all_ids,
        "omitted_from_registry": omitted,
        "tags": tag_rows,
        "releases": release_rows,
        "zero_releases_explicit": repo_class == "ZERO_RELEASES",
    }


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wfa-0016-sweep",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (
        os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_API_TOKEN")
        or ""
    ).strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_get(url: str, retries: int = 3) -> tuple[int, Any, str]:
    """GET JSON. Never logs Authorization. Returns (status, body, error_class)."""
    last_err = "untried"
    for i in range(retries):
        req = urllib.request.Request(url, headers=github_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                status = getattr(resp, "status", 200)
                try:
                    return status, json.loads(raw.decode("utf-8")), "ok"
                except json.JSONDecodeError:
                    return status, None, "unparseable-json"
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            last_err = f"http-{status}"
            if status in {429, 500, 502, 503, 504} and i + 1 < retries:
                time.sleep((2**i) + 0.25)
                continue
            if 400 <= status < 500 and status != 429:
                return status, None, last_err
            return status, None, last_err
        except urllib.error.URLError:
            last_err = "network-unreachable"
            if i + 1 < retries:
                time.sleep((2**i) + 0.25)
                continue
            return 0, None, last_err
        except TimeoutError:
            last_err = "timeout"
            if i + 1 < retries:
                time.sleep((2**i) + 0.25)
                continue
            return 0, None, last_err
    return 0, None, last_err


def live_github_sweep(owner_candidates: list[str], registry: dict, repo_limit: int = 8) -> dict:
    owners_tried = []
    repos_out = []
    errors = []
    for owner in owner_candidates:
        if not owner:
            continue
        status, body, cls = github_get(
            f"https://api.github.com/users/{owner}/repos?per_page=30&type=owner&sort=updated"
        )
        owners_tried.append({"owner": owner, "status": status, "class": cls})
        if cls != "ok" or not isinstance(body, list):
            errors.append({"owner": owner, "class": cls, "status": status})
            continue
        for repo in body[:repo_limit]:
            if not isinstance(repo, dict):
                continue
            full = str(repo.get("full_name") or "")
            rstatus, releases, rcls = github_get(
                f"https://api.github.com/repos/{full}/releases?per_page=10"
            )
            tstatus, tags, tcls = github_get(
                f"https://api.github.com/repos/{full}/tags?per_page=10"
            )
            rel_list = releases if isinstance(releases, list) else []
            tag_list = tags if isinstance(tags, list) else []
            assets = []
            empty = 0
            for rel in rel_list:
                if not isinstance(rel, dict):
                    continue
                for asset in rel.get("assets") or []:
                    if not isinstance(asset, dict):
                        continue
                    size = int(asset.get("size") or 0)
                    cls_a = "EMPTY" if size == 0 else "PRESENT"
                    if cls_a == "EMPTY":
                        empty += 1
                    assets.append(
                        {
                            "release": rel.get("tag_name") or rel.get("name"),
                            "name": asset.get("name"),
                            "bytes": size,
                            "digest": asset.get("digest") or asset.get("sha256"),
                            "content_type": asset.get("content_type"),
                            "classification": cls_a,
                            "skipped": False,
                            "browser_download_url_present": bool(
                                asset.get("browser_download_url")
                            ),
                        }
                    )
            repo_class = "ZERO_RELEASES" if not rel_list else "HAS_RELEASES"
            repos_out.append(
                {
                    "full_name": full,
                    "classification": repo_class,
                    "release_count": len(rel_list),
                    "tag_count": len(tag_list) if isinstance(tag_list, list) else 0,
                    "empty_asset_count": empty,
                    "zero_releases_explicit": repo_class == "ZERO_RELEASES",
                    "releases_api_class": rcls,
                    "tags_api_class": tcls,
                    "assets": assets,
                    "tag_names": [
                        t.get("name") for t in (tag_list or []) if isinstance(t, dict)
                    ][:10],
                }
            )
        if repos_out:
            break
    return {
        "attempted": True,
        "owners_tried": owners_tried,
        "repo_count": len(repos_out),
        "repos": repos_out,
        "errors": errors,
        "registry_join_note": (
            "Live GitHub asset bytes were not downloaded (read-only metadata sweep). "
            "Per-asset size and API digest are evidence A. Fixture git world is the "
            "mechanically independent evidence-B byte compare (git cat-file vs zip)."
        ),
        "zero_release_repos": [
            r["full_name"] for r in repos_out if r.get("classification") == "ZERO_RELEASES"
        ],
    }


def environment_record() -> dict:
    import platform
    import sys

    git_ver = ""
    try:
        p = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, timeout=10
        )
        git_ver = (p.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        git_ver = "unavailable"
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "git": git_ver,
        "cwd_is_git": (Path.cwd() / ".git").exists(),
        "ts": utc_now(),
    }
