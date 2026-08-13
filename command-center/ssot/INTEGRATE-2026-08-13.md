# LANE SSOT — INTEGRATE round (last stage)

Measured 2026-08-13 in `C:/Users/Prekzursil/source/ast-integrate` @ `main`.
Every number below was produced by a command quoted in this file. Counts are SNAPSHOTS.

COVERAGE: sections 1-6 are measured. Section 5 lists what is NOT done, inline.

## 1. What the prior rounds left unwired

BUILD round 1 shipped three things and made none of them reachable. Its own residual #4 says
so: *"the drift gate is a script, not yet enforced. It must be run by hand."*

| artifact | reachable before this round? | measurement |
|---|---|---|
| `docs/ssot/SSOT-CLONE-INVENTORY.md` (the 25-checkout table + the SSOT rule) | **NO** | nothing in the harness loads `docs/`; the rule existed only where a human would have to go looking |
| `command-center/ssot/ssot_drift_gate.py` | **NO** | no hook, workflow, command or skill invoked it |
| `command-center/ssot/*` receipts | committed, inert | evidence, not enforcement |

A rule nobody reads and a gate nobody runs are indistinguishable from not having done the
work. That is the gap this round closes.

## 2. Integration surface chosen (and why the obvious one is WRONG)

**REJECTED — `rules/common/`.** The obvious home for a standing rule is an always-on rule
file. Measured and rejected, because it would have been a wire that *looks* connected:

```
$p = "C:\Users\Prekzursil\.claude\rules"; (Get-Item $p -Force).LinkType -> (empty)
LIVE  ~/.claude/rules/common/harness-vcs-hygiene.md  2149 bytes
REPO  rules/common/harness-vcs-hygiene.md            3142 bytes
```

`~/.claude/rules` is a plain directory, **not** a junction to the repo, and the live copy is
**993 bytes behind** its repo source. So a repo-only rule edit does not reach a session until
somebody runs a deploy. Writing the SSOT rule there would have produced an integration I
could not honestly claim was live. (The 993 bytes are another lane's hardening — the repo
warns that `sync-from-live.ps1 -Report json` **writes**; the live copy still says it is safe
to inspect with. Out of my scope, reported not fixed.)

**CHOSEN — three wires.**

| # | wire | why it is genuinely reachable | evidence |
|---|---|---|---|
| A | the `<!-- SSOT-WIRE -->` block in the repo-root `CLAUDE.md` | git-tracked AND auto-injected into any session whose cwd is this checkout — **no deploy hop** | this very session's context contained `Contents of C:\Users\Prekzursil\source\ast-integrate\CLAUDE.md`, i.e. observed loading in a live session |
| B | `ci/tests/test_ssot_wiring.py` | `skill-dual-write.yml` runs `python -m pytest ci/tests tools/d001-dual-write/tests -q` — a real tree-wide sweep, read from the workflow itself, not from a comment claiming it | the workflow's `gate-skill-dual-write self-test` step |
| C | an explicit `gate-ssot-wiring self-test` step in `skill-dual-write.yml` | the sweep in (B) is "one refactor away from not containing this file" — the repo's own words, three times in that file | pinned by `test_the_workflow_names_this_suite_explicitly` |

`skill-dual-write.yml` rather than `quality.yml` on purpose. `.quality/charter_check.sh:17`
sets `workflow="$here/.github/workflows/quality.yml"` and scans **only** that file
bidirectionally, so a `gate-` marker there without a matching charter slug turns the existing
lint job red. A step in `skill-dual-write.yml` carries no charter obligation — and `quality.yml`
is the shared file that red-blocked every PR on main tonight.

## 3. The end-to-end proof — one check, shown going red

`command-center/ssot/ssot_wiring_check.py` is the gate. Six wires, each with a paired
mutation. The red-proof does **not** hand-make a broken state: it reconstructs the genuine
pre-integration tree with `git show HEAD:<path>` and runs the same checker over it.

