# E2E WAVE STATUS — one authoritative account of the six-lane program

Written by the SYNTHESIS lane, 2026-08-12, against **HEAD `39f30ab2`**.
Every claim carries the command that produced it, or names the file it was read from, or is
labelled inherited. Forward-looking claims carry a Sherman-Kent band.

**COVERAGE.** Sections 1-8 are all MEASURED. Two things are NOT, and are stated rather than
folded into a pass: (a) no GitHub Actions run has executed any of this wave's gates, and
(b) I did not re-derive every per-lane number — where I cite a lane's own measurement I say so,
and where I re-ran it myself I say that instead.

**§9 was added by a separate SYNTHESIS-REVIEW lane** at HEAD `575a42d8`, which re-executed all six
gates, corrected four overclaims and one misstated blocker **in place above** (each marked
`[REVIEW]`), restored four dropped lane residuals as §2 items 10-13, and rewrote D1/D2/D6. Read
§9.1 first if you want the diff between what this document said at `39f30ab2` and what survived.

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

**[REVIEW, 2026-08-12] Two legs of that sentence were missing and are now supplied.**
(a) `gate-lint-format` runs `ruff check` **and** `ruff format --check`; only the first was
reported above. Measured: `uvx ruff@0.15.17 format --check .` → 14 would-reformat, **0 tracked**
(matcher control passes both states). (b) The blob-level check stopped at `39f30ab2`; this
document's own commit `1ff5bbf8` then added **four more** `.py` blobs (the `workflow_lint` fix and
its two dual-write twins), which had been lint-checked in the WORKTREE only — the exact
worktree-vs-blob gap the check exists to close. Re-measured at blob level with `ruff.toml`
mirrored and a firing control: `SUCCESS:synthrev-blobruff 4 blob(s) CI-clean; control fired`,
0 CRLF each. All six gates below also re-execute clean at **`575a42d8`**, three commits past the
HEAD this document was written against.

### Per lane

| lane | what now exists that did not | anchor |
|---|---|---|
| **CS** | `/claude-science` + `/cs` both resolve **and execute the fixed tool** (they ran a detached-HEAD checkout until round 2). `cs doctor` has a 4th state NOT-CHECKED and exits non-zero on it, closing four fail-open rows (DB timeout mis-reported as "not found", backup PASS over an unreachable VM, a daemon row that silently vanished, a disk row that printed a fabricated `0GB`). Backup **restorability** is proven by opening a temp copy, not by `ls`. The always-on watchdog no longer launches out of a disposable git worktree. Fault injection is armed + banner-marked so the doctor can never be ordered to print an unmarked green. `cs_wiring_check.py` — 10 repo-only invariants — is a **CI gate**, red-proofed with 14 single-wire mutations + a healthy control. | `ebf415f5`, `3545a700`, `d14cea8f`, `39f30ab2` |
| **SKILLS** | The last deploy hop into `~/.claude/skills.daily` (the only tree Claude Code reads) is now **wired into CI twice** and reachable by an agent (`writing-skills/SKILL.md`, +2,823 chars of body, description delta **+0**). 16 hermetic tests; the new suite killed 3/3 mutants where the tool's own `--self-test` left 2 alive. `ui-audit`'s silent-no-op fix reconciled live→repo before anything could deploy over it (**[REVIEW]** re-measured: guard present **6/6** in repo `skills/ui-audit/`, **0/6** in the live `~/.agents/skills/ui-audit/` — same matcher, both states). **[REVIEW]** Both CI lines live in `skill-dual-write.yml`, which is `pull_request`-only (§2 item 1), and the agent-facing reachability is **single-carrier** (§2 item 11). | `e9b65d60`, `3678417c` |
| **MON** | `launchpath.py` — the first thing in this repository that **executes** a registered monitor instead of checking its bytes — materialising from committed blobs, both registry mirrors, every stanza accounted for by name, fail-closed six ways. 4-leg both-states control (incl. an inverted control). Verified on **Linux as well as Windows**, and from a **real LF clone**. Cockpit health pane adopted as the 6th pane. | `b9a77ad7`, `0ae5b2a6`, `cdac3f26` |
| **P2** | `ready_units.py` — the delivery predicate that stands between a fabricated artifact and a `delivered` count — is now a CI gate (`gate-p2-delivery`) with a **self-defending seam** that runs in a different step, so deleting the gate still turns something red. A live fail-open was found and fixed *before* wiring: with the contract checker dark, 367 declarations unchecked and 2,007 units ungated, the tool still printed `SUCCESS`. 4-mutation red-proof with attribution checked. | `70f70f74`, `eac025c6`, `a9b7dde5` |
| **CASUALTY** | Two dead agents' work recovered as receipts that reproduce their published digest and byte count; `casualty_guard.py` (6 probes) + `integration_redproof.py` (4 controls) wired into CI plus a second independent `suitefloor --suite casualty` line. Four instruments that hardcoded this box's repo root now derive it from `__file__`, so they run in a clone — verified by an actual clone: `SUCCESS:int-freshclone`. **[REVIEW]** Detects a missing wire; does **not** enforce one — not tamper-proof (§2 item 12). | `f087a6f6`, `5e3c2271`, `bc411d87` |
| **WFSOTA** | H6 per-agent timeout + settled barrier, and the CI step **is** the H6 red-proof (its control feeds `parallel()` a thunk that never resolves and requires the barrier to hang). `workflow_lint` — 110 tests, 100% coverage, and **never run over a line of workflow code** — now runs over the real template corpus on every PR. Non-circular pin: the wiring assertion lives in a *different* workflow's directory sweep, so deleting the step turns that other workflow red. Coverage taken 99%→100% with a real test instead of a permanent exception. | `1f05e805`, `b3412595`, `5c4111fc` |

