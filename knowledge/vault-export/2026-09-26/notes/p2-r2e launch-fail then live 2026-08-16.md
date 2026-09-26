---
title: p2-r2e launch-fail then live 2026-08-16
type: note
permalink: main/notes/p2-r2e-launch-fail-then-live-2026-08-16
tags:
- p2-r2e
- scaleway
- codex
- status
---

valid_as_of: 2026-08-16

Scaleway p2-r2e-codex (51.15.199.18, GP1-M) first wave burned ~130 units in 0.5s each with rc=2 / 0 bytes.

Root cause (two signals: 251B logs + `codex exec --help`):
1. r2e_loop.py passed `--ask-for-approval never` which Codex CLI 0.147 does not have.
2. Codex 0.147 ignores OPENAI_API_KEY env; needs `codex login --with-api-key` -> $CODEX_HOME/auth.json.

Fix: valid 0.147 argv (`--dangerously-bypass-approvals-and-sandbox`, stdin prompt), login with service key (sk-svcacct, HTTP 200 / gpt-5.6-sol present), preflight + fast-fail abort.

Verified live: PING-OK from gpt-5.6-sol; 16 units in flight; ground logs 16KB-941KB. Delivered still 0 — work just started.

Friendly status: python %USERPROFILE%\source\ast-integrate\command-center\p2-wave\p2_status.py
Do not type the raw events.ndjson.