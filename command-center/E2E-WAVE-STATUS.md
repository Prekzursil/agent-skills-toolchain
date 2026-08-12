# E2E WAVE STATUS — one authoritative account of the six-lane program

Written by the SYNTHESIS lane, 2026-08-12, against **HEAD `39f30ab2`**.
Every claim carries the command that produced it, or names the file it was read from, or is
labelled inherited. Forward-looking claims carry a Sherman-Kent band.

**COVERAGE.** Sections 1-8 are all MEASURED. Two things are NOT, and are stated rather than
folded into a pass: (a) no GitHub Actions run has executed any of this wave's gates, and
(b) I did not re-derive every per-lane number — where I cite a lane's own measurement I say so,
and where I re-ran it myself I say that instead.

**PROVENANCE CAVEAT, load-bearing.** The orchestrator handed me the lane-results payload
**truncated**: it contained lane CS only, and CS's round-2 refutation was cut off mid-sentence.
I did not fill that gap by inference. I reconstructed the other five lanes from their terminal
on-disk dossiers and from `git log`, and then re-executed each lane's headline gate myself.
Consequence to hold onto: **if a lane produced a finding that never reached disk, it is not in
this document.** The write-as-you-go mandate is the only reason that gap is small.

**The six lanes.** CS (claude-science) · SKILLS (skills fleet / deploy hop) · MON (monitor
cockpit) · P2 (Prompt-Two delivery predicate) · CASUALTY (recovered dead agents) ·
WFSOTA (workflow SOTA / H6 timeout).

---

## 1. SHIPPED — what exists and works that did not before

Only items that survived the refute stage. Anchors are commit shas and re-runnable commands.

### The cross-lane check no lane could run: all six gates pass **together at HEAD**

Each lane verified itself at its own commit; HEAD has moved 10-30 commits since. Nobody had
re-run them as a set. I did, sequentially, at `39f30ab2`:

```
CS        python scripts/claude-science/cs_wiring_check.py     SUCCESS:cs-wiring 10 invariants intact      exit 0
CASUALTY  python command-center/casualty/casualty_guard.py     SUCCESS:casualty-guard 6 probe(s) green     exit 0
MON       python tools/measure-guard/launchpath.py             SUCCESS:launchpath 2 launch(es), 5 exempt   exit 0
P2        python tools/measure-guard/unitgate.py               SUCCESS:unitgate 2007 units / 53 artifacts  exit 0
WFSOTA    cd tools/wf-timeout && python wf_gate.py             SUCCESS:wf-gate 0 error(s), 1 warning(s)    exit 0
SKILLS    pytest ci/tests/test_deploy_skills_daily.py -q       16 passed in 1.32s                          exit 0
```

**And main's FIRST gate is clean as CI will see it.** `ruff check .` over the whole repo returns
9 findings, **all 9 on untracked scratch a fresh checkout never contains, 0 on tracked files** —
so the matcher fires and the zero is a reading, not a blind spot. For the 21 tracked `.py` files
that landed *after* the last ruff sweep (`4573b603`), I re-checked at **blob level**
(`git cat-file -p`, never `git archive`), with `ruff.toml` alongside and a deliberately
mis-formatted control: `SUCCESS:synth-blobruff 21 committed blobs are CI-clean; control fired`,
0 CRLF. `bash .quality/charter_check.sh` → `OK -- 7 gates consistent`.

### Per lane

