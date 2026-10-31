---
title: Research coverage — never pay twice for the same discovery
scope: common
loads: on-demand (referenced from AGENTS-RUNTIME §1d); read BEFORE dispatching any
  research agent
verified: 2026-09-25 (register built from run wf_a2bae891-84b — 3,070 urls / 1,360
  queries, reproduced by an independent verifier)
paths:
- '**/.claude/**'
- '**/.agents/**'
permalink: dqverify-repo-20261013/rules/common/research-coverage
---

# Research coverage — register 5 of 5

**A sweep that re-runs is indistinguishable from a sweep that works.** Both burn quota, both
come back with sources, both look busy. The only thing separating them is a durable record of
what the LAST sweep already found — and without one, every new sweep silently re-buys ground it
already owns. Owner instruction, 25.09.2026: *"so we dont risk redoing it again."*

The SSOT is the append-only JSONL under `knowledge/research-coverage/`
(`coverage.jsonl`, `queries.jsonl`, `runs.jsonl`). `knowledge/RESEARCH-COVERAGE.md` is a
**generated face** — `scripts/research-coverage.py index` writes it; never hand-edit it.

## The two commands

**Before** dispatching research agents:

```
python ~/.agents/scripts/research-coverage.py digest --topic <topic> \
       --out <scratch>/prior-coverage.txt
```

Thread that file's contents into every research agent's prompt. After the sweep finishes,
ingest it so the next one inherits the coverage:

```
python ~/.agents/scripts/research-coverage.py ingest \
       --journal <transcriptDir>/journal.jsonl --topic <topic>
```

Other subcommands: `stats` (whole-store aggregates), `queries`, `check`, `index`.
All output is counts and aggregates — never a URL dump — and every subcommand ends with
a §4 `SUCCESS:`/`FAILED:` marker.

## Discipline

1. **Digest before dispatch, ingest after return.** A sweep that skips the digest is
   re-running by default; a sweep that skips the ingest makes the NEXT one re-run. Both
   halves or neither — half the loop is worse than none, because it looks closed.
2. **The digest is an instruction, not a reading list.** It ships domains and angles, not
   3,000 raw URLs — a URL dump would blow the agent's context and defeat the point. Its
   load-bearing line: *if every angle you try lands back on covered ground, that is the
   signal to report `exhausted=true`, NOT to invent breadth.* An agent that manufactures
   long-tail noise to look productive is the failure this register exists to catch.
3. **The dedup key must be the sweep's own key, character for character.** Get it wrong and
   the register silently UNDER-reports coverage — which is worse than no register, because it
   licenses a re-run while claiming it did not. The current key (workflow + register + verifier
   all agree): `trim → lowercase → drop #fragment → drop ?query → strip trailing /`.
   Whenever the sweep's normalisation changes, re-verify with an independent transcription
   (§4b fresh-context re-derivation) — do NOT import the register's own function to check itself.
4. **`ingest` is idempotent; re-run it at completion.** Mid-flight, `citations[]` from later
   phases are not in the journal yet and the run's stop cause reads `in-flight`. Re-ingesting
   when the run finishes folds in the late sources and resolves the stop cause. Re-running it
   costs nothing and adds no duplicates (keyed on the normalised URL).
5. **Provider attribution is agent free-text, not telemetry.** The same provider shows up under
   several spellings (measured 2026-09-25: firecrawl under four, exa under three). Never quote
   a single provider row as a measured total; sum the spellings or say "self-reported".
6. **Report coverage honestly** (§7): a run that terminated because it hit its round cap is
   CAP-BOUNDED, not converged. Say which. `exhausted` counts in the register are what
   distinguish the two — read them before claiming a sweep finished.

Sibling: `rules/common/web-search-discipline.md` rule 3 ("Cache + don't re-query") is the
WITHIN-run counterpart of this CROSS-run register — that one stops you double-querying inside a
sweep, this one stops the next sweep repeating the last. Also `rules/common/context-reduction.md`
(aggregates in-session, raw payloads to disk). Evidence: `scripts/research-coverage.py` +
`knowledge/RESEARCH-COVERAGE.md`, built from run `wf_a2bae891-84b`'s own journal with zero
provider calls and independently verified set-identical (0 missing / 0 extra / 0 duplicate keys),
2026-09-25.