# Logic Prototype

A tiny interactive terminal app that lets the user drive a state model by hand. Use this when the question is about **business logic, state transitions, or data shape** — the kind of thing that looks reasonable on paper but only feels wrong once you push it through real cases.

If the question is "what should this look like" — wrong branch. Use [UI.md](UI.md).

## When this is the right shape

- "I'm not sure if this state machine handles the edge case where X then Y."
- "Does this data model actually let me represent the case where..."
- "I want to feel out what the API should look like before writing it."
- Anything where the user wants to **press buttons and watch state change**.

## Process

### 1. State the question

Before writing code, write down what state model and what question you are prototyping — one paragraph, in the prototype's README or a comment at the top of the file. A logic prototype that answers the wrong question is pure waste; make the question explicit so it can be checked later, whether the user is watching now or returning to it AFK.

### 2. Pick the language

Use whatever the host project uses (Node/bun/pnpm/Deno, Python, etc.). If the project has no obvious runtime (e.g. a docs repo), ask. Do not add a new package manager or runtime just for the prototype.

### 3. Isolate the logic in a portable module

Put the actual logic — the bit answering the question — behind a small, pure interface that could be lifted out and dropped into the real codebase later. The TUI around it is throwaway; the logic module is not. Pick the shape that fits the question:

- **A pure reducer** — `(state, action) => state`. Good when actions are discrete events and state is a single value.
- **A state machine** — explicit states and transitions. Good when "which actions are even legal right now" is part of the question.
- **A small set of pure functions** over a plain data type. Good when there is no implicit current state — just transformations.
- **A class or module with a clear method surface** when the logic genuinely owns ongoing internal state.

Keep it pure: no I/O, no terminal code, no `console.log` for control flow. The TUI imports it and calls into it; nothing flows the other direction. This is what makes the prototype useful past its own lifetime — the validated reducer / machine / function set lifts into the real module and the TUI shell gets deleted.

### 4. Build the smallest TUI that exposes the state

Build a **lightweight TUI** — on every tick, clear the screen (`console.clear()` / `print("\033[2J\033[H")` / equivalent) and re-render the whole frame. The user should always see one stable view, not an ever-growing scrollback. Each frame has two parts:

1. **Current state**, pretty-printed and diff-friendly (one field per line, or formatted JSON). Bold field names / headers, dim less important context. Native ANSI is fine (`\x1b[1m` bold, `\x1b[2m` dim, `\x1b[0m` reset) — no styling library unless one is already in the project.
2. **Keyboard shortcuts**, listed at the bottom: `[a] add user  [d] delete user  [t] tick clock  [q] quit`.

Behaviour: initialise state (single in-memory object), render the first frame, read one keystroke at a time and dispatch to a handler that mutates state, re-render the full frame after every action (replace, don't append), loop until quit. The whole frame fits on one screen.

### 5. Make it runnable in one command

Add a script to the project's existing task runner (`package.json` scripts, `Makefile`, `justfile`, `pyproject.toml`). The user runs `pnpm run <prototype-name>` or equivalent — never a path to remember. If there is no task runner, put the command at the top of the prototype's README.

### 6. Hand it over

Give the user the run command. They will drive it themselves; the interesting moments are "wait, that shouldn't be possible" or "huh, I assumed X would be different" — those are bugs in the *idea*, which is the whole point. Add new actions if they ask. Prototypes evolve.

### 7. Capture the answer (workspace-native)

When the prototype has done its job, the answer is the only thing worth keeping. Write it where the workspace looks for decisions — not a `NOTES.md` left to rot:

- `python ~/.claude/hooks/event-ledger/note.py --kind decision "<question> -> <answer> (logic prototype: <path>)"`
- For a decision worth surviving compaction or reuse across projects, also `mcp__basic-memory__write_note`.
- If AFK and the answer is not in yet, leave a `PROTOTYPE-Q:` placeholder beside the code so it can be filled before the prototype is deleted.

Then lift the validated pure module into the real codebase and delete the TUI shell.

## Anti-patterns

- **Don't add tests.** A prototype that needs tests is no longer a prototype.
- **Don't wire it to the real database.** In-memory store unless the question is specifically about persistence.
- **Don't generalise.** No "what if we wanted to support X later." The prototype answers one question.
- **Don't blur the logic and the TUI together.** If the reducer / machine references `console.log`, prompts, or escape codes, it is no longer portable. Keep the TUI a thin shell over a pure module.
- **Don't ship the TUI shell into production.** The shell is optimised for being driven by hand; the logic module behind it is the bit worth keeping.
