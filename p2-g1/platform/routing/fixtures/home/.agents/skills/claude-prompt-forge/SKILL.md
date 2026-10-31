---
name: "claude-prompt-forge"
description: "Prompt-forging skill for Claude Code and long autonomous Claude sessions — the prompt analogue of grill-me-extensive. Builds orchestration, session, unit, and handoff prompts with resume-don't-restart preambles, both-states evidence contracts, AND-gate completion, hard safety bans, and unit sentinels so work survives compaction and resists false greens. Use when writing or hardening a multi-phase Claude prompt, when a prior prompt caused restarts or false completion, or when the user says forge a prompt, prompt for Claude Code, make this prompt robust, orchestration prompt, session prompt, or handoff prompt."
---

Forge prompts that drive Claude (especially Claude Code) through multi-phase autonomous work without restarting completed gates, trusting uncontrolled zeros, or claiming success from partial evidence.

This skill is the prompt analogue of `grill-me-extensive`. Where grill-me-extensive scopes a program by walking decisions, this skill produces the **instrument** that executes a decided program. Read `references/prompt-anatomy.md` for the full anatomy, `references/failure-patterns.md` for the measured failure modes each rule prevents, and `references/discovery-surface.md` when forging prompts that discover tools, MCPs, skills, or capacity upgrades (multi-registry + maturity flags + concrete borrow lines).

## When to use

- Writing or hardening an orchestration / session / unit prompt for Claude Code
- Turning a decision log or backlog into a paste-ready Claude prompt
- Fixing a prompt that caused restart-of-completed-work, false greens, or fragment overwrites
- Producing prompts for fan-out units, harvest units, or review units

Do **not** use for ordinary one-shot questions, casual chat, or prompts that do not need durability across context loss.

## The 8-section method

Produce prompts in this order. Omit a section only when it is genuinely inapplicable — never because it is long.

### 1. ROLE AND DELIVERABLE (who + what only)

State who Claude is in this turn and the single deliverable class. Ban pretence of access Claude does not have.

```
You are the [architect | implementer | reviewer | miner] for [program].

### 2. RESUME-DON'T-RESTART PREAMBLE
### 3. GROUND TRUTH (measured, banked)
### 4. BINDING DECISIONS (settled, do not re-litigate)
### 5. HARD SAFETY BOUNDARIES (prohibitions)
### 6. EVIDENCE AND COMPLETION CONTRACT
### 7. PHASED WORK (numbered, ordered, gated)
### 8. OUTPUT / UNIT CONTRACT
### Question policy (encode in the prompt)
### Anti-patterns to ban inside the forged prompt
### Modes (state which you are forging)
### Process
