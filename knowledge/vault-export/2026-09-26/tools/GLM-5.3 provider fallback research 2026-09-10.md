---
title: GLM-5.3 provider fallback research 2026-09-10
type: note
permalink: main/tools/glm-5.3-provider-fallback-research-2026-09-10
tags:
- cyberstrike
- glm-5.3
- providers
- pricing
---

# GLM-5.3 provider fallback research 2026-09-10

- [decision] Keep CyberStrike on `zai-model-api/glm-5.3` for the current Coding Plan quota gap. The separately purchased Z.AI Model API bundle returned HTTP 200 in a direct test; the Coding Plan quota error is tied to a different endpoint.
- [decision] Preferred external fallback order is Vercel AI Gateway, Sail Research, then the already registered OpenRouter route.
- [fact] Vercel publishes $5 every 30 days for eligible free-tier teams and full `zai/glm-5.3`; its catalog currently reports prices from $0.70 input and $2.20 output per million, but explicit cost sorting is required to target the cheapest provider.
- [fact] Sail publishes $5 monthly after attaching a payment method. Full `zai-org/GLM-5.3` is $0.98/$3.08 ASAP, $0.50/$2.50 Balanced, and $0.40/$1.80 Flex per million input/output; Flex requires background Responses or Batch for reliable use.
- [fact] TokenRouter's current catalog lists `z-ai/glm-5.3-free` at zero price, while its launch post says the free period ended 04.09.2026. Treat it as an authenticated-probe candidate, not dependable capacity.
- [fact] Research receipt is `C:/Users/Prekzursil/.config/cyberstrike/verification/glm53-provider-options_2026-09-10_1708.md`, SHA-256 `500C4C69E5081B761C8BC33687C12BD7B93885EC6E1F511AECD34D4C30919BBA`.

- relates_to [[CyberStrike default GLM-5.3 and Codex invoke 2026-09-02]]
- relates_to [[CyberStrike GPT-6 Astra primary and Daybreak helper 2026-09-07]]