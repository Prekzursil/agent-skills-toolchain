#!/usr/bin/env python3
"""AUD-0081 shared classifier: inert documentation vs active auto-load mechanism.

Catalog evidence_requirement (verbatim): "Probe 2: a content read of each hit
classifying it as inert documentation versus an active hook or MCP
registration - the presence of a file named CLAUDE.md is not by itself a
risk finding." This module is that classifier, used by BOTH probe 2 (real
hits) and the tests_required control (a synthetic fixture toggled between
two states) so the control exercises the exact same code path as the real
probe, not a hand-written stand-in.

Three-way vocabulary, not just active/inert:
  * "active"       - the content contains a hook-lifecycle event marker, a
                      non-empty JSON "hooks" key, a non-empty mcpServers
                      registration, or a YAML `hooks:` block with a
                      `command:` entry. THIS IS A CONTENT-SYNTAX FINDING,
                      NOT PROOF THAT THE FILE IS AUTO-LOADED TODAY BY A
                      REAL AGENT PROCESS -- a file can carry a real
                      registration syntax and still require an explicit
                      opt-in flag to be loaded (see AUD-0081 probe 2's
                      documented finding for
                      examples/hooks/minimal/ralph.hooks.yml, whose own
                      header comment says "Validate with: ralph hooks
                      validate -c ..."). That auto-load-vs-explicit-opt-in
                      distinction is recorded in the reason string, never
                      silently collapsed into "active" without comment.
  * "mention-only"  - the auto-load filename/dirname is present but its
                      content does not contain a confirmed registration
                      (e.g. skills/agents markdown with no hooks key, or a
                      directory literally named "hooks" that holds
                      executable-shaped scripts with no discoverable
                      settings/YAML registration wiring them in) -- the
                      exact use-vs-mention failure_classification this
                      catalog entry names.
  * "inert"         - prose-only documentation, an empty/absent
                      registration block, or a directory containing only
                      non-executable source-code files (a coding
                      convention, e.g. React/Rust "hooks" modules).

HOOK_LIFECYCLE_MARKERS matches the event names Claude Code's own hooks
settings schema uses (PreToolUse, PostToolUse, SessionStart, SessionEnd,
UserPromptSubmit, Notification, Stop, SubagentStop, PreCompact) so a
markdown file that merely *talks about* hooks in prose (no literal event
name) is not misclassified as active.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HOOK_LIFECYCLE_MARKERS = [
    "PreToolUse",
    "PostToolUse",
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "SubagentStop",
    "PreCompact",
    "Notification",
]

_HOOKS_JSON_BLOCK_RE = re.compile(r'"hooks"\s*:\s*\{')
_YAML_HOOKS_KEY_RE = re.compile(r"^\s*hooks:\s*$", re.MULTILINE)
_YAML_COMMAND_LINE_RE = re.compile(r"^\s*command:\s*(.+)$", re.MULTILINE)

SCRIPT_LIKE_SUFFIXES = {".sh", ".py", ".js", ".mjs", ".ts", ".ps1"}
SOURCE_ONLY_SUFFIXES = {".tsx", ".jsx", ".rs", ".go", ".java", ".c", ".cpp", ".h"}
YAML_SUFFIXES = {".yml", ".yaml"}

# Header-comment substrings that, when present in the SAME file that also
# matches an active YAML hooks pattern, disclose that the file requires an
# explicit CLI opt-in (e.g. `-c path/to/file.yml`) rather than being
# auto-discovered -- surfaced in the reason string, never used to
# downgrade the classification silently.
_EXPLICIT_OPT_IN_MARKERS = ["-c ", "--config"]


def classify_text_content(text: str) -> tuple[str, str]:
    """Classify markdown/prose-shaped content (AGENTS.md, CLAUDE.md, or any
    settings-shaped text). Looks for a literal hook-lifecycle event name or
    an embedded '"hooks": {' JSON registration block; anything else is
    prose and classified inert."""
    for marker in HOOK_LIFECYCLE_MARKERS:
        if marker in text:
            return (
                "active",
                f"content contains hook-lifecycle event marker '{marker}'",
            )
    if _HOOKS_JSON_BLOCK_RE.search(text):
        return "active", "content contains an embedded '\"hooks\": {' JSON registration block"
    return (
        "inert",
        "prose-only content; no hook-lifecycle event marker or hooks "
        "registration block found",
    )


def classify_mcp_json(text: str) -> tuple[str, str]:
    """Classify a .mcp.json (or settings.json mcpServers) file's raw text."""
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return "inert", "unparseable JSON; no confirmed live registration"
    if not isinstance(doc, dict):
        return "inert", "top-level JSON value is not an object"
    servers = doc.get("mcpServers")
    if not isinstance(servers, dict):
        servers = doc.get("servers") if isinstance(doc.get("servers"), dict) else None
    if isinstance(servers, dict) and servers:
        return (
            "active",
            f"non-empty mcpServers registration block ({len(servers)} server(s))",
        )
    hooks = doc.get("hooks")
    if isinstance(hooks, dict) and hooks:
        return "active", f"non-empty 'hooks' key ({len(hooks)} lifecycle event(s))"
    return "inert", "JSON parses but no non-empty mcpServers/hooks key found"


