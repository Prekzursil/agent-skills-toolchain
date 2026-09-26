---
title: qwythos pattern-driven consultation recipe 2026-09-04
type: note
permalink: main/decisions/qwythos-pattern-driven-consultation-recipe-2026-09-04
tags:
- qwythos
- fabric-patterns
- consultation
- recipe
---

# qwythos pattern-driven consultation recipe 2026-09-04

- [fact] The Modal Qwythos H100 endpoint (`main/decisions/qwythos-9b-modal-h100-deployment-2026-09-04`) works as a pattern-driven advisor over the estate's fabric pattern library (256 patterns at `C:\Users\Prekzursil\.config\fabric\patterns`, each with `system.md`).
- [fact] Working recipe: (1) list all 256 pattern names in the prompt as catalog (~2K tokens); (2) inline the `system.md` of the 3-4 patterns relevant to the question (~1.2K chars each, truncated); (3) instruct explicit pattern-labeled sections; (4) **max_tokens ≥ 8-16K** — the model spends 600-3000 tokens on reasoning before content, a 3K budget dies with finish_reason=length mid-first-section.
- [fact] Verified live on the AWS credential question: produced a full STRIDE threat model (create_stride_threat_model), 8 secure-by-design gating questions (ask_secure_by_design_questions), risk scoring (analyze_risk: colleague-credential approach = High, own-SSO = Low), and two failure scenarios with detection paths (create_threat_scenarios) — consistent with the agent's held position and the earlier independent consultation.

Related: [[qwythos-9b modal h100 deployment 2026-09-04]], [[incident-agents-md-policy-inversion-forensic-attribution-2026-09-03-1]].