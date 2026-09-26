---
title: Cowork dump RETIRED option A 2026-08-24
type: guide
permalink: main/harness/cowork-dump-retired-option-a-2026-08-24
tags:
- harness
- cowork
- basic-memory
- agents-md
---

valid_as_of: 2026-08-24

Owner chose **A**: retire the imported Claude Cowork defaults in `C:\\Users\\Prekzursil\\Agents.md`.

`~/Cowork/` is archive-only. Agents must not read/write `memory.md` / `output/` / `research/` / `scripts/` / `trash/` there unless cwd is inside `~/Cowork`.

Semantic memory = basic-memory (`D:/basic-memory`). Objective history = event ledger. Project receipts = active project folder (phenibut: `D:\\Research\\projects\\phenibut\\docs\\` and `compute\\`). No parallel `memory.md`.

Cause of the bad write: Agents.md lines that said check/update `~/Cowork/memory.md` at session start/end. Those lines are gone.
