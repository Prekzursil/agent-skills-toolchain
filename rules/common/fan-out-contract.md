---
paths:
  - "**/.claude/**"
  - "**/.agents/**"
---

# Fan-Out Contract (spawn prompts and fan-in gates)

Measured over 50 agents / 6 workflows, 2026-07-18. Element presence in the prompt predicts
compliance almost perfectly; nothing is inherited from the global contract.

## A. AGENT-FACING — what every fan-out prompt MUST carry

1. **Re-state the honesty instrumentation every time. It does NOT spill over.**
   The 8 lens docs (~190 KB) whose prompt omitted it scored **0 UNVERIFIED tags, 0 URLs**;
   named fields scored 26-62 hits each. Zero inheritance from AGENTS.md §7 was measured.

2. **Enumerate the vocabulary; never ship a bare tag name.**
   Sherman-Kent bands listed inline → **20/21 (95%)** adoption. `NATIVE-vs-BUILD` as a bare tag
   with no value set → **7/21 (33%)**, the most-dropped field in the corpus despite being
   load-bearing. Either enumerate the values or delete the field.

3. **UNVERIFIED must be INLINE, adjacent to the claim.**
   127 real flags, but **40% (51) sit in the final 15%** of their document. Measured damage:
   `D2-harness-queue.md:31` promoted a Tier-0 build item on a "double-fire confirmed" premise
   that line 293 admits was never checked — and an adversarial reviewer disproved it. Required
   wording: *"Attach UNVERIFIED inline to the sentence it qualifies. A limitations section at the
   end does not satisfy this. If a recommendation's premise is UNVERIFIED, the recommendation
   inherits the tag in its heading."* Every UNVERIFIED names the experiment that would settle it.

4. **A briefed fact needs a probe tag, a timestamp, and a MECHANICALLY DIFFERENT re-probe rule.**
   Disclosing that a fact might be stale is not enough: on "`mon` is NOT on PATH", 4 agents
   correctly refuted it while **2 "CONFIRMED" it by re-running the orchestrator's own broken
   Git-Bash `which`** — complete with dutiful evidence tags. Evidence-tag theatre. Require: *"To
   confirm OR refute you MUST use a different shell, a different data field, or a different
   measurement. Re-running the tagged probe does NOT count and must not be reported as
   CONFIRMED."* Four briefed "VERIFIED GROUND TRUTH" facts were false in one run.

5. **A path must carry its access method** whenever it is not readable by `Read` at that literal
   path. `tools/monitorcore` (main-only) cost **7 agents** independent rediscovery. One line
   fixes it: *"exists ONLY on origin/main — read via `git show origin/main:<path>`."*

6. **Specify the output MECHANISM, not vendor-specific syntax**, and cap the chunk size. A
   PowerShell here-string contract is vendor-fragile: 21/21 for Claude agents, but a direct
   contributor to the Codex-rail transport failure.

7. **Keep the ≤350/400-word digest cap.** It was NOT lossy — median 340 words, 4/40 over (worst
   +12%), and **4/4 correcting agents led their digest with the correction.** The cap forced
   prioritisation and agents prioritised correctly.

8. **Long ground-truth blocks earn their tokens.** A ~1,100-word block correlates with 18-44 tool
   calls and 2-49 citations per agent; a 3.8 KB prompt with no ground-truth block correlates with
   2-7 tool calls and **zero** citations. The cost ceiling is transport, not attention.

9. **Split the evidence standard by lens type.** GROUNDED lenses must cite `file:line`; IDEATION
   lenses must cite an external domain source and be told explicitly NOT to ground in the repo
   (5.0 tool calls/agent, zero duplicate reads, 177 KB usable output). Holding an ideation lens to
   a repo standard, or accepting ungrounded prose from a grounded one, is the failure.

10. **Freeze the preamble and launcher once the first unit launches.** Editing mid-run leaves
    contradictory instructions live (one run had `PLAN.md:26` "UNDER ~30 tool calls" against a
    revised launcher saying "there is NO tool-call cap"). To revise: kill cleanly, delete
    partials, restart.

