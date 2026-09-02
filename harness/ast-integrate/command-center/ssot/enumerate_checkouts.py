"""Enumerate every checkout of agent-skills-toolchain by IDENTITY, not by NAME.

Why this exists
---------------
`sweep_all_checkouts.py` produced the inventory's "25 checkouts across 18 object stores".
Its identity test is:

    if TARGET not in origin.lower() and TARGET not in common.lower(): continue

i.e. a checkout counts only if the literal string "agent-skills-toolchain" appears in its
remote URL or in its git-common-dir path. That is a test for the repo's NAME appearing in a
path, standing in for a test of what the repo IS. It is blind to:

  * a clone with NO remote (nothing to match) whose directory is named something else
  * a `git init`-only working copy (no commits, no remote, no object store to name)
  * any checkout somebody renamed

`NO-REMOTE-REPO-TRIAGE.md` found two live examples under `~/source/_advver_M14/` -- `chk`
(1 commit, 7,763 tracked files) and `scratch` (0 commits, 7,802 files, 99 MB). Both are
working copies of this repo; neither is in the inventory. The walk DID reach them (depth 3,
well inside MAXDEPTH=7) -- the identity test rejected them.

Three mechanically independent signals are computed here, and a checkout counts if ANY fires:

  NAME     the original test, kept so the delta against the inventory is attributable
  HISTORY  the object store contains canonical's root commit 66e383dd. Independent of every
           path and URL; survives renames and missing remotes. Cannot see a 0-commit repo.
  CONTENT  blobs of sentinel working-tree files are members of canonical's reachable object
           set. This is the only signal that can identify a `git init`-only working copy,
           because it reads bytes rather than refs.

Read-only. Writes one JSON report under command-center/ssot/.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
ROOT_COMMIT = "66e383dd97e4e53bd34085636f9b2a2f83efce02"
TARGET = "agent-skills-toolchain"
OUT = Path(__file__).resolve().parent / "enumerate-checkouts.json"
PRIOR = Path(__file__).resolve().parent / "all25.json"

ROOTS = ["C:/Users/Prekzursil", "D:/"]
SKIP = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "AppData",
    "$Recycle.Bin",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    ".cache",
    "site-packages",
    "System Volume Information",
    ".ruff_cache",
    ".pytest_cache",
    "OneDrive",
}
MAXDEPTH = 7

# Files distinctive enough that a blob match means "this is a working copy of this repo".
SENTINELS = [
    "AGENTS.md",
    "README.md",
    "package.json",
    "ruff.toml",
    "REPO-TOPOLOGY.md",
    "CLAUDE.md",
]


def git(repo, *a):
    p = subprocess.run(
        ["git", "-C", str(repo), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def git_hash(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def content_hashes(data: bytes) -> list[str]:
    """Both the raw hash and the LF-normalised hash.

    The working tree on this box is CRLF; git stores LF. Hashing working-tree bytes and
    comparing against the object store therefore MISSES every text file. Measured: the
    positive control (canonical's own AGENTS.md against canonical's own reachable set)
    returned False -- a content signal that could never fire, which would have silently
    re-created the very blind spot this file exists to close, because a 0-commit working
    copy is findable by NO other signal. windows-shell.md sec.8b, reproduced inside the
    tool written to avoid it.
    """
    out = [git_hash(data)]
    lf = data.replace(b"\r\n", b"\n")
    if lf != data:
        out.append(git_hash(lf))
    return out


def canonical_reachable() -> set[str]:
    p = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=str(CANONICAL),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        line.split(" ", 1)[0].strip()
        for line in p.stdout.splitlines()
        if len(line.split(" ", 1)[0].strip()) == 40
    }


def walk_for_git() -> list[str]:
    found = []
    for root in ROOTS:
        if not Path(root).exists():
            continue
        base_depth = root.rstrip("/").count("/")
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            d = dirpath.replace("\\", "/")
            if d.count("/") - base_depth > MAXDEPTH:
                dirnames[:] = []
                continue
            dirnames[:] = [x for x in dirnames if x not in SKIP]
            if ".git" in dirnames or ".git" in filenames:
                found.append(d)
                dirnames[:] = [x for x in dirnames if x != ".git"]
    return found


def cheap_origin_and_common(path: str) -> tuple[str, str]:
    """origin URL + git-common-dir WITHOUT spawning git.

    `full-sweep.json` records 911 git checkouts on this box. At ~6 spawns each that is the
    difference between a minute and a timeout on Windows, so the two values the NAME signal
    needs are read straight off disk:
      .git as a FILE -> 'gitdir: <path>' (a linked worktree; strip /worktrees/<name>)
      .git as a DIR  -> the store is that dir
    and the origin URL is parsed out of <store>/config.
    """
    p = Path(path)
    dotgit = p / ".git"
    common, cfg = "", None
    try:
        if dotgit.is_file():
            txt = dotgit.read_text(encoding="utf-8", errors="replace").strip()
            if txt.startswith("gitdir:"):
                gd = Path(txt.split(":", 1)[1].strip())
                common = (
                    str(gd.parent.parent) if gd.parent.name == "worktrees" else str(gd)
                )
                cfg = Path(common) / "config"
        elif dotgit.is_dir():
            common, cfg = str(dotgit), dotgit / "config"
    except OSError:
        pass

    origin = ""
    try:
        if cfg and cfg.is_file():
            in_origin = False
            for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s.startswith("["):
                    in_origin = (
                        s.replace(" ", "").lower().startswith('[remote"origin"]')
                    )
                elif in_origin and s.lower().startswith("url") and "=" in s:
                    origin = s.split("=", 1)[1].strip()
                    break
    except OSError:
        pass
    return origin, common.replace("\\", "/")


def classify(path: str, reach: set[str], full: bool = False) -> dict:
    """Signals cheapest-first: only a repo no zero-spawn signal decided pays a spawn."""
    origin, common = cheap_origin_and_common(path)

    # --- signal 1: NAME (the inventory's original test) -- 0 spawns
    sig_name = TARGET in origin.lower() or TARGET in common.lower()

    # --- signal 3: CONTENT (sentinel blobs live in canonical) -- 0 spawns
    hits, checked = [], 0
    for s in SENTINELS:
        f = Path(path) / s
        try:
            if f.is_file():
                checked += 1
                if any(h in reach for h in content_hashes(f.read_bytes())):
                    hits.append(s)
        except OSError:
            pass
    sig_content = len(hits) > 0

    # --- signal 2: HISTORY -- 1 spawn, and ONLY when still undecided.
    # Recorded as None (unmeasured) rather than False when skipped, so a later reader
    # cannot mistake "not needed" for "measured and negative".
    if sig_name or sig_content:
        sig_history = None
    else:
        sig_history = (
            subprocess.run(
                ["git", "-C", path, "cat-file", "-e", ROOT_COMMIT], capture_output=True
            ).returncode
            == 0
        )

    row = {
        "path": path,
        "origin": origin,
        "git_common_dir": common,
        "dotgit": "DIR" if (Path(path) / ".git").is_dir() else "FILE",
        "sig_name": sig_name,
        "sig_history": sig_history,
        "sig_content": sig_content,
        "content_hits": hits,
        "sentinels_checked": checked,
        "belongs": bool(sig_name or sig_history or sig_content),
    }
    if full and row["belongs"]:
        row["branch"] = git(path, "rev-parse", "--abbrev-ref", "HEAD")
        row["head"] = git(path, "rev-parse", "HEAD")
        row["commits"] = git(path, "rev-list", "--count", "HEAD") or "0"
        row["dirty"] = len(
            [x for x in git(path, "status", "--porcelain", "-uall").splitlines() if x]
        )
        if row["sig_history"] is None:
            row["sig_history"] = (
                subprocess.run(
                    ["git", "-C", path, "cat-file", "-e", ROOT_COMMIT],
                    capture_output=True,
                ).returncode
                == 0
            )
    return row


def main() -> int:
    reach = canonical_reachable()

    # ---- CONTROL: the content signal must answer BOTH ways, or it is inert.
    # positive: canonical's own AGENTS.md must match. negative: fabricated bytes must not.
    pos_file = CANONICAL / "AGENTS.md"
    pos = pos_file.is_file() and any(
        h in reach for h in content_hashes(pos_file.read_bytes())
    )
    neg = any(
        h in reach
        for h in content_hashes(b"definitely not a file in this repo \xde\xad\xbe\xef")
    )
    ctl = {
        "reachable_set": len(reach),
        "positive_sentinel_matches": pos,
        "negative_fabricated_matches": neg,
        "discriminates": bool(pos and not neg and len(reach) > 1000),
    }
    print(
        f"CONTROL: reachable={len(reach)} positive={pos} negative={neg} "
        f"-> discriminates={ctl['discriminates']}"
    )
    if not ctl["discriminates"]:
        print("FAILED:enumerate content signal does not discriminate")
        return 3

    found = walk_for_git()
    print(f"filesystem sweep: {len(found)} git checkouts under {ROOTS}", flush=True)
    # Persist the walk: `full-sweep.json` recorded "911 scanned" but discarded the paths,
    # so the expensive part could not be reused. It can now.
    (OUT.parent / "walk-paths.json").write_text(
        json.dumps({"roots": ROOTS, "maxdepth": MAXDEPTH, "paths": found}, indent=2),
        encoding="utf-8",
    )

    rows = []
    for i, p in enumerate(found, 1):
        rows.append(classify(p, reach, full=True))
        if i % 100 == 0:
            print(f"  classified {i}/{len(found)}", flush=True)
    mine = [r for r in rows if r["belongs"]]

    # by-signal breakdown -- this is what makes the enumeration defect legible
    name_only = [r for r in mine if r["sig_name"]]
    missed_by_name = [r for r in mine if not r["sig_name"]]

    stores = {}
    for r in mine:
        stores.setdefault(r["git_common_dir"] or r["path"], []).append(r["path"])

    print(
        f"\nbelongs to {TARGET}: {len(mine)} checkouts across {len(stores)} object stores"
    )
    print(f"  found by NAME signal (the inventory's test) : {len(name_only)}")
    print(f"  MISSED by NAME, found by history/content     : {len(missed_by_name)}")
    for r in missed_by_name:
        print(
            f"    + {r['path']}\n"
            f"        commits={r['commits']} origin={r['origin'] or '(none)'}\n"
            f"        history={r['sig_history']} content={r['sig_content']} "
            f"hits={r['content_hits']}"
        )

    prior_paths = set()
    if PRIOR.is_file():
        try:
            pj = json.load(open(PRIOR, encoding="utf-8"))
            for row in pj.get("rows", []):
                p = (row.get("path") or "").replace("\\", "/").rstrip("/")
                if p:
                    prior_paths.add(p)
        except (ValueError, OSError):
            pass
    now_paths = {r["path"].rstrip("/") for r in mine}
    added = sorted(now_paths - prior_paths)
    gone = sorted(prior_paths - now_paths)
    print(
        f"\nvs all25.json ({len(prior_paths)} rows): +{len(added)} new, -{len(gone)} absent"
    )
    for a in added:
        print(f"    NEW  {a}")
    for g in gone:
        print(f"    GONE {g}")

    report = {
        "control": ctl,
        "root_commit": ROOT_COMMIT,
        "swept": len(found),
        "belongs": len(mine),
        "stores": len(stores),
        "found_by_name": len(name_only),
        "missed_by_name_signal": [r["path"] for r in missed_by_name],
        "vs_prior": {"added": added, "absent_now": gone},
        "rows": mine,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    print(f"SUCCESS:enumerate-checkouts total={len(mine)} stores={len(stores)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
