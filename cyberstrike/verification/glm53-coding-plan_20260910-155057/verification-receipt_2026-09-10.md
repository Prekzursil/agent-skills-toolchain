---
title: verification-receipt_2026-09-10
type: note
permalink: dqverify-repo-20261013/cyberstrike/verification/glm53-coding-plan-20260910-155057/verification-receipt-2026-09-10
---

# GLM 5.3 Coding Plan compatibility check

Date: 10.09.2026
Provenance: disk-verified
Runtime result: FAILED-TO-GENERATE (subscription quota exhausted)

The user requested a check of GLM 5.3 using the Coding Plan rather than usage-based General API billing.

The current CyberStrike 1.1.16 configuration already has a Z.AI provider named zai. Its baseURL is https://api.z.ai/api/coding/paas/v4, the dedicated Coding Plan endpoint documented by Z.AI. Authentication resolves through the existing ZAI_API_KEY environment binding. The environment credential and stored zai credential match; no credential contents were printed or changed.

The local CyberStrike model catalog lists zai/glm-5.3. A separate zai-coding-plan provider name was not present in this installation; the existing zai provider has a Coding Plan endpoint override. The current default remains GPT-6 Astra with Daybreak as small_model.

## Bounded response probe

One harmless coding question was sent directly through the same configured Coding Plan endpoint and credential. Request model: glm-5.3. No tools or offensive task prompts were sent. Reasoning effort: low. Maximum output: 1024 tokens. General API fallback was not attempted.

At 2026-09-10T12:50:57.6808152Z, the service returned HTTP 429 with error 1310:
"Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-09-13 01:52:26"

No model-generated text or response-model identity was returned. Therefore this is evidence of a quota blocker, not a successful end-to-end CyberStrike model test, nor a test of how GLM handles previously refused requests.

## Independent account quota check

The read-only quota endpoint used by Z.AI's official usage-query plugin returned HTTP 200 and success=true.

- Short-period CREDIT_LIMIT: number 5, unit 3, allowance 28000, consumed 0, remaining 28000, percentage 0.
- Blocking CREDIT_LIMIT: number 1, unit 6, allowance 140000, consumed 140059, remaining 0, percentage 100.
- nextResetTime: 1789235546999 milliseconds since the Unix epoch.
- UTC reset: 2026-09-12T17:52:26.999Z.
- Europe/Bucharest reset: 2026-09-12T20:52:26.999+03:00.

The numeric timestamp resolves the timezone ambiguity in the inference error. The error's text clock is eight hours ahead of UTC; the Bucharest reset above is derived from the numeric timestamp, not a timezone guess.

## Evidence and limits

- coding-plan-response.json: sanitized inference response metadata, re-read as valid JSON.
- quota-readback.json: sanitized account quota metadata, re-read as valid JSON.
- Live config SHA256 before and after: 83744CF475451EBF125B8B30197FC019D1AFDC4EF4B574CD401BB4C205B648B9.
- Live CyberStrike configuration was unchanged.
- No server or autonomous CyberStrike workflow was launched.
- Successful model generation remains unverified because the subscription quota prevented inference.
- CyberStrike-specific official Coding Plan support was not established by the provider documentation; protocol compatibility and correct endpoint configuration are separate from vendor support status.

Sources:
https://docs.z.ai/guides/llm/glm-5.3
https://docs.z.ai/scenario-example/develop-tools/others
https://docs.z.ai/devpack/tool/opencode
https://docs.z.ai/api-reference/api-code
https://docs.z.ai/devpack/extension/usage-query-plugin
https://github.com/zai-org/zai-coding-plugins/blob/main/plugins/glm-plan-usage/skills/usage-query-skill/scripts/query-usage.mjs

UNIT-COMPLETE: check-glm53-coding-plan