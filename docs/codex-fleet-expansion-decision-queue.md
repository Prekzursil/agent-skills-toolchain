---
title: codex-fleet-expansion-decision-queue
type: note
permalink: dqverify-repo-20261013/docs/codex-fleet-expansion-decision-queue
---

# Codex Fleet Expansion + CI Parity Runner — Decision Queue

> **Source:** 9-agent ultracode research workflow (8 Opus lenses + synthesis), 2026-07-11, 0 errors, ~968K tokens.
> **Verified independently (Claude, before adopting):** `codex exec --dangerously-bypass-hook-trust`, `--json`, and `-o/--output-last-message` all exist in the live CLI (0.144.0) — the vendored-harness parity build is genuinely feasible. Fleet = **26 owned non-fork repos** (8 private + 18 public); forks (Stirling-PDF, ladybird, ToolUniverse, event-link, VirtualApp, BCSFE-Python, mcp-funnel, OmniVoice-Studio, …) excluded.
> **Status:** discovery + decide (NOT built). Preserves the deliberate security model (workflow_dispatch-only · env-passed inputs · propose-only · no fork-triggerable events).

## 1. Headline verdict
**Build it.** The parity runner is ~85% feasible, cheap, and mostly native Codex flags (`--dangerously-bypass-hook-trust` + the harness being pure-stdlib that degrades gracefully without basic-memory). The parity requirement **forces** the auth.json-in-Actions architecture: **Codex Cloud / the GitHub App is a managed black box** that strips secrets before the agent phase, runs no lifecycle hooks, and exposes no arbitrary secret-bearing MCPs — it structurally *cannot* carry the harness. So **keep auth.json-in-Actions; add the Cloud App only as a complementary secretless layer for public-repo `@codex review`.** Bill **sub-only by default with an engineered quota-guard**; flip the CI runner alone to a dedicated metered API key only if committing to a nightly full-fleet sweep at max reasoning, or on Plus/Pro-5x (the key isolates spend, it is **not** cheaper — credits map 1:1 to API prices). **Biggest single call: build a curated mirror, not a 1:1 clone** (7-MCP subset + ~20 skills + max-effort), and **fix the token-refresh write-back before scheduling anything**, or the fleet silently dies ~8 days after the secret was captured.

