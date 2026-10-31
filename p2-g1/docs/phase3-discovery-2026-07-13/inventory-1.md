
# MCP Config Divergence Map — READ-ONLY audit (2026-07-13)

All secrets referenced as `${VAR}` placeholders only; no secret values were read or printed. This is analysis only — nothing was mutated.

## 0. Sources inspected
| Layer | File | Server count | Role |
|---|---|---|---|
| **Canonical** | `C:/Users/Prekzursil/.mcp.json` | **42** | Hand-curated single source of truth (`mcpServers`) |
| **Live loaded (Claude user scope)** | `C:/Users/Prekzursil/.claude.json` → top-level `mcpServers` | **63** | What every normal session actually loads |
| **Codex** | `C:/Users/Prekzursil/.codex/config.toml` → `[mcp_servers.*]` | ~19 defined (heavy/RE `enabled=false`) | Codex parity port |
| **Stale mirror** | `D:/Research/.mcp.json` | **40** | Frozen OLD copy of canonical (divergent) |
| **Per-project** | `.../insta-mcp/.mcp.json`, `.../bilbo-app/.mcp.json` | 1 each | Legit repo-local dev servers |
| Promote mechanism | `~/.claude/hooks/mcp-userscope-sync/promote-mcp-userscope.ps1` | — | Manual canonical→user-scope promoter |
| Stale RAM-tier file | `~/.claude/.mcp-disabled-defaults.json` | — | Dated 2026-04-05, obsolete (see §6) |

Plugin-cache `.mcp.json` under `~/.claude/plugins/cache/**`, `~/.codex/.tmp/**`, and this session's `~/.claude/checkpoints/**/copies/` are marketplace/runtime artifacts — noise, not config sources; ignore.

---

## 1. Canonical vs Live (the core divergence): user scope has drifted +22, −1

**41 of 42 canonical servers ARE present in live user scope** (good). The drift is asymmetric:

### (a) In LIVE user scope but NOT in canonical — 22 drift-in servers
These loaded servers were never promoted from canonical; they were added directly to user scope (via `claude mcp add`, plugin install, or the old `local-mcp-bridge`) and never reconciled back:

- **Resurfaced/dropped code-quality family** (see §2): `codacy`, `deepsource`, `sonarqube`, `codecov`, `deepscan`
- **Explicitly removed-from-canonical in the 2026-07-13 reconcile** (superseded): `firecrawl`, `tavily` (→ superseded by `search-hub` rotator), `figma-rest` (→ superseded by official `figma` MCP), `semgrep` (RAM hog — kept as skill/opengrep only)
- **Legit-but-un-canonicalized** (need an owner keep/prune decision): `codex` (the mounted Codex fan-out MCP — intentional per CLAUDE.md, SHOULD be added to canonical), `github` (remote Copilot MCP / plugin), `meta-tool`, `mcp-graphql`, `scrapegraph`, `sentry`, `postgres`, `linear`, `notion`, `digitalocean`, `browserstack`, `apify`, `claude-code-mcp`

### (b) In canonical but NOT in live user scope — 1
- `angr` (SSE `http://127.0.0.1:8760/sse`) — added to canonical in the reconcile but never promoted (promote blocked-on-restart, see §7).

### (c) Stale values in live scope (promote hasn't run since reconcile)
Because `promote-mcp-userscope.ps1` has not been run since the 2026-07-13 canonical fixes, live user scope very likely still carries the **pre-fix** `playwright` (`playwright-mcp` instead of `@playwright/mcp`) and `cloud-hub` Kaggle env (`KAGGLE_API_TOKEN` instead of `KAGGLE_USERNAME`+`KAGGLE_KEY`). Canonical is fixed; the live loaded set is not.

---

## 2. Resurfaced dropped servers — codacy + deepsource (and the whole cloud-quality family)

**What resurfaced:** `codacy`, `deepsource`, `sonarqube`, `codecov`, `deepscan` are all live in user scope (top-level = enabled). `codacy` is ALSO `enabled=true` in `~/.codex/config.toml` (lines 460-465). They also appear as `plugin:local-mcp-bridge:codacy/deepsource/...` in per-project `disabledMcpServers`, i.e. two parallel representations.

