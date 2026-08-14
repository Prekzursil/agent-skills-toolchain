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

> **REVIEWED AND CORRECTED — see §9.** An independent reviewer re-executed all 22 gates and
> re-measured every numeric and owner-facing claim at `22b33d8d`. **Four claims are REFUTED**
> (B3/D2, B5/D5, D3's PR-sequencing premise, and §3's DOCS-died verdict), the §4 ledger
> arithmetic self-contradicted three ways, and one owner item had no row anywhere in this
> document. Each is corrected **in place below** and recorded in §9 with the probe that settled
> it. Nothing was deleted. **§2 numbers are ordered B1, B2, B7, B3…, and §5 ends on CL6 — read
> by label, not by position.**

---

## 1. SHIPPED — only what survived refute

I re-executed **22 lane gates** with a three-state control (`PASS` / `FAIL` / `MISSING`) proven to
discriminate before any verdict was read: a known-exit-0 command → PASS, a known-exit-1 → FAIL, a
fabricated path → MISSING. **19 PASS, 3 non-PASS — and all three non-PASS are explained below, none
of them a live lane defect.** Anchor: `command-center/GRIND-GATE-RESULTS.json`.

> **INDEPENDENTLY RE-EXECUTED at `22b33d8d` (§9 R-CONF).** A reviewer re-ran all 22 gates plus a
> 23rd probe, behind its own three-state control that discriminated (`PASS`/`FAIL`/`MISSING`,
> 3 distinct states, all matching expectation): **21 PASS, 2 FAIL.** Exactly **one** row moved —
> `r4_credential_rule_gate` **FAIL → PASS**, because the §9 credential fix was **committed** in the
> interval (B3, now closed). Every other row reproduced identically. The receipt JSON is therefore
> correct for its timestamp and stale on that one row.

| lane | headline gate (re-run by me) | result | CI workflow | fires on push→main |
|---|---|---|---|:--:|
| SSOT | `ssot_wiring_check.py` · `ssot_drift_gate.py` · `pytest ci/tests/test_ssot_wiring.py` | **PASS** ×3 (~~6/6 wires, 16 passed~~ → **7/7 wires, 21 passed**, re-measured §9 R9) | skill-dual-write.yml | **NO** ⚠ |
| HOOKRESEARCH | `check_citations.py` · `test_citation_gate.py` | **PASS** (43/43 cases) | hook-audit.yml | yes |
| MCPRESEARCH | `mcp-audit/ci_gate.py` | **PASS** | mcp-audit.yml | yes |
| RULERESEARCH | `rule-audit/ci_gate.py` + r2/r3/r4-receipt/r5 | **PASS** ×5 | rule-audit.yml | yes |
| P2NEXT | `rail_count_gate.py` · `split_review_gate.py` | **PASS** ×2 | p2next-rail-count.yml | yes |
| SLOP | `check_published_commands.py` | **PASS** — 428 published commands / 366 docs, **0 NEW** unrunnable *(re-measured at `22b33d8d`: **437 / 369**, 0 NEW, **1 inherited/baselined** — "0 NEW" is not "0 unrunnable")* | no-runtime-junk.yml:135 | yes |
| DOCS | `test_docs_executable_claims` · `test_docs_gate_ci_wiring` · `test_command_doc_promises` | **PASS** ×3 | quality.yml | yes |
| SKILLS2 | `test_deploy_skills_daily` · `test_check_skill_deploy_drift` | **PASS** ×2 | skill-dual-write.yml | **NO** ⚠ |
| CIGREEN | `command-center/ci/interpreter_floor_gate.py` | **PASS** | interpreter-floor.yml | yes |

**almost certain (90-99%)** that every lane's CI-wired headline gate passed *on this disk at the
commit I measured*. That is a narrower statement than "the lanes are green" — see §2 B1 and §5 CL6.

> **The RULERESEARCH row above went PASS → FAIL → PASS while this document was being written, and I
> am leaving the original measurement visible rather than editing it.** The orchestrator's
> *uncommitted* edit to a shared workflow briefly destroyed the fixture of one of its controls; the
> edit was reverted and the gate is **green again at rc=0**. That is **B7**, and it is the sharpest
> illustration in this document of why a gate table is a snapshot: nothing in RULERESEARCH ever
> changed, and for about twenty minutes the honest reading of that row was the opposite of both the
> before and the after.

Volume, measured: **247 commits in 36 hours**. Per-lane last-commit age / 36h commit count —
HOOKRESEARCH 0.4h/32 · P2NEXT 1.2h/27 · SLOP 1.7h/38 · MCPRESEARCH 1.9h/36 · SSOT 2.4h/32 ·
CIGREEN 2.7h/9 · SKILLS2 4.5h/9 · RULERESEARCH 6.0h/17 · DOCS 25.3h/4.

> **Re-measured at `22b33d8d`: 259 commits in 36 hours** (drift, expected). The per-lane row that
> does **not** reproduce is **DOCS 25.3h/4** — path-scoped to `docs/_LANE-DOCS*` it is **14 commits
> in 36 h, newest non-synthesis commit `f6a1f91b` 3.3 h ago**; the same 14 carry a
> `lane-docs`/`docs-lane` subject tag; and `docs/GRIND-STATUS.md` §1 independently counts **16**.
> Three scopes, none of them 4. **That figure is the load-bearing arm of the §3 DOCS-died verdict,
> which is withdrawn there.**

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
What I newly ruled out: `actions/permissions` returns `{"enabled":true,"allowed_actions":"all"}`,
so this is **not** a repo-level Actions disablement.

