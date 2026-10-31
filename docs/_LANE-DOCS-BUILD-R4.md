---
title: _LANE-DOCS-BUILD-R4
type: note
permalink: dqverify-repo-20261013/docs/lane-docs-build-r4
---

# LANE DOCS — BUILD round 4

Docs-vs-reality reconcile. Every row below is an **executed** probe, not a read.

COVERAGE: rows G1–G8 and N1–N2 are measured. Explicitly NOT measured: a real CI run;
a full `validate-all-skills.ps1` sweep over 337 skills; live HTTP reachability of the 498
inventoried URLs. Those are marked `NOT-CHECKED` below rather than folded into a pass.

Starting state, executed before any edit:
`python -m pytest ci/tests/test_docs_executable_claims.py ci/tests/test_docs_gate_ci_wiring.py -q`
→ **25 passed, exit 0**.

---

## 1. What shipped

| # | file | change |
|---|---|---|
| 1 | `commands/context-budget.md` | delegation to a nonexistent skill replaced with the four phases inline |
| 2 | `agent-self/config/commands/context-budget.md` | byte-identical mirror of (1) |
| 3 | `ci/tests/test_command_doc_promises.py` | **new gate** — a command doc may not delegate to a skill that resolves in no skill root |
| 4 | `ci/tests/test_docs_gate_ci_wiring.py` | the new gate added to the wiring assertions |
| 5 | `.github/workflows/quality.yml` | one line, inside the existing docs step — **shared-file edit, declared** |
| 6 | `docs/_lane_docs_r4_bothstates.py` | both-states control on the real pre-fix blob |

---

## 2. The doc-vs-reality table

Verdict = what the probe measured. Resolution = fix-doc / fix-code / no-action, with the reason.

| # | claim | probe (executed) | verdict | resolution + reason |
|---|---|---|---|---|
| **G1** | `commands/context-budget.md:22` — "Run the **context-budget** skill (`skills/context-budget/SKILL.md`)" and ":35 The skill handles all scanning logic…" | `git ls-files \| grep context-budget` → 3 command docs, **zero** skill dir; suffix-resolve over all tracked paths → no `skills/context-budget/SKILL.md` under **any** root; live `~/.claude/skills/context-budget` and `~/.agents/skills/context-budget` both ABSENT | **REFUTED — 100% delegation to a void** | **FIX DOC, and it raises capability.** See §3 for why doc beat code here. Gated by (3) + a regression pin. |
| **G2** | `commands/sessions.md:289` names `scripts/hooks/cost-tracker.js` | `git ls-files \| grep cost-tracker` → EMPTY; file present at `~/.claude/scripts/hooks/cost-tracker.js`. **Then the wider probe:** `hooks/hooks.json` has 26 command entries, **24** name `scripts/hooks/*.js`, and **all 24 are absent from VCS and present live** | **REFUTED — but the grounding's SCOPE was wrong** | **ROUTE to hook-audit, do NOT reconcile one file.** Reconciling `cost-tracker.js` alone would import 1 of 21 siblings and misrepresent a systemic gap as a doc typo. See §4. |
| **G3** | `commands/rollback.md` pre-edit checkpoint | not re-probed — prior rounds measured repo `PreToolUse` n=7 with `edit-checkpoints`, live n=5 without | **still REFUTED (doc right, repo right, DEPLOY stale)** | **no action here.** A corrected deploy plan awaits the owner at `docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md`. Open by design, not undiscovered. |
| **G4** | `README.md:44` stale "Latest (2026-06-10)" banner | already fixed and gated by `test_readme_has_no_stale_currency_banner` | **FIXED (round 2)** | **no action.** Not re-reported. |
| **G5** | dead relative paths in README / AGENTS / CLAUDE / roadmap | prior `docs/_lane_docs_detector.py` (3-state control) | 2 + 1 + 0 + 0, **all use-vs-mention** | **no action.** |
| **G6** | CLAUDE.md's two documented gates | executed both | `SUCCESS:ssot-drift-gate drift=0`; `SUCCESS:ssot-wiring-check wires=6` | **ACCURATE.** |
| **G7** | `AGENTS.md:19` `python .\scripts\test-live-skill-helpers.py` | executed | rc=0 | **ACCURATE.** |
| **G8** | `AGENTS.md:18` `validate-all-skills.ps1` | precondition only | validator PRESENT | **NOT-CHECKED** for the full 337-skill run. |
| **N1** | *(new)* `commands/external-tools-health.md:30` → `skills/external-tools/SKILL.md`, `commands/start-task.md:183` → `skills/plan-review-gate/SKILL.md` | a repo-root-only resolver calls **both** broken. Both files are vendored **metaswarm plugin** commands; metaswarm has its own `.claude-plugin/plugin.json`; both targets exist at `tools/editor/metaswarm/skills/<name>/SKILL.md` | **NOT DEFECTS — the docs are correct** | **no action.** Recorded because a naive gate here is a **3x overclaim**. The multi-root resolver and `test_multi_root_resolution_is_load_bearing` exist to keep it that way. |
| **N2** | *(new)* `hooks/hooks.json` and `agent-self/config/hooks/hooks.json` are **byte-identical** (md5 `c789c2d2…`) and wire 24 hooks to a `scripts/hooks/` tree absent from VCS | executed, see G2 | **REFUTED — a whole referenced tree is live-only** | **ROUTE to hook-audit.** Deliberately **not** gated red by this lane. See §4. |

