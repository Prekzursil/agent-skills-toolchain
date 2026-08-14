# GRIND-STATUS — nine-program synthesis

Written by the SYNTHESIS lane, 2026-08-14. Every gate below was **re-executed by me**; no lane's
claim about its own gate is repeated here without an independent run.

> **The input payload arrived TRUNCATED.** It carried **1 of 9 lanes** (SSOT), and that one was cut
> mid-sentence inside round-3 `detector_controls` ("SELF-CONTRADICTION TREA…"). The other eight
> lanes — HOOKRESEARCH, MCPRESEARCH, RULERESEARCH, P2NEXT, SLOP, DOCS, SKILLS2, CIGREEN — were
> **reconstructed from their on-disk dossiers and `git log`**, exactly as the last wave did. That
> reconstruction is the basis for everything attributed to them; where I could not measure a lane
> claim first-hand I say so rather than restating it.

COVERAGE: §1–§8 are measured. What is **not** measured: the interior reasoning of the eight
reconstructed lanes (I re-ran their gates and read their dossier headings, not every round), and
anything CI-side after 04:33:59Z (§2 B1).

## How to read this

| band | meaning |
|---|---|
| **almost certain (90-99%)** | I executed it this session, with a both-states control that discriminated. |
| **likely (55-80%)** | Measured, but inherits a disclosed blind spot named inline. |
| **uncertain (20-55%)** | One signal only, or an instrument I could not control. |

Snapshot warning: `origin/main` moved during this session and lanes committed while I measured.
Re-run before acting on any count.

---

## 1. SHIPPED — only what survived refute

I re-executed **22 lane gates** with a three-state control (`PASS` / `FAIL` / `MISSING`) proven to
discriminate before any verdict was read: a known-exit-0 command → PASS, a known-exit-1 → FAIL, a
fabricated path → MISSING. **19 PASS, 3 non-PASS — and all three non-PASS are explained below, none
of them a live lane defect.** Anchor: `command-center/GRIND-GATE-RESULTS.json`.

| lane | headline gate (re-run by me) | result | CI workflow | fires on push→main |
|---|---|---|---|:--:|
| SSOT | `ssot_wiring_check.py` · `ssot_drift_gate.py` · `pytest ci/tests/test_ssot_wiring.py` | **PASS** ×3 (6/6 wires, 16 passed) | skill-dual-write.yml | **NO** ⚠ |
| HOOKRESEARCH | `check_citations.py` · `test_citation_gate.py` | **PASS** (43/43 cases) | hook-audit.yml | yes |
| MCPRESEARCH | `mcp-audit/ci_gate.py` | **PASS** | mcp-audit.yml | yes |
| RULERESEARCH | `rule-audit/ci_gate.py` + r2/r3/r4-receipt/r5 | **PASS** ×5 | rule-audit.yml | yes |
| P2NEXT | `rail_count_gate.py` · `split_review_gate.py` | **PASS** ×2 | p2next-rail-count.yml | yes |
| SLOP | `check_published_commands.py` | **PASS** — 428 published commands / 366 docs, **0 NEW** unrunnable | no-runtime-junk.yml:135 | yes |
| DOCS | `test_docs_executable_claims` · `test_docs_gate_ci_wiring` · `test_command_doc_promises` | **PASS** ×3 | quality.yml | yes |
| SKILLS2 | `test_deploy_skills_daily` · `test_check_skill_deploy_drift` | **PASS** ×2 | skill-dual-write.yml | **NO** ⚠ |
| CIGREEN | `command-center/ci/interpreter_floor_gate.py` | **PASS** | interpreter-floor.yml | yes |

**almost certain (90-99%)** that every lane's CI-wired headline gate passes *on this disk at this
commit*. That is a narrower statement than "the lanes are green" — see §2 B1 and §5 CL6.