> **SUPERSEDED — read `docs/GRIND-STATUS.md` §0 for the authoritative diagnosis.** I wrote that
> "the user billing endpoint is 410 Gone… two instruments closed, so quota stays a band". **A 410
> here means *moved*, not *closed*, and I never tried the replacement.** The orchestrator did:
> `users/{user}/settings/billing/usage` returns real data. Their probe set eliminates four
> alternatives I left open — plan is **pro**; August billing is **$0.99**, storage only, so there is
> no unpaid hold; and **Reframe, on the same account, ran Actions successfully at 06:05:25Z today**,
> which clears account suspension, a global outage and org policy. The discriminator neither of us
> saw at first is **private vs public**: `agent-skills-toolchain` is private and draws on the Pro
> plan's 3,000 included minutes, while Reframe is public and draws from a free unmetered pool.
> Best reading: **the private-repo included-minutes allowance is exhausted with no spending limit
> configured to overflow into paid usage** — `likely (65-80%)`, held there because no direct
> remaining-minutes figure was obtained (`check-suites`, which carries the refusal reason, is 403
> to this token).

**Owner-only. No agent action clears it.**

**B2 — SSOT and SKILLS2 gates have never run on the path the work actually takes.**
`almost certain (90-99%)` **as of the committed state.** Their only CI wiring is
`skill-dual-write.yml:114` (and its `ci/tests` glob), and that workflow's `on:` block in the HEAD
blob is **`pull_request` only** — no `push:` key at all. Meanwhile **all 247 commits landed by
direct push to main.** Two independent signals: the static `on:` parse (control: `quality.yml`
correctly reads push→main **True**, `skill-dual-write.yml` **False**), and the observed run history
on main, which lists 9 workflow names and **never** `skill-dual-write`. `ssot_drift_gate.py` is
invoked by **no workflow at all**.

> **LIVE UPDATE, measured after this document was first committed.** The orchestrator was probing
> this fix while I wrote: the **working copy** of `.github/workflows/skill-dual-write.yml` is dirty (` M`) and
> already carries `push: branches: [main]`, while `git show HEAD:` still carries `pull_request`
> only. So the finding stands for the committed state and is being closed in the working tree —
> and its fix has a side effect that was not visible from inside it. See **B7** and **CL7**.
>
> **↑ STALE, and it contradicted B7 six lines below it while both were on the page (§9 R8).**
> Re-measured at `22b33d8d`: the file is **clean** (`git status --porcelain` empty), and **neither
> the HEAD blob nor the working tree contains a `push:` key** — the orchestrator reverted the edit,
> which is what B7 records. Control, so the parse is not the thing that is silent: `quality.yml`
> reads `push: True` from the same reader. **B2 itself is unchanged and still live** — the gate is
> `pull_request`-only and nothing is closing it in any tree. **Nothing is in flight; D3 is the
> whole remedy.**

**B7 — `rule-audit` went RED mid-session and is GREEN again. RESOLVED, kept as evidence.**
`almost certain (90-99%)`, executed at three points in time. While I wrote §1, **the orchestrator** was
experimenting with the B2 fix in the working tree; `docs/rule-audit/ci_gate.py` exited 1 on
`r6_wiring_redproof 4/5 arms behaved`. The failing arm was
`test_control_fires_on_a_workflow_with_no_push_trigger` — a **control** that uses
`skill-dual-write.yml` as its known-negative fixture. It reverted and committed the analysis as
`a8728558`, and named the misattribution in `92735ca8`; the file is clean again and `rule-audit ci_gate` is back to **rc=0**.
Nothing in RULERESEARCH ever changed. I did not touch the shared workflow at any point.

**B3 — a real §9 credential inversion in `agent-self/config/AGENTS.md`, unfixed.**
`almost certain (90-99%)`, executed. `r4_credential_rule_gate` reports 4 violations: the bullet
forbidding an agent to rotate/revoke/regenerate a credential is **absent from the deploy source**,
and §9/§9b instead instructs the agent to *"rotate, don't just delete"* — the banned action. The
live `~/.claude/AGENTS.md` carries the protective wording; the deploy source would **overwrite it
with the inversion**. Per AGENTS.md §9 an agent does not change credential policy, so this lane may
only propose. **Owner action (§6 D2).**

> **LATE UPDATE — a fix is IN FLIGHT and UNCOMMITTED, and that distinction is the whole point.**
> Re-measured at the end of this session, `r4_credential_rule_gate` now exits **0** and prints
> *"the deploy source carries the credential non-negotiable and does not invert it"*, and
> `docs/rule-audit/ci_gate.py` has promoted the entry from *must FAIL: owner action* to
> **blocking**. **Do not read that as closed.** All three files are ` M` (uncommitted), and the
> committed state is unchanged:
>
> | | lines | non-negotiable present | `rotate, don't just delete` present |
> |---|---:|:--:|:--:|
> | **HEAD blob** | 158 | **0** | **1** |
> | working tree | 172 | 1 | 0 |
>
> So the defect is still live in `HEAD`, the gate reads green **only** off uncommitted bytes, and
> a CI run against `HEAD` would still be red. The three files move together, which is the correct
> sequencing — but until they are **committed**, one `git stash` or `git clean` reverts a
> credential-policy fix and re-arms an inverted §9. **This is the same shape as B7, for the third
> time in one session (CL8).**

> **B3 IS NOW CLOSED. The above was true when written and is superseded by commit `22b33d8d`**
> — *"fix(security): the deploy source would have overwritten §9 with its own inversion"* — which
> landed the three files together, exactly as this entry and D2 asked. Verified at that commit on
> an AND-gate of two mechanically independent signals: the **git blob** (`git show
> HEAD:agent-self/config/AGENTS.md` → 172 lines, credential non-negotiable present **×1**,
> `rotate, don't just delete` present **×0**) and the **dirty-state** (`git status --porcelain` on
> all three files → **empty**, so the gate is now reading committed bytes). The gate itself is not
> silent-green: it prints six controls, two of which are both-states arms that **fire** on the
> broken state — *"control INV-1 fires when the bullet is removed again: got True"* and
> *"control INV-2 fires when the inversion is re-introduced: got True"* — and the live arm reports
> **RAN**, not SKIPPED. `almost certain (90-99%)`.
>
> | | lines | non-negotiable | `rotate, don't just delete` |
> |---|---:|:--:|:--:|
> | HEAD blob **before** (`603a5829`) | 158 | 0 | 1 |
> | **HEAD blob now (`22b33d8d`)** | **172** | **1** | **0** |
>
> The credential-policy *content* remains the owner's to confirm (AGENTS.md §9) — the repair copies
> the live file's own wording rather than authoring policy — but **there is nothing left to commit,
> and the `git clean` exposure is gone.** D2 is rewritten accordingly and §7 rank 2 is discharged.

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