**Why they were dropped (SOTA MCP strategy):** Code-quality is intentionally covered by the *local* stack — `qlty` MCP (kept in canonical) + `semgrep`/`opengrep` + local CLIs (`bandit`/`lizard`/`trivy`/`gitleaks`) — per `CLAUDE.md` → `guides/tool-routing-and-quality.md`. The cloud SaaS quality family (codacy/deepsource/sonarqube/codecov/deepscan/sentry) is redundant with that stack, requires cloud auth, and inflates the per-turn tool/token count (the "catalogue tax"). The Phase-3 consolidation note (`main/harness/phase-3-...-2026-07-13`) explicitly flags them: *"Resurfaced dropped MCPs (codacy, deepsource) — a prior session dropped them for a SOTA MCP strategy/skills; they came BACK → that harness mechanism may be broken."*

**Honesty gap:** I could NOT locate a dedicated standalone "SOTA-MCP-strategy" note in basic-memory by search — only the Phase-3 note that references it and the `guides/tool-routing-and-quality.md` pointer. That rationale doc is itself likely one of the "scattered forgotten harness docs" the Phase-3 program (thread 7) is trying to reconcile. Confidence the drop-rationale is *local-quality-supersedes-cloud*: **high (~85%)**, evidenced by canonical omission + qlty-in-canonical + the routing guide; confidence in the exact original wording: low (doc not found).

**Is the harness mechanism broken, or did it silently break?** Neither exactly — **it was never automatic or enforced.** The no-drift design is: canonical `~/.mcp.json` → *manual* `promote-mcp-userscope.ps1` → user scope. Its failure modes (all present here):
1. **Manual, not a hook** — it only runs when a human runs it; nothing re-syncs on drift.
2. **Additive by default** — `-PruneExtraUserServers` is OFF by default (script header line 44-47), so promote ADDS canonical entries but KEEPS pre-existing extras. codacy/deepsource were added to user scope, canonical was later pruned to drop them, but user scope was never re-promoted *with prune* → they survive.
3. **No write-guard** — nothing stops `claude mcp add` / plugin installs / the `/mcp` UI from writing servers into user or project scope, bypassing canonical.
4. **Blocked-on-restart** — a live session holds `~/.claude.json` in memory and rewrites it on exit, clobbering any external edit; promote must run with Claude fully CLOSED (script line 12-16). So the correcting prune keeps getting deferred.

The Phase-3 program's Task 8 (`canonical_config_edit_guard`, shadow-first) is the intended structural fix and is still pending.

---

## 3. Codex vs canonical divergence
- **Search stack differs by design:** Claude canonical uses the hub rotators (`search-hub`, `cloud-hub`, `social-hub`); Codex uses individual `exa` + `firecrawl` + `tavily` direct servers. Consistent *within* each tool but divergent *across* tools — a deliberate parity compromise, worth documenting as intentional so it isn't "fixed" by mistake.
- **codacy `enabled=true` in Codex too** — same resurfacing on the Codex side.
- **Kaggle:** Codex has a standalone `[mcp_servers.kaggle]` (`enabled=false`) using `env_vars=["KAGGLE_API_TOKEN"]`; unrelated to the canonical `cloud-hub` Kaggle fix, but the same OLD token-name style.
- `github_cli` `enabled=false` in Codex (de-duped in favor of `github` plugin) — this is the correct pattern that user scope should also adopt (currently user scope loads BOTH `github` and `github_cli`).

---

