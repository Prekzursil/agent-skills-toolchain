"""Twenty load-bearing official-doc statements this program depends on.

Partitions:
  A  S01-S10  plugin.json / marketplace / hooks  (hunter_a)
  B  S11-S20  settings / skills / CLI / subagents / URLs  (hunter_b)
"""
from __future__ import annotations

from typing import Any

STATEMENTS: list[dict[str, Any]] = [
    {
        "id": "S01",
        "partition": "A",
        "doc_id": "plugins-reference",
        "needles": [
            "If you include a manifest, `name` is the only required field.",
        ],
        "statement": (
            "Official plugin.json schema: if a manifest is present, `name` is "
            "the only required field."
        ),
        "depends_on": "RES-0007 plugin.json required/optional fields",
    },
    {
        "id": "S02",
        "partition": "A",
        "doc_id": "plugins-reference",
        "needles": [
            "Claude Code ignores top-level fields it does not recognize",
        ],
        "statement": (
            "Official plugin.json schema: unrecognized top-level fields are "
            "ignored (not a load error)."
        ),
        "depends_on": "RES-0007 unknown top-level field strictness",
    },
    {
        "id": "S03",
        "partition": "A",
        "doc_id": "plugins-reference",
        "needles": [
            "`claude plugin validate` reports unrecognized fields as warnings, not errors",
        ],
        "statement": (
            "Official plugin.json schema: `claude plugin validate` reports "
            "unrecognized fields as warnings, not errors."
        ),
        "depends_on": "RES-0007 validator behaviour",
    },
    {
        "id": "S04",
        "partition": "A",
        "doc_id": "plugins",
        "needles": [
            ".claude-plugin/plugin.json",
        ],
        "statement": (
            "The plugin manifest lives at `.claude-plugin/plugin.json` relative "
            "to the plugin root."
        ),
        "depends_on": "RES-0007/RES-0008 packaging layout",
    },
    {
        "id": "S05",
        "partition": "A",
        "doc_id": "plugins-reference",
        "needles": [
            "`plugin.json` wins",
        ],
        "statement": (
            "When `version` is set in both plugin.json and the marketplace "
            "entry, plugin.json wins."
        ),
        "depends_on": "RES-0008 plugin-vs-marketplace version precedence",
    },
    {
        "id": "S06",
        "partition": "A",
        "doc_id": "plugins-reference",
        "needles": [
            "kebab-case, no spaces",
        ],
        "statement": (
            "plugin.json `name` is a unique kebab-case identifier with no spaces."
        ),
        "depends_on": "RES-0007 naming contract",
    },
    {
        "id": "S07",
        "partition": "A",
        "doc_id": "hooks",
        "needles": [
            "exit 2 blocks",
        ],
        "statement": (
            "Hook exit code 2 blocks the triggering action on events that support blocking."
        ),
        "depends_on": "RES-0009 hook exit-code semantics",
    },
    {
        "id": "S08",
        "partition": "A",
        "doc_id": "hooks",
        "needles": [
            "Return `additionalContext` inside `hookSpecificOutput`",
        ],
        "statement": (
            "UserPromptSubmit additionalContext must be returned inside "
            "hookSpecificOutput (top-level additionalContext is ignored)."
        ),
        "depends_on": "RES-0009 additionalContext delivery",
    },
    {
        "id": "S09",
        "partition": "A",
        "doc_id": "hooks",
        "needles": [
            "Defaults: 600 for `command`",
        ],
        "statement": (
            "Default timeout for command/http/mcp_tool hooks is 600 seconds "
            "(except UserPromptSubmit, which lowers it)."
        ),
        "depends_on": "RES-0009 hook timeout",
    },
    {
        "id": "S10",
        "partition": "A",
        "doc_id": "plugin-marketplaces",
        "needles": [
            '"source":',
        ],
        "statement": (
            "A marketplace plugin entry identifies where to load the plugin via "
            "a `source` field."
        ),
        "depends_on": "RES-0008 marketplace.json schema",
    },
    {
        "id": "S11",
        "partition": "B",
        "doc_id": "settings-reference",
        "needles": [
            "`enabledPlugins`",
        ],
        "statement": (
            "enabledPlugins is a settings-file key (scope: any settings file), "
            "not a ~/.claude.json global-config key."
        ),
        "depends_on": "RES-0012 enabledPlugins file location",
    },
    {
        "id": "S12",
        "partition": "B",
        "doc_id": "settings",
        "needles": [
            "~/.claude/settings.json",
        ],
        "statement": (
            "User-scope settings live at `~/.claude/settings.json`."
        ),
        "depends_on": "RES-0012 settings precedence",
    },
    {
        "id": "S13",
        "partition": "B",
        "doc_id": "settings-reference",
        "needles": [
            "~/.claude.json",
        ],
        "statement": (
            "Claude Code keeps a separate global config file at `~/.claude.json` "
            "that is not one of the four settings.json scopes."
        ),
        "depends_on": "RES-0012 ~/.claude.json vs settings.json",
    },
    {
        "id": "S14",
        "partition": "B",
        "doc_id": "mcp",
        "needles": [
            "disabledMcpServers",
        ],
        "statement": (
            "disabledMcpServers is an opt-out list (documented on the MCP page) "
            "distinct from settings-file MCP approval keys."
        ),
        "depends_on": "RES-0012 disabledMcpServers location",
    },
    {
        "id": "S15",
        "partition": "B",
        "doc_id": "skills",
        "needles": [
            "| `paths`",
        ],
        "statement": (
            "Skill YAML frontmatter supports a `paths` field that limits when "
            "the skill auto-activates."
        ),
        "depends_on": "RES-0010 skill paths: lazy-load",
    },
    {
        "id": "S16",
        "partition": "B",
        "doc_id": "skills",
        "needles": [
            "aren't loaded at startup",
        ],
        "statement": (
            "Skills in nested `.claude/skills/` directories below the starting "
            "directory are not loaded at startup."
        ),
        "depends_on": "RES-0010 turn-0 vs lazy skill load",
    },
    {
        "id": "S17",
        "partition": "B",
        "doc_id": "cli",
        "needles": [
            "`--print`, `-p`",
        ],
        "statement": (
            "The CLI `--print` / `-p` flag runs Claude Code non-interactively."
        ),
        "depends_on": "RES-0015 headless/SDK surface",
    },
    {
        "id": "S18",
        "partition": "B",
        "doc_id": "cli",
        "needles": [
            "stream-json",
        ],
        "statement": (
            "Print mode `--output-format stream-json` is a documented CLI output format."
        ),
        "depends_on": "RES-0015 stream-json control channel",
    },
    {
        "id": "S19",
        "partition": "B",
        "doc_id": "sub-agents",
        "needles": [
            "If you leave it unset, the subagent inherits",
        ],
        "statement": (
            "If a subagent's permissionMode is unset, it inherits the parent "
            "conversation's permission mode."
        ),
        "depends_on": "RES-0016 subagent permission inheritance",
    },
    {
        "id": "S20",
        "partition": "B",
        "doc_id": "hooks",
        "needles": [
            "code.claude.com",
            "hooks",
        ],
        "statement": (
            "The historical docs.claude.com/en/docs/claude-code/* URLs redirect "
            "to code.claude.com/docs/en/* (the live docs host)."
        ),
        "depends_on": "RES-0001 URL 301 chain this program depends on",
    },
]


def by_id() -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in STATEMENTS}


def partition(part: str) -> list[dict[str, Any]]:
    return [s for s in STATEMENTS if s["partition"] == part]


for _stmt in STATEMENTS:
    _stmt.setdefault("doc_id", _stmt.get("doc_id"))
    _stmt.setdefault("partition", _stmt.get("partition"))
    _stmt.setdefault("needles", _stmt.get("needles"))

by_id = by_id
