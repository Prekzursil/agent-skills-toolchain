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

### The one-pass pipeline (what `forge.py` does)
### How forged hooks compose with the dispatcher / manifest
### Where this sits in the instinct → skill path
### Usage
### Inject discipline (Stop): surface uncaptured TODO/FIXME markers. Folds as 1 manifest line.
### Gate discipline (PreToolUse): block git push --force. Installs as a settings.json entry.
### Inspect without staging:  add --dry-run
### Full result as JSON:      add --json
### Trigger kinds
### Files
### Quality bar
