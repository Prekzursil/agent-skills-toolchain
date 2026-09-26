---
title: Autonomous Codex on GitHub - decision brief 2026-07-11
type: note
permalink: main/research/autonomous-codex-on-git-hub-decision-brief-2026-07-11
tags:
- research-report
- codex
- github-actions
- security
- autonomous-agents
- high-confidence
---

# Autonomous Codex on GitHub — decision brief 2026-07-11

Research (5-agent workflow) answering: how should the owner run autonomous Codex jobs on their GitHub repos (18 public + 8 private, on a ChatGPT sub, no API key, wants to avoid pay-per-token)?

## ⭐ Bottom line — the instinct flips
The owner's instinct (`auth.json`-in-Actions to reuse the sub) is **explicitly FORBIDDEN by OpenAI on public/open-source repos** ("Do not use this workflow for public or open-source repositories") — the secret is the **entire ChatGPT account session** and a fork PR can exfiltrate it. **Resolution: the Codex Cloud GitHub App** — runs server-side on the subscription, stores **NO repo secret** (fork-PR leak vector eliminated), still does hands-off work (`@codex` issue-fixes, auto PR reviews, opens PRs for review). Default it for ALL repos; keep `auth.json`-in-Actions only for the 8 private repos' custom `codex exec` pipelines; use a pay-per-token API key ONLY if heavy bot volume would starve interactive quota.

## Three paths
1. **auth.json-in-Actions** (sub billing): PUBLIC = **NO** (forbidden); high setup; secret = full account session; shares 5h/weekly window.
2. **API-key-in-Actions** (official `openai/codex-action`, SHA-pin it): pay-per-token (~$0.20–1.80/task); public = conditionally safe if hardened; **no sub/auth.json support**.
3. **Codex Cloud / GitHub App ⭐**: secretless (short-lived install tokens), sub-billed (Plus+ tier), **public-safe**, low setup, `@codex` + auto-review. THE recommended default.

## Public-repo trigger-safety matrix (for any secret-bearing agent)
- `pull_request` (fork): no secret → can't run agent. Safe but useless.
- **`pull_request_target` + fork checkout: DANGEROUS** — classic exfil, CVE-2025-61671 CVSS 9.3. NEVER.
- `issue_comment`/`issues`: safe ONLY if actor-gated to OWNER/MEMBER/COLLABORATOR (not CONTRIBUTOR/*[bot]).
- `workflow_dispatch`/`schedule`/`push`: write-access only → **trusted, best default**.
- + **Environment w/ required reviewers**: strongest single control, free on public repos.
Injection risk unique to agents: issue/PR text becomes the agent's instructions (Clinejection stole npm tokens; Copilot injection CVSS 9.6) → keep agent **propose-only, human-merge**, never auto-merge protected branches. Never self-hosted runners on public repos.

## Recommended for THIS fleet
- **PUBLIC active repos (storefront + MCPs) → Codex Cloud App ONLY.** No secret in public Actions. For custom sub-CI on a public repo: **private "control-repo" pattern** (private repo holds cred, checks out public via fine-grained PAT, opens PR back — forks never touch the secret; synthesis, MED-HIGH conf).
- **PRIVATE repos (8) → default to Codex Cloud App too**; reserve `auth.json`-in-Actions for genuine custom pipelines (base64 round-trip consistently; persist refreshed auth.json via `gh secret set` + PAT w/ `secrets:write`, else ~8-day token goes stale).
- **Storefront:** never auto-merge agent changes to checkout/payment/auth; branch protection + CODEOWNERS + human review.
- **Pilot:** one PRIVATE repo first, Codex Cloud App, turn on auto-reviews + one `@codex fix`, no secret/YAML, add CODEOWNERS. Private-first to watch quota burn + PR quality before flipping onto storefront/MCPs.

## Open decisions (to grill)
1. Pilot target — private repo first, or a low-value public MCP?
2. Storefront scope — agent touches payments repo (propose-only) or fenced out?
3. Quota vs isolation — accept Cloud jobs share the 5h/weekly window (a nightly ~26-repo sweep can starve daytime coding), or route heavy bot volume to a metered API key? (Only real reason to accept API billing.)
4. Custom-CI need — do the tasks fit Codex Cloud `@codex`, or need scheduled cron/custom pipelines (→ private control-repo or API-key Action)?

## Verify-live caveats (low-confidence)
- Model slug: under ChatGPT auth both `gpt-5.5` and `*-codex` variants may 400; pin a general non-`-codex` slug (`gpt-5.2` worked Mar-2026, churns by version/tier). Only affects the Actions paths.
- Codex Cloud on external fork PRs (public): auto-review may fall back to trusted-trigger behavior — verify in Codex settings.

## Live corroboration in the owner's own fleet
CodeQL (enabled same day, see [[Reframe fleet CodeQL default-setup enabled 2026-07-11]]) flagged **`quality-zero-platform`: 3× actions/untrusted-checkout + 1× actions/code-injection** and **`omniaudit-mcp`: missing-workflow-permissions** — the EXACT workflow-security class this brief warns about. Fix those as part of adopting safe autonomous workflows.
