# HOOKRESEARCH round 3 — the gate that was built to stop this had three holes of its own

STATUS: COMPLETE for round 3. Every number below carries a machine-checkable citation to a
**committed** evidence file, and as of this round the checker resolves each one twice — once
on disk and once against `HEAD` — because a worktree-only match is what let round 2's
evidence drift go unnoticed.

COVERAGE — MEASURED here: the three holes in `check_citations.py`, each with the
pre-round-3 gate as its control; the handed-off stub-ledger phantom claim, settled
end-to-end against the live ledger; the `/rollback` producer cost, re-measured with the two
code paths separated and a fail-closed control that the round-1 probe lacked.
NOT MEASURED, stated inline where load-bearing: the round-2 verifier's own confirmed list
(§0 — it did not reach this lane); the 7 launcher entries (unchanged since round 1); the
`~/.agents/harness` plane's internal per-module split; git-hygiene's unthrottled scan against
the FULL default root set.

If a section reads "UNKNOWN - not yet measured", the unit died before measuring anything and
no verdict here may be cited.

---

## §0 — a prompt-input gap, disclosed before anything else

This round was launched with *"a verifier CONFIRMED defects last round; fix those"*, but the
prior-round payload it carried stopped at **round 1** — the round-1 build report and the
round-1 audit. **The round-2 verifier's confirmed list is not in this lane's input**, and
`ROUND2-CORRECTIONS.md` (which answers round 1) was already committed before this round
started, so re-fixing C1–C5 would have been re-litigating what already passed.

What this lane did instead of guessing: re-derived defects by execution against the tree as
it stands, and started from the artifacts the previous rounds left visibly unfinished — two
committed-but-dirty evidence files, three documents the new gate does not cover, and the one
hand-off item round 2 explicitly left UNVERIFIED. Everything below is measured here, not
inherited. **Settling experiment for this gap:** read the round-2 verifier's artifact (this
lane could not locate one on disk; `_verify_hook/VERIFY-SKELETON.md` is the round-**1**
verifier, timestamped 06:34, before round 2's first commit at 07:14) and re-check §R3-1…3
against it. If it confirmed something not addressed here, this round did not close it.

---

## R3-1 — `check_citations.py` had three holes, and the live tree was already in one

Round 2 built this gate because a published number had drifted from its evidence with
nothing watching. The gate shipped with three defects of the same family. Each is closed
here, and each is proven by running the **pre-round-3 gate** against the same fixture and
requiring it to behave the way the defect says it did — without that pairing, "the new gate
is green" would be indistinguishable from "the new gate looks at nothing".

### H1 — it read the working tree, never the shipped blob

`check_one()` resolved every citation with `fp.read_text()`. A clone resolves it with
`git show HEAD:<path>`. Those diverge in exactly one situation — the evidence file is
regenerated after it was staged — **which is the situation that produced C3**. The gate was
therefore blind to the only drift direction that had actually occurred.

Measured, not argued: with `C6-GATE-EVIDENCE-SIDE.json` (a **cited** evidence file) differing
from its own committed blob in four fields, the gate printed `32 citations checked, 0
unbacked / SUCCESS:cite-check`. Every citation is now resolved twice and a divergence is
reported as `EVIDENCE-DRIFT`, naming both values and which one a clone reads.

### H2 — the repo root was a hardcoded absolute path

`REPO = Path("C:/Users/Prekzursil/source/ast-integrate")`. Run from any other checkout, the
gate silently validated **ast-integrate's** documents against **ast-integrate's** evidence
and reported success about files the caller does not have — the same "read the wrong tree and
still say SUCCESS" shape as the blob gate round 2 caught in itself. In the fixture test the
old gate, executed inside a two-file throwaway repo, reports on `ROUND2-CORRECTIONS.md`.
The root is now derived via `git rev-parse --show-toplevel` from the gate's own location,
overridable with `HOOK_AUDIT_REPO`, and **fails closed** if the resolved root does not hold
both expected directories rather than guessing.

### H3 — the zero-citation floor was global, not per document

The fail-closed floor triggered only when the *whole directory* had no citations, so one
annotated file satisfied it for all four. Consequence, live until this commit:
`HOOK-AUDIT.md` (the round-1 deliverable — the document whose tables the verifier faulted)
and `ROLLBACK-DEPLOY-PLAN.md` (which carried the load-bearing deploy number) contained
**zero** citations and passed. The floor is now per-document with an explicit
`NO_CITE_EXEMPT` map that must name a reason.

### The both-states proof

