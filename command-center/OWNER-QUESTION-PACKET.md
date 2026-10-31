---
title: OWNER-QUESTION-PACKET
type: note
permalink: dqverify-repo-20261013/command-center/owner-question-packet
---

# OWNER-QUESTION-PACKET

**Built 2026-08-09** · lane `side:questions` · source: `command-center/sources/REGISTER.md` §6 (27 questions)
plus `~/.claude/harness-restore-20260806/32-OWNER-DECISIONS.md` for full context.

Hand-written, NOT generated. `OWNER-DECISIONS.md` (generated) is the *list*; this is the *packet* —
each question re-probed against today's state, with options, a recommendation, and a default.

---

## THE HEADLINE

**Of 27 questions, 4 are worth your attention. 9 are already answered by events or by measurement
and should be closed without you. 14 are low-value and can be batch-answered in one line.**

I re-probed every one against today's state. The single most useful finding is negative:

> **The blocker that was described as gating the whole program — the 31-way `M-NN` id collision
> (finding F-B-02) — was already fixed on 2026-08-07 and nobody noticed.** Doc 13's mechanism
> options were re-prefixed `M-NN` → `MECH-NN`, 1:1, no renumbering, with a self-documenting mapping
> rule. **CONFIRMED, both-states control passes** (pre-fix backup: 38 `M-NN` / 0 `MECH-NN`; current
> file: 2 incidental `M-NN` / 38 `MECH-NN`; numeric parity exact).
> Evidence: `~/.claude/harness-restore-20260806/13-ARCHITECTURE-CANDIDATES.md:19-25` and
> `backups/13-ARCHITECTURE-CANDIDATES.md.pre-fb02` (2026-08-07 16:46).
> **Consequence: OQ-1 is a ratification, not an adjudication.** You are not being asked to
> disambiguate anything.
>
> **Independently cross-validated.** A separate lane reached the same verdict today by a different
> measurement — token-level rather than distinct-id: 107 substituted tokens, live file 0 bare
> `M-NN`. See `command-center/OPTION-ID-RESOLUTION.md` §0. Two agents, two extractors, one verdict.
> **Why it kept being cited as live:** `17-DECISION-LOG.md:175` still states the collision in the
> present tense and contains **zero** `MECH` tokens, so anyone pinning ground truth from the decision
> log inherits a fixed problem as an open one.

Second most useful: **all 123 `track: now` options already carry `dflt: ADOPT`** — every one, no
exceptions (`07-OPTION-UNIVERSE.json`, computed over all 283 records). So OQ-1 collapses from
"pick from 283" to "ratify 123, veto by exception".

| tier | what | count | your time |
|---|---|---|---|
| **0 — gates Prompt Two** | OQ-1, OQ-2 | 2 | 10 min |
| **1 — security / irreversible** | OQ-6, Q13 | 2 | 5 min |
| **2 — real value, cheap** | Q25, Q3, Q12, Q11, Q23, Q6 | 6 | 10 min |
| **3 — ANSWERED-BY-EVENTS, close without you** | OQ-3, OQ-4, OQ-5, OQ-8, Q10, Q15, Q19, Q20, Q22 | 9 | 0 min (read the closure) |
| **4 — low value, batch-answer** | Q9, Q14, Q16, Q17, Q18, Q21, Q24, OQ-7 | 8 | 5 min |
| **NEW** | M-36 — an owner-gated option nobody ever asked you about | 1 | 1 min |

Answer sheet at the bottom: every question, one line each.

---

# TIER 0 — THE TWO THAT ACTUALLY GATE PROMPT TWO

Both resolve to register item **R-A03** (the Prompt-Two entry inputs). Computed over
`DEPENDENCY-GRAPH.json` (21 edges, acyclic), R-A03 blocks **exactly 11 items**, all direct
successors:

`R-A02` Phase-0 baseline · `R-A06` marketplace · `R-A07` workflow foundry · `R-A08` executable
blueprints · `R-A09` council system · `R-A11` formal contracts · `R-A12` plugin lifecycle ·
`R-A13` deep-research product · `R-A15` benchmark tournament · `R-A16` self-improvement loop ·
`R-A17` release ceremony.

**Honest correction to a natural assumption:** Prompt Two *itself* (`R-A01`) is **not** on this
chain. The graph blocks it via `R-A31 ← {R-A28, R-A29, R-A30}` — and all three of those are listed
**Ready now** in `STATUS.md`. So OQ-1/OQ-2 do not gate Prompt Two's start; they gate the eleven
items above, which is still the largest single unblock available.

## OQ-1 — Which option IDs are selected for Prompt Two?

**Restated:** Prompt Two's entry input `[PASTE SELECTED OPTION IDS HERE]` is still a literal
placeholder. Which of the 283 catalogued options is the executor authorised to build?

**What the answer changes:** unblocks R-A03 and with it the 11 items listed above — the whole
build half of Program A (marketplace, foundry, blueprints, council, contracts, lifecycle, release).

**What is DIFFERENT today (why this is now easy):**

