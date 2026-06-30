#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp-userscope-sync / heal.py  --  SessionStart backstop (self-healing, FAIL-OPEN)
================================================================================
Backstop for MCP / skills-mirror drift. The PRIMARY fix is USER-scope promotion
(promote-mcp-userscope.ps1), which makes the canonical MCP set load in every
NORMAL session on every drive. This hook is the belt-and-suspenders layer:

  1) MCP orphan heal  -- if the current tree is an *orphan* (NOT under the home
     dir, so it can never walk up to ~/.mcp.json, AND has no .mcp.json of its
     own up-tree), PLANT a copy of the canonical ~/.mcp.json at the tree root.
     CREATE-ONLY: it never overwrites an existing .mcp.json, and it skips any
     up-tree .mcp.json that contains 'mcp-funnel' (ralph) or lives under a
     plugins/node_modules/site-packages path.

  2) Skills-mirror heal -- keep ~/.agents/skills in sync with ~/.claude/skills
     (the mirror is a COPY, not a junction, so it can go stale). Bounded +
     throttled so SessionStart stays fast.

EVENTUAL CONSISTENCY (read this): SessionStart hooks fire AFTER Claude Code has
already loaded MCP servers for the current session. So anything this hook plants
takes effect only on the NEXT session in that tree (one session behind). That is
exactly why USER-scope promotion is the immediate primary and this is the backstop.

CONTRACT: wrapped in try/except end to end; ANY error -> print nothing, exit 0.
Never blocks. Never raises. Timeout budget is seconds (keep work bounded).