> **REFUTED — "none confirmed mergeable" is a SINGLE-POLL ARTIFACT, and this document had already
> been told so (§9 R2).** `mergeable` is computed **asynchronously**: GitHub answers `UNKNOWN` on a
> cold query and resolves on the next one. Measured at `22b33d8d`, two polls seconds apart, which is
> its own both-states control because the instrument changed answer while the world did not:
>
> | poll | #281 | #282 | #283 |
> |---|---|---|---|
> | 1 (cold) | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN |
> | **2 (seconds later)** | **MERGEABLE / CLEAN** | **MERGEABLE / CLEAN** | **MERGEABLE / UNSTABLE** |
>
> So **all three are MERGEABLE**; #283 is `UNSTABLE` because its checks are the dead ones (B1).
> **The estate lesson I invoked is real and I applied it backwards** — "UNKNOWN is not a synonym for
> mergeable" forbids reading UNKNOWN as *green*; it does not license reading it as *not-green*.
> Worse, `docs/GRIND-STATUS.md` **§3 C1 is a withdrawal of this exact error**, recorded hours
> earlier, with the same re-poll table — and this document's own header calls that §3
> *"frozen evidence"* while §5 CL6 cites the same file. **A correction that was already on disk and
> unread: the estate's dominant failure mode is recall, not detection.** New residual, and it is
> the only part of B5 that survives: **#281 is a DRAFT** (`isDraft: true`), so it is not mergeable
> in the operational sense whatever the API field says. See D5.

**B6 — 337 dirty working-tree rows (314 untracked, 23 modified)** across a shared worktree. Six of
those were orphaned deliverables; I closed that subset (§8). The rest is lane probe scratch.
*(Re-measured at `22b33d8d`: **335 rows — 311 untracked, 24 modified.** Ordinary drift; the shape
is unchanged.)*

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

> **THE "DIED" VERDICT IS WITHDRAWN — NEITHER ARM OF THE AND-GATE REPRODUCES (§9 R4).** An AND-gate
> is only as good as its two arms, and both were mis-scoped:
>
> * **Arm 1 (git history) does not reproduce.** Path-scoped to `docs/_LANE-DOCS*`: **14 commits in
>   36 h**, newest non-synthesis commit `f6a1f91b` at **3.3 h** ago — which was **2.5 h** before
>   this document measured, not 25.3. Independently, 14 commits in the same window carry a
>   `lane-docs`/`docs-lane` subject tag, and `docs/GRIND-STATUS.md` §1 counts **16**. Three scopes,
>   none of them 4 or 25.3 h.
> * **Arm 2 (filesystem) was an inert control.** It scanned *"its **7 untracked** `_LANE-DOCS-*.md`
>   documents"* — but a lane that is actively committing **removes files from that set by
>   definition**, so restricting the mtime scan to the untracked residue guarantees an "idle"
>   reading under **both** hypotheses. It cannot distinguish H1 "the lane stopped" from H2 "the lane
>   committed its recent work". Measured over **all 12** lane documents instead: `_LANE-DOCS-BUILD-R5`
>   / `-R6` / `-R7` / `-R8` have mtimes of **4.5–5.2 h**, and `-INTEGRATE-R2` **3.4 h**.
>
> **Correctly-scoped version:** DOCS is the **slowest-committing** lane of the nine, and its
> GROUNDING / ADVERSARIAL / VERIFY tail documents were left **untracked** rather than unwritten —
> which is CL3, not a death. Whether the lane's *process* is still running is **UNVERIFIED and not
> answerable from this disk** (the settling experiment is the orchestrator's live agent roster, not
> git or mtime). Untracked `_LANE-DOCS` count is now **4**, down from 7, because §8 committed three.

**The synthesis stage itself has now died four times.** Three before this run — twice on
`401 API key is invalid`, once on a session limit (recorded in `docs/GRIND-STATUS.md`, which exists
only because the orchestrator wrote it by hand) — and a fourth partial death this run: **the payload
was truncated to 1 of 9 lanes.** Reconstruction from disk worked, again.

**No other lane died.** The remaining eight last committed 0.4–6.0 hours ago with 9–38 commits each;
that is a program winding down, not a lane freezing. I am explicitly **not** calling RULERESEARCH
(6.0h) or SKILLS2 (4.5h) dead — one signal, and their deliverables are committed.

---

## 4. OVERCLAIMS CAUGHT

The measured base rate on this estate is ~7 overclaims per 5 real defects. ~~This pass found **10
overclaims against 3 real defects**, which is *worse* than the base rate — and **3 of the 10 are
mine**.~~ Not softened.

