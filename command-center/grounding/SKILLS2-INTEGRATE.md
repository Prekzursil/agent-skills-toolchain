# SKILLS2 — INTEGRATE lane

STATUS: MEASURED. Every claim below was executed, and the commands are in
`command-center/grounding/S2I-*.out.txt`.

COVERAGE: §1-§5 measured. NOT measured: CI green on a real GitHub runner (I ran the gates
locally on Windows; the one CI-relevant difference I found is settled in §6.1). NOT measured:
whether the advisory surface total predicts truncation in any session other than the two
already sampled — that is deliberately non-blocking for exactly this reason.

## What the lane already had, and what it was missing

SKILLS2 diagnosed the render bug (budget truncation, not parse failure), read the vault
dry-run, wrote the union-merge proposal, and landed 7 negative-case clauses. All four are real.
But the diagnosis lived in prose and probe scripts, and **nothing stopped the next skill author
from re-creating the defect.** The measured hole:

- `ci/check_skill_context_budget.py` enforces a real 8,000-char ceiling and already refuses
  folded scalars — but only over the curated DAILY tier (`ci/skills-allowlist`).
- The 337-346 skill fleet under `.agents/skills` and `skills` had **no description gate at all**.
- The lane's own worst moment — a writer bug stamping a 4,000-char control string over 7 real
  descriptions in 3 trees — was caught by a post-write re-read, i.e. by luck and diligence, not
  by a gate.

## §1 The wiring

| Surface | What landed |
|---|---|
| Gate | `ci/check_skill_description_ratchet.py` — shrink-only ratchet over both repo skill roots |
| Pinned debt | `ci/skill-description-exemptions.txt` — 5 over-spec + 6 folded, shrink-only |
| CI | `.github/workflows/skill-dual-write.yml` — two steps: the suite by explicit path, and the gate run against the real tree |
| Tests | `ci/tests/test_skill_description_ratchet.py` — 23 tests, both-states on every rule |
| Agent surface | `writing-skills/SKILL.md` in BOTH repo roots, and **deployed** to `~/.claude/skills.daily` |

**It is a RATCHET, not a ceiling — deliberately.** An absolute limit is RED at HEAD: 5
descriptions already exceed the 1,024-char spec max (workflow-foundry 1750, silence-trim 1089,
audio-extract-mix 1073, browser-rail 1063, caption-burn 1043) and 6 already use folded scalars.
Shipping that as blocking would have red-blocked main and every sibling PR — the exact failure
this program has already paid for. So the debt is pinned and only NEW violations block. The gate
refuses a STALE pin, so the list can only get shorter.

## §2 The executable check

```
python -m pytest ci/tests/test_skill_description_ratchet.py -q   -> 23 passed
python ci/check_skill_description_ratchet.py                     -> SUCCESS, exit 0
```

## §3 Both states — it goes RED without the integration

**Fail-first, captured before I wired anything** (`S2I-PREWIRE-RED.out.txt`):

```
3 failed, 20 passed
FAILED test_the_workflow_runs_this_suite_by_explicit_path
FAILED test_the_workflow_runs_the_gate_itself
FAILED test_the_ratchet_has_an_agent_facing_surface
  AssertionError: no curated skill tells an agent to run
  `python ci/check_skill_description_ratchet.py`
```

The 20 behavioural tests passed at that point — the gate already worked. Exactly the 3 wiring
assertions were red, and they went green only after the workflow steps and the dual-written
skill edit landed. That is the integration proof: delete either, and this suite fails.

The gate's own defect detection is proven in both states too — each rule has a fixture that
makes it FIRE, including `test_an_oversized_description_fails`, which reproduces the lane's own
4,000-char corruption. `test_the_verdicts_are_distinguishable` asserts clean / violation /
config-error return three DIFFERENT exit codes, so the suite cannot be measuring merely that the
tool imports.

## §4 Deployability — and an independent reproduction of the audit's D1

The audit's one REAL DEFECT was that the builder's 7 **description** edits made previously
IDENTICAL vault files DIVERGED, which the deploy hop refuses by design — widening the very
orphan tree the lane existed to diagnose. I asked the same question of my own edit, with the
builder's 7 files as the paired control in the SAME run (`S2I-DEPLOYABILITY.out.txt`):

