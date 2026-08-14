# LANE DOCS — INTEGRATE round 2 (last stage; follows BUILD R8 `f5ca2282`)

COVERAGE: every row in §2 is backed by a command executed this round. NOT measured, and said so
rather than folded into a pass: a real CI run, a Linux run, and the full `ci/tests` sweep. See §6.

> Write-as-you-go marker, kept verbatim: *If it still reads this way, the unit died before
> measuring anything and no verdict here may be cited.* — it does NOT still read that way.

---

## 0. What this round is for

Rounds 5–8 built the DOCS lane's gate and it is genuinely wired: `quality.yml:1503` runs
`ci/tests/test_command_doc_promises.py` inside job `test-python`, on `push: [main]`, and
`ci/tests/test_docs_gate_ci_wiring.py` pins that step against deletion, renaming, weakening and
the py3.12 pivot. I re-measured all of that rather than inheriting it (§2 I2-1). **Nothing about
the existing wiring needed fixing.**

One thing was not wired, and it was the lane's own verdict. Round 8 found two published commands
whose entry points exist nowhere and resolved both as *"ROUTE, not fix-doc … an implement-or-retire
decision for the owner"*. That verdict is right. **The route had no destination.**

---

## 1. Starting state (executed, not assumed)

```
HEAD at entry   e9ec5bd2   branch main   (siblings active; 25 modified + untracked paths, none mine)
gate suite      31 passed, exit 0        ci/tests/test_command_doc_promises.py   py -3.11.9
3 docs suites   56 passed, exit 0        the three the wired step invokes
```

---

## 2. Doc-vs-reality table (integrate round)

| # | claim under test | probe (executed this round) | verdict | resolution + reason |
|---|---|---|---|---|
| **I2-1** | the DOCS lane's gate is reachable on a push to `main` | `git grep` over `.github/workflows` → `quality.yml:1501-1503`; job boundaries put 1503 inside `test-python` (283→1571); `test_docs_gate_ci_wiring.py` pins all three commands | **CONFIRMED, already wired** | **no action.** Re-wiring it would be theatre. |
| **I2-2** | round 8: `scripts/claw.js` is *"ROUTED"* for an implement-or-retire call | `_lane_docs_i2_register_census.py` P3, full-token search over every tracked file: **15 carriers, 0 actionable rows.** Every carrier publishes the broken command, repeats it, is a frozen routing fixture, or is the lane's own build log | **CONFIRMED DEAD *and* UNROUTED** — the route ends in a test-file dict whose only effect is keeping the ratchet green | **FIX CODE.** A register row + a gate arm that fails without it (§3). |
| **I2-3** | same, for `scripts/harness-audit.js` | same probe → 13 carriers. Three hits survived the filter and I **read** each: `docs/audit-design-2026-07-13/A5-doc-registry.json:535` (`status: broken-canonical`), `A5-decision-ledger.json:49` (`D-015`, `BROKEN-PACKAGING`), `phase3-discovery-2026-07-13/reconcile-codex-findings.md:34` | **RECORDED ON 2026-07-13 — a month before round 8 rediscovered it — and still dead.** Nothing reads those files; no gate asserts anything about `status: broken-canonical` | **FIX CODE**, and the reason is sharper than I2-2: *recording is demonstrably not routing.* |
| **I2-4** | the repo's existing dangling-command gate could cover them | imported `check_published_commands.py` and fed its own `CMD` matcher two samples: `node …js` → **0 hits**, `python …py` → **1 hit** | **CONFIRMED python-only**, so neither token can ever reach it | **no action on that gate.** Widening measured, not done — see I2-5. |
| **I2-5** | "just widen that gate to `node`" | same probe P2 over its own corpus (~4,960 tracked `.md`): **22 node invocations, 13 unresolved**, most in other lanes' trees (`dist/index.js`, `ovh-mcp/dist/index.js`, `scripts/postinstall.js`, …) | **REJECTED with a number.** A 13-row cross-lane change | **route, with the measurement recorded** so the next reader need not re-derive it. **First published as 16 — REFUTED by my own second signal, see §6.10.** |
| **I2-6** | round 8: *"a third artifact (the skill) points at the same absent file"* | `grep` across skill roots: `skills/nanoclaw-repl/SKILL.md:9`, `skills/source-command-claw/SKILL.md:19`, **and `skills/autonomous-loops/SKILL.md:130,133`** — plus deployed `.agents/skills/` mirrors | **UNDERSTATED, not wrong.** Three skill families, four invocation sites, not one | **FIX DOC** — the register row names all of them, so a retire decision sees its true blast radius. |
| **I2-7** | my own first register parser judged the right columns | printed the parsed cells instead of trusting the pass: the `harness-audit` row split into **8** cells, so the "owner" check read the *measured* column and the "settling action" check read the *owner* column | **MY OWN DEFECT — a green for the wrong reason** | **FIX MY CODE.** Split on unescaped pipes; control added (§4). |