> **THIS LEDGER CONTRADICTED ITSELF THREE WAYS AND ALL THREE COUNTS WERE WRONG (§9 R5).** The
> paragraph above said `10 : 3` with *3 of the 10 mine*; the paragraph closing this section said
> `13 : 4` with *5 of the 13 mine*; §8 item 7 said *"four of my own overclaims (O7, O8, O9, O11)"*.
> A self-contradicting output is a **detector failure, not a finding** — the counts were written
> once and never re-derived when O11, O12 and O13 were appended. Counted mechanically off the table
> rows at `22b33d8d`: **13 rows, of which 6 are marked `*mine*` (O7, O8, O9, O11, O12, O13).** The
> honest ledger for this pass is **13 overclaims : 4 real defects, 6 of the 13 mine** — and the
> reviewer adds **4 more against this document** in §9, which the pass total should absorb rather
> than hide.

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
| O11 | *mine* — §8 of this document, first version: *"Ran the both-states test that committing them requires"* | **True but not sufficient, and it read as sufficient.** I staged the 6 orphans, ran the 2 doc gates, saw green — then added my own 2 files and committed all 8. `check_published_commands.py` reads `git ls-files`, so it only saw the half I was cautious about, and it could not see the *transitive* target at all until the document landed. The very next run went red: `P2NEXT-GROUNDING-R2.md:159` publishes `python command-center/p2-next/_g2_independent.py`, which was untracked. | "Ran the both-states test over the 6 orphans; it did not cover the commit as a whole, and it caught a real regression on the next run." Fixed in commit `5e31a03c` by tracking the target (clean under ruff format / ruff check / py_compile); gate back to **0 NEW unrunnable**. |
| O12 | *mine* — CL7, first version: *"**Remedy is one line** — repoint the control"* | **REFUTED by the orchestrator, which ran the experiment I only reasoned about.** I measured one failing arm (`r6_wiring_redproof`); they ran the whole `ci/tests` suite and got **three** failing tests. And I never saw `ci/tests/test_ci_wiring.py:163`, which forbids the push trigger for a *separate* reason: on a push `--base origin/main --head HEAD` makes base == head, so the parity gate degenerates to a permanently-green no-op. My conclusion was wider than my evidence in the estate's dominant direction. | The fix is a **coordinated multi-file change**, specified in `docs/harness/skill-dual-write-trigger-gap-2026-08-14.md`. Corrected in place in §5 CL7 rather than deleted. |
| O13 | *mine* — B1, first version: *"the user billing endpoint is **410 Gone**… two instruments closed, so quota stays a band"* | **A 410 means the endpoint MOVED, and I never tried its replacement** — I reported an instrument as unavailable and let the diagnosis stall at a band. `users/{user}/settings/billing/usage` works and returns real data. This is the recall failure this estate names as its dominant error: the answer was reachable and unread. | The cause is narrowed to *private-repo included minutes exhausted, no spending limit* at `likely (65-80%)`, with four alternatives eliminated by measurement. Authoritative write-up: `docs/GRIND-STATUS.md` §0. |

Real defects found this pass: **B2** (PR-only gate blind spot, independently corroborated), **B3**
(credential inversion, already tracked by its lane), **CL3** (6 orphaned deliverables) — plus **one
I caused and fixed** (O11). B7 resolved itself and is not counted. **Ratio 13 overclaims : 4
defects — worse than the estate's 7:5 base rate, and ~~5~~ 6 of the 13 are mine** (O7, O8, O9, O11,
O12, O13 — counted mechanically, §9 R5)**.** The two most useful
lines here are O12 and O13, both cases where the orchestrator beat me by *executing* what I had only
reasoned about, or by *trying the replacement instrument* where I had recorded a closed one. A
synthesis lane that only reads is structurally prone to both.

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

**CL7 — the repo uses its own unfixed defect as a test fixture, so fixing B2 is expensive.**
`almost certain (90-99%)`. `ci/tests/test_rule_audit_ci_wiring.py:435` —
`test_control_fires_on_a_workflow_with_no_push_trigger` — uses `skill-dual-write.yml` as its
**known-negative fixture**: it needs a *real* push-triggerless workflow as its known-bad arm.
Fixing B2 destroys the fixture. The control's own assertion message anticipates it verbatim:
*"precondition: skill-dual-write.yml gained a push: trigger, so it is no longer a known-broken
example. Re-point this control."* **A known-broken example used as a fixture makes the defect
expensive to fix, and nothing warns you until you try.**

> **MY OWN OVERCLAIM, CORRECTED IN PLACE (O12).** I first wrote that the *"remedy is one line —
> repoint the control"*. **That is refuted**, and by the orchestrator, which ran the experiment I only
> reasoned about. Two things I had not measured: (a) `ci/tests/test_ci_wiring.py:163`
> `test_workflow_does_not_advertise_null_range_events` asserts `"\n  push:\n" not in text` for this
> workflow — the trigger was **deliberately removed and the decision encoded as a test**, because on
> a push `--base origin/main --head HEAD` makes base == head, so the parity gate degenerates to a
> **permanently-green no-op**, which is the Goodhart-green shape `rules/common/ci-hygiene.md` §1
> forbids; and (b) the change breaks **three** tests, not the one failing arm I measured — I ran
> `r6_wiring_redproof`, they ran the whole `ci/tests` suite. My sentence was wider than my evidence
> in exactly the estate's dominant direction.
> **The authoritative plan is theirs, not mine:** `docs/harness/skill-dual-write-trigger-gap-2026-08-14.md`
> — split the six state checks onto `push` + `pull_request`, keep the diff-based parity check
> `pull_request`-only, and re-point the two controls at a genuinely push-triggerless workflow *after*
> checking the wiring checker does not then flag that one as a violation.

**CL8 — B2 was found twice within the hour, by two different methods, by two different agents — and the second one was the orchestrator, not a lane.** I derived it statically (trigger matrix + run history); the orchestrator derived it by *attempting the fix* and hitting three failing tests. Independent methods, same conclusion — corroboration, not duplication. **The attribution matters:** my first write-up called it a "sibling lane", and `docs/GRIND-STATUS.md` C5 corrects it, because a future reader chasing *which lane broke rule-audit* would hunt a defect that never existed in any lane. The transferable lesson is sharper than the finding: **an uncommitted working-tree edit to a shared file is visible to every agent on this disk and has no branch to contain it** — which is exactly how it entered my measurements as if it were committed lane work. **It happened three times in this one session**, which promotes it from an anecdote to the pass's central operational finding: (1) the `skill-dual-write.yml` push trigger, which flipped `rule-audit` red under me mid-write; (2) the same file reverted, which flipped it green again; and (3) the §9 credential repair (B3), where an uncommitted working tree makes the gate print SUCCESS while `HEAD` still carries the inverted policy. In all three the *local* gate was an honest reading of dishonest bytes. **Operational rule this earns: on a shared disk, a gate result is only citable together with the dirty-state of the files it read** — `git status --porcelain -- <subjects>` belongs in the receipt beside the exit code.