| fact | measured | anchor |
|---|---|---|
| id namespace is unambiguous | **CONFIRMED** — F-B-02 fixed 2026-08-07, `M-NN`→`MECH-NN`, 1:1 | `13-ARCHITECTURE-CANDIDATES.md:19-25`; both-states control vs `backups/…pre-fb02` |
| every option carries a default | **283 of 283** have a `dflt` field | `07-OPTION-UNIVERSE.json` `options[].dflt` |
| the "now" track is unanimous | **123 of 123** `track:now` options default to ADOPT | computed over all 283 records |
| owner-gated subset is small | **15** are `track:now` AND `owner:true` — they are exactly the questions in this packet | `owner:true`=70 total, 55 of them on platform/research tracks |

So the decision surface is: **123 now-track options (15 of which you are answering here anyway),
and 160 platform/research options that are explicitly NOT in this tranche.**

**The ids in THIS packet are unambiguous.** The resolution lane checked `32-OWNER-DECISIONS.md`
specifically: all 3 of its `M-NN` references settle as doc-07 option cards, **no rewrite needed**
(`OPTION-ID-RESOLUTION.md` §7a). So `M-29`, `M-31` and `M-36` below mean exactly one thing.

**One residual worth 30 seconds of your attention (it is an author call, not a blocker):** the
resolution lane counted **117** `M-NN` references outside the doc-07 family, of which **59 are
mechanically settled and 58 require the author to say which namespace was meant**. It also found a
**third** live `M-NN` namespace — `M-16` appears as a wave-3 deliverable id baked into deployed
`deep-research` skill text (20 refs / 16 files) — and a **near**-collision that is the dangerous
shape: doc-07 `M-18` = workflow *benchmark* harness vs doc-13 `MECH-18` = workflow *certification*
harness, both plausible in almost any sentence. None of this blocks OQ-1; it is cleanup that should
be scheduled, not answered.

**Options:**

- **(a) Ratify all 123 `track: now` defaults as the selected set.** Simplest. Risk: you have not
  read 108 of them individually, so you are trusting the `dflt` field authored by the option lanes.
- **(b) Ratify the 123 *by exception* — "all of track:now except the ids I name".** Same coverage,
  but you keep a veto and the veto list is auditable. Costs one extra pass over the 15 owner-gated
  titles (they are listed in the answer sheet).
- **(c) Hand-pick from all 283.** Highest fidelity, and it is exactly the weeks-long adjudication
  you have been avoiding. Not recommended — and no longer necessary now the namespace is clean.
- **(d) Ratify a bounded first tranche only** (e.g. the 15 owner-gated + the ~20 S-effort items),
  prove the pipeline, then ratify the rest. Slowest to full value, smallest blast radius.

**Recommendation: (b), ratify-by-exception.** *Likely (70-85%).* Evidence: the now/platform/research
split was authored precisely as a staging boundary, and the 123 now-track options are unanimous on
ADOPT — a set with zero internal disagreement is a set you can ratify wholesale. (b) over (a) purely
because a recorded veto list makes the ratification falsifiable later; (b) over (d) because the
dependency graph (`DEPENDENCY-GRAPH.json`, 21 edges, acyclic) already serialises execution, so a
smaller tranche buys safety the graph is already buying.

**Against me:** you have not read 108 option bodies, and `dflt` was written by the same lanes that
proposed the options — that is a same-author signal, the estate's most-repeated failure mode. If
that bothers you, (d) is the honest answer and costs one extra cycle.

**Default if you never answer:** Program A stays blocked permanently; 11 items never start; the next
executor either stalls or silently invents a selection — which is precisely the paraphrase-drift
that produced the unapproved 50× de-scope (OQ-4).

---

## OQ-2 — Owner overrides and priority ordering?

**Restated:** in what order should the selected work run, and what do you want to override?

**What the answer changes:** same gate (R-A03). Also determines whether the executor follows the
register's own critical path or invents one.

**What is DIFFERENT today:** an ordering already exists and is machine-checked. `REGISTER.md` §5
gives 9 ordered steps with reasoning; `DEPENDENCY-GRAPH.json` holds 21 edges and is **acyclic**;
`STATUS.md` renders "Ready now" (50 items with no open dependency) and "Blocked" (19). So the ask is
not "invent an order" — it is "ratify or amend one".

**The existing order, top 5:** 1. R-B08 live credentials · 2. R-B06 basic-memory notes ·
3. R-M01+R-M02 cockpit reachability · 4. R-A03+R-A04 this packet · 5. R-H01..H03 resume pointer.
Note **step 3 is already done** — `[cockpit]` is now present in all three `monitors.toml` copies
(CONFIRMED, three-file probe), so the live top of the list is really 1, 2, 4, 5.

**Options:**

- **(a) Ratify §5 as written.** Zero effort. Its #1 (the exposed credentials) is defensibly first.
- **(b) Ratify §5 but pin your own top 3.** You override only what you care about; the topological
  sort handles the rest.
- **(c) Supply a full ordering yourself.** Highest fidelity, highest cost, and the graph will
  reject any order that violates a dependency edge anyway.
- **(d) Say "no overrides — follow the dependency graph".** Fully mechanical, no human ordering at
  all; ties broken by effort ascending.

**Recommendation: (b).** *Likely (65-80%).* The register's ordering is evidence-backed and its
top item is the only one with a security blast radius, so it needs no correction — but "priority
ordering" is genuinely a value call about what you want to *see* working first, and (b) is the only
option that captures that without costing you an hour. Concretely I would pin:
**1) OQ-6 credential quarantine · 2) Q13 unregistered-clone review · 3) R-B06 memory notes**, then
let the graph run.

