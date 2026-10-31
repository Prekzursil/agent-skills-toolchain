---
title: README
type: note
permalink: dqverify-repo-20261013/docs/cyberstrike-adoption/readme
---

# CyberStrike adoption — implementation report and operator runbook

Status of this change set: **partial, reversible landing.** This PR commits only the
license-neutral, in-repo, gate-clean pieces of the CyberStrike adoption. The install,
license, promotion, and live-runtime pieces are HUMAN-GATED and are handed back below with
exact commands. Per the adoption prompt's own §13 rule, an unmet human §9 receipt, missing
license decision, or missing Windows prerequisite is a legitimate `FAILED` — weakening a
gate is not — so this lane terminates **FAILED (blocked on human/runtime gates)** with the
reversible work landed.

Grounding: adoption executed against `agent-skills-toolchain` @ base
`7475ee799fcd0bc7204042941a73c0e9e33ff734`. Frozen prompt sha256
`ac7162a84eb34a33a9e3f621ecb5639d4a6cdc22bc1d237eb7f280db08bfd4a2`. Upstream pins:
CyberStrike source review `62fdec93617581a6af97901e0f0c74293cd8d52e`, release `1.1.15`;
Bolt `7f74e5fde28640b9671fec1c6225f301611f68c5`; cloud-audit-mcp
`e32c53a1b02df50e4a1ba072da17b00dc971bb15`; github-security-mcp
`e3ae1322beb487f1a9871e98e698e33000ba32b3`; cve-mcp
`31ee55553a39f0c5d8270977ea308e7a733a57ee`; osint-mcp-server
`7611f70e6a82425f1aa1e40d964057ed5f0dcb60`.

## Committed repository changes (reversible, gate-clean)

1. **Skill wrapper, dual-written and byte-identical:**
   - `.agents/skills/cyberstrike/SKILL.md` and `skills/cyberstrike/SKILL.md`
   - `.agents/skills/cyberstrike/references/capabilities.md` and `skills/cyberstrike/references/capabilities.md`
   - `.agents/skills/cyberstrike/references/plugin-bridge.md` and `skills/cyberstrike/references/plugin-bridge.md`
   - Frontmatter is `name`/`description` only. Byte parity proven by SHA-256 (both roots
     match) and by `ci/check_skill_dual_write.py`.
2. **Canonical MCP fleet (SSOT) merge** in `tools/mcp/canonical-mcp-servers.json`: added
   `cloud-audit`, `github-security`, `osint`; refreshed the existing `cve-mcp` entry in
   place to `cve-mcp@0.2.0` (a refresh, not a second `cve` alias). No `@cyberstrike-io/*`
   dependency, no vendored source. This is a declaration only; nothing promotes it
   automatically.
3. **Regenerated skill index:** `.claude-plugin/marketplace.json` (one added route,
   `./.agents/skills/cyberstrike`), produced by `python ci/gen_skill_index.py --write`;
   `--check --fail-on-drift` reports `INDEX DRIFT: no`.
4. **This documentation directory** (`docs/cyberstrike-adoption/`), including the operator
   SAFE-TO-START review-aid script.

No CyberStrike source/binary/asset/lock/patch/generated-SDK/gitlink; no Bun; no QZP
workflow / Ruff / gitleaks / OSV waiver; no new npm workspace; both skill roots
byte-identical; no literal secret (only `${VAR}` env placeholders).

## What the toolchain CI attests (and does not)

A green QZP run proves only these repository-owned wrapper/config/doc changes. It does NOT
attest to the external CyberStrike application, its dependencies, the companion MCP source,
or any live capability. This change set adds no `.py`/`.ts`/`.mjs` source, so it does not
alter the Ruff, basedpyright, pytest-coverage, OpenGrep, gitleaks, or OSV surfaces.

## AGPL / commercial-license decision status — NOT DECIDED (human gate)

CyberStrike, `@cyberstrike-io/plugin`, and `@cyberstrike-io/sdk` are `AGPL-3.0-only`
(version 3 only). Durable wording (reproduced in the skill references):

