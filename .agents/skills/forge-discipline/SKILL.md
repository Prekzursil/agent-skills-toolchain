---
name: forge-discipline
description: Use when you want to turn a named behavioral pattern (a gem, a fresh arXiv finding, or a matured instinct) into an INSTALLED, self-tested Claude Code hook in one pass. This is a BEHAVIOR forge, not a tool forge - it forges hooks/tripwires (things the harness runs deterministically), not MCP tools. Given a pattern spec it scaffolds the hook plus any tripwire, state schema, and skill stub it needs, generates and runs a chaos/GameDay self-test that PROVES the hook fires on its trigger, stays silent otherwise, and fails open on garbage, then stages everything in a review queue with the exact one-line install instruction. It NEVER auto-wires settings.json or the dispatcher manifest - the human reviews and applies the one line.
---

# Discipline-Forge

The durable moat is not which cross-domain analogy you borrow today (those deprecate
the moment the field mines the same paper). The moat is **owning the pipeline that
turns any named behavioral pattern into an installed, self-tested discipline in one
pass.** This generalizes the instinct→skill evolution one step further: instead of
maturing an observed regularity into an *advisory* skill, it forges an *enforced*
hook that the harness runs deterministically — and refuses to call it "installed"
until a fault-injection self-test proves it actually fires.

This forges **behaviors** (hooks/tripwires). A tool-forge forges **tools** (things
the model chooses to call). Different artifact, different home: forged behaviors land
in `~/.claude/hooks/...` and fold into the dispatcher or `settings.json`.

## SAFETY: review before install (read this first)

`forge.py` **never edits your live `settings.json` or `_dispatch/manifest.json`.** A
forged discipline is staged in a review queue with its passing self-test and a single
ready-to-apply line. **You** read it and apply that line by hand. This mirrors the
auto-skill-authoring discipline (the forge proposes; the human installs) and means a
forged hook can never silently start blocking your tools or injecting context.

Every forged hook also fails open (any error → exit 0; a gate never blocks on error)
and ships a kill-switch: an env var `FORGE_<NAME>_OFF=1` and a `.disabled` file.

## The pattern spec

A discipline is described by a small spec (CLI flags or a `--spec file.json`):

| field | meaning |
|-------|---------|
| `name` | hyphen-case identity (becomes the hook dir + manifest name) |
| `event` | `sessionstart` \| `stop` \| `pretooluse` \| `posttooluse` \| `userpromptsubmit` |
| `trigger_kind` | how the predicate reads its source: `tool` \| `command` \| `prompt` \| `response` \| `field` \| `always` |
| `trigger_regex` | the pattern the source must match to fire (not needed for `always`) |
| `fire_example` / `silent_example` | a value that SHOULD / must NOT match — used to build the chaos test (validated at forge time) |
| `action` | the inject message (may contain `{count}`) or the block reason for a gate |
| `gates` | if set, forge a blocking tripwire (exit-2 path) instead of an inject |
| `needs_state` | scaffold a state/ledger schema + session-scoped dedup |
| `has_procedure` | also emit a companion SKILL stub |

The forge **validates the exemplars against the regex at generation time**: if the
fire example does not match (or the silent example does), it refuses to generate —
because the chaos test would otherwise be a lie.

## The one-pass pipeline (what `forge.py` does)

1. **Scaffold** exactly the artifacts the pattern needs:
   - `hook.py` — conforms to the dispatcher check-interface: `main(argv)` reads the
     payload on stdin and prints one `hookSpecificOutput` JSON (inject), or writes a
     reason to stderr and exits 2 (gate).
   - `tripwire.py` — the pure HALT predicate `should_halt(payload) -> (bool, reason)`
     (only when `gates`); kept separate so the block *decision* is unit-testable.
   - `state_schema.json` — the ledger record schema (only when `needs_state`).
   - `SKILL.md` — a companion procedure stub (only when `has_procedure`).
   - Everything fails open (try/except → exit 0).