Volume, measured: **247 commits in 36 hours**. Per-lane last-commit age / 36h commit count —
HOOKRESEARCH 0.4h/32 · P2NEXT 1.2h/27 · SLOP 1.7h/38 · MCPRESEARCH 1.9h/36 · SSOT 2.4h/32 ·
CIGREEN 2.7h/9 · SKILLS2 4.5h/9 · RULERESEARCH 6.0h/17 · DOCS 25.3h/4.

The three non-PASS results, each run down to a cause:

1. **`test_citation_gate.py` rc=5 — MY detector failure, not a defect.** I invoked it through
   `pytest`; it is a standalone `main()` script, so pytest collected zero tests. `hook-audit.yml:66`
   documents this exactly ("NOT `pytest`… pytest collects ZERO tests from it"). Correct invocation:
   **ALL PASS (43 cases, 0 failed)**. Recorded rather than deleted — an rc=5 read as a lane failure
   would have been a fabricated finding.
2. **`r4_credential_rule_gate.py` rc=1 — pinned red ON PURPOSE.** `rule-audit.yml:127` declares it:
   the gate's parent `ci_gate.py` expects rc=1 for this entry, which is why `rule-audit ci_gate`
   itself PASSES. The underlying defect is real and owner-only (§6 D2). This is a known defect kept
   **tracked** instead of silently tolerated — good engineering, not a broken gate.
3. **`hook_predeploy_gate.py` rc=1, 21 HAZARDs of 74 findings — deliberately not a CI gate.**
   `hook-audit.yml:94` excludes it with the measurement: it diffs the repo hook tree against the
   live `~/.claude`, which does not exist on a runner, where it fails closed at exit 2. It is a
   **local pre-deploy gate**. See §2 B4 — the 21 hazards are real and nothing in CI can ever see them.

---

## 2. STILL BROKEN — with the precise blocker

**B1 — GitHub Actions cannot start a job. This gates verification of everything else.**
`almost certain (90-99%)` that no step executes; `likely (60-85%)` that the cause is Actions
quota / a spending limit.
Measured on run `31777879813` (`quality`, event=push, main): **all 8 jobs `conclusion=failure` with
`nsteps: 0`**, started 06:53:27Z and completed 06:53:30–38Z — 3 to 11 seconds, no checkout, no
install, no logs (`--log-failed` returns empty). Every workflow on main behaves identically.
What I could newly rule out that the previous pass could not: `actions/permissions` returns
`{"enabled":true,"allowed_actions":"all"}`, so this is **not** a repo-level Actions disablement.
What still blocks a verdict: the user billing endpoint is **410 Gone** (moved) and check-run
annotations return **403** to this PAT. Two instruments closed, so "quota" stays a band.
**Owner-only. No agent action clears it.**

**B2 — SSOT and SKILLS2 gates have never run on the path the work actually takes.**
`almost certain (90-99%)`. Their only CI wiring is `skill-dual-write.yml:114` (and its `ci/tests`
glob), and that workflow's `on:` block is **`pull_request` only** — no `push:` key at all. Meanwhile
**all 247 commits landed by direct push to main.** Two independent signals: the static `on:` parse
(control: `quality.yml` correctly reads push→main **True**, `skill-dual-write.yml` **False**), and
the observed run history on main, which lists 9 workflow names and **never** `skill-dual-write`.
`ssot_drift_gate.py` is invoked by **no workflow at all**. Blocker: fixing it means editing
`.github/workflows/skill-dual-write.yml`, which open PRs **#281** and **#282** both touch — see §6 D4.

**B3 — a real §9 credential inversion in `agent-self/config/AGENTS.md`, unfixed.**
`almost certain (90-99%)`, executed. `r4_credential_rule_gate` reports 4 violations: the bullet
forbidding an agent to rotate/revoke/regenerate a credential is **absent from the deploy source**,
and §9/§9b instead instructs the agent to *"rotate, don't just delete"* — the banned action. The
live `~/.claude/AGENTS.md` carries the protective wording; the deploy source would **overwrite it
with the inversion**. Per AGENTS.md §9 an agent does not change credential policy, so this lane may
only propose. **Owner action (§6 D2).**