**CL9 — the local-RED / CI-green inverse, newly measured by the orchestrator and worth carrying.**
`python -m pytest ci/tests tools/d001-dual-write/tests -q` reports **7 failed, 909 passed** locally;
**four fail at clean HEAD** as pure Windows artifacts (NTFS has no exec bit; Windows paths cannot
hold non-UTF-8 bytes; one ref-race left UNVERIFIED). This repo has burned five *local-green/CI-red*
mechanisms (CL6); this is the mirror image, and it matters because a local CI substitute that swept
`ci/tests` wholesale would show four permanent false reds — and a standing false red trains you to
ignore the output.

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
| **D1** | GitHub Actions runs no steps on this **private** repo while the same account runs them fine on a **public** one (B1). Go to **Settings → Billing → Actions minutes used this month / spending limit** — is the 3,000-minute Pro allowance spent, and is the spending limit $0? | **Raise or enable the spending limit** (or wait for the monthly reset). | Every other cause is eliminated by measurement: Actions `enabled:true`, plan `pro`, August billing $0.99 storage-only, and a **public** repo on the same account succeeding *after* this one broke. **Everything else in this document is unverifiable until this clears.** |
| ~~**D2**~~ | ~~The §9 credential inversion … **Commit the three files together?**~~ **SUPERSEDED — the commit happened. This question can no longer be answered as phrased.** | — | Landed as `22b33d8d` with all three files together. Verified on two independent signals: HEAD blob = 172 lines / non-negotiable **×1** / inversion **×0**, and `git status --porcelain` on the three files is **empty**. The gate's own INV-1 and INV-2 controls **fire** on the broken state, so its rc=0 is a measurement, not a silence. See B3. |
| **D2′** *(replaces D2)* | The repair copies the **live** `~/.claude/AGENTS.md` wording into the deploy source rather than authoring new policy. Under AGENTS.md §9 the *content* of credential policy is still yours. **Confirm the restored §9/§9b wording is what you want shipped?** | **Yes — read it once and confirm.** | The urgency is gone (nothing is uncommitted, no `git clean` exposure). What remains is a one-time content confirmation of a security-relevant file an agent edited. Zero engineering. |
| **D3** | `skill-dual-write.yml` is `pull_request`-only, so SSOT's and SKILLS2' gates never run on a push to main (B2). Split the 6 push-safe steps into a workflow that fires on push? | **Yes, split them out** — do **not** just add `push:` to the existing file. | The D-001 dual-write job is genuinely diff-based (`--base origin/main --head HEAD`) and belongs on `pull_request`; the other six steps are absolute checks. ~~Also: PRs #281/#282 already touch this file, so this must be sequenced with them, not raced.~~ **That sequencing premise is REFUTED (§9 R3): measured file lists show #281 = 2× `ci-silent-pass-lint/SKILL.md`, #282 = 2× `codex-databricks-fanout/scripts/batch_runner.py`, #283 = `quality.yml` + `CIGREEN-R2-RETRACTIONS.md` — no open PR touches `skill-dual-write.yml` at all.** The real shared-workflow hazard is **#283 on `quality.yml`**, which this document never named. Sequence against **#283**, not #281/#282. |
| **D4** | Prompt Two condition 11 — `command-center/p2-next/OWNER-DECISION-condition-11.md`. | **Option B**, as that document recommends. | It gates **all 2,007 remaining units**. One decision, largest single unblock. *(FROM-RECORD — I did not re-derive the option set.)* |
| **D5** *(rationale rebuilt, §9 R2/R12)* | Merge PRs #281 / #282 / #283? | **Hold until D1 clears, then merge #282 first** — and either mark **#281 ready or close it**. | ~~All three are `mergeable: UNKNOWN` purely because CI is down. #281 fixes never-run gates.~~ **Both halves were wrong.** Re-polled twice: all three are **MERGEABLE** (#281 CLEAN, #282 CLEAN, #283 UNSTABLE) — the UNKNOWN was a cold-poll artifact, exactly what `docs/GRIND-STATUS.md` §3 **C1** already withdrew. And **#281 is a DRAFT** whose net diff vs main is **2 files, +1/-0 each**, both `ci-silent-pass-lint/SKILL.md`: the gate steps its title advertises **already exist on main** (`skill-dual-write.yml:87` `gate-skill-deploy-hop`, `:101` `gate-cs-wiring`). Sharp consequence for D3 — **those "never-run" gates were fixed *into the one workflow that never fires on a push*, so they still never run on the delivery path.** Holding for D1 is still right: merging CI changes while no runner can verify them is how main goes red invisibly. |
| **D6** | Retire the `chk` / `scratch` checkouts? | **No, not yet.** | `scratch` has 0 commits and thousands of untracked entries in no store anywhere. `git worktree remove` **follows junctions and deletes their targets**. |
| **D7** | 22 of 29 entries in `command-center/OWNER-DECISIONS.md` are still OPEN. | **Answer as one batch**, as that file itself instructs. | Piecemeal answers have already caused re-litigation. *(Re-measured: `\bOPEN\b` occurs **22** times in that file, agreeing with `docs/GRIND-STATUS.md` B3. My first probe was case-insensitive and said 24 — my detector error, corrected before use.)* |
| **D8** *(added by review, §9 R13)* | **A sensitive-artifact notice has no row anywhere in this document.** `classification=POTENTIAL-CREDENTIAL kind=transcript id=sha256:839ca3224e60`, tracked as **B5 in `docs/GRIND-STATUS.md` §2.1**, where the classification oscillates POTENTIAL-CREDENTIAL / UNKNOWN. **Decide the disposition of that transcript?** | **Treat as exposed and rotate**, per AGENTS.md §9b — *by the owner, not by any agent.* | The sweep was report-only and emitted no matched value; no agent action clears it and none was taken. **`UNKNOWN` means the scan did not finish, not that it is clean** — the adverse-inference default applies. It appears here because `docs/GRIND-STATUS.md` names *this* file as the owner-decision table, so an item with a row only there is invisible to anyone reading the table. **A question with no row is worse than an open one.** |

