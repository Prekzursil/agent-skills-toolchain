# MCP Tools

`tools/mcp/` is the live home for MCP-native tools and adapters.

Put a project here only when it is runnable or clearly bounded enough that its runtime, auth model, and validation path are explicit. Do not use this folder for vague notes or mixed browser automation experiments.

Current bounded projects:

- [`agent-lanes-codex/`](agent-lanes-codex/README.md) - Codex-side orchestration lane with explicit profiles, aliases, and bounded fallback behavior.
- [`workstation-codex-bundle/`](workstation-codex-bundle/README.md) - curated Windows-first MCP bundle with explicit self-made vs curated provenance and validation notes.
- [`cheatengine-mcp-bridge/`](cheatengine-mcp-bridge/README.md) - thin Windows-first wrapper around the upstream Cheat Engine MCP Bridge with install and validation helpers.
- [`hexstrike-ai/`](hexstrike-ai/README.md) - Windows-first wrapper around the upstream HexStrike AI runtime with localhost bootstrap and Codex / Claude / Gemini registration helpers.
- [`codex-fleet-github/`](codex-fleet-github/README.md) - local FastMCP connector that drives the private Codex-on-GitHub runner (`codex-runner.yml`); propose-only draft PRs, fail-closed auth (`CODEX_DISPATCH_PAT`), four tools (dispatch / sweep / status / orchestrate).
- [`linkedin-mcp/`](linkedin-mcp/README.md) - self-serve LinkedIn (personal developer app) FastMCP server: OpenID-Connect identity + Share-on-LinkedIn member posting. Env-only credentials (no committed secret), 11 tools, partner-gated surface documented not shipped. See its `SETUP.md` for the developer-portal click-path.
- [`proxy-mcp/`](proxy-mcp/README.md) - HTTP(S) traffic inspection over MCP: list/filter flows, read request+response headers and bodies, replay or modify a request, export HAR. Adopts snapspecter/mitmproxy-mcp (MIT) as the engine and adds credential redaction (ON by default) plus `export_har`. mitmproxy rail verified working here; Fiddler is not installed on this box. Registered disabled-by-default; HTTPS interception needs an owner-installed CA.

Current incubation notes for this surface live under `docs/incubating/tools/`.
