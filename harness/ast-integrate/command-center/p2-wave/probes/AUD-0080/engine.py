#!/usr/bin/env python3
"""AUD-0080 permission-surface engine: allow-list merge + hook matcher tests.

Probe 1 is the config read (per-scope allow/deny and the effective merged set).
Probe 2 is the matcher receipt: construct an allow-listed command that matches a
hook's intent and test whether the matcher actually fires.

The recorded false-positive class is a guard that greps the payload body instead
of the tool verb. Two planted mentions: echo quoting rm -rf, and grep -F of the
same string. Those must not be treated as use.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

RULE_RE = re.compile(r"^([A-Za-z0-9_.:-]+)(?:\((.*)\))?$")
EXACT_MATCHER_RE = re.compile(r"^[A-Za-z0-9_ \-,|]*$")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_*=]*=\S+\s+")
NAIVE_RM_RE = re.compile(r"\brm\s+-r?f\b|\brm\s+-fr\b", re.I)
TOKEN_RE = re.compile(r"""\s+|(?P<q>['"])(?P<body>(?:\\.|[^\\])*?)(?P=q)|(?P<tok>[^\s'"]+)""")

REDACT_KEYS = frozenset(
    {
        "authinfo",
        "email",
        "authid",
        "userid",
        "apikey",
        "api_key",
        "token",
        "secret",
        "password",
        "organizationid",
        "teamid",
    }
)


def repo() -> Path:
    return REPO


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        stripped = re.sub(r"^\s*//.*$", "", stripped, flags=re.M)
        return json.loads(stripped)


def parse_rule(raw: str) -> dict[str, str | None]:
    text = str(raw).strip()
    match = RULE_RE.match(text)
    if not match:
        return {"raw": text, "tool": None, "pattern": None}
    return {"raw": text, "tool": match.group(1), "pattern": match.group(2)}


def strip_assignments(command: str) -> str:
    text = command.strip()
    while True:
        match = ASSIGN_RE.match(text)
        if not match:
            return text
        text = text[match.end() :]


def tokenize(command: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(strip_assignments(command)):
        if match.group("body") is not None:
            tokens.append(match.group("body"))
        elif match.group("tok"):
            tokens.append(match.group("tok"))
    return tokens


def verb_of(command: str) -> str:
    tokens = tokenize(command)
    return tokens[0] if tokens else ""


def _extract_dollar_subs(command: str) -> list[str]:
    found: list[str] = []
    i = 0
    while i < len(command):
        if command.startswith("$(", i):
            depth = 1
            j = i + 2
            while j < len(command) and depth:
                if command.startswith("$(", j):
                    depth += 1
                    j += 2
                    continue
                if command[j] == ")":
                    depth -= 1
                    j += 1
                    continue
                j += 1
            found.append(command[i + 2 : j - 1])
            i = j
            continue
        if command[i] == "`":
            j = command.find("`", i + 1)
            if j < 0:
                break
            found.append(command[i + 1 : j])
            i = j + 1
            continue
        i += 1
    return found


def _split_unquoted(command: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            if ch == "\\" and i + 1 < len(command):
                buf.append(ch)
                buf.append(command[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            buf.append(ch)
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            parts.append("".join(buf).strip())
            buf = []
            i += 2
            continue
        if ch in ";":
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf).strip())
    return [p for p in parts if p]


def iter_subcommands(command: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        text = item.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)

    for part in _split_unquoted(command):
        add(part)
        for nested in _extract_dollar_subs(part):
            for inner in iter_subcommands(nested):
                add(inner)
    return out


def glob_match(value: str, pattern: str) -> bool:
    if pattern in {"*", "**"}:
        return True
    if fnmatch.fnmatch(value, pattern):
        return True
    if "*" not in pattern and "?" not in pattern and "[" not in pattern:
        return verb_of(value) == pattern or value == pattern
    return False


def rule_matches(rule: str, tool: str, command: str | None) -> bool:
    parsed = parse_rule(rule)
    want_tool = parsed.get("tool")
    if not want_tool:
        return False
    if want_tool != tool and want_tool.lower() != tool.lower():
        aliases = {
            ("Bash", "Shell"),
            ("Shell", "Bash"),
            ("PowerShell", "Shell"),
        }
        if (want_tool, tool) not in aliases and (tool, want_tool) not in aliases:
            return False
    pattern = parsed.get("pattern")
    if pattern is None or pattern in {"*", "**"}:
        return True
    if command is None:
        return False
    for sub in iter_subcommands(command):
        body = strip_assignments(sub)
        if glob_match(body, pattern):
            return True
    return False


def naive_payload_guard(command: str) -> bool:
    """Known-broken detector: greps the whole command string, including quotes."""
    return bool(NAIVE_RM_RE.search(command))


def verb_aware_rm_gate(command: str) -> bool:
    """Production detector: flag only when a subcommand *verb* is rm with -rf/-fr/-r -f."""
    for sub in iter_subcommands(command):
        if verb_of(sub) != "rm":
            continue
        tokens = tokenize(sub)
        flags = {t for t in tokens[1:] if t.startswith("-")}
        joined = "".join(sorted("".join(f[1:] for f in flags)))
        if "r" in joined and "f" in joined:
            return True
        if any(f in {"-rf", "-fr", "-Rf", "-rF", "-FR", "-Rf"} for f in flags):
            return True
    return False


def matcher_hits_tool(matcher: str | None, tool_name: str) -> bool:
    if matcher is None or matcher.strip() in {"", "*"}:
        return True
    text = matcher.strip()
    if EXACT_MATCHER_RE.match(text):
        parts = [p.strip() for p in re.split(r"[|,]", text) if p.strip()]
        return tool_name in parts
    try:
        return re.search(text, tool_name) is not None
    except re.error:
        return tool_name == text


def cursor_command_matcher_hits(matcher: str | None, command: str) -> bool:
    if matcher is None or matcher.strip() in {"", "*"}:
        return True
    try:
        return re.search(matcher, command) is not None
    except re.error:
        return matcher in command


def extract_permissions(doc: Any) -> tuple[list[str], list[str]]:
    if not isinstance(doc, dict):
        return [], []
    block = doc.get("permissions")
    if not isinstance(block, dict):
        return [], []
    allow = [str(x) for x in (block.get("allow") or []) if isinstance(x, str)]
    deny = [str(x) for x in (block.get("deny") or []) if isinstance(x, str)]
    return allow, deny


def flatten_hooks(doc: Any, source: str, scope: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(doc, dict):
        return rows
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return rows
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_matcher = group.get("matcher")
            inner = group.get("hooks")
            if isinstance(inner, list) and inner:
                for handler in inner:
                    if not isinstance(handler, dict):
                        continue
                    rows.append(
                        {
                            "scope": scope,
                            "source": source,
                            "event": str(event),
                            "matcher": group_matcher
                            if group_matcher is not None
                            else handler.get("matcher"),
                            "if_rule": handler.get("if"),
                            "handler_id": handler.get("id") or handler.get("command")
                            or handler.get("script"),
                            "handler_type": handler.get("type") or "command",
                            "family": "claude-or-plugin",
                        }
                    )
            else:
                rows.append(
                    {
                        "scope": scope,
                        "source": source,
                        "event": str(event),
                        "matcher": group.get("matcher"),
                        "if_rule": group.get("if"),
                        "handler_id": group.get("command") or group.get("id"),
                        "handler_type": group.get("type") or "command",
                        "family": "cursor",
                    }
                )
    return rows


def command_for_allow_rule(rule: str) -> dict[str, str | None]:
    parsed = parse_rule(rule)
    tool = parsed.get("tool") or "Unknown"
    pattern = parsed.get("pattern")
    if pattern is None or pattern in {"*", "**"}:
        command = "true"
    elif "*" in pattern:
        command = pattern.replace("*", "status").replace("  ", " ").strip()
        if command.endswith("status") and pattern.startswith("rm"):
            command = "rm -rf /tmp/aud0080-intent"
        elif pattern.startswith("ls"):
            command = "ls -la"
        elif pattern.startswith("echo"):
            command = 'echo hello'
        elif pattern.startswith("grep"):
            command = "grep -F needle notes.txt"
        elif pattern.startswith("find"):
            command = "find /tmp -delete"
        elif pattern.startswith("git"):
            command = "git status"
        elif pattern.startswith("python"):
            command = "python3 -V"
        else:
            command = command or "true"
    else:
        command = pattern
    return {"tool": tool, "command": command, "rule": rule}


def live_scope_specs() -> list[dict[str, str]]:
    home = Path.home()
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (home / ".claude"))
    return [
        {
            "scope": "managed-claude",
            "path": "/etc/claude-code/managed-settings.json",
        },
        {
            "scope": "user-claude",
            "path": str(claude_dir / "settings.json"),
        },
        {
            "scope": "project-claude",
            "path": str(REPO / ".claude" / "settings.json"),
        },
        {
            "scope": "local-claude",
            "path": str(REPO / ".claude" / "settings.local.json"),
        },
        {
            "scope": "user-cursor",
            "path": str(home / ".cursor" / "cli-config.json"),
        },
        {
            "scope": "project-cursor",
            "path": str(REPO / ".cursor" / "cli.json"),
        },
    ]


def live_hook_specs() -> list[dict[str, str]]:
    home = Path.home()
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (home / ".claude"))
    return [
        {
            "scope": "user-claude",
            "path": str(claude_dir / "settings.json"),
        },
        {
            "scope": "project-claude",
            "path": str(REPO / ".claude" / "settings.json"),
        },
        {
            "scope": "local-claude",
            "path": str(REPO / ".claude" / "settings.local.json"),
        },
        {
            "scope": "user-cursor-hooks",
            "path": str(home / ".cursor" / "hooks.json"),
        },
        {
            "scope": "project-cursor-hooks",
            "path": str(REPO / ".cursor" / "hooks.json"),
        },
        {
            "scope": "managed-claude",
            "path": "/etc/claude-code/managed-settings.json",
        },
    ]


def read_scope_file(path: Path) -> dict[str, Any]:
    rel = str(path)
    row: dict[str, Any] = {
        "path": rel,
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "parse_ok": False,
        "allow": [],
        "deny": [],
        "error": None,
    }
    if not path.is_file():
        return row
    try:
        doc = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        row["error"] = f"{type(exc).__name__}:{exc}"
        return row
    row["parse_ok"] = True
    allow, deny = extract_permissions(doc)
    row["allow"] = allow
    row["deny"] = deny
    if isinstance(doc, dict) and "approvalMode" in doc:
        row["approval_mode"] = doc.get("approvalMode")
    return row


def merge_allow_deny(scope_rows: list[dict[str, Any]]) -> dict[str, Any]:
    allow: list[str] = []
    deny: list[str] = []
    for row in scope_rows:
        for item in row.get("allow") or []:
            if item not in allow:
                allow.append(item)
        for item in row.get("deny") or []:
            if item not in deny:
                deny.append(item)
    effective: list[str] = []
    for rule in allow:
        sample = command_for_allow_rule(rule)
        blocked = False
        for d in deny:
            if rule_matches(d, str(sample["tool"]), sample["command"]):
                blocked = True
                break
            parsed_a = parse_rule(rule)
            parsed_d = parse_rule(d)
            if (
                parsed_a.get("tool") == parsed_d.get("tool")
                and parsed_a.get("pattern")
                and parsed_d.get("pattern")
                and glob_match(str(parsed_a["pattern"]), str(parsed_d["pattern"]))
            ):
                blocked = True
                break
        if not blocked:
            effective.append(rule)
    return {
        "allow_union": allow,
        "deny_union": deny,
        "effective_allow": effective,
        "deny_wins": True,
    }


def fixture_merge_scopes() -> list[dict[str, Any]]:
    mapping = [
        ("fixture-user", HERE / "fixtures" / "merge" / "user.json"),
        ("fixture-project", HERE / "fixtures" / "merge" / "project.json"),
        ("fixture-local", HERE / "fixtures" / "merge" / "local.json"),
    ]
    rows = []
    for scope, path in mapping:
        rec = read_scope_file(path)
        rec["scope"] = scope
        rec["path"] = str(path.relative_to(REPO)).replace("\\", "/")
        rows.append(rec)
    return rows


def live_permission_scopes() -> list[dict[str, Any]]:
    rows = []
    for spec in live_scope_specs():
        rec = read_scope_file(Path(spec["path"]))
        rec["scope"] = spec["scope"]
        rows.append(rec)
    return rows


def catalog_tool_policy() -> dict[str, Any]:
    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    out: dict[str, Any] = {
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "exists": catalog.is_file(),
        "note": (
            "Program tool_policy is not a Claude/Cursor settings scope; "
            "recorded as a related surface and not merged into live effective allow."
        ),
        "allow": [],
        "deny": [],
    }
    if not catalog.is_file():
        return out
    doc = load_json(catalog)
    policy = doc.get("tool_policy") if isinstance(doc, dict) else None
    if isinstance(policy, dict):
        out["allow"] = [str(x) for x in (policy.get("allow") or []) if isinstance(x, str)]
        out["deny"] = [str(x) for x in (policy.get("deny") or []) if isinstance(x, str)]
        out["default"] = policy.get("default")
    return out


def load_hooks_from(path: Path, scope: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        doc = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    rel = str(path)
    try:
        rel = str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        rel = str(path)
    return flatten_hooks(doc, rel, scope)


def live_and_repo_hooks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in live_hook_specs():
        rows.extend(load_hooks_from(Path(spec["path"]), spec["scope"]))
    plugin = REPO / "command-center/p2-wave/probes/CNF-0146/package/hooks/hooks.json"
    rows.extend(load_hooks_from(plugin, "repo-plugin-fixture-cnf0146"))
    return rows


def fixture_hooks() -> list[dict[str, Any]]:
    rows = load_hooks_from(HERE / "fixtures" / "hooks" / "settings.json", "fixture-claude")
    rows.extend(
        load_hooks_from(HERE / "fixtures" / "hooks" / "cursor-hooks.json", "fixture-cursor")
    )
    return rows


def hook_fires(
    hook: dict[str, Any], tool: str, command: str
) -> dict[str, Any]:
    event = str(hook.get("event") or "")
    matcher = hook.get("matcher")
    if_rule = hook.get("if_rule")
    family = hook.get("family")
    tool_hit = True
    command_hit = True
    if event.lower() in {
        "beforeshellexecution",
        "aftershellexecution",
    } or family == "cursor" and "shell" in event.lower():
        command_hit = cursor_command_matcher_hits(
            None if matcher is None else str(matcher), command
        )
        tool_hit = True
    else:
        tool_hit = matcher_hits_tool(
            None if matcher is None else str(matcher), tool
        )
        command_hit = True
    if_hit = True
    if if_rule:
        if_hit = rule_matches(str(if_rule), tool, command)
    fires = bool(tool_hit and command_hit and if_hit)
    return {
        "fires": fires,
        "tool_hit": tool_hit,
        "command_hit": command_hit,
        "if_hit": if_hit,
        "matcher": matcher,
        "if_rule": if_rule,
        "event": event,
        "handler_id": hook.get("handler_id"),
        "scope": hook.get("scope"),
        "source": hook.get("source"),
    }


def mention_cases() -> list[dict[str, str]]:
    return [
        {
            "id": "fp-echo-quotes-rm",
            "tool": "Bash",
            "command": 'echo "rm -rf /"',
            "why": "PAYLOAD quotes a dangerous string; VERB is echo",
        },
        {
            "id": "fp-grep-needle-rm",
            "tool": "Bash",
            "command": "grep -F 'rm -rf' notes.txt",
            "why": "PAYLOAD is a search needle; VERB is grep",
        },
    ]


def use_cases() -> list[dict[str, str]]:
    return [
        {
            "id": "use-rm-rf",
            "tool": "Bash",
            "command": "rm -rf /tmp/aud0080-intent",
            "why": "VERB is rm with -rf",
        },
        {
            "id": "use-nested-rm",
            "tool": "Bash",
            "command": "echo $(rm -rf /tmp/aud0080-nested)",
            "why": "rm is a real subcommand inside $(), not a mention",
        },
    ]


def evaluate_use_vs_mention() -> dict[str, Any]:
    mentions = mention_cases()
    uses = use_cases()
    naive_fp = [c["id"] for c in mentions if naive_payload_guard(c["command"])]
    verb_fp = [c["id"] for c in mentions if verb_aware_rm_gate(c["command"])]
    naive_use = [c["id"] for c in uses if naive_payload_guard(c["command"])]
    verb_use = [c["id"] for c in uses if verb_aware_rm_gate(c["command"])]
    pass_control = (
        set(naive_fp) == {c["id"] for c in mentions}
        and not verb_fp
        and set(verb_use) == {c["id"] for c in uses}
        and set(naive_use) == {c["id"] for c in uses}
    )
    return {
        "mentions": mentions,
        "uses": uses,
        "naive_flags_mentions": naive_fp,
        "verb_aware_flags_mentions": verb_fp,
        "naive_flags_uses": naive_use,
        "verb_aware_flags_uses": verb_use,
        "recorded_false_positive_count": 2,
        "pass": pass_control,
    }


def construct_and_test_hooks(
    hooks: list[dict[str, Any]], allow_rules: list[str]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    samples = [command_for_allow_rule(r) for r in allow_rules]
    for hook in hooks:
        intent_cmd = "rm -rf /tmp/aud0080-intent"
        intent_tool = "Bash"
        if_rule = hook.get("if_rule")
        if if_rule:
            sample = command_for_allow_rule(str(if_rule))
            intent_tool = str(sample["tool"])
            intent_cmd = str(sample["command"])
        elif str(hook.get("event") or "").lower() in {
            "beforeshellexecution",
            "aftershellexecution",
        }:
            intent_tool = "Shell"
            intent_cmd = "rm -rf /tmp/aud0080-intent"
        satisfying = [
            s
            for s in samples
            if rule_matches(str(s["rule"]), intent_tool, intent_cmd)
            or (
                s["tool"] == intent_tool
                and s["command"]
                and verb_of(str(s["command"])) == verb_of(intent_cmd)
            )
        ]
        if not satisfying:
            for s in samples:
                if rule_matches(str(s["rule"]), str(s["tool"]), str(s["command"])):
                    pass
            constructed = {
                "tool": intent_tool,
                "command": intent_cmd,
                "allow_rule": None,
                "allow_satisfied": False,
            }
        else:
            constructed = {
                "tool": intent_tool,
                "command": intent_cmd,
                "allow_rule": satisfying[0]["rule"],
                "allow_satisfied": True,
            }
        fired = hook_fires(hook, constructed["tool"], constructed["command"])
        classification = "NO-ALLOW-HIT"
        if constructed["allow_satisfied"] and fired["fires"]:
            classification = "CAUGHT"
        elif constructed["allow_satisfied"] and not fired["fires"]:
            classification = "BYPASS"
        elif fired["fires"]:
            classification = "CAUGHT-UNALLOWLISTED"
        results.append(
            {
                "hook": {
                    "scope": hook.get("scope"),
                    "event": hook.get("event"),
                    "matcher": hook.get("matcher"),
                    "if_rule": hook.get("if_rule"),
                    "handler_id": hook.get("handler_id"),
                    "source": hook.get("source"),
                },
                "constructed": constructed,
                "matcher_result": fired,
                "classification": classification,
            }
        )
    return results


def mention_vs_hooks(hooks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for case in mention_cases():
        for hook in hooks:
            fired = hook_fires(hook, case["tool"], case["command"])
            out.append(
                {
                    "case_id": case["id"],
                    "command": case["command"],
                    "hook_id": hook.get("handler_id"),
                    "matcher": hook.get("matcher"),
                    "if_rule": hook.get("if_rule"),
                    "event": hook.get("event"),
                    "fires": fired["fires"],
                    "class": (
                        "FALSE-POSITIVE"
                        if fired["fires"]
                        else "SILENT-ON-MENTION"
                    ),
                }
            )
    return out


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        clean = {}
        for key, value in obj.items():
            if str(key).lower() in REDACT_KEYS:
                continue
            clean[key] = redact_obj(value)
        return clean
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    return obj
