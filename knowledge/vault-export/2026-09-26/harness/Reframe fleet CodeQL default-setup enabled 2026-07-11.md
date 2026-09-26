---
title: Reframe fleet CodeQL default-setup enabled 2026-07-11
type: note
permalink: main/harness/reframe-fleet-code-ql-default-setup-enabled-2026-07-11
tags:
- github
- codeql
- fleet
- security
- default-setup
---

# Fleet CodeQL default-setup enabled 2026-07-11

Owner decided (grill: ambition = "targeted default-setup", scope = "Core 6 + 3 borderline") to enable **free default CodeQL** on the active/input-handling public repos only — NOT advanced setup, NOT blanket, NOT the paid-GHAS private repos.

## Enabled (10 total, all verified `state=configured`)
Reframe (already on) + newly enabled via `gh api --method PATCH repos/Prekzursil/<repo>/code-scanning/default-setup -f state=configured -f query_suite=default`:
momentstudio (payments/storefront), omniaudit-mcp, abbyy-finereader-ocr-mcp (MCP servers), env-inspector (secrets), quality-zero-platform (GitHub governance), DevExtreme-Filter-Go-Language (Go backend), codex-session-manager, bilbo-app, WebCoder.

## Deliberately skipped
- 8 PRIVATE repos — CodeQL needs paid GitHub Advanced Security (403 "code scanning not enabled"); not worth it for personal projects.
- Toy/course/game/scraper public repos (Airline-Reservations, Personal-Finance course project, the two save-game/mod editors, TanksFlashMobile, pbinfo-scrape, grace-iberlef NLP, codeblocks-packager) — ~zero attack surface.

## Key API gotcha
Enabling default-setup is **PATCH**, not PUT (PUT → 404 "Not Found"). Response returns a `run_id` (the initial scan). GET works for reading `.state`.

## Advanced CodeQL — decided NOT needed (see [[Reframe issues #264 #265 resolved 2026-07-11]])
Advanced setup's only real payoff = custom sanitizer models to make FP-classes (e.g. Reframe's keystore path-injection) recognized instead of dismissed. Proven not worth the per-repo maintenance for a personal fleet; default-setup is free + zero-maintenance. Reframe stays default + keeps its FP dismissals.

Related open thread: autonomous Codex-on-GitHub jobs (auth.json-in-Actions vs API key vs Codex cloud) — under research; the public-repo secret-exposure constraint is the crux.