| tree | my `writing-skills` | the 7 builder description edits |
|---|---|---|
| `~/.agents/skills` (vault) | before IDENTICAL-class → **RIGHT-AHEAD** | **DIVERGED ×7** |
| `~/.claude/skills.daily` | IDENTICAL → **RIGHT-AHEAD** → deployed → **IDENTICAL** | IDENTICAL ×7 |

`verdicts_are_distinguishable: True` in both runs, so RIGHT-AHEAD carries information. **Audit
D1 is CONFIRMED independently.** The mechanism is the one the builder's own fixture proved: an
append-only body insertion classifies RIGHT-AHEAD and deploys; a description MODIFY classifies
DIVERGED and is refused forever. My edit is a pure insertion, so it deployed cleanly
(`SUCCESS:deploy-skills-daily copied=1`, IDENTICAL 231→232) and added nothing to the orphan pile.

I did **not** write `~/.agents/skills`. It is outside the declared file scope and the audit is
right that the remedy there is a handback, not a write.

## §5 Commit

Explicit pathspec only. The shared file `.github/workflows/skill-dual-write.yml` is edited —
declared loudly here because it is the cross-lane hazard. The edit is purely additive (two new
steps before `gate-skill-surface-manifest`); no existing step, marker or job name changed.
`.github/workflows/quality.yml` is untouched, so no charter obligation is incurred — the same
reasoning the workflow's own header records.

## §6 Residual — honest and inline

### 6.1 One pre-existing test fails on Windows. It is not mine and CI is unaffected.
`ci/tests/test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`
fails locally. Four signals: both that file and its subject are unmodified by me
(`git status` empty); it reproduces with my suite fully deselected; the runner is
`ubuntu-latest`; and the cross-OS probe settles the mechanism — `os.fsdecode(b"\xff")` returns
`'\udcff'` under WSL and raises `UnicodeDecodeError` on Windows. The fixture needs a filename
holding a lone invalid UTF-8 byte, which Windows cannot represent. Full local run:
**667 passed, 1 skipped, 1 failed**. *Almost certain (90-99%) this is Windows-only and
pre-existing. UNVERIFIED that CI is green on it — I did not run CI; settling experiment: read
the next PR's `gate-skill-dual-write self-test` log.*

### 6.2 Audit D2 is CLOSED — by a sibling, not by me. Two NEW sites are open.
The builder's residual #1 and audit D2 both flagged `ui-audit/dead_button_crawl.mjs` as carrying
the old lexical main-guard in the repo trees. **That is now stale:** commit `ea37057f`
("fix a guard whose fix tool never fixed it") landed `__isMain` there, and all four trees now
agree (repo 287/291, live 357/361). I re-derived it rather than repeating the residual.

Searching for the pattern instead of the file surfaced **two sites nobody has reported**, both
in both repo roots, both lacking the helper:

- `design-studio/loop.mjs:233`
- `design-studio-session/session.mjs:625`

