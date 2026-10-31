# Hardened HackTricks MCP server (derivative)

Standalone, lockfile-owning, hardened Node/TypeScript derivative of the community
`Xplo8E/hacktricks-mcp-server`, intended to be deployed to
`C:/Users/{{USER}}/.local/opt/hacktricks-mcp-server` and registered under the stable
fleet server ID `hacktricks`. It is deliberately **not** added to the root npm
workspace and does **not** vendor the corpus.

## Adoption statement (normative)

> Add the pinned community `Xplo8E/hacktricks-mcp-server@1.3.4` as the practical local HackTricks MCP backend, exposed in the canonical/user-scope roster but effectively disabled per project by default. Never call it official. Preserve the existing offline `hacktricks` and official REST `hacktricks-api` layers because neither the community MCP nor a stale GitBook mirror is the first-party HackTricks AI service.

> As of 2026-07-24, HackTricks does **not** publish an official MCP server or MCP repository. Official HackTricks AI is an authenticated REST Chat/RAG API. The practical installable MCP is the community-maintained `Xplo8E/hacktricks-mcp-server`; adopt it only under that label, never as an official HackTricks server.

## Provenance and license

- Provenance receipt: `references/provenance.json`
- Safe-review record + rejected unsafe registrations: `references/upstream-sources.md`
- Third-party notice + planned hardening: `NOTICE.md`
- Upstream MIT license (unmodified): `LICENSE`

The reviewed upstream commit `931b474ce6d725ed71cd1a8534758e0dd3f4a110` was
independently re-confirmed by a fresh read-only clone on 2026-07-24 (see
`references/upstream-sources.md`).

## Status of this directory (honest)

Landed earlier: the provenance/license/review record above.

**Built in this change:** the hardened runtime — `package.json`, `package-lock.json`,
`tsconfig.json` (strict, NodeNext, ES2022), and `src/` (`index.ts`, `server.ts`,
`tools.ts`, `corpus.ts`, `markdown.ts`, `provenance.ts`, `citation.ts`, `verify.ts`,
`verify-citation.ts`, `validation.ts`, `errors.ts`, `text.ts`, `util.ts`, `limits.ts`,
`defaults.ts`), `test/*.test.mjs`, `scripts/install-hacktricks-mcp-server.ps1`,
`scripts/validate-hacktricks-mcp-server.ps1`, and `scripts/smoke.mjs`. The seven MCP
tools initialize over stdio through the MCP SDK (verified by `scripts/smoke.mjs`) and
perform real read-only operations against a pinned corpus; all inputs are validated
before I/O; ripgrep is invoked as an executable (`-e … --`, `--json`, bounded
timeout/buffer); the corpus is fail-closed on wrong origin/SHA/dirty/symlink-escape.

**Coverage scope (honest):** `npm test` gates 100% line/branch/function coverage under
`node --test` over the twelve tested modules (all of `src/` except the three
process-boundary entrypoints). `index.ts`, `defaults.ts`, and `verify-citation.ts` are
the real transport/argv/network boundary and are excluded from the coverage denominator
(they are not imported by any test); their behavior is exercised end-to-end by the
`smoke.mjs` stdio round-trip. Test files are excluded from the denominator via
`--test-coverage-exclude`.

**Still human-gated (NOT done by the build):** corpus provisioning to
`D:\knowledge\hacktricks`, deploy to `~/.local/opt/hacktricks-mcp-server`, MCP fleet
registration + user-scope promotion, and a live Claude/Codex `tools/list` acceptance.
Until those run, the `hacktricks` MCP backend is NOT registered in the live fleet, and
the offline corpus lane (`htk_search.ps1`) plus the official REST `hacktricks-api`
helper remain the working retrieval paths.

Build/test contract for the follow-up (from the frozen adoption prompt):

```powershell
Push-Location .\tools\mcp\hacktricks-mcp-server
npm install --package-lock-only --ignore-scripts
npm ci --ignore-scripts
npm test   # tsc build + node --test with 100% line/branch/function coverage
Pop-Location
```

Deployment (Windows estate, human-gated — mutates live state):

```powershell
pwsh -NoProfile -File .\tools\mcp\hacktricks-mcp-server\scripts\install-hacktricks-mcp-server.ps1
pwsh -NoProfile -File .\tools\mcp\hacktricks-mcp-server\scripts\validate-hacktricks-mcp-server.ps1 -InstallRoot 'C:\Users\Prekzursil\.local\opt\hacktricks-mcp-server'
```

Never register the raw upstream via `npx`, `@latest`, global install, or its
`postinstall` script. The runtime identifies as `hacktricks-mcp-hardened` version
`1.3.4-hardened.1`.
