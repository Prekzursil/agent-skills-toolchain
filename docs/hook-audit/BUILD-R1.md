# HOOKRESEARCH — BUILD lane, round 1

Round 5 was a grounding lane and wrote no production code. This round builds. Everything below
was executed on this box today; every number has a re-runnable command and every detector has a
control that was made to FIRE on a known-broken state before its silence was allowed to count.

Artifacts (all in `command-center/hook-audit/`):

| file | what it is |
|---|---|
| `hook_predeploy_gate.py` | the gate the repo→live hook deploy has never had — 4 axes + 2 lints |
| `test_hook_predeploy_gate.py` | 53 tests, all of them regressions for a defect measured here |
| `_b3_mutation_control.py` | 12 mutations, each a defect actually made while building the gate |
| `_b1_direction.py` | the exact direction classifier for the 12 drifted wired hook bodies |
| `_b4_posttool_block.py` | half A of the per-edit-check settling experiment |
| `B1-DIRECTION.json` `B2-PREDEPLOY.json` `B3-MUTATION.json` `B4-POSTTOOL-BLOCK.json` | evidence blobs |

---

## 1. P0 — SETTLED: all 12 drifted wired hook bodies are DIVERGED

Round 5 measured that 43 of 235 shared hook files differ and 12 of those are wired, then
deliberately stopped: byte counts, def-name sets and mtimes cannot tell REPO-AHEAD (a clean
upgrade) from DIVERGED (both sides hold unique content). It rated that question UNCERTAIN
(20-55%) and refused to convert it into a recommendation. Correct call.

`_b1_direction.py` settles it by line-set membership — the exact algorithm, because
fan-out-contract C4 measured six Opus agents doing this classification by judgement, scoring 86%,
with **100% of the 47 errors pointing at data loss**: every one a DIVERGED file read as
deploy-safe, because a one-directional read cannot see two-directional divergence.

**Result: 12 of 12 DIVERGED. Zero REPO-AHEAD, zero LIVE-AHEAD, zero EQUAL.**
<!-- cite: id=R1-dir-n file=B1-DIRECTION.json path=files_read value=12 -->
<!-- cite: id=R1-dir-div file=B1-DIRECTION.json path=summary.DIVERGED value=12 -->
<!-- cite: id=R1-dir-disp-r file=B1-DIRECTION.json path=rows.0.repo_only_lines value=91 -->
<!-- cite: id=R1-dir-disp-l file=B1-DIRECTION.json path=rows.0.live_only_lines value=129 -->
<!-- cite: id=R1-dir-hs-r file=B1-DIRECTION.json path=rows.4.repo_only_lines value=90 -->
<!-- cite: id=R1-dir-pec-r file=B1-DIRECTION.json path=rows.7.repo_only_lines value=211 -->

| hook | repo-only lines | live-only lines |
|---|---|---|
| `_dispatch/dispatch.py` | 91 | **129** |
| `honest-signal/check.py` | 90 | **90** |
| `wire-check/check.py` | 118 | 17 |
| `memory-spool/flush_check.py` | 23 | 9 |
| `no-force-push/hook.py` | 32 | 8 |
| `git-hygiene/check.py` | 54 | 6 |
| `background-digest/reader.py` | 45 | 6 |
| `codex-monitor-autolaunch/check.py` | 79 | 4 |
| `semantic-router/route.py` | 6 | 4 |
| `workflow-monitor-autolaunch/check.py` | 16 | 2 |
| `per-edit-check/check.py` | 211 | 1 |
| `test-tamper-guard/guard.py` | 26 | 1 |

**Consequence for the deploy plan.** `HOOK-MANIFEST-DRIFT.md` concludes "deploying repo→live is
SAFE … nothing live would be lost". That conclusion is CONFIRMED **for manifest entries** and is
not refuted. It must not be generalised to the trees: `ROLLBACK-DEPLOY-PLAN.md` Step 1 says "copy
… the two hook trees if absent", which is safe for the *absent* case it names, and a wider tree
copy would delete live content in **every wired hook it touched**.