## 4. D:/Research divergence — a STALE FROZEN COPY of canonical
`D:/Research/.mcp.json` (40 servers) is an **older snapshot of `~/.mcp.json`**, not an independent config:
- Carries the **pre-reconcile bugs**: `playwright` → `playwright-mcp`, `cloud-hub` Kaggle env → `KAGGLE_API_TOKEN` (old), `figma-rest` still present.
- **Lacks the newer canonical additions**: `agent-mail`, `biomni-hub`, `angr`.
- It exists only because a session was launched from `D:\Research` and Claude's per-tree walk-up can't reach `C:\Users` from `D:\`. This is exactly the problem user-scope promotion was meant to eliminate. **It is superseded and should be deleted** (once the canonical set is promoted to user scope, no per-tree copy is needed on any drive).

Also note per-project `disabledMcpServers` curation under `D:/Research/projects/phenibut` etc. is legitimate RAM curation (keep), but references dead entities (`sci-hub`, `vultr`, `local-mcp-bridge`, `mcp-funnel` plugins) — stale, harmless.

---

## 5. Per-project servers — genuinely per-project (no migration needed)
- `insta-mcp/.mcp.json` → `insta-mcp` (`node dist/index.js`) — a repo-local dev server with placeholder creds; correctly per-project. Keep.
- `bilbo-app/.mcp.json` → `agent_handler` (perplexity agent-proxy via `mcp-remote`, empty `${AUTH_TOKEN}`) — repo-specific external; correctly per-project. Keep.

**There are NO custom project-scoped servers that belong in user scope.** The bulk of what looks like "project scope" in `.claude.json` is `disabledMcpServers` *curation* (the per-tree RAM-off list), which is correct to keep project-scoped. So task-(c)'s migration direction is effectively empty — the real work is the reverse: reconcile the 22 user-scope drift-ins (§1a) against canonical.

---

## 6. Why the "attempted sync" fails (root causes)
1. **Live-session clobber:** `~/.claude.json` is rewritten from memory on session exit → any promote done while a session is open is overwritten. Promote MUST run with all Claude closed.
2. **Additive promote + never-run prune:** default promote keeps extras; the prune (`-PruneExtraUserServers`) that would evict codacy/deepsource/etc has not been run.
3. **No enforcement layer:** `claude mcp add`, plugin installs, and the `/mcp` UI all write outside canonical, so drift re-accumulates between promotes.
4. **Stale tier file:** `~/.claude/.mcp-disabled-defaults.json` is dated **2026-04-05** and describes a retired architecture (Option-G `mcp-funnel` + `local-mcp-bridge`, `tavily`+`github_cli` as tier-1). It no longer matches reality and should be regenerated or retired.
5. **Multi-drive walk-up gap:** sessions on `D:\` can't see `C:\Users\...\.mcp.json`, which spawned the stale `D:/Research/.mcp.json` copy. User-scope promotion is the fix, but see (1)-(2).

---

## 7. Recommended single-source-of-truth architecture
1. **Canonical stays `~/.mcp.json`, versioned in the toolchain repo** (`agent-skills-toolchain`), so it's the one place every session/tool reads and it's diffable. (Aligns with Phase-3 thread 2-3.)
2. **Make canonical complete first:** decide per-server on the 13 "legit-but-un-canonicalized" drift-ins (§1a) — ADD the keepers (`codex`, `github`, `meta-tool`, `mcp-graphql`, `scrapegraph`, and any of sentry/postgres/linear/notion/digitalocean/browserstack/apify/claude-code-mcp the owner actually uses) to canonical; leave the rest for pruning.
3. **Promote with prune, Claude closed:** run `promote-mcp-userscope.ps1 -PruneExtraUserServers -Yes` after a full restart so user scope becomes EXACTLY canonical (adds `angr`, evicts the dropped cloud-quality family + firecrawl/tavily/figma-rest/semgrep). This also lands the pending playwright + cloud-hub Kaggle fixes into live scope.
4. **Delete `D:/Research/.mcp.json`** (and any other per-tree copies) — user scope makes them redundant and they only re-introduce drift on `D:\`.
5. **Add the write-guard (Phase-3 Task 8):** a shadow-first `canonical_config_edit_guard` PreToolUse gate that flags any server added outside `~/.mcp.json`, plus a periodic drift-audit that diffs live user scope vs canonical and reports extras. This is what converts "manual, un-enforced, re-drifts" into "self-healing."
6. **Codex parity:** disable `codacy` in `~/.codex/config.toml`; keep the intentional exa/firecrawl/tavily-vs-hub divergence documented as a known parity choice so it isn't churned.
7. **Regenerate or retire `~/.claude/.mcp-disabled-defaults.json`** to match the current set (RAM-heavy servers to default-off per tree), or delete it if the tiering is now handled elsewhere.

---

## 8. User-scope reconcile candidate list (actionable)

**PRUNE from user scope (superseded/dropped — do NOT add to canonical):**
`codacy`, `deepsource`, `sonarqube`, `codecov`, `deepscan` (cloud quality → qlty+semgrep+local skills), `firecrawl`, `tavily` (→ search-hub), `figma-rest` (→ figma MCP), `semgrep` (RAM hog → opengrep/skill).

**PROMOTE to canonical then keep (owner-confirm each):**
`codex` (fan-out MCP — clearly intentional), `github`, `meta-tool`, `mcp-graphql`, `scrapegraph`, and any actually-used of `sentry`, `postgres`, `linear`, `notion`, `digitalocean`, `browserstack`, `apify`, `claude-code-mcp`.

**ADD to user scope (canonical-only, currently missing):** `angr`.

**Project → user migration:** none required (`insta-mcp`, `bilbo-app/agent_handler` are genuinely per-project).

**Delete:** `D:/Research/.mcp.json` (stale mirror).

Confidence on the divergence counts and membership: **high (~95%)** — read directly from the four config files this session. Confidence on the "keep vs prune" split of the 13 legit drift-ins: **medium** — these need an owner decision (EVPI-gated), not a silent bet.