`ui-audit/_fix_main_guard.py:33` also matches, but there the pattern is the repair tool's `OLD =
"..."` constant — a mention, not a defect, and excluded on that basis.

Why the guard matters, per the repair tool's own comment: `~/.claude/skills` is a junction to
`skills.daily`, and Node resolves symlinks for ESM, so `import.meta.url` reports the real path
while `process.argv[1]` does not — the guard silently never fires and the script becomes a
no-op. **Not fixed here:** out of DoD, it is another lane's skill, and it is not a one-line swap
(the `__isMain` helper must be inserted in 2 files × 2 roots, and the dual-write gate requires
both roots in the same change). `_fix_main_guard.py` is the right instrument.

### 6.3 The budget overrun is quantified but not acted on, and the number is session-dependent.
The gate prints the cumulative surface (105,637 chars / 346 canonical skills) as **ADVISORY,
never blocking**, with the uncertainty stated in the tool itself: two independent sessions
fitted the same fleet's boundary ~108,144 and 102,511-105,336 — a 13-skill shift — and the
bare-skill count moved 26/29/30 across three samples. Blocking on a one-session number is the
overclaim this lane already retracted once. *Uncertain (20-55%) what the priority/exemption term
behind the post-boundary survivors is. Settling experiment, unchanged: sample cumsum-to-first-bare
across 3-4 sessions of differing injected-context weight and check whether the boundary tracks
total injected context rather than the skill surface alone.*

### 6.4 What this gate does NOT do.
It does not shorten anything, does not fix the 5 over-spec descriptions, and cannot see the live
trees or plugin skills that also consume the client budget. It freezes the repo-side surface so
it cannot silently get worse. Closing the ~7,300-char (one-session) overrun still means removing
curated skills or shortening descriptions — both owner calls, priced in `SKILLS2-GROUNDING.md`.

### 6.5 Description quality, measured on the tree the gate guards.
264/346 canonical skills say WHEN to use; only 60/346 state a negative case. My "names the
sibling" matcher returned 2/346, which is implausible next to 60 and next to the 7 clauses the
builder deliberately wrote — so that matcher is too strict to cite and I have not cited it. The
two credible axes are the ones quoted in `writing-skills`.

### 6.6 The vault's ui-audit no-op and the workflow-authoring union merge are unchanged.
Both remain owner decisions. `command-center/S2-WORKFLOW-AUTHORING-UNION-MERGE.md` still stands
as written; nothing in this lane picked a side.


---

# SKILLS2 — INTEGRATE lane, ROUND 2 (render traps)

Round 1 is preserved above, verbatim and unedited, including the one claim of its own that
this round REFUTES (§R0). Nothing above was deleted.

STATUS: MEASURED. Every command below was executed on 2026-08-14 and its real output is
quoted. NOT measured: CI green on a real GitHub runner — same residual as §6.1, I ran every
gate locally on Windows. NOT measured: whether the corrected `writing-skills` text renders in
a FRESH session (the listing is budget-filtered; body edits are not charged, but that is an
argument, not a receipt).

## §R0 What round 1 left open, and one of its claims that is now REFUTED

Round 1 wired the DESCRIPTION RATCHET — a shrink-only gate over how MANY characters the fleet
spends. It did not ask whether the characters an author spends are RENDERED AT ALL. Two
defects that had actually shipped in this repo were invisible to it, because in both the text
was present on disk and absent from the listing the model received.

**REFUTED, kept rather than deleted.** Line 13 above says the lane "diagnosed the render bug
(budget truncation, not parse failure)", and `ci/check_skill_description_ratchet.py`'s docstring
carried the same exclusive wording. The DOMINANT cause is budget and that survives. The
EXCLUSIVE half does not: `cv-studio` wrote a folded description inside a frontmatter that does
not strict-parse, so the listing dropped the description entirely and rendered 74 characters of
the body `# H1` in place of 729 — nowhere near any cap. Counting folded scalars cannot see this
class, because the defect is the INTERSECTION of a fold with an unparseable frontmatter; a fold
in a VALID file renders fine (11 of 12 measured). The docstring is corrected at source in this
commit, with the refuted version kept beside it.

The corrected sentence is now three causes, not two, and it is in the skill an author reads:
`writing-skills/SKILL.md` §"The skill listing budget", bullet 3.

## §R1 The wiring — what makes this round reachable

| Surface | What landed |
|---|---|
| Gate | `ci/check_skill_render_traps.py` — two blocking rules over the RENDERED surface, in both repo skill roots |
| CI | `.github/workflows/skill-dual-write.yml` — `gate-skill-render-traps self-test` + `gate-skill-render-traps`, additive, placed after the ratchet |
| Dependency | that workflow's `pip install` now pins `pyyaml==6.0.3` — the gate strict-parses and REFUSES to verdict without a parser |
| Tests | `ci/tests/test_skill_render_traps.py` — 24 tests, each blocking rule red-proofed against the blob that really shipped it |
| Agent surface | `writing-skills/SKILL.md` in BOTH repo roots **and deployed** to `~/.claude/skills.daily`: the corrected 3-cause diagnosis plus the command to run |
| Sibling correction | `ci/check_skill_description_ratchet.py` docstring rescoped (§R0) |

The two rules, and why each is a rule:

- `comment-truncation` — a plain (unquoted) `description`/`when_to_use` scalar containing `#`
  after whitespace. `bc-drive-plus` authored 793 characters and 440 were eaten by one `#`.
- `block-scalar-in-invalid-frontmatter` — a block (`>`/`|`) `description` in a frontmatter that
  does not strict-parse. `cv-studio` authored 729 and rendered 74 characters of body heading.