---

## 3. What was wired in

### 3.1 `docs/DEAD-COMMAND-PROMISES.md` — the register (new, tracked)

A five-column table row per confirmed-dead published command: token · published by · measured ·
owner · settling action. Both rows carry the two independent signals behind them, and the
`harness-audit` row carries the 2026-07-13 prior record, because a register that hides the fact
that the estate already knew would repeat the exact failure it exists to stop.

### 3.2 `ci/tests/test_command_doc_promises.py` — +9 tests (31 → 40)

Two assertions and seven controls. `DEAD` in `KNOWN_UNRESOLVED_INVOCATIONS` now **obliges** a
register row that names an owner and a settling action, in a file that is tracked. It is
**self-retiring**: if the script lands, `paid-debt` fires and the row must go — the same
construction as `command-center/slop-report/published-commands-baseline.json`, for the same
reason (a debt list that can only grow is a mute button).

**No workflow file was touched.** The suite is already wired at `quality.yml:1503`, so the new
arms reach CI without re-opening the shared hazard that red-blocked every PR.

---

## 4. The end-to-end check, and it goes red without the integration

`docs/_lane_docs_i2_bothstates.py` runs the **shipped** pytest arm (not a copy of its logic) in
three states against the real file:

```
FIXED     rc=0  names_the_unrouted_token=False
ABSENT    rc=1  names_the_unrouted_token=True     <- register file deleted
HOLLOWED  rc=1  names_the_unrouted_token=True     <- file kept, rows deleted
restore   before=6a8f96ff9859 after=6a8f96ff9859 ok=True
SUCCESS:docs-i2-bothstates controls=C1,C2,C3,C4-ok
```

The first red proof was cheaper still and came free from TDD: the arm was written **before** the
register existed and run against the real tree — `4 failed, 34 passed, rc=1`, the headline arm
among them. That is red-before/green-after on real bytes, not a synthetic mutation.

| control | H1 | H2 | result |
|---|---|---|---|
| `..._fires_when_a_row_is_deleted` | arm reads ROWS → fires | reads only that the file exists → silent | **PASS** |
| `..._fires_on_a_row_with_no_settling_action` | cells are judged → `no-owner`+`no-settling` fire, `unrouted` does not | row presence is enough → silent | **PASS** |
| `..._a_prose_mention_is_not_a_register_row` | only a table row counts → prose still `unrouted` | any occurrence counts → a paragraph satisfies it | **PASS** — use-vs-mention |
| `..._an_escaped_pipe_does_not_shift_columns` | split on unescaped pipes → owner stays col 4 | naive split → every column shifts right | **PASS** — asserts cell count *and* content, because **both hypotheses produce a passing row** |
| `..._fires_on_a_paid_debt` | resolution re-checked → a row for `scripts/longrun.ps1` fires | row presence is enough → stale row passes forever | **PASS**, both directions |
| `..._parser_is_not_empty` | ≥1 row and ≥1 DEAD token | collapsed → vacuous green | **PASS** |
| `..._is_eol_agnostic` | verdict independent of line endings | CRLF and LF disagree | **PASS** |
| P3 census control | searcher finds the row for the KNOWN-registered `platform/lib/ssot/verify.py` | finds nothing either way → null result measures the searcher | **PASS** — `published-commands-baseline.json:37` |

---

## 5. Evidence (executed; commands and their real output)