**Against me:** (d) is more honest. Any human ordering you give will be stale within a week, and the
graph is already correct; a pinned top-3 that ages badly is worse than no pin.

**Default if you never answer:** the executor invents an order. Measured cost of that last time:
the entire Prompt-Two de-scope.

---

# TIER 1 — SECURITY AND IRREVERSIBLE

## OQ-6 — `Diag 1.txt` live credentials: quarantine where, and blast-radius trace before or after?

**Restated:** a file holding third-party credentials tied to a corporate identity is sitting in
`~/Downloads/workflow_design/`. Where does it go, and do you want the "what else indexes this
directory" trace run first?

**STILL OPEN — CONFIRMED, and one day worse than the register says.**
Measured today by `stat` only (**I did not open the file, and I will not**):
`~/Downloads/workflow_design/Diag 1.txt` — **2,172,114 bytes, mtime 2026-07-21 17:23** = **19 days**
unactioned. The parent directory holds **21 entries**, including `Diag 2.txt` and eight other
`.txt` transcripts — so the exposure surface is plausibly wider than the one named file.
**UNVERIFIED inline:** whether `Diag 2.txt` and the siblings carry credentials too — I did not scan
them. Settling experiment: a read-only, count-only regex scan over the 21 siblings that emits match
*counts and offsets only*, never a matched value.

**Rotation is yours and only yours (AGENTS.md §9). Nothing below rotates anything.**

**Options:**

- **(a) Move the whole directory to an offline, non-indexed quarantine** (e.g. an encrypted volume
  or a path excluded from every archiver/indexer), trace afterwards. Fastest containment; you lose
  easy access to 20 legitimate planning docs in there.
- **(b) Move only the credential-bearing files, trace first to find them all.** Preserves the
  useful docs. Costs one scan pass before anything moves — and during that pass the exposure
  continues.
- **(c) Trace first, decide after.** Maximum information, zero containment for another day.
- **(d) Leave in place, exclude the directory from every ingestor.** Cheapest, and it does not
  reduce the exposure at all — it only stops it growing.

**Recommendation: (a) then trace — contain first, enumerate second.** *Almost certain (90-97%)*
that containment-before-enumeration is right here: the credentials are already 19 days exposed, the
marginal information from tracing first is small, and the directory is described in the register as
sitting in "the tree the conversation archive ingests" — every hour of enumeration is another hour
of potential ingestion. Then run the count-only trace on the quarantined copy, where it is safe.

**And regardless of a/b/c/d: recommend rotation of every credential in that file.** A secret is
compromised by exposure duration, not by whether anyone is known to have read it. 19 days is long.
You do the rotating; I will not touch it.

**Against me:** if any live automation reads a path inside that directory, (a) breaks it silently
and you find out at the worst moment. Mitigation: quarantine by *copy-then-shred-original* and keep
a tombstone file naming the new location.

**Default if you never answer:** exposure continues indefinitely; day 20, 21, 22…

---

## Q13 — Quarantine and review the unregistered marketplace clone that ships its own `hooks/`

**Restated:** a cloned marketplace inside `~/.claude/plugins/` carries its own hook directory. Is it
reachable, and do we quarantine it?

**STILL OPEN — CONFIRMED, and now pinned to exactly one directory.** I enumerated all 8 marketplace
clones and cross-checked each against the registration state in `~/.claude/settings.json`
(`enabledPlugins`, 99 entries, 9 enabled) and `~/.claude.json`:

| clone | ships `hooks/` | registered? |
|---|---|---|
| `context-mode` | **YES — 20 files**, incl. `sessionstart.mjs`, `pretooluse.mjs`, `posttooluse.mjs`, `precompact.mjs`, `userpromptsubmit.mjs`, `routing-block.mjs`, `hooks.json` | **NO — 0 occurrences in `.claude.json`, 0 in `enabledPlugins`** |
| `claude-reflect-marketplace` | yes — `hooks/hooks.json` only | yes, enabled |
| other 6 | no | mixed |

So the CVE-2026-47751-shaped item is **one directory: `~/.claude/plugins/marketplaces/context-mode`** —
an unregistered clone shipping a full lifecycle hook set including a `SessionStart` and a
`PreToolUse` handler. **UNVERIFIED inline:** whether those hooks are actually *reachable* by the
host (registration absence suggests not, but discovery-by-directory-walk would defeat that). That
unknown is the entire question. Settling experiment: add a canary `console.error` line to a *copy*
of `sessionstart.mjs`, restart one session, and check whether the canary appears — a both-states
probe, since it must be silent when the file is moved away.

**Options:**

- **(a) Move `context-mode/` to `context-mode.quarantined-20260809/` and restart.** If nothing
  breaks in a day, it was unreachable and can be deleted. Reversible, decisive.
- **(b) Read the 20 hook bodies first, then decide.** Higher confidence, several hours, and
  reading is not the same as proving reachability.
- **(c) Run the canary reachability probe, then quarantine only if it fires.** Cheapest true answer
  (~15 min), but leaves it live during the probe.
- **(d) Leave it — it is unregistered, therefore inert.** This is an inference, not a measurement,
  and it is exactly the class of inference this estate has been burned by.

**Recommendation: (a), then read at leisure.** *Likely (75-88%).* A rename is instantly reversible
and converts an unbounded unknown into a bounded one; the register's own author called this the one
item they would not defer. (c) is defensible if you want the measurement, but (a) gets the same
safety in 10 seconds.

