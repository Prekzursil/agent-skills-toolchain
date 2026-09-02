#!/usr/bin/env python3
"""Measure the EAGER-LOAD surface the gateway/lazy-activation architecture targets:
skill descriptions injected at turn 0, always-on rules, marketplace manifest fan-out,
and the skills/ vs .agents/skills duplication.

Terminal state: SUCCESS:gwlazy-eager / FAILED:gwlazy-eager <reason>
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_eager_out.json"
res: dict = {"probe": "gwlazy-eager"}

FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def frontmatter(text: str):
    m = FM.match(text.replace("\r\n", "\n"))
    return m.group(1) if m else None


def skill_survey(root: Path) -> dict:
    out = {"root": str(root.relative_to(REPO)).replace("\\", "/"), "skills": 0,
           "desc_bytes": 0, "body_bytes": 0, "no_frontmatter": 0, "no_description": 0,
           "max_desc_bytes": 0, "max_desc_name": None}
    if not root.exists():
        out["MISSING"] = True
        return out
    for p in root.rglob("SKILL.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        out["skills"] += 1
        out["body_bytes"] += len(t.encode())
        fm = frontmatter(t)
        if fm is None:
            out["no_frontmatter"] += 1
            continue
        m = re.search(r"^description:\s*(.*)$", fm, re.M)
        if not m:
            out["no_description"] += 1
            continue
        d = m.group(1).strip()
        nb = len(d.encode())
        out["desc_bytes"] += nb
        if nb > out["max_desc_bytes"]:
            out["max_desc_bytes"] = nb
            out["max_desc_name"] = p.parent.name
    return out


res["skills_repo"] = skill_survey(REPO / "skills")
res["skills_agents_mirror"] = skill_survey(REPO / ".agents/skills")
res["skills_claude_only"] = skill_survey(REPO / "skills-claude-only")


def index(root: Path) -> dict:
    d = {}
    if not root.exists():
        return d
    for p in root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            d[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return d


a = index(REPO / "skills")
b = index(REPO / ".agents/skills")
common = set(a) & set(b)
res["dup_skills_vs_agents"] = {
    "skills_files": len(a),
    "agents_files": len(b),
    "common_paths": len(common),
    "identical_bytes": sum(1 for k in common if a[k] == b[k]),
    "differing_bytes": sum(1 for k in common if a[k] != b[k]),
    "only_in_skills": len(set(a) - set(b)),
    "only_in_agents": len(set(b) - set(a)),
}

rules = {"total": 0, "always_on_no_paths": [], "lazy_with_paths": [],
         "always_on_bytes": 0, "lazy_bytes": 0}
for p in (REPO / "rules").rglob("*.md"):
    if not p.is_file():
        continue
    rules["total"] += 1
    t = p.read_text(encoding="utf-8", errors="replace")
    fm = frontmatter(t)
    rel = str(p.relative_to(REPO)).replace("\\", "/")
    if fm and re.search(r"^paths:", fm, re.M):
        rules["lazy_with_paths"].append(rel)
        rules["lazy_bytes"] += len(t.encode())
    else:
        rules["always_on_no_paths"].append(rel)
        rules["always_on_bytes"] += len(t.encode())
rules["always_on_count"] = len(rules["always_on_no_paths"])
rules["lazy_count"] = len(rules["lazy_with_paths"])
res["rules"] = rules

mk = REPO / ".claude-plugin"
if mk.exists():
    res["marketplace_files"] = sorted(
        str(p.relative_to(REPO)).replace("\\", "/") for p in mk.rglob("*") if p.is_file()
    )
    for p in mk.rglob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        res.setdefault("marketplace_manifests", {})[p.name] = {
            "keys": sorted(d.keys()) if isinstance(d, dict) else type(d).__name__,
            "plugins": len(d.get("plugins", [])) if isinstance(d, dict) else None,
            "bytes": p.stat().st_size,
        }

hk = REPO / "hooks/_dispatch/manifest.json"
if hk.exists():
    m = json.loads(hk.read_text(encoding="utf-8"))
    ev = m.get("events", m)
    rows = {}
    if isinstance(ev, dict):
        for name, body in ev.items():
            if isinstance(body, dict):
                ch = body.get("checks") or []
                rows[name] = {
                    "checks": len(ch),
                    "settings_timeout": body.get("settings_timeout"),
                    "wall_cap": body.get("wall_cap", "ABSENT"),
                    "budget_sum": sum(c.get("timeout", 0) or 0 for c in ch),
                }
    res["repo_manifest"] = {"events": rows, "event_count": len(rows),
                            "total_checks": sum(r["checks"] for r in rows.values())}

hd = REPO / "hooks"
if hd.exists():
    res["repo_hook_dirs"] = sorted(
        p.name for p in hd.iterdir() if p.is_dir() and not p.name.startswith("_")
    )
    res["repo_hook_dir_count"] = len(res["repo_hook_dirs"])

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res, indent=2)[:7000])
print(f"\nwrote {OUT}")
print("SUCCESS:gwlazy-eager")
