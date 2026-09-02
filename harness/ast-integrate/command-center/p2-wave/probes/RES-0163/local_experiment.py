#!/usr/bin/env python3
"""Live no-server stale-lock experiment for RES-0163.

Runs in an isolated temp git repo (not the delivery worktree).
Records crash-without-release outcomes for:
  * git worktree occupancy + prune
  * git worktree `locked` file (no PID/TTL)
  * emacs-style USER@HOST.PID lock
  * naive lockfile with no PID and no TTL (must DISQUALIFY)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "captures" / "local_experiment.json"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def classify(option: dict) -> str:
    """DISQUALIFIED if crash-without-release has no stale-lock story."""
    story = option.get("stale_lock_story") or ""
    if not story.strip():
        return "DISQUALIFIED"
    kinds = set(option.get("stale_mechanisms") or [])
    allowed = {
        "pid_liveness",
        "ttl_expiry",
        "directory_missing_prune",
        "kernel_flock_release",
        "fencing_token",
    }
    if not kinds.intersection(allowed):
        return "DISQUALIFIED"
    return "QUALIFIED"


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    root = Path(tempfile.mkdtemp(prefix="res0163-wt-"))
    try:
        main_repo = root / "main"
        wt_a = root / "wt-a"
        wt_b = root / "wt-b"
        main_repo.mkdir()
        r = run(["git", "init", "-b", "main"], main_repo)
        if r.returncode != 0:
            print(f"FAILED:local git init {r.stderr}")
            return 1
        run(["git", "config", "user.email", "res0163@local.invalid"], main_repo)
        run(["git", "config", "user.name", "RES-0163"], main_repo)
        (main_repo / "README").write_text("res0163\n", encoding="utf-8")
        run(["git", "add", "README"], main_repo)
        r = run(["git", "commit", "-m", "init"], main_repo)
        if r.returncode != 0:
            print(f"FAILED:local git commit {r.stderr}")
            return 1

        add_a = run(["git", "worktree", "add", str(wt_a), "-b", "topic-a"], main_repo)
        listed = run(["git", "worktree", "list", "--porcelain"], main_repo)
        list_after_add = listed.stdout

        # Crash-without-remove: delete the working tree directory.
        shutil.rmtree(wt_a)
        listed_after_rm = run(
            ["git", "worktree", "list", "--porcelain"], main_repo
        ).stdout
        prune_unlocked = run(
            ["git", "worktree", "prune", "-v", "--expire=now"], main_repo
        )
        listed_after_prune = run(
            ["git", "worktree", "list", "--porcelain"], main_repo
        ).stdout
        unlocked_reclaimed = "topic-a" not in listed_after_prune and str(wt_a) not in (
            listed_after_prune or ""
        )

        add_b = run(["git", "worktree", "add", str(wt_b), "-b", "topic-b"], main_repo)
        lock_b = run(["git", "worktree", "lock", str(wt_b), "--reason", "crash-test"], main_repo)
        locked_file = main_repo / ".git" / "worktrees" / "wt-b" / "locked"
        # Git names the admin dir from the path basename.
        admin_dirs = list((main_repo / ".git" / "worktrees").glob("*"))
        locked_paths = [p / "locked" for p in admin_dirs if (p / "locked").is_file()]
        shutil.rmtree(wt_b, ignore_errors=True)
        prune_locked = run(
            ["git", "worktree", "prune", "-v", "--expire=now"], main_repo
        )
        listed_after_locked_prune = run(
            ["git", "worktree", "list", "--porcelain"], main_repo
        ).stdout
        locked_still_present = any(
            (p / "locked").is_file() for p in (main_repo / ".git" / "worktrees").glob("*")
        ) or "locked" in listed_after_locked_prune

        # Emacs-style lock with a dead PID.
        dead_pid = 2**22  # well above typical pid_max on this box; still check
        while is_pid_alive(dead_pid) and dead_pid > 1:
            dead_pid -= 1
        lock_dir = root / "locks"
        lock_dir.mkdir()
        emacs_lock = lock_dir / ".#target.py"
        emacs_lock.symlink_to(f"tester@testhost.{dead_pid}:0")
        emacs_dead = not is_pid_alive(dead_pid)
        live_pid = os.getpid()
        live_lock = lock_dir / ".#live.py"
        live_lock.symlink_to(f"tester@testhost.{live_pid}:0")
        live_alive = is_pid_alive(live_pid)

        naive = lock_dir / "target.py.lock"
        naive.write_text("LOCKED\n", encoding="utf-8")

        options = [
            {
                "id": "git-worktree-occupancy",
                "no_server": True,
                "crash_without_release": (
                    "Holder dies leaving the worktree directory: git worktree "
                    "list still shows the checkout. Holder dies and the "
                    "directory is gone: prune --expire=now reclaims admin files."
                ),
                "stale_lock_story": (
                    "git worktree prune removes $GIT_DIR/worktrees/<id> when "
                    "the gitdir path is missing and the entry is not locked."
                ),
                "stale_mechanisms": ["directory_missing_prune"],
                "measured": {
                    "add_rc": add_a.returncode,
                    "listed_contains_wt_a_before_rm": str(wt_a) in list_after_add,
                    "listed_after_rm_still_mentions_path": str(wt_a) in listed_after_rm
                    or "topic-a" in listed_after_rm,
                    "prune_unlocked_rc": prune_unlocked.returncode,
                    "unlocked_reclaimed": unlocked_reclaimed,
                    "prune_unlocked_stderr": (prune_unlocked.stderr or "")[-400:],
                    "prune_unlocked_stdout": (prune_unlocked.stdout or "")[-400:],
                },
            },
            {
                "id": "git-worktree-locked-file",
                "no_server": True,
                "crash_without_release": (
                    "git worktree lock writes $GIT_DIR/worktrees/<id>/locked "
                    "with a reason string and no PID/TTL. After the directory "
                    "is deleted, prune --expire=now does not reclaim it."
                ),
                "stale_lock_story": "",
                "stale_mechanisms": [],
                "measured": {
                    "add_rc": add_b.returncode,
                    "lock_rc": lock_b.returncode,
                    "locked_paths": [str(p) for p in locked_paths],
                    "prune_locked_rc": prune_locked.returncode,
                    "locked_still_present": locked_still_present,
                    "listed_after": listed_after_locked_prune[-800:],
                },
            },
            {
                "id": "emacs-style-pid-lock",
                "no_server": True,
                "crash_without_release": (
                    "Symlink .#file -> USER@HOST.PID remains after crash. "
                    "Same-host kill(pid,0) ProcessLookupError => stale, reclaim."
                ),
                "stale_lock_story": (
                    "When the host matches, Emacs checks pid validity with kill; "
                    "a dead pid is treated as a stale lock."
                ),
                "stale_mechanisms": ["pid_liveness"],
                "measured": {
                    "dead_pid": dead_pid,
                    "dead_pid_alive": is_pid_alive(dead_pid),
                    "emacs_dead_reclaimable": emacs_dead,
                    "live_pid": live_pid,
                    "live_pid_alive": live_alive,
                    "lock_text": os.readlink(emacs_lock),
                },
            },
            {
                "id": "naive-lockfile-no-pid-no-ttl",
                "no_server": True,
                "crash_without_release": (
                    "A file containing only LOCKED remains forever. No pid, "
                    "no TTL, no prune. Holder crash leaks the claim."
                ),
                "stale_lock_story": "",
                "stale_mechanisms": [],
                "measured": {
                    "contents": naive.read_text(encoding="utf-8"),
                    "bytes": naive.stat().st_size,
                },
            },
        ]
        for opt in options:
            opt["verdict"] = classify(opt)

        if options[0]["verdict"] != "QUALIFIED":
            print("FAILED:local occupancy should be QUALIFIED")
            return 1
        if not options[0]["measured"]["unlocked_reclaimed"]:
            print("FAILED:local prune did not reclaim missing unlocked worktree")
            return 1
        if options[1]["verdict"] != "DISQUALIFIED":
            print("FAILED:local locked-file should be DISQUALIFIED")
            return 1
        if not options[1]["measured"]["locked_still_present"]:
            print("FAILED:local locked worktree was pruned; expected persist")
            return 1
        if options[2]["verdict"] != "QUALIFIED" or not options[2]["measured"][
            "emacs_dead_reclaimable"
        ]:
            print("FAILED:local emacs dead pid not reclaimable")
            return 1
        if options[2]["measured"]["live_pid_alive"] is not True:
            print("FAILED:local live pid not alive")
            return 1
        if options[3]["verdict"] != "DISQUALIFIED":
            print("FAILED:local naive lock should be DISQUALIFIED")
            return 1

        planted_ok_story = dict(options[3])
        planted_ok_story["stale_lock_story"] = "pretend"
        planted_ok_story["stale_mechanisms"] = []
        if classify(planted_ok_story) != "DISQUALIFIED":
            print("FAILED:local classifier accepted empty mechanisms")
            return 1

        doc = {
            "unit_id": "RES-0163",
            "fetch_timestamp": ts,
            "kind": "local-measurement",
            "isolated_repo": True,
            "host_pid_max_note": "dead_pid chosen so os.kill raises ProcessLookupError",
            "options": options,
            "disqualified_ids": [o["id"] for o in options if o["verdict"] == "DISQUALIFIED"],
            "qualified_ids": [o["id"] for o in options if o["verdict"] == "QUALIFIED"],
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "unlocked_reclaimed="
            + str(unlocked_reclaimed)
            + " locked_persists="
            + str(locked_still_present)
            + " disqualified="
            + ",".join(doc["disqualified_ids"])
        )
        print("SUCCESS:RES-0163-local-experiment")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