> CyberStrike may be used commercially under AGPL if its obligations are satisfied. An
> alternative commercial license is advertised through `contact@cyberstrike.io`; obtain and
> review its written terms before relying on it for proprietary embedding, distribution, or
> a modified hosted service.

No license decision has been made in this lane. The in-process SDK plugin
(`plugin/harness-bridge.ts`) is therefore NOT authored or committed; it must remain a
separately installed CyberStrike-side artifact under an explicitly reviewed
AGPL-compatible or written-commercial license. Process separation reduces combined-work
risk; it is not a legal opinion.

## Deferred engineering (reversible but NOT in this PR, with rationale)

The following are license-neutral and reversible, but are intentionally deferred rather
than half-built, because (a) they are coupled to the AGPL external plugin and Windows
runtime that this lane cannot exercise, so §13 items 6–7 cannot reach SUCCESS regardless,
and (b) shipping unverified security-critical code (HMAC auth, fail-closed policy,
redaction) as green-but-untested would violate the honesty contract. Full authoritative
specifications are in `skills/cyberstrike/references/plugin-bridge.md`.

- **Private gateway** `tools/mcp/cyberstrike-harness-bridge/` (Node ESM, no CyberStrike
  import): `server.mjs`, `protocol.mjs`, `auth.mjs` (per-request HMAC-SHA256, ±30 s skew,
  nonce cache, constant-time), `redact.mjs`, `policy.mjs`, `capabilities.mjs` (ten
  capabilities with real strict schemas), `harness-provider.mjs`, `skill-trust.mjs`,
  `cyberstrike-client.mjs`, plus 8 `node --test` suites and the sterile PS7 supervisor.
  Adds itself (only) as a root npm workspace and regenerates `package-lock.json` with
  Node 22/npm. Residual: full protocol + 17-hook + reverse-control + redaction + negative
  tests at 100% coverage.
- **Python harness extension** (`agent-self/harness/`): add `"cyberstrike"` to
  `SUPPORTED_PROVIDERS`, `normalize_event`, dispatcher CLI choices, and the hook-event
  schema provider enum; CyberStrike-only `render_output()` emits `HookResult.to_dict()`
  unchanged. Prove Claude/Codex registrations byte-for-byte unchanged and an unsupported
  fourth provider fails; 100% line+branch for the package. Coupled to the gateway (nothing
  consumes the provider without it), so deferred with it.
- **Fan-out adapter** beside `.agents/skills/codex-databricks-fanout/scripts/harness/`
  for the four `fanout.*` capabilities (preserving frozen `RAIL`, concurrency 48, stagger
  3.0, ambient `DATABRICKS_TOKEN` removal, child-scoped `MSYS_NO_PATHCONV`).
- **Claude-side direct-MCP engagement guard**: extend the existing reviewed `PreToolUse`
  policy to cover `mcp__cloud-audit__*`, `mcp__github-security__*`, `mcp__cve-mcp__*`,
  `mcp__osint__*`. Until this guard exists AND the four servers are proven effectively
  project-disabled by default, the four companion servers MUST NOT be enabled.

## Human gates — exact hand-back commands

### G1. AGENTS.md §9 auto-load-hazard SAFE-TO-START (operator, non-agent PowerShell 7)

An operator must run `docs/cyberstrike-adoption/operator-safe-to-start-gate.ps1` from a
fresh, trusted PowerShell 7 that is NOT an agent, and return the exact
`SAFE-TO-START:62fdec93617581a6af97901e0f0c74293cd8d52e` receipt plus the recorded hashes.
Claude Code must never run this gate itself, never make the raw clone a CWD, and never run
a cloned repo's hooks. Until the receipt exists, no agent process may start with its CWD
inside the raw CyberStrike clone, and installation/adoption of the runtime is blocked.

### G2. Install the pinned external backend (operator, trusted external dir — NOT the monorepo)