def classify_settings_json(text: str) -> tuple[str, str]:
    """Classify a settings.json / settings.local.json found inside a
    .claude or .codex directory hit."""
    return classify_mcp_json(text)


def classify_yaml_hooks_config(text: str) -> tuple[str, str] | None:
    """Classify a YAML config for a top-level `hooks:` block containing at
    least one `command:` entry (the ralph-orchestrator hooks.yml shape:
    `hooks.events.<phase>[].command: [...]`). Returns None (not a YAML
    hooks config at all) rather than "inert" when no `hooks:` key is
    present, so callers can fall through to other checks."""
    if not _YAML_HOOKS_KEY_RE.search(text):
        return None
    commands = _YAML_COMMAND_LINE_RE.findall(text)
    if not commands:
        return "inert", "YAML has a 'hooks:' key but no 'command:' entries under it"
    opt_in_disclosed = any(m in text for m in _EXPLICIT_OPT_IN_MARKERS)
    sample = commands[0].strip()[:120]
    if opt_in_disclosed:
        return (
            "active",
            f"YAML 'hooks:' block registers {len(commands)} command(s) "
            f"(e.g. {sample!r}); NOTE the file's own header discloses an "
            "explicit CLI opt-in flag (-c/--config), so this is a real "
            "hook-registration SYNTAX finding, not proof of auto-load by "
            "default",
        )
    return (
        "active",
        f"YAML 'hooks:' block registers {len(commands)} command(s) "
        f"(e.g. {sample!r})",
    )


