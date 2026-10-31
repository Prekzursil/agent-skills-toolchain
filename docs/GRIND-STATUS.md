---
title: GRIND-STATUS
type: note
permalink: dqverify-repo-20261013/docs/grind-status
---

# GRIND-STATUS — what is done, what is not, and what only the owner can unblock

> **THERE ARE TWO GRIND-STATUS DOCUMENTS. Read both; neither supersedes the other.**
> `command-center/GRIND-STATUS.md` is the later nine-lane synthesis. It re-executes all 22 lane
> gates first-hand, reconstructs the eight lanes missing from a truncated payload, and carries the
> cross-lane findings, the overclaim ledger and the owner-decision table.
> **This document is authoritative on the CI outage (§0)** — its private-vs-public discriminator and
> its elimination table are stronger than the synthesis's, which defers to it — and its §3
> corrections are frozen evidence of what was wrong when. The synthesis is authoritative on
> per-lane gate state, and it corrects §4 here on one point: `check_citations.py`, reported as
> `FAILED:cite-check`, now **PASSES** (it was flagged against a mid-write untracked document).

Written by the orchestrator on 2026-08-14, **not** by the workflow's `synthesize` stage. That
stage has now died three times before writing anything — twice on `401 API key is invalid`, once
on a session limit — so this document exists because a deliverable that is only ever *scheduled*
is not a deliverable. Everything below was measured from the repository and the GitHub API in the
half hour before writing; nothing is carried over from a lane's own summary of itself.

## How to read the confidence tags

Per AGENTS.md §7 every load-bearing line carries one:

| tag | meaning |
|---|---|
| **MEASURED** | I ran the command in this session and read its output. |
| **FROM-RECORD** | Asserted by an artifact or an earlier turn; **not** re-checked now. |
| **STALE** | Was true when recorded, and a later measurement contradicts it. |
| **UNKNOWN** | The instrument that would answer it is unavailable. Not a synonym for "fine". |

The distinction is not decorative. Two claims in this session's own record were **STALE** by the
time I re-measured them, and both are corrected below rather than quietly restated.

---

## 0. The one fact that gates everything else: CI cannot start a job

**MEASURED.** Every workflow run on `main` since `2026-08-14T04:33:59Z` fails. The signature is
identical across all of them and does not look like a test failure:

* all nine workflows report `failure` **in the same second** (05:42:06 for eight of them, autofix-models at 05:42:14);
* each run has `steps=0` — no step ever executed, so there are no logs to read;
* re-running a failed run reproduces it exactly, which rules out a transient dispatch flake;
* the last 60 runs on `main` are `failure:36, success:20, skipped:4` — the 20 successes are all
  from **before** 04:33:59.

### Diagnosis, narrowed — the discriminator is PRIVATE vs PUBLIC

The first version of this section said "likely quota, 60-80%" and stopped, on the grounds that
the billing endpoint returned 410 and check-runs returned 403. **The 410 was a moved endpoint,
not a closed one.** `users/{user}/settings/billing/usage` works and returns real data. Reporting
an instrument as unavailable without trying its replacement is how a diagnosis stalls at a band.

**MEASURED, and each line eliminates something:**

| probe | reading | eliminates |
|---|---|---|
| `repos/{r}/actions/permissions` | `enabled: true`, `allowed_actions: all` | repo/org-level Actions disablement |
| `user.plan` | **pro** | unpaid / free-tier-without-Actions |
| August billing, all products | **$0.99 billed** (storage only); everything else discounted to $0 | unpaid balance / hard billing hold |
| **Reframe** (same account) latest run | **`success` at 06:05:25Z today** — after this repo broke at 04:33:59Z | account suspension, global GitHub outage, org policy |
| `agent-skills-toolchain` visibility | **private** | — |
| `Reframe` visibility | **public** | — |
| failed-run duration | created 06:59:29Z, updated 06:59:34Z — **5 seconds, `steps=0`** | a test/step failure; this is a refusal to allocate a runner |

**The account can run Actions right now — but only on a PUBLIC repo.** Public repos draw from a
free, unmetered pool; private repos draw on the Pro plan's 3,000-minute monthly allowance. So
Reframe succeeding is *not* a clean control for the private allowance — it is a control for
everything else, and it clears all of it.

### CONFIRMED — the allowance is exhausted at 108%. This is no longer a hypothesis.

The band below said "likely 65-80%, because I never obtained a direct remaining-minutes figure."
**That figure was one query parameter away.** `settings/billing/usage` accepts `?year=&month=`,
which returns **per-repository** rows (638 of them) instead of the monthly aggregate I had been
reading. Splitting those by repository visibility settles it:

