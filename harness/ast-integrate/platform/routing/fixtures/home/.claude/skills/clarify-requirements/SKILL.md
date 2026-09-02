---
name: clarify-requirements
description: Resolve genuine pre-execution ambiguity by scanning repo context, generating 1-6 grounded options, and asking 1-3 focused questions via AskUserQuestion. NOT for mid-task use (injection risk); NOT when the goal is already unambiguous; use to disambiguate vague prompts before any file edits.
---

# clarify-requirements

Invoked when the inquisitiveness guard (or the agent itself) detects a prompt that could be interpreted in meaningfully different ways before file edits begin.

## Procedure

1. **Cheap repo scan (1-2 reads).** Identify the most likely files/modules relevant to the user's request. Look for names, recent modifications, or patterns that suggest intent. This bounds the question space so questions are grounded, not open-ended.

2. **List interpretations.** Generate 2-6 concrete, mutually exclusive interpretations of the request. Label them A, B, C... For each note the implied scope (which files/behaviors change) and the outcome difference.

3. **EVPI gate.** Only proceed to ask if the interpretations lead to meaningfully different implementations. If one interpretation is clearly dominant from context (imports, recent commits, task name), pick it, state your assumption, and skip asking.

4. **Ask via AskUserQuestion — 1-3 questions, max.** Questions must be:
   - Grounded (reference actual file/module names or concrete options found in step 1-2).
   - Mutually exclusive (each question resolves a distinct axis of ambiguity).
   - Short (one sentence + options where applicable).
   - Never asking about things inferrable from the codebase.

5. **Proceed.** Once the user answers (or you confirm no material ambiguity), proceed with implementation. Do not loop back into this skill.

## Scope exclusions

- Do NOT invoke mid-task; clarification mid-execution amplifies prompt-injection risk 15-16x.
