---
name: design-review-loop
description: MOVED - renamed to design-studio. Redirect tombstone kept so old invocations
  still resolve. Use design-studio instead; it is the SAME TCR design-review loop
  (G0 PRIME to G7 VERIFY, revert-gate) plus a mode router (direct, audit, mirror,
  critique, iterate, implement, verify, loop, drive, session). Old triggers - design
  review, TCR loop, mirror to Figma - route to design-studio.
metadata:
  origin: user
permalink: dqverify-repo-20261013/skills/design-review-loop/skill
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
> Do NOT confuse with metaswarm `/review-design` (that reviews design *documents*).

**Action:** invoke **`design-studio`**. This tombstone will be archived to
`~/.agents/skills-retired-<date>/` once the router rebuild has propagated (item C.11).