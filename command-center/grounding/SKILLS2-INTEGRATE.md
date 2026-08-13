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