RALPH SAFETY: ralph launches with --setting-sources project,local, which excludes
USER scope -- so this hook (wired in ~/.claude/settings.json = user scope) does
NOT run in ralph sessions at all, and it never edits an existing .mcp.json. Ralph's
mcp-funnel project file is untouched.
"""

import sys
import os
import json
import time
import shutil

HOME = os.path.expanduser("~")
CANON_MCP = os.path.join(HOME, ".mcp.json")
CLAUDE_SKILLS = os.path.join(HOME, ".claude", "skills")
AGENTS_SKILLS = os.path.join(HOME, ".agents", "skills")
STATE_DIR = os.path.join(HOME, ".claude", "hooks", "mcp-userscope-sync")
SKILLS_STAMP = os.path.join(STATE_DIR, ".last-skills-heal")

SKILLS_THROTTLE_SEC = 6 * 3600  # only scan/sync the skills mirror every 6h
MAX_SKILL_SYNC = 30  # if more than this many skills drift, notify only
BAD_PATH_PARTS = ("node_modules", "site-packages")
BAD_PATH_SUBSTR = (
    os.path.join(".claude", "plugins"),
    os.path.join(".claude", "checkpoints"),
    os.path.join(".claude", "_config-backups"),
)


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def _is_under(child, parent):
    c, p = _norm(child), _norm(parent)
    return c == p or c.startswith(p + os.sep)


def _safe_path(p):
    n = _norm(p)
    if any(part in n.split(os.sep) for part in BAD_PATH_PARTS):
        return False
    if any(s in n for s in (os.path.normcase(x) for x in BAD_PATH_SUBSTR)):
        return False
    return True


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _canon_names():
    data = _read_json(CANON_MCP)
    return set((data.get("mcpServers") or {}).keys())


def _find_uptree_mcp(start):
    """Walk up from `start` to the drive root; return (path, text) of the nearest
    .mcp.json, else (None, None)."""
    cur = _norm(start)
    while True:
        cand = os.path.join(cur, ".mcp.json")
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    return cand, f.read()
            except Exception:
                return cand, ""
        parent = os.path.dirname(cur)
        if parent == cur:
            return None, None
        cur = parent


def _plant_root(start):
    """Choose where to plant a canonical .mcp.json for an orphan tree: nearest
    ancestor containing a .git, else the first-level dir under the drive root,
    else `start` itself."""
    cur = _norm(start)
    drive_root = os.path.splitdrive(cur)[0] + os.sep
    first_level = None
    walk = cur
    while True:
        if os.path.isdir(os.path.join(walk, ".git")):
            return walk
        parent = os.path.dirname(walk)
        if parent == walk:
            break
        if parent == _norm(drive_root):
            first_level = walk
        walk = parent
    return first_level or cur


def heal_mcp(cwd, actions):
    if not os.path.isfile(CANON_MCP):
        return
    # Under the home dir? Then the ~/.mcp.json walk-up already covers this tree.
    if _is_under(cwd, HOME):
        # Only note if the canonical source itself is missing up-tree (shouldn't happen).
        return
    path, text = _find_uptree_mcp(cwd)
    if path is not None:
        # An existing .mcp.json governs this tree. NEVER overwrite it.
        # (ralph mcp-funnel / dev repos / intentionally-curated sets are respected.)
        return
    # True orphan: no .mcp.json anywhere up-tree, and not under home.
    root = _plant_root(cwd)
    if not _safe_path(root):
        return
    target = os.path.join(root, ".mcp.json")
    if os.path.exists(target):
        return  # create-only
    try:
        with open(CANON_MCP, "r", encoding="utf-8") as src:
            canon_text = src.read()
        # defensive: never plant a funnel-bearing file (canonical never is, but be safe)
        if "mcp-funnel" in canon_text:
            return
        with open(target, "w", encoding="utf-8", newline="") as dst:
            dst.write(canon_text)
        actions.append(
            "planted canonical .mcp.json at %s (orphan tree -> next session gets the full MCP set)"
            % root
        )
    except Exception:
        return


def _dir_signature(d):
    """Cheap recursive signature of a skill dir: (file_count, max_mtime_ns)."""
    count = 0
    mx = 0
    for r, _dirs, files in os.walk(d):
        for fn in files:
            count += 1
            try:
                st = os.stat(os.path.join(r, fn))
                if st.st_mtime_ns > mx:
                    mx = st.st_mtime_ns
            except Exception:
                pass
    return count, mx


def heal_skills(actions):
    if not (os.path.isdir(CLAUDE_SKILLS) and os.path.isdir(AGENTS_SKILLS)):
        return
    # Throttle: only do the (relatively expensive) scan every SKILLS_THROTTLE_SEC.
    try:
        if (
            os.path.isfile(SKILLS_STAMP)
            and (time.time() - os.path.getmtime(SKILLS_STAMP)) < SKILLS_THROTTLE_SEC
        ):
            return
    except Exception:
        pass

    src_dirs = {
        n
        for n in os.listdir(CLAUDE_SKILLS)
        if os.path.isdir(os.path.join(CLAUDE_SKILLS, n))
    }
    dst_dirs = {
        n
        for n in os.listdir(AGENTS_SKILLS)
        if os.path.isdir(os.path.join(AGENTS_SKILLS, n))
    }

    drifted = []
    for name in src_dirs:
        s = os.path.join(CLAUDE_SKILLS, name)
        d = os.path.join(AGENTS_SKILLS, name)
        if name not in dst_dirs:
            drifted.append(name)
            continue
        sc, sm = _dir_signature(s)
        dc, dm = _dir_signature(d)
        # sync when the source (live ~/.claude/skills) is newer or differs in size
        if sc != dc or sm > dm:
            drifted.append(name)
    extras = sorted(
        dst_dirs - src_dirs
    )  # present only in mirror (reported, not deleted)

    # write throttle stamp regardless of outcome so we don't rescan every session
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(SKILLS_STAMP, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
    except Exception:
        pass

    if not drifted and not extras:
        return
    if len(drifted) > MAX_SKILL_SYNC:
        actions.append(
            "skills mirror: %d skills drifted (> %d) -- run a full resync manually "
            "(copy ~/.claude/skills -> ~/.agents/skills); auto-sync skipped to keep startup fast"
            % (len(drifted), MAX_SKILL_SYNC)
        )
        return
    synced = 0
    for name in drifted:
        s = os.path.join(CLAUDE_SKILLS, name)
        d = os.path.join(AGENTS_SKILLS, name)
        if not _safe_path(s):
            continue
        try:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(s, d)
            synced += 1
        except Exception:
            continue
    if synced:
        actions.append(
            "skills mirror: re-synced %d skill(s) ~/.claude/skills -> ~/.agents/skills"
            % synced
        )
    if extras:
        actions.append(
            "skills mirror: %d dir(s) exist only in ~/.agents/skills (not deleted): %s"
            % (
                len(extras),
                ", ".join(extras[:10]) + (" ..." if len(extras) > 10 else ""),
            )
        )


def main():
    actions = []
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    except Exception:
        raw = ""
    cwd = os.getcwd()
    try:
        if raw.strip():
            payload = json.loads(raw)
            cwd = payload.get("cwd") or cwd
    except Exception:
        pass

    try:
        heal_mcp(cwd, actions)
    except Exception:
        pass
    try:
        heal_skills(actions)
    except Exception:
        pass

    if actions:
        msg = "[mcp/skills drift backstop] " + " | ".join(actions)
        try:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": msg,
                        }
                    }
                )
            )
        except Exception:
            pass
    # FAIL-OPEN: always succeed.
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # absolute last-resort fail-open
        try:
            sys.exit(0)
        except Exception:
            os._exit(0)
