#!/usr/bin/env python3
"""build-workflow-registry — sweep ALL workflow roots (incl. session-embedded) into one registry.

The scatter (measured 2026-09-30): 9 live ~/.claude/workflows, 3 ~/.agents/workflows,
12 repo agent-self/config/workflows, and 518 session-embedded scripts under
~/.claude/projects/*/workflows/ — the 'unsaved' class nothing tracked. This makes
them all visible in one generated registry (regen anytime; the map is cheap).

Output: ~/.agents/knowledge/workflows-registry.json (+ .md digest)
Exit: SUCCESS:workflow-registry <counts> / FAILED:workflow-registry <reason>
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
OUT_DIR = os.path.join(HOME, ".agents", "knowledge")
ROOTS = [
    ("live-claude", os.path.join(HOME, ".claude", "workflows"), "*.js"),
    ("shared-agents", os.path.join(HOME, ".agents", "workflows"), None),
    ("repo-canonical", os.path.join(HOME, "source", "agent-skills-toolchain",
                                    "agent-self", "config", "workflows"), None),
]
SESSION_GLOB_PARENT = os.path.join(HOME, ".claude", "projects")

META_NAME = re.compile(r"name\s*[:=]\s*['\"]([^'\"]+)['\"]")
PHASE_TITLE = re.compile(r"title\s*:\s*['\"]([^'\"]+)['\"]")
MODEL_RE = re.compile(r"model\s*:\s*['\"]([^'\"]+)['\"]")


def sha8(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def parse_js(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError as e:
        return {"error": str(e)[:80]}
    name = META_NAME.search(src)
    phases = PHASE_TITLE.findall(src)
    models = sorted(set(MODEL_RE.findall(src)))
    return {
        "meta_name": name.group(1) if name else None,
        "phases": phases[:12],
        "models": models,
        "bytes": len(src),
    }


def collect():
    rows = []
    for label, root, _ in ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if "_bak" in dirpath:
                continue  # snapshots stay snapshots; note in digest, not rows
            for fn in sorted(files):
                if not fn.endswith((".js", ".mjs", ".yaml", ".yml", ".json")):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    row = {
                        "class": label,
                        "file": fn,
                        "path": p,
                        "mtime": datetime.fromtimestamp(
                            os.path.getmtime(p), tz=timezone.utc
                        ).strftime("%Y-%m-%d"),
                    }
                    row["sha8"] = sha8(p)
                    if fn.endswith((".js", ".mjs")):
                        row.update(parse_js(p))
                except OSError as e:
                    # Reserved-name entries (stray NUL in ~/.claude/workflows) and
                    # unreadable files are skipped with a WARN, never fatal. 2026-10-13
                    print(f"WARN:workflow-registry skipped {p!r}: {e}")
                    continue
                rows.append(row)
    # session-embedded class: ~/.claude/projects/<proj>/<session>/workflows/**
    if os.path.isdir(SESSION_GLOB_PARENT):
        try:
            projects = sorted(os.listdir(SESSION_GLOB_PARENT))
        except OSError as e:
            print(f"WARN:workflow-registry listdir failed "
                  f"on {SESSION_GLOB_PARENT}: {e}")
            projects = []
        for proj in projects:
            pproj = os.path.join(SESSION_GLOB_PARENT, proj)
            if not os.path.isdir(pproj):
                continue
            for dirpath, _dirs, files in os.walk(pproj):
                if not (dirpath.endswith("workflows") or "workflows" in dirpath):
                    continue
                for fn in sorted(files):
                    if not fn.endswith((".js", ".mjs")):
                        continue
                    p = os.path.join(dirpath, fn)
                    try:
                        rel = os.path.relpath(p, pproj).replace("\\", "/")
                        sess = rel.split("/")[0] if "/" in rel else "-"
                        row = {
                            "class": "session-embedded",
                            "file": re.sub(r"-wf_[0-9a-f-]+", "", fn),
                            "path": p,
                            "project": proj[:28],
                            "session": sess,
                            "mtime": datetime.fromtimestamp(
                                os.path.getmtime(p), tz=timezone.utc
                            ).strftime("%Y-%m-%d"),
                        }
                        row.update(parse_js(p))
                    except OSError as e:
                        print(f"WARN:workflow-registry skipped {p!r}: {e}")
                        continue
                    rows.append(row)
    return rows


def main():
    rows = collect()
    by_class = {}
    for r in rows:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1
    # duplicate detection on meta_name across durable roots
    seen = {}
    dupes = []
    for r in rows:
        mn = r.get("meta_name")
        if not mn or r["class"] == "session-embedded":
            continue
        if mn in seen:
            dupes.append({"meta_name": mn, "a": seen[mn]["path"], "b": r["path"]})
        else:
            seen[mn] = r
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(
        {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "counts": by_class, "dupes": dupes, "rows": rows},
        open(os.path.join(OUT_DIR, "workflows-registry.json"), "w", encoding="utf-8"),
        indent=1,
    )
    # MD digest: durable-root table + session-embedded name histogram
    names = {}
    for r in rows:
        if r["class"] == "session-embedded":
            names[r["file"]] = names.get(r["file"], 0) + 1
    with open(os.path.join(OUT_DIR, "workflows-registry.md"), "w", encoding="utf-8") as f:
        f.write("# Workflows registry (generated — regen: scripts/build-workflow-registry.py)\n\n")
        f.write(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n")
        f.write("## Counts by class\n\n")
        for k, v in sorted(by_class.items()):
            f.write(f"- {k}: **{v}**\n")
        f.write("\n## Durable workflows\n\n| class | name | meta_name | models | mtime |\n|---|---|---|---|---|\n")
        for r in rows:
            if r["class"] != "session-embedded":
                f.write(f"| {r['class']} | {r['file'][:48]} | {r.get('meta_name') or '-'} | "
                        f"{','.join(r.get('models', [])) or '-'} | {r['mtime']} |\n")
        if dupes:
            f.write("\n## Duplicate meta_names across roots (reconcile)\n\n")
            for d in dupes:
                f.write(f"- `{d['meta_name']}`: {d['a']} <-> {d['b']}\n")
        f.write(f"\n## Session-embedded distinct names: {len(names)}\n\n")
        for n, c in sorted(names.items(), key=lambda x: -x[1])[:80]:
            f.write(f"- {n} (x{c})\n")
    print(f"SUCCESS:workflow-registry {json.dumps(by_class)} dupes={len(dupes)} "
          f"distinct_session_names={len(names)}")


if __name__ == "__main__":
    sys.exit(main())
