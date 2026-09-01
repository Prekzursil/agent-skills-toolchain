# Long-Horizon Closure Program

Date: 29.08.2026  
Status: IN PROGRESS  
Owner goal: Finish every active workstream without regression, silent abandonment, or false green.

## Completion contract

A lane is complete only when:

1. promised artifact exists on disk;
2. deterministic tests/checks pass;
3. applicable code, language, and security reviews pass;
4. live wiring is tested when the lane claims live behavior;
5. no unresolved critical/high finding remains;
6. optional/minor findings are fixed or explicitly disproven;
7. state and rollback/resume instructions are recorded.

Budget abort, interruption, missing output, stale UI card, or agent self-report is not completion.

## Banked completed evidence

- Fabric diagnosis: no working provider default; strategy folder error identified.
- Cursor CLI: current build and ACP handshake verified.
- Avante: installed, configured, hardened, ACP model response and Zen startup verified.
- Avante launcher ACLs restricted to owner/SYSTEM/Administrators.
- Windows optional diagnostics root cause fixed: stale local organization policy removed after backup;
  normal optional diagnostics set to level 3; DiagTrack running.
- `/mcp-gui` removed; `/mcp-manager` is the sole live/repo/mirror command.
- Command rename isolated-index tests: 127 passed; review passed.
- LinkedIn MCP source recovered; 82 offline tests pass; live auth/API remains NOT-CHECKED.
- Daria Codeg: pinned container running non-root, read-only root, only `D:\Daria_proiect`
  writable, skills/AGENTS read-only, 1.5 GiB memory and 128 PID limits.
- Daria Tailscale URL active: `https://desktop-a60s9gp.taile2627e.ts.net/`.
- Daria Codeg workspace `/workspace` registered; token stored owner-only and never printed.
- Workflow catalog: 40 workflows, 320 exact required subsections, assembled blueprint on disk.
- Workflow scope/alignment review passed.
- Long-horizon research report: `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md`, 20 graded
  sources, SHA-256 `815330B6EAB375CA8F7E8307F35212C5FE8047649022739DE39F223393B70E72`.
- Quality-gate playbook: `LONG-HORIZON-QUALITY-GATE-PLAYBOOK_2026-08-29.md`.
- Concurrency bound: one live/shared mutation, one local Cursor agent, one browser automation
  lane, at most two read-only research/review agents, and one final reconciler.

## Active lanes

### L1 — MCP manager and definition restoration

State:

- `D:\tools\mcp-manager` latest disk verification: 363 tests pass; Ruff lint/format and mypy pass;
  guarded verification left `.mcp-funnel.json` byte-identical.
- No implementation repair agent remains active.
- Multi-model review still finds an untested plane-specific core mismatch: Cursor `core` currently
  resolves from the Claude preset catalog and can disable four required Cursor core servers.
- Deployed and private-SSOT mcp-manager trees diverge in both directions; reconciliation must retain
  SSOT-only `surface_census`/dead-MCP work and deployed-only Cursor support.
- `.agents` now uses two-phase guarded attachment: default sync remains core-six-only; attach-all
  dry-run projects 38; live write refuses unless approval evidence is core-only.
- Shared MCP control-plane tests pass after fixing the Claude HTTP renderer.
- Current workspace has 38 approval records / 37 unique names / 31 unique non-core names; live
  attachment remains forbidden until
  the exact-workdir pre-disable maintenance step.
- Live funnel was unintentionally changed by a test to the `re` profile. Further manager tests are
  frozen until the owner selects a temporary recovery profile.

Remaining:

1. repair reviews to zero critical/high/minor findings;
2. sync reviewed D:\ source/tests/docs selectively into private SSOT
   `source\agent-skills-toolchain\tools\mcp-manager`;
3. run both deployed and SSOT test suites;
4. freeze Cursor sessions for maintenance;
5. use manager to pre-disable every non-core ID and verify approval store is core-only;
6. guarded attach-all-safe write;
7. restart one workspace and prove only core six processes/tools active;
8. test one named preset and disable→enable refresh;
9. retain LinkedIn default-off.