2. **Unit test** the predicate (`build_message` / `should_halt`) directly and run it.
3. **Chaos / GameDay self-test** (`chaos_<name>.py`) — fault-injects against the REAL
   hook process to prove three properties; the discipline is **not installed until
   all three hold**:
   - **fires** on a matching payload,
   - stays **silent** (inject) / **allows** (gate) on a non-matching payload,
   - **fails open** on garbage stdin and honours the opt-out.

   The GameDay lesson: an untested safety net fails exactly when you need it. A gate
   that crashed-closed would block every command, so "fail open on garbage → exit 0,
   never 2" is an explicit, proven property.
4. **Stage** in the review queue `~/.claude/forge-queue/<name>/` with the artifacts,
   the passing self-test (`SELFTEST-RESULT.txt`), and `INSTALL.md` containing the one
   line to apply. Nothing is auto-wired.

## How forged hooks compose with the dispatcher / manifest

The forge picks the install target from the event and whether it gates:

- **Inject hook on `sessionstart` / `stop` / `pre` / `posttooluse`** → folds into
  `~/.claude/hooks/_dispatch/manifest.json` as **one line** under
  `events.<Event>.checks`. The dispatcher already runs that file in-process (one spawn
  per event), so this is the cheap path. The manifest's own description literally says
  "adding a future check = one manifest line (seeds the later Discipline-Forge)" — this
  is that forge.
- **Any gate (exit-2)** → a standalone `settings.json` entry. The dispatcher only ever
  exits 0 (it is inject-only), so a blocking hook cannot live inside it.
- **`userpromptsubmit` (any)** → a standalone `settings.json` entry. The dispatcher
  does not handle that event.

`INSTALL.md` always prints the exact target and the exact line/object to add.

## Where this sits in the instinct → skill path

The continuous-learning / homunculus path observes sessions, writes confidence-scored
**instincts** (`~/.claude/homunculus/instincts/`), and evolves the strong ones into
`~/.claude/homunculus/evolved/{skills,commands,agents}` — all **advisory** (the model
must choose to read/run them). Discipline-Forge adds a new evolution target at the end
of that path: a matured instinct (or a gem, or an arXiv pattern) → an **enforced,
self-tested hook**. Advisory knowledge becomes deterministic enforcement, with proof.

## Usage

```bash
cd skills/forge-discipline

# Inject discipline (Stop): surface uncaptured TODO/FIXME markers. Folds as 1 manifest line.
python forge.py --name todo-surfacer --event stop --trigger-kind response \
  --trigger-regex '\b(TODO|FIXME)\b|- \[ \]' \
  --fire-example 'TODO wire API; - [ ] ship' --silent-example 'all shipped' \
  --action 'You left {count} open TODO/FIXME marker(s) - capture them before they are lost.'

# Gate discipline (PreToolUse): block git push --force. Installs as a settings.json entry.
python forge.py --name no-force-push --event pretooluse --trigger-kind command --gates \
  --trigger-regex 'git\s+push\b[^\n]*(--force\b|-f\b)' \
  --fire-example 'git push --force origin main' --silent-example 'git push origin main' \
  --action 'Tripwire: refusing git push --force (AGENTS.md s9 needs explicit approval). Override: FORGE_NO_FORCE_PUSH_OFF=1.'

# Inspect without staging:  add --dry-run
# Full result as JSON:      add --json
```

Then open `~/.claude/forge-queue/<name>/INSTALL.md`, review the artifacts and the
passing self-test, and apply the one line if you approve.

## Trigger kinds

| kind | source read | typical event |
|------|-------------|---------------|
| `tool` | `payload.tool_name` | pre/posttooluse |
| `command` | `payload.tool_input.command` (Bash) | pre/posttooluse |
| `prompt` | `payload.prompt` | userpromptsubmit |
| `response` | final assistant text from `transcript_path` | stop |
| `field` | any dotted payload path (`--trigger-field`) | any |
| `always` | no predicate — always fires (inject only) | sessionstart/stop |

## Files

- `forge.py` — the scaffolder + self-test orchestrator (pure stdlib).
- `templates/` — the hook / tripwire / test / chaos / skill-stub / install templates.
- `selftest_forge.py` — regression harness: forges every branch combination in
  `--dry-run` and asserts each self-tests cleanly and resolves to the right target.

## Quality bar

A discipline that "looks wired but is dead" is the failure this skill exists to
prevent. The chaos self-test is the gate: no PASS, no queue entry, no install line.
Run `python selftest_forge.py` after any change to the engine or templates.