**Blocking, with NO exemptions file.** Measured over all 683 `SKILL.md` in the two repo roots:
zero violations at HEAD, so there is no debt to grandfather; each fix is one line (quote the
scalar). An exemptions list here would only add a stale-pin surface to police. This is the
opposite call from the ratchet's, and deliberately so — the ratchet WAS red at HEAD.

**Deliberately NOT blocking:** a strict-invalid frontmatter on its own. That claim shipped once
in `writing-skills` and was refuted — 5 of the 6 live skills carrying a `: ` in a plain
`description` render in full, so the client's parser is more forgiving than PyYAML. It is
printed advisory (8 files at HEAD) and never blocks. Only the measured intersection violates.

## §R2 The executable check, and it goes RED without the integration

**Fail-first, captured before I touched the workflow** — the suite was complete and the gate
already worked; exactly the wiring assertions were red:

```
$ python -m pytest ci/tests/test_skill_render_traps.py -q
FAILED ci/tests/test_skill_render_traps.py::test_the_gate_is_wired_into_ci
FAILED ...::test_removing_a_wire_turns_the_wiring_check_red[python -m pytest ci/tests/test_skill_render_traps.py -q]
FAILED ...::test_removing_a_wire_turns_the_wiring_check_red[python ci/check_skill_render_traps.py]
3 failed, 21 passed in 3.38s
```

After adding the two workflow steps, unchanged suite:

```
$ python -m pytest ci/tests/test_skill_render_traps.py -q
24 passed in 3.39s
```

Delete either workflow step and those three go red again — `test_removing_a_wire_turns_the_
wiring_check_red` proves that mechanically by cutting each wire in a scratch copy, so the
wiring assertion cannot be a tautology that passes against any file.

All gates on the real tree:

```
$ python ci/check_skill_render_traps.py
skill render-trap surface (ADVISORY): 683 SKILL.md measured, 8 strict-invalid frontmatter
SUCCESS:skill-render-traps no violations                                     rc=0
$ python ci/check_skill_description_ratchet.py   -> SUCCESS:skill-description-ratchet   rc=0
$ python ci/gen_skill_index.py --check --fail-on-drift -> INDEX DRIFT: no             rc=0
$ python ci/gen_skills_manifest.py --check -> skills_tracked=337 manifest_rows=337     rc=0
```

## §R3 Detector controls — both states, on blobs that really shipped

The controls are NOT synthetic mutations of a healthy file. Mutating a good file into the shape
your own regex was written to catch demonstrates self-consistency, not discrimination — this
program already made that mistake once (`SKILLS2-ROUND4-BUILD.md`, the guard census). Each rule
is proven against the REAL blob that shipped the defect and the REAL blob that fixed it:

| rule | BROKEN blob | fires? | FIXED twin | silent? |
|---|---|---|---|---|
| `comment-truncation` | `ff14d2a6^:.agents/skills/bc-drive-plus/SKILL.md` | exit 1, rule matched | `ff14d2a6:` same path | exit 0 |
| `block-scalar-in-invalid-frontmatter` | `878cd621^:skills/cv-studio/SKILL.md` | exit 1, rule matched | `878cd621:` same path | exit 0 |

`control_ok: true` — `SUCCESS:s2i-bothstates gate fires on broken and is silent on fixed`.

**A trap this control walked into and out of.** The obvious fixed-twin for cv-studio is
`1baa7ad5` ("repair unparseable SKILL.md frontmatter"). It is **not an ancestor of main** —
`git merge-base --is-ancestor 1baa7ad5 HEAD` returns **rc=1**; it is the pre-squash branch
commit. Pinning it would have resolved on this box and failed in CI. The squashed twin
`878cd621` (rc=0) is pinned instead. The rc was read explicitly rather than compared `== 0`,
because rc=128 ("could not be asked") is a third outcome and this repo has been bitten by
folding it into "no".

Four further controls stop the gate from being a tripwire rather than a rule, each an executable
test: `foo#bar` and `C#` do NOT fire (proves it is not a naive `"#" in value`); a `#` inside a
QUOTED scalar does not fire (the fix the gate recommends must pass it); a folded scalar in VALID
frontmatter does not fire (11 of 12 live folds render); a strict-invalid file with a plain
description raises advisory only, violations empty. Fail-closed is tested four ways — empty
walk, absent root, missing frontmatter, unclosed frontmatter — plus
`test_configuration_error_exits_two_not_zero`, because CI reads the exit code, and
`test_absent_pyyaml_is_a_configuration_error_not_a_pass`, because "cannot check, therefore
clean" is the no-op-gate shape `rules/common/ci-hygiene.md` forbids.
`test_the_real_repository_measures_a_plausible_number_of_files` asserts a COUNT (>300), because
four successive probes in this program agreed with each other and were all wrong from counting
the wrong collection.

