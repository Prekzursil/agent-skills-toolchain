"""Shared corpus walk and token extract for ADV-0019. Inventory resolvers stay probe-local."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0019"
RETIRED = ("get_budget", "check_budget")
KNOWN_PRESENT = "python3"
GHOST_MCP = "mcp__ghostbridge__vanish"
GHOST_CLI = "agentbridge-budget"
PLUGIN_NAME = "AgentBridge"
FIXTURE_CORPUS = HERE / "fixtures" / "instruction-corpus"
PLUGIN_STATE_PATH = HERE / "fixtures" / "live-inventory" / "plugin-state.json"
MCP_SCHEMA_PATH = HERE / "fixtures" / "live-inventory" / "mcp-tools.schema.json"

NAMED_RE = re.compile(
    r"mcp__[A-Za-z0-9][A-Za-z0-9_-]*__[A-Za-z0-9][A-Za-z0-9_-]*"
    r"|\b(?:get_budget|check_budget|agentbridge-budget|AgentBridge|python3)\b"
)
RUN_RE = re.compile(r"(?:^|\n)\s*-?\s*run:\s+(\S+)", re.I)
BACKTICK_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_-]{1,48})`")
KEEP_BACKTICK = frozenset(
    {KNOWN_PRESENT, GHOST_CLI, *RETIRED, "git", "pwsh", "powershell"}
)
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "adversarial",
        "receipts",
    }
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def parse_frontmatter_tools(text: str) -> list[str]:
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    if end < 0:
        return []
    tools: list[str] = []
    in_tools = False
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if stripped.startswith("tools:"):
            in_tools = True
            rest = stripped.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                if inner:
                    tools.extend(x.strip().strip("\"'") for x in inner.split(","))
            continue
        if in_tools:
            if stripped.startswith("- "):
                tools.append(stripped[2:].strip().strip("\"'"))
            elif stripped and not line[:1].isspace():
                in_tools = False
    return [t for t in tools if t]


def classify_file(path: Path) -> str:
    posix = path.as_posix().replace("\\", "/")
    name = path.name.lower()
    if name == "skill.md" or "/skills/" in posix:
        return "skill"
    if path.suffix.lower() == ".mdc" or "/rules/" in posix:
        return "rule"
    if "/agents/" in posix or name in {"agents.md", "agent.md"}:
        return "agent"
    if "/commands/" in posix:
        return "command"
    if "/workflows/" in posix or path.suffix.lower() in {".yml", ".yaml"}:
        return "workflow"
    return "other"


def extract_from_text(text: str, path: Path) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def add(name: str, how: str) -> None:
        name = name.strip().strip("\"'")
        if not name:
            return
        rec = found.setdefault(
            name,
            {"name": name, "how": [], "paths": [], "classes": []},
        )
        if how not in rec["how"]:
            rec["how"].append(how)
        rp = rel(path)
        if rp not in rec["paths"]:
            rec["paths"].append(rp)
        cls = classify_file(path)
        if cls not in rec["classes"]:
            rec["classes"].append(cls)

    for t in parse_frontmatter_tools(text):
        add(t, "frontmatter-tools")
    for m in NAMED_RE.finditer(text):
        add(m.group(0), "named-token")
    for m in RUN_RE.finditer(text):
        token = m.group(1).split()[0].split("/")[-1]
        if token in KEEP_BACKTICK or token in RETIRED or token == GHOST_CLI:
            add(token, "workflow-run")
    for m in BACKTICK_RE.finditer(text):
        token = m.group(1)
        if token in KEEP_BACKTICK or token.startswith("mcp__"):
            add(token, "backtick")
    return list(found.values())


def fixture_files() -> list[Path]:
    if not FIXTURE_CORPUS.is_dir():
        return []
    return sorted(p for p in FIXTURE_CORPUS.rglob("*") if p.is_file())


def estate_instruction_files() -> list[Path]:
    out: list[Path] = []
    singles = [
        REPO / "AGENTS.md",
        REPO / "CLAUDE.md",
        REPO / ".cursorrules",
        REPO / "command-center" / "AGENTS.md",
    ]
    for p in singles:
        if p.is_file():
            out.append(p)
    roots = [
        REPO / "skills",
        REPO / "plugins",
        REPO / "rules",
        REPO / "agents",
        REPO / "commands",
        REPO / ".cursor",
        REPO / ".github" / "workflows",
        REPO / "command-center" / "skills",
        REPO / "command-center" / "plugins",
    ]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            out.append(root)
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            if p.suffix.lower() in {".md", ".mdc", ".yml", ".yaml", ".json"}:
                out.append(p)
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def load_corpus() -> dict[str, Any]:
    fixture = fixture_files()
    estate = estate_instruction_files()
    hits: dict[str, dict[str, Any]] = {}
    files_read = []
    for path, origin in [(p, "fixture") for p in fixture] + [
        (p, "estate") for p in estate
    ]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_read.append({"path": rel(path), "origin": origin, "bytes": len(text)})
        for rec in extract_from_text(text, path):
            name = rec["name"]
            slot = hits.setdefault(
                name,
                {
                    "name": name,
                    "how": [],
                    "paths": [],
                    "classes": [],
                    "origins": [],
                },
            )
            for k in ("how", "paths", "classes"):
                for item in rec[k]:
                    if item not in slot[k]:
                        slot[k].append(item)
            if origin not in slot["origins"]:
                slot["origins"].append(origin)
    return {
        "files_read": files_read,
        "file_count": len(files_read),
        "fixture_count": len(fixture),
        "estate_count": len(estate),
        "tokens": sorted(hits.values(), key=lambda r: r["name"]),
        "token_names": sorted(hits),
    }


def load_plugin_state() -> dict[str, Any]:
    doc = json.loads(PLUGIN_STATE_PATH.read_text(encoding="utf-8"))
    live_root = REPO / ".plugin-state.json"
    if live_root.is_file():
        try:
            live = json.loads(live_root.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            live = None
        if isinstance(live, dict):
            return {"fixture": doc, "estate": live, "merged": True}
    return doc


def enabled_plugins(state: dict[str, Any]) -> dict[str, bool]:
    if "fixture" in state and isinstance(state.get("fixture"), dict):
        packages = dict(state["fixture"].get("packages") or {})
        packages.update((state.get("estate") or {}).get("packages") or {})
    else:
        packages = state.get("packages") or {}
    out: dict[str, bool] = {}
    for name, rec in packages.items():
        if isinstance(rec, dict):
            out[name] = bool(rec.get("enabled"))
        else:
            out[name] = False
    return out


def load_mcp_schema() -> dict[str, Any]:
    return json.loads(MCP_SCHEMA_PATH.read_text(encoding="utf-8"))


def mcp_tool_names(schema: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    servers = schema.get("servers") or {}
    for server, body in servers.items():
        if not isinstance(body, dict):
            continue
        if not body.get("enabled", True):
            continue
        names.add(str(server))
        for tool in body.get("tools") or []:
            if isinstance(tool, str):
                names.add(tool)
                names.add(f"mcp__{server}__{tool}")
            elif isinstance(tool, dict) and tool.get("name"):
                n = str(tool["name"])
                names.add(n)
                names.add(f"mcp__{server}__{n}")
    return names


def catalog_unit() -> dict[str, Any]:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for u in catalog.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return u
    raise RuntimeError("ADV-0019 missing from WORK-UNIT-CATALOG.json")


load_corpus = load_corpus
load_mcp_schema = load_mcp_schema
mcp_tool_names = mcp_tool_names
enabled_plugins = enabled_plugins