```powershell
$CyberStrikeVersion = '1.1.15'
npm view "@cyberstrike-io/cyberstrike@$CyberStrikeVersion" version license dist.integrity dist.tarball scripts
npm pack --ignore-scripts "@cyberstrike-io/cyberstrike@$CyberStrikeVersion"   # review tarball/postinstall FIRST
$env:HUSKY = '0'
npm install --global "@cyberstrike-io/cyberstrike@$CyberStrikeVersion"
Get-Command cyberstrike -ErrorAction Stop
cyberstrike --version   # must equal 1.1.15
```

Bun 1.3.9 is a separate external user-scoped prerequisite for `cloud-audit` and the
external plugin only; it must never enter the monorepo. cloud-audit bootstrap
(hook-inert, `--ignore-scripts`, pinned to `e32c53a1b02df50e4a1ba072da17b00dc971bb15`) is
specified in `skills/cyberstrike/references/plugin-bridge.md`.

### G3. Promote the canonical fleet to user scope (operator, ALL Claude processes closed)

Cannot run while Claude Code is live (live processes rewrite `.claude.json`). After closing
every Claude window/CLI:

```powershell
$Repo = "$env:USERPROFILE\source\agent-skills-toolchain"
$Promoter = "$Repo\hooks\mcp-userscope-sync\promote-mcp-userscope.ps1"
# 1) render/copy the versioned roster to ~/.mcp.json (back up first), then:
pwsh -NoProfile -File $Promoter -DryRun -PruneExtraUserServers   # REVIEW every add/update/prune line
pwsh -NoProfile -File $Promoter -PruneExtraUserServers -Yes      # apply after review; never -Force
```

Then merge/sort/dedup the four IDs into `%USERPROFILE%\.claude\.mcp-disabled-defaults.json`
`disabledMcpServers` (see `default-off-fragment.json`), verify SessionStart wires
`python {{USER_HOME}}/.claude/hooks/mcp-defaults/enforce-mcp-defaults.py`, pre-seed the four
IDs into every known project's effective disabled list while Claude is closed, restart, and
prove for one existing and one new project that `/mcp` reports all four disabled and no
companion child process spawned. Only then enable one at a time in an authorized test
project and assert exact tool counts `38` (cloud-audit), `39` (github-security), `41`
(cve-mcp), `37` (osint).

Verify the cloud-audit path on the real Windows host before trusting it (the hardcoded user
path was not verifiable on the synthesis node):

```powershell
Test-Path -LiteralPath 'C:\Users\Prekzursil\.local\opt\cloud-audit-mcp\src\index.ts'
```

If false because the actual user/path differs, render the verified absolute forward-slash
path in the SSOT and record the deviation.

### G4. Live runtime + capability smoke (operator, Windows / separately authorized Linux)

Sterile supervisor TUI/web/run/HackBrowser/Bolt paths, `/global/health`, tier-one offline
prompt, one authorized non-mutating lab action, native `winhook` (Administrator) marked but
not smoke-run, eBPF only on a separately authorized Linux host (kernel ≥ 4.7, root, BCC).
See `skills/cyberstrike/references/capabilities.md`.

### G5. Signed engagement guard + external AGPL plugin

Author `plugin/harness-bridge.ts` in the external CyberStrike-owned config tree under a
reviewed AGPL-compatible or written-commercial license (blocked on G-license), and stand up
the private gateway + Claude-side direct-MCP guard with the negative/bypass test matrix in
`plugin-bridge.md`. No active/tier-three capability may be enabled before these fail-closed
controls pass their negative tests.

## Terminal marker

`FAILED` — blocked on: (1) operator SAFE-TO-START:<commit> receipt = NONE; (2) CyberStrike
1.1.15 / Bun 1.3.9 / cloud-audit install = not performed (human gate); (3) AGPL/commercial
license decision = NONE; (4) user-scope MCP promotion requires all Claude processes closed
= not satisfiable in-session; (5) live Windows/Linux runtime + external AGPL plugin +
signed engagement guard = not exercised. Reversible work (skill wrapper dual-write, MCP
SSOT declaration, regenerated index, docs) is landed and gate-clean. Smallest safe next
action: run G1, then G2/G3/G5 in order; do not enable any companion MCP or tier-two/three
CyberStrike capability until the engagement guard passes its negative tests.