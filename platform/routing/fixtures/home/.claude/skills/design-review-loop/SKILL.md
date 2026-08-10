---
name: design-review-loop
description: MOVED — renamed to design-studio. This is a redirect tombstone kept so in-flight invocations of the old name still resolve. Use the design-studio skill instead; it is the SAME TCR design-review loop (G0 PRIME to G7 VERIFY, revert-gate) plus a thin mode router. Pick a mode — direct, audit, mirror, critique, iterate, implement, verify, loop, drive, session — or run design-studio loop for the whole pass. Triggers that used to land here (design review, run the design-review loop, TCR loop, audit the UI, transpose or mirror to Figma, design critique, implement the design, iterate design, drive the app, interactive design tweak) now route through design-studio.
metadata:
  origin: user
---

# design-review-loop — MOVED to `design-studio` (tombstone redirect)

**This skill was renamed to `design-studio`** (gem-hunt 2026-07-12, item C1; evidence
MASTER-DECISION-QUEUE C.1 / UIUX-CONSOLIDATION C.1). It is kept ONLY as a redirect so any
in-flight or cached invocation of the old name `design-review-loop` still resolves and
points you at the new entry — renaming a live skill would otherwise break those calls.

## Where it went

- **Skill:** `~/.claude/skills/design-studio/` (same harness: `loop.mjs`, `gates.mjs`,
  `revertDecision()`, `loop-state.json` — nothing about the loop changed).
- **New capability:** a **thin mode router** — jump to one stage instead of the whole loop.

```
/design-studio <mode> --app <app>
  modes: direct | audit | mirror | critique | iterate | implement | verify | loop | drive | session
```

| Old use | Now |
|---|---|
| the whole design-review pass | `design-studio loop` (or just the skill) |
| just audit a screen | `design-studio audit` (→ `ui-audit`) |
| code→Figma / mirror | `design-studio mirror` (→ `transpose-to-figma`) |
| persona critique | `design-studio critique` (→ `critique-panel`) |
| Figma→code + revert-gate | `design-studio implement` (→ `figma-implement-design`) |
| drive / point at the live app | `design-studio drive` (→ `ui-drive`) |
| interactively restyle a live element | `design-studio session` (→ `design-studio-session`) |

> The loop-state terminal marker id-prefix stays `design-review-<id>` for state
> backward-compat; only the skill entry name changed to `design-studio`.