---

## 7. RANKED NEXT ACTIONS

> **RE-RANKED BY REVIEW (§9).** Item 2 is **DONE** (`22b33d8d`) and item 8's count has moved.
> Everything else stands. The live ordering is now **D1 → D3 → D4 → D8 → 5 → 6 → 7 → 8**, with
> **D2′** (confirm the shipped credential wording) as a zero-engineering read-once item.

1. **D1 — restore the runner.** Nothing below can be *verified* while B1 holds, only asserted.
2. ~~**D2 — repair the §9 credential inversion.**~~ **DONE at `22b33d8d`** — the three files landed
   together, HEAD now carries the non-negotiable and not the inversion, and `r4_credential_rule_gate`
   is rc=0 with both-states controls that fire. Residual is **D2′**: the owner confirms the *content*
   once, per AGENTS.md §9. What remains at this rank instead is **D8 — the
   `sha256:839ca3224e60` transcript**, which is now the only open item with a credential blast radius.
3. **D3 — give SSOT and SKILLS2 a gate on the delivery path, following the plan in
   `docs/harness/skill-dual-write-trigger-gap-2026-08-14.md`, not the one-line version.** Split the
   six state checks onto `push` + `pull_request`; keep the diff-based parity check
   `pull_request`-only (on a push base == head, and a gate that cannot fail is the defect, not the
   safety property); re-point the two `no_push_trigger` controls, then confirm the wiring checker
   does not flag the replacement. Coordinated multi-file CI change — **do it after D1**, because
   shipping unverifiable CI wiring while the runner is dead is how main goes red invisibly.
4. **D4 — decide condition 11.** Unblocks 2,007 units; pure decision, zero engineering.
5. **Wire `ssot_drift_gate.py` into a push-triggered workflow**, or adopt RULERESEARCH's pinned-entry
   pattern (CL5). It is currently invoked by nothing.
6. **Triage the 21 `hook_predeploy_gate` HAZARDs** (B4) — repo-vs-live deploy drift that CI
   structurally cannot see, so it will only ever be caught by someone choosing to run it.
7. **Re-run the SSOT retire-candidate predicate against `origin/main`** (O4) before retiring
   anything; 4 of 43 currently fail the lane's own stated criterion.
8. **Sweep the remaining 308 untracked working-tree files** once lanes are confirmed idle. Lowest
   priority — measured as probe scratch, and the 6 real deliverables are now committed.
   *(Re-measured at `22b33d8d`: **311 untracked**, 24 modified. Drift; ranking unchanged.)*

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
   it) and to `_r6_transcript.py --committed`. **↑ Half right, and the missing half is why O11's
   regression only appeared on the NEXT run — §9 R15.** The gate takes its *target* set from
   `git ls-files` (index), so staging a **target** does help; but it reads every *citing document*
   from `git cat-file -p HEAD:<path>` (`check_published_commands.py:197`, consumed at `:221`). So an
   edit to a **document** is invisible to this gate until it is **committed**, whatever you stage.
   Both re-run **green** with all 6 staged —
   428 published commands across 366 documents, 0 NEW unrunnable. Had either gone red I would have
   unstaged and reported instead.
3. **Cross-linked the two GRIND-STATUS documents** (CL2), additively in both directions. The prior
   `docs/GRIND-STATUS.md` is left otherwise untouched — its §3 corrections are frozen evidence.
4. **Re-executed all 22 lane gates** and published the raw results as
   `command-center/GRIND-GATE-RESULTS.json`, so the next pass inherits a receipt instead of a claim.
5. **Caught and fixed a regression I caused, on the next gate run** (O11). Committing
   `P2NEXT-GROUNDING-R2.md` landed a document publishing `python
   command-center/p2-next/_g2_independent.py` against an **untracked** target, taking
   `gate-published-commands` from 0 NEW unrunnable to 1 NEW. Fixed in `5e31a03c` by tracking the
   target — it exists (7,488 B), is real rerunnable evidence, and is clean under `ruff format`,
   `ruff check` and `py_compile`. Gate back to **0 NEW unrunnable** (435 commands / 367 documents).
   The lesson is in §4 O11: my pre-commit both-states test covered the 6 files I was cautious about
   and not the commit as a whole, and no test can see a *transitive* target until the document lands.
6. **Diagnosed a live cross-agent collision without touching it** (B7/CL7): the orchestrator's uncommitted
   push-trigger edit to `skill-dual-write.yml` currently red-fails `rule-audit` by destroying the
   fixture of another lane's control. Named the one-line remedy and three verified replacement
   fixtures instead of editing a shared workflow another agent is mid-write in.
7. **Recorded ~~four~~ six of my own overclaims** (O7, O8, O9, O11, **O12, O13**) in §4 beside the
   lanes', rather than silently correcting them. *(The "four" was written before O12 and O13 were
   appended and never re-derived — §9 R5.)*

What I deliberately did **not** do: edit `.github/workflows/skill-dual-write.yml` (~~open PRs #281
and #282 both touch it~~ — **that reason is REFUTED, §9 R3: neither PR touches that file; the sound
reason is that another agent was mid-write in it, which is B7**, and a shared file is the single
hazard that red-blocked every PR on main), retire or delete any checkout, touch
`agent-self/config/AGENTS.md` (owner-only credential policy), or run any `git worktree` subcommand.

---

## 9. REVIEW — an independent pass over this document

Written by the **synthesis-review** lane at `22b33d8d`. I did not read this document and agree with
it; I **re-executed** it. Every row below names the probe that settled it.

**The receipts are the probes, and they are committed** — CL3's own lesson, applied to this review:
a JSON snapshot in an untracked working tree is one `git clean` from gone, so what ships is the
re-runnable measurement, not its output.

