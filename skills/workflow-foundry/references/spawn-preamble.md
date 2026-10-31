---
title: spawn-preamble
type: note
permalink: dqverify-repo-20261013/skills/workflow-foundry/references/spawn-preamble
---

# The spawn preamble — copy, fill the angle brackets, ship

Nothing is inherited. MEASURED: 8 lens documents (~190 KB) whose prompt omitted the
honesty instrumentation scored **0** UNVERIFIED tags and **0** URLs, while prompts that
named the fields scored 26-62 hits each (`rules/common/fan-out-contract.md:8`, §A1). Zero
spill-over from the global contract into a subagent was measured. Restate it every time.

Freeze this text at the moment unit 1 launches (L1). If you must revise: kill cleanly,
delete partials, restart.

---

```
## FROZEN CONTEXT (do not re-derive; DO verify anything load-bearing)

TREE: <repo> @ <SHA>            <-- pinned; every file:line you cite must resolve here
ARTIFACT ROOT: <abs path>       <-- ls of that dir, inline, below
  <paste the actual `ls` output here — 10 Read failures in one corpus were pure cwd confusion>

GROUNDING PACK: <abs path>      <-- built ONCE, frozen; do not rebuild mid-run
  python <checkout>/tools/repomap/repo_map.py --root <checkout> --budget 900 \
    --out <artifact-root>/GROUNDING-PACK.md
  (ABSOLUTE paths only — it dies with [Errno 2] from any other cwd)

## YOUR EXCLUSIVE FILE SCOPE
  <path glob>            <-- you own ONLY this. Siblings run in parallel on disjoint scopes.
If your fix needs a file another unit owns: STOP and report it. Do not edit it.

## PATHS THAT NEED AN ACCESS METHOD
  <path>  -- exists ONLY on origin/main; read via `git show origin/main:<path>`
  <path>  -- inside a container; read via <cmd>
(A main-only path cost 7 agents independent rediscovery. One line fixes it. §A5)

## BRIEFED FACTS — each with its probe, its timestamp, and a DIFFERENT re-probe rule
  FACT: <claim>   PROBE: <exact command>   AS-OF: <ts>
  To CONFIRM or REFUTE you MUST use a different shell, a different data field, or a
  different measurement. Re-running the tagged probe does NOT count and must not be
  reported as CONFIRMED.
(4 agents correctly refuted one briefed fact; 2 "CONFIRMED" it by re-running the
orchestrator's own broken Git-Bash `which`. Evidence-tag theatre. §A4)

## HONESTY INSTRUMENTATION (restated in full — it does not spill over)

Confidence bands, use these words: almost-certain 90-99% | likely 55-80% |
roughly-even 45-55% | unlikely 20-45% | remote 1-20%.
Pair every band with its evidence tag: MEASURED | CITED | INFERRED | ASSUMED.

UNVERIFIED goes INLINE, in the sentence it qualifies. A limitations section at the end
does NOT satisfy this. If a recommendation's premise is UNVERIFIED, the recommendation
inherits the tag IN ITS HEADING. Every UNVERIFIED names the experiment that would settle
it. (127 real flags in one corpus; 40% sat in the final 15% of their document. §A3)

## EVIDENCE STANDARD FOR YOUR LENS TYPE
  [ ] GROUNDED  — cite `file:line` for every claim. Do not speculate beyond the tree.
  [ ] IDEATION  — cite an external domain source. Do NOT ground in this repo.
(Holding an ideation lens to a repo standard, or accepting ungrounded prose from a
grounded one, is the failure. §A9)

## WRITE AS YOU GO — total-loss risk otherwise
Write <artifact path> IMMEDIATELY as a skeleton with every claim marked
`UNKNOWN - not yet measured`, plus a COVERAGE line naming the unmeasured sections.
REWRITE at each milestone. What is on disk must ALWAYS be truthful.
Include this sentence: "If it still reads this way, the unit died before measuring
anything and no verdict here may be cited."
(One unit ran 70 min, produced 691 KB, wrote nothing. Unrecoverable. §C1)

## BOTH-STATES
For every fix or detector: run the probe against the KNOWN-BROKEN state and confirm it
FIRES, then against the fixed state and confirm silence. Report both. A probe silent in
both states measures nothing. A control that cannot fail is not a control.

## MECHANICAL WORK IS NOT YOURS
If a question is answerable by an exact algorithm — byte/line comparison, set membership,
counting, hashing, existence — WRITE THE ALGORITHM and run it. Do not judge it by reading.
(Six Opus agents classifying 338 files: 86% accurate, 47 disagreements with a 40-line
differ, 31 of them in the DANGEROUS direction, 0 over-cautious. §C4)

## OUTPUT CONTRACT
Write to: <exact abs path>            <-- the orchestrator Test-Paths this before reading
End the file with a line that is EXACTLY:  UNIT-COMPLETE: <your unit id>
  (its own line, nothing else on it — a substring elsewhere in the tail does not count)
Minimum <N> bytes.

DIGEST: <=350 words.
EVIDENCE: 3-5 `file:line` or URL anchors — EXEMPT from the word cap.
  (87% of file:line refs and 100% of URLs otherwise die at the digest boundary. §B3)

FIRST LINE of your return, always one of:
  SUCCESS:<unit-id> <headline>
  FAILED:<unit-id> <reason>
Never return nothing. Never return a job id, "started in the background", or
"Check /codex:status" — those are rejected on sight and the work is lost.
```

---

## Elements that are load-bearing and get dropped most

| element | measured adoption | note |
|---|---|---|
| Sherman-Kent bands **enumerated inline** | **20/21 (95%)** | list the values |
| a bare `NATIVE-vs-BUILD` tag, no value set | **7/21 (33%)** | most-dropped field in the corpus |
| honesty block omitted entirely | **0/8 docs** carried any tag | zero inheritance |

Enumerate the vocabulary or delete the field (§A2). A bare tag name is worse than no tag —
it manufactures the appearance of instrumentation.

## Digest cap: keep it

MEASURED NOT lossy — median 340 words, 4/40 over the cap, worst +12%, and **4/4**
correcting agents led their digest with the correction (§A7). The cap forced
prioritisation and agents prioritised correctly. Keep it, and keep the `EVIDENCE:` block
exempt.

## Long ground-truth blocks earn their tokens

A ~1,100-word ground-truth block correlates with 18-44 tool calls and 2-49 citations per
agent. A 3.8 KB prompt with **no** ground-truth block correlates with 2-7 tool calls and
**zero** citations (§A8). The cost ceiling is transport, not attention.