---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] The 2026-09-25 gem-hunt sweep produced 216 findings, triaged 101 ADOPT / 63 TRIAL / 41 ALREADY / 11 SKIP, and a separate classification of 47 MCP servers into 22 KEEP / 16 QUARANTINE / 9 DELETE. The 9 deletions were verified against the HOME config before being proposed, not inferred from the VM alone.
- [decision] The sweep did NOT converge and must not be reported as converged. URL counts per round went 901 -> 711 -> 704 -> 693 with `exhausted = 0`, and it stopped because MAX_ROUNDS = 6 was reached. That is CAP-BOUNDED, which is a budget outcome, not an evidence outcome.
- [fact] At the close of the window the adoption backlog stood at 178 gems with 153 still pending against 20 open loops - i.e. triage outran adoption by roughly an order of magnitude.
- [fact] Supporting scripts were pushed as ca3776b3b with regression verification, so the triage is reproducible rather than a one-off reading.
- [decision] Findings are worth nothing until adopted, so the register-shaped answer is the durable part: the research-coverage register exists precisely so the next sweep's job is the COMPLEMENT of this one rather than a repeat of it.
- relates_to [[Research coverage register register 5 of 5 built 2026-09-25]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-07 src: .remember/today-2026-09-25.done.md 14:38, 15:22, 16:19, 18:18, 20:24, 20:42, 23: sha256: 1b351af4ffb4 -->