| lane | what now exists that did not | anchor |
|---|---|---|
| **CS** | `/claude-science` + `/cs` both resolve **and execute the fixed tool** (they ran a detached-HEAD checkout until round 2). `cs doctor` has a 4th state NOT-CHECKED and exits non-zero on it, closing four fail-open rows (DB timeout mis-reported as "not found", backup PASS over an unreachable VM, a daemon row that silently vanished, a disk row that printed a fabricated `0GB`). Backup **restorability** is proven by opening a temp copy, not by `ls`. The always-on watchdog no longer launches out of a disposable git worktree. Fault injection is armed + banner-marked so the doctor can never be ordered to print an unmarked green. `cs_wiring_check.py` — 10 repo-only invariants — is a **CI gate**, red-proofed with 14 single-wire mutations + a healthy control. | `ebf415f5`, `3545a700`, `d14cea8f`, `39f30ab2` |
| **SKILLS** | The last deploy hop into `~/.claude/skills.daily` (the only tree Claude Code reads) is now **wired into CI twice** and reachable by an agent (`writing-skills/SKILL.md`, +2,823 chars of body, description delta **+0**). 16 hermetic tests; the new suite killed 3/3 mutants where the tool's own `--self-test` left 2 alive. `ui-audit`'s silent-no-op fix reconciled live→repo before anything could deploy over it. | `e9b65d60`, `3678417c` |
| **MON** | `launchpath.py` — the first thing in this repository that **executes** a registered monitor instead of checking its bytes — materialising from committed blobs, both registry mirrors, every stanza accounted for by name, fail-closed six ways. 4-leg both-states control (incl. an inverted control). Verified on **Linux as well as Windows**, and from a **real LF clone**. Cockpit health pane adopted as the 6th pane. | `b9a77ad7`, `0ae5b2a6`, `cdac3f26` |
| **P2** | `ready_units.py` — the delivery predicate that stands between a fabricated artifact and a `delivered` count — is now a CI gate (`gate-p2-delivery`) with a **self-defending seam** that runs in a different step, so deleting the gate still turns something red. A live fail-open was found and fixed *before* wiring: with the contract checker dark, 367 declarations unchecked and 2,007 units ungated, the tool still printed `SUCCESS`. 4-mutation red-proof with attribution checked. | `70f70f74`, `eac025c6`, `a9b7dde5` |
| **CASUALTY** | Two dead agents' work recovered as receipts that reproduce their published digest and byte count; `casualty_guard.py` (6 probes) + `integration_redproof.py` (4 controls) wired into CI plus a second independent `suitefloor --suite casualty` line. Four instruments that hardcoded this box's repo root now derive it from `__file__`, so they run in a clone — verified by an actual clone: `SUCCESS:int-freshclone`. | `f087a6f6`, `5e3c2271`, `bc411d87` |
| **WFSOTA** | H6 per-agent timeout + settled barrier, and the CI step **is** the H6 red-proof (its control feeds `parallel()` a thunk that never resolves and requires the barrier to hang). `workflow_lint` — 110 tests, 100% coverage, and **never run over a line of workflow code** — now runs over the real template corpus on every PR. Non-circular pin: the wiring assertion lives in a *different* workflow's directory sweep, so deleting the step turns that other workflow red. Coverage taken 99%→100% with a real test instead of a permanent exception. | `1f05e805`, `b3412595`, `5c4111fc` |

---

## 2. STILL BROKEN — with the precise blocker