---

## 2. STILL BROKEN — with the precise blocker

1. **No GitHub Actions run has executed ANY of this.** Five of six lanes disclose this in the
   same words. Five new/extended gates (`gate-p2-delivery`, `casualty`, `launchpath`,
   `wf-timeout`, `gate-skill-deploy-hop`, plus CS's `cs-wiring`) have runner evidence of exactly
   zero. ~~Blocker: nobody has opened a PR.~~ **[REVIEW — the blocker was misstated; corrected
   here, and it changes D1.]** The real blocker is measured, two mechanically-independent signals:
   `git rev-list --left-right --count origin/main...HEAD` → **`0  75`**, and a live
   `git ls-remote origin refs/heads/main` → **`2decae91`**. **The entire wave is UNPUSHED — 75
   commits ahead of `origin/main`, 0 behind — and the checkout IS `main`.** Two consequences the
   lanes could not see individually:
   - `quality.yml` triggers on **`push: branches: [main]`** as well as `pull_request`. So a plain
     push of `main` runs four of the six gates (`casualty`, `launchpath`, `gate-p2-delivery`,
     `wf-timeout` — all four measured to sit in job `test-python`, which carries no job-level
     `if:`). No PR is required for those four.
   - `skill-dual-write.yml` triggers on **`pull_request: branches: [main]` ONLY** (`:34-36` — this
     is SKILLS R2, a lane residual this document dropped). Its two gates, `gate-skill-deploy-hop`
     and `gate-cs-wiring`, therefore **can never run on a push to main**, and cannot be reached by
     a `main → main` PR either, because that PR cannot exist. The route is: push HEAD to a
     non-main branch (`git push origin main:refs/heads/<branch>`), then open one PR into `main`.
   Band that they pass first try: **likely (55-80%)**. **[REVIEW]** That band silently *lowers*
   two lanes': MON §6.2 says *almost certain, low end (~90%)* and CASUALTY R-I1 says
   *almost-certain (90-99%)*. The downgrade is defensible and is kept, but it is a downgrade and
   is now labelled as one. It is raised above a guess by three independent legs (a Linux
   interpreter run, real LF-clone runs, blob-level ruff parity) and lowered below "almost certain"
   by the one thing none of them removes: the runner's Python. **[REVIEW — precision]** "CI pins
   3.11" is true of every job that runs these gates (`lint:81`, `types:134`, `test-python:290`,
   and `skill-dual-write:55`) but is *not* true of `quality.yml` as a whole, which also pins
   **3.12** at `:1453` and `:1522`. Every local leg measured 3.12.3 / 3.14.6.
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
5. **REFUTED 2026-08-14 — this item asserted "The cross-vendor review rail is DOWN, and it gates 42 blocked units". [superseded 2026-08-14]**
   The wording is kept rather than deleted: it is preserved verbatim in permanent commit messages
   and cannot be corrected there. It was pronounced down on ONE transport — a single failing
   `mcp__codex__codex` call (`agent identity registration failed for
   …auth.openai.com/api/accounts/v1/agent/register`) beside two green signals, `codex --version`
   and `claude mcp list … ✔ Connected`. None of the three probes the rail end to end.
   **Re-probed 2026-08-14 on two mechanically independent transports, with a control:**
   `codex exec --ignore-user-config --sandbox read-only -o <f> -` exits 0 and the output file
   carries the exact nonce its prompt demanded; `mcp__codex__codex` returns its nonce too; and the
   SAME CLI call with `CODEX_HOME` pointed at an empty directory fails `401`, so the probe can
   demonstrably see an auth failure. **42 units still DEMAND a cross-vendor review and 39 are
   still owed one** — 3 already hold an executed Codex PASS, so restoring credentials was never
   the lever for those. The owning page is `command-center/CROSS-VENDOR-RAIL-STATUS.md`;
   `rail_count_gate.py` C6 now fails closed when this item and that page disagree, which is the
   check that was missing while this bullet stayed wrong for a whole round.
   Separately, **449/449 READY units carry a `reviewer_requirement`**, so no unit can reach
   `state: SUCCESS` from a build lane at all.
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