### L2 — Daria private AI workspace

State:

- Codeg container, Tailscale Serve, workspace, mounts, and host-side HTTPS mapping are live.
- Container was recreated without `CURSOR_API_KEY`; no owner Cursor credential remains in its env.
- Banned `mem0-qdrant` container is stopped, not deleted.
- Codeg detects Cursor but reported local Cursor agent not installed before installation was started.
- Browser automation is paused at owner request.

Remaining:

1. confirm Codeg Cursor install completion;
2. configure API-key auth without exposing key;
3. configure sandbox/manual permissions and host-tools=agent;
4. hide/lock terminal by default; owner-unlock only;
5. disable all non-Cursor agents for Daria;
6. verify chat, attachment/photo, permission, cancellation, session resume, and workspace-only write;
7. verify no host path/secret/MCP access;
8. provide Daria only Tailscale invite, URL, Codeg token, and `/workspace` instructions.

### L3 — Workflow blueprint repair

State:

- Final artifact: `.agents\PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md`.
- Scope/alignment: PASS.
- Feasibility: FAIL with 13 blockers.
- Completeness: FAIL with 12 blockers.

Remaining:

1. repair shared taxonomies, SourceRecord, capabilities, engine contract, disclaimers, approval
   semantics, resource state, deterministic rendering, duplicate-prevention schema, and roadmap;
2. repair Part 02 lifecycle/capability/risk enums;
3. expand Part 05 workflow graphs/sources/gates;
4. add graph edges and canonical-owner grammar across all parts;
5. reassemble final blueprint and re-pin hashes;
6. rerun feasibility, completeness, and scope reviews until all PASS;
7. deterministic 40/320/source/citation/reconciliation verification.

### L4 — Browser, Avante, diagnostics, and documentation

State:

- Playwright MCP proved background/no-focus automation.
- Browser rail foreground launcher does not survive the driver process; it is not the seamless lane.
- Active Playwright MCP is unpinned and lacks an explicit persistent headless profile.
- Rollback placeholder corrected to `agents-cp rollback <release> --dry-run`.

Remaining:

1. pin Playwright MCP;
2. configure dedicated persistent headless profile for no-focus work;
3. preserve mandatory per-run live/persistent/ephemeral profile choice;
4. re-run no-focus browser smoke without touching owner Chrome;
5. re-verify Windows Diagnostics Settings UI after policy refresh/reboot;
6. final Avante security re-review after ACL/wrapper hardening.

### L5 — Independent evidence and governance

State:

- Formal uncommitted security review completed.
- Ten-model adversarial review completed/near-completed with consensus verdict FAIL until L1-L4 close.
- Quick grill research completed: G-12, G-14-G-18, and G-20 are evidence-derived; G-13 plus
  G-19/G-21 thresholds require owner choices.
- Quality-gate architecture and 20-source long-horizon research are complete on disk.
- DeepSource/Codacy analyzer work is retired by current owner direction. The newly installed
  DeepSource CLI was moved out of the active install and removed from user PATH; its reversible
  backup is under `.agents\backups\retired\`.
- Basic Memory MCP has repeatedly returned `Session not found`; memory writes are deferred, not
  silently treated as complete.

Remaining:

1. reconcile the exact broader retired analyzer skill/MCP set when Basic Memory is available or
   the owner confirms the names;
2. synthesize/deduplicate the multi-model findings against the latest subject digests;
3. resume and converge extensive grill G-12 through G-21;
4. self-reflect candidate learnings individually with the owner;
5. final completion audit across all lanes.

## Hard boundaries

- No force push, hard reset, credential rotation, secret output, or live-browser profile access.
- No commit unless owner explicitly requests it.
- No expanded Cursor MCP write before approval state is proven core-only.
- No Daria access to owner filesystem, browser profiles, global MCPs, or harness writes.
- No browser automation while owner says it is manually controlled.
- One local `cursor-agent` process maximum.
- Do not disable Basic Memory semantics or other capabilities to buy reliability.

## Current next event

Await MCP repair agents while independent review/research lanes run in background. Browser lane
remains paused. Update this file at every lane boundary.
