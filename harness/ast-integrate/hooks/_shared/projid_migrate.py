#!/usr/bin/env python
"""projid migrate — back-merge fragmented event-ledger shards onto stable identities.

The legacy ledger keyed each shard by a *cwd*-hash, so one repo opened from several
worktrees / case-variant paths / sub-dirs produced several shards. This tool folds those
duplicates onto the ``projid``-canonical slug, matching by git remote/toplevel and, for
worktree dirs that no longer exist on disk, by a *commit-rescue* check (does the shard's
recorded git head still live inside a resolvable repo? — verifiable shared history, not a
name guess).

DRY-RUN by default — prints exactly what WOULD merge and nothing is touched. ``--apply``
performs the merge: events are concatenated, re-sequenced by timestamp (original seq/shard
kept as provenance), state.json is rebuilt, every consumed cwd is recorded in an
``aliases`` list, and each source shard is MOVED to ``<root>/.migrated/`` (reversible) —
never deleted.

Usage:
  python projid.py migrate                 # dry-run (default)
  python projid.py migrate --apply         # perform the merge
  python projid.py migrate --root <dir>    # operate on a non-default ledger root
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import projid  # noqa: E402

DEFAULT_ROOT = Path(
    os.environ.get("EVENT_LEDGER_ROOT", str(Path.home() / ".claude" / "event-ledger"))
)
_BACKUP_DIRNAME = ".migrated"


# ── reading shards ─────────────────────────────────────────────────────────────────
def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so an interrupted run can't leave a half-written
    (corrupt) target. Sources are moved only AFTER this returns, so recovery is always possible."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_events(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _shard_heads(shard: Path) -> list[str]:
    """All git heads this shard ever recorded (state + turn events) — for commit-rescue."""
    heads: list[str] = []
    st = _read_json(shard / "state.json")
    if st.get("head"):
        heads.append(st["head"])
    for e in _read_events(shard / "events.jsonl"):
        h = e.get("head")
        if h and h not in heads:
            heads.append(h)
    return heads


def _commit_in_repo(toplevel: str, head: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", toplevel, "cat-file", "-e", f"{head}^{{commit}}"],
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


# ── planning ───────────────────────────────────────────────────────────────────────
class _Plan:
    def __init__(self):
        self.target_of: dict[str, str] = {}  # shard slug -> target slug
        self.reason: dict[str, str] = {}  # shard slug -> why
        self.project_of: dict[str, str] = {}  # shard slug -> stored cwd
        self.live_repos: dict[str, str] = {}  # target slug -> a live toplevel


def build_plan(root: Path) -> _Plan:
    """Decide, for every shard, which canonical slug it belongs to. No side effects."""
    plan = _Plan()
    shards = sorted(
        d.name
        for d in root.iterdir()
        if d.is_dir() and d.name != _BACKUP_DIRNAME and (d / "state.json").exists()
    )

    # IDEMPOTENCY: any slug recorded in some shard's `migrated_from` was already absorbed by a
    # prior (possibly interrupted) --apply. Never re-include it, or its events would be merged
    # twice. Because state.json is written BEFORE any source is moved, a present migrated_from
    # entry is authoritative even if the source move did not complete.
    already_absorbed: set[str] = set()
    for slug in shards:
        for m in _read_json(root / slug / "state.json").get("migrated_from") or []:
            already_absorbed.add(m)

    # Pass 1: shards whose stored path still exists -> resolve canonical slug.
    for slug in shards:
        st = _read_json(root / slug / "state.json")
        proj = st.get("project") or ""
        plan.project_of[slug] = proj
        if slug in already_absorbed:
            plan.target_of[slug] = (
                slug  # leftover of a prior run; exclude from any merge
            )
            plan.reason[slug] = "already absorbed by a prior run -> skipped"
            continue
        exists = False
        try:
            exists = bool(proj) and Path(proj).is_dir()
        except Exception:
            exists = False
        if exists:
            pid = projid.resolve(proj)
            target = projid.ledger_slug(proj)
            plan.target_of[slug] = target
            plan.reason[slug] = f"path exists -> {pid.source}:{pid.canonical_id}"
            if pid.toplevel and target not in plan.live_repos:
                plan.live_repos[target] = pid.toplevel
        else:
            plan.target_of[slug] = slug  # provisional; may be rescued in pass 2
            plan.reason[slug] = "path gone"

    # Pass 2: commit-rescue gone shards whose recorded head lives in a known live repo.
    for slug in shards:
        if not plan.reason[slug].startswith("path gone"):
            continue
        heads = _shard_heads(root / slug)
        if not heads:
            plan.reason[slug] = "path gone, no recorded head -> unresolved"
            continue
        hit = None
        for target, top in plan.live_repos.items():
            if any(_commit_in_repo(top, h) for h in heads):
                hit = target
                break
        if hit:
            plan.target_of[slug] = hit
            plan.reason[slug] = f"commit-rescue: head in {hit}"
        else:
            plan.reason[slug] = (
                "path gone, head not in any live repo -> unresolved (kept)"
            )
    return plan


def _groups(plan: _Plan) -> dict[str, list[str]]:
    g: dict[str, list[str]] = {}
    for slug, target in plan.target_of.items():
        g.setdefault(target, []).append(slug)
    return g


# ── merging ──────────────────────────────────────────────────────────────────────--
def _project_state(
    events: list[dict], seqmap: dict, project: str, aliases: list[str]
) -> dict:
    """Rebuild a state.json projection from a merged, re-sequenced event list, mirroring
    ledger.append's rules (goal/head/open_failures + milestone supersession)."""
    st = {
        "seq": len(events),
        "project": project,
        "goal": None,
        "head": None,
        "open_failures": [],
        "last_event_ts": None,
        "aliases": sorted(set(aliases)),
    }
    for ev in events:
        st["last_event_ts"] = ev.get("ts") or st["last_event_ts"]
        kind = ev.get("kind")
        if kind == "goal":
            st["goal"] = ev.get("text")
        elif kind == "turn" and ev.get("head"):
            st["head"] = ev["head"]
        elif kind == "failure":
            st["open_failures"].append(
                {
                    "seq": ev["seq"],
                    "text": ev.get("text"),
                    "preconditions": ev.get("preconditions"),
                }
            )
            st["open_failures"] = st["open_failures"][-25:]
        elif kind == "milestone" and ev.get("supersedes_failures"):
            # translate the milestone's old (orig) seqs -> new seqs within its own shard
            src = ev.get("_orig_shard")
            old = set(ev["supersedes_failures"])
            kill = {seqmap.get((src, o)) for o in old}
            st["open_failures"] = [
                f for f in st["open_failures"] if f.get("seq") not in kill
            ]
    return st