**Against me:** counting is not reading. If quarantining ends the investigation, you have hidden an
unknown rather than resolved it — and a false all-clear is worse than honest ignorance.

**Default if you never answer:** it stays, unread and unregistered, indefinitely.

---

# TIER 2 — REAL VALUE, CHEAP TO DECIDE

## Q25 — Hook test files that collect zero tests. **Re-measured: 6× worse than reported.**

**Restated:** some hook test files are standalone scripts, so pytest collects nothing from them and
every "hook tree passed" count silently excludes them. Wire them into pytest, or run them separately
and print the count?

**STILL OPEN — CONFIRMED and materially understated.** The register says *five* files. Measured
today with an exact algorithm (AST classification + per-file `pytest --collect-only`, controls
passing — two known-good files collected 5 tests each):

- **102** `test_*.py` files under `hooks/`
- **31** collect **zero** tests — not 5
- **2 of them abort the entire tree collection**: `hooks/cmd-rewrite/test_hooks.py` and
  `hooks/memory-guard/test_scan.py` raise `INTERNALERROR> SystemExit: 0` at import
- a whole-tree run reports `831 tests collected, 2 errors` **and then INTERNALERRORs**

So the exposure is not "31 files are uncounted" — it is "**any whole-tree `pytest hooks` run
crashes**, and the number anyone quotes after that crash is not a suite result".

**What the answer changes:** every past and future "the hook tree passes" claim. This is a
verification-integrity hole, not a tidiness item.

**Options:**

