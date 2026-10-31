---
title: OWNER-PACKET-2026-08-11
type: note
permalink: dqverify-repo-20261013/command-center/owner-packet-2026-08-11
---

# OWNER PACKET — what actually needs your call, 2026-08-11 03:30

Current as of `1bdb1189`. Supersedes the owner sections of `FOUR-PROGRAM-DECISION-QUEUE.md`, which
was written at 23:14 before any close was applied and still says "7 applied, 11 pending".

**State:** register 26 → **36 DONE-VERIFIED**, 59 open, validator clean (`items=103 open=59
reachable=all`), CI green on main. Ten closes applied, each anchor re-measured by me rather than
taken from a lane digest — the verifier blocked 4 of the first 7 attempts, so that step earned itself.

**The one framing fact.** Five of the ten closed because the deliverable had **shipped under
`platform/`** while the register's anchor still named a pre-`platform/` path. Nothing was built to
close them.

> **CORRECTION, measured after this packet was first committed.** I wrote here that "if that ratio
> holds across the 59 still open, a meaningful fraction may already be done". **It does not hold.**
> `command-center/namespace_sweep.py` indexed 4,978 tracked basenames against all **51** items whose
> status is literally `OPEN` (the 59 figure includes IN-FLIGHT / DONE-CLAIMED / UNKNOWN) and found
> **zero** naming an artifact that exists under `platform/`. Thirteen items name a file that exists
> elsewhere, but on inspection: most are MONITOR rows whose file exists in three copies
> (`.agents/skills/`, `skills/`, `tools/monitorcore/`) — the already-understood repo/live
> triplication, not a namespace miss — and `R-A21`/`R-A22` match `PROMPT-ONE-REVERIFY.md` only
> because I wrote that filename into their evidence field tonight, which is use-vs-mention against
> my own prose.
>
> **Scope of the refutation:** it kills the "same filename, different directory" hypothesis. It does
> NOT prove the 51 are all genuinely undone — an item whose deliverable shipped under a *different
> name* is invisible to a basename sweep, and R-A06/R-A09/R-A12 were exactly that shape (the anchor
> named a concept, not the delivered filename). Settling that needs semantic review per item, not a
> set-membership check. Plan against 51 open, not against a discount.
>
> **SECOND INDEPENDENT AXIS, measured 2026-08-11 05:40 — also negative.** Every one of the 51 open
> items declares an `output_path`, and **0 of 51 exist on disk** (`os.path.exists` per item; control:
> a known-present path returns True, a bogus one False). So the two cheap mechanical tests for
> "already delivered but invisible" both come back empty:
>
> | axis | result |
> |---|---|
> | declared `output_path` exists | **0 / 51** |
> | named artifact exists under `platform/` | **0 / 51** |
>
> What survives is only the CONCEPTUALLY-RENAMED case — the item's anchor names an idea, and the
> deliverable shipped under an unrelated filename. That is exactly how R-A06 ("a single self-listing
> manifest" → `platform/marketplace/mkt/`) and R-A09 ("skills/council" → `platform/lib/councilspec/`)
> closed, so the class is real and demonstrably not rare. It is also **not mechanically detectable**
> — no path or name comparison can find it. Settling it needs a human or an LLM reading each item's
> intent against the tree, one item at a time. Until someone does that, **51 open is the honest
> number** and any discount applied to it is a guess.

---

## 1. HIGHEST LEVERAGE — three decisions that unblock most of the program

### O-1 · OQ-1 + OQ-2 → unblocks R-A03 and its 8 remaining dependents
Which Prompt Two option IDs are selected, and what is the priority ordering. The
`[PASTE SELECTED OPTION IDS HERE]` placeholder is still literal.
**Recommendation:** accept `07-OPTION-UNIVERSE.json`'s existing `owner_decisions: 70` as the OQ-1
answer unless you disagree with specific cards; that turns a blank into a reviewable diff.
**Note:** three of R-A03's original 11 dependents shipped *without* the gate and are now closed, so
the edge is already known-counterfactual. The remaining 8 edges are deliberately left intact — I
retired only the three where the gated work was verified complete. Retiring the other 8 is your call.

### O-2 · `REL-0003` → the ONLY entry point to all 43 Phase-15/16 units
Exactly **1 of 43** units is startable and it is this one: an owner ruling on what substitutes for
the canary that PR-ONLY does not have (spec `:11125`, promotion gate `:11131`). OQ-3 fixed the
release *mode*, not the *pass condition*.
**It has no row in `OWNER-DECISIONS.md` at all** — the largest gate in the program is unrecorded.
**Recommendation:** add the row, then rule. Everything else in P15/P16 is transitively behind it.

### O-3 · What does a `B\d+` dependency MEAN? → 876 edges and 17 of the 43 P15/P16 units
`bucket` is undefined in the catalog's `contract`, `defaults` and `tool_policy`, and appears twice in
the 29,273-line spec — neither time as a definition (control: `phase` appears 172 times). Ten of
thirteen bucket tokens have **zero members**; B07 alone carries 297 inbound edges.
Three readings are possible: *all members done* · *any member done* · *a bucket-level gate artifact
exists*. Under the first, 876 edges are permanently unsatisfiable.
**Recommendation:** the cheapest coherent answer is "a bucket-level gate artifact exists", which
makes them satisfiable without inventing membership for 1,735 unbucketed units.
**Do not** let anyone "repair the tokens" first — lane C1 recommended that, and it is not actionable
until this is answered. Gated now by `tools/measure-guard/wudeps.py`, which ratchets the counts.

---

## 2. SEVEN CLOSES I DELIBERATELY DID NOT APPLY

Each self-scores `likely (55-80%)` in its own lane, or turns on a reading rather than on evidence.
A `likely` is a bet, not a verdict, and I applied only `almost-certain` rows.

| id | why it is yours | the actual question |
|---|---|---|
| **R-A08** | lane A1 says outright the disposition "turns on how EXECUTABLE is read" | 97 blueprints validate and dry-run, but `platform/lib/wfdsl/` is a **validator** and no engine has ever run one. Does "executable" mean authored-and-validated, or an-engine-has-run-it? Also in definitional conflict with scorecard condition 17 |
| **R-A04** | in-repo remediation surface measured **zero** (all 19 hits are use-vs-mention), but the untracked `variant4-pre-prompt2/` tree was never enumerated | close on the in-repo evidence, or enumerate that tree first? |
| **R-A14, R-A15** | lane A2 rates both `likely` | R-A15 also carries a `dependencies: [R-A03]` edge, so closing it before O-1 adds a REACH-1 violation |
| **R-A25, R-A26, R-A27** | lane A3 rates all three `likely`; R-A27 weakest at 55-70% | R-A27's conversational half is **structurally unobservable from disk** and can never close on disk evidence — leaving it OPEN forever is a register defect, not a work item |
| **R-B04** | its own lane defers to you | the Q22 gate premise is measurably false, but the row stays gated until you retire Q22 as moot |

---

## 3. THE REST OF THE OWNER QUEUE, ranked honestly

**Only 7 of the 25 open questions gate a register item. Eighteen gate nothing** — they are open
questions that block no work, and treating all 25 as a backlog overstates what is actually stuck.

| gates work | question | blocks |
|---|---|---|
| yes | OQ-1, OQ-2 | R-A03 (+8 dependents) |
| yes | OQ-5 | R-A05 — no longer *blocked*, its dependency R-A04 resolved; simply unanswered |
| yes | OQ-7 | R-B07 — Program B B3/B4/B5 renumbering; prompt wins by authority order, just needs confirming |
| yes | OQ-8 | R-M18 — enrol the monitor cockpit into the unified contract, at what priority |
| yes | Q19 | R-H10 — `owner-ops-authorization.md` is live-only on no git ref |
| yes | OQ-6 | R-B08 — credentials. **You told me to stop spending attention here; parked, not forgotten** |
| **no** | Q3, Q6, Q9–Q18, Q20–Q25 (18 of them) | nothing |

---

## 4. READY TO RUN, no decision needed

1. **Retire the 8 remaining counterfactual `R-A03` edges** — but only after O-1, since your answer
   may make the gate real again for some of them.
2. ~~Sweep the 59 open items for the `platform/` path-namespace miss.~~ **DONE, and it came back
   negative** — see the correction above. `namespace_sweep.py` is committed and re-runnable; the
   remaining question it cannot answer is the *renamed-deliverable* case, which needs per-item
   semantic review rather than a basename check.
3. **`10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json`** is the only genuinely missing R-A22
   artifact. Its two siblings exist at 344,197 B and 161,920 B — the old action line said to write
   the 344 KB one first.
4. **Prompt 1.5 residual R5** — the repaired msys hook was never run against the live registered
   rail. A fix validated somewhere other than where it runs.
5. **The flaky harness test** — `test_every_registered_provider_event_has_valid_native_wire_output`,
   2 of 6 full-suite runs, 5/5 isolated, both failures on the slowest runs. Pre-existing, CI-safe,
   documented on the test itself. Root cause unrecorded because two capture attempts both passed.

---

## 4b. LIVE DEFECT ON THIS MACHINE — a stale deployed hook is silently dropping Bash options

**Found while verifying Prompt 1.5's residual R5. This is the most immediately actionable item in
the packet, and it is affecting every session on this box right now.**

`~/.claude/hooks/cmd-rewrite/inject-nopager.py` is a `PreToolUse` rewriter registered in live
`settings.json`. The deployed copy is **stale**, and the version it is stuck on carries a real bug:

```python
live (stale):  payload["updatedInput"] = {"command": rewritten}
repo (fixed):  payload["updatedInput"] = {**tool_input, "command": rewritten}
```

`updatedInput` **replaces** the whole `tool_input` object. The stale line therefore discards every
field it does not restate — the repo's own comment names them: *"a requested background call with a
600000 ms timeout became a foreground call at the default timeout"*. So on this machine, any Bash
call this hook rewrites silently loses `description`, `timeout` and `run_in_background`.

**Five independent signals, not one:**

| # | signal |
|---|---|
| 1 | LF-normalised sha of the caller: repo `1b067a25a9b3` vs live `77fb44633741` |
| 2 | the diff is 8 lines and contains exactly the buggy assignment |
| 3 | the repo's comment documents the precise symptom, so this was a known, fixed defect |
| 4 | `hooks/cmd-rewrite/test_updated_input_preservation.py` — 9 tests for this exact behaviour, green in repo, and CI runs them |
| 5 | the harness's OWN `install.py --check` independently reports `drift` on `hooks.claude` and `hooks.codex` |

**The fix already exists and is tested — it simply has not been deployed.** `msys_pathconv.py`
itself is byte-identical repo-to-live (`50740f9c4369`), so only the caller drifted.

**Why I did not deploy it.** Repo → live is the correct direction (`harness-vcs-hygiene.md`), but the
deployment tooling is outside what I run unattended, and a hand-copy into the live hook tree is how
harnesses break at 4am. Evidence is above; the deploy is yours.

**Incidental result: Prompt 1.5's R5 is now partly discharged.** R5 read *"the repaired msys hook was
never run against the live registered rail."* It ran tonight — it fired on one of my own commands
with `[msys-pathconv] ENFORCED … FIX APPLIED`, correctly excluded a `/c/Users/...` argument, and the
command then succeeded. That is the first observed live execution. The **module** is verified live
and correct; the **caller** is not, which is the newly-found half above.

**Correction to my own method here, recorded because it nearly became a false report.** I first ran
`python -m pytest hooks/cmd-rewrite/test_msys_pathconv.py` and reported "1 error —
`test_real_git_end_to_end`, fixture `repo` not found". That was my wrong invocation, not a defect:
the file is a standalone script with its own `main()`, CI runs `python test_msys_pathconv.py`, and
that way it reports **174 passed, 0 failed, 0 skipped**. Exactly the trap
`single-signal-verification.md` already documents about running a standalone script under pytest.

---

## 4c. 735 KB OF WORK EXISTS IN NO VERSION-CONTROLLED LOCATION

Two no-remote repos under `source/_advver_M14/` — `chk` (1 commit) and `scratch` (**zero commits**,
40 uncommitted). Both are working copies of the toolchain, so the hygiene hook's "this work exists
nowhere else" needed testing rather than believing. Measured by content, LF-normalised, against every
tracked blob in `ast-integrate` (`command-center/triage_noremote.py`, controls pass):

| repo | files | VARIANT (path in repo, content differs) | **ORPHAN (no such path anywhere)** |
|---|---|---|---|
| `chk` | 7,770 | 350 | **77** |
| `scratch` | 7,772 | 348 | **77** |

The 350 variants are diverged copies of tracked files — low risk. The **77 orphans, 735,139 bytes**,
are whole subsystems that exist only here:

| files | area |
|---|---|
| 46 | `tools/web/agentify-desktop` |
| 17 | `tools/mcp/codex-orchestrator` (package.json, src/, integrations/codex/, manager/, orchestrator/) |
| 7 | `tools/web/promptbridge-talk-lane` |
| 3 | `tools/mcp/agent-lanes-codex` |
| 2 | `tools/web/agent-lanes-chatgpt-web` |
| 2 | root `mcp-server.mjs`, `docs/incubating/tools/agentify-web-chatgpt-bridge.md` |

`chk` at least has them in local git. **`scratch` has zero commits**, so its copies are working-tree
files only — deleting that directory destroys them with no recovery.

**Per your standing decision I triaged and stopped: no remote created, nothing pushed, nothing
deleted.** The decision is whether these subsystems are live work worth a remote, or abandoned
experiments worth deleting. I have not read them for intent — only measured their uniqueness.

**Method correction, disclosed:** my first working run reported "427 unique files". That was an
overclaim — it counted modified copies of tracked files as unique. Splitting VARIANT from ORPHAN
took the real at-risk number from 427 to 77.

---

## 5. THINGS THAT ARE BROKEN AND ARE NOT MINE TO FIX

- **`autofix-models` has never worked.** It triggers on `workflow_run` completion of `quality` and
  only acts when quality FAILS, so every prior run reads "skipped". Its first real invocation was
  tonight and it died at step one: `Copilot CLI not found`. Needs a CLI install and a
  `COPILOT_GITHUB_TOKEN` — a credential decision, so yours.
- **3 high-severity Dependabot alerts** on the default branch, surfaced by GitHub on every push.
  Not touched; dependency bumps are a decision, not a chore.
- **`hooks/worktree-debug.json`** — the harness itself classifies it as an "orphaned worktree
  marker" (`agent-self/harness/modules.py:3124`). I stripped its BOM so it parses; whether it should
  exist at all is yours.