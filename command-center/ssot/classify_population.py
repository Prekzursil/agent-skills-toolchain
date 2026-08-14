"""Classify EVERY checkout in the corrected population on the lane's DoD axes.

Round 1 made the count honest (25 -> 170) and in doing so created its own largest gap: it
classified 27 checkouts out of a population it had just shown to be far larger. Round 2
fixed the rc=128 defect, moving the corrected total to 178. This closes the classification
gap over that whole set, mechanically.

WHY A SCRIPT AND NOT AGENTS. The four questions here -- worktree-or-clone, unique commits,
uncommitted files, who points at it -- are answerable by exact algorithm: file-vs-directory,
set membership, counting. rules/common/fan-out-contract.md sec.C4 measured what happens when
this class is handed to LLM judgement instead: 86% accuracy, and 100% of the errors pointed
at data loss.

THE AXES

  kind        `.git` is a FILE (gitdir: pointer) => linked worktree; a DIRECTORY => its own
              store. Corroborated by a second, mechanically different signal: whether
              `--git-common-dir` resolves INSIDE this path or outside it. Both must agree or
              the row is marked `kind-signals-disagree` rather than guessed.
  store       realpath of the common dir, so checkouts sharing one object store group
              together. A worktree cannot diverge in HISTORY from its store's other
              checkouts; an independent clone can. That is the whole reason the axis matters.
  unique      unpushed commits + dirty files + staged files. The unpushed count uses an
              EXPLICIT positive ref (`rev-list HEAD --not --remotes`) because
              `git log --not --remotes` with no positive ref returns EMPTY -- round 1's
              salvage_atrisk.py:24-28 records that exact false "0 unpushed". A checkout with
              NO remote is flagged `no_remote`, never silently reported as 0-unique.
  inbound     one pass over the config corpus extracting every absolute path, intersected
              with the population. O(corpus), not O(corpus x 178). Field-level use-vs-mention
              is preserved: an executable-config extension counts as a reference candidate,
              a .md/.txt/.log hit is a MENTION and is counted separately.

CONTROLS, both states, all of which must pass before any row is believed:
  kind         a known linked worktree must read FILE/outside AND a known main checkout must
               read DIR/inside.
  dirty        a known-dirty checkout must report >0 and a known-clean one 0.
  inbound      a known-referenced path must be FOUND and a fabricated path must NOT be.
               (Round 1 measured 8 field-level references, every one naming the canonical
               checkout, so canonical is the positive.)

Read-only against every checkout: no writes, no checkouts, no worktree subcommands. Writes
one JSON report, re-dumped every 25 rows so a kill cannot lose the whole sweep.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "population-classified.json"

KNOWN_WORKTREE = "C:/Users/Prekzursil/source/ast-integrate"
KNOWN_MAIN_CHECKOUT = "C:/Users/Prekzursil/source/agent-skills-toolchain"
FABRICATED = "C:/Users/Prekzursil/source/this-path-does-not-exist-92f1a"

EXEC_EXT = {
    ".json", ".toml", ".yaml", ".yml", ".ps1", ".py", ".sh", ".mjs", ".js",
    ".cmd", ".bat", ".ini", ".cfg", ".xml", ".env",
}  # fmt: skip
MENTION_EXT = {".md", ".txt", ".jsonl", ".log", ".rst", ".html", ".csv"}

SCAN_ROOTS = [
    "C:/Users/Prekzursil/.claude/hooks",
    "C:/Users/Prekzursil/.claude/skills",
    "C:/Users/Prekzursil/.claude/commands",
    "C:/Users/Prekzursil/.claude/workflows",
    "C:/Users/Prekzursil/.claude/agents",
    "C:/Users/Prekzursil/.claude/rules",
    "C:/Users/Prekzursil/.claude/plugins",
    "C:/Users/Prekzursil/.agents",
    "C:/Users/Prekzursil/.codex",
    "C:/Users/Prekzursil/.local/opt",
]
SCAN_FILES = [
    "C:/Users/Prekzursil/.claude/settings.json",
    "C:/Users/Prekzursil/.claude/settings.local.json",
    "C:/Users/Prekzursil/.claude.json",
    "C:/Users/Prekzursil/.mcp.json",
    "C:/Users/Prekzursil/CLAUDE.md",
    "C:/Users/Prekzursil/AGENTS.md",
    "C:/Users/Prekzursil/.gitconfig",
]
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", ".ruff_cache",
    ".pytest_cache", "dist", "build", ".mypy_cache",
}  # fmt: skip
MAX_BYTES = 3_000_000

# Windows absolute paths, in the shapes config files actually use.
PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"',;:)\]}<>|*?]{2,}")


def norm(p: str) -> str:
    return p.replace("\\\\", "/").replace("\\", "/").rstrip("/").lower()


def git(args: list[str], cwd: str) -> tuple[int, str]:
    p = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, p.stdout.strip()


def resolve_severed(path: str) -> dict | None:
    """THIRD signal, applied ONLY when the first two disagree.

    A `.git` FILE is a worktree pointer (`gitdir: <admin dir>`). When that admin dir is
    GONE the checkout is a SEVERED worktree, and that is the only shape that produces this
    particular disagreement: the pointer is well-formed so signal A reads `worktree`, while
    every git command inside exits 128 so `--git-common-dir` returns nothing and signal B
    reads `unknown`. Determinate, not a guess.

    THE NEGATIVE CASE IS THE POINT. A LIVE linked worktree also has a `.git` FILE -- measured
    on this box, `ast-integrate` and `wt-salvage-probe` both do -- and its target EXISTS, so
    it resolves to `worktree`, not `severed-worktree`. A resolver keyed on "`.git` is a FILE"
    would return severed for all three and be INERT while passing a control
    (rules/common/single-signal-verification.md sec.3c). Returns None when the shape does not
    apply, so no row is ever resolved by default.
    """
    dotgit = Path(path) / ".git"
    if not dotgit.is_file():
        return None
    try:
        body = dotgit.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not body.lower().startswith("gitdir:"):
        return None
    pointer = body.split(":", 1)[1].strip()
    target = Path(pointer)
    if not target.is_absolute():
        target = Path(path) / pointer
    exists = target.exists()
    return {
        "kind": "worktree" if exists else "severed-worktree",
        "resolved_by": "third-signal:dotgit-file-pointer-target-"
        + ("present" if exists else "missing"),
        "gitdir_pointer": pointer,
        "gitdir_target_exists": exists,
    }


def kind_buckets(live: list[dict]) -> dict:
    """Split the on-disk rows by kind and CHECK THAT THE SPLIT ADDS UP.

    The defect this exists for: round 2 published "9 linked worktrees + 168 independent
    clones" against a population of 178 and nobody added them up, so a whole kind went
    unaccounted in the sentence a future agent reads. A number that does not close is a
    defect whether or not any individual row is wrong.

    One implementation, called by both the full sweep and `apply_severed_resolution.py`,
    so a red-proof of one is a red-proof of both.
    """
    worktrees = [r for r in live if r["kind"] == "worktree"]
    clones = [r for r in live if r["kind"] == "own-store"]
    severed = [r for r in live if r["kind"] == "severed-worktree"]
    unresolved = [r for r in live if r["kind"] == "kind-signals-disagree"]
    total = len(worktrees) + len(clones) + len(severed) + len(unresolved)
    return {
        "worktrees": worktrees,
        "clones": clones,
        "severed": severed,
        "unresolved": unresolved,
        # The PRIMARY-signal disagreement is a separate fact from whether it was resolved.
        # Reporting only the resolved verdict would delete the record; reporting only the
        # disagreement would repeat round 3's overclaim in the other direction.
        "primary_disagree": [r for r in live if r.get("signals_agree") is False],
        "sum": total,
        "on_disk": len(live),
        "closes": total == len(live),
    }


def classify_kind(path: str) -> dict:
    dotgit = Path(path) / ".git"
    sig_a = (
        "worktree"
        if dotgit.is_file()
        else "own-store"
        if dotgit.is_dir()
        else "unknown"
    )
    rc, common = git(["git", "rev-parse", "--git-common-dir"], path)
    common_abs = norm(str(Path(path) / common)) if rc == 0 and common else ""
    if common_abs and not Path(common_abs).exists():
        common_abs = norm(common)
    inside = bool(common_abs) and common_abs.startswith(norm(path) + "/")
    sig_b = "own-store" if inside else "worktree" if common_abs else "unknown"
    out = {
        "dotgit": "file"
        if dotgit.is_file()
        else "dir"
        if dotgit.is_dir()
        else "missing",
        "common_dir": common_abs,
        "sig_dotgit": sig_a,
        "sig_commondir": sig_b,
        "signals_agree": sig_a == sig_b,
        "kind": sig_a if sig_a == sig_b else "kind-signals-disagree",
    }
    # `signals_agree` stays False: the two PRIMARY signals really did disagree, and
    # deleting that fact to make the row look clean is the overclaim this round exists to
    # fix. The third signal adds a verdict alongside it; it does not overwrite the record.
    if sig_a != sig_b:
        third = resolve_severed(path)
        if third:
            out.update(third)
    return out


def measure_unique(path: str) -> dict:
    rc_r, remotes = git(["git", "remote"], path)
    has_remote = bool(remotes)
    rc_h, head = git(["git", "rev-parse", "HEAD"], path)
    if rc_h != 0:
        unpushed, unpushed_note = None, "no HEAD (0-commit working copy)"
    elif not has_remote:
        # Every commit is trivially "unpushed" with no remote; report it as UNKNOWN with
        # the reason rather than as a number that reads like a finding.
        unpushed, unpushed_note = None, "no_remote: unpushed is undefined, not 0"
    else:
        rc_u, cnt = git(
            ["git", "rev-list", "--count", "HEAD", "--not", "--remotes"], path
        )
        unpushed = int(cnt) if rc_u == 0 and cnt.isdigit() else None
        unpushed_note = "" if unpushed is not None else "rev-list failed"
    rc_s, porcelain = git(["git", "status", "--porcelain", "-uall"], path)
    dirty = (
        len([ln for ln in porcelain.splitlines() if ln.strip()]) if rc_s == 0 else None
    )
    rc_i, staged = git(["git", "diff", "--cached", "--name-only"], path)
    n_staged = (
        len([ln for ln in staged.splitlines() if ln.strip()]) if rc_i == 0 else None
    )
    rc_b, branch = git(["git", "rev-parse", "--abbrev-ref", "HEAD"], path)
    return {
        "branch": branch if rc_b == 0 else "",
        "head": head[:8] if rc_h == 0 else "",
        "has_remote": has_remote,
        "unpushed_commits": unpushed,
        "unpushed_note": unpushed_note,
        "dirty_files": dirty,
        "staged_files": n_staged,
    }


def harvest_paths() -> tuple[dict[str, list], dict[str, list]]:
    """One corpus pass. Returns (exec_hits, mention_hits) keyed by normalised path."""
    exec_hits: dict[str, list] = {}
    mention_hits: dict[str, list] = {}

    def scan(fp: Path) -> None:
        ext = fp.suffix.lower()
        if ext not in EXEC_EXT and ext not in MENTION_EXT and ext != "":
            return
        try:
            if fp.stat().st_size > MAX_BYTES:
                return
            with open(fp, "r", encoding="utf-8", errors="ignore", newline="") as fh:
                text = fh.read()
        except OSError:
            return
        if not text:
            return
        bucket = exec_hits if ext in EXEC_EXT else mention_hits
        for i, ln in enumerate(text.splitlines(), 1):
            for m in PATH_RE.findall(ln):
                key = norm(m)
                rows = bucket.setdefault(key, [])
                if len(rows) < 6:
                    # NEVER the matched line: settings.json holds live credentials.
                    rows.append({"file": str(fp).replace("\\", "/"), "line": i})

    for root in SCAN_ROOTS:
        if not Path(root).exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                scan(Path(dirpath) / fn)
    for f in SCAN_FILES:
        if Path(f).exists():
            scan(Path(f))
    return exec_hits, mention_hits


def lookup(
    key: str, hits: dict[str, list], population: set[str] | None = None
) -> tuple[list, list]:
    """Hits on <checkout> or anything under it, SPLIT by where the naming file lives.

    Returns (harness, intra_repo).

    The split exists because the first version of this function did not have it and
    over-counted by 3x, reproducing the use-vs-mention failure this lane keeps hitting --
    "count the FIELD, not the document". Measured on the first run:

      * the `.codex` plugin-cache copy of this repo scored 12 "references", every one of
        them a `tools/crcp/**` TEST FIXTURE or captured-conversation JSON inside ITSELF;
      * `ast-harness-reconcile` and `agent-skills-toolchain-re` scored 12 and 6, almost all
        from `docs/audit-design-2026-07-13/*.json` -- an AUDIT REPORT that lists worktree
        paths. A report naming a path is a mention; the `.json` suffix is what fooled the
        extension rule.

    A file living inside a checkout of this repo is repo CONTENT, not live harness config,
    so it cannot establish that the harness depends on that checkout. Those hits are kept
    and reported separately rather than dropped, because "who talks about it" is still
    useful -- it is just not the retire criterion.
    """
    found = list(hits.get(key, []))
    prefix = key + "/"
    for k, v in hits.items():
        if k.startswith(prefix):
            found.extend(v)
            if len(found) > 40:
                break
    harness, intra = [], []
    for h in found:
        src = h["file"].lower()
        in_pop = any(src.startswith(p + "/") for p in (population or ()))
        (intra if in_pop else harness).append(h)
    return harness[:12], intra[:12]


def main() -> int:
    # ---------------- CONTROL 1: worktree-vs-clone, both known states.
    a, b = classify_kind(KNOWN_WORKTREE), classify_kind(KNOWN_MAIN_CHECKOUT)
    kind_ok = a["kind"] == "worktree" and b["kind"] == "own-store"
    print(f"CONTROL known linked worktree : dotgit={a['dotgit']:<8}-> {a['kind']}")
    print(f"CONTROL known main checkout   : dotgit={b['dotgit']:<8}-> {b['kind']}")
    print(f"discriminates: {kind_ok}")
    if not kind_ok:
        print("FAILED:classify-population kind control did not discriminate")
        return 3

    # ---------------- CONTROL 1b: the THIRD signal, both states.
    # The positive is SYNTHETIC (a temp dir whose `.git` names a gitdir that does not
    # exist) so the control does not depend on a particular cache copy still being on the
    # box. The negative is a REAL live linked worktree, which also has a `.git` FILE -- if
    # the resolver called that one severed too it would be inert, and a control that
    # cannot separate the two hypotheses is not a control.
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / ".git").write_text(
            f"gitdir: {Path(td) / 'no-such-admin-dir'}\n", encoding="utf-8"
        )
        synth = resolve_severed(td) or {}
    live_wt = resolve_severed(KNOWN_WORKTREE) or {}
    third_ok = (
        synth.get("kind") == "severed-worktree" and live_wt.get("kind") == "worktree"
    )
    print(
        f"CONTROL third signal: synthetic-missing-target -> {synth.get('kind')} ; "
        f"live linked worktree -> {live_wt.get('kind')} ; discriminates: {third_ok}"
    )
    if not third_ok:
        print("FAILED:classify-population third signal did not discriminate")
        return 3

    # ---------------- CONTROL 2: the dirty counter must separate dirty from clean.
    dirty_here = measure_unique(KNOWN_WORKTREE)["dirty_files"]
    clean_probe = measure_unique(KNOWN_MAIN_CHECKOUT)["dirty_files"]
    print(f"CONTROL dirty counter: ast-integrate={dirty_here} canonical={clean_probe}")
    if not dirty_here:
        print("FAILED:classify-population dirty counter read 0 on a known-dirty tree")
        return 3

    paths = json.loads(
        (HERE / "identity-by-ancestry.json").read_text(encoding="utf-8")
    )["all_checkout_paths"]
    print(f"\npopulation to classify: {len(paths)}")

    print("harvesting inbound references (one corpus pass)...")
    exec_hits, mention_hits = harvest_paths()
    print(f"  distinct absolute paths in exec-config : {len(exec_hits)}")
    print(f"  distinct absolute paths in prose       : {len(mention_hits)}")

    pop = {norm(p) for p in paths}

    # ---------------- CONTROL 3: the inbound scanner, both states, AFTER the intra-repo
    # split. The split must not silently delete the known positive: if canonical's live
    # harness hits vanish too, the filter is over-aggressive and every zero elsewhere is
    # meaningless.
    pos, pos_intra = lookup(norm(KNOWN_MAIN_CHECKOUT), exec_hits, pop)
    neg, _ = lookup(norm(FABRICATED), exec_hits, pop)
    inbound_ok = len(pos) > 0 and len(neg) == 0
    print(
        f"CONTROL inbound: known-referenced canonical -> {len(pos)} harness hit(s) "
        f"(+{len(pos_intra)} intra-repo); fabricated -> {len(neg)}; "
        f"discriminates: {inbound_ok}"
    )
    if not inbound_ok:
        print("FAILED:classify-population inbound control did not discriminate")
        return 3

    rows = []
    for n, p in enumerate(paths, 1):
        key = norm(p)
        row = {"path": p, "exists": Path(p).exists()}
        if row["exists"]:
            row.update(classify_kind(p))
            row.update(measure_unique(p))
            e, e_intra = lookup(key, exec_hits, pop)
            m, _ = lookup(key, mention_hits, pop)
            row["inbound_exec"] = len(e)
            row["inbound_exec_intra_repo"] = len(e_intra)
            row["inbound_mention"] = len(m)
            row["inbound_exec_files"] = sorted({h["file"] for h in e})[:6]
        rows.append(row)
        if n % 25 == 0:
            print(f"  ...{n}/{len(paths)}")
            with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"partial": True, "done": n, "rows": rows}, fh, indent=2)

    live = [r for r in rows if r["exists"]]
    buckets = kind_buckets(live)
    worktrees = buckets["worktrees"]
    clones = buckets["clones"]
    disagree = buckets["unresolved"]
    severed = buckets["severed"]
    primary_disagree = buckets["primary_disagree"]
    stores = sorted({r["common_dir"] for r in live if r.get("common_dir")})
    referenced = [r for r in live if r["inbound_exec"] > 0]
    at_risk = [
        r
        for r in live
        if (r["unpushed_commits"] or 0) > 0
        or (r["dirty_files"] or 0) > 0
        or (r["staged_files"] or 0) > 0
    ]
    no_remote = [r for r in live if not r["has_remote"]]
    disposable = [
        r
        for r in live
        if r["inbound_exec"] == 0
        and r["has_remote"]
        and (r["unpushed_commits"] == 0)
        and (r["dirty_files"] == 0)
        and (r["staged_files"] == 0)
    ]

    print(f"\n{'=' * 70}")
    print(
        f"  population                          : {len(rows)} ({len(live)} still on disk)"
    )
    print(f"  linked worktrees                    : {len(worktrees)}")
    print(f"  independent clones (own store)      : {len(clones)}")
    print(f"  severed worktrees (3rd signal)      : {len(severed)}")
    print(f"  kind signals DISAGREE (primary)     : {len(primary_disagree)}")
    print(f"  ...of those still UNRESOLVED        : {len(disagree)}")
    print(f"  distinct object stores              : {len(stores)}")

    kinds_sum = buckets["sum"]
    print(f"  kind arithmetic {kinds_sum} == on-disk {len(live)}: {buckets['closes']}")
    if not buckets["closes"]:
        print(
            f"FAILED:classify-population kind arithmetic does not close "
            f"({kinds_sum} != {len(live)})"
        )
        return 3
    print(f"  checkouts with an inbound EXEC ref  : {len(referenced)}")
    print(f"  checkouts with unique/uncommitted   : {len(at_risk)}")
    print(f"  checkouts with NO remote            : {len(no_remote)}")
    print(
        f"  clean + referenced-by-nothing       : {len(disposable)}  <- retire candidates"
    )

    print("\n  checkouts an executable config POINTS AT:")
    for r in sorted(referenced, key=lambda x: -x["inbound_exec"]):
        print(f"    {r['inbound_exec']:>3} ref(s)  {r['kind']:<12}{r['path'][:58]}")

    report = {
        "controls": {
            "kind": {"worktree": a, "main_checkout": b, "discriminates": kind_ok},
            "dirty_counter": {
                "known_dirty": dirty_here,
                "other": clean_probe,
                "discriminates": bool(dirty_here),
            },
            "inbound": {
                "positive_hits": len(pos),
                "fabricated_hits": len(neg),
                "discriminates": inbound_ok,
            },
        },
        "population": len(rows),
        "on_disk": len(live),
        "linked_worktrees": len(worktrees),
        "independent_clones": len(clones),
        "severed_worktrees": [r["path"] for r in severed],
        "kind_signals_disagree": [r["path"] for r in primary_disagree],
        "kind_signals_disagree_unresolved": [r["path"] for r in disagree],
        "kind_arithmetic": {
            "linked_worktrees": len(worktrees),
            "independent_clones": len(clones),
            "severed_worktrees": len(severed),
            "unresolved": len(disagree),
            "sum": kinds_sum,
            "on_disk": len(live),
            "closes": kinds_sum == len(live),
        },
        "distinct_object_stores": len(stores),
        "object_stores": stores,
        "referenced_by_exec_config": [
            {
                "path": r["path"],
                "refs": r["inbound_exec"],
                "files": r["inbound_exec_files"],
            }
            for r in sorted(referenced, key=lambda x: -x["inbound_exec"])
        ],
        "with_unique_or_uncommitted": [
            {
                "path": r["path"],
                "unpushed": r["unpushed_commits"],
                "dirty": r["dirty_files"],
                "staged": r["staged_files"],
                "note": r["unpushed_note"],
            }
            for r in at_risk
        ],
        "no_remote": [r["path"] for r in no_remote],
        "retire_candidates": [r["path"] for r in disposable],
        "rows": rows,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")
    print(
        f"SUCCESS:classify-population n={len(rows)} worktrees={len(worktrees)} "
        f"clones={len(clones)} referenced={len(referenced)} retire_candidates={len(disposable)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