def _merge_group(root: Path, target: str, members: list[str], stamp: str) -> dict:
    """Concatenate + re-sequence all member events onto ``target``; return a summary."""
    backup = root / _BACKUP_DIRNAME
    backup.mkdir(parents=True, exist_ok=True)

    tagged: list[dict] = []
    aliases: list[str] = []
    existing_aliases: list[str] = []
    for slug in members:
        sd = root / slug
        st = _read_json(sd / "state.json")
        if st.get("project"):
            aliases.append(st["project"])
        existing_aliases += st.get("aliases", []) or []
        for e in _read_events(sd / "events.jsonl"):
            e = dict(e)
            # PRESERVE provenance if already present (an event re-read from a target that was
            # written by an earlier merge), else stamp it now. This makes the merge idempotent:
            # a previously-absorbed event and its still-present source carry the SAME origin key
            # and dedup to one — even if a prior --apply was interrupted before sources moved.
            e.setdefault("_orig_shard", slug)
            e.setdefault("_orig_seq", e.get("seq"))
            tagged.append(e)
    # stable sort by timestamp, then original shard/seq for deterministic ties
    tagged.sort(
        key=lambda e: (
            e.get("ts") or "",
            str(e.get("_orig_shard") or ""),
            e.get("_orig_seq") or 0,
        )
    )
    # dedup by origin (idempotency belt-and-suspenders, covers the interrupted-run gap)
    seen: set = set()
    uniq: list[dict] = []
    for e in tagged:
        key = (e.get("_orig_shard"), e.get("_orig_seq"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    tagged = uniq

    seqmap: dict = {}
    for i, e in enumerate(tagged, start=1):
        seqmap[(e["_orig_shard"], e["_orig_seq"])] = i
        e["seq"] = i

    project = _read_json(root / target / "state.json").get("project") or next(
        (
            _read_json(root / m / "state.json").get("project")
            for m in members
            if _read_json(root / m / "state.json").get("project")
        ),
        "",
    )
    state = _project_state(tagged, seqmap, project, aliases + existing_aliases)
    state["migrated_from"] = sorted(m for m in members if m != target)
    state["migrated_at"] = stamp

    # 1) back up the target's current contents (if any) so the merge is reversible
    tdir = root / target
    if tdir.exists():
        shutil.copytree(tdir, backup / f"{target}-{stamp}-target", dirs_exist_ok=True)
    tdir.mkdir(parents=True, exist_ok=True)

    # 2) write merged events.jsonl + state.json atomically (temp + os.replace)
    _atomic_write(
        tdir / "events.jsonl",
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in tagged),
    )
    _atomic_write(tdir / "state.json", json.dumps(state, indent=2, ensure_ascii=False))

    # 3) move every consumed (non-target) source shard into the backup dir (reversible)
    moved = []
    for slug in members:
        if slug == target:
            continue
        src = root / slug
        if src.exists():
            shutil.move(str(src), str(backup / f"{slug}-{stamp}"))
            moved.append(slug)
    return {
        "target": target,
        "events": len(tagged),
        "merged": moved,
        "aliases": len(state["aliases"]),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────────--
def _fmt_group(root: Path, plan: _Plan, target: str, members: list[str]) -> list[str]:
    lines = []
    for m in sorted(members):
        ev = len(_read_events(root / m / "events.jsonl"))
        tag = "  (=target)" if m == target else ""
        lines.append(
            f"      <- {m:<42} {ev:>4} events  [{plan.reason.get(m, '')}]{tag}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="projid migrate")
    ap.add_argument(
        "--apply", action="store_true", help="perform the merge (default: dry-run)"
    )
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="event-ledger root")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not root.is_dir():
        print(f"FAILED:migrate no ledger root at {root}", file=sys.stderr)
        return 1

    plan = build_plan(root)
    groups = _groups(plan)
    merges = {t: m for t, m in groups.items() if len(m) > 1}
    relabels = {
        t: m
        for t, m in groups.items()
        if len(m) == 1 and m[0] != t and not plan.reason[m[0]].startswith("path gone")
    }
    unresolved = [s for s, r in plan.reason.items() if "unresolved" in r]

    total_shards = len(plan.target_of)
    canonical = len(groups)
    print(f"projid migrate ({'APPLY' if a.apply else 'DRY-RUN'}) — root={root}")
    print(
        f"  {total_shards} shards -> {canonical} canonical ids "
        f"| {len(merges)} merge-groups, {len(relabels)} relabels, {len(unresolved)} unresolved\n"
    )

    if merges:
        print("MERGES (multiple shards collapse to one identity):")
        for t, m in sorted(merges.items(), key=lambda kv: -len(kv[1])):
            print(f"  => {t}   ({len(m)} shards)")
            print("\n".join(_fmt_group(root, plan, t, m)))
        print()
    if relabels:
        print("RELABELS (one shard re-keyed to its canonical slug):")
        for t, m in sorted(relabels.items()):
            print(f"  => {t}   <- {m[0]}  [{plan.reason[m[0]]}]")
        print()
    if unresolved:
        print(
            f"UNRESOLVED (kept as-is — path gone & identity unverifiable): {len(unresolved)}"
        )
        for s in sorted(unresolved):
            print(f"  .. {s}  [{plan.reason[s]}]")
        print()

    if not a.apply:
        print(
            "DRY-RUN only. Re-run with --apply to perform the merge (sources backed up to "
            f"{root / _BACKUP_DIRNAME}, nothing deleted)."
        )
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    actions = {**merges, **relabels}
    done = []
    for t, m in actions.items():
        try:
            done.append(_merge_group(root, t, m, stamp))
        except Exception as ex:  # fail-open per shard; keep going
            print(f"  WARN: group {t} failed: {ex}", file=sys.stderr)
    print(
        f"SUCCESS:migrate applied {len(done)} groups; sources moved to {root / _BACKUP_DIRNAME}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
