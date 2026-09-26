---
title: OpenAI Trusted Access jailbreak wiring 2026-09-10
type: config
permalink: main/tools/open-ai-trusted-access-jailbreak-wiring-2026-09-10
status: active
valid_as_of: '2026-09-10'
tags:
- cyberstrike
- jailbreak
- daybreak
- gpt-6
- trusted-access
- codex
---

# OpenAI Trusted Access jailbreak wiring 2026-09-10

- [fact] The ChatGPT/Codex overlay "This content can't be shown / Trusted Access / chatgpt.com/cyber" is a product-level output classifier. Op-wrapper and DAN cannot clear it.
- [fact] OpenAI: reduced refusals are not available on Astra for most Daybreak customers. Daybreak Blue is `gpt-daybreak-blue-latest` mapped to `gpt-5.6-sol`. Daybreak Red is `gpt-daybreak-red-latest` mapped to `gpt-5.6-cyber` and needs separate approval.
- [fact] This account's Codex models_cache listed Daybreak Blue and did not list Daybreak Red or gpt-5.6-cyber on 10.09.2026 (blue_hits=1, red_hits=0).
- [decision] Never use GPT-6 Astra as the cyber brain. OpenAI cyber path is Daybreak Blue. Overlay on Blue pivots off OpenAI (NVIDIA NIM / GLM / abliterated).
- [decision] Codex profiles `cyber` (Daybreak high) and `glm-cyber` (OpenRouter GLM) are the launch knobs. Default Codex model was already Daybreak Blue.
- [fact] CyberStrike live default on 10.09.2026 is `nvidia/moonshotai/kimi-k3` (concurrent NIM switch); that path does not hit OpenAI Trusted Access.
- [fact] chatgpt.com/cyber in the debug Chrome profile was logged out. Apply page requires government ID and Advanced Account Security with two hardware keys. Owner-account approval status NOT-CHECKED.
- [fact] Disk receipt: `C:/Users/Prekzursil/.config/cyberstrike/verification/jailbreak-trusted-access_2026-09-10.md`
- relates_to [[CyberStrike GPT-6 Astra primary and Daybreak helper 2026-09-07]]
See also [[jailbreak]].