**Not everything DIVERGED is equally alarming, and the gate says so.** Line-set membership
over-reports a refactor: extracting a block into a helper makes the same behaviour read as both
repo-only and live-only. So the gate adds a second, mechanically different measure — *capability
markers* (env vars read, path literals, regexes, count of blocking exit-2 sites) — which survive
reformatting and renaming. Marker loss across the 12:

- **`_dispatch/dispatch.py` loses `ENV:HOOK_DISPATCH_WALL_CAP`** — a wall-clock cap knob the live
  dispatcher has and the repo version does not. Real capability, real loss.
- **`wire-check/check.py` loses two symbol-detection regexes.**
- **`semantic-router/route.py` loses a `.claude` path literal.**
- The other nine lose no hard marker — consistent with a refactor, not a rewrite.
- **Both blocking security hooks keep their gate**: `no-force-push/hook.py` and
  `test-tamper-guard/guard.py` each hold exactly **1** exit-2 site in *both* trees, read directly
  from source. Whatever else the refactor did, it did not disarm them. Confidence ALMOST CERTAIN
  (90-99%).

UNVERIFIED, inline: marker parity is not behavioural equivalence — nine hooks losing no *marker*
is evidence against a rewrite, not proof the refactor is correct. Settling experiment: run each
repo-side hook and its live counterpart against the same recorded payload and diff stdout/exit.
That is a round-2 item; it is not needed to make the deploy decision, because the decision is
already "do not bulk-copy".

## 2. P1 — /rollback: the promise is now a FAILING GATE, and re-confirmed dark two ways

`commands/` is outside this lane's file scope, so `commands/rollback.md` was **not edited**. What
was missing was not another description of the gap — a costed deploy plan already exists — but a
way for it to *fail* instead of sitting in a document for 27 days. Axis P does that.

Two independent signals, AND-gated (a config read alone is not enough — see §6):

1. **Config:** `edit-checkpoints` is declared in the repo manifest and wired in **neither** live
   registry (live `_dispatch/manifest.json` nor live `settings.json`).
2. **Behaviour:** `~/.claude/checkpoints/` holds 502 files whose newest write is **642.2 hours =
   26.8 days** old.

Axis P now fails on four commands that point a reader at a dead artifact:

| command | artifact | state |
|---|---|---|
| `commands/rollback.md` | `~/.claude/checkpoints` | last written **26.8 days** ago |
| `commands/loop-start.md` | `~/.claude/plans` | last written **37.6 days** ago |
| `commands/checkpoint.md` | `~/.claude/checkpoints.log` | **does not exist** |
| `commands/orchestrate.md` | `~/.claude/plan` | **does not exist** |

Each message states the load-bearing fact (the dead artifact) and explicitly labels the
hook-name pairing as document-scoped, because that pairing is the weaker inference.

**Handoff, one line, ready to apply by whoever owns `commands/`:** amend
`commands/rollback.md`'s opening sentence so it stops asserting that the `edit-checkpoints` hook
"snapshots the pre-edit state once per turn" — today it does not. Option (c) of the existing plan
is the zero-latency honest default; if (a)/(b) is chosen instead, option (b) is CONFIRMED
feasible (the vendor evaluates `if` on PreToolUse). The gate fails either way until one is done,
which is the point.

## 3. P3 — SETTLED BY EXECUTION: per-edit-check's `return 2` does not prevent the write

Round 5 rated this LIKELY (55-80%) and refused to act on it, having read the vendor doc but not
run the experiment. It named the experiment. Here it is, in two halves.

**Half A — does the detector discriminate?** (`_b4_posttool_block.py`, feeding the *live* hook a
synthetic PostToolUse payload.) Without this, an rc of 2 could just mean "this hook always
returns 2", and half B would be unreadable.

| state | rc | message |
|---|---|---|
| credential shape, no placeholder marker | **2** | `BLOCKED: AWS access key ID on line 1 …` |
| same shape **with** an adjacent marker | 0 | silent |
| no credential shape | 0 | silent |