1. **No GitHub Actions run has executed ANY of this.** Five of six lanes disclose this in the
   same words. Five new/extended gates (`gate-p2-delivery`, `casualty`, `launchpath`,
   `wf-timeout`, `gate-skill-deploy-hop`, plus CS's `cs-wiring`) have runner evidence of exactly
   zero. Blocker: nobody has opened a PR. Band that they pass first try: **likely (55-80%)** —
   raised above a guess by three independent legs (a Linux interpreter run, real LF-clone runs,
   blob-level ruff parity), lowered below "almost certain" by the one thing none of them
   removes: CI pins Python **3.11** while every local leg measured 3.12.3 / 3.14.6.
2. **`~/.agents/skills` (the Codex vault) is an orphan tree with a live silent-no-op in it.**
   The `ui-audit` guard is fixed 6/6 in the repo and 6/6 in `skills.daily`, and **0/6 in the
   vault**. Blocker: no repo-side writer with guards targets that tree — `deploy-skills-daily.py`
   points at `skills.daily`, and `sync-skills.ps1` writes there from `skills/` with a `-Prune`
   mode that would **delete** `microsoft-foundry` and `qdx-rush`. Not vacuous today (nothing
   reparse-points into it); one deploy away from being reached.
3. **`workflow-authoring/SKILL.md` cannot be deployed safely and cannot be left alone.**
   Two-way diverged: 53 live-only vs 234 repo-only lines. `unsafe_to_deploy=2`. Blocker: the only
   reachability-improving deploy is the destructive one, because the diverged `SKILL.md` is what
   would have to reference the new H6 template. Needs a union-merge decision.
4. **103 register rows cannot emit a receipt at all.** `platform/schema/receipt.schema.json`
   `$defs.unit_id` is `^[A-Z][A-Z0-9]*-[0-9]{4}$`, which matches **2007/2007 work units and 0/103
   register rows** (my own re-derivation: `BLD-0023`→True, `ADV-0021`→True, `R-M18`→False).
   R-M18 is blocked on this, R-M06 depends on R-M18, so MONITOR stays gated. **Do not let anyone
   hand-write a SUCCESS receipt to clear it.**
5. **The cross-vendor review rail is DOWN, and it gates 43 blocked units.** `codex --version`
   works, `claude mcp list` says `codex … ✔ Connected`, and an actual `mcp__codex__codex` call
   **fails**: `agent identity registration failed for …auth.openai.com/api/accounts/v1/agent/register`.
   Three green signals, unusable rail. Separately, **449/449 READY units carry a
   `reviewer_requirement`**, so no unit can reach `state: SUCCESS` from a build lane at all.
6. **Four committed adversarial artifacts are rejected by their own declared contracts**
   (ADV-0007: 6 errors, ADV-0022: 12, ADV-0041: 1, ADV-0040: passes from the worktree, fails from
   the blob). Reported, **not gated**, because `command-center/adversarial/` is frozen while a
   sibling wave writes it. None is a live false green — all four are rejected today.
7. **Both recovered casualty receipts have zero reviewers** (`reviewer.verdict = NOT-REVIEWED`)
   and sit outside their canonical `output_path`, so a tool reading only the canonical path sees
   two 2 KB skeletons and will report two false casualties.
8. **Nothing in the 328-skill fleet was merged or retired**, and that is only backed by
   token-level evidence (57 candidate pairs, max Jaccard 0.185 vs a 0.30 floor). That refutes
   *textual* duplication; it cannot see two skills doing the same job in different words. The
   sixth (overlap) lens never got adversarial clearance. Confidence no pair is functionally
   redundant: **likely (55-80%)**, not higher.
9. **ADV-0040 exposes a blind spot in P2's own gate**: its worktree and blob verdicts differ in
   REASON but agree in BOOLEAN, and the divergence check compares the boolean, so it is masked.

---

## 3. LANES THAT DIED

**In this wave: none.** All six lanes produced terminal on-disk dossiers, and I re-executed all
six headline gates at HEAD (§1). No lane is a total loss.

That is worth stating plainly because **the previous attempt at this same wave was very nearly a
total loss**, and the record must not blur the two:

- `52a6d6ab` (08:17) — *"preserve interrupted lane output — 1.2 MB of real work, explicitly
  UNAUDITED"*. The six GROUND lanes completed; then the build/audit/refute agents were
  **interrupted**. **23 agents produced 240-480 KB transcripts each and journalled ZERO results.**
  The audit and refute stages never ran against any of it. It survived only because those agents
  wrote artifacts to disk as they went — the mandate that exists precisely because a 70-minute
  unit earlier in this program held its results in memory and wrote nothing.
- Two casualties inside the adversarial build wave (`fb2f477f`: 38 of 40 ADV units substantial,
  2 known casualties) were recovered by the CASUALTY lane as ADV-0021 / ADV-0022.
- The sixth audit lens (overlap) never completed and had to be recovered from disk (`4d421333`).

**One honest caveat about my own inputs:** five of six lanes were absent from the payload I was
handed. That is orchestrator payload truncation, **not** a lane death — I verified each of the
five has a complete terminal artifact on disk. Do not read a missing lane in a synthesis payload
as a dead lane again without checking disk first.

---

## 4. OVERCLAIMS CAUGHT

The most valuable section, unsoftened. **At least 21 distinct overclaims** were caught and
recorded across the six lanes against **at least 15 confirmed defects** — a ratio of roughly
**7:5**, close to the program's measured 5:3 base rate. In almost every case the code was right
and the SENTENCE was wider than its evidence.

### The program's own ground floor carried one
- **"`git archive` AND `git show <rev>:<path>` both return CRLF worktree bytes."** The
  `git show` half is **FALSE** and was measured false (24,400 B, zero CRLF, byte-identical to
  `git cat-file -p`). `rules/common/windows-shell.md` §8b had it right; the orchestrator
  mis-transcribed it into the floor. A rule that tells you to verify against the wrong bytes
  manufactures false confidence in the exact check meant to catch this class.
- Downstream instance: `workflow-authoring/templates/governed-run-orchestrator.md:1145` taught
  the wrong recipe to every agent that read it. Fixed in `faedd97e`.

### CS
- **"`/claude-science` WORKS"** — certified from a **command listing**. A listing is a render,
  not an execution. Executed, both commands ran a detached-HEAD checkout whose `cs-doctor.ps1`
  still contained the exact fail-open line the lane existed to delete (11 rows, `0 FAIL, 1 WARN,
  9 PASS`, zero `NOT-CHECKED`) — while `cs doctor` on PATH returned 13 rows the same minute.
- **"CLASS-FIX, not just the instance"** — refuted with two live counterexamples *inside the
  builder's own file scope*: the watchdog scheduled-task action pointed at the disposable
  `ast-integrate` worktree, and `cs-deploy.sh` installed from the same stale checkout. A third
  instance (a documented probe `install.ps1` never deployed) was found in round 3. The class was
  fixed four times and guarded zero times until `cs_wiring_check.py`.
- **"AFTER 12, all 12 inside the two seam files"** — self-contradicting with the same report's
  own residual: `cs-lib.ps1` carries the same fallbacks. **Three** seam files.
- **"Config centralised"** — true of the repo, **false of the running system**: the live WSL tree
  still held 2026-07-07 copies with no `cs-lib.sh` and no `cs.conf`, so editing `cs.conf` changed
  nothing shell-side. Closed in round 3 (`DEPLOYED_COMMAND_BYPASS_TOTAL=0`, matcher controlled).
- **"Fully hermetic harness"** — WSL probes are stubbed, Windows-side probes are not; the healthy
  control S1 goes RED against an empty `CS_BACKUP_ROOT`. Acting on the residual that recommended
  CI-wiring it "because it is hermetic" would have produced a red job and invited someone to
  "fix" a doctor that is not broken.
- **"TWO stale sidecars"** → four (two pairs). **"`git mv` from cs.md"** → git recorded A + M,
  not a rename.
- **An auditor overclaim, withdrawn on new evidence:** the 168h backup cadence was flagged as
  contradicted by an observed ~20-minute snapshot cadence, then correctly withdrawn once the
  invocation graph showed those were `cs fix` side effects.

### SKILLS
- **The tool's own docstring: "FOUR SAFETY PROPERTIES, each enforced AND self-tested."** False
  for P4, and structurally so — `--self-test` returns before `main()` reaches the `--apply`
  branch, so no fixture inside it can reach P4. Mutation-proven: the tool's self-test left 2 of 3
  mutants alive; the new suite killed 3 of 3.
- **"434 files need a human merge"** → rescoped to **189** genuinely two-directional; the other
  245 are fully accounted (199 vendored, 31 `.bak-`, 12 self-nested, 3 binaries).
- **Two of its own CONTROLS were broken detectors.** Attempt 2 returned green in all three states
  — reporting off it would have been evidence-tag theatre.

### P2
- **"38 delivered"** → **38 *substantive*; Prompt Two has 2 delivered of 2,007** (`c0f4e169`).
  The single largest number-correction of the wave.
- **"one added key was enough to be counted DELIVERED"** (`11c53a1b`), and `why_not_delivered`
  used the wrong resolver and over-counted delivered 2 vs 1 (`c4b82e39`).
- **The charter promised a two-directional ratchet; the code only printed the falling case.**
  Brought the CODE up to the CHARTER rather than weakening the sentence (`a9b7dde5`).
- **`--self-test` fails closed but the partition run did not** — dark checker, 367 declarations
  unchecked, still `SUCCESS`.
- **Its own corrected overclaim:** WFA-0001 reported as a surviving mutation. It was not — that
  artifact is a JSON Schema pack, so dropping `$schema` leaves a valid discriminating schema. The
  claim was narrowed rather than the finding buried.

### CASUALTY
- **Eight round-1 CASUALTY verdicts, of which SIX were false.** Those outputs are now
  banner-stamped `_DO_NOT_CITE` rather than deleted, and a guard probe keeps the banners on.
- **Its own anti-rot check was VACUOUS** — "every EXECUTED instrument has a real call site"
  returned True for all eight names *because every name is also a key of the registry dict*.
  Use-vs-mention, reproduced inside the check written to prevent it.
- The wiring probe printed a **fake locator** ("line 176" for an invocation at line 439); P4
  **crashed instead of failing**, which in a CI log reads as infrastructure noise, not a finding.

### MON
- **"13 stale monitorcore files"** → **0 real drift**. **"a `[cockpit]` stanza at line 58 of all
  three `monitors.toml` copies"** → line **72**, and **2** registries plus **1** fixture.
- **R-M18's blocker was misidentified** (the SUCCESS-branch reviewer clause is real but gates
  only SUCCESS receipts; `BLD-0023.json` is a schema-valid BLOCKED receipt with no reviewer — I
  confirmed `state: BLOCKED` myself).
