---
title: Workspace hygiene audit + resolution 2026-07-03
type: note
permalink: main/projects/workspace-hygiene-audit-resolution-2026-07-03
tags:
- hygiene
- audit
- cloud-spend
- security
- hooks
- preservation
- tier-d
---

2026-07-03 workspace hygiene sweep (read-only) + fixes. Full record: `~/.claude/harness-gemhunt-2026-07-03/HYGIENE-AUDIT.md`.

**Cloud spend — VERIFIED read-only (mostly clean):**
- GCE VM (feared hourly-biller) = **GONE**: `gcloud compute instances list --project peak-emitter-443615-d5` → 0 instances (SSH artifacts were stale leftovers).
- OCI social-mcp-deploy trigger = **never billed** ($0; VM never provisioned).
- Azure = student sub (`@s.unibuc.ro`), credit-capped, ~$0.
- **momentstudio.ro = LIVE** (HTTP 200) — the only real recurring spend; who-pays is the USER's call.

**🔴 SECURITY (USER must act):** `C:\Users\Prekzursil\Downloads\AdrianaArt(momentstudio)…\Netopia\live.private.key` + PayPal/Stripe/password txt = unencrypted LIVE payment keys → ROTATE + move to secrets manager. (Flagged, NOT touched.)

**Preservation done:** both toolchain feat branches pushed; 4 single-copy MCP repos vendored into the toolchain (see [[MCP fleet expansion 2026-07-03]]).

**social-mcp-deploy:** re-scoped — proxy (Byteful, already wired into fb FB_DM_PROXY + tiktok TIKTOK_PROXY) is integrated; in-folder README + secret-backup gate written; retire folder only AFTER user backs up the 4 single-copy secrets.

**TIER-D hook drift — RESOLVED (commit 8253df8):** live `~/.claude/hooks` had drifted from 3 repo copies. 2 deploy scripts: `sync-hooks.ps1`←`<repo>/hooks/` (lacks these 4), `sync-self.ps1`←`agent-self/config/hooks`. Per-file: **inquisitiveness/prompt-guard.py** (live-ahead: TU-router + CS-safety gating) + **event-ledger/ledger.py** (live-ahead: _get_projid/_legacy_slug) BACK-PORTED live→repo (re-template {{USER_HOME}}, ruff-clean, verified by each hook's own runner 13/13 + PASS; LIVE never written). anti-degen/goal-reinject = formatting-only, left as-is. ⭐ LESSON: harness-hook drift is a per-file TEMPLATE-vs-RENDERED merge (repo uses {{USER_HOME}}) with MIXED direction — a blind one-way snapshot LOSES work; check per-file direction + write-repo-only to never risk the running session.

**Pending USER:** rotate keys · momentstudio who-pays · GitLab PAT · Figma seat · FB `fr` cookie. **Pending follow-up:** MCP cutover (restart-gated) · basic-memory reliability · optional PR feat/cloud-hub-mcp→main.