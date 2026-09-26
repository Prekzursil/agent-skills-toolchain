---
name: Default to skill chains, not single-skill responses
description: For multi-step work, automatically use the prebuilt chain from chains.md
  instead of single skill invocations
type: feedback
permalink: main/claude-memory/downloads-swfoc-editor/feedback-workflow-chains
---

For any non-trivial task, default to running the full appropriate chain from `C:\Users\Prekzursil\Desktop\claude-cheatsheets\chains.md` rather than invoking a single skill.

**Why:** User finds it tedious to manually invoke skills repeatedly and explicitly asked for auto-chaining behavior. Project's CLAUDE.md mandates several gates anyway (design review, plan review, TDD, coverage, self-reflect) — chains bake those in.

**How to apply:**
- Bug fix → Chain B (systematic-debugging → TDD → fix → verify → commit)
- New feature → Chain A (full metaswarm pipeline)
- SWFOC RE task → Chain C (address hunting → CE → IDA → signature → modding → tests)
- Quality cleanup → Chain D
- Research → Chain E (search-first → docs → github → exa)
- Stuck → Chain F (codex delegation)

Only deviate when user explicitly says "skip the gates" or "just do X directly". Mandatory CLAUDE.md gates (coverage, lint, no suppressions) still run regardless.