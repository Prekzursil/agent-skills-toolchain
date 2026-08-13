"""Measure — and then salvage — the files the SSOT lane measured as existing nowhere else.

Two sources, both named in docs/ssot/SSOT-CLONE-INVENTORY.md sec.4:

  1. D:/wt-salvage-probe   -- a STAGED INDEX, never committed. `git worktree remove` destroys
                              a worktree's index, so this content dies with the directory.
  2. ~/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain
                           -- 2 unpushed commits whose 3 files are ABSENT from main.

The uniqueness test is REACHABILITY in the canonical object store -- membership in
`git rev-list --objects --all`, the set `git gc` preserves. It is content-blind on purpose:
"unreachable" is a fact about bytes, not a judgement about whether the bytes deserve to come
back.

TWO DETECTOR FAILURES THIS FILE COMMITTED FIRST, both in the DANGEROUS direction (reporting
safety where there is exposure). Recorded rather than edited away:

  1. `git cat-file -e <blob>` was used as the uniqueness test. `D:/wt-salvage-probe` is a
     LINKED WORKTREE of canonical, so `git add` wrote its blobs into the SHARED object store:
     every at-risk file reported "present in canonical" and the run concluded `unique=0`.
     Existence and reachability are different questions and an existence probe answers them
     identically -- it cannot distinguish "preserved in history" from "loose object one gc
     from gone". Measured truth: exists_in_store=True, reachable_from_any_ref=False.
  2. `git log --format=%H --not --remotes` was run with NO positive ref. It does not default
     to HEAD once `--not` is present -- it returns EMPTY. That produced "files=0" for
     `_b5-toolchain`, i.e. a clean bill of health for a checkout holding the only copy of
     three files. Fixed by passing `HEAD` explicitly; `reachability_probe.py` prints the
     query's return code so the silence cannot be mistaken for an answer again.

Read-only against every source. Writes ONLY under command-center/ssot/.

Usage:
    python command-center/ssot/salvage_atrisk.py            # measure only
    python command-center/ssot/salvage_atrisk.py --salvage  # measure, then copy into this repo
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
HERE = Path(__file__).resolve().parent
OUT_JSON = HERE / "salvage-atrisk.json"
DEST = HERE / "salvaged-at-risk"

SOURCES = {
    "wt-salvage-probe": {
        "path": Path("D:/wt-salvage-probe"),
        "kind": "staged-index",
        "expect": [
            "ci/tests/test_codex_profiles.py",
            "tools/monitorcore/r0_monitor_live_gate.py",
        ],
    },
    "b5-toolchain": {
        "path": Path(
            "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/"
            "agent-1521081161/_b5-toolchain"
        ),
        "kind": "unpushed-commits",
        "expect": [
            "tools/mcp-manager/core/health.py",
            "tools/mcp-manager/mcp_health.py",
            "tools/mcp-manager/tests/test_health.py",
        ],
    },
}


def run(args, cwd=None, check=False):
    p = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"{args} -> {p.returncode}: {p.stderr[:400]}")
    return p


def git_hash(data: bytes) -> str:
    """git's blob SHA-1 = sha1("blob <len>\\0" + bytes). Computed locally, no spawn."""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def canonical_reachable() -> set[str]:
    """Every object reachable from ANY ref in canonical -- the set `git gc` preserves.

    This replaces the `cat-file -e` existence check, which could not tell a preserved blob
    apart from a loose object hanging off a worktree index (see the module docstring).
    """
    p = run(["git", "rev-list", "--objects", "--all"], cwd=CANONICAL)
    out = set()
    for line in p.stdout.splitlines():
        sha = line.split(" ", 1)[0].strip()
        if len(sha) == 40:
            out.add(sha)
    return out


def control_reach_reader(reach: set[str]) -> dict:
    """BOTH-STATES control for the reachable set.

    An empty set marks everything unique; a universal set marks nothing unique. Either makes
    every verdict below vacuous. So probe one object that MUST be reachable (a blob from
    canonical's own HEAD) and one that cannot exist, and require the two answers to differ.
    """
    real = run(["git", "rev-parse", "HEAD:README.md"], cwd=CANONICAL)
    known_present = real.stdout.strip() if real.returncode == 0 else None
    known_absent = git_hash(
        b"this blob was never committed anywhere " + b"\xde\xad" * 64
    )
    ok = (
        known_present is not None
        and known_present in reach
        and known_absent not in reach
        and len(reach) >= 1000
    )
    return {
        "reachable_set_size": len(reach),
        "known_present_sha": known_present,
        "known_present_result": known_present in reach if known_present else None,
        "known_absent_sha": known_absent,
        "known_absent_result": known_absent in reach,
        "discriminates": ok,
    }


