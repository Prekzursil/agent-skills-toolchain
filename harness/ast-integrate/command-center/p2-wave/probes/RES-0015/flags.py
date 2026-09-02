"""Documented flag catalogs for RES-0015.

Cursor official CLI docs were fetched 2026-08-24 from
https://cursor.com/docs/cli/reference/parameters (sha recorded at measure time
from the live --help snapshot, not from this module). Claude Code CLI flags were
fetched the same day from https://code.claude.com/docs/en/cli-reference.

Probes must not fetch the network. These frozen lists plus live `agent --help`
are the documented set executed against the installed binary.
"""
from __future__ import annotations

# Invented flag: acceptance test must REJECT this or the detector is vacuous.
INVENTED_FLAG = "--res0015-invented-flag-xyzzy"

# Cursor docs (parameters page, global options) as of 2026-08-24 fetch.
CURSOR_DOC_FLAGS: tuple[str, ...] = (
    "--version",
    "--api-key",
    "--header",
    "--print",
    "--output-format",
    "--stream-partial-output",
    "--resume",
    "--continue",
    "--model",
    "--mode",
    "--plan",
    "--list-models",
    "--force",
    "--yolo",
    "--sandbox",
    "--approve-mcps",
    "--trust",
    "--workspace",
    "--plugin-dir",
    "--worktree",
    "--worktree-base",
    "--skip-worktree-setup",
    "--help",
)

CURSOR_DOC_SHORT: tuple[str, ...] = ("-v", "-H", "-p", "-f", "-w", "-h")

# Claude Code CLI flags table (code.claude.com/docs/en/cli-reference) 2026-08-24.
# Catalog inputs name this page. A flag here that the installed binary rejects
# is a doc-vs-binary contradiction, not a capability of this box's client.
CLAUDE_DOC_FLAGS: tuple[str, ...] = (
    "--add-dir",
    "--advisor",
    "--agent",
    "--agents",
    "--allow-dangerously-skip-permissions",
    "--allowedTools",
    "--allowed-tools",
    "--append-subagent-system-prompt",
    "--append-system-prompt",
    "--append-system-prompt-file",
    "--autocompact",
    "--ax-screen-reader",
    "--bare",
    "--betas",
    "--bg",
    "--background",
    "--channels",
    "--chrome",
    "--cloud",
    "--continue",
    "--dangerously-load-development-channels",
    "--dangerously-skip-permissions",
    "--debug",
    "--debug-file",
    "--disable-slash-commands",
    "--disallowedTools",
    "--disallowed-tools",
    "--effort",
    "--enable-auto-mode",
    "--environment",
    "--exclude-dynamic-system-prompt-sections",
    "--exec",
    "--fallback-model",
    "--fork-session",
    "--forward-subagent-text",
    "--from-pr",
    "--ide",
    "--init",
    "--init-only",
    "--include-hook-events",
    "--include-partial-messages",
    "--input-format",
    "--json-schema",
    "--maintenance",
    "--max-budget-usd",
    "--max-turns",
    "--mcp-config",
    "--model",
    "--name",
    "--no-chrome",
    "--no-session-persistence",
    "--output-format",
    "--permission-mode",
    "--permission-prompt-tool",
    "--plugin-dir",
    "--plugin-url",
    "--print",
    "--prompt-suggestions",
    "--ref",
    "--remote",
    "--remote-control",
    "--remote-control-session-name-prefix",
    "--replay-user-messages",
    "--resume",
    "--safe-mode",
    "--session-id",
    "--setting-sources",
    "--settings",
    "--strict-mcp-config",
    "--system-prompt",
    "--system-prompt-file",
    "--teleport",
    "--teammate-mode",
    "--tmux",
    "--tools",
    "--verbose",
    "--version",
    "--worktree",
)

CLAUDE_DOC_SHORT: tuple[str, ...] = ("-p", "-c", "-r", "-v", "-n", "-w")

# Flags that take a required value: execute as `<flag>` with no value so
# commander reports "argument missing" (known) vs "unknown option".
VALUE_FLAGS: frozenset[str] = frozenset(
    {
        "--api-key",
        "--header",
        "-H",
        "--endpoint",
        "-e",
        "--output-format",
        "--model",
        "--mode",
        "--sandbox",
        "--workspace",
        "--plugin-dir",
        "--worktree-base",
        "--add-dir",
        "--advisor",
        "--agent",
        "--agents",
        "--append-subagent-system-prompt",
        "--append-system-prompt",
        "--append-system-prompt-file",
        "--autocompact",
        "--betas",
        "--channels",
        "--debug-file",
        "--disallowedTools",
        "--disallowed-tools",
        "--effort",
        "--environment",
        "--fallback-model",
        "--from-pr",
        "--input-format",
        "--json-schema",
        "--max-budget-usd",
        "--max-turns",
        "--mcp-config",
        "--name",
        "--permission-mode",
        "--permission-prompt-tool",
        "--plugin-url",
        "--ref",
        "--remote-control-session-name-prefix",
        "--session-id",
        "--setting-sources",
        "--settings",
        "--system-prompt",
        "--system-prompt-file",
        "--teammate-mode",
        "--tools",
        "--allowedTools",
        "--allowed-tools",
    }
)

# Optional-value / mutating-risk flags: pass a dummy token so the parser
# classifies the flag without opening a picker or creating a worktree.
DUMMY_VALUE_ARGV: dict[str, tuple[str, ...]] = {
    "--resume": ("--resume", "res0015-no-such-chat"),
    "-w": ("--worktree",),  # missing git repo → runtime error, not unknown
    "--worktree": ("--worktree",),
}

# Subcommands: only `<cmd> --help` (never login/update/start).
COMMANDS: tuple[str, ...] = (
    "login",
    "logout",
    "status",
    "whoami",
    "about",
    "models",
    "mcp",
    "plugin",
    "worker",
    "sandbox",
    "acp",
    "update",
    "ls",
    "resume",
    "create-chat",
    "generate-rule",
    "install-shell-integration",
    "uninstall-shell-integration",
    "help",
    "bedrock",
    "agent",
)

# Do not launch a live agent session. --list-models talks to the API but does
# not start a chat; it is a documented flag and must be executed once.
NEEDS_LIVE_INVOKE: frozenset[str] = frozenset({"--list-models", "--version", "-v", "--help", "-h"})
