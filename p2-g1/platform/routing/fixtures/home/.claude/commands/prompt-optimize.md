---
description: Analyze a draft prompt and output an optimized, ECC-enriched version ready to paste and run. Does NOT execute the task — outputs advisory analysis only.
---

# /prompt-optimize

Analyze and optimize the following prompt for maximum ECC leverage.

## Your Task

Apply the **prompt-optimizer** skill to the user's input below. Follow the 6-phase analysis pipeline:

0. **Project Detection** — Read CLAUDE.md, detect tech stack from project files (package.json, go.mod, pyproject.toml, etc.)
1. **Intent Detection** — Classify the task type (new feature, bug fix, refactor, research, testing, review, documentation, infrastructure, design)
2. **Scope Assessment** — Evaluate complexity (TRIVIAL / LOW / MEDIUM / HIGH / EPIC), using codebase size as signal if detected
3. **ECC Component Matching** — Map to specific skills, commands, agents, and model tier
4. **Missing Context Detection** — Identify gaps. If 3+ critical items missing, ask the user to clarify before generating
5. **Workflow & Model** — Determine lifecycle position, recommend model tier, and split into multiple prompts if HIGH/EPIC