```
python command-center/_synthrev2_gates.py     # 22 gates + a 23rd probe, behind a 3-state control
python command-center/_synthrev2_checks.py    # shas, paths, §9 credential state, B2 trigger, ledger arithmetic
python command-center/_synthrev2_claims.py    # workflow triggers, B4/B6 counts, PR file lists, SLOP counts
python command-center/_synthrev2_docs.py      # DOCS-lane recency in 3 scopes, owner-decision count, B-id collision
python command-center/_synthrev2_fixtable.py  # the R6 table repair; idempotent, asserts on read-back
```

Each derives its repo root from `__file__` and contains **zero** hardcoded estate paths (`grep -c
'C:/Users'` → 0 across all five) — a Windows absolute path frozen into a blob is one of the five
local-green/CI-red mechanisms CL6 lists, and a review that reproduced it while auditing for it would
be worthless. Their `*.out.json` outputs sit beside them as **untracked working-tree scratch** and
are deliberately not committed: two of the gate tails contain an absolute `~/.claude` path, which is
the disclosure class this repo's own ADV-0041 tracks. The numbers quoted below are the durable form.

COVERAGE: measured = all 22 gates re-run, every cited sha and path resolved, the §9 credential state
at HEAD vs worktree, the `skill-dual-write` trigger in both trees, PR mergeability (two polls) and PR
file lists, DOCS-lane recency in three independent scopes, the owner-decision count, published-command
counts, the worktree census, and the cross-link. **Not measured:** the 909-test local suite behind CL9
(inherited FROM-RECORD), anything CI-side (B1 still holds), and the interior of the eight
reconstructed lanes. *If this section ever reads as unmeasured placeholders, the unit died before
measuring anything and no verdict here may be cited.*

### Refuted — the sentence was wider than its evidence

| # | claim as written | probe that settled it | corrected |
|---|---|---|---|
| **R1** | B3 / D2 / §7 rank 2: *"a fix is IN FLIGHT and UNCOMMITTED… one `git clean` re-arms an inverted §9"* | AND-gate, two mechanically independent signals: `git show HEAD:agent-self/config/AGENTS.md` → **172 lines, non-negotiable ×1, inversion ×0**; `git status --porcelain` on all three files → **empty**. Gate rc=0 with **INV-1 and INV-2 controls that fire on the broken state** and a live arm reporting RAN. | **CLOSED at `22b33d8d`.** B3, D2→D2′, §7 rank 2. `almost certain (90-99%)` |
| **R2** | B5: *"All three `mergeable: UNKNOWN` … none confirmed mergeable"*, and D5's rationale on it | Two polls seconds apart — cold: UNKNOWN ×3; second: **#281 MERGEABLE/CLEAN, #282 MERGEABLE/CLEAN, #283 MERGEABLE/UNSTABLE**. The instrument changed answer while the world did not, which is the both-states control. | **All three are MERGEABLE.** And **the withdrawal was already on disk**: `docs/GRIND-STATUS.md` §3 **C1** retracts this exact inference, in a section this document's own header calls *"frozen evidence"*. **The dropped refutation is C1** — a recall failure, not a detection failure. `almost certain (90-99%)` |
| **R3** | D3 and §8: *"open PRs #281 and #282 both touch [`skill-dual-write.yml`]"* | `gh api …/pulls/{n}/files`: #281 → 2× `ci-silent-pass-lint/SKILL.md`; #282 → 2× `codex-databricks-fanout/scripts/batch_runner.py`; #283 → `quality.yml` + `CIGREEN-R2-RETRACTIONS.md`. | **No open PR touches that file.** The *abstention* was correct (B7 — another agent was mid-write); the *reason given* was false, twice. The real shared-workflow hazard is **#283 on `quality.yml`**. `almost certain (90-99%)` |
| **R4** | §3: *"DOCS — died, on an AND-gate of two mechanically independent signals"* | Arm 1: `docs/_LANE-DOCS*` → **14 commits/36 h, newest non-synthesis `f6a1f91b` 3.3 h ago** (2.5 h *before* this document measured); 14 subject-tagged `lane-docs`/`docs-lane`; `docs/GRIND-STATUS.md` §1 counts **16**. Arm 2 scanned only the **untracked** subset — a set a committing lane empties by definition, so it reads "idle" under both hypotheses; over all 12 lane docs, `-BUILD-R5…R8` are **4.5–5.2 h** and `-INTEGRATE-R2` **3.4 h**. | **Verdict withdrawn.** DOCS is the slowest-committing lane and left its tail **untracked**, which is CL3. Whether its process still runs is **UNVERIFIED from this disk** — the settling experiment is the live agent roster. `almost certain (90-99%)` that the two named arms do not reproduce. |

### Self-contradictions and structure

| # | finding | measured |
|---|---|---|
| **R5** | §4 states the ledger **three incompatible ways** — `10 : 3` with *3 of the 10 mine*, `13 : 4` with *5 of the 13 mine*, and §8.7 *"four … (O7, O8, O9, O11)"*. | Counted off the table rows: **13 rows, 6 marked `*mine*`**. A self-contradicting output is a **detector failure, not a finding**. Fixed in §4 and §8.7. |
| **R6** | The **O12 and O13 rows sat outside the table** — a blank line severed them, so in any renderer they showed as literal pipe text, and they ran backwards. | Two of the six self-caught overclaims were effectively invisible. Repaired (`command-center/_synthrev2_fixtable.py`, idempotent, with a read-back assertion). |
| **R7** | §2 runs **B1, B2, B7, B3, B4, B5, B6** and §5 ends on **CL6** after CL9 — and §1 forward-references CL6. | Not reordered (the prose is frozen evidence of when each was written); a read-by-label warning is now in the header. |
| **R8** | B2's *"LIVE UPDATE"* says the working copy of `skill-dual-write.yml` *"is dirty (` M`) and already carries `push:`"* — while **B7, six lines below, says it was reverted.** Both were on the page at once. | Measured: file **clean**, and **no `push:` in the HEAD blob or the worktree**. Control so the parse is not the silent thing: `quality.yml` reads push **True**. **B2 itself is unchanged and still live; nothing is closing it in any tree.** |

