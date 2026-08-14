# HOOKRESEARCH — BUILD lane, round 2

Round 1 of this build lane shipped `hook_predeploy_gate.py` and settled P0/P1/P3-premise. Its §9
left five items. This round works that list, and opens with something none of the five predicted.

Four commits: `2a139b87` · `0e2370be` · `7ccaa24b` · `0d040fff`.

---

## 1. Unplanned and urgent: CI's format gate was RED on main, and the blob gate could not see it

Not on any round's list, found while checking whether my own new files would pass CI.
`ruff format --check .` — one of the two commands `gate-lint-format` runs — fails on
`command-center/hook-audit/_g5_vendorcaps.py`, committed unformatted by `bac65640` (round 1 of
this lane). Its own follow-up `c2ab418f` reformatted the files its author knew about and missed
this one. Round 1 §6.7 records that near-miss as *caught*; one file survived it.

**Why nothing caught it is the more useful half.** `_r4_blobgate.py` does the hard part
correctly — staged blobs, the committed `ruff.toml`, both-states controls — but walks a
**hardcoded eight-entry `PATHS` list**. A file committed outside that list is not *clean* to it,
it is **invisible**. That is the same shape as `check_citations`' own H4 hole, where a number
carrying no `cite:` marker was not unbacked but unseen. The blob gate reported GREEN throughout.

`_b9_format_tracked.py` replaces the hand-maintained list with a **derived** one: every tracked
`*.py` plus every tracked ruff config, materialised from the index with a single
`git cat-file --batch` and checked with the pinned ruff. Blobs, not the worktree — a Windows tree
is CRLF, git stores LF, CI checks out LF (windows-shell §8b).

<!-- cite: id=R2-fmt-after file=B9-FORMAT-TRACKED.json path=tracked_unformatted_count value=0 -->
<!-- cite: id=R2-fmt-files file=B9-FORMAT-TRACKED.json path=controls.C3_files value=2595 -->
<!-- cite: id=R2-fmt-c4 file=B9-FORMAT-TRACKED.json path=controls.C4_config_parity value=True -->
<!-- cite: id=R2-fmt-cfgn file=B9-FORMAT-TRACKED.json path=controls.C4_configs value=16 -->
<!-- cite: id=R2-fmt-before file=B9-CRLF-SPLIT.json path=genuinely_unformatted.0 value=command-center/hook-audit/_g5_vendorcaps.py -->

| state | offenders | files measured |
|---|---|---|
| before the fix | 1 (`_g5_vendorcaps.py`) | 2,593 |
| after `ruff format` | **0** | 2,595 |

### 1b. My own probe reported 5 offenders and 4 of them were innocent

Recorded, not quietly fixed, because the shape is this program's most repeated failure. The
first version materialised only `*.py` + the **root** `ruff.toml`, so
`tools/mcp/patent-search-mcp/{patent_api,server,tests/*}.py` were formatted against settings
that do not govern them — ruff resolves config from the nearest `pyproject.toml` upward, and
that file was not in the temp tree.

**Controls C1, C2 and C3 all PASSED while this was true.** None of them can separate *genuinely
unformatted* from *formatted against the wrong config*; a control that cannot distinguish the
two hypotheses only proves the instrument ran. **C4 (config parity, fail-closed, 16/16)** is the
one that separates them, and with it the probe re-reports 1 offender, agreeing with the worktree
measurement it had contradicted.

What sent me back to the instrument was a **self-contradiction**, not suspicion:
`_b9_crlf_split.py` measured every blob as LF, 0 CRLF, including all four suspects — so a file
cannot be clean under CRLF and dirty under byte-identical LF.

### 1c. OPEN, and not mine to fix: three tracked files are unformatted again

`command-center/mcp-audit/{_b1_redproof_backend,backend_map,render_table}.py`, committed by a
sibling lane *while this round was running* — the new gate caught it within minutes of existing.
Out of this lane's file scope and that lane is actively committing, so it is **reported, not
edited**. `gate-lint-format` is red on main until someone runs
`ruff format command-center/mcp-audit/` (semantics-preserving; verify with
`python command-center/hook-audit/_b9_format_tracked.py`).

## 2. Item 4 — `check_citations.py` is wired into CI · DONE

