# Opt-in: hooks and MCP are deliberately NOT shipped by this plugin

This plugin (`agent-skills-toolchain` v0.4.x) is a curated **entry plugin**: six
skill-estate meta-skills, portable slash commands, and agent definitions. It
intentionally declares and ships **no hooks and no MCP servers**:

- no `hooks` key in either manifest twin, and no `hooks/hooks.json` anywhere
  under `plugin/`;
- no `mcpServers` key in either manifest twin, and no `.mcp.json` anywhere
  under `plugin/`.

The repo schema (`.claude-plugin/plugin.schema.json`) keeps
`additionalProperties: false`, so re-introducing a `hooks` or `mcpServers` key
into a manifest fails schema validation at build time — the drift guard is
encoded in the artifact, not in review vigilance.

## Who owns the live wiring (single-writer rule)

Your machine's live hook and MCP wiring already has exactly one writer each:

- **Hooks** — machine settings plus the repo's canonical `hooks/` tree,
  deployed by `scripts/sync-hooks.ps1` from a clone of this repository.
- **MCP** — machine `~/.claude.json`, fed from
  `tools/mcp/canonical-mcp-servers.json` (the repo's canonical 51-server
  registry).

This plugin will never write to either config. Installing, updating, or
uninstalling the plugin is inert with respect to that wiring by construction:
the plugin root (`plugin/`) contains none of the packaged-wiring hazards that
live repo-side (`hooks/`, `hooks/_dispatch/`, `tools/mcp/`, `agent-self/`).

## How to activate hooks or MCP (deliberate, manual steps)

If you want the repo's hook suite or MCP fleet on a machine, that activation is
a **deliberate user action** through the repo's own deployment flows — never a
side effect of installing this plugin:

1. Clone the repository:
   `git clone https://github.com/Prekzursil/agent-skills-toolchain`
2. For hooks: run `scripts/sync-hooks.ps1` from the clone (it deploys the
   canonical `hooks/` tree into your user settings).
3. For MCP: merge the servers you want from `tools/mcp/canonical-mcp-servers.json`
   into your machine `~/.claude.json` (an explicit registry merge).

Deliberately, **no hook or MCP templates ship inside this plugin**: a second
copy of the canonical wiring would itself be the drift this boundary exists to
prevent.