`command-center/hook-audit/test_citation_gate.py`, 14 cases, all pass. The three control
rows are the load-bearing ones:

| case | pre-round-3 gate | shipped gate |
|---|---|---|
| blob says 1.0, worktree says 2.0, doc prints 2.0 | **exit 0 (passes)** | exit 1, `EVIDENCE-DRIFT` |
| run inside a fixture repo | reports on `ROUND2-CORRECTIONS.md` | reports on the fixture's `DOC.md` |
| one annotated doc + one unannotated doc | **exit 0 (passes)** | exit 1, names `UNGATED.md` |
| blob == worktree == doc (CLEAN control) | — | exit 0 |
| evidence untracked (round-2 behaviour) | — | exit 1, `UNTRACKED` |
| `HOOK_AUDIT_REPO` without the two dirs | — | exit 1, refuses to guess |

The CLEAN row is not decoration: without it, a gate that failed everything would score three
out of three on the rows above.

---

## R3-2 — the stub-ledger phantom count: the proposed mechanism is REFUTED

The orchestrator hand-off (`command-center/hook-audit/orchestrator-findings.md` §1) reported
`31 placeholder/TODO(s) … STILL open` naming five files present in none of the nine clones,
and proposed the mechanism *"the ledger records a placeholder at WRITE time and never
re-validates at REPORT time"*, with the fix *"a `Path.exists()` filter at report time"*.
Round 2 carried it forward as N3, UNVERIFIED.

**Measured: the fix is already implemented and demonstrably working, so the mechanism does
not hold.** `report.py:262-278` re-runs the detector on each recorded file's *current*
content and drops a file that no longer exists. `_r3_stubledger.py` states both hypotheses
first and then discriminates them with two independent probes:

* **A, the live ledger, read-only.** Across
  <!-- cite: id=R3-sl-sessions file=R3-STUBLEDGER.json path=probe_a_live.session_files value=12 -->
  12 session files holding
  <!-- cite: id=R3-sl-recs file=R3-STUBLEDGER.json path=probe_a_live.records_total value=446 -->
  **446 records**,
  <!-- cite: id=R3-sl-missing file=R3-STUBLEDGER.json path=probe_a_live.records_pointing_at_absent_file value=120 -->
  **120 point at a file that does not exist now** — and
  <!-- cite: id=R3-sl-surv file=R3-STUBLEDGER.json path=probe_a_live.still_open_survivors_for_absent_files value=0 -->
  **0** of them survive into `still_open()`, the function that builds the message. If the
  hand-off's mechanism were live, that number would be 120, not 0.
* **B, end-to-end, isolated.** Two temp files are driven through the real `record.py`, one is
  deleted, and the real `report.py` runs as a subprocess:
  <!-- cite: id=R3-sl-ctl file=R3-STUBLEDGER.json path=probe_b_e2e.control_kept_file_named value=True -->
  the surviving file **is** named (the control — without it, "the deleted file is absent"
  could just mean nothing was ever recorded) and
  <!-- cite: id=R3-sl-ph file=R3-STUBLEDGER.json path=probe_b_e2e.phantom_deleted_file_named value=False -->
  the deleted file is **not**.

<!-- cite: id=R3-sl-verdict file=R3-STUBLEDGER.json path=verdict value=H_TIMING -->
Verdict **H_TIMING**: the five named files existed when the notice was emitted; the `find`
that returned zero hits ran afterwards. Agent scratch is written, run and removed inside one
turn, so a notice quoting it is stale by the time a human reads it — but the count was true
at emission, and **no code change is warranted**. Two further readings from the same run,
both of which would have been the next thing to blame: records with an empty `file` field
(kept unconditionally, because they cannot be re-scanned) number
<!-- cite: id=R3-sl-empty file=R3-STUBLEDGER.json path=probe_a_live.records_with_empty_file_field value=0 -->
**0**, and the ledger currently emits
<!-- cite: id=R3-sl-emit file=R3-STUBLEDGER.json path=probe_a_live.still_open_emitted_total value=87 -->
**87** still-open records across all 12 sessions.

**What was refuted, kept rather than deleted:** the hand-off's mechanism, and its proposed
fix. Building the `Path.exists()` filter would have been building a second copy of a filter
that already exists — the same shape as round 2's N2, where a `git cherry` guard was *not*
built for a trap that did not reproduce. Residual, disclosed: this settles the *mechanism*,
not every possible phantom. A record whose file is unreadable (not absent) is still kept by
design, on the grounds that unreadable is not proof of resolved; that path is not exercised
here. Settling experiment: make a recorded file unreadable (deny read ACL) and check whether
the notice keeps citing it.