Round 4 called this the single highest-value follow-up; round 5 re-measured it as still 0
workflow files. **It could not be wired, because it was red**: `check_citations.py` had been
exiting 1 since `bac65640`, and one of the two documents failing it was round 1's own report,
which carried **zero** citations. The per-document floor exists precisely so an unannotated
document is not invisible; nothing was reading its output.

Now: BUILD-R1.md carries 21 citations and `docs/hook-audit/GROUNDING.md` 9, all resolved against
committed evidence. The gate rejected my first marker because the evidence holds `True` and I
wrote `true` — the level of pedantry that makes it worth running.

`GROUNDING.md` and its evidence (`G5-BODY-DRIFT.json`, `_g5_wired.json`, four `_g5_*.py` probes)
were **untracked** — the body-drift measurement this whole round builds on lived on one disk.
Now in git, so the numbers are re-derivable by someone without this working tree. That is the
same failure the gate was built for: `H4-TIMING-live.json` was once cited by a published table
and never committed at all.

**`.github/workflows/hook-audit.yml`, its own file — never `quality.yml`**, which is a closed
gate set policed bidirectionally by `.quality/charter_check.sh` (a `gate-<slug>` marker with no
charter entry turns the existing lint job red). That is the shape `rule-audit.yml`,
`no-runtime-junk.yml`, `skill-dual-write.yml`, `p2next-rail-count.yml` and `mcp-audit.yml`
already use, and it touches no file a sibling lane is editing.

**The second wired command is the one to read.**
`pytest command-center/hook-audit/test_citation_gate.py -q` collects **zero** tests and exits 0 —
it is a standalone script with `main()`, not pytest functions. Wiring it the obvious way would
have installed a permanently green no-op (ci-hygiene §1) directly on top of the gate that exists
to stop that class of thing. Run as `python` it reports 24 cases, ALL PASS.

Verified from a **fresh clone** with `HOME`/`USERPROFILE` redirected to a nonexistent directory,
each child's real exit code captured without a pipe:
<!-- cite: id=R2-ci-green file=B10-CI-PROOF.json path=all_wired_commands_green value=True -->
<!-- cite: id=R2-ci-c1 file=B10-CI-PROOF.json path=controls.C1_redirection_bites value=True -->
<!-- cite: id=R2-ci-c2 file=B10-CI-PROOF.json path=controls.C2_gate_can_fail_in_clone value=True -->
<!-- cite: id=R2-ci-hot file=B10-CI-PROOF.json path=controls.C2_rc_mutated value=1 -->
<!-- cite: id=R2-ci-cold file=B10-CI-PROOF.json path=controls.C2_rc_restored value=0 -->
<!-- cite: id=R2-ci-verdict file=B10-CI-PROOF.json path=verdict value=RUNNER-GREEN -->
4/4 `rc=0`, and control C2 proves the gate **can still fail in that clone** (a mutated citation
→ rc 1; restored → rc 0). Without C2, "green on a runner" is indistinguishable from "cannot fail
on a runner".

**Not wired, each with the measurement behind the reason:** `hook_predeploy_gate.py` (exits **2**
under the same redirection, naming `C9_manifest_reader_plausible` and
`C10_settings_reader_nonempty` — it fails closed, which is correct and also permanently red on a
runner); `probe_hook_fleet.py` (proves inertness by FIRING hooks, two of which launch external
processes and one of which does not terminate); `_b9_format_tracked.py` (duplicates quality.yml's
ruff step); every other probe (reads `~/.claude`).

## 3. Item 2 — per-edit-check's secret reason · DONE, and round 5's finding re-scoped

Round 1 deferred this edit until the repo-vs-live direction question was settled; it settled it
(12/12 DIVERGED), so the edit lands here. **`hooks/**` edit, reported as this lane's scope
requires.**

The reason opened `BLOCKED:` for a write it cannot prevent. per-edit-check is wired only at
PostToolUse; `B4-POSTTOOL-BLOCK.json` measured the file still on disk with the credential shape
intact in every arm, including the one returning 2. An agent told "BLOCKED" concludes the secret
never landed, and *carry on* is the dangerous next move — AGENTS.md §9b is explicit that a secret
is compromised regardless of how briefly it was exposed.

