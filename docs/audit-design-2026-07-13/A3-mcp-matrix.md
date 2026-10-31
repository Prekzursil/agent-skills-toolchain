---
title: A3-mcp-matrix
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/a3-mcp-matrix
---

# A3 — MCP Scope / Topology / Lifecycle + Disposition Matrix

**Document:** `A3-mcp-matrix` · **Status:** EVIDENCE (Workflow A) — READ-ONLY audit, no config mutated · **Valid as of:** 2026-07-13  
**Canonical for:** MCP control-plane inventory + disposition across Claude+Codex+Gemini/Antigravity  
**Program:** Workflow A (EVIDENCE, Phase 2 + 4.4) of the one-declarative-harness reliability program (Claude + Codex + Antigravity/Gemini, all first-class).

> **Freeze note.** READ-ONLY audit. Nothing was mutated. All secrets are `${VAR}` placeholders — no secret value was read or printed. Every recommendation below is a **finding**, not an applied change.

**Method.** Direct disk/config/port reads this session; reconciled against Codex CSV + Axis-A inventory-1 + AUDIT-DESIGN-CONVERGED. Every load-bearing claim cited to a path/config-key/port/git-hash.

---

## 1. Source layers (the control-plane surface)

| Layer | Path | Count | Role / health |
|---|---|---|---|
| canonical (live) | `C:/Users/Prekzursil/.mcp.json` | 42 | hand-curated SSOT loaded at HOME project scope; SOURCE of promote script |
| research (stale copy) | `D:/Research/.mcp.json` | 40 | frozen OLD copy (pre-reconcile bugs); only exists because D: sessions can't walk up to C:\Users |
| claude user-scope (loaded) | `C:/Users/Prekzursil/.claude.json -> mcpServers` | 63 | what every normal session actually loads; = canonical + 22 drift-ins − angr |
| claude plugin-bridge | `C:/Users/Prekzursil/.claude.json -> projects[*].disabledMcpServers (plugin:local-mcp-bridge:*)` | ~19 names | RESURFACING route for codacy/deepsource/etc.; a plugin re-registers user-scope servers under plugin: namespace; disabled per-project |
| codex | `C:/Users/Prekzursil/.codex/config.toml -> [mcp_servers.*] + [plugins.*]` | 25 enabled (+1 github removed, 9 flip-off) | Codex parity port; codacy enabled=true; github_cli enabled=false (de-duped) |
| gemini/antigravity | `C:/Users/Prekzursil/.gemini/settings.json -> mcpServers` | 33 | Gemini fleet; carries full cloud-quality family + own `memory` server + WSL ralph adapter |
| repo catalog ca_main (STALE) | `C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/canonical-mcp-servers.json` | 44 | the DECIDED repo SSOT (D2) — but currently STALE vs live ~/.mcp.json (still has exa/figma-rest/firecrawl/tavily; lacks agent-mail/angr/biomni-hub) · `f406d95…` |
| repo template | `C:/Users/Prekzursil/source/agent-skills-toolchain/agent-self/config/mcp/mcp.json` | 37 | {{USER}}-placeholder template fragment, most servers disabled:true; yet another copy |
| reconcile catalog | `(staging, git_hash 8d2bc76…)` | 43 | newer reconcile catalog = ~/.mcp.json + codex-fleet-github; not yet the deployed repo SSOT |
| project | `source/repos/insta-mcp/.mcp.json (+ bilbo-app agent_handler per Axis-A)` | 1 each | genuinely per-project dev servers; keep project-scoped |

**Provider fleet counts (reconciled):** Claude user-scope **63** · Codex **25** enabled (+1 `github` removed 2026-07-13) · Gemini **33** · Antigravity **2** · canonical `~/.mcp.json` **42** · D:/Research **40** · repo catalog (ca_main) **44** · reconcile catalog **43**.

**Live port health (this session, `Get-NetTCPConnection`):** UP → agent-mail `:8812`, basic-memory `:8765`, hexstrike `:8888`. DOWN → angr `:8760` (SSE), searxng `:8890`, ghidra `:8089`, biomni broker `:18787`, binary-ninja `:9009`, IDA `:13337/:8745`, claude-science `:8000`. This corroborates the 'MCP unstable this session' observation: several registered servers have no live backend.

