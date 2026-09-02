"""AUD-0063 agent-roster model audit.

Probe 1 extracts the frontmatter `model` FIELD (not a body grep).
Probe 2 classifies dispatching from declared tool permissions.

The opus floor applies to dispatchers (subagent-spawning or cross-vendor
tools). A file that merely mentions sonnet or Task in prose is not assigned
that model or those tools.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0063"

FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?\r?\n)---[ \t]*(?:\r?\n|$)", re.DOTALL)

DISPATCH_EXACT = frozenset(
    {
        "task",
        "agent",
        "taskcreate",
        "spawn",
        "spawnagent",
        "subagent",
        "tasktool",
    }
)
CROSS_VENDOR_PREFIXES = (
    "mcp__codex",
    "mcp__openai",
    "mcp__chatgpt",
    "mcp__gpt",
    "mcp__gemini",
    "mcp__google",
    "mcp__grok",
    "mcp__xai",
    "mcp__cursor",
    "mcp__copilot",
    "mcp__azure-openai",
)
TOOL_KEYS = (
    "tools",
    "allowed-tools",
    "allowed_tools",
    "tool_permissions",
    "tools_permissions",
)
BELOW_OPUS = frozenset({"sonnet", "haiku", "UNDECLARED"})


def split_frontmatter(text: str) -> tuple[str, str]:
    m = FM_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end() :]


def _unquote(val: str) -> str:
    v = val.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1].strip()
    return v


def parse_simple_yaml(block: str) -> dict[str, Any]:
    """Minimal frontmatter parser. Does not read the markdown body."""
    meta: dict[str, Any] = {}
    key: str | None = None
    acc: list[str] | None = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if acc is not None and re.match(r"^-\s+", raw.strip()):
            acc.append(_unquote(re.sub(r"^-\s+", "", raw.strip())))
            continue
        if acc is not None and raw.startswith(" ") and key:
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", raw)
        if not m:
            acc = None
            key = None
            continue
        if acc is not None and key is not None:
            meta[key] = acc
        key = m.group(1)
        rest = m.group(2).strip()
        if rest == "" or rest in ("|", ">"):
            acc = []
            continue
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            meta[key] = [_unquote(p) for p in inner.split(",") if p.strip()]
            acc = None
            continue
        meta[key] = _unquote(rest)
        acc = None
    if acc is not None and key is not None:
        meta[key] = acc
    return meta


def extract_model_linewise(fm_raw: str) -> str | None:
    """Mechanically different from mapping parse: first `model:` line in FM."""
    for line in fm_raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^model\s*:\s*(.+)$", s, re.I)
        if m:
            v = _unquote(m.group(1))
            return v or None
    return None


def extract_tools_linewise(fm_raw: str) -> list[str]:
    names: list[str] = []
    in_tools = False
    tool_key_aliases = {
        "tools",
        "allowed-tools",
        "tool-permissions",
        "tools-permissions",
        "allowed_tools",
        "tool_permissions",
        "tools_permissions",
    }
    for line in fm_raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", stripped)
        if m and m.group(1).lower().replace("_", "-") in {
            k.replace("_", "-") for k in tool_key_aliases
        }:
            in_tools = True
            rest = m.group(2).strip()
            if rest.startswith("[") and rest.endswith("]"):
                names.extend(_unquote(p) for p in rest[1:-1].split(",") if p.strip())
                in_tools = False
            elif rest and rest not in ("|", ">"):
                names.extend(
                    _unquote(p) for p in re.split(r"[\s,]+", rest) if p.strip()
                )
                in_tools = False
            continue
        if in_tools and stripped.startswith("-"):
            names.append(_unquote(stripped.lstrip("-").strip()))
            continue
        if m:
            in_tools = False
    out: list[str] = []
    for n in names:
        if n and n not in out:
            out.append(n)
    return out


def tools_from_meta(meta: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in TOOL_KEYS:
        val = meta.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            names.extend(str(x) for x in val)
        else:
            names.extend(re.split(r"[\s,]+", str(val)))
    out: list[str] = []
    for n in names:
        n = n.strip()
        if n and n not in out:
            out.append(n)
    return out


def model_tier(raw: str | None) -> str:
    if not raw:
        return "UNDECLARED"
    s = raw.strip().lower()
    if s in {"inherit", "inherit-from-parent", "default", "none", "null"}:
        return "UNDECLARED"
    if "opus" in s:
        return "opus"
    if "sonnet" in s:
        return "sonnet"
    if "haiku" in s:
        return "haiku"
    return "other"


def naive_body_mentions(body: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", body, re.I) is not None


def classify_dispatching(tools: list[str]) -> dict[str, Any]:
    reasons: list[str] = []
    for t in tools:
        low = t.strip().lower()
        compact = re.sub(r"[^a-z0-9]", "", low)
        if low in DISPATCH_EXACT or compact in DISPATCH_EXACT:
            reasons.append(f"spawn-tool:{t}")
            continue
        if any(low.startswith(p) for p in CROSS_VENDOR_PREFIXES):
            reasons.append(f"cross-vendor:{t}")
    return {
        "dispatching": bool(reasons),
        "reasons": reasons,
        "declared_tools": tools,
    }


def below_opus_floor(dispatching: bool, tier: str) -> bool:
    return bool(dispatching and tier in BELOW_OPUS)


def parse_agent_file(
    path: Path, *, tree_id: str, kind: str, root: Path
) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm_raw, body = split_frontmatter(text)
    meta = parse_simple_yaml(fm_raw)
    model_map = meta.get("model")
    if isinstance(model_map, list):
        model_map = model_map[0] if model_map else None
    model_map_s = None if model_map is None else str(model_map)
    model_line = extract_model_linewise(fm_raw)
    tools_map = tools_from_meta(meta)
    tools_line = extract_tools_linewise(fm_raw)
    disp_map = classify_dispatching(tools_map)
    disp_line = classify_dispatching(tools_line)
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    try:
        rel_tree = path.relative_to(root).as_posix()
    except ValueError:
        rel_tree = path.name
    assigned = model_map_s or model_line
    tier = model_tier(assigned)
    return {
        "path": rel,
        "tree_id": tree_id,
        "kind": kind,
        "name": str(meta.get("name") or path.stem),
        "has_frontmatter": bool(fm_raw.strip()),
        "model_frontmatter": assigned,
        "model_map_parse": model_map_s,
        "model_linewise_parse": model_line,
        "model_tier": tier,
        "declared_tools": tools_map,
        "declared_tools_linewise": tools_line,
        "dispatching": disp_map["dispatching"],
        "dispatching_linewise": disp_line["dispatching"],
        "dispatch_reasons": disp_map["reasons"],
        "below_opus_floor": below_opus_floor(disp_map["dispatching"], tier),
        "body_mentions_sonnet": naive_body_mentions(body, "sonnet"),
        "body_mentions_opus": naive_body_mentions(body, "opus"),
        "body_mentions_task": naive_body_mentions(body, "Task"),
        "naive_body_would_assign_sonnet": naive_body_mentions(body, "sonnet")
        and model_tier(assigned) != "sonnet",
        "rel_in_tree": rel_tree,
    }


def production_roots(repo: Path) -> list[dict[str, Any]]:
    home = Path.home()
    claude_home = os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    return [
        {"id": "repo-agents", "path": repo / "agents", "kind": "production"},
        {
            "id": "repo-dot-claude-agents",
            "path": repo / ".claude" / "agents",
            "kind": "production",
        },
        {
            "id": "live-claude-agents",
            "path": Path(claude_home) / "agents",
            "kind": "production",
        },
        {
            "id": "repo-cursor-agents",
            "path": repo / ".cursor" / "agents",
            "kind": "production",
        },
    ]


def control_root() -> dict[str, Any]:
    return {
        "id": "control-fixtures",
        "path": HERE / "fixtures" / "agents",
        "kind": "control",
    }


def iter_md(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _path_rel(root: Path) -> str:
    try:
        return root.relative_to(REPO).as_posix()
    except ValueError:
        return str(root)


def scan_tree(tree: dict[str, Any]) -> dict[str, Any]:
    root = Path(tree["path"])
    files = iter_md(root)
    agents = [
        parse_agent_file(p, tree_id=tree["id"], kind=tree["kind"], root=root)
        for p in files
    ]
    return {
        "id": tree["id"],
        "kind": tree["kind"],
        "path": str(root),
        "path_rel": _path_rel(root),
        "present": root.is_dir(),
        "md_count": len(files),
        "agents": agents,
    }


def inventory(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    trees = [scan_tree(t) for t in production_roots(repo)]
    control = scan_tree(control_root())
    prod_agents = [a for t in trees for a in t["agents"]]
    ctl_agents = list(control["agents"])
    below = [a for a in prod_agents + ctl_agents if a["below_opus_floor"]]
    dispatchers = [a for a in prod_agents + ctl_agents if a["dispatching"]]
    return {
        "unit_id": UNIT,
        "production_trees": trees,
        "control_tree": control,
        "production_agent_count": len(prod_agents),
        "control_agent_count": len(ctl_agents),
        "production_agents": prod_agents,
        "control_agents": ctl_agents,
        "dispatcher_count": len(dispatchers),
        "below_opus_floor": below,
        "below_opus_floor_count": len(below),
        "production_below_opus_floor_count": sum(
            1 for a in prod_agents if a["below_opus_floor"]
        ),
    }


def control_checks(inv: dict[str, Any]) -> dict[str, Any]:
    by_name = {a["name"]: a for a in inv["control_agents"]}
    mention = by_name.get("mention-only-lookup")
    d_sonnet = by_name.get("loop-operator")
    d_opus = by_name.get("chief-of-staff")
    nd_sonnet = by_name.get("docs-lookup")
    body_task = by_name.get("body-task-mention")
    checks = {
        "mention_fixture_present": mention is not None,
        "mention_assigned_opus_not_sonnet": bool(
            mention
            and mention["model_tier"] == "opus"
            and mention["body_mentions_sonnet"]
            and mention["naive_body_would_assign_sonnet"]
        ),
        "map_and_linewise_model_agree": all(
            a["model_map_parse"] == a["model_linewise_parse"]
            for a in inv["control_agents"]
        ),
        "dispatcher_sonnet_below_floor": bool(
            d_sonnet and d_sonnet["dispatching"] and d_sonnet["below_opus_floor"]
        ),
        "dispatcher_opus_on_floor": bool(
            d_opus and d_opus["dispatching"] and not d_opus["below_opus_floor"]
        ),
        "non_dispatcher_sonnet_not_floor": bool(
            nd_sonnet
            and not nd_sonnet["dispatching"]
            and nd_sonnet["model_tier"] == "sonnet"
            and not nd_sonnet["below_opus_floor"]
        ),
        "body_task_mention_not_dispatching": bool(
            body_task
            and body_task["body_mentions_task"]
            and not body_task["dispatching"]
        ),
        "naive_grep_disagrees_with_frontmatter": bool(
            mention and mention["naive_body_would_assign_sonnet"]
        ),
    }
    checks["pass"] = all(v is True for k, v in checks.items() if k != "pass")
    return checks


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
