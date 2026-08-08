---
name: workflow-foundry
description: Use when RUNNING a multi-agent fan-out on this estate — dispatching N parallel work units, deciding barrier-vs-pipeline, gating fan-in, or judging whether a unit is actually done. The operating contract distilled from measured runs here, not generic advice: freeze the SHA and the spawn preamble before the first unit launches; fan in on RECEIPTS (Test-Path every contracted output BEFORE reading any digest — 3/3 agents once returned plausible digests for files that did not exist); UNIT-COMPLETE is a string the unit writes about itself, not proof; pipeline by default and use a barrier only when stage N genuinely needs ALL of stage N-1; write-as-you-go (a 70-minute unit produced 691 KB and wrote nothing, unrecoverable); both-states controls (a probe silent in the broken state measures nothing); never fan a MECHANICAL comparison out to LLM judgement (measured 86% accuracy with 100% of errors in the dangerous direction against an exact 40-line differ); per-needle deferral is the wrong LAYER and recurses, only a role-aware discriminator terminates; adversarial verifiers get siblings FULL text not digests; and most refutations are OVERCLAIMS where the code was right and the sentence was too wide — fix the sentence. Ships a runnable receipt gate with a built-in both-states self-test. Triggers include fan out N agents, gate the fan-in, is this unit done, my parallel phase deadlocked, an agent returned a digest for a missing file, design the work-unit decomposition, review the siblings adversarially. NOT for writing the workflow .mjs runtime code (use workflow-authoring), NOT for the cross-vendor Codex dispatch transport (use cross-vendor-dispatch and multi-ai-mingle), NOT for remote compute placement (use codex-databricks-fanout).
---

# workflow-foundry

The **run-time operating contract** for a fan-out on this estate. Ten laws, each one paid
for by a measured failure here. Every number below is MEASURED; do not re-derive it from
first principles and do not soften it because a run "looks fine".

**Where this sits.** `workflow-authoring` tells you how to WRITE the `.mjs` (the injected
`agent`/`parallel`/`phase` globals, the args-as-string gotcha, the `Date.now()` ban).
`cross-vendor-dispatch` owns the Claude→Codex transport. `codex-databricks-fanout` owns
remote compute placement. **This skill owns what happens between "launch" and "done".**

**The card catalogue is elsewhere.** 108 named blueprint cards live in
`~/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.md` (464 KB). This skill
is the contract those cards must satisfy, not a copy of them. Pick a card there; obey the
laws here.

Evidence anchors with access methods: `references/evidence-index.md`. Read it before citing
any rule path — the live `~/.claude/rules/common/` tree was measured EMPTY on 2026-08-08
while its content was still being injected into sessions, so the durable citation is the
repo copy, not the live path.

---

## L1 — Freeze before you fan out

Freeze **three** things the moment the first unit launches, and change none of them until
the cohort is dead:

1. the **commit SHA** every unit reads (record it in the preamble, so all N sets of
   `file:line` citations resolve against one tree),
2. the **spawn preamble**,
3. the **launcher**.

MEASURED: editing mid-run left contradictory instructions live in one run — `PLAN.md:26`
said "UNDER ~30 tool calls" while a revised launcher said "there is NO tool-call cap".
Units obeyed different contracts and their outputs were not comparable
(`fan-out-contract.md:54`, §A10).

To revise: **kill cleanly, delete partials, restart.** A hot-patched cohort is not a cohort.

Corollary — **freeze also means the units must not race each other.** Give every mutating
unit a **file-disjoint scope** and state it in the preamble. Parallel agents share one git
index; a broad `git add` has swept siblings' in-flight work here before.

## L2 — Fan in on RECEIPTS, never on digests

**`Test-Path` (or `os.path.exists`) every contracted output BEFORE reading any digest.**

MEASURED: **3/3** Codex agents returned plausible, well-formed digests for files that **do
not exist** (`fan-out-contract.md:70-71`). A digest is a *claim*. Only the artifact is a
*receipt*.

Two cheap regex rejects that kill an entire failure class outright
(`fan-out-contract.md:72`, `cross-vendor-dispatch.md:12`):

- reject any result containing `started in the background`
- reject any result containing `Check /codex:status`

A backgrounded unit's result is unreachable in practice, so a job-id receipt is a silently
lost work unit, not a pending one.