```
start            31 passed / 56 passed, exit 0            py -3.11.9 (the CI interpreter)
RED (TDD)        4 failed, 34 passed, rc=1                register absent, real tree
GREEN            40 passed, rc=0                          register present + tracked
3 wired suites   65 passed, exit 0                        (56 before this round)
4 siblings       55 passed, exit 0                        deploy_doc_consistency, rules_doc_coherence,
                                                          command_env_deny_awareness, ci_wiring
both-states      SUCCESS:docs-i2-bothstates fixed=0 absent=1 hollowed=1 restored=True
census           SUCCESS:docs-i2-register controls=ok gate_scope=H1-python-only
                 node_unresolved=13/22 routed=[claw.js, harness-audit.js] unrouted=[]
                 control_ancestor_walk_discriminates=True
                 resolved_only_via_ancestor=[lib/sync-resources.js,
                   scripts/scaffold_node_ext_apps.mjs, uicrit-pack/_test_pack.mjs]
                 ^ a mechanically DIFFERENT instrument (text search over all tracked files,
                   not a table parse) independently agrees both are now routed
node re-derive   tokens=22 unresolved=16(old resolver); basename second signal DISAGREED on 5.
                 3 were genuine false positives, 2 were generic-basename noise. Corrected
                 resolver -> 13. See §6.10.
published-cmds   --self-test 10/10 ok ; real run 407 published commands / 350 documents,
                 1 unrunnable (1 inherited/baselined), 0 NEW, 0 stale rows, exit 0
column check     both rows ncells=7, owner in col 4       (harness-audit was 8 before the fix)
ruff 0.15.17     check exit 0 "All checks passed!" ; format --check exit 0 "3 files already
                 formatted" — exits captured BEFORE any pipe. FIRST run exit 1 ("2 files would
                 be reformatted"); `ruff format` applied, then re-verified.
EOL              test file CR 1270 -> 1269 after reformat (preserved, NOT normalised to 0, so
                 the diff stays scoped); the 3 new files CR=0, so working tree == blob for them
```

---

## 6. Residual, disclosed inline rather than in a footnote

1. **The debt is ROUTED, not PAID.** `/claw` and `/harness-audit` are still published and still
   broken for anyone who types them today. This round makes the debt impossible to lose; it does
   not decide it. Settling action is in each register row and belongs to the owner.
2. **`/harness-audit` was recorded on 2026-07-13 and nothing moved for a month.** The uncomfortable
   reading is that this register could suffer the same fate — which is exactly why it is bound to a
   test that fails rather than to a document that waits. UNVERIFIED [likely 55-80%] that binding it
   to a gate changes the outcome; settling experiment: whether either row is deleted within a month.
3. **No real CI run, no Linux run, and this lane does not push.** Everything is local on the CI
   interpreter (3.11.9). Settling experiment: push and read `gate-tests-coverage (python packages)`
   and `gate-lint-format (ruff)`.
4. **Blob-vs-working-tree for the test file is NOT covered by the ruff run above.** Its working
   tree is CRLF (1269 CR) against an LF blob, so `ruff format --check` on it measured the wrong
   bytes — windows-shell §8b, the exact trap R8 §6.1b was caught by. The blob-level check is run
   after the commit and recorded in §7; the three new files need no such caveat (CR=0, so working
   tree == blob byte-for-byte).
5. **Scope, stated up front rather than left implicit.** This round edits `ci/tests/`, outside the
   lane's declared `docs/**` + `README.md` + `AGENTS.md` + `CLAUDE.md`. Precedent: rounds 3 §7.6,
   5 §8.5, 7 §3.4 and 8 §3.4 all record this lane owning `ci/tests/` for its own gate. An audit
   faulted round 5 for *not disclosing* this, so it is disclosed. `AGENTS.md`, `CLAUDE.md`,
   `README.md`, `.github/workflows/**` and every `commands/**` file are **untouched**.
