#!/usr/bin/env python3
"""AUD-0007 detectors: git remote -v vs git config --get-regexp remote.

Probe 1 lists fetch/push URLs (`git remote -v`). A remote section with no URL
prints a name and a tab and is treated as URL-empty.

Probe 2 reads every `remote.*` config key. A fetch refspec without a URL, or
`remote.pushDefault` with no remote, is invisible as a URL under probe 1 and
visible under probe 2 — that disagreement is the independence control.

Read-only against owner trees. Scratch control repos are created under
tempfile and destroyed. Never git add/commit/push/stash/checkout/rebase.
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
UNIT = "AUD-0007"
OUT_REL = "command-center/audit/AUD-0007-no-remote-repo-triage.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0007 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
OWNER_DECISION = "TRIAGE FIRST, report, owner decides"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0007/probe1_remote_v.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0007/probe2_config_regexp.py"
)
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".cursor",
        ".grok",
        ".ssh",
        ".local",
        ".npm",
        ".cache",
        ".pytest_cache",
        ".mypy_cache",
        "unit-locks",
        "workers",
        "dist",
        "build",
    }
)
_VALIDATOR = None
READ_CAP = 65536
PATH_CAP = 200


def git(root: Path, *args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT git {' '.join(args)}"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_remote_v(raw: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if "\t" not in line:
            rows.append({"name": line.strip(), "url": "", "kind": "unknown"})
            continue
        name, rest = line.split("\t", 1)
        kind = ""
        url = rest
        if rest.endswith(" (fetch)"):
            kind = "fetch"
            url = rest[: -len(" (fetch)")]
        elif rest.endswith(" (push)"):
            kind = "push"
            url = rest[: -len(" (push)")]
        rows.append({"name": name, "url": url.strip(), "kind": kind})
    return rows


def probe1_remote_v(root: Path) -> dict[str, Any]:
    """URL-listing detector. Empty URL list => probe1 no-remote."""
    rc, raw = git(root, "remote", "-v")
    lines = parse_remote_v(raw)
    urls = [r for r in lines if r["url"]]
    return {
        "command": "git remote -v",
        "cwd": str(root),
        "rc": rc,
        "raw": raw,
        "lines": lines,
        "url_count": len(urls),
        "no_remote": rc in (0, 1) and len(urls) == 0,
    }


def probe2_config_regexp(root: Path) -> dict[str, Any]:
    """Config-key detector. Any remote.* key => not remote-less."""
    rc, raw = git(root, "config", "--get-regexp", r"^remote\.")
    keys = [ln for ln in raw.splitlines() if ln.strip() and not ln.startswith("TIMEOUT")]
    return {
        "command": "git config --get-regexp ^remote\\.",
        "cwd": str(root),
        "rc": rc,
        "raw": raw,
        "keys": keys,
        "key_count": len(keys),
        "has_remote_config": rc == 0 and len(keys) > 0,
    }


def classify(p1: dict[str, Any], p2: dict[str, Any]) -> str:
    if p1["no_remote"] and not p2["has_remote_config"]:
        return "no-remote"
    if p1["no_remote"] and p2["has_remote_config"]:
        return "probe1-empty-probe2-config"
    if not p1["no_remote"] and p2["has_remote_config"]:
        return "has-remote"
    return "probe1-url-probe2-empty"


def repo_identity(root: Path) -> dict[str, Any]:
    rc_count, count_raw = git(root, "rev-list", "--count", "--all")
    commit_count: int | None
    if rc_count == 0:
        try:
            commit_count = int(count_raw.strip().splitlines()[-1])
        except (ValueError, IndexError):
            commit_count = None
    else:
        commit_count = 0 if "does not have any commits" in count_raw.lower() else None
    rc_log, log_raw = git(root, "log", "-1", "--format=%cI", "--all")
    last_commit = log_raw.strip().splitlines()[0] if rc_log == 0 and log_raw.strip() else None
    rc_ls, ls_raw = git(root, "ls-files", "-z")
    paths = [p for p in ls_raw.split("\0") if p] if rc_ls == 0 else []
    return {
        "commit_count": commit_count,
        "last_commit_date": last_commit,
        "tracked_path_count": len(paths),
        "tracked_paths_head": paths[:PATH_CAP],
        "rev_list_rc": rc_count,
        "log_rc": rc_log,
        "ls_files_rc": rc_ls,
    }


def _file_sha256(path: Path) -> str | None:
    try:
        data = path.read_bytes()[:READ_CAP]
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()


def unique_path_surface(root: Path, comparison_hashes: set[str]) -> dict[str, Any]:
    ident = repo_identity(root)
    unique: list[dict[str, Any]] = []
    shared = 0
    missing = 0
    for rel in ident["tracked_paths_head"]:
        fp = root / rel
        digest = _file_sha256(fp)
        if digest is None:
            missing += 1
            continue
        if digest in comparison_hashes:
            shared += 1
            continue
        unique.append({"path": rel, "sha256_prefix": digest[:16]})
        comparison_hashes.add(digest)
    return {
        "tracked_considered": len(ident["tracked_paths_head"]),
        "unique_count": len(unique),
        "shared_content_count": shared,
        "unreadable_count": missing,
        "unique_paths": unique[:PATH_CAP],
    }


def comparison_hash_set(repo: Path, limit: int = 4000) -> set[str]:
    """Content hashes from this unversioned worktree (not a git object db)."""
    out: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".git")]
        for name in filenames:
            if len(out) >= limit:
                return out
            fp = Path(dirpath) / name
            digest = _file_sha256(fp)
            if digest:
                out.add(digest)
    return out


def discover_git_repos(roots: list[Path]) -> dict[str, Any]:
    found: list[str] = []
    dirs_visited = 0
    skipped = 0
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirs_visited += 1
            git_here = False
            if ".git" in dirnames or ".git" in filenames:
                git_here = True
            if git_here:
                rel_or_abs = str(Path(dirpath))
                if rel_or_abs not in seen:
                    seen.add(rel_or_abs)
                    found.append(rel_or_abs)
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            skipped += sum(1 for d in list(dirnames) if False)
    confirmed: list[str] = []
    rejected: list[dict[str, str]] = []
    for path in found:
        rc, raw = git(Path(path), "rev-parse", "--is-inside-work-tree")
        if rc == 0 and "true" in raw.lower():
            confirmed.append(path)
        else:
            rejected.append({"path": path, "rev_parse": raw.strip()[:200]})
    return {
        "roots": [str(r) for r in roots],
        "dirs_visited": dirs_visited,
        "git_markers_found": len(found),
        "confirmed_worktrees": confirmed,
        "rejected_markers": rejected,
    }


def default_scan_roots() -> list[Path]:
    roots = [REPO]
    opt = Path("/opt/p2")
    if not opt.is_dir():
        return roots
    opt_r = opt.resolve()
    repo_r = REPO.resolve()
    if opt_r == repo_r:
        return roots
    try:
        repo_r.relative_to(opt_r)
        return [opt]
    except ValueError:
        roots.append(opt)
        return roots


def inspect_repo(root: Path, comparison_hashes: set[str]) -> dict[str, Any]:
    p1 = probe1_remote_v(root)
    p2 = probe2_config_regexp(root)
    bucket = classify(p1, p2)
    ident = repo_identity(root)
    unique = (
        unique_path_surface(root, comparison_hashes)
        if bucket == "no-remote"
        else None
    )
    disposition = disposition_for(bucket, ident, unique)
    return {
        "path": str(root),
        "rel_to_worktree": _rel_or_abs(root),
        "probe1_no_remote": p1["no_remote"],
        "probe1_url_count": p1["url_count"],
        "probe1_raw": p1["raw"][:4000],
        "probe2_has_remote_config": p2["has_remote_config"],
        "probe2_key_count": p2["key_count"],
        "probe2_raw": p2["raw"][:4000],
        "classification": bucket,
        "commit_count": ident["commit_count"],
        "last_commit_date": ident["last_commit_date"],
        "tracked_path_count": ident["tracked_path_count"],
        "unique_path_surface": unique,
        "recommended_disposition": disposition,
        "owner_action_taken": False,
        "remote_created": False,
        "pushed": False,
    }


def _rel_or_abs(root: Path) -> str:
    try:
        return root.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(root)


def disposition_for(
    bucket: str, ident: dict[str, Any], unique: dict[str, Any] | None
) -> str:
    if bucket == "has-remote":
        return "HAS-REMOTE — no triage as no-remote; leave remotes untouched"
    if bucket == "probe1-empty-probe2-config":
        return (
            "NOT remote-less — probe 1 URL list is empty but remote.* config "
            "exists. TRIAGE FIRST; do not create remotes."
        )
    if bucket == "probe1-url-probe2-empty":
        return (
            "ANOMALY — git remote -v listed a URL but git config --get-regexp "
            "remote did not. TRIAGE FIRST; do not create remotes."
        )
    unique_n = (unique or {}).get("unique_count") or 0
    tracked = ident.get("tracked_path_count") or 0
    if unique_n > 0:
        return (
            "NO-REMOTE with unique tracked content "
            f"(unique_paths={unique_n}, tracked={tracked}). "
            "PRESERVE content; TRIAGE FIRST; owner decides; never create remotes."
        )
    if tracked > 0:
        return (
            "NO-REMOTE; tracked paths share content with the comparison corpus. "
            "Owner may retire only after confirming preservation. TRIAGE FIRST."
        )
    return (
        "NO-REMOTE empty or unborn repository. TRIAGE FIRST; owner decides; "
        "never create remotes."
    )


def plant_control_repos(base: Path) -> dict[str, Path]:
    """Three scratch repos. No commits. No network."""
    a = base / "true-noremote"
    b = base / "url-less-fetch"
    c = base / "fetch-less-url"
    for d in (a, b, c):
        d.mkdir(parents=True, exist_ok=True)
        rc, raw = git(d, "init", "-q")
        if rc != 0:
            raise RuntimeError(f"git init failed in {d}: {raw}")
        git(d, "config", "user.email", "aud-0007-control@invalid")
        git(d, "config", "user.name", "AUD-0007 control")
    # B: remote section with fetch refspec and no URL — remote -v has no URL.
    rc, raw = git(b, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    if rc != 0:
        raise RuntimeError(f"plant B failed: {raw}")
    # C: fetch-less remote (URL, no fetch). Both probes must see it.
    rc, raw = git(c, "config", "remote.origin.url", "https://example.invalid/aud-0007.git")
    if rc != 0:
        raise RuntimeError(f"plant C failed: {raw}")
    return {"true-noremote": a, "url-less-fetch": b, "fetch-less-url": c}


def independence_control() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aud0007-ctl-") as tmp:
        plants = plant_control_repos(Path(tmp))
        rows = {}
        for name, path in plants.items():
            p1 = probe1_remote_v(path)
            p2 = probe2_config_regexp(path)
            rows[name] = {
                "path": str(path),
                "probe1_no_remote": p1["no_remote"],
                "probe1_url_count": p1["url_count"],
                "probe1_raw": p1["raw"],
                "probe2_has_remote_config": p2["has_remote_config"],
                "probe2_keys": p2["keys"],
                "probe2_raw": p2["raw"],
                "classification": classify(p1, p2),
            }
        a, b, c = rows["true-noremote"], rows["url-less-fetch"], rows["fetch-less-url"]
        independent = (
            b["probe1_no_remote"] is True
            and b["probe2_has_remote_config"] is True
            and b["classification"] == "probe1-empty-probe2-config"
        )
        same_on_plant = b["probe1_no_remote"] == (not b["probe2_has_remote_config"])
        true_noremote_ok = (
            a["probe1_no_remote"] is True
            and a["probe2_has_remote_config"] is False
            and a["classification"] == "no-remote"
        )
        fetchless_url_visible = (
            c["probe1_no_remote"] is False
            and c["probe2_has_remote_config"] is True
            and c["classification"] == "has-remote"
        )
        pass_ctl = independent and true_noremote_ok and fetchless_url_visible and not same_on_plant
        return {
            "id": "AUD-0007-C1",
            "plants": rows,
            "independent": independent,
            "same_fingerprint_on_url_less_plant": same_on_plant,
            "true_noremote_both_agree": true_noremote_ok,
            "fetch_less_url_visible_to_both": fetchless_url_visible,
            "pass": pass_ctl,
            "note": (
                "Catalog asks to add a fetch-less remote such that probe 1 reports "
                "no-remote while probe 2 sees config. On this git, a URL-only "
                "(fetch-less) remote is listed by git remote -v. The disagreement "
                "the row describes is produced by a remote.* fetch refspec without "
                "a URL (url-less remote). The URL-only plant is the opposite "
                "control: both probes must see it, or probe 1 is blind."
            ),
        }


def live_inventory() -> dict[str, Any]:
    roots = default_scan_roots()
    discovery = discover_git_repos(roots)
    confirmed = discovery["confirmed_worktrees"]
    hashes: set[str] = comparison_hash_set(REPO) if confirmed else set()
    repos = [inspect_repo(Path(p), hashes) for p in confirmed]
    no_remote = [r for r in repos if r["classification"] == "no-remote"]
    disagreement = [r for r in repos if r["classification"] == "probe1-empty-probe2-config"]
    has_remote = [r for r in repos if r["classification"] == "has-remote"]
    return {
        "worktree": str(REPO),
        "worktree_is_git": (REPO / ".git").exists(),
        "discovery": discovery,
        "repos": repos,
        "counts": {
            "confirmed_worktrees": len(repos),
            "no_remote": len(no_remote),
            "probe1_empty_probe2_config": len(disagreement),
            "has_remote": len(has_remote),
        },
        "no_remote_repos": no_remote,
        "probe1_empty_probe2_config_repos": disagreement,
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def load_schema() -> dict[str, Any]:
    path = REPO / SCHEMA_REL
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in (
        SCHEMA_REL,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        sid = doc.get("$id")
        if sid:
            store[str(sid)] = doc
    return store


def validator():
    """Offline Draft 2020-12 validator. Does not fetch ast-integrate.invalid."""
    global _VALIDATOR
    if _VALIDATOR is None:
        from jsonschema import Draft202012Validator, RefResolver

        store = _schema_store()
        schema = store["https://ast-integrate.invalid/" + SCHEMA_REL]
        resolver = RefResolver(
            base_uri=str(schema["$id"]), referrer=schema, store=store
        )
        _VALIDATOR = Draft202012Validator(schema, resolver=resolver)
    return _VALIDATOR


def validate_doc(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    try:
        v = validator()
    except Exception as exc:  # noqa: BLE001 — surface resolver/schema load failures
        return [f"validator-init:{type(exc).__name__}: {exc}"]
    for err in v.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def named_probes_of(doc: dict[str, Any]) -> list[Any]:
    np = doc.get("named_probes")
    if isinstance(np, list) and np:
        return np
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    np = ext.get("named_probes")
    return np if isinstance(np, list) else []


def artifact_row(rel: str, role: str) -> dict[str, Any]:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }
