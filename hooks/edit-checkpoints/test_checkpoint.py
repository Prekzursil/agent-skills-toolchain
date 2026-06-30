#!/usr/bin/env python3
"""Tests for edit-checkpoints. Runs WITHOUT pytest: `python test_checkpoint.py`.

Uses throwaway temp repos/dirs and an isolated EDIT_CHECKPOINTS_DIR; never touches
the real user repos or checkpoint store.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

_FAILS = []


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def write_transcript(path: Path, human_uuid: str):
    """Minimal transcript with one genuine human turn + one tool_result (ignored)."""
    lines = [
        {
            "type": "user",
            "uuid": human_uuid,
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "do edits"}],
            },
        },
        {
            "type": "user",
            "uuid": "tr_" + human_uuid,
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "content": "ok"}],
            },
        },
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")


def run_hook(checkpoint_mod, event: dict):
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(event))
    try:
        with redirect_stdout(buf):
            checkpoint_mod.main()
    finally:
        sys.stdin = old_stdin
    return buf.getvalue()


def main():
    git = __import__("shutil").which("git")
    work = Path(tempfile.mkdtemp(prefix="ckpt-test-"))
    ckpt_dir = work / "store"
    os.environ["EDIT_CHECKPOINTS_DIR"] = str(ckpt_dir)
    import checkpoint  # imported AFTER env set

    checkpoint.CKPT_ROOT = ckpt_dir  # ensure module picks up the test store

    sid = "ckpt-sess"
    index = ckpt_dir / sid / "index.ndjson"

    def index_records():
        if not index.exists():
            return []
        return [
            json.loads(x)
            for x in index.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]

    # ----- GIT MODE -----
    if git:
        repo = work / "repo"
        repo.mkdir()
        for args in (
            ["init", "-q"],
            ["config", "user.email", "t@t"],
            ["config", "user.name", "t"],
        ):
            subprocess.run([git, "-C", str(repo), *args], capture_output=True)
        f = repo / "a.txt"
        f.write_text("v1\n", encoding="utf-8")
        subprocess.run([git, "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(
            [git, "-C", str(repo), "commit", "-qm", "init"], capture_output=True
        )
        f.write_text("v2-dirty\n", encoding="utf-8")  # dirty working tree

        tA = work / "tA.jsonl"
        write_transcript(tA, "AAA")
        ev = {
            "tool_name": "Edit",
            "session_id": sid,
            "cwd": str(repo),
            "transcript_path": str(tA),
            "tool_input": {"file_path": str(f)},
        }
        run_hook(checkpoint, ev)
        recs = index_records()
        git_recs = [r for r in recs if r["type"].startswith("git")]
        check("git: one checkpoint after first edit", len(git_recs) == 1)
        check(
            "git: stash-create snapshot has a restore sha",
            git_recs
            and git_recs[0]["type"] == "git-stash"
            and len(git_recs[0]["restore"]) >= 7,
        )
        # ref exists + is reachable
        rc = subprocess.run(
            [git, "-C", str(repo), "rev-parse", "refs/claude-checkpoints/u_AAA"],
            capture_output=True,
            text=True,
        )
        check(
            "git: checkpoint ref created + reachable",
            rc.returncode == 0 and rc.stdout.strip(),
        )

        # same turn -> dedup
        run_hook(checkpoint, ev)
        check(
            "git: same-turn second edit deduped (still 1)",
            len([r for r in index_records() if r["type"].startswith("git")]) == 1,
        )

        # new turn -> new checkpoint
        tB = work / "tB.jsonl"
        write_transcript(tB, "BBB")
        ev2 = dict(ev, transcript_path=str(tB))
        run_hook(checkpoint, ev2)
        check(
            "git: new turn -> new checkpoint (2)",
            len([r for r in index_records() if r["type"].startswith("git")]) == 2,
        )
    else:
        print("SKIP: git not on PATH (git-mode not asserted)")

    # ----- NON-GIT MODE -----
    plain = work / "plain"
    plain.mkdir()
    b = plain / "b.txt"
    b.write_text("original-content\n", encoding="utf-8")
    tC = work / "tC.jsonl"
    write_transcript(tC, "CCC")
    ev3 = {
        "tool_name": "Write",
        "session_id": sid,
        "cwd": str(plain),
        "transcript_path": str(tC),
        "tool_input": {"file_path": str(b)},
    }
    run_hook(checkpoint, ev3)
    copy_recs = [r for r in index_records() if r["type"] == "copy"]
    check("non-git: file copied to checkpoint store", len(copy_recs) == 1)
    if copy_recs:
        saved = Path(copy_recs[0]["copy_path"])
        check(
            "non-git: copy preserves pre-edit content",
            saved.exists()
            and saved.read_text(encoding="utf-8") == "original-content\n",
        )
    run_hook(checkpoint, ev3)  # same turn+file -> dedup
    check(
        "non-git: same-turn same-file deduped (still 1)",
        len([r for r in index_records() if r["type"] == "copy"]) == 1,
    )

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