- **(a) Convert all 31 to pytest test functions.** One true suite, one number. Risk: converting a
  standalone script can silently change what it asserts (the register's own objection).
- **(b) Fix only the 2 INTERNALERROR files** (guard their `sys.exit` behind `if __name__ ==
  "__main__"`), run the other 29 separately in the gate and print their count. Smallest change that
  restores a trustworthy number.
- **(c) Run all 31 separately, print the count, convert nothing.** Zero behaviour risk; two numbers
  to read forever, and the whole-tree crash stays.
- **(d) Leave it.** Every hook-tree pass claim stays unfalsifiable.

**Recommendation: (b).** *Almost certain (90-97%)* that guarding two module-level `sys.exit` calls
is safe and turns a crashing collection into a clean one; only *likely (60-80%)* that converting all
31 preserves their assertions, which is why (a) is not the recommendation. (b) is roughly an hour.

**Against me:** (b) leaves 29 files outside the suite forever, so coverage numbers stay wrong even
though the count stops lying. If you want one number, (a) is the only option that gets there.

**Default if you never answer:** the crash and the 31-file blind spot persist; this is agent-fixable
without you, so consider delegating rather than deciding.

---

## Q3 — `dark-surface/check.py` is 97% of the Stop battery. Who converts it?

**STILL OPEN — CONFIRMED unchanged.** Measured today: the file is **byte-identical in repo and live
(18,096 B both)**, still contains `_final_text`, still performs a whole-file read. No conversion has
happened. (The repo==live identity is a small bonus: this one is *not* part of the 18-of-20 rules
drift, so a fix deploys cleanly.)

**What the answer changes:** ~4.29 s of a 4.4 s Stop battery, on every turn of every session.

**Options:** (a) one lane converts it *and* its NOT-CHECKED typed-silence contract together, with
its own both-states row · (b) convert the speed path only, leave the silence contract alone and
document the gap · (c) leave it, accept 4.3 s/turn · (d) delete the check.

**Recommendation: (a).** *Almost certain (90-97%)* the conversion works — it is mechanically
identical to four already-proven conversions (35×-60×, both-states proven). The contract change
travels with it because it is a behaviour change on a guard, not a pure speed-up, and deserves its
own both-states row rather than riding in as an optimisation.

**Against me:** bundling a guard behaviour change into a performance PR is how behaviour changes
escape review. (b) is the more conservative split.

**Default if you never answer:** it stays at 4.29 s and stays unowned — two lanes already declined
it as out of scope, which is how it got here.

---

## Q12 — Plugin-cache GC. **Re-measured: fewer GB, far more files.**

**STILL OPEN — CONFIRMED, and the orphan ratio has worsened.** Measured today by directory walk:

| metric | register (2026-08-08) | measured today | direction |
|---|---|---|---|
| size | 12 GB | **10.62 GB** | slightly smaller |
| files | 230,181 | **298,679** | **+30%** |
| cache children | 57 | 82 | +25 |
| temp orphans | 49 of 57 | **74 of 82** (`temp_subdir_*`) | worse ratio |

74 of 82 cache entries are `temp_subdir_<epoch>_<rand>.clone` directories. Only 8 are real
marketplaces. The file count is the number that matters here: this box's freeze root cause is
**commit exhaustion**, and 298k files is a metadata load, not just disk.

**Options:** (a) dry-run report now, approve the delete after reading it · (b) delete only entries
matching `^temp_subdir_\d+_[a-z0-9]+(\.clone)?$` older than 7 days — a mechanical, auditable
predicate · (c) full GC with retention policy (option B-20 as specified) · (d) nothing; the 96 GB
pagefile is holding.

**Recommendation: (b), then (a) for the rest.** *Likely (75-88%).* The temp-orphan pattern is
regular enough to be matched exactly, which removes the judgement from the deletion — and mechanical
beats judgement on anything deletion-bearing. Hard requirement either way: **must not follow reparse
points** (live junctions exist inside backup dirs), and must never touch the 8 real marketplace
entries, which are load-bearing curation.

**Against me:** 10.6 GB is not worth a deletion bug on a box whose pagefile is coping. If you are
not feeling the pain, (d) is rational.

**Default if you never answer:** the orphan count keeps climbing (it grew ~30% in a day).

---

## Q11 — C-32 budget-aware fan-out width profiles. **The numbers are yours.**

**STILL OPEN.** Not re-probed today — **NOT-CHECKED** on the current declared `max_threads` value.
Settling experiment: grep the live workflow configs for `max_threads`/width caps and compare with
the widest fan-out in the last 30 days of the event ledger.

**What the answer changes:** whether a fan-out can be admitted at width 1,000 again (one such run
failed) or is clamped.

**Options:** (a) adopt profiles, numbers = 1.25× the widest *successful* observed width ·
(b) adopt profiles, numbers you pick · (c) adopt the mechanism in SHADOW (log admission decisions,
never clamp) for 2 weeks, then set numbers from data · (d) reject; keep fan-out unbounded.

**Recommendation: (c) then (a).** *Likely (70-85%).* Your standing rule is explicit that a provider
429 must **never** cause self-throttling, and a clamp is one config error away from becoming exactly
that. Shadow-first gets you the distribution without ever being the thing that starves a run — and
it is the same gate-maturity discipline as L-28 (already adopted, Q7). Whatever you choose, make
"429 never feeds the admission decision" an explicit, tested invariant.

**Against me:** shadow-forever is the known failure mode of shadow mode. If you adopt (c), put a
date on the promotion review or it never promotes.

**Default if you never answer:** unbounded width; the failure mode that already cost one run.

---

## Q23 — `dup-guard` precision vs recall. **I have fresh evidence: 2 for 2 false positives, today.**

**STILL OPEN. The "68 open fires" count is NOT-CHECKED** — I could not re-derive it. Probe: the
guard is `hooks/dup-guard/guard.py` (19,574 B) and it has **no state directory, no fires ledger, no
snooze store** (`state` 0, `ledger` 0, `open_fires` 0 occurrences; no `state/` dir in repo or live).
So 68 came from an external tally I could not locate. Settling experiment: count `dup-guard` events
in `~/.claude/event-ledger/` over a fixed window.

**But I have direct evidence on precision, generated by accident.** Writing two throwaway probe
scripts in this session fired the guard **twice, and both were false positives**:

1. writing `_probe_questions.py` → *"the symbol `rec` is already defined at
   `.agents\skills\transpose-to-figma\transpose.mjs`"* — a 3-letter local helper matched against an
   unrelated **JavaScript** file in a skills tree.
2. writing `_p25b.py` → *"the symbol `classify` is already defined at `.wt-triage\residual.py`"* —
   a generic verb matched against an unrelated scratch file.

**2 of 2 fires were false**, both driven by generic short names, one of them matching **across
languages**. Combined with the verifier's earlier measurement of 2 firings at n=20 both false, the
running tally on this guard is **0 true positives in 4 observed fires**. That is still a small
sample (*roughly even (45-55%)* that true precision is under 25%), but it now has two independent
sources rather than one.

**Options:** (a) add a generic-name stop-list + minimum symbol length + same-language filter ·
(b) restrict the guard to same-directory-tree matches only · (c) demote to SHADOW under the L-28
ladder until precision is measured · (d) leave it loud.

**Recommendation: (a) + (b) together — cheap, and both target the exact observed failure.**
*Likely (70-85%).* Both my false positives would have been suppressed by *either* filter: `rec` fails
a length/generic test, and a `.mjs` in `.agents/skills/` fails a same-tree test against a repo-root
`.py`. This is not a precision-recall trade in the abstract — it is two specific, observed defects.
The guard currently has **no** stop-list mechanism at all (`MIN_LEN` 0, `allowlist` 0).

**Against me:** every filter removes recall, and the guard reportedly has real true positives. If
you would rather not touch a working guard, (c) is the honest holding position.

**Default if you never answer:** it keeps crying wolf, and you learn to ignore it — the failure the
32-doc itself warns about.

---

## Q6 — RT-01 role-based model floor, with or without a cheap T3 tier

**STILL OPEN.** Not re-probed — **NOT-CHECKED** on the "81% of workflows declare no model at all"
figure. Settling experiment: parse every `.mjs` under `~/.claude/workflows/` and the repo's
`workflows/`, count those with no `model:` key.

**Options:** (a) adopt the table, T3 OFF · (b) adopt with a bounded T3 pilot on exactly one
mechanical role (verbatim span extraction), measured against an Opus control · (c) adopt with T3 on
everywhere · (d) reject the table.

**Recommendation: (a) now, (b) as a scheduled follow-up.** *Almost certain (90-99%)* the table
itself is right — the real defect is that most workflows declare no model at all, which silently
inherits whatever the runtime defaults to. Only *roughly even (45-60%)* that a cheap extraction tier
is safe here, and your standing preference is explicit: Opus for all substantive subagents. (a)
respects the standing preference; (b) is how you would ever learn otherwise.

**Against me:** T3-off means the data that would justify T3 never gets generated. If you never
schedule (b), you have simply decided "no cheap tier, ever" — say so plainly rather than deferring.

**Default if you never answer:** 81% of workflows keep declaring no model; the floor is whatever the
runtime happens to pick.

---

# TIER 3 — ANSWERED BY EVENTS OR BY MEASUREMENT. Close these; do not spend attention.

## OQ-3 — Release mode → **ANSWERED. PR-ONLY.**
Binding owner decision. Phase 15 (R-A17) branches on it and can now be planned.
**Action needed:** flip `owner_questions[OQ-3].state` in `WORK-UNIT-CATALOG.json` and re-render —
the generated `OWNER-DECISIONS.md` still says "27 open of 27", which is stale.

## OQ-4 — Was the 38-item tranche an approved Prompt-Two substitute → **ANSWERED. NO.**
Owner ruled 2026-08-09: run the real Prompt Two. Consequences to record, not to re-ask:
every artifact calling the 38-item tranche "Prompt Two" is **mislabelled** and should be renamed
rather than deleted; R-A04 closes; R-A01 (the real Prompt Two) is the target.
**Action needed:** same catalog flip.

## OQ-5 — C22/G-05 vs I3/D07: which authority wins → **DOWNGRADED TO MOOT, and unanswerable as posed.**
Two reasons. (1) OQ-4's ruling removes the substitute program whose internal fork this was.
(2) **The question cannot be resolved in the canonical namespace: `G-05` does not exist.** Measured:
`07-OPTION-UNIVERSE.json` contains **zero** `G-*` ids — family G was re-prefixed to `PR-` (finding
F-B-03: E→`EV-`, F→`RT-`, G→`PR-`). `C-22`, `D-07`, `H-22` and `I-03` all resolve; `G-05` does not.
**Recommendation: close OQ-5 as superseded by OQ-4, and re-express any surviving conflict in
option-universe ids when the affected options actually come up.** *Likely (70-85%).*

## OQ-8 — Enroll the monitor cockpit program → **MOSTLY DONE. Only the priority is still open.**
Two things changed:
- **The cockpit is reachable.** `[cockpit]` is now present in **all three** `monitors.toml` copies
  (repo `.agents/skills/`, repo `skills/`, live `~/.agents/skills/`) — CONFIRMED by direct file read,
  which is a mechanically different signal from the runtime `mon cockpit` check done earlier today.
  R-M01 is closable.
- **The monitor program IS enrolled** — in the command-center catalog, which now carries **19
  MONITOR items** (R-M01…R-M19) rendered in `STATUS.md`. R-M18's original complaint ("`grep -ic
  cockpit` over the contract = 0") was about the *prose contract*; the catalog is the operative
  ledger now.

**Residual question, one line: at what priority?** It is not free to defer — the graph shows
`R-M06 ← R-M18`, so OQ-8 is the only thing holding the **six parked adversarial-gate verdicts**
(the program was parked 2026-07-27 immediately after them and never rescheduled).
**Recommendation: answer it now with "priority = after the Tier-0 gate".** *Likely (65-80%)* —
the highest-yield monitor item (reachability) is already banked and the remaining 18 are mostly
L/XL, but leaving OQ-8 unanswered keeps R-M06 invisible rather than merely deprioritised.
Separately, `R-M04 ← R-M01`: since R-M01 is now satisfied, **R-M04 becomes ready** the moment
R-M01 is formally closed.

## Q10 — J-15 dual-use review → **PREMISE PARTLY REFUTED. Adopt the policy; the branch action is moot.**
The question asked you to apply the review to `chore/harness-reconcile-20260808` *before merging it*.
Measured today: that branch is **19 commits ahead / 7 behind origin/main and is NOT an ancestor of
main** (control: a bogus SHA correctly errors) — it is unmerged, with no open PR.
More decisively, **the guard code it was going to expose is already public**, and has been for weeks:

| file | first landed on main |
|---|---|
| `hooks/dup-guard` | `6743b857` **2026-06-29** |
| `hooks/dark-surface` | `faae06d0` **2026-07-18** |
| `hooks/_shared/use_vs_mention.py` | `4176ca71` **2026-07-18** |

So the disclosure already happened through other PRs. **Recommendation: adopt J-15 as a
forward-looking policy for security-bearing PRs (default ADOPT), and drop the branch-specific
action.** *Likely (75-88%).* Also worth a separate decision (not asked, so not folded into a pass):
that branch is 19 commits of unmerged work with no PR — **NOT-CHECKED** whether any of it is unique.
Settling experiment: `git log origin/main..origin/chore/harness-reconcile-20260808 --stat`.

## Q15 — M-29 deploy the 11 dark cross-vendor skills → **PREMISE REFUTED. They are in the repo, not lost.**
The register says they are "absent from both repo and live". Measured today by set difference
between `git ls-tree -r origin/main` skill names and live `~/.agents/skills/`: there are **exactly 11
repo-only `codex-*` skills** —
`codex-audit`, `codex-brainstorm`, `codex-coordinate`, `codex-curate`, `codex-discuss`, `codex-fix`,
`codex-governance`, `codex-invoke`, `codex-mixed-workflow-doctrine`, `codex-review`, `codex-triage`.
They are **on origin/main and absent from the live tree** (330 live skill dirs, 354 repo skill names).
*Likely (70-85%)* these are M-29's "11 dark" set — the count matches exactly and the family matches
("cross-vendor council and invoke suite"). **UNVERIFIED inline:** that the names correspond
one-to-one to M-29's intended list; settling experiment: read M-29's body in
`07-OPTION-UNIVERSE.md` and compare names.

**This changes the decision entirely:** the bodies are readable right now from the repo, so "deploy
unread" is not the risk it was. **Recommendation: an agent reads the three named bodies
(discuss/curate/governance), checks them for retired rails (AgentBridge is gone) and hand-rolled
argv that violates current transport rules, then deploys into the LAZY vault — not the daily 79.**
*Almost certain (90-97%)* they exist as described; only *likely (55-80%)* they work unedited.
You need to say yes/no to lazy-vault deployment; everything else is agent work.

## Q19 — `owner-ops-authorization.md` is live-only, on no git ref → **REFUTED. It is on main.**
Measured three ways: it appears in `git ls-tree -r origin/main`; `git log` shows it committed as
`fb3fd55a` **2026-07-22** ("chore(skills): version two disk-only skills and three untracked
rule/guide files (#129)"); and `git merge-base --is-ancestor fb3fd55a origin/main` exits 0 while a
bogus SHA control exits 128. **The premise was already false when the register was written.**

Residual, and it is small: live is **234 lines**, repo is **215** — live is ahead by 19 lines, so
it is one of the 3 LIVE-AHEAD files inside R-H10's 18-of-20 rules drift.
**Recommendation: close Q19; carry the 19-line live delta up as part of R-H10, not as its own
decision.** *Almost certain (90-99%).*

## Q20 — Where do the 6 metaswarm guides live → **ANSWERED BY MEASUREMENT, not by you.**
All six exist at `~/.claude/guides/` (`agent-coordination`, `build-validation`, `coding-standards`,
`git-workflow`, `testing-patterns`, `worktree-development`), and `tool-routing-and-quality.md` is at
`~/guides/`. The dead links are relative-path bugs in `~/CLAUDE.md`, not missing files.
**Genuinely absent:** `templates/external-tools-setup.md`, `~/.metaswarm/`, and
`.metaswarm/external-tools.yaml`. The only owner-held part left is "is metaswarm still in play at
`~`", which is really Q21. **Recommendation: close Q20, fix the links, fold the rest into Q21.**

## Q22 — `validate-all-skills.ps1` unrunnable → **CONFIRMED, but this is not an owner decision.**
Measured: the script exists in two places (`~/source/agent-skills-toolchain/scripts/` and repo
`scripts/`, both 3,707 B, both referencing `.system`), and `~/.agents/skills/.system` **does not
exist**. It blocks R-B04. **Recommendation: repoint it — do not ask the owner.** *Likely (65-80%)*
that `.system` is simply retired. This is a one-line path fix an agent should make and report;
putting it in an owner batch is what kept it unfixed. If the repoint fails, *then* it is a question.

---

# TIER 4 — LOW VALUE. Batch-answer in one line each, or delegate.

| # | question | why it is low value | recommendation | band |
|---|---|---|---|---|
| **Q9** | B-24 measurement-only ratings (no stars/downloads) | **There is no marketplace yet.** R-A06 measures the "marketplace" as a single self-listing manifest with **1 plugin**. Rating policy for a 1-entry registry is premature. | Accept the ADOPT default; revisit at >20 entries | likely 70-85 |
| **Q14** | I-02 corpus attrition, copy-on-run now? | Real, but **NOT-CHECKED** by me — I did not re-count the 364-of-668 deletions. Settling experiment: re-run the executed-script census. Ingestion is additive and cannot lose anything. | Adopt copy-on-run now; hold retention until M-01 lands | almost certain 90-99 that ingestion is safe |
| **Q16** | B-01 marketplace index public or private | Same prematurity as Q9, but the choice constrains later architecture, so it is worth 10 seconds | **PRIVATE git repo** | likely 70-88 |
| **Q17** | `bd prime --work-type recovery` errors | **CONFIRMED still broken today**: `Error: unknown flag: --work-type` (bd v1.0.4). A one-line doc fix. | Fix the doc, not the tool | almost certain 90-99 |
| **Q18** | `.beads/plans/` vs `.beads/context/` canonical | **Both now exist at `~`** — which refutes the dated "neither exists" note in `~/CLAUDE.md:31`. The live reader only checks `.beads/context/`. | `.beads/context/` is canonical; fix the doc | likely 75-90 |
| **Q21** | `~/CLAUDE.md` is metaswarm **project** instructions living at `~` | Genuine value call with real blast radius: every session whose cwd is home inherits a mandatory 9-phase gate | Scope it or move it — almost certainly unintended | likely 70-85 |
| **Q24** | Promote `workflow-foundry` to the curated set | **CONFIRMED unchanged**: description is **1,750 chars**; curated set = **79** skills, vault = **330**. Descriptions are always-loaded context. | Leave in the lazy vault; trim the description before any promotion | high 85-95 |
| **OQ-7** | Program B B3/B4/B5 renumbering | Already resolved by the authority order (§0: prompt wins). Needs a "confirmed" so it is never re-litigated. | Confirm prompt numbering; renumber once | almost certain 90-99 |

**Q17, Q18, Q20, Q21 are one chore, not four questions.** All four are defects in `~/CLAUDE.md`.
Recommend answering Q21 (the only real value call) and letting an agent fix the other three.

---

# NEW — THE 28th QUESTION NOBODY ASKED YOU

## M-36 — Fork / merge governance and deprecation lifecycle for workflows

`07-OPTION-UNIVERSE.json` has **15** options that are both `track: now` and `owner: true`. Fourteen
of them appear in `32-OWNER-DECISIONS.md`. **M-36 appears zero times.** Detector control: the other
14 ids each return ≥1 match in the same grep, so the zero is real, not a broken matcher.

So an owner-gated, now-track option was silently dropped from the batch that exists specifically to
prevent silent drops. Its default is `ADOPT`.

**Recommendation: accept the ADOPT default and log it, or explicitly defer it — but record the
choice.** *Likely (60-80%)* that accepting the default is right (it is consistent with all 122 other
now-track defaults), but the honest point is that **you have never been shown it**, and the reason it
matters is procedural: if one slipped, the enumeration is not proven complete.

---

# WHAT I COULD NOT SETTLE

- **The `dup-guard` "68 open fires" count** — NOT-CHECKED. The guard has no fires ledger on disk;
  the number came from a tally I could not locate. Settling experiment: count dup-guard events in
  `~/.claude/event-ledger/` over a fixed window. (My 2-of-2 false positives are a *precision*
  signal, not a count.)
- **Whether `context-mode`'s hooks are reachable** — the entire substance of Q13. Settling
  experiment: the canary probe described above, run in both states.
- **Whether `Diag 2.txt` and the 19 other siblings carry credentials** — I did not scan them.
  Settling experiment: read-only, count-and-offset-only scan; never emit a matched value.
- **Q6's "81% of workflows declare no model"** and **Q11's current declared width cap** — inherited,
  not re-measured.
- **Q14's 364-of-668 script attrition** — inherited, not re-measured.
- **Whether the 11 repo-only `codex-*` skills are literally M-29's intended list** — the count and
  family match exactly, but I did not read M-29's body to compare names.

---

# ANSWER SHEET — every question, one line

Write your answer after the arrow. Anything left blank takes the stated default.

**TIER 0**
- `OQ-1` selected option ids → **(b) ratify all 123 `track:now`, veto by exception** · vetoes: ______
- `OQ-2` priority ordering → **(b) ratify register §5, pin top 3** · your top 3: ______

**TIER 1**
- `OQ-6` Diag 1.txt → **(a) quarantine the directory now, trace after** · quarantine path: ______ · *(rotation: yours)*
- `Q13` `context-mode` clone → **(a) rename to `.quarantined-20260809`, read later** → ______

**TIER 2**
- `Q25` 31 zero-collect hook tests → **(b) fix the 2 crashers, run the other 29 separately** → ______
- `Q3` dark-surface conversion → **(a) one lane, convert + contract together** → ______
- `Q12` plugin cache → **(b) mechanical `temp_subdir_*` predicate, no reparse-point follow** → ______
- `Q11` fan-out width → **(c) shadow 2 weeks then set numbers; 429 never clamps** → ______
- `Q23` dup-guard → **(a)+(b) generic-name stop-list + same-tree filter** → ______
- `Q6` model floor → **(a) adopt table, T3 OFF** · schedule the T3 pilot? Y/N → ______

**TIER 3 — closures, tick to confirm**
- `OQ-3` PR-ONLY ☐ · `OQ-4` tranche NOT a substitute ☐ · `OQ-5` closed as moot ☐ ·
  `OQ-8` priority = after Tier 0 ☐ · `Q10` adopt policy, drop branch action ☐ ·
  `Q15` deploy 3 to lazy vault after a read pass ☐ · `Q19` closed, delta rides R-H10 ☐ ·
  `Q20` closed, links fixed ☐ · `Q22` delegated (repoint) ☐

**TIER 4 — batch**
- `Q9` accept default ☐ · `Q14` copy-on-run now ☐ · `Q16` PRIVATE ☐ · `Q17` fix doc ☐ ·
  `Q18` `.beads/context/` canonical ☐ · `Q21` scope/move `~/CLAUDE.md` → ______ ·
  `Q24` stay in vault ☐ · `OQ-7` prompt numbering wins ☐

**NEW**
- `M-36` fork/merge governance → accept ADOPT ☐ / defer ☐

---

## Housekeeping this packet implies

1. **`WORK-UNIT-CATALOG.json` is stale**: `owner_questions` lists all 27 as `OPEN`, but OQ-3 and
   OQ-4 were ruled on 2026-08-09. Flip both states and re-render, or `OWNER-DECISIONS.md` keeps
   reporting "27 open of 27".
2. **Add M-36** as a 28th owner question so the enumeration is provably complete.
3. **Record the F-B-02 closure in `17-DECISION-LOG.md`.** It is fixed on disk, but the decision log
   still states it in the present tense and holds **zero** `MECH` tokens — so every reader who pins
   ground truth from the log inherits a solved problem as a live blocker. That already happened once
   in this program. Append a `REMEDIATED` row (do **not** blind-rewrite the 10 `M-NN` mentions inside
   F-B-02's own text — they are the evidence). Detail: `OPTION-ID-RESOLUTION.md` §7a.
4. **Schedule the 58 unadjudicated `M-NN` references** and the third/fourth namespaces (§7b, §7c of
   the same file). Author work, not owner work — but it needs an owner-visible slot or it rots.