---
name: design-studio-session
description: The interactive-modify capability behind `design-studio session` mode. Use when the owner wants to point at a LIVE element in a running app (Reframe, momentstudio, WebCoder, bilbo) and iteratively restyle it with Codex and Codex — preview candidates as injected style overlays FIRST, resolve the clicked element back to its source file:line, apply ONE scoped micro-commit, incrementally re-audit only the changed screen, and auto-decide KEEP or REVERT through the SAME revert-gate as the batch design-review loop. Do NOT use for a whole-app batch audit (use design-review-loop / ui-audit) or for driving the app without modifying it (use ui-drive).
---

# design-studio session — interactive-modify (gem N.2)

The **interactive twin** of the batch `design-review-loop`. Where the batch loop audits a
whole flow G0→G7, `session` runs ONE tight modify cycle per element, with the owner in the
loop and Codex + Codex as rival suggesters. It is deliberately a **consolidation, not a new
runtime**: it reuses the **same revert-gate**, the **same ui-audit summary shape**, and the
**same `loop-state.json` scope** as the batch loop, so it kills the overlap instead of
re-creating it (UIUX N.2 §89).

> Routed to by the `design-studio` meta-skill's `session` mode. Standalone entry:
> `node session.mjs <subcommand>`. No new deps, no new runtime.

## The cycle (UIUX N.2 §2.2)

```
DRIVE (ui-drive) → AUDIT baseline (ui-audit, cached)
  → PICK      owner clicks a live element → element→source picker resolves {selector, file:line, rect, computedStyle}
  → SUGGEST   Codex + Codex register N candidates, each a LIVE injected-style overlay FIRST (by:Codex|codex)
  → OVERLAY   preview every candidate BEFORE any source edit (reload = gone → reversible by construction)
  → SELECT    Artifact side-by-side gallery + one AskUserQuestion → owner picks (or "keep as-is")
  → APPLY     ONE scoped micro-commit on a design/live-<id> branch — the picked file ONLY
  → REAUDIT   incremental: changed screen only → delta from the ui-audit summary
  → REVERT-GATE  shared revertDecision(): KEEP or REVERT → loop
  → batch Figma-mirror every K accepts (hand off to design-studio mirror)

### Dual-agent mingle (UIUX N.2 §92)
### Subcommands
### Safety / SHADOW (council C5)
### Consolidation ledger (what it reuses, not rebuilds)
