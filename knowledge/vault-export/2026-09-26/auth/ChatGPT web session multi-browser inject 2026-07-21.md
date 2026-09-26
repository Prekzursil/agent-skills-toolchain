---
title: ChatGPT web session multi-browser inject 2026-07-21
type: note
permalink: main/auth/chat-gpt-web-session-multi-browser-inject-2026-07-21
tags:
- chatgpt
- cookies
- phone-bridge
- chrome
- edge
- comet
- firefox
---

# ChatGPT web session multi-browser inject (2026-07-21)

## Result
Phone-extracted NextAuth cookies injected into **main** profiles:
- Chrome Default (Prekzursil / Your Chrome) — WEB_SESSION_OK
- Edge Default — WEB_SESSION_OK
- Comet Default (Prekzursil) — WEB_SESSION_OK
- Firefox default-release — WEB_SESSION_OK

## Reapply
```
python %USERPROFILE%\.crcp\cookie-bridge\inject_all_main_profiles.py
python -m crcp auth broker --from-phone-store
```

## Secrets (never commit)
- Phone store: `~/.crcp/cookie-bridge/chatgpt_cookies.json`
- Codex OAuth: `~/.codex/auth.json`
- Okta password: human IdP only — not in repo

## Docs in toolchain
`tools/crcp/reports/auth_estate_inventory_2026-07-21.md`