### Drift — restamped at `22b33d8d`, not deleted

| # | as written | re-measured |
|---|---|---|
| **R9** | §1 SSOT *"6/6 wires, 16 passed"* | `SUCCESS:ssot-wiring-check wires=7 all intact` · `21 passed`. (**16 passed** is `test_deploy_skills_daily`'s count — a transposed row.) |
| **R10** | 247 commits/36 h · 337 dirty (314/23) · SLOP 428/366 in §1 **and** 435/367 in §8.5 | 259 · 335 (311/24) · **437/369, 0 NEW, 1 inherited**. Two different "current" SLOP figures were in one document. |
| **R11** | §3 *"7 untracked `_LANE-DOCS-*.md`"* | **4** — §8 committed three of them. Self-caused drift, worth the stamp because §3 leans on the count. |
| **R12** | D5 *"#281 fixes never-run gates"* | **#281 is a DRAFT** and its net diff vs main is 2 files, **+1/-0 each**, both `SKILL.md`. The gate steps already exist on main at `skill-dual-write.yml:87` and `:101` — **inside the workflow B2 proves never fires on push.** |

### Gaps a reader would fall into

| # | gap | closed by |
|---|---|---|
| **R13** | The `sha256:839ca3224e60` **POTENTIAL-CREDENTIAL transcript has no row in this document**, although `docs/GRIND-STATUS.md` names *this* file as the owner-decision table. | Added as **D8**. It is not a new finding — it is `docs/GRIND-STATUS.md` §2.1 B5 — but an item with a row in only one of two documents is an item a reader loses. |
| **R14** | **Cross-document ID collision.** This file numbers `B1…B7`; `docs/GRIND-STATUS.md` numbers `B1…B5` — with **different referents** (there: B2 = condition 11, B4 = the 3 PRs, B5 = the credential transcript; here: B2 = the trigger gap, B5 = the 3 PRs). | Flagged, not renumbered — renumbering either file would break every existing citation. **Cite as `<file> B<n>`, never a bare `B<n>`.** |

### R15 — my own inert control, caught by running it against the broken state

I staged this review's edits, ran `check_published_commands.py`, saw `rc=0`, and was one sentence
away from citing that as the pre-commit both-states test §8.2 demands. **It proves nothing.** I ran
the control anyway — break one published receipt path to a file that does not exist, re-run, restore
byte-for-byte — and the gate stayed **rc=0 and green in the broken state too**:

```
clean  state: rc=0  SUCCESS:published-cmds no NEW unrunnable published command
BROKEN state: rc=0  SUCCESS:published-cmds no NEW unrunnable published command
restored byte-identical: True (sha256 c4310f9f79c9…)
```

**A probe silent in both states measures nothing.** The mechanism, read directly rather than
inferred: `check_published_commands.py:195-203` fetches each citing document with
`git cat-file -p HEAD:<path>` and `:221` scans *that* — while `:256` takes the tracked-**target**
set from `git ls-files`. **Two different read-bases in one gate.** Staging a *target* is visible;
editing a *document* is not, until it is committed. That is the exact shape of O11 — the regression
could not appear until `P2NEXT-GROUNDING-R2.md` **landed** — and §8.2's explanation named only the
`git ls-files` half, so it under-described the trap it was documenting.

Consequence, applied to this commit rather than asserted: **no pre-commit run can verify a document
edit here.** The honest sequence is commit → re-run → fix-forward, which is what `5e31a03c` had to
do. I committed, re-ran, and record the post-commit result beside this line rather than a
pre-commit green that was never evidence. Control script: `python command-center/_synthrev2_bothstates.py`
(restores the document and asserts the restore by sha256).

**POST-COMMIT RE-RUN — see the commit's own message for the verdict.** *(If this sentence is ever
the last word here, the re-run did not happen and this section's green may not be cited.)*

### Confirmed — re-executed and identical

- **The gate table holds.** 22 gates re-run plus a 23rd probe, behind a three-state control that
  produced three distinct states all matching expectation: **21 PASS / 2 FAIL**, with exactly one row
  moved (`r4_credential_rule_gate`, explained by R1). Every other row reproduced.
- **B4 verbatim:** `FAILED:hook-predeploy-gate 21 HAZARD(s) of 74 findings`, and both named samples
  reproduce exactly — `PreToolUse` repo 12 / live 13 with live-only `workflow-monitor-autolaunch/check.py`;
  `UserPromptSubmit` repo `open-loops/trigger_match.py` vs live `semantic-router/route.py`.
- **The "fires on push→main" column is exact** for all 12 workflows, including both ⚠ rows.
- **43/43 citation cases** (`RESULT: ALL PASS (43 cases, 0 failed)`), **all 3 cited shas resolve**,
  and **all 6 orphans plus `_g2_independent.py` are in HEAD** — the last at **7,488 B**, the figure
  §8.5 states. Both GRIND-STATUS documents cross-link, both are tracked and clean.
- **D4 and D7 hold:** `OWNER-DECISION-condition-11.md` does mark **Option B** `<-- RECOMMENDED`, and
  `\bOPEN\b` occurs **22** times in `OWNER-DECISIONS.md`.

### What this review's own numbers are

**4 refutations, 4 structural/arithmetic defects, 4 drift restamps, 2 gaps, 1 inert control of my
own (R15) — against 8 confirmations, and 0 SHIPPED items that were not actually shipped.** Every §8
deliverable is in HEAD and clean.
Consistent with the estate's base rate, **the failures were overclaims and stale sentences, not broken
work** — the gates were real, the receipts were real, and the corrections are almost all to prose that
outran its evidence. The one exception worth carrying: **R2 is a recall failure, not a measurement
failure.** The retraction that would have prevented it was written hours earlier, in the companion
document this one calls authoritative, and was never read. That is this estate's dominant error mode
reproduced inside the pass that was auditing for it.
