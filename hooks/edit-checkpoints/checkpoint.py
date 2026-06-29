#!/usr/bin/env python3
r"""EDIT-CHECKPOINTS — snapshot-before-write undo safety.

Claude Code has NO built-in edit-undo. This PreToolUse(Edit|Write|MultiEdit) hook
takes a cheap, non-intrusive snapshot of the pre-edit state ONCE PER TURN so a botched
edit run is recoverable (see /rollback):

  * git repo  -> `git stash create` (a snapshot commit object that does NOT touch the
                 working tree or the stash stack) tagged under refs/claude-checkpoints/
                 so it is reachable + GC-safe. One snapshot per (turn, repo) captures the
                 WHOLE dirty tree, so thousands of edits in a turn cost one snapshot.
  * non-git   -> copy each distinct target file once per turn into the checkpoints dir.

A "turn" = one genuine human prompt (tool_result user-events are ignored), keyed by the
last human message uuid in the transcript; falls back to a 120s time bucket. Every
checkpoint is appended to <ckpt>/<sid>/index.ndjson for /rollback to read.

NEVER blocks; inject-only is not even needed (silent). FAIL-OPEN: any error -> exit 0.
Opt-out: EDIT_CHECKPOINTS=off or a .disabled file.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
CKPT_ROOT = Path(os.environ.get(
    "EDIT_CHECKPOINTS_DIR", str(Path.home() / ".claude" / "checkpoints")))
MAX_COPY_BYTES = 25 * 1024 * 1024  # don't copy huge artifacts in non-git mode
GIT = shutil.which("git")


def _run_git(repo: str, *args, timeout=12):
    try:
        p = subprocess.run([GIT, "-C", repo, *args], capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception:
        return 1, "", "exc"


def _turn_key(data: dict) -> str:
    """One key per genuine human turn (ignores tool_result user-events)."""
    tp = data.get("transcript_path")
    try:
        if tp and Path(tp).exists():
            last = None
            with Path(tp).open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    msg = ev.get("message") or {}
                    role = msg.get("role") or ev.get("role") or ev.get("type")
                    if role != "user":
                        continue
                    content = msg.get("content")
                    is_tool_result = isinstance(content, list) and any(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content)
                    if is_tool_result:
                        continue
                    last = ev.get("uuid") or last
            if last:
                return "u_" + str(last)[:24]
    except Exception:
        pass
    return "t_" + str(int(time.time() // 120))


def _state_path(sid: str) -> Path:
    return CKPT_ROOT / sid / "state.json"


def _load_state(sid: str) -> dict:
    try:
        return json.loads(_state_path(sid).read_text(encoding="utf-8"))
    except Exception:
        return {"git_turns": [], "copied": []}


def _save_state(sid: str, st: dict) -> None:
    try:
        _state_path(sid).parent.mkdir(parents=True, exist_ok=True)
        # keep state bounded
        st["git_turns"] = st.get("git_turns", [])[-200:]
        st["copied"] = st.get("copied", [])[-2000:]
        _state_path(sid).write_text(json.dumps(st), encoding="utf-8")
    except Exception:
        pass


def _index_append(sid: str, rec: dict) -> None:
    try:
        d = CKPT_ROOT / sid
        d.mkdir(parents=True, exist_ok=True)
        with (d / "index.ndjson").open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _git_toplevel(path_dir: str):
    if not GIT:
        return None
    rc, out, _ = _run_git(path_dir, "rev-parse", "--show-toplevel")
    return out if rc == 0 and out else None


def _checkpoint_git(sid: str, repo: str, turn: str, file_path: str) -> dict:
    """Create a stash-create snapshot for `repo` (idempotent per turn). Returns record."""
    sha = ""
    rc, out, _ = _run_git(repo, "stash", "create",
                          f"claude-checkpoint turn={turn}")
    if rc == 0 and out:
        sha = out.splitlines()[-1].strip()
        ref = f"refs/claude-checkpoints/{turn}"
        _run_git(repo, "update-ref", ref, sha)
        kind, restore = "git-stash", sha
    else:
        # Clean tree (no dirty changes) -> the restore point is just HEAD.
        rc2, head, _ = _run_git(repo, "rev-parse", "HEAD")
        kind, restore = "git-head-clean", (head if rc2 == 0 else "")
    return {"ts": time.time(), "turn": turn, "type": kind, "repo": repo,
            "restore": restore, "trigger_file": file_path}


def _checkpoint_copy(sid: str, turn: str, file_path: str) -> dict | None:
    """Copy a single file (non-git) into the checkpoints dir, once per (turn,file)."""
    src = Path(file_path)
    if not src.exists() or not src.is_file():
        return None  # brand-new file (Write of a non-existent path) -> nothing to back up
    try:
        if src.stat().st_size > MAX_COPY_BYTES:
            return None
    except Exception:
        return None
    dest_dir = CKPT_ROOT / sid / "copies" / turn
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    try:
        shutil.copy2(src, dest)
    except Exception:
        return None
    return {"ts": time.time(), "turn": turn, "type": "copy",
            "copy_path": str(dest), "original": str(src), "trigger_file": file_path}


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("EDIT_CHECKPOINTS", "").lower() in ("off", "0", "false"):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
            return 0
        ti = data.get("tool_input") or {}
        fp = ti.get("file_path")
        if not fp:
            return 0
        cwd = data.get("cwd") or os.getcwd()
        if not os.path.isabs(fp):
            fp = os.path.join(cwd, fp)
        sid = str(data.get("session_id") or "default").replace("/", "_").replace("\\", "_")
        turn = _turn_key(data)
        st = _load_state(sid)

        file_dir = os.path.dirname(fp) or cwd
        repo = _git_toplevel(file_dir) if os.path.isdir(file_dir) else None

        if repo:
            key = f"{turn}|{repo}"
            if key in st.get("git_turns", []):
                return 0  # already snapshotted this repo this turn
            rec = _checkpoint_git(sid, repo, turn, fp)
            st.setdefault("git_turns", []).append(key)
            _index_append(sid, rec)
        else:
            key = f"{turn}|{fp}"
            if key in st.get("copied", []):
                return 0
            rec = _checkpoint_copy(sid, turn, fp)
            st.setdefault("copied", []).append(key)
            if rec:
                _index_append(sid, rec)
        _save_state(sid, st)
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
