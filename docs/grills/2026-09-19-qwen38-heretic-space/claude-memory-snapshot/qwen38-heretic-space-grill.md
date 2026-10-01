---
name: qwen38-heretic-space-grill
description: "Extensive grill (2026-09-19) on the user's private HF Space Prekzursil/qwen38-27b-heretic-chat — 11 decisions made, waiting on a review workflow before converging; where everything is saved"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca9aa7a4-16ad-4e9d-bafe-00eed0171063
  modified: 2026-09-23T05:17:40.102Z
---

Grill about the user's private Hugging Face Space `Prekzursil/qwen38-27b-heretic-chat`. Everything durable is in
`/home/codespace/grills/2026-09-19-qwen38-heretic-space/`: `DECISION-QUEUE.md` (queue, **Resolved decisions**, lens/scout/workflow
digests, evidence index) and `evidence/` (verbatim subagent reports under `reports/`, `workflow-findings.md`, scout briefs). Read the
"Resolved decisions" section first when resuming.

Decided by the user on 2026-09-19 (several against Claude's recommendation): both agents write · GitHub repo as source of truth with
CI as the ONLY production writer + private staging Space + canary · production stays DOWN until the pipeline promotes a build ·
**everything ships in one production release** (integrated incrementally on staging) · hosted inference first (featherless-ai via the
HF router), ZeroGPU only as fallback · CPU-only UI/API Space + one ZeroGPU worker Space with one resident model · purpose = workbench
AND agent gateway equally · curated evidence-gated `models.yaml` (12-prompt harness gate) · `python_eval` stays in-container, hardened
(child env allowlist + parent `prctl(PR_SET_DUMPABLE,0)` + rlimits + operator flag; no upload token in the app) · personas: neutral
set, cleaned, which Claude improves and extends (Claude does not write one persona clause it declined on ethical grounds — flagged for safety review; see DECISION-QUEUE G-19) · work split: Claude = platform (pipeline, core split, backends, gateway/MCP, tool-call reliability, hardening, eval harness),
the other agent = product (UI, vision/video, persona wiring, docs, worker loading experiments).

**Why:** the Space was down, another AI agent was pushing broken, over-claimed commits to production with no gate, and the user wants
a maximal multi-model "SOTA" Space; they chose to decide deliberately before any build.
**How to apply:** nothing is built or pushed until the grill converges; the user explicitly said NOT to converge before review
workflow `wf_f47ecf9e-916` finishes and to keep every subagent's full output (saved verbatim — never rely on digests alone). Remaining
steps: re-export workflow findings when it completes, fold in the retried simplification lens, write the final decision log with
defaults listed for veto, write the hand-off brief for the other agent, then plan. Verify the Space's HEAD/running sha before acting;
it was changing minute to minute. Never store or reuse token values; the user was advised to revoke the token pasted in chat.

Related: [[toolchain-skills-not-registered-here]], [[user-prefers-grill-before-build]], [[dangling-reference-means-dropped-paste]]