## §R4 Where the defects still live, measured across four trees

```
tree                            n    comment-truncation   block-in-invalid
repo .agents/skills            346          0                    0
repo skills/                   337          0                    0
live ~/.claude/skills.daily    328          0                    0
live ~/.agents/skills (vault)  328          1 bc-drive-plus      1 cv-studio
```

Both repo roots and the tree the client reads are clean, which is why blocking is adoptable.
**The orphan Codex vault still carries both defects live** — the same tree round 1's §6 and the
build lane's residual #3 flagged for its 8 broken main-guards. CI cannot reach it; the deploy
hop refuses every one of those files as two-way diverged. This gate does not close that, and
says so rather than implying coverage it does not have.

## §R5 Residual — honest and inline

### R5.1 CI-green is still UNVERIFIED, and one new import is the reason to say so louder.
Every gate above was run locally on Windows. `.github/workflows/skill-dual-write.yml` now
installs `pyyaml==6.0.3`; local is also 6.0.3, so parse behaviour is pinned across both — but a
pin is an argument, not a receipt. *Likely (55-80%) CI is green on the new steps. Settling
experiment: read the next PR's `gate-skill-render-traps` step log.*

### R5.2 Four pre-existing test failures on Windows, none of them mine — measured, not assumed.
The full sweep the workflow runs (`pytest ci/tests tools/d001-dual-write/tests -q`) reports
**4 failed, 874 passed, 1 skipped**. Round 1's §6.1 named one of them; there are four:
`test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`,
`test_project_keeps_distinct_invalid_utf8_path_bytes`,
`test_verifier_refuses_an_executable_mode_regression`,
`test_atomic_ref_create_refuses_a_branch_created_after_precheck`.
Independent signal, with a control: the same four fail in a PRISTINE clone of HEAD that
verifiably does not contain my files (`ls: cannot access 'ci/check_skill_render_traps.py': No
such file or directory`), `4 failed in 5.88s`. All four need POSIX semantics Windows cannot
represent — invalid UTF-8 in a filename, an executable bit, a shell interposer on `git
update-ref`. *Almost certain (90-99%) pre-existing and Windows-only.*

### R5.3 The gate cannot see the trees the client actually loads.
It walks the two repo roots. `~/.claude/skills.daily` is clean today only because this lane
wrote it; nothing gates it, and the deploy hop is still a local operator command. The vault is
worse (§R4). *A repo-side gate cannot fix a deploy-side orphan; that remains the owner decision
priced in `S2-WORKFLOW-AUTHORING-UNION-MERGE.md` and round 1 §6.6.*

### R5.4 `when_to_use` is gated for the comment trap but not for the block-scalar trap.
`comment-truncation` charges both keys. `block-scalar-in-invalid-frontmatter` is scoped to
`description`, because `description` is where the H1 fallback was MEASURED. Whether a block
`when_to_use` in an unparseable file behaves the same way is *uncertain (20-55%)* and I did not
guess. Settling experiment: take a strict-invalid file, fold only its `when_to_use`, deploy, and
read the entry in a fresh session's listing.

### R5.5 The client's parser is still a black box, and this gate does not model it.
The evidence constrains it — it strips ` #` comments, tolerates `: ` in a plain scalar, and
loses a folded description when the mapping is unparseable — but I did not read client source
and assert nothing about which library it uses. *Speculative (<20%) on internals; the two rules
rest on observed input/output pairs, not on a model.*

### R5.6 Out of this round's scope, unchanged and not silently dropped.
`ci/skill-description-exemptions.txt` still pins five descriptions against a "1,024 spec max"
while the render cap is 1,536 (build-lane residual #2). The vault's 8 silent-no-op main-guards
and the two `design-studio` sites from round 1 §6.2 are untouched. The
`workflow-authoring` union merge is still an owner call, and nothing here picked a side.