---

## 3. G1 — why FIX DOC was the right call, not the cheap one

The charter says prefer fixing the CODE when the promise is correct and the code is not, and
cites a charter whose ratchet was fixed in code "because weakening the doc would make the
document true and the estate no safer." The discriminating question is therefore **does the
fix leave the estate more capable, or merely more consistent?**

- Before: `/context-budget` delegated every phase to a file that has never existed in the repo
  or in either live skill root. The command did **nothing** reliably.
- After: the command carries Phase 0–4 inline. It executes.

Capability strictly **increases**, so this is the opposite of the cautionary case.

The alternative — creating `skills/context-budget/` — was costed and rejected **for this round**:
it is a 2-root dual-write (`.agents/skills/` authoritative + `skills/` projection, per
`tools/d001-dual-write/README.md`) that also moves the README `skills/` count off **337**, which
`test_docs_executable_claims.py` gates, plus `docs/roadmap.md` and the skills manifest. That is a
wide, shared-front-door change in round 1 of 4 with siblings active and 296 dirty paths in the
tree. The option stays open, and the gate makes it easy: create the skill and
`test_context_budget_command_is_self_contained` fails loudly with instructions to restore the
delegation.

Phase content is grounded, not invented — the skills half reuses the load model that
`ci/check_skill_context_budget.py` already implements (frontmatter `name` + `description` are
session-start tax; the body is on-demand), and the rules half uses the measured
`paths:`-frontmatter loading rule.

## 4. G2/N2 — the grounding's verdict corrected

The grounding recorded G2 as "live-only file, never reconciled → FIX CODE (reconcile into repo)".
Executed measurement says that resolution is **wrong at the wrong scope**:

```
hooks/hooks.json                       26 command entries
  referencing a TRACKED repo file       2   (skills/continuous-learning-v2/hooks/observe.sh)
  referencing scripts/hooks/*.js       24   ALL absent from VCS, ALL present in ~/.claude
md5 hooks/hooks.json == md5 agent-self/config/hooks/hooks.json   (c789c2d2d0496d632096d6abf66dec71)
```

`cost-tracker.js` is 1 of ~21 siblings in that tree. Importing just it because a doc happened to
name it would leave 20 equally-referenced files behind and turn a systemic VCS-hygiene gap into a
cosmetic doc fix. The doc sentence is **accurate about behaviour** — the metric is emitted — so
FIX DOC is also wrong.

UNVERIFIED [likely 55-80%], stated inline: that `hooks/hooks.json` is live-wired as *this*
plugin's hook entry point (which would make a fresh plugin install run 24 hooks pointing at
nothing) rather than a vendored snapshot of the user's merged live config. The 2/26 repo-owned
ratio is consistent with a merged snapshot. **Settling experiment:** check whether
`agent-self/harness/install.py` deploys `hooks/hooks.json` as an entry point, and whether
`${CLAUDE_PLUGIN_ROOT}` resolves to the repo root for it — one grep plus one install dry-run.
Until that is settled the item is routed, not gated: a gate I cannot keep green is a gate the
next lane disables.

Positive control for that resolution logic, executed: metaswarm's own
`tools/editor/metaswarm/hooks/hooks.json` references `${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh`
and that file **exists** at `tools/editor/metaswarm/hooks/session-start.sh` — so plugin-root-relative
resolution is proven to work on a real case, and a "0 of 4 resolve" reading is a genuine signal
rather than a broken resolver.

---

## 5. Detector controls — what proves each probe fires when broken

Every control below distinguishes **two hypotheses**. A control whose PASS looks identical under
both is inert, which is the failure this repo measured four times in a row on
`manifest["events"][ev]`.

| control | H1 vs H2 | result |
|---|---|---|
| `test_control_negative_absent_skill_fires` | resolver discriminates **vs** resolver always returns True | absent name → **fires** |
| `test_control_positive_present_skill_resolves` | resolver discriminates **vs** resolver always returns False | `multi-ai-mingle` → **silent** |
| `test_multi_root_resolution_is_load_bearing` | single-root **vs** multi-root resolution | `plan-review-gate` fails single-root, resolves multi-root — the two hypotheses give **different** answers, which is what makes it a control |
| `test_control_mention_filter_does_not_swallow_a_real_use` | filter is scoped **vs** filter suppresses everything | USE → not suppressed; MENTION → suppressed |
| `test_control_mention_filter_is_sentence_scoped` | sentence window **vs** paragraph window | a negation in the previous sentence does **not** suppress |
| `test_corpus_is_not_empty` / `test_skill_reference_extraction_is_not_empty` | real corpus **vs** collapsed-to-zero measurement | floors 55 docs / 4 refs; measured 72 / 6 |
| `docs/_lane_docs_r4_bothstates.py` | on **real committed bytes**, not synthetic strings | blob `7f62801d` → **fires at line 22**; fixed tree → **0**. Different in the two states. |