**Run the gate, do not eyeball it:** `scripts/receipt_gate.py` (stdlib only, no deps).

```
python scripts/receipt_gate.py --manifest units.json
python scripts/receipt_gate.py --manifest units.json --strict     # exit 1 if not all DELIVERED
python scripts/receipt_gate.py --self-test                        # both-states control (L6)
```

It emits exactly one typed verdict per unit —
`DELIVERED | MISSING | UNDERSIZE | NO-TRAILER | NOT-CHECKED` — and **`NOT-CHECKED` is a
first-class outcome**, never folded into DELIVERED and never silently dropped. A unit whose
artifact could not be read (permission, decode error, path that is a directory) must say
"I could not tell". Details and the manifest schema: `references/receipt-gate.md`.

**Prior art exists — read it before writing a third gate.**
`~/scratch/codex-auth-research-fanout/completion_predicate.py` (144 lines, with tests) is
the estate's C1 predicate and is **complementary**: it folds process liveness (pid, CPU
delta, log staleness, husk detection) in with the artifact AND-gate to answer *"should I
keep waiting?"*. `receipt_gate.py` answers only *"is the artifact really there?"*. Use
both. The measured differences — and one executable-proven hole — are in
`references/receipt-gate.md`.

## L3 — `UNIT-COMPLETE` is text, not proof

The estate's own reference fan-out declares
(`~/.claude/workflows/codex-auth-research-fanout.mjs:27-28`):

```
DONE   = artifact >= 1024 B AND ends with UNIT-COMPLETE: <id>
IGNORE = CODEX THREADS idle / rollout mtime / process exit alone
```

and repeats at `:63` that *"CODEX THREADS IDLE is NOT done — only disk UNIT-COMPLETE is
done"*.

That AND-gate is **correct and much stronger than process exit** — it defeats the whole
fire-and-forget class. But be precise about what it proves: **the trailer is a string the
unit writes about itself.** It proves the unit reached its own writer. It does **not**
prove the content is right, and a unit that writes 1 KB of skeleton plus the trailer
passes.

Escalation ladder — climb only as far as the decision needs, and say where you stopped:

| rung | signal | what it actually proves |
|---|---|---|
| 0 | process exit 0 / thread idle / mtime | **nothing.** Explicitly ignored here. |
| 1 | artifact exists | the unit got as far as opening a file |
| 2 | + byte floor | it wrote something, not an empty stub |
| 3 | + `UNIT-COMPLETE: <id>` trailer | it reached its own end-of-work marker |
| 4 | + parses against the fan-in schema | the shape is right |
| 5 | + an **independent postcondition probe** | the content is right |

Rungs 1-4 are self-declared. Only rung 5 is external. Never report a rung-3 result in
rung-5 language.

**Bind the trailer to the declared unit id, never to the filename.** MEASURED 2026-08-08
over the 55 real artifacts in `~/scratch/codex-auth-research-fanout/artifacts/`: **1 of 55**
has a filename stem that differs from its trailer id (`auth-infra/auth-source-map.md`
carries `UNIT-COMPLETE: auth-src-map`). A gate keyed on the stem reports that unit
not-done forever — a false negative indistinguishable from a dead agent. Carry the id in
the manifest.

## L4 — Pipeline by default; a barrier only when stage N needs ALL of stage N-1

`parallel()` waits for every thunk and has **no per-agent timeout**, so one hung unit
stalls the entire phase; a *throwing* thunk resolves to `null` rather than rejecting, so
**`.filter(Boolean)` after every barrier** or you dereference a null.

Default to **per-work-unit pipelines** (unit U runs implement→validate→review→commit on its
own thread) and reach for a barrier only where stage N genuinely consumes ALL of stage N-1
— a synthesis, a cross-unit ranking, a stacking-order decision. Most "phases" are barriers
by habit, not by need.

MEASURED caveat that is easy to miss: **`pipeline()` is NOT a cacheable unit — resuming a
stopped pipeline RE-RUNS its first stage**
(`09-WORKFLOW-BLUEPRINT-LIBRARY.md:1767`). Budget the re-run, or make stage 1 idempotent
and cheap.

## L5 — Write as you go