It discriminates across all three states. It also, in every case, left the file it objected to
**on disk** — the hook has no power to unwrite anything.
<!-- cite: id=R1-b4-rc2 file=B4-POSTTOOL-BLOCK.json path=cases.0.returncode value=2 -->
<!-- cite: id=R1-b4-exempt file=B4-POSTTOOL-BLOCK.json path=cases.1.returncode value=0 -->
<!-- cite: id=R1-b4-clean file=B4-POSTTOOL-BLOCK.json path=cases.2.returncode value=0 -->
<!-- cite: id=R1-b4-disc file=B4-POSTTOOL-BLOCK.json path=controls.detector_discriminates value=True -->
<!-- cite: id=R1-b4-survived file=B4-POSTTOOL-BLOCK.json path=controls.A1_file_survived_the_block value=True -->

**Half B — the real tool call.** A credential-shaped placeholder was written to a scratch path
via the actual Write tool. The harness surfaced the hook's stderr as a "hook blocking error".
The file was then measured on disk:

```
EXISTS_AFTER_BLOCK = True
bytes = 199
contains the credential SHAPE = True
```

Two independent signals that the write was not prevented: the Write tool's own success receipt,
and the bytes on disk with the shape intact. The fixture was deleted immediately after
measurement, and nothing real was ever written — the literal is assembled at runtime in the
probe so this repo contains no credential-shaped string (verified by a grep whose positive
control fires and negative control does not).

**Verdict, promoted from LIKELY to ALMOST CERTAIN (90-99%) with an executable receipt:**
`per-edit-check/check.py` is wired only at PostToolUse, where the tool has already run. Its
`return 2` and its own comment `# Hard block: Claude Code reads STDERR on exit 2` describe
prevention; what it delivers is after-the-fact feedback. **Correctly scoped: as an injector it
works, and it worked on me repeatedly during this session** (it caught a live F821 in this very
gate, twice). The defect is that a security-relevant path is coded and documented as prevention
while positioned where prevention is impossible — the secret reaches disk either way.

The fix is a one-line repositioning of the secret gate to PreToolUse (`deny-credential-reads`
already blocks successfully there and is the model), or an honest downgrade of the comment and
the return. That edit is in `hooks/**`, which this lane must report before touching — **reported
here, not made**, because it changes a security hook's behaviour and the two trees are DIVERGED
(§1), so the repo edit and the live edit are different edits. Round 2 should make it once the
direction question in §1 is closed.

## 4. P4 + P5 — the pre-deploy gate exists and fails

`command-center/hook-audit/hook_predeploy_gate.py`. It cannot run on a GitHub runner (axes B/C/D
read `~/.claude`), so it is a **local** pre-deploy gate; `check_citations.py` remains the
CI-shaped sibling. Runs in **3.7 s**.