11. **Inject a shared grounding pack.** 16/25 agents read the same `codex_monitor.py`; 13/25 the
    same `codex-monitor.md`; one agent re-read `hub.py` **×22**. One grounding agent producing a
    pinned digest removes an estimated 60-90 tool calls in a single 39-agent workflow — and kills
    the mid-flight split-brain that let 8 agents ship a premise fixed while they ran. Cap
    intra-agent re-reads of one path at ~4, then read it wide once.
    **The generator now exists** — on `main` since `#166` — but its path is repo-relative, so per
    §A5 pass the ABSOLUTE form (`<checkout>` = the `agent-skills-toolchain` tree) or it dies with
    `[Errno 2]` from any other cwd: `python <checkout>/tools/repomap/repo_map.py --root <checkout>
    --budget 900 --out <artifact-root>/GROUNDING-PACK.md`. It ranks the tree by PageRank over symbol
    references, sized to a token budget. Build ONCE, inline it, freeze per §A10; see its README.

12. **Pin the artifact root and `ls` it in the prompt** — 10 `Read` failures were pure cwd
    confusion.

## B. ORCHESTRATOR-FACING — fan-in gates

1. **`Test-Path` every contracted output BEFORE reading any digest.** 3/3 Codex agents returned
   plausible digests for files that do not exist. A digest is a claim, not a receipt.
2. **Reject any result containing `started in the background` or `Check /codex:status`.** Cheap
   regex; catches the entire fire-and-forget class outright.
3. **Require an `EVIDENCE:` block of 3-5 `file:line`/URL anchors, EXEMPT from the word cap.**
   87% of file:line refs and 100% of URLs currently die at the digest boundary.
4. **On a split verdict about a briefed fact, the specific probe wins over the agent count.**
   Read the probes; do not vote. (2 agents "CONFIRMED" a false fact with a broken detector.)
5. **Digest silence is not absence of caveats** — 18 UNVERIFIED tags survive into 30 digests
   against 127 in the docs. Open the doc before treating a claim as unqualified.
6. **Give adversarial reviewers the siblings' FULL text, not digests.** This was the single
   highest-value structural choice in the corpus — the only mechanism that caught the false
   double-fire premise and duplicate-skill bloat. Also give reviewers a durable artifact contract:
   540,583 tokens of adversarial review currently leave **zero** on-disk artifact.
7. **Never score agents on output volume.** The best verification agent in the corpus is near the
   bottom on KB/token. Any productivity gate must exempt falsification work or it selects against
   exactly the behaviour the harness most needs.


## C. SUBAGENT DURABILITY — measured PROMPT-1.5 (2026-07-21)

### C1. WRITE AS YOU GO. A unit that holds results in memory is a total-loss risk.

Measured: one review unit ran **70 minutes**, produced **691 KB** of transcript, completed a full
mutation harness — then froze and wrote **nothing**. Unrecoverable. A relaunched unit under a
write-as-you-go mandate produced a truthful artifact within 3 minutes and survived every later check.

Mandate for any unit expected to run >10 minutes:
  1. Write the artifact IMMEDIATELY as a skeleton with every claim enumerated and marked
     `UNKNOWN - not yet measured`, plus a COVERAGE line naming which sections are unmeasured.
  2. REWRITE it at each milestone (per lane / per phase).
  3. Whatever is on disk must ALWAYS be truthful. A partial file with honest UNKNOWNs is a SUCCESS;
     a perfect file that never gets written is a total loss.
Include the sentence: *"If it still reads this way, the unit died before measuring anything and no
verdict here may be cited."*

Note: the freeze cause was NOT an unbounded external probe (measured: 0 hung git/git-crypt
processes). Bounding probes is good hygiene but did not address it. **Write-as-you-go is the fix
that makes the cause irrelevant.**

### C2. Most refutations are OVERCLAIMS, not broken fixes — 5 of 8 measured.

Across three lanes and four adversarial reviews, the refuted claims were:
  `recall = 1.0` . `FP=0 / FN=0` . "three holes closed" . "asserted by a test" .
  `COVERAGE_GAPS #6 states X as fact`
In every one, **the code was correct and the sentence was wider than the evidence**. Only 3 of 8
were genuine defects, and each closed in a single round.

