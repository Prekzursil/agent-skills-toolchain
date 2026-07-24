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

Landed in this change: the provenance/license/review record above. This documents the
reviewed backend and its safety verdict so the skill, fleet config, and default-off
work can reference a stable record.

**Not yet built in this change** (tracked follow-up): the hardened runtime
(`package.json`, `package-lock.json`, `tsconfig.json`, `src/index.ts`, `src/corpus.ts`,
`src/markdown.ts`, `src/provenance.ts`, `src/citation.ts`, `src/verify-citation.ts`,
`test/*.test.mjs`, `test/fixtures/`, `scripts/install-hacktricks-mcp-server.ps1`,
`scripts/validate-hacktricks-mcp-server.ps1`). Until it is built, tested to 100%
line/branch coverage under `node --test`, and deployed, the `hacktricks` MCP backend is
NOT registered in the live fleet, and the offline corpus lane (`htk_search.ps1`) plus
the official REST `hacktricks-api` helper remain the working retrieval paths.

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
