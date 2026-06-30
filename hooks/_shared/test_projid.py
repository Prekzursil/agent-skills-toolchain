#!/usr/bin/env python
"""Self-contained tests for projid + projid_migrate. Run: python test_projid.py
Creates throwaway git repos and a temp EVENT_LEDGER_ROOT — never touches real data."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fails = []


def check(name, cond):
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True
    )


def _mkrepo(path: Path, remote: str | None, commit: bool = False) -> str | None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    head = None
    if commit:
        (path / "f.txt").write_text("x", encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", "init")
        head = _git(path, "rev-parse", "--short", "HEAD").stdout.strip()
    return head


def h12(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def main():
    import projid

    importlib.reload(projid)
    tmp = Path(tempfile.mkdtemp(prefix="projid-test-"))

    print("== canonical_id reproduces CL-v2 (sha256(remote)[:12]) ==")
    rem = "https://github.com/Prekzursil/Reframe.git"
    repo = tmp / "Reframe"
    _mkrepo(repo, rem)
    pid = projid.resolve(str(repo))
    check("source is remote", pid.source == "remote")
    check("canonical_id == sha256(remote)[:12]", pid.canonical_id == h12(rem))
    check("display_name from remote basename", pid.display_name == "Reframe")

    print("== worktrees / sub-dirs collapse to ONE id (the documented-bug fix) ==")
    sub = repo / "sidecar" / "media_studio"
    sub.mkdir(parents=True, exist_ok=True)
    pid_sub = projid.resolve(str(sub))
    check(
        "sub-dir same canonical_id as repo root",
        pid_sub.canonical_id == pid.canonical_id,
    )
    check(
        "sub-dir same ledger_slug as repo root",
        projid.ledger_slug(str(sub)) == projid.ledger_slug(str(repo)),
    )
    # a second checkout path of the same remote (simulated worktree) -> same id
    wt = tmp / "Reframe-electron"
    _mkrepo(wt, rem)
    check(
        "separate checkout, same remote -> same id",
        projid.resolve(str(wt)).canonical_id == pid.canonical_id,
    )

    print("== credential stripping (normalization) ==")
    credrepo = tmp / "cred"
    cred_url = "https://user:ghp_secrettoken@github.com/Prekzursil/Reframe.git"
    _mkrepo(credrepo, cred_url)
    cpid = projid.resolve(str(credrepo))
    check("creds stripped from stored remote", "ghp_secret" not in (cpid.remote or ""))
    check("cred-stripped id == clean-remote id", cpid.canonical_id == h12(rem))
    check(
        "legacy_id preserved (raw, for old-store lookup)",
        cpid.legacy_id == h12(cred_url),
    )

    print("== git repo without remote -> toplevel identity ==")
    norem = tmp / "noremote"
    _mkrepo(norem, None)
    npid = projid.resolve(str(norem))
    check("source is toplevel", npid.source == "toplevel")
    check(
        "toplevel id == sha256(toplevel)[:12]", npid.canonical_id == h12(npid.toplevel)
    )

    print("== non-git dir -> cwd identity + ZERO-churn legacy slug ==")
    plain = tmp / "plain_dir"
    plain.mkdir()
    ppid = projid.resolve(str(plain))
    check("source is cwd", ppid.source == "cwd")
    check(
        "ledger_slug == legacy formula (no churn for non-git)",
        projid.ledger_slug(str(plain)) == projid.legacy_ledger_slug(str(plain)),
    )

    print("== explicit .claude/project-id pin overrides ==")
    pindir = repo / "pinned_sub"
    (pindir / ".claude").mkdir(parents=True, exist_ok=True)
    (pindir / ".claude" / "project-id").write_text("my-custom-proj\n", encoding="utf-8")
    pinpid = projid.resolve(str(pindir))
    check("pin wins over remote", pinpid.source == "pin")
    check("pin id distinct from repo id", pinpid.canonical_id != pid.canonical_id)

    print("== detect_project CL-v2 shim ==")
    dp = projid.detect_project(str(repo))
    check("detect_project id == canonical_id", dp["id"] == pid.canonical_id)
    check(
        "detect_project global for non-git/no-env",
        projid.detect_project(str(plain)).get("id") == "global"
        if not os.environ.get("CLAUDE_PROJECT_DIR")
        else True,
    )

    print("== migrate: dedup by remote + commit-rescue (synthetic ledger root) ==")
    head = _mkrepo(
        tmp / "RepoB", "https://github.com/Prekzursil/RepoB.git", commit=True
    )
    ledroot = tmp / "ledroot"

    def mkshard(slug, project, head=None, events=None):
        d = ledroot / slug
        d.mkdir(parents=True, exist_ok=True)
        st = {
            "seq": 1,
            "project": project,
            "goal": None,
            "head": head,
            "open_failures": [],
            "last_event_ts": "2026-01-01T00:00:00",
        }
        (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
        evs = events or [
            {"seq": 1, "ts": "2026-01-01T00:00:00", "kind": "turn", "head": head}
        ]
        with (d / "events.jsonl").open("w", encoding="utf-8") as fh:
            for e in evs:
                fh.write(json.dumps(e) + "\n")

    repoB = str(tmp / "RepoB")
    # two shards, same repo via different path strings -> must merge
    mkshard(
        "RepoB-aaaa1111",
        repoB,
        events=[
            {"seq": 1, "ts": "2026-01-01T00:00:01", "kind": "goal", "text": "G1"},
            {"seq": 2, "ts": "2026-01-01T00:00:02", "kind": "turn", "head": head},
        ],
    )
    mkshard(
        "RepoB-bbbb2222",
        repoB.replace("\\", "/"),
        events=[
            {
                "seq": 1,
                "ts": "2026-01-01T00:00:03",
                "kind": "failure",
                "text": "F1",
                "preconditions": "x",
            }
        ],
    )
    # a GONE worktree whose recorded head lives in RepoB -> commit-rescue
    mkshard("RepoB-wt-cccc3333", str(tmp / "gone-worktree-xyz"), head=head)
    # an unrelated non-git dir -> stays put
    plain2 = tmp / "loosedir"
    plain2.mkdir()
    mkshard(projid.ledger_slug(str(plain2)), str(plain2))

    os.environ["EVENT_LEDGER_ROOT"] = str(ledroot)
    import projid_migrate

    importlib.reload(projid_migrate)
    plan = projid_migrate.build_plan(ledroot)
    groups = projid_migrate._groups(plan)
    canon_target = projid.ledger_slug(repoB)
    check(
        "two same-remote shards share a target",
        plan.target_of["RepoB-aaaa1111"]
        == plan.target_of["RepoB-bbbb2222"]
        == canon_target,
    )
    check(
        "commit-rescue maps gone worktree to repo target",
        plan.target_of["RepoB-wt-cccc3333"] == canon_target,
    )
    check("RepoB group has 3 members", len(groups.get(canon_target, [])) == 3)

    print("== migrate --apply merges, re-sequences, records aliases, is reversible ==")
    projid_migrate.main(["--apply", "--root", str(ledroot)])
    tgt = ledroot / canon_target
    merged = [
        json.loads(ln)
        for ln in (tgt / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    seqs = [e["seq"] for e in merged]
    check(
        "events re-sequenced monotonically from 1",
        seqs == list(range(1, len(seqs) + 1)),
    )
    check(
        "events ordered by ts",
        [e["ts"] for e in merged] == sorted(e["ts"] for e in merged),
    )
    st = json.loads((tgt / "state.json").read_text(encoding="utf-8"))
    check("goal projected after merge", st["goal"] == "G1")
    check(
        "open failure carried into merged state",
        any(f.get("text") == "F1" for f in st["open_failures"]),
    )
    check("aliases record every source cwd", len(st.get("aliases", [])) >= 2)
    check(
        "sources backed up (reversible), not deleted",
        (ledroot / ".migrated").exists() and not (ledroot / "RepoB-bbbb2222").exists(),
    )
    check(
        "loose non-git shard untouched",
        (ledroot / projid.ledger_slug(str(plain2))).exists(),
    )

    print("== migrate dry-run is read-only ==")
    before = sorted(p.name for p in ledroot.iterdir())
    projid_migrate.main(["--root", str(ledroot)])  # dry-run
    after = sorted(p.name for p in ledroot.iterdir())
    check("dry-run changes nothing on disk", before == after)

    import shutil

    print(
        "== HIGH-1: ledger._slug keeps the legacy shard until migrated (deploy-safe) =="
    )
    sys.path.insert(0, str(HERE.parent / "event-ledger"))
    import ledger as _led

    importlib.reload(_led)
    hr = tmp / "high1"
    hr.mkdir()
    _led.ROOT = hr  # isolate
    repoB_path = str(tmp / "RepoB")
    canon = projid.ledger_slug(repoB_path)
    legacy = _led._legacy_slug(repoB_path)
    check("git repo: canonical slug != legacy cwd-slug", canon != legacy)
    (hr / legacy).mkdir(parents=True)
    (hr / legacy / "state.json").write_text("{}", encoding="utf-8")
    check(
        "_slug keeps the legacy shard while it exists (no silent abandon)",
        _led._slug(repoB_path) == legacy,
    )
    shutil.rmtree(hr / legacy)
    check(
        "_slug switches to canonical once legacy shard is gone (post-migrate)",
        _led._slug(repoB_path) == canon,
    )

    print("== HIGH-2: migrate --apply is idempotent (no event duplication) ==")

    def n_events(root, slug):
        return len(
            [
                x
                for x in (root / slug / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if x.strip()
            ]
        )

    hr2 = tmp / "high2"

    def mksh2(slug, project, events):
        d = hr2 / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "state.json").write_text(
            json.dumps({"seq": len(events), "project": project, "open_failures": []}),
            encoding="utf-8",
        )
        with (d / "events.jsonl").open("w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")

    mksh2(
        "RepoB-x",
        repoB,
        [{"seq": 1, "ts": "2026-01-01T00:00:01", "kind": "turn", "head": head}],
    )
    mksh2(
        "RepoB-y",
        repoB.replace("\\", "/"),
        [{"seq": 1, "ts": "2026-01-01T00:00:02", "kind": "goal", "text": "GG"}],
    )
    tcanon = projid.ledger_slug(repoB)
    projid_migrate.main(["--apply", "--root", str(hr2)])
    n1 = n_events(hr2, tcanon)
    check("first apply merged both shards", n1 == 2)
    projid_migrate.main(["--apply", "--root", str(hr2)])  # plain re-run
    check("plain re-run does not change event count", n_events(hr2, tcanon) == n1)
    # interrupted run (state.json written, source move did NOT happen): restore the source under
    # its ORIGINAL name -> migrated_from must cause it to be skipped, not re-merged.
    bak = next((hr2 / ".migrated").glob("RepoB-x-*"))
    shutil.copytree(bak, hr2 / "RepoB-x")
    projid_migrate.main(["--apply", "--root", str(hr2)])
    check(
        "restored source skipped via migrated_from (no dup)",
        n_events(hr2, tcanon) == n1,
    )
    # rarer gap (events written but migrated_from NOT recorded): provenance-dedup must still
    # collapse the re-read source against its already-absorbed copy in the target.
    stp = hr2 / tcanon / "state.json"
    stj = json.loads(stp.read_text(encoding="utf-8"))
    stj.pop("migrated_from", None)
    stp.write_text(json.dumps(stj), encoding="utf-8")
    projid_migrate.main(
        ["--apply", "--root", str(hr2)]
    )  # RepoB-x still present from above
    check(
        "provenance-dedup prevents duplication even without migrated_from",
        n_events(hr2, tcanon) == n1,
    )

    print(
        f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}  ({len(fails)} failures)"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
