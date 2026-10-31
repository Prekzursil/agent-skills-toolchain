---
title: README
type: note
permalink: dqverify-repo-20261013/skills/acceptance-review/readme
---

# acceptance-review

The **cross-model acceptance reviewer** gem (the C2 next-gem from the
agentic-perfection program). It runs at the *done* boundary of an app change and
returns a structured **SHIP / BLOCK** verdict from an INDEPENDENT — ideally
cross-model — reviewer that adversarially judges *"does this actually work
end-to-end, or is it green-but-broken?"* over the diff, the declared
golden-journeys, and the on-disk artifacts proving the journeys ran.

This is the human/orchestrator-facing counterpart to the always-on
functional-acceptance hooks (`claim-guard`, `test-tamper-guard`,
`journey-coverage`): those *gate silently on static signals*; this one *judges the
running-app evidence and hands you a verdict*. Thesis + why it exists:
`docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`.

## Why cross-model / fresh-context
The same context that wrote the code is a biased judge — intrinsic self-correction
degrades (Huang, ICLR'24), verifier↔generator errors couple ("Verification
Mirage"), judges prefer their own output (Panickssery, NeurIPS'24). Trustworthy
"it works" evidence requires an evaluator that did **not** write the code and,
where possible, is a **different model** (VeriMAP / MetaGPT). The reviewer is told
to demand the real artifact and is **forbidden from trusting coverage / "tests
pass"** — the gameable proxy the implementer controls.

## Install (canonical skills path)
Canonical skills live at `~/.agents/skills/<name>`. Install by copying the whole
directory:

```bash
# canonical (agents skills root)
cp -r acceptance-review ~/.agents/skills/acceptance-review

# also expose to Claude Code, if that root is used on this machine
cp -r acceptance-review ~/.claude/skills/acceptance-review
```

Invoke as `/acceptance-review` (Claude Code discovers it by the SKILL.md
frontmatter `name`). No install step for the helper — it is stdlib-only Python 3.

## Cross-model availability (probed on this machine)
- `codex` — Codex CLI **present** (`codex exec -s read-only`). Preferred reviewer.
- `gemini` — Gemini CLI **present** (`gemini --approval-mode plan`). Second choice.
- Fresh-context **Claude subagent** — always-available floor when no CLI is on PATH
  (spawned by the orchestrator via the Task tool; the helper prints the instruction).

The helper re-probes PATH at runtime (`shutil.which`) so the fallback reflects the
real environment, not this snapshot.

## Quick start
```bash
# 1. gather evidence + build the adversarial prompt + pick the reviewer
python scripts/acceptance_review.py --repo /path/to/app

# 2. dispatch the independent cross-model reviewer (wrap with longrun; may exceed 60s)
python scripts/acceptance_review.py --repo /path/to/app --dispatch

# 3. gate mode: non-zero exit on a BLOCK verdict
python scripts/acceptance_review.py --repo /path/to/app --dispatch --strict
```

Outputs land in `<repo>/.acceptance-review/`: `review-prompt.md`, `evidence.json`,
and (after `--dispatch`) `verdict.txt`.

## Tests
```bash
cd scripts && python test_acceptance_review.py
```
Covers the pure core (reward-hack scan, reviewer routing / graceful degradation,
verdict parse, prompt assembly, journey/artifact discovery) — no repo or CLI needed.
```bash
python -m py_compile scripts/acceptance_review.py scripts/test_acceptance_review.py
```