6. **ONE self-inflicted detector failure, and it would have shipped a false green (I2-7).** My
   first register parser used `split("|")`, which an escaped `\|` inside a markdown cell turns
   into an extra column. The `harness-audit` row parsed to 8 cells and the arm validated the
   *measured* and *owner* columns while believing they were *owner* and *settling action*. It
   PASSED — every cell held prose. Caught only by printing the parsed field instead of trusting
   the pass; this is the manifest-DICT shape, a check agreeing with itself about the wrong
   collection. Fixed, and pinned by a control that asserts cell count **and** content, because
   both hypotheses yield a passing row.
7. **Full `ci/tests` sweep NOT-CHECKED.** Prior rounds measured 4 Windows-only failures at parent
   `96362031` that are not this lane's. I ran the 7 suites that touch what I changed.
8. **A report-only sensitive-artifact notice fired three times** on edits to the test file:
   `sha256:6c638490d83a` — the same id R8 §6.6 recorded for the same file. Surfaced per
   AGENTS.md §9. No credential inspected, printed or modified; almost certainly the
   `GITHUB_TOKEN=$(gh auth token)` example text and `${CLAUDE_PLUGIN_ROOT}` patterns quoted in
   the corpus tripping a heuristic.
10. **A SECOND self-inflicted detector failure, found only because I distrusted my own weakest
   control — and it had already shipped in a commit.** The `16 of 22` node figure in `fd450c9c`
   rested on controls (`corpus_non_empty`, `some_token_found`) that prove only that the extractor
   *ran*; neither could tell a correct classification from a wrong one. That is the
   "a control that cannot distinguish the two hypotheses" shape, in my own probe, one paragraph
   after I cited that rule against someone else. Corroborating each token with a mechanically
   different basename search disagreed on **5 of 16**: three were real false positives caused by
   resolving against the citer's immediate parent instead of its plugin/skill root — **the exact
   root-anchoring error round 8 documented as R8-7**, reproduced in the probe written to check
   round 8 — and two were noise from the generic basename `index.js`, where my resolver was
   right and the second signal was not. Corrected to **13**, the refuted 16 kept visible in both
   carriers, and the ancestor walk now has a control that fails if it is inert. The
   recommendation it supports (do not widen the SLOP gate) is unchanged at 13.
11. **Carried, not mine:** `skill-dual-write.yml` still has no `push:` trigger (INTEGRATE §6.1), so
   a direct push deleting BOTH the `quality.yml` step and the wiring suite is caught by nothing.
   R5-1 half 2 (fresh-install plugin wiring) remains UNVERIFIED, routed to hook-audit. G3
   (rollback edit-checkpoints) still awaits the owner at `docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md`.

---

## 7. Post-commit verification

Commit **`fd450c9c`** — exactly 5 files, +888/-0. No sibling path, no `.github/workflows/**`, no
`AGENTS.md` / `CLAUDE.md` / `README.md` (asserted, not assumed: `git show --name-only | grep -E`
returns nothing). The follow-up commit adds `docs/_lane_docs_i2_cloneproof.py` and this section.

**Blob-level format, the check the working-tree ruff run could not make.**

```
SUCCESS:docs-r7-blobcheck rev=HEAD files=7 blob_format=clean control_fires=True
                          test_command_doc_promises.py:CR=0  (+6 others)
```

`control_fires=True` matters: a mangled copy fails in the same harness, so the green is a
measurement rather than proof that ruff was invoked. The blob is CR=0 while the working tree is
CR=1269 — which is exactly why §6.4 says the working-tree run did not cover this file.

**Shallow-clone proof — the one claim this lane may not assert without evidence.**

The whole finding is that *a register only the author can read routes nothing*. So the register
was checked from outside the tree that produced it, at depth 1 (the `fetch-depth` the hosting job
actually gets):

```
clone_head = fd450c9c   want = fd450c9c   shallow = True   depth = 1
register_in_clone = True      arm_collected = True
arm_rc_present = 0            arm_rc_deleted = 1     red_names_token = True
SUCCESS:docs-i2-clone
```

Arm 2 is what makes arm 1 worth anything. A clone that merely ran green would be equally
consistent with the gate being absent there; only the asymmetry — delete the register inside the
clone and the arm goes red, naming the unrouted token — shows the gate is live on a machine that
is not mine. It also confirms the arm needs no git history, so it cannot fail closed in CI.