**B4 — 21 HAZARDs in the repo-vs-live hook fleet, structurally invisible to CI.**
`almost certain` that the gate reports them; `uncertain (20-55%)` what fraction are genuine drift
versus expected local-only hooks — I did not triage all 74 findings. Sample: `PreToolUse` repo has
12 entries, live has 13 (live-only `workflow-monitor-autolaunch/check.py`); `UserPromptSubmit` repo
has `open-loops/trigger_match.py`, live has `semantic-router/route.py`. This is the deploy-drift
class `harness-vcs-hygiene` exists to catch.

**B5 — 3 open PRs, none confirmed mergeable.** #281 `ci: execute gate-cs-wiring and
gate-skill-deploy-hop, which have never run`, #282 `fix(codex-databricks-fanout): the shipped batch
runner has never compiled`, #283 `ci(sast): split install from scan`. All three
`mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN` — the expected consequence of B1, and **UNKNOWN is
not a synonym for mergeable** (this estate's own recorded lesson).

**B6 — 337 dirty working-tree rows (314 untracked, 23 modified)** across a shared worktree. Six of
those were orphaned deliverables; I closed that subset (§8). The rest is lane probe scratch.

---

## 3. LANES THAT DIED

**DOCS — died, on an AND-gate of two mechanically independent signals.** `almost certain (90-99%)`.
Signal 1 (git history): last commit **25.3 hours** ago, **4 commits in 36 hours** against a
per-lane median of 27. Signal 2 (filesystem, independent of git): its 7 untracked `_LANE-DOCS-*.md`
documents are idle **25–37 hours**, with 0 written in the last 10 minutes. Neither signal alone
would be admissible — mtime distinguishes only "not written recently", never stalled-vs-done — but
history and filesystem agreeing is the AND-gate. Its gates still PASS (§1) and rounds R4–R8 plus
INTEGRATE-R2 **did** land; what died was the tail, leaving GROUNDING, ADVERSARIAL and VERIFY
committed nowhere.

**The synthesis stage itself has now died four times.** Three before this run — twice on
`401 API key is invalid`, once on a session limit (recorded in `docs/GRIND-STATUS.md`, which exists
only because the orchestrator wrote it by hand) — and a fourth partial death this run: **the payload
was truncated to 1 of 9 lanes.** Reconstruction from disk worked, again.

**No other lane died.** The remaining eight last committed 0.4–6.0 hours ago with 9–38 commits each;
that is a program winding down, not a lane freezing. I am explicitly **not** calling RULERESEARCH
(6.0h) or SKILLS2 (4.5h) dead — one signal, and their deliverables are committed.

---

## 4. OVERCLAIMS CAUGHT

The measured base rate on this estate is ~7 overclaims per 5 real defects. This pass found **10
overclaims against 3 real defects**, which is *worse* than the base rate — and **3 of the 10 are
mine**. Not softened.

| # | claim | why it is wider than its evidence | correctly-scoped version |
|---|---|---|---|
| O1 | `CLAUDE.md`: *"This block is itself gated — `ssot_wiring_check.py` **fails CI** if the rule above drifts"* | Its only wiring is in a **`pull_request`-only** workflow. The 32 SSOT commits went straight to main, where it never ran once. | "…fails CI **on a pull request**. It does not run on a push to main; see B2." |
| O2 | SSOT R1: *"**170 checkouts, not 25**"* | `merge-base --is-ancestor` compared `== 0`, filing rc=128 ("could not be asked") as "no" — 20 rows never got a verdict. | 174 by union, 178 after round 3. Both 25 and 170 are REFUTED and kept in the inventory with the defect that produced each. |
| O3 | SSOT R2: *"132 hold unpushed commits, dirty files or a staged index. **This is the fleet's real data-loss surface**"* | The predicate is a **disjunction**; 54 of the 132 have HEAD already on origin/main and differ only in working-tree files. | "78 hold a HEAD not on origin/main — that is the surface; 54 differ only in uncommitted files." |
| O4 | SSOT R2: *"43 retire candidates"* | `rev-list HEAD --not --remotes` measures the checkout's **local remote-tracking snapshot**, not "on a pushed branch" — the criterion §5 actually states. 4 of the 43 fail it. | "39 candidates plus 4 known-unsafe rows, until the test is re-based on origin/main." |
| O5 | SSOT R1: *"identity_by_ancestry.py … **supersedes** the store-membership signals"* | It drops 4 checkouts the superseded test finds (shallow clones). | "the correct test for a complete-history checkout; must be **UNIONed** with the name signal, not substituted for it." |
| O6 | SSOT R3 DoD-1: *"**178/178** classified, two agreeing signals"* | 9 worktrees + 168 clones = **177**. A whole kind (the severed worktree) was missing and `signals_agree` is False on that row. | Already corrected in `CLAUDE.md` and `population-classified.json`, with a `kind_arithmetic` block that fails closed. |
| O7 | *mine* — `map_gates.py`: *"16 of 27 lane gates are unwired"* | Two defects in one detector: the regex anchored `check_`/`_gate` at end-of-name (so `check_citations.py` was never a candidate), and substring matching counted `hook_predeploy_gate.py` as wired because `test_hook_predeploy_gate.py` appears in a workflow — **use-vs-mention**, the exact class this repo keeps re-learning. | Discarded. Replaced by exact-token search plus reading each workflow's actual `run:` lines. |
| O8 | *mine* — *"HOOKRESEARCH `test_citation_gate` FAIL"* | Wrong invocation (pytest on a `main()` script). | 43/43 PASS. |
| O9 | *mine* — mtime control printed `discriminates=False` | The instrument was fine; my **threshold** was mis-set (I asserted a 5-minute bound on a file written 14 minutes earlier). A self-contradicting control is a detector failure and I re-ran it properly rather than waving it through. | Re-run with a just-created temp file: `discriminates=True`. |
| O10 | prior `docs/GRIND-STATUS.md` §4: *"`hook-audit/check_citations.py` **FAILED:cite-check**"* | True when written (an untracked doc was mid-write); **STALE now**. | Re-executed this session: **PASS**. |

Real defects found this pass: **B2** (PR-only gate blind spot), **B3** (credential inversion, was
already tracked by its lane), **CL3** (6 orphaned deliverables). Ratio 10:3.

---

## 5. CROSS-LANE FINDINGS — only visible from here

**CL1 — Every lane verified "is my gate wired?" and none verified "does its workflow fire on the
event that delivers our work?"** That is a *control that cannot distinguish the two hypotheses*:
H1 "the gate protects main" and H2 "the gate exists but is unreachable on the delivery path" both
produce a green `wired: yes`. Two of nine lanes (SSOT, SKILLS2) are in H2. No single lane could see
this — it needs the trigger matrix across all 12 workflows and the fact that work lands by push.

**CL2 — There are now TWO `GRIND-STATUS.md` files at different paths.** `docs/GRIND-STATUS.md`
(tracked, hand-written by the orchestrator after the synthesize stage died three times) and this one
at `command-center/GRIND-STATUS.md`. A reader who finds one will not know the other exists. Fixed
in §8 by cross-linking both, additively — I did not delete or rewrite the prior document, because
its §3 corrections are frozen evidence of what was wrong when.

**CL3 — SSOT's own #1 finding reproduced in three sibling lanes.** SSOT's grounding round opened
with "the SSOT lane's own output is untracked… one `git clean -fd` from gone". Measured across all
nine lanes, **6 deliverables with no tracked successor** were sitting untracked: DOCS' GROUNDING /
ADVERSARIAL / VERIFY, HOOKRESEARCH's `_v4_VERIFIER-NOTES.md`, and P2NEXT's `P2NEXT-GROUNDING-R2.md`
(which **supersedes a tracked R1** — the newer document was the unreachable one) and
`P2NEXT-VERIFY-R4.md`. The lesson was written down in one lane and never crossed to the others.
Closed in §8.

**CL4 — The repo's own gate-discovery habit is substring-based, and I reproduced the defect while
auditing it.** O7. Anything asking "is X wired?" by searching workflow text for `X` will count
`test_X` as a hit. `hook_predeploy_gate.py` is the live example: named 4 times in `hook-audit.yml`,
**invoked zero times**.

**CL5 — Three lanes independently built the same protection and one did it differently, correctly.**
RULERESEARCH pins a known-unfixable defect at `rc=1` inside its own `ci_gate.py`, so the defect stays
red-tracked while the gate stays green and the day it is fixed the entry goes red and forces the
promotion. HOOKRESEARCH instead **excludes** its local-only gate from CI with a documented
measurement. SSOT has no equivalent mechanism for `ssot_drift_gate.py`, which is simply unwired.
RULERESEARCH's pattern is the one to propagate.

**CL6 — "green" currently means "green on this disk".** CI has executed no step since 04:33:59Z, so
**no lane's green claim after that time is CI-verified**, including every claim in §1. This repo has
already burned five distinct local-green/CI-red mechanisms (CRLF-vs-LF blobs, f-strings under
Python <3.12, the `newline=` kwarg under <3.13, `fetch-depth: 1` hiding pinned blobs, and a Windows
absolute path frozen into a blob). Probability that ~2h of unverified commits are all genuinely
CI-green: **uncertain (40-60%)**.

---

## 6. OWNER DECISIONS

Each is a yes/no or pick-one with a recommended default. Nothing here is agent-actionable.

| # | question | recommended default | why |
|---|---|---|---|
| **D1** | GitHub Actions runs no steps (B1). Raise / re-authorise the Actions spending limit for `Prekzursil`? | **Yes — check the spending limit first.** | Actions is `enabled:true`, so it is not a repo setting. Billing API is 410 to me and annotations 403, so only you can read it. **Everything else is unverifiable until this clears.** |
| **D2** | `agent-self/config/AGENTS.md` §9 tells the agent to *rotate* credentials — the inverted policy — and would deploy over the correct live copy (B3). Repair it? | **Yes**, repair the deploy source to match live, then promote `r4_credential_rule_gate` from pinned-rc=1 to blocking rc=0 **in the same change**. | Credential policy is owner-only per AGENTS.md §9. The gate already encodes the promotion step. |
| **D3** | `skill-dual-write.yml` is `pull_request`-only, so SSOT's and SKILLS2' gates never run on a push to main (B2). Split the 6 push-safe steps into a workflow that fires on push? | **Yes, split them out** — do **not** just add `push:` to the existing file. | The D-001 dual-write job is genuinely diff-based (`--base origin/main --head HEAD`) and belongs on `pull_request`; the other six steps are absolute checks. Also: PRs #281/#282 already touch this file, so this must be sequenced with them, not raced. |
| **D4** | Prompt Two condition 11 — `command-center/p2-next/OWNER-DECISION-condition-11.md`. | **Option B**, as that document recommends. | It gates **all 2,007 remaining units**. One decision, largest single unblock. *(FROM-RECORD — I did not re-derive the option set.)* |
| **D5** | Merge PRs #281 / #282 / #283? | **Hold until D1 clears**, then merge #281 first. | All three are `mergeable: UNKNOWN` purely because CI is down. #281 fixes never-run gates, which is the same class as B2. |
| **D6** | Retire the `chk` / `scratch` checkouts? | **No, not yet.** | `scratch` has 0 commits and thousands of untracked entries in no store anywhere. `git worktree remove` **follows junctions and deletes their targets**. |
| **D7** | 22 of 29 entries in `command-center/OWNER-DECISIONS.md` are still OPEN. | **Answer as one batch**, as that file itself instructs. | Piecemeal answers have already caused re-litigation. |

---

## 7. RANKED NEXT ACTIONS

1. **D1 — restore the runner.** Nothing below can be *verified* while B1 holds, only asserted.
2. **D2 — repair the §9 credential inversion.** The only finding here with a security blast radius:
   a deploy would overwrite correct live policy with the banned instruction.
3. **D3 — give SSOT and SKILLS2 a gate on the delivery path** (split the 6 push-safe steps out).
   Sequence after PRs #281/#282 land to avoid a shared-file collision.
4. **D4 — decide condition 11.** Unblocks 2,007 units; pure decision, zero engineering.
5. **Wire `ssot_drift_gate.py` into a push-triggered workflow**, or adopt RULERESEARCH's pinned-entry
   pattern (CL5). It is currently invoked by nothing.
6. **Triage the 21 `hook_predeploy_gate` HAZARDs** (B4) — repo-vs-live deploy drift that CI
   structurally cannot see, so it will only ever be caught by someone choosing to run it.
7. **Re-run the SSOT retire-candidate predicate against `origin/main`** (O4) before retiring
   anything; 4 of 43 currently fail the lane's own stated criterion.
8. **Sweep the remaining 308 untracked working-tree files** once lanes are confirmed idle. Lowest
   priority — measured as probe scratch, and the 6 real deliverables are now committed.

---

## 8. WHAT I FIXED IN THIS PASS

1. **Committed 6 orphaned lane deliverables that were reachable from no git ref** (CL3) —
   `docs/_LANE-DOCS-GROUNDING.md`, `_LANE-DOCS-ADVERSARIAL.md`, `_LANE-DOCS-VERIFY.md`,
   `command-center/hook-audit/_v4_VERIFIER-NOTES.md`, `command-center/p2-next/P2NEXT-GROUNDING-R2.md`,
   `command-center/p2-next/P2NEXT-VERIFY-R4.md`. Selection was by measurement, not by name: a file
   qualified only if it was untracked **and** had no tracked successor (`_LANE-DOCS-BUILD.md`,
   `-R2`, `-R3` and `-INTEGRATE.md` were **excluded** because R4–R8 and INTEGRATE-R2 are tracked;
   `command-center/hook-audit/GROUNDING.md` was excluded because `docs/hook-audit/GROUNDING.md` is
   tracked). Safety, measured before writing: **0 of the 11 untracked lane `.md` had been written in
   the last 10 minutes** (all idle 4–37h, both-states control on the mtime reader), so this could
   not capture a half-written document — the `scratch` near-miss that this program already survived
   once. Bytes preserved verbatim; nothing reformatted.
2. **Ran the both-states test that committing them requires.** Staging the 6 makes them visible to
   `check_published_commands.py` (which reads `git ls-files`, so untracked files are invisible to
   it) and to `_r6_transcript.py --committed`. Both re-run **green** with all 6 staged —
   428 published commands across 366 documents, 0 NEW unrunnable. Had either gone red I would have
   unstaged and reported instead.
3. **Cross-linked the two GRIND-STATUS documents** (CL2), additively in both directions. The prior
   `docs/GRIND-STATUS.md` is left otherwise untouched — its §3 corrections are frozen evidence.
4. **Re-executed all 22 lane gates** and published the raw results as
   `command-center/GRIND-GATE-RESULTS.json`, so the next pass inherits a receipt instead of a claim.
5. **Recorded three of my own overclaims** (O7, O8, O9) in §4 beside the lanes', rather than
   silently correcting them.

What I deliberately did **not** do: edit `.github/workflows/skill-dual-write.yml` (open PRs #281 and
#282 both touch it — a shared file is the single hazard that red-blocked every PR on main), retire
or delete any checkout, touch `agent-self/config/AGENTS.md` (owner-only credential policy), or run
any `git worktree` subcommand.