---

## 2. `D:/Research` vs `~` divergence (diff of the two `.mcp.json`)

- **Only in canonical `~/.mcp.json`:** `agent-mail`, `biomni-hub`, `angr`
- **Only in `D:/Research`:** `figma-rest`
- **Value drift (same name, different definition):**
  - `playwright`: canonical @playwright/mcp  vs  D:/Research playwright-mcp
  - `cloud-hub`: canonical KAGGLE_USERNAME+KAGGLE_KEY  vs  D:/Research KAGGLE_API_TOKEN (old)
- **Verdict:** D:/Research/.mcp.json is a STALE FROZEN COPY (pre-reconcile). Superseded by user-scope promotion; recommend delete (finding only — freeze).

---

## 3. The SSOT gap

**5 Claude-side representations of the MCP set — none is both authoritative AND current:**
- `~/.mcp.json (42, live)`
- `D:/Research/.mcp.json (40, stale)`
- `tools/mcp/canonical-mcp-servers.json (44, repo 'main' catalog — STALE)`
- `agent-self/config/mcp/mcp.json (37, {{USER}} template, mostly disabled)`
- `~/.claude.json user-scope (63, actual loaded)`

**Core problem.** No single file is BOTH authoritative AND current. The DECIDED SSOT (repo canonical-mcp-servers.json, D2 repo->live) is itself STALE relative to live ~/.mcp.json. Promote is manual + additive (extras kept) + blocked-on-restart, so user-scope carries 22 drift-ins and stale playwright/cloud-hub values.

**Drift-in (in user-scope, NOT in canonical) — 22:** `apify`, `browserstack`, `claude-code-mcp`, `codacy`, `codecov`, `codex`, `deepscan`, `deepsource`, `digitalocean`, `figma-rest`, `firecrawl`, `github`, `linear`, `mcp-graphql`, `meta-tool`, `notion`, `postgres`, `scrapegraph`, `semgrep`, `sentry`, `sonarqube`, `tavily`

**Drift-out (in canonical, NOT in user-scope):** `angr` (never promoted; promote blocked-on-restart).

---

## 4. Resurfacing resolution — codacy / deepsource (the headline)

**Mechanism.** A `local-mcp-bridge` PLUGIN re-registers user-scope MCP servers under a `plugin:local-mcp-bridge:<name>` namespace. These twins appear (disabled) in EVERY project's disabledMcpServers. This is the RESURFACING route — NOT ~/.mcp.json (codacy/deepsource are absent from both .mcp.json catalogs).

**Verified.** Axis-A inventory-3 line 67 ('Verified.') + AUDIT-DESIGN-CONVERGED §6; independently confirmed this session (codacy/deepsource in ~/.claude.json user mcpServers + plugin:local-mcp-bridge:* in every projects[*].disabledMcpServers). Codex could not see it (inspects .mcp.json only) so flagged it 'unproven'.

- **codacy** → retained-for-distinct-capability; Claude-user+Codex(on)+Gemini; HOLD, do not prune on presence.
- **deepsource** → retained-but-weaker; Claude-user+Gemini, no Codex parity; prune-leaning, owner-gated.

**Strategy note.** Owner had a SOTA MCP strategy: cloud-quality (codacy/deepsource/sonarqube/codecov/deepscan/sentry) intentionally SUPERSEDED by local qlty+semgrep+CLIs (CLAUDE.md tool-routing). The strategy WORKS at the .mcp.json layer (they were dropped there) but is BYPASSED by (a) the plugin-bridge twin and (b) additive user-scope promote never re-run with prune. Fix at plugin layer + prune, not by editing .mcp.json.

**Do NOT infer regression from presence.** The owner's cloud-quality supersession *did* land in the `.mcp.json` catalogs (both omit codacy/deepsource). What resurfaced is the **user-scope + plugin-bridge** copy, which the `.mcp.json`-only view (Codex) can't see. The fix is at the plugin/user-scope layer + a prune-promote, not an `.mcp.json` edit.

---

