---
name: prototype
description: Use when the user wants to prototype, sanity-check a data model or state machine, mock up a UI, explore design options before committing, or says "prototype this", "let me play with it", "try a few designs". Routes to a runnable terminal app for state/logic questions or several toggleable UI variations for design questions.
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

### Capture the answer (workspace-native)
### Compose with