MEASURED: one review unit ran **70 minutes**, produced **691 KB** of transcript, completed a
full mutation harness — then froze and wrote **nothing**. Unrecoverable. A relaunched unit
under a write-as-you-go mandate produced a truthful artifact in **3 minutes** and survived
every later check (`fan-out-contract.md:91-95`, §C1).

Mandate for any unit expected to run >10 minutes:

1. Write the artifact **immediately** as a skeleton with every claim enumerated and marked
   `UNKNOWN - not yet measured`, plus a COVERAGE line naming the unmeasured sections.
2. **Rewrite** it at each milestone (per lane / per phase).
3. What is on disk must **always** be truthful. A partial file with honest UNKNOWNs is a
   SUCCESS; a perfect file that never gets written is a total loss.

Put this sentence in the artifact: *"If it still reads this way, the unit died before
measuring anything and no verdict here may be cited."*

The freeze cause was **not** an unbounded external probe (measured: 0 hung git processes).
Bounding probes is good hygiene but did not address it. Write-as-you-go makes the cause
irrelevant.

## L6 — Both-states, or it does not count

Before a probe's silence counts as "clean", run it against the **known-BROKEN** state and
confirm it **FIRES** there (`single-signal-verification.md:40`, rule 3b).

**A control that cannot fail is not a control.** A "control" that printed a reassuring
message while both its numbers were 0 shipped on this estate.

- Applied to a test suite, this is **mutation testing** — revert the real bug and require
  the suite to go red. A suite that stays green is not protecting that behaviour.
- Applied to a fan-in gate, it means: delete an artifact, truncate one below the floor,
  strip one trailer — and confirm the gate reports `MISSING` / `UNDERSIZE` / `NO-TRAILER`
  **before** you trust it reporting `DELIVERED`.

`scripts/receipt_gate.py --self-test` does exactly that on throwaway fixtures and reports
`CONTROL-OK` only when the gate fires on all six broken shapes **and** is silent on the
good one. If either half fails it prints `CONTROL-BROKEN` and exits non-zero — the gate's
verdicts are then uncitable.

### Independence must hold across TIME, not just mechanism

MEASURED 2026-08-08, by this skill's own lane, against itself: two mechanically
independent probes — Git Bash `ls -la` and PowerShell `Get-ChildItem -Force -Recurse` —
both reported `~/.claude/rules/common/` **empty**, and that was written up as a finding.
It was wrong. A concurrent lane was mid-write; the gate's own `INV-6-rules-common`
(`check_no_regression.py:445`, globbing that exact path) reported `n=20 missing=[]` minutes
later, and a re-probe listed all 20 files.

Both probes were run at the **same instant**. For a **mutating** resource that is **one
observation, not two.** Different shell + different API buys you independence of
*mechanism*; it buys nothing against a transient. When the subject can change under you —
a directory a sibling lane is writing, a process table, a lock file, a queue depth — the
second signal must be **separated in time**, and the claim must be scoped to the instant
it was taken: not *"the directory is empty"* but *"the directory was empty at 02:17"*.

A standing property inferred from a single time point is an overclaim even when the
instrument is perfect. That is L10 reproduced by the lane documenting L10.

**And: read the instrument you are already running.** The refutation came from a gate this
lane was required to run anyway. It cost nothing and had been available the whole time.

## L7 — Never fan a MECHANICAL comparison out to LLM judgement

MEASURED, six Opus agents classifying 338 files as repo-ahead / live-ahead / diverged /
noise, given the work-list, an enumerated verdict vocabulary, a worked counter-example, and
an explicit instruction to classify by CONTENT (`fan-out-contract.md:140-165`, §C4):

| | |
|---|---|
| agent accuracy | **86%** (291/338) |
| disagreements with a 40-line differ | 47 |
| errors in the DANGEROUS direction (said safe, was DIVERGED) | **31** |
| errors in the safe / over-cautious direction | **0** |

Every disagreement was the two-sided DIVERGED case read as one-sided. Deploying on those
verdicts would have destroyed content in 31 files.

**86% accuracy is the wrong metric. Error DIRECTION is the metric** — 100% of the errors
pointed at data loss. The differ had no such bias, ran in seconds, and was exact.

RULE: if a question is answerable by an exact algorithm — byte/line comparison, set
membership, counting, hashing, existence — **write the algorithm.** Reserve agents for what
code cannot do: judging whether the divergent content MATTERS, summarising what a change
means, weighing a trade-off. The right split in that task was: differ classifies all 338,
agents describe the 10 behaviour-bearing DIVERGED files.