```
$ python command-center/ssot/_integrate_redproof.py
=== BEFORE: reconstructed from 33f3f2d3~1 (4 files) ===
    (absent at that rev, as expected pre-integration: ['command-center/ssot/ssot_wiring_check.py'])
  [CUT ] W1-claude-md-no-ssot-block   CLAUDE.md has no SSOT-WIRE block
            - CLAUDE.md is missing <!-- SSOT-WIRE:start -->
FAILED:ssot-wiring-check cut=1
--> BEFORE exit=1
=== AFTER: the working tree, with the integration applied ===
SUCCESS:ssot-wiring-check wires=6 all intact
--> AFTER  exit=0
DISCRIMINATION: before=1 after=0
SUCCESS:ssot-redproof before=RED after=GREEN, the wire is load-bearing
```

**Remove the integration and the check goes red. That is the whole claim, executed.**

The suite: 16 tests, all green.

```
$ python -m pytest ci/tests/test_ssot_wiring.py -q
16 passed in 4.09s
```

It also makes the drift gate's logic **portable**. The gate's real target is one Windows path
on one machine, so on any other host its verdict was unproven. Four tests now drive it against
a synthetic git repo built in `tmp_path`, covering all four exit codes:

| state | expected | asserted |
|---|---|---|
| executed dir behind the reference | 1 | `FAILED:ssot-drift-gate drift=` + the offending file + `control PASS` |
| at parity | 0 | `SUCCESS:ssot-drift-gate drift=0` |
| HEAD off the reference, every diff legitimately 0 (empty commit) | 3 | `FAILED:ssot-drift-gate detector-broken` — fails CLOSED |
| executed checkout absent | 2 | `executed checkout absent` |

The empty-commit case is a real construction, not a monkeypatch: it puts HEAD off the
reference while every diff is honestly zero, which the gate cannot tell apart from a blind
differ, so it must refuse to certify rather than report clean.

## 4. Detector controls (both states)

Every code was watched firing. Nothing here is a silence.

- **Healthy control** — `test_the_real_repository_is_green`: without it, a permanently-red
  checker would satisfy every mutation below.
- **Scratch-parity control** — `test_the_scratch_copy_is_green_before_mutation`. This one
  earned its place: it caught my own bug. `command-center/ssot/ssot_wiring_check.py` was
  missing from `COPY_PATHS`, so the UNMUTATED scratch copy was already red and four
  exclusivity assertions were measuring noise. Fixed, and the omission is recorded in the
  file rather than quietly deleted.
- **Six exclusive mutations** — W1 block marker removed, W2 sentence reworded, W3 path
  renamed to a dangling one, W4 gate reference swapped for another real path, W5 the gate's
  `__main__` guard neutered, W6 both CI invocations stripped. Each must fire its own code and
  **only** its own code.
- **One deliberately NON-exclusive mutation** — deleting the inventory cuts W2 and W3 at once.
  A rule that only ever fires one code at a time would be hiding one of them.
- **Coverage gate** — `test_every_invariant_has_a_red_proof` fails if a code is added to
  `CHECKS` without a mutation, so a code nobody has watched fire cannot ship.
- **Fail-closed** — `--root` pointed at an empty directory exits **3**, never "all wires
  intact".
- **Mutation-anchor guard** — `_sub()` asserts its anchor exists, so a mutation that silently
  missed cannot masquerade as a passing test.

**A THIRD detector failure — the probe invalidated itself on landing.** `_integrate_redproof.py`
originally reconstructed the BROKEN state from `HEAD`. It passed while uncommitted, and the
instant the integration commit landed it reported:

```
DISCRIMINATION: before=0 after=0
FAILED:ssot-redproof the checker did not distinguish the two states -- it is inert
```