| repository | visibility | Actions minutes |
|---|---|---:|
| `agent-skills-toolchain` | **PRIVATE** | **2,506** |
| `PrimariRo` | **PRIVATE** | **726** |
| `Reframe`, `bilbo-app`, `momentstudio`, … | public | 12,239 (free, unmetered) |
| | | |
| **PRIVATE TOTAL** | | **3,240 / 3,000 = 108%** |

Every observation now has one cause. Private repos cannot allocate a runner because the Pro
plan's 3,000 included private-repo minutes are spent and no spending limit is configured to
overflow into paid usage. Public repos draw from a separate free pool, which is exactly why
`Reframe` completed a run at 06:05:25Z while this repo could not start one.

**Caveat, disclosed rather than buried:** `codex-session-manager` (910 minutes) returned neither
`true` nor `false` for visibility — renamed or deleted. If it was private, the overage is larger
than 3,240; it cannot be smaller.

**Owner action, and it is cheap.** The overage is ~240 minutes at $0.006/min ≈ **$1.44**.
Setting any non-zero Actions spending limit (Settings → Billing → spending limit) restores
private-repo CI immediately. The alternative — waiting for the monthly reset on **2026-09-01** —
is ~18 days away and is not a viable plan for a repo taking 262 commits in 36 hours.

**Superseded reading, kept as evidence of what the weaker instrument supported:** the original
"likely 65-80%" band, held because `check-suites` (which carries the refusal reason) is 403 to
this token. That remains true and no longer matters — a detector limit on one probe was not a
reason to stop looking for another.

**Where the owner should look:** GitHub → Settings → Billing → *Actions minutes used this month*
and *spending limit*. If the allowance is spent, raising or enabling the spending limit restores
private-repo CI immediately. **UNVERIFIED** that this is the cause; it is the hypothesis that
survives every probe I could run.

**Consequence, and it is the important part: no claim of "green" below is CI-verified after
04:33:59.** For everything committed since, "green" means *the repo's own gates pass locally* —
a weaker statement, and one that has been wrong before on this repo for five separately-measured
local-green/CI-red mechanisms (CRLF-vs-LF blobs, f-string syntax under Python <3.12, the
`newline=` kwarg under <3.13, `fetch-depth: 1` hiding pinned blobs, and a Windows absolute path
frozen into a git blob).

**This needs the owner.** No agent action clears it.

---

## 1. Volume delivered

**MEASURED.** 242 commits in the last 36 hours, by lane scope:

| lane | commits | principal artifacts |
|---|---:|---|
| SLOP | 38 | published-command markers, stale-baseline reconciliation |
| MCPRESEARCH | 35 | `docs/mcp-audit/` — 4 build rounds, 3 defect-closure rounds, capability/disposition table |
| SSOT | 31 | `docs/ssot/SSOT-CLONE-INVENTORY.md` (686 lines), 178-checkout classification |
| HOOKRESEARCH | 29 | `docs/hook-audit/` — 5 build rounds, 4 correction rounds, citation gate |
| P2NEXT | 25 | `command-center/p2-next/` — 20 receipt/proof JSONs |
| RULERESEARCH | 17 | `docs/rule-audit/` — 4 build + 4 adversarial rounds |
| DOCS | 16 | lane-doc reconciliation |
| SKILLS2 | 8 | `command-center/grounding/SKILLS2-*` — grounding + 5 rounds |
| CIGREEN | 4 | gate wiring |
| other/unscoped | 39 | secrets, interpreter-floor, sast, claim-gate |

Both the four research lanes the owner asked for by name — **MCPs, hooks, rules** — and the
**skills** lane flagged as unfinished have produced multi-round build-plus-adversarial-review
artifacts. That is the shape that was asked for. Whether the *content* survives review is a
separate question this document does not settle for them.

---

## 2. What is NOT done

### 2.1 Blocked on the owner — no agent action can advance these