This law binds this skill too — which is why L2 ships a script and not a checklist.

## L8 — Per-needle deferral is the wrong LAYER; only a role-aware discriminator terminates

When a guard must decide whether a matched string is a real occurrence or merely
*mentioned* (a doc quoting a banned command, a hook matching its own name), the tempting
fix is to defer each ambiguous needle to a smarter check. **That recurses** — the deferral
record itself contains the needle, so the next pass matches it again.

The layer that terminates is a **role-aware discriminator** that judges the match by its
syntactic role. On this estate that is
`~/.claude/hooks/_shared/use_vs_mention.py` (41,045 B, 59 tests):

- `classify(text, span, context, kind) -> Judgement` at `:602`, verdict `USE | MENTION |
  UNKNOWN`
- `is_real_occurrence(...) -> bool` at `:788` (the bool projection)
- `audit_subject_rule(path)` at `:571`
- `Judgement` at `:164`
- an `ast`-exact string-literal rule **structurally** terminates the recursion

`UNKNOWN` is the point: the discriminator is allowed to say "I could not tell", and that
state surfaces rather than defaulting either way.

MEASURED: **16** use-vs-mention false fires in a single day here; three of them were a hook
matching the substring `todo` inside its own name `todo-surfacer` (the hyphen is a word
boundary). Wire the discriminator; do not hand-roll a per-needle exception list.

