---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] ROOT CAUSE of a wholly failed synthesis run: the effort config. Setting consensus to medium and draft/critique/review to high turned run-1's 0 agents in 10 minutes into run-2's 59/59 agents, 0 errors, 35.5 minutes. A run that finishes fast with zero output is a config failure wearing a success exit code.
- [fact] Run-2 delivered a 2.7k summary, 8 sections and 26 briefs, carrying 86 GitHub references and 136 items explicitly tagged UNVERIFIED - the tags being the point, not a defect.
- [decision] The prompt-rewrite hypothesis is REFUTED: the mechanism is an append-block, not a rewrite, which refutes 7-plus downstream claims that assumed rewriting. `PreModelSwitch` is hook-deniable, but its efficacy as a mitigation is UNVERIFIED.
- [fact] Two defects surfaced in the same pass: a false positive in `fable-safe-prompt`, and a broken prevent-to-recovery path.
- [fact] An identity defect in the corpus was repaired before synthesis could be trusted: `rename_corpus.py` exited 0 recovering 109 labels across 106 renamed files totalling 2.037M characters. Without the lane identity join, the corpus was 106 files with no way to attribute a finding to the agent that produced it.
- [fact] Pre-flight before the relaunch measured 55.85 GB free with 251 MCP processes discharged by the reaper - the gate ran before the fan-out, not after it failed.
- relates_to [[Claude Code UserPromptSubmit hook output schema measured in the installed binary 2026-09-25]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-08 src: .remember/today-2026-09-26.done.md 01:07, 13:57 sha256: fdca19baf64f -->
