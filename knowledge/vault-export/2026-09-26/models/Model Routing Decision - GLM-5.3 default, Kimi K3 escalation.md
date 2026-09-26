---
title: Model Routing Decision - GLM-5.3 default, Kimi K3 escalation
type: note
permalink: main/models/model-routing-decision-glm-5.3-default-kimi-k3-escalation
tags:
- decision
- model-routing
- glm-5.3
- kimi-k3
- clinepass
---

# Model Routing Decision - GLM-5.3 default, Kimi K3 escalation-only (23.09.2026)

- [decision] GLM-5.3 (1M ctx) is the default model for all owner workload classes (research-synthesis, security-enum, infra, coding). Kimi K3 is escalation-only: reasoning-quality failures (2 failed fixes / 3 tool-loop retries) and submission-critical phenibut synthesis turns. Context >180k is NO LONGER a Kimi trigger (both models are 1M).
- [fact] ClinePass (.99/mo, active) includes both cline-pass/glm-5.3 and cline-pass/kimi-k3, quota-metered (5h/weekly/monthly), totalCost: 0 observed (~1.7M input tokens = ). Kimi burns quota ~2.1-3.4x faster than GLM-5.3 per reference prices.
- [fact] Latest 12-session inventory: research-synthesis = 73% of bytes (phenibut 258 MB, 774k peak input, 52 compactions on glm-5.3[1m] + claude-opus-5 passes); headless lanes die on quota/OAuth exhaustion, never model failure.
- [decision] Small automation (probes, chunked writes, canary fleets) routes to GLM-5.3-Flash / glm-free-shim lane, never subscription quotas.

Evidence: [[model-router-analysis_2026-09-23]] artifacts at C:/Users/Prekzursil/model-router-analysis_2026-09-23/. Related: [[phenibut]] [[clinepass]] [[glm-5.3]] [[kimi-k3]]