| axis | what it compares | current finding |
|---|---|---|
| A | manifest entries, both directions | 2 WARN — `edit-checkpoints`, `mcp-liveness/pretool` declared, not deployed |
| B | wired script bodies, direction | **12 HAZARD** (the §1 table), 14 WARN, 16 INFO |
| C | capability markers lost on deploy | **3 HAZARD**, 5 WARN, 9 INFO |
| D | `settings.json` hooks surface | **1 HAZARD** — a repo→live settings deploy DELETES the whole `SessionEnd` event |
| L1 | `if` on a non-tool event | 0 (nothing uses `if`; this is a tripwire for the first author who does) |
| L2 | check timeout above its event ceiling | 2 WARN (round 4's finding, now non-regressing) |

`SUCCESS/FAILED` terminal state, `--json` for the blob, exit **2** on a control failure, **1** on
any hazard, **0** clean. Current: **exit 1, 20 hazards of 71 findings.**
<!-- cite: id=R1-pd-live file=B2-PREDEPLOY.json path=stats.live_manifest_checks value=25 -->
<!-- cite: id=R1-pd-shared file=B2-PREDEPLOY.json path=stats.shared_files value=235 -->
<!-- cite: id=R1-pd-div file=B2-PREDEPLOY.json path=stats.direction_tally.DIVERGED value=42 -->
<!-- cite: id=R1-pd-wired file=B2-PREDEPLOY.json path=stats.wired_scripts value=45 -->
<!-- cite: id=R1-pd-liveev file=B2-PREDEPLOY.json path=stats.live_settings_events value=20 -->
<!-- cite: id=R1-pd-repoev file=B2-PREDEPLOY.json path=stats.repo_settings_events value=19 -->

**Fail-closed is load-bearing, not decoration.** Point the gate at an unreadable live tree and it
exits **2** naming the control that fired — it never reports clean because it could not measure.
That is the direct descendant of this program's four-probe false-parity episode.

## 5. Evidence that the tests are worth anything

53 tests pass — which on its own proves nothing. `_b3_mutation_control.py` re-introduces 12
defects that were **actually made while building this gate** and requires the suite to go RED for
each. **12/12 CAUGHT.** Three did not, at first:
<!-- cite: id=R1-mut-n file=B3-MUTATION.json path=mutations value=12 -->
<!-- cite: id=R1-mut-caught file=B3-MUTATION.json path=caught value=12 -->
<!-- cite: id=R1-mut-survived file=B3-MUTATION.json path=survived value=0 -->
<!-- cite: id=R1-mut-na file=B3-MUTATION.json path=not_applied value=0 -->

- **M5** — making a control unfalsifiable survived, because the fail-closed test asserted only
  that the control's *name* appeared in the output. It prints either way; a *different* control
  was carrying the exit code. Now the test asserts `C9_…=FAIL`.
- **M6** — leaking the whole command line survived, because the leak test used a command ending
  in `.py` and returned from the loop, never reaching the fallback. **The dangerous path was the
  untested one.** Now both branches are tested.
- **M9** — the first version dropped the CRLF normalisation and survived. That was **not** a test
  hole: `rstrip()` on the next line already removes the trailing CR, so the mutant is
  EQUIVALENT — measured directly, both variants return identical line sets. Reporting an
  equivalent mutant as a test hole would have sent the next reader to patch correct tests, so
  the case was re-pointed at `rstrip`, which is what actually carries the behaviour.

## 6. Corrections made before publishing (recorded, not deleted)

Six, all caught by running the thing rather than reading it:

1. **The gate's `wired` set came from the manifest alone**, scoring `no-force-push/hook.py` and
   `test-tamper-guard/guard.py` as unwired — it under-reported exactly the two files whose loss
   matters most. Both are registered directly in `settings.json`. Wiredness is now the union of
   both registries.
2. **Then wiredness was taken as the union across both trees**, and the gate printed "the live
   harness runs this file" about `mcp-liveness/liveness.py`, which is declared in the repo
   manifest and deployed nowhere. The denominator must be what runs *today*.
3. **A regex was classified as a lost PATH** — `_PATHISH` matched any backslash, so
   `(?:def|class)\s+` read as a path. A label the reader can see is wrong discredits the true
   findings beside it. Regex is now tested for first.
4. **Axis P fired on the config signal alone and produced a false positive it could not have
   caught by reading itself**: `commands/sentinel.md` names `event-ledger`, nothing under
   `hooks/event-ledger/` is wired live, and `~/.claude/event-ledger/` is **1.0 h fresh** — some
   other wired hook writes it. Inferring the producer from a directory-name match is
   use-vs-mention in new clothes. Axis P now AND-gates config with a behavioural staleness probe,
   and that case is a permanent regression test.
5. **The staleness probe walked a FILE and reported it absent** — it called
   `~/.claude/settings.json` "produces nothing" about a file that plainly exists. Falsifiable by
   looking.
6. **I read the gate's exit code through a pipe** (`… | head -60; echo $?`) and recorded a 0 that
   belonged to `head`. Every exit code in this document is measured without a pipe.
7. **I ran the check I liked and nearly called it CI.** `ruff check` passed throughout, so I
   committed. The quality workflow runs **both** `ruff check .` and `ruff format --check .`, and
   four of the five new files would have been reformatted — a red `gate-lint-format` job on
   shared main, the exact shape that red-blocks every sibling lane. Fixed in a follow-up commit.
   Local ruff is 0.15.17, the same as the CI pin — *verified*, not assumed, because a local green
   against a different version proves nothing about the LF blob CI checks out.
   One non-cosmetic consequence: the formatter split `axis_manifest(report)  # comment` across
   three lines, breaking `_b3_mutation_control.py`'s M10 anchor. The harness reported
   `NOT-APPLIED` instead of a misleading `SURVIVED`/`CAUGHT` — that fail-closed branch earned
   itself on its first real use. Re-verified after formatting: same 20 hazards of 71, 53 tests,
   12/12 mutations.

One more, worth its own line because it was a *wrong inference I nearly published*: the
`SENSITIVE ARTIFACT REPORT` hook fired five times with an identical `sha256:ee4704cabe65` across
edits that changed the file's content, and I formed the hypothesis that the id was not
content-derived — a detector failure. It then fired with a **different** id on a different file,
which refutes that. The stable id is consistent with a stable matched artifact (the test fixture
retains `ANTHROPIC_API_KEY` as a *key name* across every edit). **Corrected before publishing.**

## 7. False-positive sources named this round, with fixes

DoD-4 was already met by round 1's three fixes (cp1252 silent-empty, `IGNORECASE` path/Path,
untracked scratch). These are additional, all measured here:

