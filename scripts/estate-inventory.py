#!/usr/bin/env python3
"""Estate inventory: nothing disappears without a recorded reason.

WHY THIS EXISTS
Owner, 2026-09-24: "these types of stuff gone, regressed, disappeared shouldnt be
possible there should be a clear ssot ... so we dont know if they were gone
upgraded or just disappeared or other causes".

The concrete failure: 13 skills and 6 MCP servers vanished between 2026-06-29 and
2026-09-24 and NOBODY COULD SAY WHY. Measured:
  - 9 `devtu-*` skills have ZERO commits touching them -- `~/.agents/skills/` is a
    DEPLOYED tree, so a skill can exist, be indexed, and vanish with no git record
    at all.
  - `chatgpt5-web-*` WAS explained, by commit 365cd9e7 "consolidate 3->1" -- but
    that explanation lives in a commit message, not attached to the path, so
    `git log --diff-filter=D -- skills/chatgpt5-web-query` returns nothing.
  - Result: 0 of 13 had a retrievable explanation, and an assistant reported them
    as "genuinely gone" when the honest answer was "absent, cause unknown".

Git is not the SSOT here because the deployed tree is not fully tracked. This is.

WHAT IT DOES
  snapshot  record every skill / command / agent / MCP server with a content sha
  check     diff against the last snapshot; anything that DISAPPEARED without a
            recorded reason is reported UNEXPLAINED
  explain   attach a durable reason to a disappearance, once, forever

DESIGN FOR "BENEFICIAL, NOT BAD"
  - GENERATED, never hand-maintained. A hand-kept list decays; this is measured.
  - SILENT when nothing changed unexplainedly. It is not a report you read daily.
  - Explanations PERSIST. You explain a disappearance once and never again.
  - Additions are recorded but never nag -- gaining a skill is not a problem.
  - Fails open and is read-only except for its own two files.

Usage:
  python scripts/estate-inventory.py snapshot
  python scripts/estate-inventory.py check            # exit 1 if unexplained
  python scripts/estate-inventory.py explain <name> <state> "<reason>"
      states: RETIRED | MERGED-INTO:<target> | RENAMED-TO:<target> | LOST
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
import datetime

HOME = os.path.expanduser("~")
AGENTS = os.path.join(HOME, ".agents")
STORE = os.path.join(AGENTS, "knowledge", "INVENTORY.json")
REPORT = os.path.join(AGENTS, "knowledge", "INVENTORY.md")

VALID_STATE = re.compile(r"^(RETIRED|LOST|MERGED-INTO:.+|RENAMED-TO:.+)$")


def _sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except Exception:
        return ""


def _today():
    return datetime.date.today().isoformat()


def collect():
    """Everything the estate exposes, by kind. Measured, never assumed."""
    items = {}

    for md in glob.glob(os.path.join(AGENTS, "skills", "*", "SKILL.md")):
        name = os.path.basename(os.path.dirname(md))
        items["skill:" + name] = {"kind": "skill", "name": name,
                                  "path": md, "sha": _sha(md)}

    for md in glob.glob(os.path.join(HOME, ".claude", "commands", "**", "*.md"),
                        recursive=True):
        name = os.path.splitext(os.path.basename(md))[0]
        items["command:" + name] = {"kind": "command", "name": name,
                                    "path": md, "sha": _sha(md)}

    for md in glob.glob(os.path.join(HOME, ".claude", "agents", "*.md")):
        name = os.path.splitext(os.path.basename(md))[0]
        items["agent:" + name] = {"kind": "agent", "name": name,
                                  "path": md, "sha": _sha(md)}

    # MCP servers live in .claude.json after the promote-to-user-scope move, and
    # historically in .mcp.json. Read both or the count silently collapses.
    for cfg in (os.path.join(HOME, ".mcp.json"), os.path.join(HOME, ".claude.json")):
        try:
            with open(cfg, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        for s in (d.get("mcpServers") or {}):
            items.setdefault("mcp:" + s, {"kind": "mcp", "name": s,
                                          "path": cfg, "sha": ""})
        for proj in (d.get("projects") or {}).values():
            if isinstance(proj, dict):
                for s in (proj.get("mcpServers") or {}):
                    items.setdefault("mcp:" + s, {"kind": "mcp", "name": s,
                                                  "path": cfg, "sha": ""})
    return items


def load_store():
    try:
        with open(STORE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"version": 1, "items": {}, "history": []}


def save_store(store):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def cmd_snapshot(store, live):
    today = _today()
    added, changed = [], []
    for key, meta in live.items():
        rec = store["items"].get(key)
        if rec is None:
            store["items"][key] = dict(meta, state="ACTIVE",
                                       first_seen=today, last_seen=today)
            added.append(key)
        else:
            if rec.get("sha") and meta.get("sha") and rec["sha"] != meta["sha"]:
                changed.append(key)
            rec.update(meta)
            rec["last_seen"] = today
            # something that came back was not lost after all
            if rec.get("state") != "ACTIVE":
                rec["state"] = "ACTIVE"
                rec.pop("reason", None)
    # present in the store, absent from disk
    vanished = []
    for key, rec in store["items"].items():
        if key in live or rec.get("state") != "ACTIVE":
            continue
        rec["state"] = "UNEXPLAINED"
        rec["vanished_on"] = today
        vanished.append(key)
    if added or changed or vanished:
        store["history"].append({"date": today, "added": len(added),
                                 "changed": len(changed), "vanished": len(vanished)})
    return added, changed, vanished


def unexplained(store):
    return sorted(k for k, r in store["items"].items() if r.get("state") == "UNEXPLAINED")


def write_report(store):
    by_kind = {}
    for key, rec in store["items"].items():
        by_kind.setdefault(rec["kind"], []).append(rec)
    lines = [
        "# Estate inventory",
        "",
        "**Generated by `scripts/estate-inventory.py`. Do not hand-edit** -- a",
        "hand-kept list decays, which is the failure this file exists to prevent.",
        "",
        "Every skill, command, agent and MCP server the estate exposes, with a",
        "lifecycle state. Anything that disappears is flagged **UNEXPLAINED** until",
        "someone records why, so \"retired\", \"merged\", \"renamed\" and \"lost\" can",
        "never again be collapsed into \"gone\".",
        "",
        "Record a reason once and it persists:",
        "",
        "```",
        "python scripts/estate-inventory.py explain <name> RETIRED \"superseded by X\"",
        "python scripts/estate-inventory.py explain <name> MERGED-INTO:grill \"3->1 merge\"",
        "```",
        "",
        "Last updated %s." % _today(),
        "",
    ]
    ux = unexplained(store)
    if ux:
        lines += ["## Unexplained disappearances", "",
                  "These vanished with no recorded reason. Each is a gap.", "",
                  "| Item | Kind | Last seen | Vanished |", "|---|---|---|---|"]
        for k in ux:
            r = store["items"][k]
            lines.append("| `%s` | %s | %s | %s |" % (
                r["name"], r["kind"], r.get("last_seen", "?"), r.get("vanished_on", "?")))
        lines.append("")
    for kind in sorted(by_kind):
        rows = sorted(by_kind[kind], key=lambda r: r["name"])
        active = [r for r in rows if r.get("state") == "ACTIVE"]
        gone = [r for r in rows if r.get("state") not in ("ACTIVE", "UNEXPLAINED")]
        lines += ["## %s (%d active)" % (kind, len(active)), ""]
        if gone:
            lines += ["Retired or superseded:", "",
                      "| Item | State | Reason | Since |", "|---|---|---|---|"]
            for r in gone:
                lines.append("| `%s` | %s | %s | %s |" % (
                    r["name"], r.get("state", ""), r.get("reason", ""),
                    r.get("vanished_on", "")))
            lines.append("")
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    store = load_store()

    if cmd == "snapshot":
        added, changed, vanished = cmd_snapshot(store, collect())
        save_store(store)
        write_report(store)
        print("  added=%d changed=%d vanished=%d  tracked=%d"
              % (len(added), len(changed), len(vanished), len(store["items"])))
        for v in vanished:
            print("    VANISHED (now UNEXPLAINED):", v)
        print("SUCCESS:inventory-snapshot")
        return 0

    if cmd == "check":
        live = collect()
        tmp = json.loads(json.dumps(store))
        _, _, vanished = cmd_snapshot(tmp, live)
        ux = unexplained(tmp)
        if not ux:
            print("SUCCESS:inventory - %d items, nothing unexplained" % len(live))
            return 0
        print("  %d UNEXPLAINED disappearance(s):" % len(ux))
        for k in ux:
            print("    -", k)
        print("  record a reason:  python scripts/estate-inventory.py explain <name> <state> \"<why>\"")
        print("FAILED:inventory-unexplained")
        return 1

    if cmd == "explain":
        if len(argv) < 4:
            print("usage: explain <name> <state> \"<reason>\"")
            return 2
        name, state, reason = argv[1], argv[2], " ".join(argv[3:])
        if not VALID_STATE.match(state):
            print("  invalid state %r -- use RETIRED | LOST | MERGED-INTO:<t> | RENAMED-TO:<t>" % state)
            return 2
        hits = [k for k in store["items"] if k.split(":", 1)[1] == name or k == name]
        if not hits:
            # Retroactive record. Something that vanished BEFORE the first
            # snapshot is exactly what needs capturing -- refusing to record it
            # would lose the only knowledge anyone still has about it.
            kind = argv[4] if len(argv) > 4 else "skill"
            key = kind + ":" + name
            store["items"][key] = {"kind": kind, "name": name, "path": "",
                                   "sha": "", "state": state, "reason": reason,
                                   "first_seen": "before-baseline",
                                   "last_seen": "before-baseline",
                                   "vanished_on": "before 2026-09-24",
                                   "retroactive": True}
            save_store(store)
            write_report(store)
            print("  %s -> %s (RETROACTIVE: %s)" % (key, state, reason))
            print("SUCCESS:inventory-explain")
            return 0
        for k in hits:
            store["items"][k]["state"] = state
            store["items"][k]["reason"] = reason
            store["items"][k].setdefault("vanished_on", _today())
            print("  %s -> %s (%s)" % (k, state, reason))
        save_store(store)
        write_report(store)
        print("SUCCESS:inventory-explain")
        return 0

    print("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
