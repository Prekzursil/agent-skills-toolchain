#!/usr/bin/env python3
"""Worktree identity, dirty-surface, and sha256 preservation helpers for AUD-0002.

Preservation is a content-hash search. A sibling path with the same relative
name and different bytes is not proof the unique blob survives.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_ROOT = HERE / "fixtures" / "_scratch"

SEED_NAME = "AUD-0002-unique-seed.bin"
SEED_REL = f"only-here/{SEED_NAME}"
COPY_REL = f"preserved-copies/from-increment1-{SEED_NAME}"
SAME_PATH = "notes.md"
COMMON_PAYLOAD = b"AUD-0002-SHARED-COMMON-BYTES-v1\n"

# Catalog / WFA-0015 names for the 6 surviving trees after the 2026-08-09
# 20-to-6 cleanup. The five NEEDS-OWNER-DECISION gradings are named here;
# the original grading documents are not in this Linux copy.
SURVIVING = [
    {
        "name": "ast-integrate",
        "needs_owner_decision": False,
        "grading": "working-checkout",
        "same_repo_as": "agent-skills-toolchain",
        "windows_paths": ["C:/Users/Prekzursil/source/ast-integrate"],
    },
    {
        "name": "agent-skills-toolchain",
        "needs_owner_decision": True,
        "grading": "NEEDS-OWNER-DECISION",
        "same_repo_as": "agent-skills-toolchain",
        "windows_paths": ["C:/Users/Prekzursil/source/agent-skills-toolchain"],
    },
    {
        "name": "ast-harness-reconcile",
        "needs_owner_decision": True,
        "grading": "NEEDS-OWNER-DECISION",
        "same_repo_as": None,
        "windows_paths": ["C:/Users/Prekzursil/source/ast-harness-reconcile"],
    },
    {
        "name": "ast-statusline-capture",
        "needs_owner_decision": True,
        "grading": "NEEDS-OWNER-DECISION",
        "same_repo_as": None,
        "windows_paths": ["C:/Users/Prekzursil/source/ast-statusline-capture"],
    },
    {
        "name": "cookie-bridge-skill",
        "needs_owner_decision": True,
        "grading": "NEEDS-OWNER-DECISION",
        "same_repo_as": None,
        "windows_paths": ["C:/Users/Prekzursil/source/cookie-bridge-skill"],
    },
    {
        "name": "ast-increment1",
        "needs_owner_decision": True,
        "grading": "NEEDS-OWNER-DECISION",
        "same_repo_as": None,
        "windows_paths": [
            "C:/Users/Prekzursil/source/ast-increment1",
            "D:/inc1-wt/ast-increment1",
        ],
    },
]

ORIGIN = {
    "agent-skills-toolchain": "https://github.com/Prekzursil/agent-skills-toolchain.git",
    "ast-integrate": "https://github.com/Prekzursil/agent-skills-toolchain.git",
    "ast-harness-reconcile": "https://github.com/Prekzursil/ast-harness-reconcile.git",
    "ast-statusline-capture": "https://github.com/Prekzursil/ast-statusline-capture.git",
    "cookie-bridge-skill": "https://github.com/Prekzursil/cookie-bridge-skill.git",
    "ast-increment1": "https://github.com/Prekzursil/ast-increment1.git",
}

SKIP_DIR_NAMES = {".git", "__pycache__", ".cursor", "node_modules"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def seed_payload() -> bytes:
    return (
        b"AUD-0002-SEED-ONLY-IN-ONE-WORKTREE\n"
        + bytes(range(256))
        + b"\nend-seed\n"
    )


def git(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "AUD-0002",
            "GIT_AUTHOR_EMAIL": "aud-0002@invalid.local",
            "GIT_COMMITTER_NAME": "AUD-0002",
            "GIT_COMMITTER_EMAIL": "aud-0002@invalid.local",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    try:
        proc = subprocess.run(
            [
                "git",
                "-c",
                "user.name=AUD-0002",
                "-c",
                "user.email=aud-0002@invalid.local",
                "-c",
                "safe.directory=*",
                *args,
            ],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT git {' '.join(args)}"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def parse_porcelain_v2(raw: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line:
            continue
        tag = line[0]
        if tag in "12":
            fields = line.split(" ", 8)
            path = fields[8] if len(fields) > 8 else ""
            if tag == "2" and "\t" in path:
                path = path.split("\t", 1)[0]
            out.append({"path": path, "xy": fields[1] if len(fields) > 1 else "", "kind": "tracked-change"})
        elif tag == "?":
            out.append({"path": line[2:], "xy": "??", "kind": "untracked"})
        elif tag == "u":
            fields = line.split(" ", 10)
            out.append(
                {
                    "path": fields[10] if len(fields) > 10 else "",
                    "xy": fields[1] if len(fields) > 1 else "",
                    "kind": "unmerged",
                }
            )
    return out


def parse_worktree_list(raw: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            if cur:
                rows.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            if cur:
                rows.append(cur)
            cur = {"path": line[len("worktree ") :]}
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch ") :]
        elif line == "bare":
            cur["bare"] = "true"
        elif line == "detached":
            cur["detached"] = "true"
    if cur:
        rows.append(cur)
    return rows


def dirty_surface(wt: Path) -> dict[str, Any]:
    rc, raw = git(["status", "--porcelain=v2", "--untracked-files=all"], cwd=wt)
    entries = parse_porcelain_v2(raw) if rc == 0 else []
    tracked = [e for e in entries if e["kind"] != "untracked"]
    untracked = [e for e in entries if e["kind"] == "untracked"]
    return {
        "path": str(wt),
        "exit_code": rc,
        "raw": raw,
        "entries": entries,
        "dirty_tracked": len(tracked),
        "dirty_untracked": len(untracked),
        "tracked": tracked,
        "untracked": untracked,
    }


def origin_url(wt: Path) -> tuple[str | None, int, str]:
    rc, raw = git(["remote", "get-url", "origin"], cwd=wt)
    if rc != 0:
        return None, rc, raw
    return raw.splitlines()[0].strip() if raw else None, rc, raw


def walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if path.is_file() and not path.is_symlink():
                files.append(path)
    return files


def content_index(trees: dict[str, Path]) -> dict[str, list[dict[str, str]]]:
    """sha256 -> [{tree, relpath, bytes}, ...] across every file except .git."""
    index: dict[str, list[dict[str, str]]] = {}
    for name, root in trees.items():
        for path in walk_files(root):
            rel = path.relative_to(root).as_posix()
            data = path.read_bytes()
            digest = sha256_bytes(data)
            index.setdefault(digest, []).append(
                {"tree": name, "relpath": rel, "bytes": str(len(data))}
            )
    return index


def unique_files(wt: Path, dirty: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in dirty["entries"]:
        rel = entry["path"]
        if not rel or rel in seen:
            continue
        seen.add(rel)
        path = wt / rel
        if not path.is_file():
            rows.append(
                {
                    "relpath": rel,
                    "kind": entry["kind"],
                    "present": False,
                    "sha256": None,
                    "bytes": 0,
                }
            )
            continue
        data = path.read_bytes()
        rows.append(
            {
                "relpath": rel,
                "kind": entry["kind"],
                "present": True,
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            }
        )
    return rows


def preservation_for(
    tree_name: str,
    files: list[dict[str, Any]],
    index: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in files:
        digest = row.get("sha256")
        if not digest:
            out.append(
                {
                    **row,
                    "verdict": "NOT-CHECKED",
                    "reason": "file missing on disk",
                    "content_matches": [],
                    "same_path_elsewhere": [],
                }
            )
            continue
        matches = [
            m
            for m in index.get(digest, [])
            if not (m["tree"] == tree_name and m["relpath"] == row["relpath"])
        ]
        verdict = "PRESERVED" if matches else "UNPRESERVED"
        out.append(
            {
                **row,
                "verdict": verdict,
                "reason": (
                    "sha256 found in another tree or path"
                    if matches
                    else "sha256 not found outside this file"
                ),
                "content_matches": matches,
            }
        )
    return out


def path_name_matches(tree_name: str, relpath: str, trees: dict[str, Path]) -> list[str]:
    hits: list[str] = []
    for name, root in trees.items():
        if name == tree_name:
            continue
        other = root / relpath
        if other.is_file():
            hits.append(name)
    return hits


def _rmtree(path: Path) -> None:
    if not path.exists():
        return

    def onerror(func, p, _exc):  # noqa: ANN001
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onerror=onerror)


def _init_repo(path: Path, origin: str, files: dict[str, bytes]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    rc, raw = git(["init", "-b", "main"], cwd=path)
    if rc != 0:
        raise RuntimeError(f"git init failed in {path}: {raw}")
    for rel, data in files.items():
        dest = path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    rc, raw = git(["add", "-A"], cwd=path)
    if rc != 0:
        raise RuntimeError(f"git add failed in {path}: {raw}")
    rc, raw = git(["commit", "-m", "AUD-0002 fixture baseline"], cwd=path)
    if rc != 0:
        raise RuntimeError(f"git commit failed in {path}: {raw}")
    rc, raw = git(["remote", "add", "origin", origin], cwd=path)
    if rc != 0:
        raise RuntimeError(f"git remote add failed in {path}: {raw}")


def build_fixtures() -> dict[str, Path]:
    """Create 6 named trees: two worktrees of one repo + four sibling repos."""
    _rmtree(FIXTURE_ROOT)
    trees_dir = FIXTURE_ROOT / "trees"
    trees_dir.mkdir(parents=True, exist_ok=True)

    shared_files = {
        "README.md": b"# agent-skills-toolchain fixture\n",
        "shared/common.txt": COMMON_PAYLOAD,
        SAME_PATH: b"MAIN-NOTES-DIFFERENT-BYTES\n",
    }
    toolchain = trees_dir / "agent-skills-toolchain"
    _init_repo(toolchain, ORIGIN["agent-skills-toolchain"], shared_files)

    integrate = trees_dir / "ast-integrate"
    rc, raw = git(
        ["worktree", "add", "-b", "ast-integrate-wt", str(integrate)],
        cwd=toolchain,
    )
    if rc != 0:
        raise RuntimeError(f"git worktree add failed: {raw}")

    # Dirty tracked file only in the ast-integrate worktree.
    readme = integrate / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\n# worktree-local tracked edit\n")
    (integrate / "unique-ast-integrate.txt").write_bytes(
        b"UNIQUE-BYTES-AST-INTEGRATE-WORKTREE\n"
    )

    others = {
        "ast-harness-reconcile": {
            "README.md": b"# ast-harness-reconcile fixture\n",
        },
        "ast-statusline-capture": {
            "README.md": b"# ast-statusline-capture fixture\n",
        },
        "cookie-bridge-skill": {
            "README.md": b"# cookie-bridge-skill fixture\n",
        },
        "ast-increment1": {
            "README.md": b"# ast-increment1 fixture\n",
        },
    }
    for name, committed in others.items():
        _init_repo(trees_dir / name, ORIGIN[name], committed)

    # Same relative path, different bytes: path-name is not preservation.
    (trees_dir / "ast-harness-reconcile" / SAME_PATH).write_bytes(
        b"HARNESS-NOTES-UNIQUE-BYTES\n"
    )
    # Content-identical to main shared/common.txt at a different path.
    copy = trees_dir / "ast-statusline-capture" / "elsewhere" / "copy-of-common.txt"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(COMMON_PAYLOAD)
    # Tracked edit in cookie-bridge-skill.
    cb_readme = trees_dir / "cookie-bridge-skill" / "README.md"
    cb_readme.write_bytes(cb_readme.read_bytes() + b"\n# cookie dirty tracked\n")
    # Seed unique to ast-increment1 (control starts UNPRESERVED).
    seed = trees_dir / "ast-increment1" / SEED_REL
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_bytes(seed_payload())

    return {name: trees_dir / name for name in ORIGIN}


def copy_seed_to_main(trees: dict[str, Path]) -> Path:
    dest = trees["agent-skills-toolchain"] / COPY_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(seed_payload())
    return dest


def inspect_tree(name: str, root: Path, trees: dict[str, Path]) -> dict[str, Any]:
    dirty = dirty_surface(root)
    origin, origin_rc, origin_raw = origin_url(root)
    wt_rc, wt_raw = git(["worktree", "list", "--porcelain"], cwd=root)
    uniques = unique_files(root, dirty)
    index = content_index(trees)
    preserved = preservation_for(name, uniques, index)
    for row in preserved:
        row["same_path_elsewhere"] = path_name_matches(name, row["relpath"], trees)
        if row["verdict"] == "UNPRESERVED" and row["same_path_elsewhere"]:
            row["path_name_would_claim"] = "PRESERVED"
        else:
            row["path_name_would_claim"] = row["verdict"]
    return {
        "name": name,
        "path": str(root),
        "source": "fixture-recreation",
        "origin_url": origin,
        "origin_exit_code": origin_rc,
        "origin_raw": origin_raw,
        "worktree_list_exit_code": wt_rc,
        "worktree_list": parse_worktree_list(wt_raw) if wt_rc == 0 else [],
        "worktree_list_raw": wt_raw[:8000],
        "dirty_tracked": dirty["dirty_tracked"],
        "dirty_untracked": dirty["dirty_untracked"],
        "porcelain_exit_code": dirty["exit_code"],
        "porcelain_raw": dirty["raw"][:8000],
        "unique_file_count": len(uniques),
        "unique_files": preserved,
        "unpreserved_count": sum(1 for r in preserved if r["verdict"] == "UNPRESERVED"),
        "preserved_count": sum(1 for r in preserved if r["verdict"] == "PRESERVED"),
    }


def seed_verdict(trees: dict[str, Path]) -> str:
    index = content_index(trees)
    digest = sha256_bytes(seed_payload())
    matches = [
        m
        for m in index.get(digest, [])
        if not (m["tree"] == "ast-increment1" and m["relpath"] == SEED_REL)
    ]
    return "PRESERVED" if matches else "UNPRESERVED"


def run_preservation_control() -> dict[str, Any]:
    trees = build_fixtures()
    before = seed_verdict(trees)
    # Path-name strawman: notes.md exists on main with different bytes.
    harness_notes = trees["ast-harness-reconcile"] / SAME_PATH
    main_notes = trees["agent-skills-toolchain"] / SAME_PATH
    path_hit = main_notes.is_file() and harness_notes.is_file()
    same_bytes = (
        path_hit and sha256_file(main_notes) == sha256_file(harness_notes)
    )
    path_name_rejected = path_hit and not same_bytes

    copy_path = copy_seed_to_main(trees)
    after = seed_verdict(trees)
    return {
        "seed_path": (trees["ast-increment1"] / SEED_REL).as_posix(),
        "copy_path": copy_path.as_posix(),
        "copy_relpath": COPY_REL,
        "seed_sha256": sha256_bytes(seed_payload()),
        "unpreserved_before_copy": before == "UNPRESERVED",
        "preserved_after_copy": after == "PRESERVED",
        "before": before,
        "after": after,
        "flipped": before == "UNPRESERVED" and after == "PRESERVED",
        "path_name_match_rejected": path_name_rejected,
        "path_name_same_relpath": SAME_PATH,
        "path_name_same_bytes": same_bytes,
    }


def fixture_inventory() -> list[dict[str, Any]]:
    trees = build_fixtures()
    return [inspect_tree(name, path, trees) for name, path in trees.items()]


def candidate_live_paths(name: str, windows_paths: list[str]) -> list[str]:
    home = Path.home()
    out = [
        f"/opt/p2/{name}",
        str(home / "source" / name),
        str(home / "Documents" / "GitHub" / name),
        str(home / ".claude" / "agent-worktrees" / name),
    ]
    out.extend(windows_paths)
    # Dedup, keep order.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def live_host_scan() -> dict[str, Any]:
    cwd = Path(os.getcwd()) if os.getcwd() else REPO
    delivery = REPO
    rc_inside, raw_inside = git(["rev-parse", "--is-inside-work-tree"], cwd=delivery)
    git_worktree = rc_inside == 0 and "true" in raw_inside.lower()
    origin = None
    origin_raw = raw_inside
    if git_worktree:
        origin, _, origin_raw = origin_url(delivery)
    wt_rc, wt_raw = git(["worktree", "list", "--porcelain"], cwd=delivery)
    porcelain_rc, porcelain_raw = git(
        ["status", "--porcelain=v2", "--untracked-files=all"], cwd=delivery
    )

    found_git: list[str] = []
    opt = Path("/opt/p2")
    if opt.is_dir():
        for child in sorted(opt.iterdir()):
            if (child / ".git").exists():
                found_git.append(str(child))

    named_live: list[dict[str, Any]] = []
    present = 0
    absent = 0
    for spec in SURVIVING:
        name = spec["name"]
        candidates = candidate_live_paths(name, spec["windows_paths"])
        existing = [p for p in candidates if Path(p).exists()]
        gitish = [p for p in existing if (Path(p) / ".git").exists()]
        if gitish:
            present += 1
            status = "present-git"
        elif existing:
            absent += 1
            status = "present-not-git"
        else:
            absent += 1
            status = "absent"
        named_live.append(
            {
                "name": name,
                "grading": spec["grading"],
                "needs_owner_decision": spec["needs_owner_decision"],
                "status": status,
                "existing_paths": existing,
                "git_paths": gitish,
                "candidates_checked": candidates,
            }
        )

    return {
        "cwd": str(delivery),
        "git_worktree": git_worktree,
        "git_rev_parse_exit_code": rc_inside,
        "git_rev_parse_raw": raw_inside[:2000],
        "origin_url": origin,
        "origin_raw": origin_raw[:2000],
        "worktree_list_exit_code": wt_rc,
        "worktree_list_raw": wt_raw[:4000],
        "porcelain_exit_code": porcelain_rc,
        "porcelain_raw": porcelain_raw[:4000],
        "host_git_dirs_under_opt_p2": found_git,
        "named_surviving": named_live,
        "named_surviving_present": present,
        "named_surviving_absent": absent,
        "grading_documents": "INPUT-ABSENT on this Linux copy; names taken from WORK-UNIT-CATALOG WFA-0015 / AUD-0002 inputs",
    }


def not_present_row(spec: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    match = next(
        (r for r in live["named_surviving"] if r["name"] == spec["name"]),
        {},
    )
    return {
        "name": spec["name"],
        "source": "not-present",
        "origin_url": None,
        "dirty_tracked": 0,
        "dirty_untracked": 0,
        "unique_file_count": 0,
        "unpreserved_count": 0,
        "grading": spec["grading"],
        "needs_owner_decision": spec["needs_owner_decision"],
        "live_status": match.get("status"),
        "existing_paths": match.get("existing_paths") or [],
        "candidates_checked": match.get("candidates_checked") or [],
        "note": (
            "The 2026-08-09 surviving worktree is not a git checkout on this "
            "Linux delivery host; identity, dirty surface, and preservation "
            "are NOT-CHECKED for the live tree."
        ),
    }


def dump_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
