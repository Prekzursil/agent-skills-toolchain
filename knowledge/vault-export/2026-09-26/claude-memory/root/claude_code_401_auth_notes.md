---
name: Claude Code 401 auth errors and prevention
description: Why mariusvisalon70@gmail.com's Max-plan Claude Code intermittently throws
  401 "Invalid authentication credentials" and how to mitigate
type: project
originSessionId: 174a3e5e-8ec8-4b41-8953-de3f1a677d12
permalink: main/claude-memory/root/claude-code-401-auth-notes
---

User account `mariusvisalon70@gmail.com` is on **Max plan via Google Play subscription** (`billingType: google_play_subscription`, `subscriptionType: max`). OAuth credentials live in `~/.claude/.credentials.json` (`claudeAiOauth.{accessToken, refreshToken, expiresAt, scopes, subscriptionType, rateLimitTier}`).

**Why 401s happen even when the cached token is valid:**
- `~/.claude/.credentials.json` is **shared across all running Claude Code instances on this machine**. When one instance hits its refresh window and rewrites the file, another instance can race the rewrite, send an API call with a token the server has already invalidated, and receive 401.
- Google Play subscriptions add an extra refresh hop (Anthropic verifies via Play receipt validation) which slightly widens the race window vs direct Anthropic billing.
- `passesEligibilityCache` showing `eligible: false` is misleading — that field is for a referral-promo program, NOT API access. Don't treat it as a 401 cause.
- `hasAvailableSubscription: false` at the top level is similarly cached/stale and is not the live API access gate.

**Mitigations (ordered by effectiveness):**
1. **Reduce concurrent Claude Code instances.** When you must run several, expect occasional 401s on the loser of a refresh race; `/login` resolves them instantly.
2. **Run `/login`** when 401 happens — re-runs OAuth, gets fresh access+refresh pair, writes a clean `.credentials.json`. This is the standard recovery and the user has been doing it correctly.
3. **Hard reset path** if `/login` doesn't help: delete `~/.claude/.credentials.json` and re-authenticate. Equivalent to a full re-login, useful if `.credentials.json` got corrupted by a partial refresh.
4. **Don't switch to `ANTHROPIC_API_KEY` env var auth** unless you want pay-per-use API billing instead of the Max plan; that auth path bypasses the subscription entirely.

**What does NOT help:**
- Editing `passesEligibilityCache`, `overageCreditGrantCache`, or `hasAvailableSubscription` — these are server-driven caches.
- Restarting Claude Code without `/login` — it will reuse the same potentially-stale token from `.credentials.json`.
- Network-level interventions — the 401 is auth, not connectivity.

**How to diagnose a 401 quickly:**
```powershell
$cred = Get-Content ~/.claude/.credentials.json -Raw | ConvertFrom-Json
$exp = [DateTimeOffset]::FromUnixTimeMilliseconds([int64]$cred.claudeAiOauth.expiresAt)
"expiresAt: $exp ($([math]::Round(($exp - [DateTimeOffset]::UtcNow).TotalHours, 1)) hours from now)"
"subscriptionType: $($cred.claudeAiOauth.subscriptionType)"
```
If `subscriptionType` is `max` and `expiresAt` is in the future and you're still 401ing, it's almost certainly a refresh race — just `/login`.