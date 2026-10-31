---
title: README
type: note
permalink: dqverify-repo-20261013/skills/seed-golden-journey/readme
---

# seed-golden-journey

A process skill that scaffolds an app's **keystone acceptance test** — a *held-out golden-journey*
that launches the REAL app, drives the ONE primary user journey, and asserts a REAL artifact on
disk. It is the single external **done-signal** the implementing agent can't author or fake, and
the antidote to coverage-theater (100% coverage, green units, and the product still broken).

Live proof it's needed: Reframe shipped v1.4 at 100% coverage / green units while "Make Shorts"
never produced a file on Windows. A held-out golden-journey that asserted a real vertical short on
disk red-repro'd it and peeled back three real Windows-only bugs sitting exactly at the seams the
unit tests mock and Linux CI can't reach.

## What's here

```
seed-golden-journey/
├── SKILL.md                                     # the five rules + assertion ladder + stack recipes
├── README.md
└── templates/
    ├── golden-journey.template.spec.ts          # Electron (primary) + Web variant, fill-in-the-blanks
    └── golden-journey.cli.template.spec.ts       # CLI variant (+ Python/pytest equivalent inline)
```

`SKILL.md` teaches: pick the ONE money journey; drive the real app (nothing stubbed); assert a
real produced artifact (the four-rung ladder — exists → non-empty → structurally valid via
ffprobe/parse/open → semantically correct), never element-present; poll the product's own status
channel to real completion with a diagnostic snapshot on timeout; make it the merge gate; and
forbid citing coverage as done (with the verbatim task line and the reward-hack surface to forbid).

The templates are adaptable, annotated specs derived from the Reframe exemplar
(`Reframe/app/e2e/golden-journey.spec.ts`) — replace every `<< PLACEHOLDER >>` and delete the
launch variant you don't use.

## Install

Canonical location (personal skill store):

```
~/.agents/skills/seed-golden-journey/
├── SKILL.md
├── README.md
└── templates/...
```

Mirror into `~/.claude/skills/seed-golden-journey/` if that store is synced separately.

## Relationship to other skills

- **two-tier-verify** — runs this golden-journey in its OUTER (commit-boundary) loop. This skill
  defines *what* the acceptance test is; that skill decides *when* to run it.
- **fresh-context-verify** — the independent-oracle check for a load-bearing *value*; a held-out
  golden-journey is the independent oracle for *"does the product work?"*.

## Provenance

Distilled from `agent-skills-toolchain/docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md` and
`Reframe/docs/research/GOLDEN-JOURNEY-FINDINGS-2026-07-07.md` (2026-07-07), grounded in a 7-agent
SOTA workflow (SWE-ABS held-out adversarial rejection of 19.78% of "passing" patches; bFinder
behavioural-coverage gaps; verifier↔generator error coupling) and the proven Reframe case study.