**[REVIEW] Items 10-13: lane residuals this document dropped.** Each was in a terminal on-disk
dossier the synthesis read. Restored with its source so no reader has to re-derive them.

10. **The next casualty triage still runs the tool with the known over-match** (CASUALTY R-I5).
    `command-center/recover_failed_agents_v2.py` was written but **is not installed over v1**;
    `command-center/recover_failed_agents.py` is what a triage invokes, and it over-matches
    **62/92** transcripts. Outside that lane's file scope, and outside every other lane's — so it
    appeared in no §2, no §6 and no §7 row of this document until now. This is a live defect, not
    a caveat.
11. **The deploy hop's agent-facing reachability rests on exactly ONE skill body** (SKILLS R8).
    The +2,823-char edit lives in `writing-skills/SKILL.md`; a re-vendor from upstream
    `superpowers` overwrites it and the hop goes dark. Not silent —
    `test_the_deploy_hop_has_an_agent_facing_surface` turns RED — but §1 states the reachability
    as shipped without stating that it is single-carrier.
12. **The casualty integration is NOT tamper-proof** (CASUALTY R-I2, verbatim: *"Do not read this
    integration as tamper-proof"*). The red-proof shows the guard *detects* a missing wire; it
    cannot *enforce* one, because deleting the CI line also stops the guard running. §1's
    "self-defending seam" / "second independent line" language carries the mitigations and not the
    limit. Branch-protection / CODEOWNERS question, not a script question.
13. **Eight WFSOTA round-1 residuals are still open** (WFSOTA R3: *"Round 1's residuals 2-9 are
    untouched by this lane"*, `docs/workflow-sota/BUILD-LOG.md`), including R6 (migrating the 15
    live barriers to `pipeline()`/`settle()`) and R5 (two competing resume mechanisms). This
    document counted WFSOTA's integration residuals and not its build residuals.

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
| **D1** | **[REVIEW — rewritten; as originally phrased this was not executable.]** The wave is 75 commits ahead of `origin/main` and **unpushed**, and the checkout is `main`, so there is no `main → main` PR to open. Push `main`, or branch-and-PR, or both? | **BOTH, in this order.** (1) `git push origin main` — `quality.yml` fires on `push: [main]` and runs four of the six gates with no PR at all. (2) `git push origin main:refs/heads/wave/e2e-2026-08-12` and open **one** PR into `main` — `skill-dual-write.yml` is `pull_request`-only, so `gate-skill-deploy-hop` and `gate-cs-wiring` are unreachable any other way. Read the **`lint`** job (which contains the `gate-lint-format` step and `charter_check.sh`) and the **`test-python`** job; the named risk is the 3.11-vs-3.12/3.14 gap. Pushing 75 commits at once is the cost of having worked on `main`; see D9. |
| **D2** | Fix the receipt id shape by **widening** `$defs.unit_id`, or by giving register rows an emittable **`receipt_id` alias**? | **ALIAS.** Widening loosens a pattern that currently validates 2007/2007 work units — a contract worth keeping tight. The alias touches only the 103 register rows. **[REVIEW]** This decision already has a second, differently-worded row open: `command-center/sources/REGISTER.md` §6 **OQ-8** and its §9 both point at it. Answer D2 and mark OQ-8 resolved-by-D2 in the same edit, or the register keeps asking. |
| **D3** | Union-merge `workflow-authoring/SKILL.md` (53 live-only lines are the input) and then deploy? | **YES, as an owner-run merge — not an agent deploy.** The 53 live-only lines are unread by anyone; a machine cannot decide which survive. Then re-run the reachability probe and require `unsafe_to_deploy=0`. |
| **D4** | Give `~/.agents/skills` a guarded repo-side writer (point `deploy-skills-daily.py` at it with `--target`), or declare the Codex vault hand-deployed forever? | **Point the existing tool at it in DRY-RUN and read the plan first.** It is one flag. Do **not** run `sync-skills.ps1 -Prune` — it deletes `microsoft-foundry` and `qdx-rush`. |
| **D5** | When does `command-center/adversarial/` unfreeze? | **After the currently-active sibling wave is quiescent.** Then re-run `_i4_percontract.py`, promote the two casualty receipts to their canonical path, and ratchet the count. |
| **D6a** | De-curate the 23 `source-command-*` wrappers? **[REVIEW — split from D6; it bundled two decisions under one reason.]** | **NO, not yet**, and prefer **de-curation over deletion** if it ever happens: the `/command` and the vault copy both survive de-curation, whereas deleting loses Codex-side fallback prose that is unquantified for 22 of the 23. |
| **D6b** | Deploy the **committed 75-skill description cap**? | **NO, not yet.** **[REVIEW — the locator was missing; the owner could not find the artifact from this document.]** It is the grounding lane's R1b: `command-center/grounding/SKILLS-FLEET-GROUNDING.md:241` — *"75 skills, −17,244 chars"* — carried forward as SKILLS R5. Reason to hold, and it is NOT the render bug: a description is the **entire lexical recall surface**, so every keyword shortened away is a query that no longer matches, and the before/after cannot be measured from inside a subagent (the startup truncation warning is not readable there). |
| **D6c** | Rewrite the 26 description-less skills? | **NO.** They are a **render** bug, not a curation gap — their `SKILL.md` on disk carries a real description (workflow-foundry: 1,750 chars). Rewriting trades good text for nothing while the render path still hides it. Diagnose the render path first. |
| **D7** | Merge or retire any of the 328 skills? | **KEEP everything.** The overlap lens never got adversarial clearance and token-level evidence cannot see functional redundancy. Default hard to KEEP. |
| **D8** | Fix the cross-vendor review rail before dispatching another build wave? | **YES.** 42 units and 449 READY units all name an independent cross-vendor reviewer. Building more units into a dead rail manufactures more un-reviewable work. |
| **D9** | One worktree per lane (or a single-writer rule on `quality.yml`) for the next wave? | **Worktree per lane.** Two commit-sweep incidents in one night, one of which red-blocked every PR on main. |
| **D10** | Register a `measure-guard` suite floor (C8)? | **Defer.** Total collapse is already caught by pytest exit 5; the fix requires editing the twice-burned shared `quality.yml`; siblings are still extending that directory. Revisit when the estate is quiet. |

---

## 7. RANKED NEXT ACTIONS

1. **Push, then open one PR from a non-main branch, and read the CI logs.** **[REVIEW — corrected;
   see §2.1 and D1.]** The wave is 75 commits ahead of `origin/main` and unpushed, on `main`. A
   push alone runs four of the six gates (`quality.yml` fires on `push: [main]`); the other two
   live in a `pull_request`-only workflow and need a branch-and-PR. Closes the single residual
   shared by five of six lanes. Zero build cost, and until it happens every "wired into CI" claim
   in this wave is *likely (55-80%)*, not measured.
2. **Fix the cross-vendor review rail** (`mcp__codex__codex` → agent-identity registration
   failure). It gates 42 BLOCKED units and every one of the 449 READY units. Note the trap it
   already sprang: three green signals (`codex --version`, `Get-Command`, `mcp list ✔ Connected`)
   and the rail is unusable — probe with a real call, never a health check.
3. **Decide D2 (receipt id shape)**, then emit R-M18's receipt with
   **`command-center/p13_emit_receipt.py`** — **[REVIEW]** the path was missing and the tool is
   *not* under `tools/measure-guard/` where §1's other instruments live. Unblocks R-M06 and
   un-gates MONITOR; unblocks 103 register rows as a side effect. Resolve `REGISTER.md` OQ-8 in
   the same edit.
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
10. **[REVIEW — added] Install `recover_failed_agents_v2.py` over v1** (§2 item 10, CASUALTY R-I5).
    Until then the next casualty triage runs the v1 tool that over-matches 62/92 transcripts. It
    ranks here rather than higher only because no triage is scheduled; it jumps to the top the
    moment one is.

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

## Security notices raised during this pass — surfaced, not actioned

Two hook notices fired while I was closing out. **Neither was actioned on a credential:** per
AGENTS.md §9 credential lifecycle is the owner's, so nothing was rotated, revoked, regenerated or
edited. Both ids are recorded here because a chat message is not a durable surface.

- **`sha256:839ca3224e60` — kind=transcript, classification=UNKNOWN.** A bounded scan could not
  establish it clean (unreadable, linked, oversized, or *changed during inspection*). Nothing was
  modified. **UNKNOWN is not clean and I am not reporting it as clean.** I cannot resolve the id
  to a path, so I make no claim about its contents. Most probable benign cause, **likely
  (55-80%)**: four sibling agents were writing transcripts continuously throughout this pass, and
  a file growing under the scanner produces exactly this verdict. Settling experiment: re-run the
  sweep when the estate is quiet, when a transcript is not being appended to.
  - **[REVIEW, second observation — recorded, not actioned.]** The identical notice fired again at
    the end of the SYNTHESIS-REVIEW pass, hours later and from a different agent:
    `classification=UNKNOWN kind=transcript id=sha256:839ca3224e60`, same wording — *unreadable,
    linked, oversized, or changed during inspection*. **Still UNKNOWN, still not reported clean,
    and no credential was read, printed or modified** (AGENTS.md §9 — lifecycle is the owner's).
    Two things this adds and two it does not. It adds: the id is **stable across two independent
    scans**, so both passes hit the same target, and it is not a one-off artifact of a single
    sweep; and the estate was still not quiet — four sibling agents (`main`, `bleed-audit`,
    `retire-crux`, `routing-hermetic`) were live for this pass too, which is consistent with the
    growing-transcript hypothesis without confirming it. It does **not** add: any resolution of
    the id to a path (I still cannot), nor any read of a transcript, nor any narrowing of the
    band — **likely (55-80%) benign, unchanged**. A stable id across a *changing* file suggests
    the id keys on identity rather than content, which is a testable side-claim and is
    **UNVERIFIED**. The settling experiment is unchanged and still unrun: re-run the sweep with
    no sibling agent writing.
- **`sha256:35a06ea53b67` — kind=artifact, classification=POTENTIAL-CREDENTIAL.** Diagnosed as a
  **use-vs-mention false positive**, the same class that produced four false findings earlier in
  this wave. I had written a throwaway secret-scanner to `%TEMP%` whose CONTROL fixtures included
  a literal PEM private-key header — a fixture *for* a secret detector, not a secret. The
  `per-edit-check` hook blocked the write on that line, correctly by its own rule. I did **not**
  set `PER_EDIT_SECRETS=off`: overriding a security guard is not fixing a false positive.
  **Caveat, self-inflicted:** I deleted the file before hashing it, so I cannot *prove* the
  flagged id is that script — the attribution rests on the notice arriving attached to that exact
  write. Confidence it was mine: **likely (55-80%)**, not certain.
- **What I did instead, and it is the better answer:** I was about to become the fifth lane to
  hand-roll an instrument that already exists — my own finding C6. The repo ships
  `gate-secrets (gitleaks)`. Run with the repo's own config over my exact commit range:
  `gitleaks git --config .gitleaks.toml --redact --log-opts 1ff5bbf8^..82d4025e` →
  **`no leaks found`**, exit 0, 2 commits / 39.99 KB. `--redact` means no value could be printed
  even if one existed.

## Discipline record

No `git add -A`, no `git add .`, no `git commit -a`; explicit pathspecs only, with a foreign-path
check between staging and committing. `command-center/adversarial/` never written. No force-push,
no `--no-verify`, no history rewrite. No credential read or modified. `sync-from-live.ps1` and
`install.py` never run. 102 dirty files under `platform/` and 20 under `command-center/` belong to
live sibling agents and were left untouched. My throwaway instruments live in `%TEMP%`
(`synth_blobruff.py`, `synth_mapsnull_control.py`) and were deliberately **not** added to the
repo — five near-identical blob harnesses already exist (C6).

---

## 9. REVIEW — the adversarial pass over this document

Run by the SYNTHESIS-REVIEW lane at **HEAD `575a42d8`** (three commits past the HEAD §1-§8 were
written against), 2026-08-12. Method: re-execute, never re-read. Every verdict below names the
command that produced it. **COVERAGE: R1-R7 are all MEASURED.** What is NOT measured and is not
folded into a pass: no GitHub Actions run (unchanged — §2 item 1), and I did not re-derive P2's
four contract-rejection counts in §2 item 6, because `command-center/adversarial/` is frozen and
those numbers are reported-not-gated already.

### 9.1 Scoreboard

| # | check | verdict |
|---|---|---|
| **R1** | Every SHIPPED command in §1 re-executes at *current* HEAD | **CONFIRMED — 6/6 exit 0**, plus charter |
| **R2** | Every commit sha cited anywhere in the document resolves | **CONFIRMED — 28/28** resolve to `commit` |
| **R3** | Every file named as shipped exists and is tracked | **CONFIRMED**, one path imprecision (fixed) |
| **R4** | Overclaims remaining in the document's own prose | **4 found, all corrected in place** |
| **R5** | Lane residual / refutation dropped by the synthesis | **4 found, restored as §2 items 10-13** |
| **R6** | Owner questions answerable as phrased | **D1 was NOT executable; D6 unanchored+bundled; D2 duplicated. All three rewritten.** |
| **R7** | §8 FIXED claims reproduce | **CONFIRMED** — F1 word-boundary fix present and byte-identical in both twins; F2 §9 present in REGISTER.md with no row deleted |

### 9.2 R1 — the six gates, re-executed by me at `575a42d8`

Not inherited from §1. Each was run in this review, sequentially:

```
python scripts/claude-science/cs_wiring_check.py   SUCCESS:cs-wiring all 10 wiring invariants intact   exit 0
python command-center/casualty/casualty_guard.py   SUCCESS:casualty-guard 6 probe(s) green             exit 0
python tools/measure-guard/launchpath.py           SUCCESS:launchpath 2 launch(es) ... 5 exempt        exit 0
python tools/measure-guard/unitgate.py             SUCCESS:unitgate units=2007 artifacts=53            exit 0
cd tools/wf-timeout && python wf_gate.py           SUCCESS:wf-gate 0 error(s), 1 warning(s)/15 blocks  exit 0
pytest ci/tests/test_deploy_skills_daily.py -q     16 passed in 1.19s                                  exit 0
bash .quality/charter_check.sh                     OK -- 7 gates consistent                            exit 0
```

Two legs §1 was missing, supplied here (both now recorded inline in §1):
`uvx ruff@0.15.17 format --check .` → 14 would-reformat, **0 tracked** (the other half of
`gate-lint-format`, previously unreported); and blob-level CI-parity over the **four** `.py` blobs
this document's own commit added after `39f30ab2` → `SUCCESS:synthrev-blobruff 4 blob(s) CI-clean;
control fired`, 0 CRLF.

**Detector controls, because a clean reading is a claim.** The tracked-vs-untracked matcher was
run in both states (a known-tracked path classifies tracked, a known-untracked path classifies
untracked). `ruff check . --show-files` enumerates **2,126** files including
`tools/measure-guard/launchpath.py` and both `workflow_lint.py` copies, so "0 tracked findings" is
a reading and not an empty walk — and the reason my own scratch never appears is
`.gitignore:76: command-center/_*.py`, checked with `git check-ignore -v`, not assumed. The blob
harness carried a deliberately mis-formatted control which **fired** (`rc=1`) in the same run that
returned `rc=0` for the four real blobs.

### 9.3 R4 — overclaims still in the prose (all corrected in place)

1. **"Blocker: nobody has opened a PR" (§2 item 1) — the blocker was misstated, and it was the
   single most load-bearing sentence in the document** because D1 and next-action 1 both rest on
   it. Measured with two mechanically-independent signals: `git rev-list --left-right --count
   origin/main...HEAD` → `0  75`, and a live `git ls-remote origin refs/heads/main` → `2decae91`
   (so the verdict does not depend on the local remote-tracking ref, last fetched 2026-08-10).
   **The wave is unpushed and the checkout is `main`.** `quality.yml` fires on `push: [main]`, so
   four of the six gates need no PR at all; `skill-dual-write.yml` is `pull_request`-only, so its
   two gates cannot run on a push to main and cannot be reached by a `main → main` PR, which
   cannot exist. Corrected in §2 item 1, D1 and action 1.
2. **"main's FIRST gate is clean as CI will see it" (§1)** rested on `ruff check` + charter only.
   `gate-lint-format` also runs `ruff format --check`, and the blob-level leg stopped at
   `39f30ab2` while this document's own commit added four more `.py` blobs, lint-checked in the
   worktree only — the exact worktree-vs-blob gap the check exists to close. Both legs measured
   (9.2); the sentence is now CONFIRMED rather than narrowed.
3. **"CI pins Python 3.11" (§2 item 1)** is true of every job that runs these gates and false of
   `quality.yml` as a whole (3.12 at `:1453` and `:1522`). Scoped in place; the risk statement
   survives intact.
4. **The band silently overrode two lanes.** §2 item 1 says *likely (55-80%)* where MON §6.2 says
   ~90% and CASUALTY R-I1 says *almost-certain (90-99%)*. Being more conservative is defensible
   and is kept; not saying so was the defect. Now labelled as a downgrade.

### 9.4 R5 — residuals the synthesis dropped (restored as §2 items 10-13)

Each was in a terminal on-disk dossier. Ranked by whether a reader would act wrongly without it:
**CASUALTY R-I5** (the next triage still runs the v1 tool that over-matches 62/92 transcripts — a
live defect present in no §2/§6/§7 row until now, and it earned a new action 10) · **SKILLS R2**
(the `pull_request`-only trigger — the mechanism behind the corrected D1) · **SKILLS R8**
(single-carrier reachability) · **CASUALTY R-I2** (*"do not read this integration as
tamper-proof"*) · **WFSOTA R3** (eight round-1 residuals still open in `BUILD-LOG.md`).

Two things I checked and did **not** call dropped, because the content is carried under a
different label: CASUALTY **R-I3** (no reviewer on either receipt) is §2 item 7, and P2/CASUALTY
**R-I9** (the swept sibling edit, charter-red main) is C1. Counting ids rather than content would
have produced two false findings here — the use-vs-mention shape this program keeps hitting.

### 9.5 R6 — owner questions: two were worse than open

- **D1 was not executable as phrased.** "Open one PR" from a `main` checkout 75 commits ahead of
  an unpushed `origin/main`. Rewritten with the concrete route and what each half buys.
- **D6 bundled three decisions behind one reason and gave no locator for its object.** The
  "75-skill description cap" is real but its only anchor is
  `command-center/grounding/SKILLS-FLEET-GROUNDING.md:241` (*"75 skills, −17,244 chars"*), which
  the document never cited — an owner reading this file alone could not find the thing being
  declined. Split into D6a/D6b/D6c, each with its own anchor and its own reason; the render-bug
  reason answers D6c only, and the cap's real cost is the lexical recall surface.
- **D2 already had a competing row open** — `REGISTER.md` §6 OQ-8 plus §9 — so the owner would
  answer twice or miss one. Cross-referenced in D2 and in action 3.
- D3, D4, D5, D7, D8, D9, D10 are answerable as written. D4's "it is one flag" is CONFIRMED:
  `scripts/deploy-skills-daily.py` exposes `--target` (argparse: `--apply --only --self-test
  --source --target`).

### 9.6 What I verified and left alone

`cs_wiring_check.py` **is** a real gate, not a self-test — `ci/tests/test_cs_wiring.py:228
test_the_real_repository_is_green` calls `wiring.check(REPO_ROOT)`, so a wiring regression in the
repo turns it red; only its *trigger* is narrower than §1 implied. `$defs.unit_id` re-derived
independently: `^[A-Z][A-Z0-9]*-[0-9]{4}$`, `BLD-0023`→True, `ADV-0021`→True, `R-M18`→False.
**449/449** READY units carry a `reviewer_requirement` — my own join of `READY-UNITS.json`
(`ready_units`, len 449) against `WORK-UNIT-CATALOG.json` (2,007 entries, 0 unmatched). The
"42 blocked units" is anchored at `command-center/CROSS-VENDOR-RAIL-STATUS.md:1`, which is now
re-derived on every push by `command-center/p2-next/rail_count_gate.py`; it read 43 when this
section was written. *[superseded 2026-08-13]* The two casualty
receipts are 176,468 B and 114,103 B in `command-center/casualty/`, against 2,100 B and 1,818 B
skeletons at the canonical path — §2 item 7's "two 2 KB skeletons", exactly. The cockpit health
pane exists (`tools/monitorcore/monitorcore/health_source.py`, referenced from `pane_views.py` and
`unified.py`). All 28 shas resolve. `command-center/adversarial/` was read, never written.

### 9.7 Scope of this review, stated rather than implied

I re-executed the gates and re-derived the numbers a wrong decision would rest on. I did **not**
re-run every lane's internal red-proof, re-audit the 21 overclaims in §4 against their source
transcripts, or independently reproduce the two casualty digests. Where §1-§8 cite a lane's own
measurement and I did not re-run it, that citation stands as the lane's, not as mine. My own
scratch instruments are gitignored (`command-center/_synthrev_*.py`) and deliberately not added to
the repo — the same C6 reasoning the synthesis lane applied to its own.

`SUCCESS:synthesis-review` — 4 overclaims corrected, 4 dropped residuals restored, 3 owner
questions made answerable, 2 missing verification legs supplied, 0 SHIPPED items found unshipped.