- **Two of its own detectors failed:** an earlier round shipped a bare `grep mtime` that matched
  `fromtimestamp`; and a PowerShell CR-byte probe resolved a relative path against the wrong cwd,
  threw, and printed `CR bytes: 0` from the empty result. Both disclosed rather than cited.

### WFSOTA
- **"tools/wf-timeout is named NOWHERE"** — confirmed by the auditor, then closed. Round 1 had
  shipped a linter with 110 tests and a 100% CI lane that had never been run over a line of
  workflow code.
- A proposed permanent `--cov-fail-under=95` exception was replaced with an actual test.
- **`workflow_lint._maps_nulls` was a bare substring test** — a real defect, fixed in this pass
  (§8), and its severity re-scoped: measured corpus impact today is **zero**, not "fires once".

---

## 5. CROSS-LANE FINDINGS

Things no single lane could see.

**C1 — `.github/workflows/quality.yml` is the estate's single-writer hazard, and it fired twice
in one night.** `772159ce`: a sibling's blanket `git add` swept the entire CS lane (cs.conf,
cs-lib.sh, the harness, both SKILL.md twins) into a 66-file commit titled *"print WHY a unit is
not delivered"* — content intact, attribution lost. `f087a6f6`: CASUALTY's `git add
.github/workflows/quality.yml` carried P2's **uncommitted** `gate-p2-delivery` step, whose charter
entry did not exist yet, so `charter_check.sh` — which runs inside `gate-lint-format`, the FIRST
gate — went red and **every PR on main was blocked** until `96b44bf8`. The mechanism is precise:
pathspec staging stops a lane *staging* a sibling's file; **nothing stops a lane *committing* a
sibling's uncommitted edit to a file both lanes touch.** Verified fixed: `charter_check` →
`OK -- 7 gates consistent`.

**C2 — "CI has never run" is not five residuals, it is one.** MON §6.2, CASUALTY R-I1, WFSOTA R2,
P2 §4 and SKILLS all disclose it independently and identically. One PR closes all five. This is
the highest-value single action available and it costs nothing.

**C3 — a blocker chain neither lane can see.** WFSOTA R1 defers its live deploy on the grounds
that *"a concurrent sibling lane is already fixing it"* (SKILLS' `deploy-skills-daily.py`).
SKILLS' hop targets `skills.daily` only and, by design, **REFUSES two-directionally diverged
files**. `workflow-authoring/SKILL.md` **is** two-directionally diverged. So WFSOTA's residual can
never be closed by the tool it is waiting on. It needs a union-merge decision, not patience.

**C4 — `~/.agents/skills` is nobody's tree.** SKILLS R1 (no guarded writer; ui-audit guard 0/6)
and WFSOTA R1 (32-vs-234 divergence there too) are the same gap seen from two sides. One tree,
two lanes, no owner, and a `-Prune` path that would delete two live skills.

**C5 — the dominant defect class of the whole wave is "a long-lived reference points at a stale,
disposable or absent tree", and five lanes hit it independently.** CS four times (slash command →
detached HEAD; watchdog → ephemeral worktree; `cs-deploy.sh` → stale checkout; a documented probe
never deployed). CASUALTY: four instruments hardcoded this box's repo root so none could run in a
clone — *lesson 1 of this program, reproduced inside the lane that exists to catch it*. WFSOTA and
SKILLS: the blob-verification recipe naming the wrong command. MON: three gates that proved
byte-identical / tracked / present but never that anything **launches**. Only CS built a
generalizable standing guard for it (`cs_wiring_check.py`, 10 repo-only invariants). **That
instrument's shape — decidable from the repository alone, so it runs on every PR — is the
transferable asset of this wave.**

**C6 — four lanes each rebuilt the same instrument.** `command-center/p2-wave/_i3_blobfmt.py`,
`tools/monitorcore/_blob_ruff.py`, `command-center/casualty/verify_ci_parity.py` and
`docs/workflow-sota/_int_blobcheck.py` are four independent blob-level ruff/CI-parity harnesses —
while a shared `tools/measure-guard/blobread.py` (with its own tests) already existed. I made it
five before deciding not to add mine to the repo. This is the fan-out contract's
"shared grounding pack" item going unapplied, and it is cheap to consolidate.

**C7 — one frozen directory blocks three lanes' closure simultaneously.**
`command-center/adversarial/` being off-limits is why P2's 4 contract-rejected artifacts are
reported-not-gated, why CASUALTY's two receipts sit outside their canonical `output_path`
(R-I4) and why its `census_v2.py` is `TESTED` rather than `CI-EXECUTED` (R-I6). That is a
scheduling decision, not an engineering one.

**C8 — a lane residual whose severity I am correcting downward.** P2 discloses that
`tools/measure-guard` has **no registered suite floor**, so its 117 collected tests (its own 21,
MON's 26, and 70 pre-existing) are "ungated against collapse". Partly true: `pytest` exits **5**
on zero collected, so a *total* collapse already turns the existing
`gate-tests-coverage measure-guard` step red. The genuinely uncovered case is a **partial**
collapse (117 → 3). Real, smaller than stated, and deliberately not fixed by me — see §8.

**C9 — the id-shape blocker is a platform decision wearing a monitor lane's clothes.** It reads
as MON residual R-M18, but `$defs.unit_id` rejecting **0/103** register rows means *no register
row in the estate can produce a valid receipt*. Fixing it for MON fixes it for all 103.

---

## 6. OWNER DECISIONS WAITING

Each is an answerable question with my recommended default.

| # | Question | Recommended default |
|---|---|---|
| **D1** | Open one PR so CI actually runs these six gates? | **YES, now.** It is the only thing that closes five identical residuals, and it costs one PR. Read the `test-python` and `gate-lint-format` job logs; the named risk is the 3.11-vs-3.12/3.14 gap. |
| **D2** | Fix the receipt id shape by **widening** `$defs.unit_id`, or by giving register rows an emittable **`receipt_id` alias**? | **ALIAS.** Widening loosens a pattern that currently validates 2007/2007 work units — a contract worth keeping tight. The alias touches only the 103 register rows. |
| **D3** | Union-merge `workflow-authoring/SKILL.md` (53 live-only lines are the input) and then deploy? | **YES, as an owner-run merge — not an agent deploy.** The 53 live-only lines are unread by anyone; a machine cannot decide which survive. Then re-run the reachability probe and require `unsafe_to_deploy=0`. |
| **D4** | Give `~/.agents/skills` a guarded repo-side writer (point `deploy-skills-daily.py` at it with `--target`), or declare the Codex vault hand-deployed forever? | **Point the existing tool at it in DRY-RUN and read the plan first.** It is one flag. Do **not** run `sync-skills.ps1 -Prune` — it deletes `microsoft-foundry` and `qdx-rush`. |
| **D5** | When does `command-center/adversarial/` unfreeze? | **After the currently-active sibling wave is quiescent.** Then re-run `_i4_percontract.py`, promote the two casualty receipts to their canonical path, and ratchet the count. |
| **D6** | De-curate the 23 `source-command-*` wrappers and deploy the 75-skill description cap? | **NO, not yet.** The 26 description-less skills are a **render** bug, not a curation gap; rewriting good descriptions trades real text for nothing while the render bug still hides them. Diagnose the render path first. |
| **D7** | Merge or retire any of the 328 skills? | **KEEP everything.** The overlap lens never got adversarial clearance and token-level evidence cannot see functional redundancy. Default hard to KEEP. |
| **D8** | Fix the cross-vendor review rail before dispatching another build wave? | **YES.** 43 units and 449 READY units all name an independent cross-vendor reviewer. Building more units into a dead rail manufactures more un-reviewable work. |
| **D9** | One worktree per lane (or a single-writer rule on `quality.yml`) for the next wave? | **Worktree per lane.** Two commit-sweep incidents in one night, one of which red-blocked every PR on main. |
| **D10** | Register a `measure-guard` suite floor (C8)? | **Defer.** Total collapse is already caught by pytest exit 5; the fix requires editing the twice-burned shared `quality.yml`; siblings are still extending that directory. Revisit when the estate is quiet. |

---

## 7. RANKED NEXT ACTIONS

1. **Open one PR and read the CI logs.** Closes the single residual shared by five of six lanes.
   Zero build cost, and until it happens every "wired into CI" claim in this wave is
   *likely (55-80%)*, not measured.
2. **Fix the cross-vendor review rail** (`mcp__codex__codex` → agent-identity registration
   failure). It gates 43 BLOCKED units and every one of the 449 READY units. Note the trap it
   already sprang: three green signals (`codex --version`, `Get-Command`, `mcp list ✔ Connected`)
   and the rail is unusable — probe with a real call, never a health check.
3. **Decide D2 (receipt id shape)**, then emit R-M18's receipt with `p13_emit_receipt.py`.
   Unblocks R-M06 and un-gates MONITOR; unblocks 103 register rows as a side effect.
4. **Union-merge `workflow-authoring/SKILL.md`, then deploy the 32 absent-live files.** This is
   the only route that closes WFSOTA R1 (C3).
5. **Point `deploy-skills-daily.py --target ~/.agents/skills` in dry-run** and read the plan.
   Closes the last live silent-no-op (`ui-audit` 0/6 in the vault).
6. **Unfreeze `command-center/adversarial/`**, promote the two casualty receipts, re-run
   `_i4_percontract.py`, and get reviewers onto ADV-0021 / ADV-0022.
7. **Adopt worktree-per-lane** before the next wave (C1).
8. **Consolidate the five blob-parity instruments onto `tools/measure-guard/blobread.py`** (C6) —
   pure cleanup, no behaviour change, removes four drift sites.
9. **Generalize `cs_wiring_check.py`'s shape** into a standing repo-only reference-integrity gate
   (C5). This is the wave's transferable asset and currently exists for exactly one directory.

---

## 8. FIXED IN THIS PASS (synthesis lane)

Cross-lane items small enough to close now. Everything else above genuinely needs a decision
(§6) or a long build (§7).

### F1 — `workflow_lint._maps_nulls` false negative (WFSOTA R5), CLOSED

The rule that suppresses `parallel-filter-boolean` when a `.map()` handles nulls tested for the
**substring** `"null"`, so `.map(v => v.nullable)` silently suppressed a warning it should have
raised. Now word-bounded (`\bnull\b`). Why it mattered enough to fix: WFSOTA's own integration
made `workflow_lint` a **CI-executed** gate this session, so a false negative went from academic
to live. It sat in a residual because it is in `skills/**`, outside that lane's file scope — and
outside every other lane's too.

- Files: `skills/workflow-authoring/scripts/{workflow_lint.py,test_workflow_lint.py}` and their
  `.agents/skills/` dual-write twins (verified byte-identical after the edit; the estate's
  dual-write gate passes: `OK: no skills/ change lacks a .agents/skills/ counterpart`).
- Two tests added as a **pair**, not one: a positive control (a `.map` that genuinely types the
  null drop, with no `.filter(Boolean)`, must still suppress) and the new negative case. Without
  the positive control a permanently-red rule would satisfy the new assertion.
- Suite: `110 → 112 passed`, coverage held at **100%** (453 stmts / 216 branch / 0 miss).
- **Both-states control, because a green suite proves nothing until the assertion has been
  watched to fail.** Reverting the fix in a scratch copy:
  `CONTROL fixed rc=0 112 passed` / `MUTANT reverted rc=1 1 failed` — RED on exactly the new
  test, positive control unaffected → `SUCCESS:mapsnull-control`.
- **My first control harness was broken and I fixed the instrument before reading it.** Copying
  only `scripts/` produced 11 failures in *both* states (the suite reads `templates/` by relative
  path). A harness that is red in both states measures nothing; copying the whole skill directory
  fixed it.
- **Severity re-scoped downward, honestly:** WFSOTA described this as firing "once on the whole
  live corpus". Measured after the fix, `wf_gate.py` over the real corpus is **unchanged** —
  `0 error(s), 1 warning(s) across 15 block(s)`, and that one warning is `agent-schema`, not
  `parallel-filter-boolean`. So this is a latent false negative closed, with **zero** corpus
  churn — not a live suppression removed.
- Pinned CI lint on all four files: `ruff@0.15.17 check` → *All checks passed*;
  `format --check` → *4 files already formatted*.

### F2 — refuted register evidence recorded (MON §6.5 delegated this explicitly), CLOSED

MON's dossier says verbatim: *"Recording those corrections belongs to whoever owns
`command-center/sources/REGISTER.md`. Record the refutation; do not delete the rows."* No lane
owned that file. New **§9** appended to `command-center/sources/REGISTER.md`; **no row deleted**.
It refutes four premises a reader of §1C or §8 would otherwise act on: *"13 monitorcore files
stale"* (0 real drift), *"cockpit unregistered"*, *"stanza at line 58 of all three copies"*
(line 72, 2 registries + 1 fixture), and R-M18's misidentified blocker.
Independence is declared per row: the launch refutation is **my own run** at HEAD `39f30ab2`
(`SUCCESS:launchpath 2 launch(es) … 5 exempt`), the id-shape refutation is **my own
re-derivation** from the schema (`BLD-0023`→True, `ADV-0021`→True, `R-M18`→False, and
`BLD-0023.json` carries `state: BLOCKED`); the line-72 correction is MON's, cited not re-run.

### F3 — cross-lane verification performed and recorded (not a code change)

All six headline gates re-run **together at HEAD**, whole-repo ruff filtered to tracked files,
and blob-level CI-parity over the 21 `.py` files that landed after the last sweep with a control
that fired. Results in §1. Nobody had done this; each lane verified itself at its own commit.

Post-commit, my own six blobs measure **0 CRLF** each (binary `git cat-file` reads) — the LF form
CI checks out. Getting that number cost **two more self-caught detector failures**, recorded
because this wave's dominant lesson is that instruments lie before code does:

1. The first probe piped `git cat-file -p` through PowerShell's `Out-String`, which re-joins the
   pipeline with CRLF. It reported 415/339/962 CRLF on files git had *just* said were LF in the
   index. Self-contradicting output is a detector failure, not a finding — replaced with binary
   reads, never reported as a result.
2. The replacement's **control predicate was wrong**: it asserted every worktree copy is CRLF, but
   four of the six were written LF by the editing tool, so the control read `False` and the script
   printed `FAILED`. The counter is nonetheless proven able to see CRLF — it returned 962 on the
   two genuinely-CRLF worktree copies. The correct control is "at least one known-CRLF file counts
   non-zero", which holds. **A failing control invalidates the verdict, not the reading** — but
   only once you have checked which of the two is wrong.

### Deliberately NOT fixed, with the reason

- **`measure-guard` suite floor** (C8/D10) — needs an edit to the twice-swept `quality.yml`
  while siblings are active, and the exposure is smaller than the residual states.
- **`is_noise()` leaking `.bak-` directories** (SKILLS R4, inflates `needs_merge` by 31) — a
  one-line fix in a differ that three lanes' published numbers depend on. Changing it now
  invalidates their evidence for a cosmetic count. Do it when the estate is quiet.
- **The five duplicated blob-parity instruments** (C6) — consolidation is real work with real
  regression surface, not a synthesis-pass edit. Ranked as next action 8.
- **Anything under `command-center/adversarial/`** — frozen; a sibling wave is writing it.

---

## Discipline record

No `git add -A`, no `git add .`, no `git commit -a`; explicit pathspecs only, with a foreign-path
check between staging and committing. `command-center/adversarial/` never written. No force-push,
no `--no-verify`, no history rewrite. No credential read or modified. `sync-from-live.ps1` and
`install.py` never run. 102 dirty files under `platform/` and 20 under `command-center/` belong to
live sibling agents and were left untouched. My throwaway instruments live in `%TEMP%`
(`synth_blobruff.py`, `synth_mapsnull_control.py`) and were deliberately **not** added to the
repo — five near-identical blob harnesses already exist (C6).
