---
title: 30-day convergence freeze
date: 2026-09-24
status: proposed
review_by: 2026-10-24
evidence:
  - docs/AUDIT-2026-09-24-sota-transcript-and-lanes.md#8-root-cause
  - docs/AUDIT-2026-09-24-sota-transcript-and-lanes.md#95-sequence
---

# 30-day convergence freeze

## Decision

For 30 days, from 2026-09-24 to 2026-10-24, start no new research waves, grills, gem hunts, councils, hooks or skills. The only admissible work is landing, deleting and measuring what already exists. The 2026-09-24 audit proposes this; it is in force once the owner sets `status: accepted`.

## Rationale

Section 8 of the audit finds that the instability is a convergence failure, not a missing architecture. Generation outruns integration by roughly an order of magnitude: research and audit waves arrive every week or two, one measured 13.3-hour build wave delivered 2 units rather than the 38 it reported, and the work-unit catalog stands at 58 open of 103. With no outcome instrument, every addition is justified by argument, so each new wave adds surface faster than anything is landed or measured.

Section 9.5 adopts the freeze from both blind derivations as the frame for the rest of the sequence (baseline first, stop the bleeding, shrink exposure, close the lanes) and names the freeze as the first decision record.

## What this replaces

No earlier record; this is the first in `docs/decisions/`. It replaces the unwritten default of opening a new research wave, grill, gem hunt, council, hook or skill whenever a transcript or audit suggests one. Nothing is deleted by this record.

## How to verify it is still in force

1. No new skills or hooks have landed on `main` since the freeze began, other than fold-backs of existing work that cite their source branch. Expect empty output, or only such fold-backs:
   `git log origin/main --since=2026-09-24 --diff-filter=A --name-only --format= -- '*SKILL.md' hooks/`
2. Every remote branch updated since the freeze began is a landing, deletion or measurement lane, not a research, grill, gem-hunt or council lane:
   `git for-each-ref --format='%(committerdate:short) %(refname:short)' refs/remotes/origin | awk '$1 >= "2026-09-24"'`
3. On `review_by`, measure the exit criteria in Phase 5 of `docs/RUNBOOK-2026-09-24-settle-and-harden.md`. If they hold, end the freeze: set `status: retired` and record the measurement in `retested:`. If they do not, add `retested:` with the measured gap and set the next `review_by`.
