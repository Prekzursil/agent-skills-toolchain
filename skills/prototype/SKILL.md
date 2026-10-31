---
name: prototype
description: Use when the user wants to prototype, sanity-check a data model or state
  machine, mock up a UI, explore design options before committing, or says "prototype
  this", "let me play with it", "try a few designs". Routes to a runnable terminal
  app for state/logic questions or several toggleable UI variations for design questions.
permalink: dqverify-repo-20261013/skills/prototype/skill
---

# Prototype

A prototype is **throwaway code that answers one question**. The question decides the shape — pick the wrong branch and the whole prototype is wasted.

## Pick a branch

Identify which question is being answered — from the prompt, the surrounding code, or by asking if the user is reachable:

- **"Does this logic / state model feel right?"** -> [LOGIC.md](LOGIC.md). A tiny interactive terminal app that drives a pure state model by hand through cases that are hard to reason about on paper.
- **"What should this look like?"** -> [UI.md](UI.md). Several radically different UI variations behind one switcher, flipped through in the running app.

If it is genuinely ambiguous and the user is AFK, default by the surrounding code (a backend module -> logic; a page or component -> UI) and state the assumption at the top of the prototype.

## Rules that apply to both

1. **Throwaway from day one, clearly marked.** Put the prototype next to the code it is prototyping for (context is obvious) but name it so a casual reader sees it is a prototype, not production. For throwaway UI routes, obey the project's existing routing convention — do not invent a new top-level structure.
2. **One command to run.** Whatever the project's task runner supports — `pnpm <name>`, `bun <path>`, `python <path>`, an Electron `start` script. The user starts it without thinking.
3. **No persistence by default.** State lives in memory. Persistence is the thing the prototype is *checking*, not something it depends on. If the question is explicitly about a database, hit a scratch DB or local file with a clear "PROTOTYPE — wipe me" name.
4. **Skip the polish.** No tests, no error handling beyond what makes it runnable, no abstractions. Learn something fast, then delete it.
5. **Surface the state.** After every action (logic) or on every variant switch (UI), render the full relevant state so the user sees what changed.
6. **Delete or absorb when done.** Once it has answered its question, delete it or fold the validated decision into real code — never leave it rotting in the repo.

## Capture the answer (workspace-native)

The *answer* is the only durable output of a prototype. When it has answered its question, write the resolved decision into the workspace stores — **not** a stray `NOTES.md` or `docs/adr/` file:

- **Event ledger** (objective, replayed after compaction):
  `python ~/.claude/hooks/event-ledger/note.py --kind decision "<question> -> <answer> (prototype: <path>)"`
- **basic-memory** for a decision worth surviving compaction or reuse across projects: write it with `mcp__basic-memory__write_note` so recall surfaces it later.
- If running AFK and the answer is not in yet, leave a one-line `PROTOTYPE-Q:` comment beside the code so the verdict gets filled in (by you on the next pass) before the prototype is deleted.

Then delete the throwaway shell, or lift the validated core (the pure module behind a logic prototype, the winning variant from a UI prototype) into the real code and delete the rest.

## Compose with

- **ui-audit** — after building UI variants, drive the running app with the `ui-audit` skill to get objective per-variant numbers (contrast, spacing, tap targets, dead buttons) plus the Track-B design VERDICT. Turns "which looks best" from vibes into measured + reasoned.
- **to-prd** — a prototype snippet that nails a decision (reducer, state machine, schema, type shape) can be inlined into a PRD's Implementation Decisions; `to-prd` has an explicit hook for this.
- **app launch** — start the prototype with the project's own runner; the `run` skill / app-driver patterns cover Electron, web, and CLI launch.

---
_Idea adapted from the `prototype` skill in https://github.com/mattpocock/skills — MIT License, Copyright (c) 2026 Matt Pocock. This is a workspace-native rebuild (capture rewired to the event-ledger + basic-memory; composes with ui-audit / to-prd; stack-agnostic launch), not a verbatim copy. Original under MIT; full notice in LICENSE (this folder). Built 2026-06-30._