| # | item | evidence | why it is stuck |
|---|---|---|---|
| B1 | **GitHub Actions cannot run** | §0 above | Billing/quota/org setting. Owner-only. |
| B2 | **Prompt Two condition 11** | `command-center/p2-next/OWNER-DECISION-condition-11.md` | Blocks **all 2,007 remaining units**. Three options written up, B recommended. Needs a pick. |
| B3 | **22 of 29 owner decisions still OPEN** | `command-center/OWNER-DECISIONS.md` **MEASURED** | Q3, Q6, Q9–Q25, OQ-5, OQ-6, OQ-7. The file itself says to send them as one batch, not piecemeal. |
| B4 | **3 open PRs** (#281, #282, #283) | **MEASURED** | See the correction in §3 — none is currently confirmed mergeable. |
| B5 | **Credential `sha256:839ca3224e60`** | prior session | Classification oscillates POTENTIAL-CREDENTIAL / UNKNOWN. **UNKNOWN means the scan did not finish, not that it is clean.** Rotation is the owner's per AGENTS.md §9; I will not touch it. |

Of these, **B2 is the largest single unblocker**: one decision releases 2,007 units of work.
B1 is the most urgent, because while it holds, nothing else can be *verified* even if it is fixed.

### 2.2 Not blocked — genuinely unfinished work

| item | state | next action |
|---|---|---|
| `chk` retirement | ~122 MB, triage says safe | Safe to retire; deliberately deferred so it does not compete with live lane writes. |
| `scratch` retirement | **NOT safe yet** | `salvage_scratch.py` must report 0 **and** the directory must show no writes in the last 10 min. It was under active write when first assessed — see §3. |
| Working tree | **MEASURED**: 313 untracked, 22 modified, 1 unpushed commit | Lane scratch, mostly `_`-prefixed probes. Needs a sweep once lanes idle. |
| Lane round convergence | Lanes are still writing (28 files in the 30 min before this doc) | The grind's own stopping rule is "until no round refutes"; that has not been reached. |

---

## 3. Corrections — claims from this session's record that re-measurement contradicts

Recorded verbatim rather than silently fixed, because a claim that was wrong once will be wrong
again if only its conclusion is edited.

**C1 — WITHDRAWN, and the withdrawal is the interesting part.** This entry originally read:
*"'PR #281 is green and mergeable.' STALE. Re-measured now: `mergeable=UNKNOWN`."* **That
correction was itself wrong**, and it was wrong by committing the exact error the rest of
this document is about.

`mergeable` is computed **asynchronously**: GitHub returns `UNKNOWN` on the first query and
resolves on a subsequent one. I read it once, saw `UNKNOWN`, and — because this estate has a
note saying *"`mergeStateStatus: UNKNOWN` is not a synonym for mergeable"* — treated the
single reading as evidence the earlier claim had decayed. The note is correct; using it to
convert one unresolved poll into a verdict is not. Re-polled 20 seconds later, **MEASURED**:

| PR | mergeable | state |
|---|---|---|
| #281 | MERGEABLE | CLEAN |
| #282 | MERGEABLE | CLEAN |
| #283 | MERGEABLE | UNSTABLE (its checks are the dead ones) |

So the original record was **right**: #281 is green and mergeable. Only the "one open PR"
part was wrong — there are **three**.

This also **narrows §0**. I had briefly widened the hypothesis to "GitHub is degraded for
this repo generally", on the strength of all three PRs reading UNKNOWN at once. They resolve
normally, so mergeability computation is healthy and **only Actions is broken** — which
raises confidence in the Actions-specific reading (quota / billing / disablement) rather
than a platform-wide fault.

**C2 — "the `scratch` directory is retire-safe." REFUTED, withdrawn in place.** It was under
active write by a live lane; publishing that verdict would have destroyed lane artifacts. 21
files were salvaged. The missing step was one command — `find <dir> -newermt '10 minutes ago'` —
and it is now a precondition in the triage document.

**C3 — "the cross-vendor rail is down." REFUTED.** Reported four times and wrong each time. A
single failing `mcp__codex__codex` call was treated as evidence of a dead rail; an independent
probe returned exit 0 with a nonce, and the control (empty `CODEX_HOME`) returned exit 1 / 401.
Textbook single-signal verification failure.

**C4 — "both new red gates should clear." WRONG when stated.** CI then showed `gate-sast` still
red on three findings *inside my own fixer*, and `gate-lint-format` newly red from a regression I
had introduced in the same push.

**C5 — the synthesis lane's B7/CL7 "sibling lane" was me.** `command-center/GRIND-STATUS.md`
records that `rule-audit` flipped PASS→FAIL mid-session because *"a sibling lane's uncommitted
edit to a shared workflow destroyed the fixture of one of its controls"*, and correctly notes
nothing in RULERESEARCH changed. **There was no sibling lane.** It was this orchestrator: I added
`push: branches: [main]` to `skill-dual-write.yml` in the working tree, which is the known-bad arm
of two `test_control_fires_on_a_workflow_with_no_push_trigger` controls.

The edit is **reverted** and B7 is **resolved** — re-measured after the revert: `rule-audit`
self-test 12/12, gate 9/9, `test_rule_audit_ci_wiring.py` 16 passed, `test_docs_gate_ci_wiring.py`
+ `test_ci_wiring.py` 25 passed. The lane independently observed it go green and marked B7
RESOLVED without being told.

Recorded because the misattribution is the expensive part: a future reader chasing "which lane
broke rule-audit" would be hunting a defect that never existed in any lane. The real lesson is
that **an uncommitted working-tree edit to a shared file is visible to every other agent on this
disk** — it has no branch to contain it. The full analysis of what I was attempting, and why it
was refuted, is in `docs/harness/skill-dual-write-trigger-gap-2026-08-14.md`.

---

## 4. What "green" currently rests on

**MEASURED.** With CI unavailable, two committed runners execute the CI steps that *can* run on
this box — **76 steps green, 0 failing**:

| runner | scope | result |
|---|---|---|
| `_ci_local_substitute.py` | the 8 small workflows | **29/29 pass** |
| `_ci_quality_nopip.py` | quality.yml's no-`pip install` slice | **47/47 pass** |

Still unverified and not claimed: every `--cov-fail-under=100` suite (they need a per-subproject
`pip install -e`), the opengrep SAST scan and the gitleaks secret scan (Linux binaries), and the
docker-service benchmark. No count of passing steps substitutes for those.

Three scope bugs were found *in the runners themselves*, each by a control rather than by review,
and each fixed by delegating to a gate that already existed:

* `ruff format --check .` reported 50 red files — it walked the working tree (313 untracked lane
  files CI never sees) **and** the working-tree bytes, while `core.autocrlf=true` means a tracked
  file is CRLF on disk when its blob is LF. Delegated to `_b9_format_tracked.py`, which
  materialises from `git cat-file -p`: **0 of 2,716 tracked files unformatted**, 4 controls firing.
* `ruff check .` reported 4 violations, every one in untracked scratch.
* Its replacement then reported **90** violations while `ruff check .` reported 0 — a
  self-contradiction, and the new tool was wrong: ruff applies `extend-exclude` during file
  *discovery*, so paths named on argv bypass it and the deliberate p2-wave control fixtures read
  as real findings. `--force-exclude` fixes it: **0 violations on 2,700 tracked files**.

All three were the same defect wearing different clothes — measuring a surface CI does not have.

The earlier hand-run of the lane gates, for the record:

```
mcp-audit/ci_gate.py                     SUCCESS:mcp-audit-ci-gate
rule-audit/ci_gate.py                    SUCCESS:rule-audit-ci-gate
slop-report/check_published_commands.py  SUCCESS:published-cmds
ssot/ssot_wiring_check.py                SUCCESS:ssot-wiring-check
ssot/ssot_drift_gate.py                  SUCCESS:ssot-drift-gate
hook-audit/check_citations.py            FAILED:cite-check
```

The single failure is `docs/hook-audit/INTEGRATE-R1.md — ZERO citations`. **MEASURED**: that file
is untracked, dirty, and was modified 135 seconds before the check — the HOOKRESEARCH lane writing
its integrate document live. It is not committed, so CI would never have seen it. Left alone
deliberately: editing a file a live agent is mid-write is how the `scratch` near-miss (C2) happened.

Every push since 04:33:59 was gated on three local checks over changed Python files — `ruff format
--check`, `ruff check`, and `py -3.11 -m py_compile` — all three clean, or the push was held. That
is a real gate, and it is **not** equivalent to CI.

---

## 5. Honest assessment

The grind is **not** converged and this document does not claim it is. What is true:

* The four research lanes the owner named all exist with multi-round adversarial artifacts.
* Main was fully green at `a4594b69` — **FROM-RECORD**, and that was the last CI-verified state.
  It included five gate workflows the lanes built that had never executed before.
* 242 commits of real work landed in 36 hours.

What is equally true, and matters more:

* **Nothing committed after 04:33:59 has been CI-verified**, and this repo has burned five
  distinct local-green/CI-red mechanisms already. The probability that ~1.5 hours of unverified
  commits are all actually green is not high — call it **uncertain, 40-60%**, and I would not
  claim better without a runner.
* **The two largest items are both owner decisions**, not engineering work. B2 alone gates 2,007
  units. No amount of further agent grinding moves either.
* Four claims in this session's own record needed correction on re-measurement (§3). That is the
  base rate to apply to any *un*-re-measured claim in the lane artifacts, including the ones that
  say a lane is finished.

The most useful next thing is not more lane rounds. It is **B1 and B2** — restore the runner, pick
condition 11 — after which the accumulated work can actually be verified instead of asserted.