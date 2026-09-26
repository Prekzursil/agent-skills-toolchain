---
title: CyberStrike GPT-6 Astra primary and Daybreak helper 2026-09-07
type: config
permalink: main/tools/cyber-strike-gpt-6-astra-primary-and-daybreak-helper-2026-09-07
tags:
- cyberstrike
- openai
- gpt-6
- daybreak
- model-routing
---

# CyberStrike GPT-6 Astra primary and Daybreak helper

- [decision] CyberStrike now uses `openai/gpt-6.0-astra` as its main selector, mapped to the exact OpenAI wire id `gpt-6-astra`.
- [decision] CyberStrike now uses `openai/gpt-5.6-daybreak-blue-latest` as `small_model`, mapped to `gpt-daybreak-blue-latest`.
- [fact] OpenAI currently maps Daybreak Blue to `gpt-5.6-sol`; current OpenAI guidance says Astra does not support Daybreak reduced-refusal mode for most customers. A combined GPT-6 Daybreak wire id is not exposed.
- [fact] CyberStrike 1.1.16 needs visible version-shaped aliases for these ChatGPT OAuth models; provider `id` fields preserve the exact wire ids.
- [fact] Live attached CyberStrike probes returned `GPT6_CYBERSTRIKE_OK` and `DAYBREAK_CYBERSTRIKE_OK`, both with exit 0, empty stderr, and zero session errors.
- [fact] CyberStrike's stale OpenAI OAuth entry first returned `token_expired`. The active canonical Codex ChatGPT session was reused with a timestamped backup; token contents were never printed and no credential was rotated.
- [fact] The disk-verified receipt is at `C:/Users/Prekzursil/Cowork/private/cyberstrike-engagements/daybreak-wire-2026-09-07-2250/verification-receipt_2026-09-07.md`.
- [fact] The temporary server tree was stopped after testing; port 4097 and all 50 original tree processes were absent on re-check.

Related: [[CyberStrike AI providers 2026-09-02]]