The mention filter exists because the first version of this gate **flagged the very sentence that
fixed the defect** ("…pointed at `skills/context-budget/SKILL.md`, which has never existed") —
use-vs-mention reproduced inside the lane whose subject is use-vs-mention, for at least the third
time in this program's history. It was caught by running the gate, not by inspecting it.

A second self-inflicted error, disclosed: my first command-promise probe reported **3** missing
skills. Two were false (N1). Shipping that number would have been a 3x overclaim; the multi-root
resolver is the fix and its control is now permanent.

---

## 6. Evidence (executed, verbatim markers)

```
starting state   25 passed, exit 0        (2 pre-existing docs suites)
new gate         10 passed, exit 0        ci/tests/test_command_doc_promises.py
three suites     35 passed, exit 0        the two above + the new one
siblings         76 passed, exit 0        test_command_env_deny_awareness, test_cs_wiring,
                                          test_ci_wiring, test_deploy_doc_consistency,
                                          test_rules_doc_coherence
both-states      SUCCESS:docs-r4-bothstates broken_state_fires=1 fixed_state_fires=0
                 mentions_suppressed=1    (blob is 0-CR LF; tree is 68-CRLF -> EOL-agnostic)
wiring control   SUCCESS:r4-wiring-control wired=0 unwired=1
ruff 0.15.17     check "All checks passed!" exit 0; format --check exit 0
                 new files carry CR=0, so working-tree bytes == stored blob bytes
mirror           commands/context-budget.md == agent-self/config/commands/... (sha equal)
commit surface   8b2914da, exactly 7 files, +812/-30, zero sibling paths swept in
```

Post-commit, in a FRESH CLONE at `8b2914da` (empty working tree, no venv) — working-tree
green is not clone green, so these were re-run there:

```
clone-green      35 passed, exit 0    the three docs suites
clone both-states SUCCESS:docs-r4-bothstates broken_state_fires=1 fixed_state_fires=0
clone EOL         the clone checked out test_command_doc_promises.py with 386 CR and
                  commands/context-budget.md with 68 CR -- i.e. the gate was proven
                  green on genuinely CRLF bytes, not only on the LF blobs
MUTATION          `git cat-file -p 7f62801d > commands/context-budget.md` in the clone
                  -> 2 failed, 8 passed, exit 1. The SHIPPED pytest assertion goes RED
                  on the known-broken state and GREEN on the fixed one. This is the
                  strongest control here: it is the gate itself failing, not a probe
                  re-implementing the gate's logic and agreeing with itself.
CI-WIRING PROOF   the literal `run:` block was extracted from the clone's quality.yml
                  and executed as a runner would:
                  SUCCESS:r4-cloneproof commands=3 combined_exit=0
                  (15 + 10 + 10 passed). The wiring is executable, not merely asserted.
```

---

## 7. Residual, disclosed

1. **No real CI run.** Everything above is local + fresh-clone; the commit is not pushed.
   The closest substitute was executing the literal `run:` block out of the clone's own
   `quality.yml` (`SUCCESS:r4-cloneproof combined_exit=0`), which proves the commands run and
   pass but not that the runner reaches the step. Settling experiment: push and read the
   `gate-tests-coverage docs executable claims (README + roadmap)` step.
2. **`.github/workflows/quality.yml` was edited** — one line appended inside the existing docs
   step. No new step, no new charter slug, no change to the step's position relative to the
   py3.12 pivot (a test pins that ordering and still passes). It was clean before the edit.
   Declared because it is the named shared hazard. It was necessary: `skill-dual-write.yml`
   sweeps `ci/tests` but has **no `push:` trigger**, and this program lands commits by direct
   push to main — so a gate reachable only through that sweep never runs on the commit shipping
   it, the exact defect the three commits before this one were fixing.
3. **N2 is routed, not closed.** See §4, including the settling experiment.
4. **The full `ci/tests` sweep is NOT-CHECKED here.** Prior rounds measured 4 Windows-only
   failures at parent commit `96362031` that reproduce with an empty tree and are not this
   lane's. I ran the 8 suites that touch what I changed.
5. **G8** — full `validate-all-skills.ps1` over 337 skills NOT-CHECKED (>60 s, needs `longrun`).
6. **Scope widened deliberately, twice:** into `commands/` (the lane charter's own exemplar
   defect is `commands/rollback.md`, and all genuine findings live there) and into `ci/tests/`
   (this lane's own gate, precedent recorded in BUILD-R3 §7.6). No sibling owns either file;
   both were clean before the edit.