---
description: "Extract reusable patterns from the session, self-evaluate quality before saving, and determine the right save location (Global vs Project)."
---

# /learn-eval - Extract, Evaluate, then Save

Extends `/learn` with a quality gate, save-location decision, and knowledge-placement awareness before writing any skill file.

## What to Extract

Look for:

1. **Error Resolution Patterns** — root cause + fix + reusability
2. **Debugging Techniques** — non-obvious steps, tool combinations
3. **Workarounds** — library quirks, API limitations, version-specific fixes
4. **Project-Specific Patterns** — conventions, architecture decisions, integration patterns

## Process

1. Review the session for extractable patterns
2. Identify the most valuable/reusable insight

3. **Determine save location:**
   - Ask: "Would this pattern be useful in a different project?"
   - **Global** (`~/.claude/skills/learned/`): Generic patterns usable across 2+ projects (bash compatibility, LLM API behavior, debugging techniques, etc.)
   - **Project** (`.claude/skills/learned/` in current project): Project-specific knowledge (quirks of a particular config file, project-specific architecture decisions, etc.)