| source | why it misfires | fix |
|---|---|---|
| `SENSITIVE ARTIFACT REPORT` on a test fixture | fires on the key *name* `ANTHROPIC_API_KEY` in a security regression test, and re-fires on every subsequent edit of the same unchanged artifact | dedupe by artifact id per session — it already computes one; five identical notices for one artifact is the noise this audit's own axis warns about |
| per-edit-check secret gate on a placeholder | correctly exempt only when a marker sits within 24 chars; a fixture whose marker is on another line still blocks | worked as designed here; noted so the next author writes the marker adjacent |
| axis P config-only inference | see §6.4 | shipped AND-gated with a behavioural probe |
| body-drift report volume | 42 DIVERGED files at one severity trains the reader to ignore all of them | severity ladder: wired → HAZARD, unwired code → WARN, `test_*` and data/state files → INFO |

## 8. DoD status

| DoD item | verdict |
|---|---|
| every wired hook timed against its budget | **PASS (prior art, rounds 1-4)** — `H4-TIMING-live.json`; round 1's table was withdrawn in round 4 and only the corrected values are citable. Not re-measured here, and not claimed as mine. |
| inert hooks proven inert by a fired probe | **PASS** — prior art fired 5 to prove inertness; this round adds an executed both-states probe on the live `per-edit-check` (§3) and on `~/.claude/checkpoints` (§2). |
| /rollback producer gap resolved or a deploy plan written | **PASS** — plan already existed; this round adds a failing gate so it cannot stay quietly broken, and re-confirms it dark by two independent signals. The `commands/` edit is handed off, not made (out of file scope). |
| false-positive sources named with a fix | **PASS** — §7, four new sources with fixes; three shipped in code. |

## 9. What round 2 should do, in order

1. **Do not bulk-copy the hook trees.** §1 is the reason. If a specific hook must be deployed,
   deploy that one file after reading its diff, and run the gate before and after.
2. **Reposition per-edit-check's secret gate to PreToolUse** (or downgrade its "Hard block"
   comment and `return 2` to an honest inject). §3 gives the measured premise. `hooks/**` edit —
   report first.
3. **Close the `SessionEnd` settings hazard** before anyone deploys `agent-self/config/settings.json`.
4. **Wire `check_citations.py` into CI.** Still 0 workflow files. `quality.yml` is shared with
   every sibling lane and is the file that red-blocked main — coordinate before editing.
5. **Behavioural equivalence for the 12 DIVERGED bodies** — the settling experiment in §1.

---

### Re-run everything

```bash
python command-center/hook-audit/hook_predeploy_gate.py --json command-center/hook-audit/B2-PREDEPLOY.json
python -m pytest command-center/hook-audit/test_hook_predeploy_gate.py -q
python command-center/hook-audit/_b3_mutation_control.py
python command-center/hook-audit/_b1_direction.py
python command-center/hook-audit/_b4_posttool_block.py
```
