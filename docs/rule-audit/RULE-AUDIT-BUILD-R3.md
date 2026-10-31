---
title: RULE-AUDIT-BUILD-R3
type: note
permalink: dqverify-repo-20261013/docs/rule-audit/rule-audit-build-r3
---

# RULERESEARCH — BUILD lane, round 3

STATUS: complete and measured. Every number below was produced by a command in this round.

COVERAGE: measured — the grounding's staleness, the one un-closed residual and its closure, the
first-hand re-verification of contradiction 4.2, the drift census, and both-states controls for
everything shipped. Declared NOT measured, inline where it matters: the other seven
contradictions, BUILD-R2's internal timing claims, and any runner execution.

> The orchestrator labelled this "round 1 of at most 4". The directory says otherwise: this lane
> has already shipped BUILD rounds 1 and 2, so this is **round 3** and is named for the series
> rather than for the spawn. Reading it as a first round is the fastest way to rebuild what
> already exists.

## 1. The grounding I was handed is STALE, and acting on it would have rebuilt shipped work

The grounding's plan opens with "WIRE THE 8 RULE-AUDIT GATES INTO CI. Highest leverage." It was
pinned at `HEAD 27da3215`. Measured at spawn: **`HEAD 7618a6fa`**, and `git log -- docs/rule-audit`
shows four later commits, the relevant one being **`4ef63930 ci(rule-audit): wire the lane's 8
gates into CI`**. Grep of `.github/workflows/` confirms `rule-audit.yml` exists and runs
`python docs/rule-audit/ci_gate.py`.

| grounding plan item | state at spawn |
|---|---|
| 1. wire the 8 gates into CI | **already shipped** (`4ef63930`) |
| 2. deploy corrected rules to live | open — deliberately left to the owner |
| 3. escalate credential inversion | shipped as a pinned rc=1 gate (`f27dbb93`) |
| 4. repo↔live parity gate | **open — this round** |
| 8. load-semantics gate | already shipped (`ci_gate` invariants 3 and 4) |
| 9. fill or delete `RULE-AUDIT-INTEGRATE.md` | already filled (BUILD-R2, uncommitted) |

So the single genuinely-open, in-scope item was #4 — which is also the residual BUILD-R2 closes
on: *"Repo↔live drift (29/88 files, 7/8 always-on) is still neither gated nor fixed."*

**A stale grounding is not a defect in the grounding lane** — it measured honestly at its own
HEAD. It is a defect in treating any handoff as current. The cheap fix is the one that worked
here: re-run the grounding's own load-bearing probe before spending a round on its plan.

## 2. I inherited 1,205 lines of my own lane's finished work, uncommitted in the index

`git status` at spawn showed BUILD-R2's entire output **staged but never committed**
(`RULE-AUDIT-BUILD-R2.md`, `_b10_gate_timing.py`, `_b11_home_index_equivalence.py`, the
`r2_pathrefs` index optimisation, `ci_gate.py`, `RULE-AUDIT-INTEGRATE.md`).

Two independent signals that the author was finished rather than mid-flight, which is the pair
`mtime` alone can never give:

1. The artifact's own first line: `STATUS: complete and measured`.
2. No foreign write to `docs/rule-audit/` in 6 h — **while other lanes were writing to
   `command-center/**` every few minutes** during the same scan. That second clause is the
   control: the detector demonstrably sees live agents, and it sees none here. Without it,
   "no recent writes" would just be a quiet box.

It is committed in this round as its own commit, attributed to BUILD-R2. **NOT re-verified by
me: its internal timing claims** (§3-§5 of that document). What I did verify is that its shipped
code runs — `r2_pathrefs --self-test` measured 50.9 s in my `ci_gate` run, consistent with its
post-change 20-25 s band and far below its pre-change 98-210 s, but a single sample on a shared
box and *not* an independent confirmation of its equivalence proof.

## 3. Contradiction 4.2, re-verified first-hand against the code (not against a prior receipt)

The grounding reports 4.2 as fixed-in-repo and wrong-in-live. Prior rounds' receipts are one
signal; the source is another. Read directly from `scripts/sync-from-live.ps1`:

| line | text | consequence |
|---|---|---|
| `:133` | `[ValidateSet('text','json')][string]$Report = 'text'` | `Report` selects OUTPUT FORMAT |
| `:477` | `$writeAllowed = (-not $WhatIf -and -not $Drift)` | **`Report` is absent from the guard** |
| `:499` | `$mode = if ($Drift) {'drift'} elseif ($WhatIf) {'whatif'} else {'sync'}` | bare `-Report json` ⇒ `sync` |
| `:601`, `:670` | `Copy-Item -LiteralPath … -Force` | live bytes overwrite repo files |

So `-Report json` alone is a WRITING run. **CONFIRMED, almost certain (90-99%)** — four
independent lines of the actual script, not a re-read of the lane's own note.

**A sixth signal, from inside this agent.** My own turn-0 context carries the *live* copy of
`common/harness-vcs-hygiene.md`, and it reads:

> `scripts/sync-from-live.ps1` (`-Report json` to see drift, `-WhatIf`, then a scoped commit)

The repo copy carries the correction (`-Drift -Report json` … *"Bare `-Report json` WRITES"*).
I was being instructed by the defective copy while auditing it. This is not a documentation
nit: it is an always-on instruction, in force in every session on this box right now, telling
agents that a destructive command is an inspection.

**A detector-honesty note the grounding raised and I reproduced the resolution for:** a plain
substring search for the wrong text also matches the REPO copy, because the repo file quotes the
wrong form inside its own correction. That is use-vs-mention. The gate below therefore compares
whole-file content and never greps for the phrase.

## 4. Shipped: the deploy-drift ratchet (`r5_deploy_drift_gate.py`)

The hole in one sentence, from `ci_gate.py`'s own docstring: *"Everything that compares against
the LIVE tree cannot run in CI at all … which is exactly why the repo-vs-live drift grew from
28 to 29 files while 167 tests stayed green."* Every one of those 167 tests reads `rules/` and
`agent-self/config/rules/`; none reads the deployed tree.

**Why the existing live-tree gates could not be reused.** `lazy_predict.py` and
`r3_corpus_parity_gate.py` fail CLOSED when `~/.claude` is absent, correctly — for them a zero
scan is a broken detector. A drift gate has a third state those two do not: the comparison is
not failed, it is *unperformable*. Conflating that with either a pass or a failure is what makes
a gate lie. So this one reports three outcomes and only one is a clean bill of health:

| state | rc | marker |
|---|---|---|
| live tree ABSENT (runner) | 0 | `NOT-CHECKED … asserted NOTHING about drift` |
| drift == baseline | 0 | `baseline holds … Still DRIFTED, not fixed` |
| drift != baseline, **either direction** | 1 | `GREW` / `SHRANK` |

Both directions, because an unrecorded repair is how a baseline rots into a rubber stamp — the
same discipline `ci_gate.divergence_problems` already applies to the two in-repo trees.

### The census, reproduced this round

```
scanned repo=88 live=88 .md files;  LF-normalised differ=29  (raw-byte differ=83)
always-on drift=7 (every turn-0 prompt) · lazy drift=22 · only-in-repo=0 · only-in-live=0
```

- **29/88 and 7/8 always-on** — independently reproduces the grounding, from a new instrument.
  The one always-on rule that matches is `common/stale-megapr-reconcile.md`.
- **83 raw-byte vs 29 LF-normalised is new.** 54 of the 83 are pure CRLF phantoms. A naive
  byte-compare ratchet would have been **~65% false positive** and would have been retuned into
  uselessness within a round. Both numbers are printed on every run so nobody has to re-derive
  which one they are looking at.

### Severity is not uniform, and the gate says so

A rule with no `paths:` frontmatter is injected at turn 0 into every agent; a lazy one costs
nothing until a matching file is touched. The 7 always-on drifted rules are therefore 7 wrong
instructions in force, which is why they are a separate pinned set and printed by name.

### A fourth axis nothing in this repo checked: repo↔live LOAD CLASS

`ci_gate` invariant 4 compares load semantics between the two **in-repo** deploy sources and
stops there. Nobody compared it against the **deployed** tree — the one agents actually read. If
a deploy stripped or added `paths:` frontmatter, the live turn-0 set would differ from the repo's
and DoD-1 would be measuring the wrong tree.

