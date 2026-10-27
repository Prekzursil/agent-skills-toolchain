---
name: transpose-to-figma
description: Use when lifting a running or built UI back onto the Figma canvas (the G2 TRANSPOSE / Code-to-Canvas edge of the design-review loop) and you must pick the right code-to-Figma path — story.to.design for the component system loop, the Figma MCP generate_figma_design for live or localhost screens, or html.to.design for an audit-only DOM record. Also use when reasoning about what survives the lossy round-trip (DTCG design tokens and Code-Connected components) versus what is lost (React state, routing, data, logic). Do NOT use for Figma-to-code implementation (use figma-implement-design) or plain Figma data fetch and MCP setup (use figma). Covers Reframe, momentstudio, WebCoder, bilbo.
---

<!-- origin: user (design-SOTA research, 2026-06-30); implements DESIGN-SKILLS-AND-EVAL.md §1.2, DESIGN-WORKFLOW.md G2/§1/§3, FIGMA-SETUP.md §1/§2.3/§2.6/§3 -->


# transpose-to-figma Skill

The **G2 TRANSPOSE** gate of the TCR design-review loop — the *altitude selector* for
the code-to-Figma edge. Its one job: lift the **running UI onto the canvas so you
critique reality, not a stale design file** — and pick the *right* transpose path for
the situation so you don't pay for drift you didn't need.

**Skill location:** `~/.claude/skills/transpose-to-figma/`

> Implements `DESIGN-SKILLS-AND-EVAL.md §1.2` (the `transpose-to-figma` row),
> `DESIGN-WORKFLOW.md` G2 + §1 (lossy round-trip) + §3 (the transpose→discuss→revert
> micro-loop), and `FIGMA-SETUP.md §1` (transpose-plugin table) + `§2.3` (tool surface)
> + `§2.6` (Code Connect) + `§3` (token spine). Cross-reference **FIGMA-SETUP.md** for
> MCP install/auth, rate limits, and the token pipeline before first use.

---

## Overview — the one load-bearing truth

**The code → Figma → code round-trip is LOSSY and render-mediated.** `generate_figma_design`
does not convert code to Figma; it spins your dev server, renders in a browser, and
**serializes the rendered DOM**. Visual structure transfers; **React state, routing, API
calls, and business logic do NOT.** (`DESIGN-WORKFLOW.md §1`)

**The only things that round-trip cleanly:**
1. **W3C DTCG design tokens** (Tokens Studio ⇄ Git ⇄ Style Dictionary).
2. **Code-Connected components** (the agent emits *your* `<Button>`, not a re-derived div).

### When to use
### The altitude decision (the key insight)
### Recommend a path + drift class + caveats + the exact next tool call:
### Driving each path
### A. System loop — `story.to.design` (LOW drift, the preferred path)
### B. Live / localhost — `generate_figma_design` (MEDIUM drift, the workhorse)
### C. Audit record — `html.to.design` (HIGH drift, look-only)
### Record the transpose (the revert-surface manifest)
### System loop (both bound) -> systemLoopReady: true, revert via token diff:
### Audit record (nothing bound) -> emits the AUDIT-ONLY warning:
### Standard questions for this gate (the G2 question bank)
### What survives vs. what is lost (cite this every time)
