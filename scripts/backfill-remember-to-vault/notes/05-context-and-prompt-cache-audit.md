---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] The dominant context cost measured on 2026-09-25 was NOT the per-turn payload but cold cache starts: about 50 cold prefix rewrites accounting for 7.03M tokens. A high cache hit rate and a large cold-start bill coexist happily, so hit rate alone is the wrong instrument.
- [fact] Three context levers were measured INERT, i.e. configured but doing nothing: `skillListingBudgetFraction` at 0.04, the `auto:5` control, and the recall gate (14.5 KB, tested and unused since Aug 9). A lever that is set but non-binding reads as a solved problem in a config diff.
- [decision] The reduction that actually paid was archiving 41 MEMORY entries and compacting 3 rules, measured at 8,550 tokens saved per session (commit e04ffabc4) - a payload cut, not a lever flip.
- [fact] The ported settings file is live at 27,211 B carrying 8 levers, verified by reading the live file rather than by trusting the port log.
- [fact] The 1M-context model picker needed 5 missing rows added (7 total: opus-5-5, opus-5, opus-4-8, opus-4-7, opus-4-6, sonnet-5, sonnet-4-6, all `[1m]`), verified against the build 2.1.282 catalogue. The `/model` command STRIPS the `[1m]` suffix on write, so a picker edited through `/model` silently loses the 1M variant.
- [fact] Two mechanical footguns hit the settings work itself: an encoding flip (LF vs CRLF) and a wrong `modelPicker` schema shape (the keys belong under `inferenceModels`).
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
See also [[Harness reconcile offload-w2025 2026-09-23]].
<!-- backfill-id: L6-BF-05 src: .remember/today-2026-09-25.done.md 03:15, 06:59, 22:25, 23:48 sha256: 105b61bcf7bf -->
