# Frozen excerpt from https://code.claude.com/docs/en/sub-agents fetched 2026-08-24

## Permission modes

Set `permissionMode` to choose the permission mode a subagent runs in. Use the modes' config values, so Manual mode is `default`. If you leave it unset, the subagent inherits the main conversation's mode, which starts as [auto mode](/docs/en/permission-modes#eliminate-prompts-with-auto-mode) on Pro, Max, and Team plans unless your settings or your organization change it. Setting it overrides that mode, except in the cases described below.

If the parent uses `bypassPermissions` or `acceptEdits`, this takes precedence and can't be overridden. If the parent uses [auto mode](/docs/en/permission-modes#eliminate-prompts-with-auto-mode), the subagent inherits auto mode and any `permissionMode` in its frontmatter is ignored: the classifier evaluates the subagent's tool calls with the same block and allow rules as the parent session.

If bypass mode is disabled by [`permissions.disableBypassPermissionsMode`](/docs/en/permissions#managed-settings), Claude Code ignores `permissionMode: bypassPermissions` in the frontmatter and the subagent runs with the parent session's mode. Before v2.1.223, Claude Code applied the frontmatter mode even with bypass disabled.

## Let subagents spawn their own subagents

By default, a subagent can spawn subagents of its own, up to three layers below the main conversation. At the depth limit, Claude Code withholds the `Agent` tool from every subagent except a [fork](#fork-the-current-conversation), so a subagent at the limit does its delegated work itself and returns one summary. A fork at the limit keeps `Agent` in its inherited tool list, but the tool returns an error instead of spawning.

To change the limit, set [`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`](/docs/en/env-vars) to the number of subagent layers you want below your main conversation. Set `1` to turn nesting off.

## Concurrent subagent limit

Two limits control subagent use, each with its own variable: this one stops Claude from spawning more subagents while too many are running, and the [depth limit](#let-subagents-spawn-their-own-subagents) caps how deeply subagents nest. There's no limit on the total number of subagents Claude can spawn over a session.

By default, when 20 subagents are running in a session, spawning another with the Agent tool fails with `Concurrent subagent limit reached`, and the error tells Claude not to retry. Spawning succeeds again when the running count drops below the limit. To change the limit, set [`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`](/docs/en/env-vars) to any positive whole number. Sessions with [ultracode](/docs/en/model-config#adjust-effort-level) active are exempt: the limit isn't enforced there. Requires Claude Code v2.1.217 or later.
