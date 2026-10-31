---
paths:
- '**/*.ts'
- '**/*.tsx'
- '**/*.js'
- '**/*.jsx'
permalink: dqverify-repo-20261013/rules/typescript/hooks
---

# TypeScript/JavaScript Hooks

> This file extends [common/hooks.md](../common/hooks.md) with TypeScript/JavaScript specific content.

## PostToolUse Hooks

**What the shipped hook already does — and does NOT do.** `hooks/per-edit-check/check.py`
is the PostToolUse checker wired for `Edit|Write|MultiEdit`. It runs `node --check` on
`.js/.mjs/.cjs/.jsx`, but it **deliberately skips `.ts` and `.tsx`** and returns "no
issues" (`hooks/per-edit-check/check.py:272-273` — `tsc --noEmit` is too slow for a
per-edit hook and `node --check` cannot parse TS). It never runs Prettier and never scans
for `console.log` on any extension. So a TypeScript edit gets **no** automatic
format/type/debug-log feedback by default.

To get any of the following you must add them yourself in `~/.claude/settings.json`; none
is provided out of the box:

- **Prettier**: Auto-format JS/TS files after edit
- **TypeScript check**: Run `tsc` after editing `.ts`/`.tsx` files — budget for it, this is
  the cost that kept it out of the shipped hook
- **console.log warning**: Warn about `console.log` in edited files

## Stop Hooks

- **console.log audit**: Check all modified files for `console.log` before session ends