---

## R3-3 — the `/rollback` cost measured the wrong code path, and its own evidence said so

Round 1 published *"cold 5,486 ms / warm mean 2,545 ms = 17.0% of the check budget"* and
concluded the deploy *"charges ~2.5 s to every Edit, Write and MultiEdit"*. Round 2 left it
alone; the round-1 verifier re-ran the probe and got 18.5%, and treated the difference as
variance.

Both readings are of a path that is not the one the sentence describes.
`hooks/edit-checkpoints/checkpoint.py:208-211` keys a snapshot on `f"{turn}|{repo}"` and
returns 0 if that key is already present — **one snapshot per human turn per repo**. The
round-1 probe sent five identical payloads with no `transcript_path`, so all five shared one
turn key: one snapshot and four early returns, whose mean was then published as the per-edit
charge. The contradiction was already in the committed evidence — `index_records: 1` beside
five samples — and went unread for two rounds.

`_b8_rollback_cost.py` now runs the paths as separate phases and **refuses to publish** unless
a control proves they are different paths (one index record per armed call, exactly one for
the whole repeat phase):

| path | when paid | median | max | max % of 15 s budget |
|---|---|---|---|---|
| first edit in a turn (snapshot) | once per turn per repo | <!-- cite: id=R3-b8b-med file=B8-ROLLBACK-COST.json path=first_in_turn_median_ms value=369.2 tol=0.001 -->369 ms | <!-- cite: id=R3-b8b-max file=B8-ROLLBACK-COST.json path=first_in_turn_max_ms value=596.3 tol=0.001 -->597 ms | <!-- cite: id=R3-b8b-pct file=B8-ROLLBACK-COST.json path=first_in_turn_max_pct_of_check_budget value=4.0 tol=0.001 -->4.0% |
| every other edit (early return) | all remaining edits | <!-- cite: id=R3-b8b-sub file=B8-ROLLBACK-COST.json path=subsequent_median_ms value=194.6 tol=0.001 -->195 ms | 271 ms | 1.8% |

<!-- cite: id=R3-b8b-ctl file=B8-ROLLBACK-COST.json path=control_phases_distinguished value=True -->
Control passed. **The correctly-scoped claim:** the producer's cost is dominated by Windows
process spawn and varies with box load — worst samples across three runs of the same probe
are 5,486 ms (round 1, nine lanes mid-wave), 7,428 ms (verifier, same conditions) and 597 ms
(this run, quiet). Quote it as a range, ~0.3 s to ~7.4 s, never as a constant. **The decision
does not move**: even 7,428 ms is 49.5% of the 15 s check budget, so it fits, and the reason
to ask the owner first is the per-turn latency and the growing `git stash` ref namespace, not
the budget.

---

## What did NOT change, and must not be read as fixed

* **Both hook fixes are still repo-only.** Live `~/.claude/hooks/wire-check/check.py` still
  has 0 occurrences of `encoding="utf-8"` and live `git-hygiene/check.py` still has 0
  occurrences of `LIVE_STATE_GLOBS`. The cp1252 false positives and the `accounts.json`
  false positive keep firing every turn until the repo→live deploy step runs. Nothing in this
  round touched the live tree.
* **`edit-checkpoints` and `mcp-liveness/pretool` are still undeployed**, so `/rollback` still
  returns nothing. This round makes the deploy decision better-informed; it does not make it.
* **The repo→live deploy step still has no gate at all.** That single architectural hole now
  accounts for the wire-check fix, the git-hygiene fix, the /rollback producer and the
  round-2 settings drift. `ROLLBACK-DEPLOY-PLAN.md` step 4 remains the proposal.
* **The 7 launcher entries remain untimed** for round 1's reason: firing them spawns IDA,
  Ghidra, monitor TUIs, desktop notifications, or creates/removes a git worktree. Measuring
  their *non-armed* path was considered and rejected as a number nobody can use — in
  production the settings matcher prevents that path from ever being taken. Settling
  experiment unchanged: run them on an idle box with a disposable worktree target.

## One defect this round committed in its own instruments, recorded not deleted

`_b8_rollback_cost.py`'s first round-3 revision reported `warm median 224.6 ms = 1.5% of
budget` — a 10x improvement on round 1 — and it was wrong for exactly the reason round 1 was
wrong: 15 of its 16 samples were early returns. It was caught by reading the probe's own
`index_records: 1` in the output rather than by review, which is the same signal that had
been sitting unread in the committed round-1 file. The two-phase split and its fail-closed
control exist because of that, and the intermediate number is not cited anywhere.
