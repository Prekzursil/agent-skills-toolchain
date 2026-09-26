---
title: Research coverage register register 5 of 5 built 2026-09-25
type: report
permalink: main/research/research-coverage-register-register-5-of-5-built-2026-09-25
tags:
- research-coverage
- harness
- discipline
- measured
- registers
---

# Research coverage register — register 5 of 5

Built to satisfy the owner instruction of 25.09.2026: *"you also journal/knowledge archive …
with coverage of what was already found searched and parsed … so we dont risk redoing it
again."* Built **from an existing workflow journal with zero provider calls** — itself
compliance with the same turn's "do not rerun the research" instruction.

## Observations

- [decision] A sweep that re-runs is indistinguishable from a sweep that works. Both burn quota, both come back with sources, both look busy. The only thing separating them is a durable record of what the last sweep already found.
- [fact] SSOT is append-only JSONL at `~/.agents/knowledge/research-coverage/` (`coverage.jsonl`, `queries.jsonl`, `runs.jsonl`). `~/.agents/knowledge/RESEARCH-COVERAGE.md` is a **generated face** written by `research-coverage.py index` — never hand-edit it.
- [fact] Contents from run `wf_a2bae891-84b` (topic: prompt-interception): **3,070 unique URLs · 1,360 recorded queries · 1 run**. Tier split A 1,899 / B 650 / C 518 / A-B 3 (sums to 3,070; A-share 61.9%).
- [fact] Independently verified set-identical: **0 missing / 0 extra / 0 duplicate keys**. Raw 3,782 URL rows → 3,070 unique + 712 duplicates. Confidence: high (verified, not estimated).
- [decision] The dedup key must be the sweep's own key character for character, and must be re-verified by **independent hand transcription**, never by importing the register's own function to check itself. Current key: `trim → lowercase → drop #fragment → drop ?query → strip trailing /`.
- [fact] The verifier must read JSONL with `newline=""` and `.split("\n")`. `str.splitlines()` also splits on `\v \f \x1c \x1d \x1e \x85 U+2028 U+2029` and lone `\r`; U+2028 is legal raw inside a JSON string, so `splitlines()` cuts records in half. Measured machine-wide: 1 of 1,554 `.jsonl` files carries U+2028 (0.064%) — rare enough to look clean, common enough to destroy a file.
- [fact] Stored record shape: normalised key under **`"u"`**, original under **`"raw"`**, **no top-level `"url"`**. Guessing `"url"` produced `register unique 1 / duplicate keys stored 3069` and then a TypeError.
- [decision] **Enumerate the schema before extracting from it.** A zero or empty reading is evidence about the *probe* until the field names are confirmed. This error class fired three times in one session (`url` vs `u`; `notes` vs `note`; a missing `cli.js`) — the third time it cost a false "105 of 106 agents returned nothing" alarm whose real corpus was 313,962 chars, median 2,867, zero results under 500.
- [limitation] `research-coverage.py ingest` is **journal-only**: `--journal` is `required=True` and there is **no `--sources` flag** (measured at lines 496-525). Do not write `--sources` into any skill file until the flag exists.
- [fact] `stop` derivation: `open_agents = started - len(results) - failed`; `"in-flight"` if open, else `"converged"` if any exhausted reports, else `"cap-bound-or-unknown"`. The run row reads **`in-flight`**, correctly, because the workflow was paused.
- [decision] Report coverage honestly: a run that terminated on its round cap is **CAP-BOUNDED, not converged**. Say which. Measured for this run: **`exhausted: 0 of 105 sweep agents`** — the owner's stated yardstick (*"until they dont match anything anymore"*) was **never met**.
- [fact] Root cause is my own design flaw, not a provider failure: the exit condition `while (dry < 2 && round < MAX_ROUNDS)` with `MAX_ROUNDS = 6` could never fire, because the agents had no working way to report exhaustion. Fresh-unique per round 901/711/704/693 and A-tier 710/561/572/555 — still finding real material at round 4, so the tail was **not** long-tail noise.
- [decision] Provider attribution is agent free-text, not telemetry. Measured: firecrawl appears under four spellings, exa under three. Summed, **exa ≈1,446 vs firecrawl ≈506** — exa carried the sweep. Never quote a single provider row as a measured total.
- [fact] Wiring: agent leg is `deep-research/SKILL.md` Step 0 (thread the digest into every research agent's prompt verbatim — *"your job is the complement, not the repeat"*) and Step 7b (ingest the journal, then `index`). Rule leg is `rules/common/research-coverage.md`. Deliberately **not** added to `gap_check.py` — it is consulted at dispatch time, and editing a hook that fires every turn costs more than it buys.
- [decision] Digest before dispatch, ingest after return. Half the loop is worse than none, because it looks closed.
- [fact] Workflow resume cache key is `(prompt, opts)`: the longest unchanged prefix returns cached, the first edited/new call and everything after runs live. A `failed` agent has no cached result, so it **breaks the prefix** — measured, 4 agents re-ran on resume (the one failure at index 22 of 26, plus indices 23-25), ~30 agents of ~434.

## Relations

- relates_to [[Claude Code UserPromptSubmit hook output schema measured in the installed binary 2026-09-25]]