It now opens `SECRET ON DISK`, states that the check runs after the write and cannot unwrite it,
and says to treat the credential as EXPOSED, remove it, and report it to the owner **without
rotating it** — §9 reserves credential lifecycle to the owner, so a hook telling an agent to
rotate would be instructing a banned action.

**Correction to round 5, scoped rather than inherited.** It reported the hook as "coded *and
documented* as prevention". Measured across both trees: the **repo** copy already carries a
correct §6 reconciliation in its module docstring ("exit 2 here is NOT a block … the edit has
already been written"), and the **live** copy contains that text **zero** times while carrying
the `# Hard block:` comment. The documentation half is true of LIVE and false of the repo. What
was real in the repo is narrower and still worth fixing: one inline `# Hard block:` comment on
the **syntax** path contradicted the docstring twenty lines above it, and the inline comment is
the one sitting next to the code the next maintainer edits.

Red first: both new tests FAILED against the unmodified hook (2 failed, 15 passed), then 90
passed across the suite. `test_no_inline_comment_contradicts_the_docstring_reconciliation`
carries a guard assertion so it cannot go inert if the docstring claim it depends on is removed.

**Scope, plainly: this is a REPO fix. Live still runs the DIVERGED copy** (repo 211 unique
lines) and still emits the old wording. Deploying is a separate gated action.

## 4. Item 3 — the `SessionEnd` settings hazard · NOT DONE

Unstarted, not attempted, no evidence produced this round. It is real and still open: axis D of
the pre-deploy gate reports that a repo→live deploy of `agent-self/config/settings.json` would
**delete the entire `SessionEnd` event**, because the repo copy is missing three live-only
entries. Out of this lane's declared file scope (`agent-self/**`). The gate already fails on it,
so it cannot be deployed silently — which is the containment, not the fix.

## 5. Item 5 — behavioural equivalence for the 12 DIVERGED bodies · NOT DONE

Unstarted, not attempted. The settling experiment named by round 1 stands: run each repo-side
hook and its live counterpart against the same recorded payload and diff stdout/exit. It needs a
do-not-fire list first — two of the twelve are autolaunch checks that spawn external processes —
which is why it was not attempted opportunistically at the end of a round.

It is **not** blocking the deploy decision: that decision is already "do not bulk-copy", from
round 1's line-set measurement plus capability markers.

## 6. False-positive sources, this round

| source | observed | disposition |
|---|---|---|
| `SENSITIVE ARTIFACT REPORT` on `test_secrets.py` | fired 3× while editing the secret tests, twice with an identical artifact id | confirms round 1 §7 with a second corpus: the file builds fake credentials at runtime *specifically* so it contains no literal shape, and it is flagged on the key NAME. Dedupe by artifact id per session. |
| `per-edit-check` on my own edits | fired 3× with real defects (a stray `> ` prefix, two `F821`s) and I fixed each | **not a false positive** — recorded because "which hooks are so noisy they are ignored" is one of this audit's axes, and this one earned its interrupt every time |

## DoD status

Round 1 met all four. This round does not re-claim what it did not measure.

| DoD item | verdict |
|---|---|
| every wired hook timed against its budget | **PASS (prior art, rounds 1-4)** — `H4-TIMING-live.json`, round-4-corrected values only. Not re-measured here, not claimed as mine. |
| inert hooks proven inert by a fired probe | **PASS (prior art)** — 5 fired to prove inertness. Nothing added this round. |
| /rollback producer gap resolved or a deploy plan written | **PASS (round 1)** — costed plan plus a failing axis-P gate. Unchanged here; the `commands/` edit remains handed off. |
| false-positive sources named with a fix | **PASS** — §6 adds one confirmed source with a fix, and one explicit non-finding. |

## What round 3 should do, in order

1. **Get `command-center/mcp-audit/` formatted** (§1c) — CI is red for everyone until then.
2. **Item 3**, the `SessionEnd` settings hazard — bounded, and the gate already names it.
3. **Item 5**, behavioural equivalence — write the do-not-fire list first.
4. **Deploy the per-edit-check fix to live**, single file, gate run before and after. Live is the
   copy with the misleading wording *and* no §6 reconciliation.
5. Do **not** bulk-copy the hook trees. Round 1 §1 is the reason.
