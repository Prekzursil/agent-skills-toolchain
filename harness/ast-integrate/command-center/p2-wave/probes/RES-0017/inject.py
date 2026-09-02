"""Turn-0 injection set: always-on skills, MCP schemas, rules, tools.

Lazy skills (frontmatter paths:) and MCP server source are inventory, not
turn-0 occupancy. File sizes of those trees are the rejected inference.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SESSION = HERE / "fixtures" / "session"
CLASS_ORDER = ("rules", "skills", "mcp_schemas", "tools")

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    body = lf(text)
    m = FRONTMATTER_RE.match(body)
    if not m:
        return {}, body
    meta: dict = {}
    for raw_line in m.group(1).split("\n"):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.strip() == "paths:" or line.strip().startswith("paths:"):
            meta["paths"] = []
            continue
        if line.startswith("  - ") or line.startswith("\t- "):
            paths = meta.setdefault("paths", [])
            paths.append(line.split("-", 1)[1].strip().strip("\"'"))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip("\"'")
    return meta, body[m.end() :]


def is_lazy(meta: dict) -> bool:
    paths = meta.get("paths")
    return bool(paths)


def wrap_class(name: str, body: str) -> str:
    return f'<class name="{name}">\n{body}\n</class>\n'


def load_skills(root: Path) -> dict:
    injected_parts: list[str] = []
    catalog_only: list[str] = []
    files: list[dict] = []
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return {
            "injected": "",
            "files": files,
            "always_on": 0,
            "lazy": 0,
            "tree_bytes": 0,
        }
    tree_bytes = 0
    always_on = 0
    lazy = 0
    for path in sorted(skills_root.rglob("*")):
        if not path.is_file():
            continue
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        tree_bytes += len(raw)
        rel = path.relative_to(root).as_posix()
        if path.name != "SKILL.md":
            files.append(
                {
                    "path": rel,
                    "injected": False,
                    "reason": "not-SKILL.md",
                    "bytes": len(raw),
                }
            )
            continue
        text = raw.decode("utf-8")
        meta, _body = parse_frontmatter(text)
        name = str(meta.get("name") or path.parent.name)
        desc = str(meta.get("description") or "")
        if is_lazy(meta):
            lazy += 1
            stub = f"skill: {name} [lazy] {desc}\n"
            catalog_only.append(stub)
            injected_parts.append(stub)
            files.append(
                {
                    "path": rel,
                    "injected": "catalog-stub",
                    "reason": "paths-frontmatter-lazy",
                    "bytes": len(raw),
                    "stub_bytes": len(stub.encode("utf-8")),
                    "name": name,
                }
            )
        else:
            always_on += 1
            injected_parts.append(text if text.endswith("\n") else text + "\n")
            files.append(
                {
                    "path": rel,
                    "injected": True,
                    "reason": "no-paths-always-on",
                    "bytes": len(raw),
                    "name": name,
                }
            )
    return {
        "injected": "".join(injected_parts),
        "files": files,
        "always_on": always_on,
        "lazy": lazy,
        "tree_bytes": tree_bytes,
        "catalog_only_n": len(catalog_only),
    }


def load_mcp(root: Path) -> dict:
    schemas_dir = root / "mcp-schemas"
    server = root / "mcp-server.js"
    mcp_json = root / "mcp.json"
    schema_parts: list[str] = []
    files: list[dict] = []
    tree_bytes = 0
    for path in (mcp_json, server):
        if path.is_file():
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            tree_bytes += len(raw)
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "injected": False,
                    "reason": "not-tool-schema",
                    "bytes": len(raw),
                }
            )
    if schemas_dir.is_dir():
        for path in sorted(schemas_dir.glob("*.json")):
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            tree_bytes += len(raw)
            text = raw.decode("utf-8")
            schema_parts.append(text if text.endswith("\n") else text + "\n")
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "injected": True,
                    "reason": "mcp-tool-schema",
                    "bytes": len(raw),
                }
            )
    return {
        "injected": "".join(schema_parts),
        "files": files,
        "tree_bytes": tree_bytes,
        "schema_files": sum(1 for f in files if f.get("injected") is True),
    }


def load_rules(root: Path) -> dict:
    rules_dir = root / "rules"
    parts: list[str] = []
    files: list[dict] = []
    tree_bytes = 0
    if rules_dir.is_dir():
        for path in sorted(rules_dir.glob("*.md")):
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            tree_bytes += len(raw)
            name = path.name
            disabled = name.startswith("disabled-") or name.endswith(".off.md")
            if disabled:
                files.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "injected": False,
                        "reason": "disabled-rule",
                        "bytes": len(raw),
                    }
                )
                continue
            text = raw.decode("utf-8")
            parts.append(text if text.endswith("\n") else text + "\n")
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "injected": True,
                    "reason": "always-on-rule",
                    "bytes": len(raw),
                }
            )
    return {"injected": "".join(parts), "files": files, "tree_bytes": tree_bytes}


def load_tools(root: Path) -> dict:
    tools_path = root / "tools" / "builtin.json"
    files: list[dict] = []
    tree_bytes = 0
    injected = ""
    if tools_path.is_file():
        raw = tools_path.read_bytes().replace(b"\r\n", b"\n")
        tree_bytes = len(raw)
        injected = raw.decode("utf-8")
        if not injected.endswith("\n"):
            injected += "\n"
        files.append(
            {
                "path": tools_path.relative_to(root).as_posix(),
                "injected": True,
                "reason": "client-tool-schema",
                "bytes": len(raw),
            }
        )
    return {"injected": injected, "files": files, "tree_bytes": tree_bytes}


def class_payloads(root: Path | None = None) -> dict[str, dict]:
    session = root or SESSION
    return {
        "rules": load_rules(session),
        "skills": load_skills(session),
        "mcp_schemas": load_mcp(session),
        "tools": load_tools(session),
    }


def render(payloads: dict[str, dict], omit: str | None = None) -> str:
    parts: list[str] = []
    for name in CLASS_ORDER:
        if name == omit:
            continue
        parts.append(wrap_class(name, payloads[name]["injected"]))
    return "".join(parts)


def wrapped_block(name: str, payloads: dict[str, dict]) -> str:
    return wrap_class(name, payloads[name]["injected"])


def utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))
