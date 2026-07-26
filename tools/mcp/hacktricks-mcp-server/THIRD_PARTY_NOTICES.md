# Third-party notices

This hardened derivative bundles / derives from third-party components. Each
retains its own license and ownership; this file records them. It does not
relicense any corpus content.

## Runtime dependency

- `@modelcontextprotocol/sdk` @ 1.29.0 — MIT (Anthropic). Used for the stdio MCP
  server/client transport and JSON-RPC types. See its bundled LICENSE under
  `node_modules/@modelcontextprotocol/sdk`.
- Transitive `@hono/node-server` is pinned to 2.0.5 via `overrides` to avoid
  `GHSA-frvp-7c67-39w9`; it is a transitive dependency of the SDK and is not
  imported directly by this server (the server uses only the stdio transport).

## Upstream behavioral source (reviewed, pinned; not vendored verbatim)

- `Xplo8E/hacktricks-mcp-server` — MIT (Copyright (c) 2025 Xplo8E). The seven-tool
  behavioral contract of this hardened derivative is based on the reviewed commit
  `931b474ce6d725ed71cd1a8534758e0dd3f4a110` (npm `hacktricks-mcp-server@1.3.4`).
  The upstream `postinstall`, auto-configuration, cloned corpus, and lifecycle
  scripts are deliberately NOT reproduced. The unmodified upstream MIT text is in
  `LICENSE`; see `NOTICE.md` and `references/upstream-sources.md` for the review
  record and rejected-unsafe-registration notes. This is not operated, endorsed,
  or published by HackTricks.

## Corpus content (separate license, not bundled here)

- HackTricks main-book corpus (`https://github.com/HackTricks-wiki/hacktricks`),
  pinned at `346301958c8bf94120ba0aaaaf9cd963997bdac3`, is provisioned at deploy
  time to the runtime root and is NOT vendored into this repository. Original
  HackTricks text is **CC BY-NC 4.0**; third-party excerpts retain their own
  ownership and terms. Preserve attribution and the noncommercial restriction;
  require an appropriate license review before organizational or commercial reuse.
