---
title: research Cursor effort cap cannot be changed by this seat 2026-08-28
type: report
permalink: main/research/research-cursor-effort-cap-cannot-be-changed-by-this-seat-2026-08-28
status: active
valid_as_of: '2026-08-28'
---

# research Cursor effort cap cannot be changed by this seat 2026-08-28

- [fact] Live `GetTeamAdminSettings` (desktop session JWT) confirms custom `modelAllowlist` with 17 models whose effort/reasoning `allowedValues` stop at the old catalog top (Claude low/med/high; GPT extra-high/max blocked). `newModelDefault`/`newProviderDefault` are ENABLED. `newChatNudgeAllToSmartAuto` still true/balanced.
- [fact] This seat is `TEAM_ROLE_MEMBER`, `isTeamAdmin: false`. `UpdateTeamAdminSettings` and `UpdateTeamSmartAutoSettings` return 401 ERROR_NOT_LOGGED_IN (plain JWT, checksum, and exchanged API-key JWT). Official `/teams/model-access` PUT still 401 Invalid Team API Key.
- [fact] Six Cursor TEAM_ROLE_OWNER accounts can change it: bartosz.janota, marat.saddarov, vadim.kravchenko, services@, toomas, jevgeni.smirnov @bolt.eu. No TEAM_ROLE_ADMIN in 1911 members.
- [fact] Team shared-chat harvest (181, 24.08.2026) has zero chats from those owners. It does show Bolt used the same admin dashboard: Amruth 22.05.2026 plugin lockdown (`allowUserLocalPluginImports: false` the previous evening) and Kevin's sandboxing-forced chat. No harvest chat covers the 18.08 effort cap.
- [decision] Do not locally patch `adminSettings.cached` — server refresh overwrites. Ask an owner to clear parameter restrictions (or unrestricted) on Models; optional disable Auto nudge.
- relates_to [[research Cursor effort restrictions vs user API key 2026-08-28]]
- relates_to [[research CURSOR_API_TOKEN full options tree 2026-08-28]]

Receipt: `C:/Users/Prekzursil/Cowork/output/cursor-effort-change-attempt_2026-08-28.md`