**This class reaches inside the completion gate itself.** MEASURED 2026-08-08 by executing
`completion_predicate.py:45`, which tests `f"UNIT-COMPLETE: {unit_id}" not in tail` — a
substring. Fed an artifact whose tail literally reads *"This unit did NOT finish and wrote
no trailer"* but which quotes the token in prose, it returns `ok=True,
reason="and-gate-pass"`. The same module's anchored extractor at `:141` returns `None` for
that same text: **the module disagrees with itself about whether the unit is done.**
Correctly scoped (L10) — over the 55 real artifacts the two forms agree 55/55, divergence
**0**, so the hole is executable-proven but LATENT in that corpus. The realistic trigger is
an L5 write-as-you-go skeleton echoing its own contract text into the tail (*likely*,
55-80%, INFERRED from the two measured facts; UNVERIFIED against a live run — settling
experiment: run both forms over in-flight skeletons rather than finished artifacts).
`receipt_gate.py` uses line-equality and keeps a `substring` fixture in its self-test so a
regression fails the control.

## L9 — Adversarial verifiers get siblings' FULL text, not digests

Giving reviewers the siblings' complete output was **the single highest-value structural
choice** in the measured corpus — the only mechanism that caught a false "double-fire
confirmed" premise and duplicate-skill bloat (`fan-out-contract.md:80`, §B6).

- **Digest silence is not absence of caveats**: 127 UNVERIFIED tags in the documents; only
  **18** survived into 30 digests (§B5). Open the document before treating a claim as
  unqualified.
- Give reviewers a **durable artifact contract**. 540,583 tokens of adversarial review in
  one program left **zero** on-disk artifact.
- **On a split verdict about a briefed fact, the specific probe wins over the agent count**
  (§B4). Read the probes; do not vote. Two agents once "CONFIRMED" a false fact by re-running
  the orchestrator's own broken detector.
- **Never score agents on output volume** (§B7). The best verification agent in the corpus
  is near the bottom on KB/token; a volume gate selects against exactly the behaviour you
  need.

## L10 — Most refutations are OVERCLAIMS — fix the SENTENCE

MEASURED: across three lanes and four adversarial reviews, **5 of 8** refuted claims were
cases where **the code was correct and the sentence was wider than the evidence** —
`recall = 1.0`, `FP=0 / FN=0`, "three holes closed", "asserted by a test". Only 3 of 8 were
genuine defects, and each closed in one round (`fan-out-contract.md:110`, §C2).

Consequences:

- A "round N until fully green" stopping rule is **tractable, not unbounded** — convergence
  comes from scoping claims to their evidence, not from closing every conceivable gap.
- On a refuted overclaim, **fix the sentence**: state the scope actually measured, disclose
  the residual **inline**, and name the settling experiment.
- A residual gap that is honestly scoped and disclosed is **not** a refuted item and must
  not block.
- **Record** that the earlier wording was REFUTED. Do not silently delete it — a deleted
  overclaim gets re-made.
- Reviewers: an overclaim is a **REFUTED** verdict *even when the underlying code is fine*.
  Say so, and supply the correctly-scoped version.

---

## The spawn preamble is not inherited — restate it every time

Nothing spills over from the global contract into a subagent. MEASURED: 8 lens documents
(~190 KB) whose prompt omitted the honesty instrumentation scored **0** UNVERIFIED tags and
**0** URLs; prompts that named the fields scored 26-62 hits each (`fan-out-contract.md:8`,
§A1). Zero inheritance was measured.

The copy-paste preamble carrying every mandatory element is
`references/spawn-preamble.md`. The elements it must never drop:

- **Enumerate the vocabulary; never ship a bare tag name.** Sherman-Kent bands listed inline
  → **20/21 (95%)** adoption; a bare `NATIVE-vs-BUILD` tag with no value set → **7/21 (33%)**,
  the most-dropped field in the corpus (§A2). Enumerate the values or delete the field.
- **UNVERIFIED inline, adjacent to the claim.** 127 real flags, but **40% (51)** sat in the
  final 15% of their document. A trailing limitations section does not satisfy this; if a
  recommendation's premise is UNVERIFIED, the recommendation inherits the tag in its heading
  (§A3).
- **A briefed fact needs a probe tag, a timestamp, and a MECHANICALLY DIFFERENT re-probe
  rule.** 4 agents correctly refuted "mon is not on PATH"; **2 "CONFIRMED" it by re-running
  the orchestrator's own broken Git-Bash `which`** — evidence-tag theatre. Re-running the
  tagged probe does not count and must not be reported as CONFIRMED (§A4).
- **Every path carries its access method** when it is not readable by `Read` at that literal
  path. A main-only path cost **7 agents** independent rediscovery; one line fixes it (§A5).
- **Pin the artifact root and `ls` it in the prompt** — 10 `Read` failures were pure cwd
  confusion (§A12).
- **Split the evidence standard by lens type.** GROUNDED lenses cite `file:line`; IDEATION
  lenses cite an external source and are told explicitly NOT to ground in the repo (§A9).
- **Keep the ≤350/400-word digest cap** — measured NOT lossy (median 340 words, 4/40 over,
  worst +12%), and 4/4 correcting agents led with the correction (§A7). Require an
  `EVIDENCE:` block of 3-5 anchors **exempt** from the cap (§B3) — 87% of `file:line` refs
  and 100% of URLs otherwise die at the digest boundary.
- **Inject a shared grounding pack** (§A11). Build once with
  `python <checkout>/tools/repomap/repo_map.py --root <checkout> --budget 900 --out <artifact-root>/GROUNDING-PACK.md`
  — pass the ABSOLUTE path or it dies with `[Errno 2]` from any other cwd. Cap intra-agent
  re-reads of one path at ~4.

## Windows transport (this box)

- **Prompt by FILE, never inline.** `CreateProcess` caps the command line at 32,767 chars;
  an inline prompt produced `payload_len=34472` → `os error 206` and killed two runs.
- **An apostrophe in a Bash-tool command body breaks the tool's own quoting** — 6+ killed
  calls in one session. Write the script with the Write tool and run `python <path>`; never
  inline `python -c '…'`, never a heredoc carrying backslashes.
- **Use forward slashes in git revisions** and the `--` separator.
- **A here-string PAYLOAD is scanned as if it were a command** — a markdown body quoting a
  destructive command gets blocked. Use the Write tool (measured 0/40 failures vs 8/59 for
  here-strings).

## Checklist before you call a fan-out done

1. Preamble + launcher + SHA frozen since unit 1 launched, unchanged. — L1
2. `receipt_gate.py` run; every unit typed; `NOT-CHECKED` surfaced, not folded. — L2
3. `--self-test` printed `CONTROL-OK` in this session. — L6
4. No result contains `started in the background` / `Check /codex:status`. — L2
5. Every claim reported at the rung it was actually measured at. — L3
6. Every mechanical question answered by an algorithm, not a vote. — L7
7. Reviewers received FULL sibling text and produced a durable artifact. — L9
8. Every refutation triaged overclaim-vs-defect; overclaims fixed as sentences and recorded. — L10