## 5. Provider parity divergences

- search stack: Claude=hub rotators (search-hub/cloud-hub/social-hub); Codex+Gemini=raw exa/firecrawl/tavily — INTENTIONAL, document don't 'fix'.
- playwright: @playwright/mcp (canonical/user) vs playwright-mcp (D:/Research + Gemini) — reconcile to one.
- cloud-hub Kaggle env: KAGGLE_USERNAME+KAGGLE_KEY (canonical) vs KAGGLE_API_TOKEN (D:/Research + Codex kaggle) — reconcile.
- github: Codex REMOVED [mcp_servers.github] (2026-07-13, de-dup); Claude-user+Gemini still carry the remote Copilot github MCP alongside github_cli.
- github_cli: enabled in Claude/Gemini, enabled=false in Codex (de-duped vs github plugin+gh).
- ralph-orchestrator: native Windows ralph.exe (Claude/canonical) vs WSL bash wrapper (Gemini) — valid provider adapter.
- memory: Gemini runs @mcp/server-memory (2nd store) vs basic-memory authority (Claude/Codex) — SSOT conflict.

---

## 6. Process-topology & concurrency model

- **per session stdio:** Each Claude/Codex/Gemini session spawns its OWN child process per stdio server -> correctness-isolated (no shared state) but N sessions = N× processes = N× RAM. This is the RAM-OOM tax (MEMORY: ram_oom_mcp_diagnosis, semgrep ~920MB/session). Mitigation = fewer always-on stdio servers + hubs + flip-on.
- **shared daemon:** http/sse local (basic-memory:8765, agent-mail:8812, angr:8760): ONE process serves N sessions -> RAM-efficient but a shared-state singleton (basic-memory SQLite -> write-contention/wedge risk; deployment must not hard-depend on it).
- **remote:** http remote (deepwiki/figma/huggingface/github/notion/linear/apify): concurrency handled provider-side; cost = tool-schema context only.
- **external backend:** RE servers (ida/ghidra/frida/binja/cheatengine/hexstrike): per-session MCP child + ONE shared external backend GUI/server -> multi-session contends on the single backend; keep flip-on.

---

## 7. Full disposition matrix

Presence legend: `C=~/.mcp.json  R=D:/Research  U=claude user-scope  X=codex-enabled x=codex-registered-but-disabled  G=gemini  M=ca_main(44) repo catalog`