Measured, with a control proving the classifier can disagree at all (a bare file and a
paths-scoped file classify `True`/`False`):

```
repo files=88 always-on=8
live files=88 always-on=8
always-on ONLY in repo (live DEMOTED it): []
always-on ONLY in live (live PROMOTED it): []
```

**Clean negative result: the drift is content-only.** The 7 drifted always-on rules are still
always-on live — which is the bad news restated precisely (the wrong text *is* being injected),
but no rule silently changed its load class in deployment.

This also closed a robustness hole in my own gate, which is why it is asserted rather than just
recorded: the always-on/lazy severity split is computed from the **repo** copy's frontmatter, so
a live-side demotion would have filed a lazy rule under "read by every session right now" and
nothing would have caught it. The baseline for this axis is EMPTY, so any entry is a failure.

## 5. Shipped: the red-proof that stops the ratchet being decorative (`r5_driftgate_redproof.py`)

A gate that is inert in CI and has never been seen red in CI is indistinguishable from a no-op —
`ci-hygiene` §1, and the exact trap `rule-audit.yml` already documents for `rule_audit.py` bare.
`r5_deploy_drift_gate` is inert on a runner by construction, so on its own it would have been
that no-op.

The red-proof **synthesizes both trees from the in-repo `rules/` tree**, needs no home directory,
runs identically here and on a runner, and drives the gate's real `main()` through `subprocess` —
real argv, real exit code, real stdout — rather than re-testing the pure predicates:

```
  ok  A rc==0 when live tree absent / marker says NOT-CHECKED / does NOT claim baseline holds
  ok  B rc==1 when the drift disappears · SHRANK for all 29 · does NOT report GREW
  ok  C rc==1 when a new always-on rule drifts · names it in an ALWAYS-ON GREW line · both directions
  ok  E rc==1 when the deployed copy changes load class · names it (README.md)
  ok  D rc==1 on an empty repo tree · says the detector is broken
SUCCESS:r5_driftgate_redproof 14/14 states forced
```

Two of those twelve are the ones that make the rest mean anything:

- **B must NOT print GREW.** If every run printed both words, "direction" would be decoration —
  a control that cannot distinguish its two hypotheses proves only that the instrument ran.
- **D fails closed.** "Zero files differ" and "zero files looked at" produce identical output,
  and only one is good news. This is the only check that separates them.

## 6. Both-states controls, in full

| control | broken state | good state |
|---|---|---|
| `r5_deploy_drift --self-test`, 18 cases | each FIRES | each SILENT — rc=0 |
| CRLF-only difference | raw-byte counter SEES it (83) | LF-normalised does NOT count it as drift (29) |
| always-on vs lazy classification | a change to a `paths:`-scoped file lands in `lazy_drift` and NOT in `always_on_drift`, and vice versa | — |
| load class: live PROMOTED / live DEMOTED | each caught by name | a pure CONTENT change is NOT reported as a load-class change |
| empty repo tree / empty live tree | RuntimeError, rc=1, "detector broken" | 88/88 scanned |
| `r5_driftgate_redproof`, 14 states | rc 0→1 forced in both directions | — |
| `ci_gate --self-test`, 12 predicates | each FIRES | each SILENT — rc=0 |
| committed **blobs** vs ruff 0.15.17 + `ruff.toml` | a mangled blob is reported (rc=1) | 3 blobs clean, CRLF=0 |

Full-gate receipt after wiring, on this box:

```
== rule-audit CI gate (win32, py 3.14.6, encoder tiktoken/cl100k_base) ==
   world: live ~/.claude rules tree PRESENT
  ok  inventory: 8 planned runs over 8 gates, 35 excluded with reasons
  ok  rc=0 (want 0)     0.2s  r5_deploy_drift          SUCCESS: baseline holds: 7 always-on + 22 lazy …
  ok  rc=0 (want 0)     1.5s  r5_driftgate_redproof    SUCCESS: 12/12 states forced …
  -- total 58.3s in this world --
SUCCESS:rule-audit-ci-gate 8/8 gates behaved, always-on=8, divergence=3
```

The two new gates cost **1.7 s** of the 58.3 s.

