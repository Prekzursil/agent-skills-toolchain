---
title: NOTICE
type: note
permalink: dqverify-repo-20261013/tools/mcp/hacktricks-mcp-server/notice
---

# NOTICE — HackTricks MCP server (hardened derivative)

This directory holds the provenance, license, and review record for a hardened
derivative of an **unofficial, community-maintained** HackTricks MCP server. It is
**not** operated, endorsed, or published by HackTricks.

## Upstream (reviewed, pinned)

- Upstream repository: `https://github.com/Xplo8E/hacktricks-mcp-server`
- Reviewed commit: `931b474ce6d725ed71cd1a8534758e0dd3f4a110`
- npm package: `hacktricks-mcp-server@1.3.4`
- npm integrity: `sha512-UupJYXXjWFq7AD+HnY7L3LRjv1gAiVtVrnxm7gGeGE7qFNpSh3NzFr6v7JW4rAj69MbUK7CMDUuLo2BC1ezkQg==`
- MCP Registry identity: `io.github.Xplo8E/hacktricks-mcp-server`
- npm release/tag commit: `b184f3d44f946bf6b0cc751ab0817078ee55accd`

The npm package reports `1.3.4`, while the upstream MCP `serverInfo` / startup text
report `1.3.0`. Both values are preserved here on purpose; neither is falsified. The
hardened derivative identifies at runtime as `hacktricks-mcp-hardened` version
`1.3.4-hardened.1`; that derivative identity does not erase the recorded upstream
mismatch.

Never use the deprecated, non-equivalent npm package `hacktricks-mcp@1.3.0`, and never
register the raw upstream via a floating `npx`, `@latest`, global install, or its
`postinstall` script.

## Upstream license

The upstream wrapper is **MIT** (Copyright (c) 2025 Xplo8E). The unmodified upstream
MIT text is copied to `LICENSE` in this directory. That MIT grant covers the wrapper
code only and does **not** relicense HackTricks corpus content.

## Corpus license (separate)

Original HackTricks text (`src/LICENSE.md`) is **CC BY-NC 4.0**. Third-party excerpts
retain their own ownership and terms. Preserve attribution and the noncommercial
restriction; require an appropriate license review before organizational or
commercial reuse. The hardened wrapper never relicenses corpus content.

## Material security changes planned for the hardened derivative

The raw upstream fails this estate's run/lifecycle-security gate. See
`references/upstream-sources.md` for the reviewed evidence. The hardened derivative
must, at minimum:

- remove all `preinstall`/`install`/`postinstall`/`prepare` lifecycle scripts;
  the first dependency materialization is `npm ci --ignore-scripts`;
- never auto-clone or auto-fetch a corpus on install, startup, SessionStart, lookup,
  or CI; provision the corpus explicitly and detach it at a pinned 40-hex SHA;
- pin the full dependency graph via a committed `package-lock.json` (upstream leaves
  the `@modelcontextprotocol/sdk` at a floating `^1.0.0`);
- validate all inputs before I/O; spawn no shell; invoke ripgrep as an executable with
  `-e ... --`, `--json`, a bounded timeout and buffer, and reap timed-out children;
- fail closed on a missing/wrong-origin/wrong-SHA/dirty/symlinked corpus, and prove
  citation-grade reads with `git show <sha>:<path>` / blob equality;
- never log raw queries, page content, credentials, or target selectors.

> Status: the hardened runtime build (`src/`, `package.json`, `package-lock.json`,
> `test/*.test.mjs`, install/validate scripts) is landed and passes `npm test`
> (tsc build + `node --test` at 100% line/branch/function coverage over the tested
> modules). Corpus provisioning, deploy, and MCP fleet registration remain human-gated;
> see `README.md`.