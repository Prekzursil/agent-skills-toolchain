# Plan - Multi-Model Collaborative Planning

Multi-model collaborative planning - Context retrieval + Dual-model analysis → Generate step-by-step implementation plan.

$ARGUMENTS

---

## Core Protocols

- **Language Protocol**: Use **English** when interacting with tools/models, communicate with user in their language
- **Mandatory Parallel**: Codex/Gemini calls MUST use `run_in_background: true` (including single model calls, to avoid blocking main thread)
- **Code Sovereignty**: External models have **zero filesystem write access**, all modifications by Claude
- **Stop-Loss Mechanism**: Do not proceed to next phase until current phase output is validated
- **Planning Only**: This command allows reading context and writing to `.claude/plan/*` plan files, but **NEVER modify production code**

---

## Multi-Model Call Specification

**Call Syntax** (parallel: use `run_in_background: true`):
