# workspace-hooks

Optimal Agentic Workspace — Tier 2/3 behavioral-enforcement hooks, supporting skill,
agent, and event-ledger add-ons. Built 2026-06-11 per design-v1.md and
workspace-knowledge-base.md.

All hooks: stdlib-only Python, always exit 0 (fail-open), additive/reversible,
idempotent. None block; all inject via `additionalContext`.

---

## Directory Layout

```
workspace-hooks/
  inquisitiveness/        Tier-2: pre-execution clarity guard
    prompt-guard.py       hook script
    test_prompt_guard.py  unit tests (13 assertions, PASS)

  anti-degen/             Tier-2: result-aware loop-break detector
    fingerprint.py        hook script
    test_fingerprint.py   unit tests (PASS)

  goal-reinject/          Tier-3: anti-tunnel-vision goal re-injection
    reinject.py           hook script
    test_reinject.py      unit tests (PASS)

  event-ledger-extras/    Tier-3: observability add-ons to event-ledger keystone
    oats.py               Tool-selection optimiser (OATS scaffold)
    prune-report.py       Hook usage prune-report (ranked advisory)
    test_prune_oats.py    unit tests (PASS)

  skills/
    clarify-requirements/
      SKILL.md            Skill invoked by prompt-guard to ask clarifying Qs

  agents/
    intent-drift-sentinel.md  Agent: on-demand EVPI clarify + drift verdict

  AGENTS.md               Cross-tool behavioral contract (Claude/Codex/Antigravity)
  README.md               This file
```

---

## settings.json Wiring

All three hooks are wired in `~/.claude/settings.json`. Canonical commands:

| Hook script | Hook type | Matcher | Command |
|---|---|---|---|
| `inquisitiveness/prompt-guard.py` | `UserPromptSubmit` | (all prompts) | `python ~/.claude/hooks/inquisitiveness/prompt-guard.py` |
| `anti-degen/fingerprint.py` | `PostToolUse` | `tool_name in (Bash,Edit,Write,…)` | `python ~/.claude/hooks/anti-degen/fingerprint.py` |
| `goal-reinject/reinject.py` | `PreToolUse` | `tool_name in (Edit,Write,Bash)` | `python ~/.claude/hooks/goal-reinject/reinject.py` |

These scripts live at `~/.claude/hooks/<dir>/` (symlinked or copied) and are called
by the Claude Code harness. The wiring in settings.json uses absolute paths.

---

## event-ledger-extras

`oats.py` and `prune-report.py` extend the event-ledger keystone at
`~/.claude/hooks/event-ledger/`. They import `ledger.py` via sys.path.insert and
are called manually or via cron (not directly wired as hooks):

```
# Generate prune report
python ~/.claude/hooks/event-ledger/prune-report.py

# Run OATS analysis (once >=100 session events exist)
python ~/.claude/hooks/event-ledger/oats.py
```

---

## AGENTS.md

Cross-tool behavioral contract for Claude Code, Codex CLI, and Antigravity (agy).
Canonical location: `~/.claude/AGENTS.md` (also mirrored to `~/.codex/AGENTS.md`).
The copy here is for version-control durability; authoritative source is `~/.claude/AGENTS.md`.

---

## Deployment / Installation

These files are the version-controlled source of truth. To deploy or reinstall:

```powershell
# Copy hook dirs to live location
Copy-Item tools/workspace-hooks/inquisitiveness/* ~/.claude/hooks/inquisitiveness/ -Force
Copy-Item tools/workspace-hooks/anti-degen/*       ~/.claude/hooks/anti-degen/      -Force
Copy-Item tools/workspace-hooks/goal-reinject/*    ~/.claude/hooks/goal-reinject/   -Force
Copy-Item tools/workspace-hooks/event-ledger-extras/*.py ~/.claude/hooks/event-ledger/ -Force

# Copy skill + agent
Copy-Item tools/workspace-hooks/skills/clarify-requirements/SKILL.md ~/.claude/skills/clarify-requirements/ -Force
Copy-Item tools/workspace-hooks/agents/intent-drift-sentinel.md ~/.claude/agents/ -Force
```

settings.json wiring must be added once and is idempotent thereafter (the wire
stage checks before adding).

---

## Test Results (2026-06-11)

```
test_prompt_guard.py  : PASS  (13 assertions)
test_fingerprint.py   : PASS  (all assertions)
test_reinject.py      : PASS  (all assertions)
test_prune_oats.py    : PASS  (all assertions)
```