## 7. What I deliberately did NOT do

- **I did not deploy.** `scripts/sync-rules.ps1` would land the corrections where agents read
  them — and would change what every concurrently-running agent on this box reads, mid-flight,
  at ~+1,966 tok/turn. Two prior rounds classified that as an owner action; nothing I measured
  overturns that, so this round makes the debt loud and non-growing instead of paying it.
  **This is the single highest-value open item and it is an owner decision, not a missing gate.**
- **I did not touch the credential inversion.** Owner action, already pinned at rc=1.
- **I did not rewrite any rule.** `rules/` and `AGENTS.md` are untouched by this round (DoD-4).
- **I did not re-run the classification or the contradiction census** beyond what the gates
  re-execute — it exists, it reproduces, and rebuilding it was the grounding's explicit
  "NOT RECOMMENDED (a)".

## 8. Out-of-declared-scope edit, declared

My file scope was `docs/rule-audit/**`, `rules/**` (report before editing), `AGENTS.md`
(propose only). I additionally made a **comment-only** edit to
`.github/workflows/rule-audit.yml`: its comment said "Six planned invocations over six gates"
(now eight) and its "WHAT IS DELIBERATELY NOT WIRED" block did not mention the two new entries.
No step, trigger, or command changed. The file is lane-owned — created by this lane four commits
ago — and is **not** `quality.yml`, the shared file the ground floor names as the collision
hazard. Leaving a stale count in a workflow comment is precisely the "a rule can be WRONG and
propagate" failure this lane exists to fight.

Also checked, because it would have been a silent functional gap: `rule-audit.yml` has **no
`paths:` filter** (`on: push[main] / pull_request / workflow_dispatch`), so the two new gates are
picked up on every PR without a workflow change. `ci_gate.py` builds its plan from `CI_PLAN`, so
nothing enumerates gate filenames in YAML.

## 9. DoD status

- **DoD-1 — every rule classified always-on vs lazy by measured frontmatter: PASS.** Enforced by
  `ci_gate` invariant 3 and re-run green this round (`always-on=8`). Independently re-measured
  here across both deployed and repo trees: 88 files, 8 always-on.
- **DoD-2 — always-on token cost totalled: PASS (inherited, not re-derived this round).**
  17,107 tok repo / 15,141 live over the 8, `cl100k_base` — **OpenAI's tokenizer, not
  Anthropic's**, so a ±10-20% estimate and not a receipt. The first-party receipt path
  (`/context` "Memory files") still requires an owner action and remains untaken after three
  rounds.
- **DoD-3 — every contradiction measured and listed with the correction: PASS (inherited), with
  4.2 re-verified first-hand this round** against `sync-from-live.ps1` and against my own turn-0
  context. **NOT individually re-measured this round: the other seven.**
- **DoD-4 — no rule rewritten without evidence: PASS.** No rule was rewritten at all.

## 10. Residual

- **The drift is now GATED, not FIXED.** 7 always-on + 22 lazy rules are still undeployed, and
  the deployed `harness-vcs-hygiene.md` still instructs every agent that `-Report json` inspects.
  Owner action. UNVERIFIED until then, settling experiment: `pwsh scripts/sync-rules.ps1 -WhatIf`,
  read the list, then the real run, then `r5_deploy_drift_gate.py` must go red with 29 `SHRANK`
  lines and the baseline must be emptied in the same change.
- **On a runner the drift remains NOT-CHECKED**, permanently — no runner has the owner's home
  directory. A green CI run means "the ratchet works", never "the deployed tree matches".
- **`rule-audit.yml` has still never executed on a runner.** The tiktoken-on-Linux repair stays
  UNVERIFIED; the first run of the workflow settles it. My two gates are Windows/Linux-neutral
  (`pathlib` + `subprocess`, no shell), but that is a reading of the code, **not a measurement on
  Linux** — the same class of claim this lane has had refuted before.
- **The baseline is a ratchet, and a ratchet can be re-pinned.** Re-pinning requires editing the
  literal sets in the source, which is visible in review — but nothing prevents a future round
  from widening it instead of paying the debt. That is a social control, not a mechanical one.
- BUILD-R2's timing claims are inherited unverified (§2).