---
title: Claude Code UserPromptSubmit hook output schema measured in the installed binary
  2026-09-25
type: report
permalink: main/research/claude-code-user-prompt-submit-hook-output-schema-measured-in-the-installed-binary-2026-09-25
tags:
- hooks
- claude-code
- prompt-interception
- measured
- schema
- binary-scan
---

# Claude Code UserPromptSubmit hook output schema — read from the installed binary

Settles the architectural premise of the prompt-interception SOTA audit by reading the zod
schema out of the installed CLI, instead of trusting contested GitHub issue threads. No
workflow, no provider, no network required.

## Observations

- [fact] The npm package `@anthropic-ai/claude-code` ships **no `cli.js`** — 14 files, the entry point is a 242,171,040-byte native `bin/claude.exe`. A text scan over its 9 text files (incl. `sdk-tools.d.ts`) returned 0 for every term **including the controls** — the broken-probe signature, not a finding.
- [fact] The minified JS bundle is **embedded inside the exe**. Readable ASCII at offsets ~198.6M / ~200.5M / ~204.7M / ~208.0M, plus the shipped hooks documentation markdown at ~98.78M.
- [method] Chunked latin1 (`Encoding::GetEncoding(28591)`) byte-transparent scan, 16 MiB chunks, 64-byte carry, skip matches lying wholly inside the carry (`if (($i + $needle.Length) -gt $cl)`), `$i += 1` to catch overlaps. Scans 242 MB in ~1.8 s; no findstr line-length limit; counts ASCII and UTF-16LE without double-counting.
- [fact] `hookSpecificOutput` is **ONE zod discriminated union keyed on `hookEventName`**, shared by every hook type. There is **no branch on the hook's `type` field** (`command` vs `prompt`).
- [fact] The UserPromptSubmit branch, verbatim: `M0=f(()=>d({hookEventName:A("UserPromptSubmit"),additionalContext:o().optional(),sessionTitle:o().optional(),suppressOriginalPrompt:M().optional().describe('When decision is "block", omit the original prompt from the block message')}))` — that is the **complete field set**.
- [fact] `PreToolUse` by contrast carries `updatedInput:me(o(),ae()).optional()`. Tool-input rewriting exists in the product; prompt rewriting does not.
- [decision] The research brief's "Critical Design Constraint" (a UserPromptSubmit hook can only **append** `additionalContext` or **block with exit 2**) is **CONFIRMED against the installed build** — upgraded from issue-thread inference to a direct schema reading. Confidence: high (verified).
- [refuted] `replacementPrompt` (asserted by issue #37559 to work for `type:"command"` hooks) — **0 ascii / 0 utf16**. Refuted structurally as well: one union, all hook types, no `type` branch.
- [refuted] `updatedPrompt` (issue #20833, the official Python SDK UserPromptSubmit example) — **0 / 0**. Most plausibly a confusion with PreToolUse's real `updatedInput`.
- [refuted] `modifiedPrompt` (issue #34390, closed-stale) — **0 / 0**.
- [correction] `replacePrompt` (open feature request #95763) shows **10 ascii hits, ALL TEN substring noise**: `replacePromptId` ×4, `replacePromptIndex` ×3, `replacePromptCache1hAllowlist` ×3 — setters on internal `requestJournal`/`requestLatches` state classes following a `replaceX` convention (`promptId(){return this.#r}replacePromptId(e){this.#r=e}`). **A substring match is not a token match.** I reported these as "genuinely unexpected" one window earlier; that reading was wrong. The feature is open and **not implemented**.
- [decision] Controls are mandatory before any absence claim. Measured, and reproduced on a second independent run the same day: `hookSpecificOutput` 168 · `additionalContext` 201 · `UserPromptSubmit` 80 · `UserPromptExpansion` 33 · `PreToolUse` 241 · `updatedInput` 428. All non-zero ⇒ the four zeros are real absences, not a dead detector.
- [fact] Three levers the brief did not account for: **`suppressOriginalPrompt`** (26 occurrences; applies *only when decision is "block"* — it suppresses the original prompt from the block message, it does **not** replace it, and must not be inflated into a replacement mechanism), **`sessionTitle`** (75), and **`PreModelSwitch`** (58).
- [fact] `PreModelSwitch` schema: `permissionDecision:z(["allow","deny","ask"]).optional()`, described in-binary as *"Same contract as PreToolUse: allow proceeds (skipping the interactive cache-miss confirm), deny cancels the s…"*.
- [decision] **`PreModelSwitch` is the prevention lever for the fable-safe-prompt → recover-from-false-positive e2e**: the classifier-triggered automatic model switch is hook-deniable. Neither skill currently uses it.
- [fact] SessionStart additionally carries `initialUserMessage`, `watchPaths` (*"Absolute paths to watch for FileChanged hooks"*) and `reloadSkills`; a `Setup` event exists carrying `additionalContext` only.
- [fact] The error-help object at ~208.0M agrees with the schema: `"for UserPromptSubmit":{hookEventName:'"UserPromptSubmit"',additionalContext:"string (optional)"}`.
- [scope] Only `bin/claude.exe` — the binary the launcher actually invokes (`claude.ps1` → `bin/claude.exe`) — was scanned. `node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe` (240,767,648 B, a **different** build) and the three `.old.<timestamp>` copies were **not** scanned.
- [fact] Separate layer, easy to conflate: `~/.claude/rules/common/hooks.md` documents the **local harness's registration generator**, not the provider's output contract. `agent-self/harness/registration.py:21-39` defines an `EVENTS` tuple; `build_hooks()` (`:157-189`) emits registrations by iterating only that tuple. `Notification` is absent from it, so `hooks/notify-idle/notify.py` is never invoked. Provider schema ≠ harness registration.

## Relations

- relates_to [[Research coverage register register 5 of 5 built 2026-09-25]]