def staged_files(repo: Path) -> list[tuple[str, str]]:
    """(path, sha) for everything in the index but not in HEAD."""
    p = run(["git", "diff", "--cached", "--name-status"], cwd=repo)
    names = []
    for line in p.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            names.append(parts[-1])
    out = []
    for n in names:
        q = run(["git", "rev-parse", f":{n}"], cwd=repo)
        if q.returncode == 0:
            out.append((n, q.stdout.strip()))
    return out


def unpushed_commit_files(repo: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """(path, sha) for every file touched by commits not reachable from any remote ref.

    NOTE the explicit `HEAD`. `git log --not --remotes` with no positive ref returns EMPTY
    rather than defaulting to HEAD -- that silence previously read as "nothing unpushed" for
    a checkout holding the only copy of three files. rc is asserted so a failed query can
    never be mistaken for an empty one.
    """
    p = run(["git", "log", "--format=%H", "HEAD", "--not", "--remotes"], cwd=repo)
    if p.returncode != 0:
        raise RuntimeError(f"unpushed query failed in {repo}: {p.stderr[:300]}")
    commits = [c for c in p.stdout.split() if c]
    seen: dict[str, str] = {}
    for c in commits:
        q = run(["git", "show", "--pretty=", "--name-only", c], cwd=repo)
        for path in q.stdout.splitlines():
            path = path.strip()
            if not path or path in seen:
                continue
            r = run(["git", "rev-parse", f"{c}:{path}"], cwd=repo)
            if r.returncode == 0:
                seen[path] = r.stdout.strip()
    return sorted(seen.items()), commits


def read_blob(repo: Path, sha: str) -> bytes | None:
    p = subprocess.run(
        ["git", "cat-file", "blob", sha], cwd=str(repo), capture_output=True
    )
    return p.stdout if p.returncode == 0 else None


def main() -> int:
    salvage = "--salvage" in sys.argv
    reach = canonical_reachable()
    report: dict = {"control": control_reach_reader(reach), "sources": {}}

    if not report["control"]["discriminates"]:
        print("FAILED:salvage-atrisk reachable-set reader does not discriminate")
        print(json.dumps(report["control"], indent=2))
        return 3

    print(
        "CONTROL: canonical reachable objects={}  known-reachable={}  fabricated={}"
        "  -> discriminates".format(
            report["control"]["reachable_set_size"],
            report["control"]["known_present_result"],
            report["control"]["known_absent_result"],
        )
    )

    total_unique = 0
    for name, spec in SOURCES.items():
        repo: Path = spec["path"]
        entry: dict = {"path": str(repo), "kind": spec["kind"], "exists": repo.exists()}
        if not repo.exists():
            entry["files"] = []
            entry["note"] = "checkout ABSENT -- content may already be lost"
            report["sources"][name] = entry
            print(f"\n[{name}] {repo} -- ABSENT")
            continue

        if spec["kind"] == "staged-index":
            files = staged_files(repo)
            entry["commits"] = []
        else:
            files, commits = unpushed_commit_files(repo)
            entry["commits"] = commits

        rows = []
        for path, sha in files:
            data = read_blob(repo, sha)
            rows.append(
                {
                    "path": path,
                    "sha": sha,
                    "bytes": len(data) if data is not None else None,
                    # exists != reachable. Kept side by side so the gap is legible.
                    "exists_in_canonical_store": run(
                        ["git", "cat-file", "-e", sha], cwd=CANONICAL
                    ).returncode
                    == 0,
                    "reachable_in_canonical": sha in reach,
                }
            )
        entry["files"] = rows
        uniq = [r for r in rows if not r["reachable_in_canonical"]]
        entry["unique_count"] = len(uniq)
        total_unique += len(uniq)
        report["sources"][name] = entry

        print(f"\n[{name}] {repo}")
        print(
            f"  kind={spec['kind']}  files={len(rows)}  "
            f"AT RISK (unreachable in canonical)={len(uniq)}"
        )
        for r in rows:
            mark = "AT-RISK" if not r["reachable_in_canonical"] else "safe   "
            print(
                f"    {mark}  {r['bytes']:>7} B  exists={r['exists_in_canonical_store']!s:<5}"
                f" reachable={r['reachable_in_canonical']!s:<5}  {r['path']}"
            )

        if salvage and uniq:
            dest_root = DEST / name
            for r in uniq:
                data = read_blob(repo, r["sha"])
                if data is None:
                    r["salvaged"] = False
                    continue
                target = dest_root / r["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)  # raw blob bytes, no newline translation
                r["salvaged"] = True
                r["salvaged_to"] = str(target.relative_to(HERE.parent.parent))
                # prove the copy is byte-identical to the blob we read
                r["roundtrip_sha"] = git_hash(target.read_bytes())
                r["roundtrip_ok"] = r["roundtrip_sha"] == r["sha"]
            print(f"  -> salvaged {len(uniq)} file(s) into {dest_root}")

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_JSON}")
    print(
        f"SUCCESS:salvage-atrisk unique={total_unique} salvage={'yes' if salvage else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
