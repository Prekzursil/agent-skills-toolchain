"""Prompt-layer vs tool-layer permission gates for RES-0056.

A skill/rule/plugin payload is markdown (or JSON metadata) that can *declare*
permissions and *instruct* a model. The prompt layer injects that text. The
tool layer is the host allowlist / PreToolUse hook that sees the canonical
tool name of an actual call.

This module is the local measurement harness. It does not talk to a live
model: fixtures emit an explicit REQUEST-TOOL so the requested capability is
observable without executing a hostile payload.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REPO = HERE.parents[3]

REQUEST_RE = re.compile(r"REQUEST-TOOL:\s*([A-Za-z][A-Za-z0-9_-]*)")
COMMENT_TOOL_RE = re.compile(r"<!--\s*tool:([A-Za-z][A-Za-z0-9_-]*)\s*-->")
FM_ALLOWED_RE = re.compile(
    r"^(?:allowed-tools|allowed_tools|tool_permissions)\s*:\s*(.+)$",
    re.MULTILINE,
)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    rest = text[3:]
    end = rest.find("\n---")
    if end < 0:
        return {}, text
    raw = rest[:end].strip("\n")
    body = rest[end + 4 :].lstrip("\n")
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip()] = val.strip().strip("'\"")
    return meta, body


def declared_tools(meta: dict[str, Any], extra: list[str] | None = None) -> list[str]:
    names: list[str] = []
    for key in ("allowed-tools", "allowed_tools", "tool_permissions"):
        val = meta.get(key)
        if not val:
            continue
        names.extend(re.split(r"[\s,]+", str(val).strip()))
    if extra:
        names.extend(extra)
    out: list[str] = []
    for n in names:
        n = n.strip()
        if n and n not in out:
            out.append(n)
    return out


def requested_tools(body: str) -> list[str]:
    found: list[str] = []
    for rx in (REQUEST_RE, COMMENT_TOOL_RE):
        for m in rx.finditer(body):
            name = m.group(1)
            if name not in found:
                found.append(name)
    return found


def visible_body(body: str) -> str:
    return re.sub(r"<!--.*?-->", "", body, flags=re.S)


def lexical_prompt_filter(body: str, declared: list[str]) -> dict[str, Any]:
    """Naive prompt-layer 'control': reject bodies that mention undeclared tools.

    This is the security-theatre mitigation the reviewer is required to bypass.
    """
    visible = visible_body(body)
    undeclared_hits = []
    for token in ("Write", "Bash", "WebFetch", "Shell"):
        if token not in declared and re.search(rf"\b{token}\b", visible):
            undeclared_hits.append(token)
    return {
        "id": "M-PROMPT-LEXICAL",
        "stopped": bool(undeclared_hits),
        "hits": undeclared_hits,
        "classification": "DECLARED",
        "enforced": False,
        "note": "Lexical scan of visible markdown. HTML comments and synonyms evade it.",
    }


def prompt_layer(payload_text: str, *, plugin_allow: list[str] | None = None) -> dict[str, Any]:
    meta, body = parse_frontmatter(payload_text)
    declared = declared_tools(meta, plugin_allow)
    requests = requested_tools(payload_text)
    lexical = lexical_prompt_filter(body, declared)
    # Prompt layer never binds a capability. Even if the lexical filter fires,
    # the instruction is still injected — the filter is advisory theatre.
    return {
        "layer": "prompt",
        "kind": meta.get("kind") or "skill",
        "name": meta.get("name"),
        "declared_tools": declared,
        "requested_tools": requests,
        "injected": True,
        "stopped": False,
        "forwarded_to_agent": True,
        "lexical_filter": lexical,
        "enforced": False,
        "classification": "DECLARED",
        "security_theatre": True,
        "reason": (
            "Payload is prompt text. Declared permissions are metadata. "
            "Nothing at this layer intercepts a later tool call."
        ),
    }


def tool_layer(
    request_tool: str,
    allowlist: list[str],
    dest: Path,
    contents: str = "RES-0056-marker",
) -> dict[str, Any]:
    allowed = request_tool in allowlist
    if allowed:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        existed = dest.is_file()
        return {
            "layer": "tool",
            "request_tool": request_tool,
            "allowlist": list(allowlist),
            "allowed": True,
            "stopped": False,
            "file_exists": existed,
            "path": str(dest),
            "enforced": True,
            "classification": "ENFORCED",
            "security_theatre": False,
            "reason": "Canonical tool name is in the host allowlist; call proceeds.",
        }
    existed = dest.is_file()
    return {
        "layer": "tool",
        "request_tool": request_tool,
        "allowlist": list(allowlist),
        "allowed": False,
        "stopped": True,
        "file_exists": existed,
        "path": str(dest),
        "enforced": True,
        "classification": "ENFORCED",
        "security_theatre": False,
        "reason": (
            "Host allowlist / PreToolUse gate denied the canonical tool name "
            f"{request_tool!r}; the file was not written."
        ),
    }


def load_fixture(rel: str) -> str:
    path = FIXTURES / rel
    return path.read_text(encoding="utf-8")


def load_plugin_allow() -> list[str]:
    plugin = json.loads((FIXTURES / "plugin.json").read_text(encoding="utf-8"))
    return list(plugin.get("tool_permissions") or [])


def run_demonstration(scratch: Path) -> dict[str, Any]:
    plugin_allow = load_plugin_allow()
    skill_text = load_fixture("skill-read-only/SKILL.md")
    rule_text = load_fixture("rules/rule-read-only.md")
    synonym_text = load_fixture("lexical-synonym/SKILL.md")

    skill_prompt = prompt_layer(skill_text, plugin_allow=plugin_allow)
    rule_prompt = prompt_layer(rule_text, plugin_allow=plugin_allow)
    synonym_prompt = prompt_layer(synonym_text, plugin_allow=plugin_allow)

    violate = scratch / "VIOLATION.txt"
    granted = scratch / "GRANTED.txt"
    synonym_path = scratch / "SYNONYM.txt"

    # Same Write request the skill instructed, against the declared Read allowlist.
    blocked = tool_layer("Write", skill_prompt["declared_tools"], violate)
    # Both-states control: the gate is not "deny everything".
    granted_write = tool_layer("Write", ["Read", "Write"], granted)
    # Reviewer bypass of lexical filter: body avoids the token Write; tool still Write.
    synonym_blocked = tool_layer(
        (synonym_prompt["requested_tools"] or ["Write"])[0],
        synonym_prompt["declared_tools"],
        synonym_path,
    )

    prompt_not_stopped = (
        skill_prompt["stopped"] is False
        and rule_prompt["stopped"] is False
        and synonym_prompt["stopped"] is False
        and skill_prompt["injected"]
        and "Write" in skill_prompt["requested_tools"]
        and "Write" in rule_prompt["requested_tools"]
        and "Write" in synonym_prompt["requested_tools"]
    )
    lexical_fooled = (
        synonym_prompt["lexical_filter"]["stopped"] is False
        and "Write" in synonym_prompt["requested_tools"]
        and skill_prompt["lexical_filter"]["stopped"] is True
    )
    tool_blocked_same_violation = (
        blocked["stopped"] is True
        and blocked["file_exists"] is False
        and not violate.exists()
        and synonym_blocked["stopped"] is True
        and not synonym_path.exists()
    )
    both_states = granted_write["allowed"] is True and granted.exists()

    return {
        "skill_prompt": skill_prompt,
        "rule_prompt": rule_prompt,
        "synonym_prompt": synonym_prompt,
        "tool_blocked": blocked,
        "tool_granted_control": granted_write,
        "synonym_tool_blocked": synonym_blocked,
        "prompt_layer_violation_not_stopped": prompt_not_stopped,
        "lexical_filter_bypassed": lexical_fooled,
        "same_violation_blocked_at_tool_layer": tool_blocked_same_violation,
        "tool_layer_both_states_control": both_states,
        "plugin_declared": plugin_allow,
        "honest_answer": (
            "only the tool layer can enforce anything; a declared permission "
            "on a prompt, skill, or rule payload is security theatre"
        ),
    }
