#!/usr/bin/env python3
"""Where am I, and what else is running? (directives D-7 and D-8)

WHY THIS EXISTS
Owner, 2026-09-24:
  D-7 "there needs to be context awarness, and where session lives, maybe its on
       another computer or in cloud"
  D-8 "awarness regarding subagents concurrent stuff not to kill"

D-8 nearly bit this session: an edit to cv/profile.yaml was about to land while
eight verify agents were reading the copy a workflow agent had just written.
Editing underneath them would not have crashed anything -- it would have made
them report a mismatch that was not real. Silent damage, not loud failure.

WHAT IT ANSWERS
  WHERE   this host, whether it is the disposable VM or home, which peers are
          reachable right now, and which machine holds what
  RUNNING background shells, live workflow agents, other Claude sessions
  DO-NOT-TOUCH  files an agent is actively writing

DESIGN
  Read-only. Fast. Never kills anything -- it exists so a human or an agent can
  decide NOT to. Fails open and prints what it could determine rather than
  erroring on a missing piece.

Usage:
  python scripts/estate-context.py            # full report
  python scripts/estate-context.py --brief    # one line, for a hook
  python scripts/estate-context.py --busy     # exit 1 if concurrent work is live
"""
from __future__ import annotations

import datetime
import glob
import os
import socket
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
TS = r"C:\Program Files\Tailscale\tailscale.exe"
PROJECTS = os.path.join(HOME, ".claude", "projects")
ACTIVE_WINDOW_S = 300  # a file written in the last 5 min means live work


def _run(cmd, timeout=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


def where():
    host = socket.gethostname()
    info = {"host": host, "cwd": os.getcwd(), "user": os.environ.get("USERNAME", "?")}
    # This estate has exactly two machines with known roles. Naming the role
    # matters more than the hostname: "disposable" changes what you should do.
    role = {
        "offload-w2025": "VM, DISPOSABLE - can be shut down without warning; "
                         "nothing here is safe until it is pushed",
        "desktop-a60s9gp": "HOME desktop - the durable side; holds the fuller "
                           "basic-memory vault (1,126 notes vs the VM's 717)",
    }
    info["role"] = role.get(host.lower(), "unknown host - role not recorded")

    peers = []
    out = _run([TS, "status"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].count(".") == 3:
            name = parts[1]
            offline = "offline" in line
            last = ""
            if offline and "last seen" in line:
                last = line.split("last seen", 1)[1].strip().rstrip(",")
            peers.append({"name": name, "ip": parts[0],
                          "state": "offline" if offline else "online",
                          "last_seen": last, "self": name.lower() == host.lower()})
    info["peers"] = peers
    return info


def running():
    """Concurrent work. Anything here is a DO-NOT-KILL candidate."""
    now = time.time()
    out = {"workflow_agents": [], "sessions": [], "bg_tasks": []}

    # live workflow agents: transcript files written very recently
    for jl in glob.glob(os.path.join(PROJECTS, "*", "*", "subagents", "workflows",
                                     "*", "agent-*.jsonl")):
        try:
            age = now - os.path.getmtime(jl)
        except Exception:
            continue
        if age < ACTIVE_WINDOW_S:
            wf = os.path.basename(os.path.dirname(jl))
            out["workflow_agents"].append({"workflow": wf,
                                           "agent": os.path.basename(jl)[:24],
                                           "age_s": int(age)})

    # other Claude sessions: session transcripts touched recently
    for jl in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        try:
            age = now - os.path.getmtime(jl)
        except Exception:
            continue
        if age < ACTIVE_WINDOW_S:
            out["sessions"].append({"session": os.path.basename(jl)[:8],
                                    "project": os.path.basename(os.path.dirname(jl)),
                                    "age_s": int(age)})

    # background shells this session spawned
    for f in glob.glob(os.path.join(os.environ.get("TEMP", "/tmp"), "claude", "*",
                                    "*", "tasks", "*.output")):
        try:
            age = now - os.path.getmtime(f)
        except Exception:
            continue
        if age < ACTIVE_WINDOW_S:
            out["bg_tasks"].append({"task": os.path.basename(f)[:12],
                                    "age_s": int(age)})
    return out


def do_not_touch(run):
    """Files a live agent is plausibly mid-write on."""
    if not run["workflow_agents"]:
        return []
    # A live workflow means anything it was told to edit is unsafe to edit.
    # We cannot know the file list from here, so name the risk, not a false list.
    return ["%d workflow agent(s) are live -- do NOT edit files they were scoped "
            "to, and do NOT kill their processes. Wait for the run, or read "
            "journal.jsonl to see what they touched."
            % len(run["workflow_agents"])]


def main(argv):
    brief = "--brief" in argv
    busy_mode = "--busy" in argv
    w = where()
    r = running()
    live = len(r["workflow_agents"])

    if brief:
        peers = [p for p in w["peers"] if not p["self"]]
        on = sum(1 for p in peers if p["state"] == "online")
        print("host=%s role=%s peers=%d/%d online workflow_agents=%d sessions=%d"
              % (w["host"], w["role"].split(",")[0], on, len(peers), live,
                 len(r["sessions"])))
        return 1 if (busy_mode and live) else 0

    print("WHERE THIS SESSION LIVES")
    print("  host : %s  (user %s)" % (w["host"], w["user"]))
    print("  role : %s" % w["role"])
    print("  cwd  : %s" % w["cwd"])
    print("  time : %s" % datetime.datetime.now().replace(microsecond=0))
    print()
    print("REACHABLE MACHINES")
    if not w["peers"]:
        print("  (tailscale not readable)")
    for p in w["peers"]:
        tag = " <- this machine" if p["self"] else ""
        extra = ("  last seen %s" % p["last_seen"]) if p["last_seen"] else ""
        print("  %-18s %-16s %s%s%s" % (p["name"], p["ip"], p["state"], extra, tag))
    print()
    print("CONCURRENT WORK  (do not kill, do not edit underneath)")
    print("  live workflow agents : %d" % live)
    for a in r["workflow_agents"][:8]:
        print("      %s  %s  (%ds ago)" % (a["workflow"][:20], a["agent"], a["age_s"]))
    print("  recently active sessions : %d" % len(r["sessions"]))
    for s in r["sessions"][:6]:
        print("      %s in %s (%ds ago)" % (s["session"], s["project"][:28], s["age_s"]))
    print("  background shells : %d" % len(r["bg_tasks"]))
    warn = do_not_touch(r)
    if warn:
        print()
        for x in warn:
            print("  !! " + x)
    return 1 if (busy_mode and live) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