Consequences:
  * A "round N until fully green" stopping rule is **tractable, not unbounded** — convergence comes
    from scoping claims to their evidence, not from closing every conceivable gap.
  * On a REFUTED overclaim, fix the SENTENCE: state the scope measured, disclose the residual
    INLINE, name the settling experiment. A correctly-scoped claim is CONFIRMED.
  * A residual gap that is honestly scoped and disclosed is NOT a refuted item and must NOT block.
  * Record that the earlier wording was REFUTED — do not silently delete it to make the problem
    disappear.
  * Reviewers: an overclaim is a REFUTED verdict **even when the underlying code is fine**. Say so,
    and give the correctly-scoped version.

### C3. `mergeStateStatus: CLEAN` is evaluated in ISOLATION and hides PR-to-PR overlap.

It answers "does this merge into main *right now*", not "do these N PRs stack". Check pairwise file
overlap yourself. But overlap is not automatically conflict: if the overlapping content is
**byte-identical** (one PR contains the other's work), whichever merges second is a no-op. Measured:
7 "CLEAN" PRs looked mutually conflicting and were fully stackable.

### C4. Do NOT fan out a MECHANICAL comparison to LLM judgement — measured 2026-07-21.

Task: classify 338 files as repo-ahead / live-ahead / diverged / noise, to decide which were safe to
overwrite. Six Opus agents were given the work-list, an enumerated verdict vocabulary, a worked
counter-example proving the mtime heuristic wrong, and an explicit instruction to classify by CONTENT.

Scored against a 40-line deterministic differ:

| | |
|---|---|
| agent accuracy | **86%** (291/338) |
| disagreements | 47 |
| errors in the DANGEROUS direction (said safe, was DIVERGED) | **31** |
| errors in the safe/over-cautious direction | **0** |

**Every disagreement was the DIVERGED case** - both sides holding unique content - misread as
DEPLOY-SAFE or NOISE-ONLY. The blind spot is systematic: the agents checked whether the REPO had
extra content and stopped, never checking whether LIVE also had unique lines. A one-directional read
cannot see two-directional divergence.

Deploying on those verdicts would have destroyed content in 31 files, including
`hooks/_shared/completion.py` and `hooks/_shared/test_completion.py`.

**86% accuracy is the wrong metric. Error DIRECTION is the metric.** 100% of the errors pointed at
data loss. A differ has no such bias, ran in seconds, and was exact.

RULE: if a question is answerable by an exact algorithm - byte/line comparison, set membership,
counting, hashing - WRITE THE ALGORITHM. Reserve agents for what code cannot do: judging whether the
divergent content MATTERS, summarising what a change means, weighing a trade-off. In this task the
right split was: differ classifies all 338, agents describe the 10 behaviour-bearing DIVERGED files.
Handing the classification to agents cost six Opus runs and produced a result that could not be used.


## D. Dispatch-time RAM gate (2026-10-13) — ENFORCED, not advisory

`mcp-process-hygiene.md` already carries the HARD pre-flight ("run `mcp_ram_audit.ps1` before ANY
workflow / fleet / second-session launch") and the "NO multi-agent fleets < 8 GB" floor — but the
2026-10-13 audit found ZERO references to either in the workflow registry or any workflow body:
the gate existed on paper only. This section binds it to the dispatch boundary.

**Before ANY Workflow / parallel fan-out / multi-agent fleet launch, the ORCHESTRATOR runs
`C:\Users\Prekzursil\.agents\scripts\mcp_ram_audit.ps1` and branches on the free-RAM reading:**

1. **< 4 GB free** -> sequential implements only: **concurrency 1**. No parallel lanes launch;
   work units run one at a time, each joined per `cross-vendor-dispatch.md` §1 before the next
   starts.
2. **< 2 GB free** -> **postpone non-urgent fan-outs** entirely (reschedule, or degrade to a
   single agent with the smallest viable scope). Urgency waives the postponement, never the audit.
3. **Evidence, not intent.** The gate is satisfied ONLY by a **logged RAM reading in the launch
   receipt** — the free-GB value + timestamp from the audit. A fan-out launched without that
   logged reading violates this gate regardless of how the launch turned out.

This is the dispatch-time companion to the 8 GB fleet floor: that rule caps how BIG a fleet may
be; this gate decides whether any fan-out launches at all. Both hold — neither substitutes for
the other.
