"""Which breaking rows this repo is still coded against."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / ".claude-plugin" / "plugin.json"

SCAN_ROOTS = (
    REPO / ".claude-plugin",
    REPO / "hooks",
    REPO / "tools" / "plugin",
)
SKIP_PARTS = ("/tests/", "/fixtures/", "/__pycache__/")

OLD_PATTERNS = (
    ("user_config_interpolation", re.compile(r"\$\{user_config\.")),
    ("pluginConfigs_project", re.compile(r"pluginConfigs")),
    ("headersHelper", re.compile(r"headersHelper")),
    ("mcp_at_mention_enable", re.compile(r"@-mention MCP|@mcp\b", re.I)),
)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = "/" + p.relative_to(REPO).as_posix() + "/"
            if any(s in rel for s in SKIP_PARTS):
                continue
            if p.suffix.lower() in {".pyc", ".png", ".jpg"}:
                continue
            files.append(p)
    return files


def load_plugin_manifest() -> dict[str, Any]:
    if not PLUGIN.is_file():
        return {"present": False, "path": ".claude-plugin/plugin.json"}
    data = json.loads(PLUGIN.read_text(encoding="utf-8"))
    return {
        "present": True,
        "path": ".claude-plugin/plugin.json",
        "name": data.get("name"),
        "version": data.get("version"),
        "min_client_version": data.get("min_client_version"),
        "supported_clients": data.get("supported_clients"),
        "keys": sorted(data.keys()) if isinstance(data, dict) else [],
    }


def grep_old_contracts() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {k: [] for k, _ in OLD_PATTERNS}
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(REPO).as_posix()
        for name, rx in OLD_PATTERNS:
            if rx.search(text):
                hits[name].append(rel)
    return hits


def presence() -> dict[str, Any]:
    return {
        "hooks_json": (REPO / "hooks" / "hooks.json").is_file(),
        "mcp_json": (REPO / ".mcp.json").is_file(),
        "plugin_root_skill_md": (REPO / ".claude-plugin" / "SKILL.md").is_file(),
        "hooks_dir_nonempty": any((REPO / "hooks").rglob("*"))
        if (REPO / "hooks").is_dir()
        else False,
        "hooks_shared": (REPO / "hooks" / "_shared" / "use_vs_mention.py").is_file(),
    }


def classify_row(row: dict[str, Any], hits: dict[str, list[str]], manifest: dict[str, Any]) -> dict[str, Any]:
    excerpt = str(row.get("changelog_excerpt") or "")
    surface = str(row.get("surface") or "")
    old = False
    reason = "NOT-USED"
    if "user_config" in excerpt and hits["user_config_interpolation"]:
        old = True
        reason = "CODED-AGAINST:${user_config} still present"
    elif "pluginConfigs" in excerpt and hits["pluginConfigs_project"]:
        old = True
        reason = "CODED-AGAINST:pluginConfigs still present"
    elif "headersHelper" in excerpt and hits["headersHelper"]:
        old = True
        reason = "CODED-AGAINST:headersHelper still present"
    elif "@-mention MCP" in excerpt and hits["mcp_at_mention_enable"]:
        old = True
        reason = "CODED-AGAINST:@-mention MCP enable still present"
    elif surface in {"hook", "mcp", "skill", "plugin", "mixed"}:
        reason = "NOT-USED: plugin payload does not ship that host contract"
    floor = str(manifest.get("min_client_version") or "")
    return {
        "repo_still_uses_old_contract": old,
        "repo_status": "CODED-AGAINST" if old else "NOT-USED",
        "reason": reason,
        "min_client_version": floor,
        "floor_allows_prechange_clients": bool(floor) and floor == "1.0.0",
    }


def scan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = load_plugin_manifest()
    hits = grep_old_contracts()
    coded = []
    annotated = []
    for row in rows:
        extra = classify_row(row, hits, manifest)
        merged = dict(row)
        merged.update(extra)
        annotated.append(merged)
        if extra["repo_still_uses_old_contract"]:
            coded.append(merged["id"])
    return {
        "manifest": manifest,
        "presence": presence(),
        "old_contract_hits": hits,
        "coded_against_ids": coded,
        "rows": annotated,
    }