def classify_hooks_dir(root: Path) -> tuple[str, str]:
    """Classify a directory literally named 'hooks'. The catalog's own
    evidence_requirement warns this is exactly the use-vs-mention trap: a
    coding convention (React hooks, Rust hooks module) uses the same
    directory name as an agent's hook-registration directory."""
    try:
        files = [p for p in root.rglob("*") if p.is_file()]
    except OSError as exc:
        return "inert", f"could not walk directory: {type(exc).__name__}"
    if not files:
        return "inert", "hooks/ directory is empty"

    for f in files:
        if f.name in {"settings.json", "settings.local.json", "hooks.json"}:
            try:
                verdict, reason = classify_settings_json(
                    f.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                continue
            if verdict == "active":
                return "active", f"{f.name} inside hooks/ carries a live registration ({reason})"

    for f in files:
        if f.suffix.lower() in YAML_SUFFIXES:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            res = classify_yaml_hooks_config(text)
            if res is not None and res[0] == "active":
                return "active", f"{f.name} inside hooks/ {res[1]}"

    exec_scripts = [
        f
        for f in files
        if f.suffix.lower() in SCRIPT_LIKE_SUFFIXES and _is_exec(f)
    ]
    non_exec_script_shaped = [
        f
        for f in files
        if f.suffix.lower() in SCRIPT_LIKE_SUFFIXES and not _is_exec(f)
    ]
    source_only = [f for f in files if f.suffix.lower() in SOURCE_ONLY_SUFFIXES]

    if exec_scripts:
        return (
            "mention-only",
            f"hooks/ directory contains {len(exec_scripts)} REAL executable "
            "(X_OK bit set) script file(s) but no adjacent "
            "settings.json/hooks.json/YAML registration was found "
            "confirming they are wired as agent lifecycle hooks (present, "
            "not confirmed active)",
        )
    if source_only and not non_exec_script_shaped:
        return (
            "inert",
            f"hooks/ directory contains only {len(source_only)} "
            "non-executable source-code file(s) with extensions typical of "
            "a coding convention (e.g. React/Rust 'hooks' module naming), "
            "not agent lifecycle scripts -- this is the use-vs-mention case "
            "the catalog names: a directory literally named 'hooks' is not "
            "itself an agent hook registration",
        )
    if non_exec_script_shaped:
        return (
            "inert",
            f"hooks/ directory contains {len(non_exec_script_shaped)} "
            "script-shaped file(s) with NO executable bit set (measured "
            "via os.access X_OK) and no registration wiring found -- not "
            "independently runnable as a hook",
        )
    return (
        "mention-only",
        "hooks/ directory contents are ambiguous (no script/source/YAML "
        "files matched, no settings registration found)",
    )


def classify_config_dir(root: Path) -> tuple[str, str]:
    """Classify a .claude or .codex directory hit: look for a
    settings.json/settings.local.json inside; absent one, report what
    config surface IS present (skills/agents/commands) without inflating
    that into an 'active' finding -- config presence alone is not a hook."""
    try:
        entries = list(root.rglob("*"))
    except OSError as exc:
        return "inert", f"could not walk directory: {type(exc).__name__}"
    settings_files = [
        p
        for p in entries
        if p.is_file() and p.name in {"settings.json", "settings.local.json"}
    ]
    for f in settings_files:
        try:
            verdict, reason = classify_settings_json(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if verdict == "active":
            return "active", f"{f.name} carries a live hooks/mcpServers registration ({reason})"
    if settings_files:
        return (
            "inert",
            f"{len(settings_files)} settings.json found but none carry a "
            "non-empty hooks/mcpServers key",
        )
    subdirs = sorted({p.parent.name for p in entries if p.is_dir()})
    surface = ", ".join(subdirs) or "(empty)"
    return (
        "mention-only",
        f"no settings.json found; directory carries other auto-load config "
        f"surface only (subdirectories: {surface}) -- presence alone is "
        "not a hook or MCP registration finding",
    )


def _is_exec(p: Path) -> bool:
    try:
        return os.access(p, os.X_OK)
    except OSError:
        return False


def classify_hit(path: Path, matched_name: str, kind: str) -> dict:
    """Top-level dispatcher used by both probe 2 and the control. Returns
    {"classification": ..., "reason": ...}; never raises on a read error,
    an unreadable/binary hit is honestly reported as such."""
    try:
        if kind == "dir":
            if matched_name.lower() == "hooks":
                verdict, reason = classify_hooks_dir(path)
            else:
                verdict, reason = classify_config_dir(path)
        else:
            if not path.is_file():
                return {"classification": "inert", "reason": "path no longer exists on disk"}
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return {
                    "classification": "inert",
                    "reason": f"unreadable file: {type(exc).__name__}",
                }
            if matched_name.lower() == ".mcp.json":
                verdict, reason = classify_mcp_json(text)
            else:
                verdict, reason = classify_text_content(text)
    except OSError as exc:
        return {"classification": "inert", "reason": f"filesystem error: {type(exc).__name__}"}
    return {"classification": verdict, "reason": reason}


if __name__ == "__main__":
    import sys

    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if p is None:
        print("usage: _autoload_classifier.py <path>")
        raise SystemExit(2)
    kind = "dir" if p.is_dir() else "file"
    print(json.dumps(classify_hit(p, p.name, kind), indent=2))