## 2. Cross-lens convergence (≥2 lenses agreed → highest confidence)
- **C1** Keep auth.json-in-Actions; do NOT route parity through Codex Cloud. (arch, parity, billing, sota) — Very High
- **C2** Curate the MCP set — never mirror all 15 (93-tool GitHub MCP ≈ 55k tokens/turn; auto-loading a target-repo's `.codex/config.toml` MCP = **CVE-2026-47751 RCE**). (parity, billing, reliability, sota) — Very High
- **C3** Token-refresh write-back MUST be fixed before scheduling (~8-day staleness; commented out today). (fleet, reliability, guardrails, billing) — Very High
- **C4** Serialized sweep, `max-parallel: 1` (one credential = one serial lane; parallel self-inflicts 429s + kills the token family). (fleet, billing, reliability) — Very High
- **C5** basic-memory + RE/GUI fleet cannot be mirrored — honest gaps, irrelevant to coding PRs. — Very High
- **C6** Propose-only draft PRs; distinct bot identity; owner can't self-approve. — Very High
- **C7** Scrub PAT from `.git/config` + independent gitleaks gate on the diff before PR. — High
- **C8** Curated ~20 skills, not the 271-vault (Codex ~8000-char skill-description budget silently drops the rest). — High
- **C9** Off-peak cron + skip-if-unchanged + `required=false` on every MCP. — High
- **C10** Model slug is churny → `model` an overridable input + safe default + live validation. — High

## 3. Tiered decision queue
### TIER-0 — just do it (existing runner, no parity needed)
0.1 Scrub PAT from `.git/config` after clone; re-supply inline only at push (H×L) — closes the #1 leak (danger-full-access Codex reads the PAT from the working tree).
0.2 `timeout-minutes` on job + `timeout <N>m` on `codex exec` (M×L, Native).
0.3 gitleaks gate on the staged diff before PR (H×L).
0.4 Wrap `codex exec` in a PTY (`script -qfc`) + assert an outcome (non-empty diff *or* explicit no-op; empty+silent = FAILED) (H×L) — fixes headless codex exit-0-empty.
0.5 Draft PR + auto-labels + owner-as-assignee (M×L).
0.6 `if: always()` cleanup (`rm -rf $CODEX_HOME`) (L×L).
0.7 JIT local re-seed wrapper (`gh secret set CODEX_AUTH_JSON < ~/.codex/auth.json` at dispatch) (H×L) — solves staleness for manual dispatch with zero new CI privilege.
0.8 Enable native Codex Cloud `@codex review` App on public repos (M-H×L, Native) — secretless; never wire into the auth.json workflow.
0.9 Inline diff-cap + forbidden-paths abort (deny `.github/workflows/**`, `**/*.pem`, `**/.env*`) (H×L).

### TIER-1 — core builds (sequenced)
1.1 Commit the parity payload: `ci/harness` (stdlib snapshot), `ci/codex-skill-allowlist.txt` (~20), `ci/mcp-servers.ci.toml` (7-MCP), `ci/AGENTS.ci.md` (H×L).
1.2 Parity config step: `config.toml` (`model_reasoning_effort="max"` + curated MCPs) + AGENTS.md → `$CODEX_HOME` + allowlisted skills → `$HOME/.agents/skills` + Linux `hooks.json` + `codex exec … --dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust` (H×M).
1.3 `required=false` + `startup_timeout_sec=30-60` on every MCP; gate basic-memory harness modules behind `HARNESS_CI=1` (H×L) — one MCP/hook failure must degrade, never abort.
1.4 Add secrets: `CONTEXT7_API_KEY`, `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, dedicated read-scoped `GITHUB_MCP_PAT` (≠ RUNNER_PAT) (H×L).
1.5 Refactor → reusable `_codex-core.yml` (`workflow_call`-only) + thin wrapper (H×M).
1.6 **Token-refresh write-back** for scheduled runs: new `CODEX_SECRETS_PAT` (host-repo **Secrets:write only**), `if: always()` re-store refreshed auth.json (H×M) — the correctness blocker; do NOT reuse RUNNER_PAT.
1.7 Fleet-sweep mode: `codex-sweep.yml` (schedule+dispatch) + `codex-targets.yml` + matrix builder + summarizer; `max-parallel:1`, `fail-fast:false`, off-peak cron, daily 1/7 shard, skip-if-unchanged, dedupe on open codex PR (H×M-H).
1.8 Token-keepalive workflow (trivial `codex exec` + write-back) (H×L) — insurance vs >8-day idle.
1.9 Top task templates: **T0 AGENTS.md bootstrap FIRST fleet-wide**, then docs-sync, coverage-backfill, CodeQL-remediation (private-repos-first) (H×L).

**Sequencing:** 1.1 → 1.2/1.3/1.4 → **pilot ONE repo w/ T0** → 1.5 → 1.6 → 1.7 → 1.8. Never enable the sweep before 1.6.

### TIER-2 — hardening (before public/fork-adjacent sweep)
2.1 Per-repo policy file (max-files/lines/forbidden-paths; momentstudio tight caps) · 2.2 CODEOWNERS + branch protection on momentstudio · 2.3 GitHub App token (fixes self-approval + shrinks blast radius) · 2.4 `requirements.toml` MCP allowlist + targets NOT "trusted projects" (CVE-2026-47751 defense) · 2.5 Egress allowlist (tension: likely needs `danger-full-access`→`workspace-write`) · 2.6 Prebuilt ghcr.io image · 2.7 Weekly-budget guard (reserve ≥40% for interactive) · 2.8 Per-run token ledger (`--json turn.completed` → $ → step summary) · 2.9 Hybrid metered-API branch (DEFER) · 2.10 Model-slug fallback chain + `effort` input · 2.11 Self-correcting test/lint loop.

### SKIP (weakens security or duplicates native tooling)
Parity via Codex Cloud · `pull_request_target`/fork triggers · widen RUNNER_PAT to Secrets/Workflows:write · commented write-back as-written · basic-memory in CI · RE/GUI MCPs · full 271-vault / 93-tool GitHub MCP · rebuild PR-review (native `@codex review` exists) · pure dep-bumps (Dependabot) · public-repo CodeQL (Copilot Autofix is free) · `max-parallel>1` · metered key as default.

## 4. Honest non-parity gaps
1. **basic-memory** — local daemon over the D: vault; CI instance is empty → no cross-project recall. Mitigate via task prompt + target AGENTS.md. Matters little for scoped PRs.
2. **RE/GUI fleet** — impossible headless; already off locally. No loss.
3. **Ledger/recall/checkpoints ephemeral** — by design; `secret_guard`+`claim_warning` still deliver in-run.
4. **Skills = curated subset** — consequence of the 8000-char budget; correct behavior, not literal 1:1.
5. **Capability parity ≠ effort-on-every-run** — max is *available*; running max on every nightly repo is quota-infeasible on Plus. Parity of capability, not of effort-applied-to-routine-sweeps.

## 5. First build wave + steering questions
**Wave 1 (parity runner + security floor):** TIER-0 quick wins (0.1-0.9) → commit parity payload (1.1) → parity config step (1.2-1.4) → **pilot ONE safe repo with T0 (AGENTS.md bootstrap)** — a doc-only diff exercising the whole pipeline at near-zero risk.
**Wave 2 (fleet mode, after pilot):** refactor (1.5) → token write-back w/ CODEX_SECRETS_PAT (1.6) → sweep on 3-4 repos (1.7) → keepalive (1.8) → scale to ~20.
**Wave 3 (hardening before public sweep):** policy file (2.1) → momentstudio protection (2.2) → CVE defenses (2.4) + egress decision (2.5).

**Steering (defaults in brackets):**
1. **ChatGPT plan tier** (Plus / Pro-5x / Pro-20x)? [Pro-20x → sub-only viable; Plus/5x → plan the metered branch for any cadence]
2. **Cadence** (manual / weekly / nightly-changed-only / nightly-full)? [start manual, then nightly-skip-if-unchanged ≤4 repos; NOT nightly-full]
3. **Effort policy for unattended sweeps** (max everywhere / max-manual + medium-sweep)? [max for human-dispatched hard tasks, medium+Terra for the sweep]
4. **PR author identity** (PAT now / GitHub App)? [PAT for pilot; GitHub App in Wave 2 — fixes solo-owner self-approval + shrinks blast radius]
5. **`danger-full-access` + egress** (keep / tighten to workspace-write + egress allowlist)? [keep for pilot; add MCP allowlist + `requirements.toml` + egress allowlist before the sweep touches public/fork-adjacent repos — CVE-2026-47751 class]