HEAD had moved, so the "control" had silently become a copy of the treatment. That is a
control that cannot distinguish the two hypotheses — committed **by the tool built to catch
exactly that**. Fixed by pinning `BEFORE_REV = "33f3f2d3~1"` (a SHA, not a moving reference),
so the proof reproduces from any later checkout, plus a new fail-closed path: an unresolvable
rev exits **2** with `FAILED:ssot-redproof cannot resolve <rev>` rather than reporting a
passing control. Both verified. The original wording is recorded here rather than deleted.

That run also yields a free line-ending proof: `build()` writes raw `git show` blobs, so the
BEFORE tree is **LF**, and the checker is green over it — i.e. the checker is line-ending
insensitive and will behave on a Linux runner as it does on this CRLF working tree.

**A detector failure I caught in my own instrument.** W4 fired against a `CLAUDE.md` that DID
reference the gate. The path regex required an entire backtick span to be the path, so
`` `python command-center/ssot/ssot_drift_gate.py` `` — an invocation, the commonest way to
name a gate — did not count. I fixed the detector, not the document; the widened rule scans
inside code spans only, so a path merely discussed in prose is still a mention and not a
reference. `mut_w3_dangling_path` proves the widened rule still bites.

## 5. Residual — what is NOT done

1. **This is wired for CI and for a session in THIS checkout. It is not wired into a hook.**
   Nothing runs `ssot_drift_gate.py` on a schedule or at turn-end. A Stop-hook row in
   `hooks/_dispatch/manifest.json` was considered and rejected: hooks only run from
   `~/.claude/hooks`, and a sibling lane measured tonight that a committed hook fix is
   *still not deployed* (`f009c680`). Wiring it there would have been a claim of reachability
   I could not execute. **Settling experiment:** deploy the hook tree, then confirm the row
   fires by watching it emit on a turn where the executed checkout is behind.

2. **`CLAUDE.md` is per-checkout, so a stale checkout serves a stale rule.** An agent that
   opens `~/source/agent-skills-toolchain` (177+ commits behind) reads *that* copy, which does
   not contain this block. The wire is correct for the checkout you are told to edit in, and
   silent in exactly the checkouts the rule warns you not to use. Only a deployed always-on
   rule would cover all 25, and §2 measures why that surface is currently a fake wire.

3. **The drift gate's `EXECUTED_DIRS` is a static list of 5 directories** derived from the 8
   config references in inventory §3. If the fleet starts loading from a 6th directory,
   the gate reports clean and is wrong. Nothing detects that. **Settling experiment:**
   re-run `scan_inbound_refs.py` and diff the resolved directory set against `EXECUTED_DIRS`.

4. **4 pre-existing test failures in the CI sweep, none of them mine.**
   `python -m pytest ci/tests tools/d001-dual-write/tests -q` -> **4 failed, 669 passed, 1
   skipped**. Attributed on two independent signals: (a) zero file coupling —
   `test_check_skill_dual_write.py` references nothing I touched, and the single test that
   reads `skill-dual-write.yml`
   (`test_d1_shipped_instructions_do_not_NAME_the_broad_commands`) PASSES; (b) all four
   assertions are platform-bound — invalid-UTF-8 path bytes, `chmod(0o755)` exec-bit
   regressions, and a shell `git` wrapper — none of which Windows can represent, while CI runs
   `ubuntu-latest`. **UNVERIFIED [likely 55-80%]** that they are green on Linux: I did not run
   them on Linux or in a fresh clone. **Settling experiment:** the next CI run on this branch.

5. **Nothing was deleted and no clone was retired.** The prior rounds' verdict stands: retire
   nothing until `D:/wt-salvage-probe`'s 2 staged files and `_b5-toolchain`'s 3 files are on a
   pushed branch. This round did not rescue them — it is an integration round, not a salvage
   round, and that remains the next action.

6. **`origin/main` moved during this round** (`61e69cf2` at start). Local `main` is ahead with
   sibling commits. Not pushed — pushing was not in scope.

## 6. Commits

See the lane's terminal report. Files touched are listed there, with the two shared files
(`CLAUDE.md`, `.github/workflows/skill-dual-write.yml`) declared explicitly.
