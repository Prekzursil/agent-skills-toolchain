#!/usr/bin/env python3
"""AUD-0080 Probe 1: enumerate permissions.allow/deny per settings scope; merge."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-allow-merge.json"
RAW = PROBE / "probe1-allow.raw.txt"

SCOPES = [
    ("user-agent-self", "agent-self/config/settings.json"),
    ("local-agent-self", "agent-self/config/settings.local.json"),
    ("project-claude", ".claude/settings.json"),
]


def load_perms(rel: str) -> dict:
    p = REPO / rel
    if not p.is_file():
        return {"path": rel, "exists": False, "allow": [], "deny": [], "ask": [], "hooks": {}}
    doc = json.loads(p.read_text(encoding="utf-8"))
    perms = doc.get("permissions") or {}
    hooks = doc.get("hooks") or {}
    hook_summary = {}
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        matchers = []
        for e in entries:
            if isinstance(e, dict) and "matcher" in e:
                matchers.append(e["matcher"])
        hook_summary[event] = {"count": len(entries), "matchers": matchers}
    return {
        "path": rel,
        "exists": True,
        "allow": list(perms.get("allow") or []),
        "deny": list(perms.get("deny") or []),
        "ask": list(perms.get("ask") or []),
        "defaultMode": perms.get("defaultMode"),
        "hooks": hook_summary,
    }


def main() -> int:
    scopes = []
    merged_allow: set[str] = set()
    merged_deny: set[str] = set()
    for name, rel in SCOPES:
        s = load_perms(rel)
        s["scope"] = name
        scopes.append(s)
        if s["exists"]:
            merged_allow.update(s["allow"])
            merged_deny.update(s["deny"])

    # Effective: allow minus deny exact (pattern overlap left NOT-CHECKED)
    effective = sorted(merged_allow - merged_deny)
    bashish = [a for a in effective if a == "Bash" or a.startswith("Bash(")]
    result = {
        "ok": True,
        "unit": "AUD-0080",
        "probe": 1,
        "scopes": [
            {
                "scope": s["scope"],
                "path": s["path"],
                "exists": s["exists"],
                "allow_count": len(s["allow"]),
                "deny_count": len(s["deny"]),
                "ask_count": len(s["ask"]),
                "defaultMode": s.get("defaultMode"),
                "allow": s["allow"],
                "deny": s["deny"],
                "hook_events": sorted((s.get("hooks") or {}).keys()),
                "hook_matcher_count": sum(
                    len(v.get("matchers") or []) for v in (s.get("hooks") or {}).values()
                ),
            }
            for s in scopes
        ],
        "merged_allow_count": len(merged_allow),
        "merged_deny_count": len(merged_deny),
        "effective_allow_count": len(effective),
        "effective_allow": effective,
        "bash_preapproved": bashish,
        "bypassPermissions_scopes": [
            s["scope"] for s in scopes if s.get("defaultMode") == "bypassPermissions"
        ],
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0080 NAMED PROBE 1: permissions.allow/deny per scope + merged set",
        "unit=AUD-0080",
    ]
    for s in result["scopes"]:
        lines.append(
            f"SCOPE\t{s['scope']}\texists={s['exists']}\tallow={s['allow_count']}\t"
            f"deny={s['deny_count']}\tdefaultMode={s.get('defaultMode')}\t"
            f"hook_events={s['hook_events']}\thook_matchers={s['hook_matcher_count']}"
        )
        for a in s["allow"][:30]:
            lines.append(f"  ALLOW\t{a}")
    lines.append(f"merged_allow_count={result['merged_allow_count']}")
    lines.append(f"effective_allow_count={result['effective_allow_count']}")
    lines.append(f"bash_preapproved={bashish}")
    lines.append(f"bypassPermissions_scopes={result['bypassPermissions_scopes']}")
    lines.append("SUCCESS:AUD-0080-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
