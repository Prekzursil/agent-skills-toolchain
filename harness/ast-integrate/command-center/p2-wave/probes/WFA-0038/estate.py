"""Estate grant boundary: H1-H9 plus settings.json allow/deny."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REPO = HERE.parents[3]

BAN_IDS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9")

H_TITLE = {
    "H1": "git-history-mutation",
    "H2": "secret-exfil",
    "H3": "fail-closed",
    "H4": "unrestricted-network-egress",
    "H5": "credential-read",
    "H6": "git-write",
    "H7": "force-operations",
    "H8": "arbitrary-shell",
    "H9": "owner-ops-bypass",
}

# Capabilities the catalog names as "estate would not grant".
CATALOG_DENY = frozenset(
    {
        "unrestricted-network-egress",
        "credential-read",
        "git-write",
        "force-operations",
        "arbitrary-shell",
        "git-history-mutation",
        "secret-exfil",
        "owner-ops-bypass",
    }
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def locate_rules(repo: Path) -> dict:
    """Prefer live tree copies; fall back to the unit fixture."""
    candidates = [
        repo / "rules" / "common" / "owner-ops-authorization.md",
        repo / "config" / "rules" / "common" / "owner-ops-authorization.md",
        Path.home() / ".claude" / "rules" / "common" / "owner-ops-authorization.md",
        FIXTURES / "owner-ops-authorization.md",
    ]
    hits = []
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            hits.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "rel": _rel(repo, path),
                    "source": "live" if path != FIXTURES / "owner-ops-authorization.md" else "fixture",
                }
            )
    chosen = None
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            chosen = path
            break
    return {"chosen": chosen, "hits": hits}


def locate_settings() -> dict:
    home = Path.home()
    candidates = [
        home / ".claude" / "settings.json",
        home / ".config" / "claude" / "settings.json",
        FIXTURES / "settings.permissions.json",
    ]
    hits = []
    chosen = None
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            rec = {
                "path": str(path),
                "bytes": path.stat().st_size,
                "source": "live" if path != FIXTURES / "settings.permissions.json" else "fixture",
            }
            hits.append(rec)
            if chosen is None:
                chosen = path
    return {"chosen": chosen, "hits": hits}


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_h_bans(text: str) -> list[dict]:
    bans = []
    for match in re.finditer(
        r"^H([1-9])[.)]\s+(.*?)(?=^H[1-9][.)]|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    ):
        hid = f"H{match.group(1)}"
        body = " ".join(match.group(2).split())
        bans.append(
            {
                "id": hid,
                "capability": H_TITLE[hid],
                "quote": body[:280],
            }
        )
    # Fixtures always enumerate H1-H9; if a live copy is a stub, keep fixture titles.
    have = {b["id"] for b in bans}
    for hid in BAN_IDS:
        if hid not in have:
            bans.append(
                {
                    "id": hid,
                    "capability": H_TITLE[hid],
                    "quote": f"{hid} not present in this copy; catalog/fixture title used.",
                    "absent_from_source": True,
                }
            )
    bans.sort(key=lambda b: b["id"])
    return bans


def parse_settings(path: Path | None) -> dict:
    allow: list[str] = []
    deny: list[str] = []
    raw = {}
    if path is None or not path.is_file():
        return {"allow": allow, "deny": deny, "raw_keys": [], "present": False}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"allow": allow, "deny": deny, "raw_keys": [], "present": False, "parse_error": True}
    block = raw.get("permissions") or raw.get("permission") or {}
    if isinstance(block, dict):
        for key in ("allow", "allowed", "permit"):
            val = block.get(key)
            if isinstance(val, list):
                allow.extend(str(x) for x in val if x)
        for key in ("deny", "denied", "block"):
            val = block.get(key)
            if isinstance(val, list):
                deny.extend(str(x) for x in val if x)
    return {
        "allow": _dedupe(allow),
        "deny": _dedupe(deny),
        "raw_keys": sorted(raw.keys()) if isinstance(raw, dict) else [],
        "present": True,
    }


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def load_estate(repo: Path | None = None) -> dict:
    repo = repo or REPO
    rules = locate_rules(repo)
    settings = locate_settings()
    chosen_rules: Path = rules["chosen"] or (FIXTURES / "owner-ops-authorization.md")
    text = _read(chosen_rules)
    bans = parse_h_bans(text)
    settings_doc = parse_settings(settings["chosen"])
    return {
        "rules_path": _rel(repo, chosen_rules) if chosen_rules else None,
        "rules_source": next(
            (h["source"] for h in rules["hits"] if Path(h["path"]) == chosen_rules),
            "fixture",
        ),
        "rules_hits": rules["hits"],
        "h_bans": bans,
        "settings_path": (
            settings["chosen"].as_posix() if settings["chosen"] else None
        ),
        "settings_source": next(
            (h["source"] for h in settings["hits"] if Path(h["path"]) == settings["chosen"]),
            "fixture",
        ),
        "settings": settings_doc,
        "catalog_deny_capabilities": sorted(CATALOG_DENY),
        "estate_allow": settings_doc.get("allow") or [],
        "estate_deny_tools": settings_doc.get("deny") or [],
    }


def grants(tool: str, estate: dict) -> str:
    """Would the estate grant this normalized tool/capability token?"""
    cap = tool.strip()
    if cap in CATALOG_DENY:
        return "DENY"
    allow = estate.get("estate_allow") or []
    deny = estate.get("estate_deny_tools") or []
    if _tool_matches(cap, deny):
        return "DENY"
    if _tool_matches(cap, allow):
        return "ALLOW"
    # Unknown tools are not silently granted.
    if cap in {"Read", "Grep", "Glob", "Write"}:
        return "ALLOW"
    if cap.startswith("Bash(python analysis only"):
        return "ALLOW"
    return "DENY"


def _tool_matches(cap: str, listed: list[str]) -> bool:
    cap_l = cap.lower()
    for item in listed:
        it = item.strip()
        if not it:
            continue
        if cap == it or cap_l == it.lower():
            return True
        if it.endswith("(*)") and cap_l.startswith(it[:-3].lower()):
            return True
        if it.startswith("Bash(") and cap.startswith("Bash("):
            if it == "Bash(*)":
                return True
    return False