| MCP | Presence | Transport | Topology | Concurrency | Disposition class | Disposition (evidence) | Conf |
|---|---|---|---|---|---|---|---|
| `apify` | `--UX--` | http/stdio(remote or npx) | per-session/remote | per-session/provider | experimental | REVIEW — web-scrape SaaS; overlaps search-hub/firecrawl. Claude-user+Codex. Owner keep/prune. | medium |
| `claude-code-mcp` | `--U---` | http/stdio(remote or npx) | per-session/remote | per-session/provider | experimental | REVIEW-PRUNE — spawns nested Claude (@steipete); likely leftover experiment. Claude-user only, not in any catalog. | medium |
| `codex-fleet-github` | `-----M` | stdio | per-session-stdio | per-session | experimental | EXPERIMENTAL — present in BOTH catalogs (ca_main 44 + reconcile 43) but deployed to NO provider (not in ~/.mcp.json/user/codex/gemini). Do not promote until owning runtime accepted. | high |
| `scrapegraph` | `--UXG-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | experimental | REVIEW — scrape SaaS; overlaps search-hub. Claude-user+Codex+Gemini. | medium |
| `codex` | `--U---` | stdio | per-session-stdio (spawns Codex) | per-session | intentionally-restored | RETAIN — Layer-1 fan-out rail (mcp__codex__*), documented in CLAUDE.md. User-scope only; SHOULD be added to canonical ~/.mcp.json (currently SSOT-orphan). | high |
| `agent_handler` | `------` | stdio (mcp-remote) | per-session-stdio | per-session | project-specific | KEEP project-scoped — bilbo-app perplexity agent-proxy (reported by Axis-A inventory-1; not re-verified this session). Do NOT promote. | medium |
| `browserstack` | `--U-G-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | project-specific | REVIEW — cross-browser test SaaS; project-scoped at most. Claude-user+Gemini. | medium |
| `digitalocean` | `--U-G-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | project-specific | REVIEW — cloud deploy; project-scoped. Claude-user+Gemini. | medium |
| `insta-mcp` | `------` | stdio (node) | per-session-stdio | per-session | project-specific | KEEP project-scoped — repo-local dev server (source/repos/insta-mcp/.mcp.json), placeholder creds. Do NOT promote. | high |
| `mcp-graphql` | `--U-G-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | project-specific | REVIEW — GraphQL MCP bound to a local endpoint; project-scoped. Claude-user+Gemini. | medium |
| `postgres` | `--U---` | http/stdio(remote or npx) | per-session/remote | per-session/provider | project-specific | REVIEW — DB MCP; only for a repo with a Postgres target. Claude-user only; docker heavy. | medium |
| `sentry` | `--U-G-` | stdio | per-session-stdio | per-session | project-specific | REVIEW-SCOPE — observability SaaS; only useful in a repo wired to Sentry. Claude-user + Gemini. Make project-scoped, not always-on user. | medium |
| `angr` | `C-----` | sse | shared-daemon (:8760) | single shared SSE server | project-specific/experimental | REVIEW — in canonical ~/.mcp.json but NOT user-scope (never promoted) and backend DOWN; needs a health contract before it is durable | medium-high |
| `exa` | `---X-M` | stdio | per-session-stdio / remote | per-session | replaced-but-left-registered | KEEP for Codex (no search-hub there) / SUPERSEDED in Claude by search-hub. In ca_main(44) only. | high |
| `firecrawl` | `--UXGM` | stdio | per-session-stdio | per-session | replaced-but-left-registered | Claude: SUPERSEDED by search-hub (drift-in at user scope, not in ~/.mcp.json). Codex+Gemini: live direct route — KEEP there. | high |
| `github` | `--U-G-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | replaced-but-left-registered | REVIEW-PRUNE — remote Copilot MCP; redundant with github_cli+gh+github plugin. Codex ALREADY removed its [mcp_servers.github] (2026-07-13). Claude-user+Gemini still carry it. | medium |
| `tavily` | `--UXGM` | stdio | per-session-stdio | per-session | replaced-but-left-registered | Same as firecrawl: superseded in Claude by search-hub; live/kept in Codex+Gemini. | high |
| `agent-mail` | `C-UX--` | http | shared-daemon (:8812) | single shared server; designed for N agents | retained-for-distinct-capability | RETAIN — Layer-2 Claude<->Codex mingle channel; in canonical+claude+codex, absent from Gemini (expected) | high |
| `apktool-mcp` | `CRU--M` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — APK decode/build (needs apktool). Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `basic-memory` | `CRUX-M` | http | shared-daemon (:8765) | one shared server serves N sessions; SQLite write-contention risk under heavy concurrency | retained-for-distinct-capability | RETAIN — canonical semantic store; deployment must not hard-depend on it; Gemini uses a SEPARATE `memory` server (SSOT conflict, see divergences) | high |
| `binary-ninja-mcp` | `CRUxGM` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — needs BN backend :9009 (Personal=no headless). Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `biomni-hub` | `C-UX--` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — biomni (broker :18787). Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `cheatengine` | `CRUxGM` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — needs Cheat Engine GUI. Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `chrome-devtools` | `CRU-GM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — chrome (shared-catalog utility). | high |
| `cloud-hub` | `CRU--M` | stdio | per-session-hub (Python) | per-session child process; each aggregates many backends; N sessions = N heavy procs (RAM tax) | retained-for-distinct-capability | RETAIN — hub is Claude-canonical; Codex/Gemini deliberately use the raw exa/tavily/firecrawl providers instead (documented parity divergence, do NOT 'fix') | high |
| `codacy` | `--UXG-` | stdio | per-session-stdio | per-session | retained-for-distinct-capability | HOLD (do NOT prune on presence). Live in Claude-user + Codex(enabled=true) + Gemini; ABSENT from ~/.mcp.json & D:/Research (SSOT-orphan). Part of the documented Codacy/Sonar/DeepSource quality strategy (CLAUDE.md tool-routing). Its `plugin:local-mcp-bridge:codacy` twin is the RESURFACING route, disabled in every project scope. DECISION owed: add to canonical OR consciously retire the whole cloud-quality family for the local qlty+semgrep+CLI stack. | high |
| `context7` | `CRUXGM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — live docs (shared-catalog utility). | high |
| `cve-mcp` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — CVE intel. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `deepsource` | `--U-G-` | stdio (node wrapper) | per-session-stdio | per-session | retained-for-distinct-capability | PRUNE-LEANING but owner-gated. Claude-user + Gemini only, NO Codex parity (event ledger: Codex lane had no callable parity). SSOT-orphan; same plugin-bridge resurfacing. Weaker than codacy. | high |
| `deepwiki` | `CRUX-M` | http | remote | per-session/provider | retained-for-distinct-capability | RETAIN — repo wiki (remote) (shared-catalog utility). | high |
| `docker` | `CRUXGM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — containers (shared-catalog utility). | high |
| `elevenlabs` | `CRU--M` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — TTS (shared-catalog utility). | high |
| `excel` | `CRU-GM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — xlsx (shared-catalog utility). | high |
| `figma` | `CRU-GM` | http | remote | per-session/provider | retained-for-distinct-capability | RETAIN — figma (remote) (shared-catalog utility). | high |
| `frida-mcp` | `CRUxGM` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — needs frida-server. Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `ghidra-mcp` | `CRUxGM` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — needs Ghidra :8089. Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `github_cli` | `CRUxGM` | stdio | per-session-stdio | per-session | retained-for-distinct-capability | RETAIN (canonical). Provider divergence: Claude user+canonical ENABLED; Codex enabled=FALSE (de-duped vs github plugin+gh); Gemini enabled. Consider matching Codex's de-dup in Claude (loads both github + github_cli today). | high |
| `gitlab` | `CRU--M` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — gitlab (shared-catalog utility). | high |
| `hexstrike-ai` | `CRUxGM` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — security engagement backend :8888. Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `huggingface` | `CRU-GM` | http | remote | per-session/provider | retained-for-distinct-capability | RETAIN — HF (remote) (shared-catalog utility). | high |
| `ida-pro-mcp` | `CRUxGM` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — needs IDA :13337/:8745. Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `jadx-mcp` | `CRU--M` | stdio | external-backend | per-session child + shared external backend (single GUI/server; multi-session contends on the ONE backend) | retained-for-distinct-capability | RETAIN flip-on — needs jadx. Heavy/backend-gated; keep default-OFF per tree, enable on demand. | high |
| `markitdown` | `CRU--M` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — md convert (shared-catalog utility). | high |
| `node_repl` | `---X--` | stdio | codex-runtime-internal | per-session (Codex-owned) | retained-for-distinct-capability | KEEP — Codex CUA/browser runtime dependency, not a user MCP. Codex-only. | high |
| `ocr-suite` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — ABBYY OCR (D:). Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `openmm-md` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — MD (micromamba env). Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `paper-search` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — paper search. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `pdf-reader` | `CRU-GM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — pdf (shared-catalog utility). | high |
| `perplexity` | `CRU--M` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — web QA (shared-catalog utility). | high |
| `playwright` | `CRU-GM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — browser (shared-catalog utility). | high |
| `qdx-rush` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — QDX GPU QM. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `qlty` | `CRUX-M` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — local quality (shared-catalog utility). | high |
| `ralph-orchestrator` | `CRU-GM` | stdio | per-session-stdio | per-session child | retained-for-distinct-capability | RETAIN (canonical). Provider ADAPTER divergence: native Windows `ralph.exe` (Claude/canonical/D:Research) vs WSL `bash -lc ralph mcp serve` (Gemini). Valid per-provider lifecycle; document so it isn't churned. Ralph sessions ignore user-scope (project,local only). | high |
| `rdkit` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — cheminformatics. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `repomix` | `CRUXGM` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — repo pack (shared-catalog utility). | high |
| `scholarly-access` | `CRUX-M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — OA scholarly. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `schrodinger` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — needs Schrodinger license. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `search-hub` | `CRU--M` | stdio | per-session-hub (Python) | per-session child process; each aggregates many backends; N sessions = N heavy procs (RAM tax) | retained-for-distinct-capability | RETAIN — hub is Claude-canonical; Codex/Gemini deliberately use the raw exa/tavily/firecrawl providers instead (documented parity divergence, do NOT 'fix') | high |
| `searxng` | `CRU--M` | stdio | per-session-stdio | per-session/provider | retained-for-distinct-capability | RETAIN — meta-search (backend :8890) (shared-catalog utility). | high |
| `social-hub` | `CRU--M` | stdio | per-session-hub (Python) | per-session child process; each aggregates many backends; N sessions = N heavy procs (RAM tax) | retained-for-distinct-capability | RETAIN — hub is Claude-canonical; Codex/Gemini deliberately use the raw exa/tavily/firecrawl providers instead (documented parity divergence, do NOT 'fix') | high |
| `tooluniverse` | `CRU--M` | stdio | per-session-stdio | per-session child (heavy Python venv; N sessions = N× RAM) | retained-for-distinct-capability | RETAIN — life-science tools. Science/RE capability; candidate for project/flip-on scoping to cut RAM. | high |
| `codecov` | `--U-G-` | stdio | per-session-stdio | per-session | superseded-safe-to-disable | REVIEW-PRUNE — coverage SaaS; local .coverage-thresholds.json + qlty cover this. Claude-user + Gemini. | medium-high |
| `deepscan` | `--U---` | stdio (node) | per-session-stdio | per-session | superseded-safe-to-disable | REVIEW-PRUNE — JS/TS SaaS quality; redundant with local stack. Claude-user only. | medium |
| `figma-rest` | `-RU--M` | stdio | per-session-stdio | per-session | superseded-safe-to-disable | DROP — superseded by native `figma` MCP (owner already decided per basic-memory figma-seat note). Lives in D:/Research + user-scope + ca_main(44); NOT in ~/.mcp.json. | high |
| `kaggle` | `---x--` | stdio (py wrapper) | per-session-stdio | per-session | superseded-safe-to-disable | Codex-only, enabled=false; cloud-hub covers Kaggle for Claude. Keep disabled or fold into cloud-hub. | medium |
| `linear` | `--U-G-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | superseded-safe-to-disable | REVIEW-PRUNE — PM SaaS (remote http); unused in this workspace. Claude-user+Gemini; disabled in D:/Research/phenibut. | medium |
| `memory` | `----G-` | stdio | per-session-stdio | per-session | superseded-safe-to-disable | REVIEW-PRUNE — Gemini-only 2nd semantic-memory route (@mcp/server-memory -> ~/.gemini/memory.jsonl); CONFLICTS with basic-memory authority. Point Gemini at basic-memory or keep only if provably distinct. | medium-high |
| `meta-tool` | `--U---` | http/stdio(remote or npx) | per-session/remote | per-session/provider | superseded-safe-to-disable | REVIEW-SUPERSESSION — prior mcp-funnel/gateway artifact; qlty split out to its own server. Claude-user only; absent from current catalogs. | medium |
| `notion` | `--U-G-` | http/stdio(remote or npx) | per-session/remote | per-session/provider | superseded-safe-to-disable | REVIEW-PRUNE — PM SaaS (remote http); unused. Claude-user+Gemini. | medium |
| `semgrep` | `--UxG-` | stdio | per-session-stdio | per-session; RAM-heavy (osemgrep-pro ~920MB resident, MEMORY: ram_oom) | superseded-safe-to-disable | Claude: SUPERSEDED (RAM hog; prefer local opengrep/skill) → OFF/project-scope. Codex(off)+Gemini live. Known RAM-OOM contributor. | high |
| `sonarqube` | `--U-G-` | stdio (docker) | external-backend (docker) | per-session docker run; heavy | superseded-safe-to-disable | REVIEW-PRUNE — cloud-quality family; heavy (docker), redundant with local qlty+semgrep. Claude-user + Gemini; not Codex/canonical. | medium-high |

**Disposition-class tally:**
- retained-for-distinct-capability: 44
- superseded-safe-to-disable: 10
- project-specific: 7
- experimental: 4
- replaced-but-left-registered: 4
- project-specific/experimental: 1
- intentionally-restored: 1

---

## 8. Reconciliation ledger (verify, don't re-discover)

- **vs Codex `harness-mcp-scope-matrix-2026-07-13.csv`:** Confirmed the 69-row model + ca_main/ca_reconcile lineage (44 f406d95 / 43 8d2bc76). VERIFIED the two live columns directly (claude_home_project=~/.mcp.json, claude_research_project=D:/Research). ADDED what Codex couldn't: exact Codex enabled-set (25), full Gemini set (33), the plugin-bridge resurfacing mechanism (Codex called it 'unproven'), and live port health.
- **vs Axis-A `inventory-1.md`:** Verified every count (42/63/40) and the codacy/deepsource/playwright/cloud-hub claims against live disk. ADDED: the structured per-server matrix (topology/concurrency/statefulness/identity columns), the FIVE-representation SSOT map (inventory-1 named 2), the repo ca_main catalog staleness, exact Gemini fleet, and live health snapshot.
- **vs `AUDIT-DESIGN-CONVERGED.md`:** Aligned: resurfacing root cause = plugin-bridge at user scope; fix at plugin layer not .mcp.json; do not prune codacy/deepsource on redundancy alone.

---

## 9. Recommendations (FINDINGS ONLY — freeze)

1. Make ONE catalog authoritative-AND-current: update repo tools/mcp/canonical-mcp-servers.json to the reconciled 43 set, then deploy repo->~/.mcp.json (D2). Retire agent-self template + D:/Research copy.
2. ADD to canonical (intentional, currently SSOT-orphan): codex (fan-out rail); decide each of github/meta-tool/mcp-graphql/scrapegraph/sentry/postgres/linear/notion/digitalocean/browserstack/apify/claude-code-mcp (owner EVPI-gated).
3. PROMOTE angr to user-scope (canonical-only, missing) + give it a health contract (backend DOWN).
4. PRUNE decision on cloud-quality family (codacy/deepsource/sonarqube/codecov/deepscan) + firecrawl/tavily/figma-rest/semgrep — but at the PLUGIN-BRIDGE + user-scope layer (run promote -PruneExtraUserServers with Claude closed), NOT by editing .mcp.json. codacy/deepsource: HOLD until capability/cost owner-decision.
5. SCOPE: prefer USER scope for the canonical light set (drive-independent); keep RE/science/quality-heavy servers default-OFF per tree (flip-on) to cut the per-session-stdio RAM tax; keep insta-mcp/agent_handler project-scoped.
6. Add the write-guard (Axis-A Task 8 canonical_config_edit_guard, shadow-first) so claude mcp add / plugin installs / /mcp UI can't silently re-drift user or project scope.
7. Reconcile the 3 provider parity items (playwright args, cloud-hub Kaggle env, github/github_cli de-dup) and DOCUMENT the intentional hub-vs-raw + ralph-WSL + memory divergences so they aren't churned.

---

## 10. Confidence & open questions

**Confidence.** Divergence counts + membership + the resurfacing mechanism: **high (~95%)** — read directly from the live config files this session and triangulated with Axis-A + Codex. The keep/prune split of the 22 drift-ins: **medium** — owner-decision (EVPI-gated), not a silent bet. Liveness of stdio/remote servers: **low** (not probed; only local ports checked).

- Owner keep/prune verdict on the 22 user-scope drift-ins (EVPI-gated; especially the cloud-quality family + the misc SaaS extras).
- Is the `local-mcp-bridge` plugin still installed/active, or only residual as disabled twins? (plugin dir not found under ~/.claude this pass; twins persist in disabledMcpServers — likely residual, but confirm before relying on 'disabled = suppressed'.)
- Antigravity=2 taken from Axis-A count; the two entries were not enumerated this pass (~/.gemini/antigravity-cli/settings.json).
- Liveness of stdio/remote servers not probed (read-only); only local ports were checked. Several backends are DOWN (angr, searxng, ghidra, biomni-broker).