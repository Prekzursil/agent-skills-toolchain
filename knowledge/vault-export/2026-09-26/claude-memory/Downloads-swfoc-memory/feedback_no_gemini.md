---
name: no-gemini-preference
description: User prefers Claude models over Gemini for multi-model analysis — called
  Gemini "dumb"
type: feedback
permalink: main/claude-memory/downloads-swfoc-memory/feedback-no-gemini
---

Do not use Gemini CLI for multi-model collaborative planning. User explicitly prefers Claude subagents (Opus/Sonnet/Haiku) over Gemini.

**Why:** User found Gemini output quality insufficient ("sumb" [sic]) compared to Claude models.

**How to apply:** In /multi-plan or /ccg:plan workflows, replace Gemini backend with Claude subagents (architect, planner, code-reviewer). Use Codex for the second model perspective since it uses a different model family (o3/o4-mini).