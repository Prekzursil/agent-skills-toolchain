---
title: INTEGRATE-R1
type: note
permalink: dqverify-repo-20261013/docs/hook-audit/integrate-r1
---

# HOOKRESEARCH — INTEGRATE lane

**COVERAGE.** Everything below was executed; exit codes were captured without a pipe. What is
NOT measured is named as such in §5 and carries the experiment that would settle it. The one
claim I inherited rather than re-measured is labelled INHERITED in §4.

INTEGRATE has three obligations: make the work **reachable**, prove it with **one executable
check that fails if the integration is missing**, and write the **residual** down inline. This
lane found that the first obligation was the one actually unmet — four rounds had produced a
correct gate that could not see the defect sitting in the flagship deliverable.

## 1. What was wrong, and why nobody caught it

`HOOK-AUDIT.md:197` published **5 dirs INERT-CONFIRMED** and enumerated five, while its
<!-- cite: id=I1-x-inert file=B6-FLEET.json path=inertness.verdicts.INERT-CONFIRMED value=6 -->
evidence file says **6**.
The document's own round-3 addendum, 54 lines below the headline, settles `checkpoint`
as dark on four mechanically different signals and states that "the inert set can include it";
`BUILD-R3.md` cites 6; `GROUNDING.md:28` repeated the 5. So the deliverable disagreed with its
evidence, with itself, and with a sibling document — through a build round, an audit round and a
refute round.

It survived because **no gate could see it**. `check_citations.py` had four rules and every one
of them keys off something this number does not have: a `cite:` marker (H1-H3), or a unit
inside a markdown table (H4). A bolded integer in a sentence was not *unbacked* to the gate, it
was *invisible* — the H4 defect one level down.

That is a claim about a detector, so it is proven with a positive control rather than asserted:
editing the published 5 to a **7** left the gate GREEN, while mutating a CITED number in the
same clone turned it RED. A silence that is silent in both states measures nothing; this one
discriminates, and it says the rule was absent.

## 2. What I wired in

**(a) H5, inside the gate CI already runs.** A line placing an INTEGER within 40 characters of a
VERDICT LABEL must carry a `cite:` marker within 3 lines above or 1 below. It lives in
`check_citations.py`, which `.github/workflows/hook-audit.yml` already invokes, so it needed no
new CI step and cannot be forgotten separately from the gate.

The vocabulary is **derived from the tracked evidence** — any dict named `verdicts` contributes
its keys, any uppercase hyphenated string value contributes itself. A hand-written list rots the
moment a lane adds a verdict. Tracked, not on-disk: a label living only in an uncommitted file is
invisible to a clone, so guarding against it would pass here and fail there.

Scoped **before** it was written, not after. `_i1_verdict_scan.py` measured both candidate shapes
over the whole corpus first: same-line and within-40-characters select the identical 6 lines, of
which 4 were uncited. A floor the corpus can meet, not a flood that trains the reader to ignore
it — which is a finding of this very audit.

Boundaries are strict, **not** `\b`: `-` is a non-word character, so `\bPATH-WIRED\b` matches
inside `MENTIONED-BUT-NOT-PATH-WIRED`, a compound the *document* coined. Firing there would be
counting the document instead of the field.

**(b) A wiring guard, inside the suite CI already runs.** A rule that works and is invoked by
nobody is a producer with no consumer — the defect this audit opened with, and one this gate was
itself guilty of for two rounds while exiting 1. `test_citation_gate.py` now asserts that the
workflow still DECLARES the gate. It parses the `run:` **field**, never the document: the
workflow header mentions `check_citations.py` a dozen times in prose and lists
`probe_hook_fleet.py` under "deliberately NOT wired", so a grep over the file text cannot tell a
wired command from a paragraph about one. `probe_hook_fleet.py` is carried as the control that
makes that difference measurable — present in the text, absent from the steps. Plain text, no
`yaml` import: the workflow installs pytest and nothing else, so a PyYAML dependency would be an
ImportError on the runner, which is the failure shape a wiring guard exists to prevent.

**(c) The evidence two DoD verdicts rest on, put into git.** `H1 H2 H5 H6 H7 H8 H9` were
UNTRACKED — `git ls-files --error-unmatch` said "Did you forget to `git add`", and none existed
in a fresh clone. Two of them are the audit round's anchors for DoD-3 (`H8-ROLLBACK-GAP.json`)
and DoD-4 (`H7-WIRECHECK-FP.json`). They were also named by no `cite:` marker, which is why the
gate never noticed: it can only report "cited but not in git", and nothing cited them. Both DoD
sections are now re-anchored with resolving citations, so if the `/rollback` producer is ever
deployed and the probe re-run, `in_live_manifest` flips and the document goes RED rather than
continuing to describe a gap that has closed.

Tracked with a precheck, not a shrug, since these files read `~/.claude`:
<!-- cite: id=I1-sec file=I1-TRACK-PRECHECK.json path=candidate_secretish_total value=0 -->
**0** credential-shaped strings across all seven (classified by STRUCTURE only, no value ever
printed), and the home-path shape they carry already appears in
<!-- cite: id=I1-home file=I1-TRACK-PRECHECK.json path=already_tracked_files_with_homepath value=7 -->
**7** already-tracked evidence files in the same directory, so this is not a new exposure class.
Four detector controls, both directions, on both matchers.

**(d) The CI proxy coupled to the workflow it claims to model.** `_b10_ci_proof.py` cloned at
FULL depth while `actions/checkout` defaults to 1, so its "4/4 green in a fresh clone" was
emitted under both "runner-green" and "reds on a shallow checkout" — and reality already
refuted it (`e0f5ba1c`: the workflow's first real run failed with `cannot read the pinned
pre-round-3 blob 66855eed4857`). The new proof reads `fetch-depth` out of the same YAML it runs
the commands from, clones through a `file://` URL so `--depth` is honoured at all (a local-path
clone silently ignores it), and carries an arm that proves it is *sensitive* to depth.

## 3. The one executable check — `_i1_gate_proof.py`

It fails if any link in the chain breaks, and each link is a separate arm so a failure names
which one. Fresh `file://` clone at the workflow's declared depth, HOME and USERPROFILE
redirected to a nonexistent directory (control first: the redirection must bite, verified inside
the child process).

| arm | what it proves | want | measured |
|---|---|---|---|
| C | pre-fix docs + PRE-R5 gate blob → GREEN: the hole was real and ungated <!-- cite: id=I1-armC file=I1-GATE-PROOF.json path=arms.C_prefix_docs_prefix_gate_rc value=0 --> | rc 0 | rc 0 |
| D | same docs, one CITED value mutated + PRE-R5 gate → RED: that gate was ALIVE <!-- cite: id=I1-armD file=I1-GATE-PROOF.json path=arms.D_mutated_citation_prefix_gate_rc value=1 --> | rc 1 | rc 1 |
| A | pre-fix docs + SHIPPED gate → RED naming the rule <!-- cite: id=I1-armA file=I1-GATE-PROOF.json path=arms.A_prefix_docs_shipped_gate_rc value=1 --> | rc 1 | rc 1 |
| B | shipped docs + SHIPPED gate → GREEN <!-- cite: id=I1-armB file=I1-GATE-PROOF.json path=arms.B_shipped_docs_shipped_gate_rc value=0 --> | rc 0 | rc 0 |
| E | depth-1 clone → the pinned-blob step FAILS <!-- cite: id=I1-armE file=I1-GATE-PROOF.json path=arms.E_pinned_blob_step_rc_at_depth_1 value=1 --> | rc≠0 | rc 1 |
| F | gate step deleted from the workflow → the suite goes RED <!-- cite: id=I1-armF file=I1-GATE-PROOF.json path=arms.F_suite_rc_when_unwired value=1 -->, restored → GREEN <!-- cite: id=I1-armF2 file=I1-GATE-PROOF.json path=arms.F_suite_rc_when_restored value=0 --> | rc≠0 then 0 | rc 1 then 0 |

Then every command the workflow declares is run in that clone:
<!-- cite: id=I1-wired file=I1-GATE-PROOF.json path=all_wired_commands_green value=True -->
all green, with the gate confirmed present among them
<!-- cite: id=I1-reach file=I1-GATE-PROOF.json path=gate_is_wired value=True -->
(`gate_is_wired`). Overall
<!-- cite: id=I1-verdict file=I1-GATE-PROOF.json path=verdict value=PASS -->
`PASS`.

**Why each control exists, since a control that cannot distinguish the two hypotheses is not a
control.** ARM-C alone cannot separate "the old gate could not see verdict counts" from "the old
gate is dead in this clone" — ARM-D settles it. ARM-A alone cannot separate "the new rule catches
this" from "the new rule fails everything" — ARM-B settles it. The depth assertion alone cannot
separate "this proxy models the runner" from "this proxy would say green either way" — ARM-E
settles it, and it is the exact control `_b10_ci_proof.py` lacked when reality refuted it. The
wiring assertion alone cannot separate "CI declares the gate" from "this test cannot notice an
unwiring" — ARM-F settles it.

**ARM-F caught a live defect in my own guard.** Its first run reported `F_unwired_a_step=true`
and the suite still GREEN: deleting the bare `check_citations.py` step leaves the `--self-test`
step behind, so a single membership test stays green through a real unwiring. The two steps are
not interchangeable — one is the gate, the other proves the gate can fail — and they are now
asserted separately. Without ARM-F the guard would have shipped looking correct.

ARM-F mutates the workflow **inside the clone**, never in the shared worktree: four lanes commit
into this tree and a mutated workflow sitting there for even ten seconds is one `git add` away
from shipping.

**And round 5's regression caught a defect in this proof script.** `_i1_gate_proof.py` wrote its
evidence file on an early-return fail path. That is harmless while the file is untracked and
becomes evidence-destruction the moment it is tracked — a partial stub overwriting the last good
measurement — which is exactly the class `test_failpath_evidence.py` exists to gate. It went red
on `['_i1_gate_proof.py']` the moment I staged `I1-GATE-PROOF.json`, so the tool built to prove
this lane's integration committed the defect a sibling round had already named. The fail path now
prints its reason and writes nothing; 11/11 pass. Two things follow: a wired regression from
another round paid for itself here, and "my probe is fine because it is scratch" stops being true
the instant its output becomes evidence.

## 4. Status of the four must-fix items

| id | state | evidence |
|---|---|---|
| MF1 published count contradicts its evidence, gate blind to it | **FIXED** | ARM-A/C/D above; `HOOK-AUDIT.md:197` now cites 6, refuted wording kept |
| MF2 false "Measured" pytest exit-0 claim | **ALREADY FIXED by round 5, re-measured by me** | `python -m pytest ... test_citation_gate.py` → exit **5**, control `test_hook_predeploy_gate.py` → exit **0** in the same shell |
| MF3 DoD anchors untracked | **FIXED** | 7 evidence files + 8 probes tracked; DoD-3 and DoD-4 re-anchored with resolving citations |
| MF4 CI proxy cannot distinguish the hypotheses | **FIXED for the new proof** | ARM-E; `_b10_ci_proof.py` itself is untouched — see §5 |

Two items the audit carried forward were closed by round 5 before I arrived, and I checked
rather than re-reporting them: the throttle-early-return sweep now covers all 25 rows
(`B11-EARLYRETURN-SWEEP.json`, partition exact, 7 declined-by-matcher / 3 worked / 15 ran-silent),
and the `Stop` event's worst declared check timeout now fits its enforced budget
(`B12-CEILING.json`, `worst_check_fits_enforced` true on all four events).

**INHERITED, not re-measured by me:** the DoD-1 timing table and the DoD-2 firing runs. I
re-read their artifacts and re-ran nothing; my contribution to those two items is that their
numbers are now gated, not that I re-took them.

## 5. Residual — inline, with the experiment that settles each

**The workflow has still never run on a real GitHub runner for this commit. UNVERIFIED.** My
proxy is a fresh clone with a redirected HOME on Windows; Linux-vs-Windows differences are
unmeasured. Settling experiment: its first run on this commit. Confidence that it is green:
**LIKELY (55-80%)** — six commands green in a depth-0 clone is real evidence, and the one thing
that has actually broken this workflow before (a pinned blob missing at depth 1) is now covered
by ARM-E.

**`_b10_ci_proof.py` is unfixed and still says what MF4 faulted.** I built the corrected proxy
alongside it rather than editing it, because it is the receipt for an earlier round's commit and
rewriting it would destroy the record of what that round actually measured. Consequence: a future
reader who runs the OLD proxy still gets a depth-blind green. Settling action (not taken here):
either delete it in favour of `_i1_gate_proof.py`, or leave it with a header pointing at ARM-E.

**H5 does not reach a count published next to a label the evidence does not define.**
`HOOK-AUDIT.md` publishes "**2 dirs came back MENTIONED-BUT-NOT-PATH-WIRED**" — a doc-coined
compound. I cited it by hand, so that instance is now backed, but the *rule* would not have
required it. This is a deliberate boundary (the alternative fires on any sentence containing a
label as a substring, which is the use-vs-mention error). Settling experiment: extend the
vocabulary with labels the DOCUMENTS declare as well as the ones the evidence declares, re-run
`_i1_verdict_scan.py`, and keep the change only if the flagged count stays in single digits.

**H5 is a PROXIMITY rule, and that is a real limit worth stating rather than discovering.** It
requires a `cite:` marker near the line; it does not check that *this* integer equals the cited
value — H1-H3 do the exact comparison, on markers. So a paragraph that quotes a refuted number
next to the correct citation satisfies it (this document does exactly that, one line above §1's
"**5 dirs**"). What H5 guarantees is that a published verdict count cannot sit in a document
with no evidence beside it at all, which is the state that shipped for four rounds. Two
authoring consequences, both measured while writing this: a verbatim quote of a refuted count
must be fenced at TOP LEVEL, because `_strip_fenced` anchors its match at line start and does
not see a fence carrying a `>` blockquote prefix; and a marker two lines below the claim is
outside the window (lookahead is 1), which reads as a false positive until you count the lines.
Settling experiment for the stricter version: resolve the nearest marker's value and compare it
to every integer on the line, then measure how many of the corpus's existing 259 citations that
would newly break before deciding it is affordable.

**Two events' manifest budget mirror still disagrees with the enforced settings** — PostToolUse
15 s vs 25 s, PreToolUse 15 s vs 20 s (`B12-CEILING.json`,
`events_where_mirror_disagrees_with_enforced`). Documented since DoD-1 and still true, so any
"% of budget" quoted from the manifest for those two events uses the wrong denominator. Not
gateable in CI — it requires reading the live `~/.claude/settings.json`. Settling action: add it
to `hook_predeploy_gate.py`, which is the local-only gate that already reads both trees.

**The proof script itself is not in CI, by design.** It clones the repo and reads pinned
historical blobs; running it on a runner would be a self-clone inside a checkout. What IS in CI
is the gate plus the wiring cases, so an unwiring reds the build; the both-states proof stays a
local pre-commit instrument. If that trade is ever judged wrong, the cheap version is a workflow
step that runs only ARM-A against a pinned pre-fix blob.

**Live hook behaviour observed while working, reported not acted on.** The `SENSITIVE ARTIFACT
REPORT` hook fired twice on files I had just written — `_i1_verdict_scan.py` and
`_i1_track_precheck.py`, both probe scripts whose only credential-shaped content is a regex that
*matches* credential shapes. Artifact ids `sha256:c267c61beed9` and `sha256:56d76b54f45b`,
surfaced to the owner per AGENTS.md §9; nothing rotated, revoked or edited. This is a third
independent corpus for the false-positive class DoD-4 names, and it is the same shape the audit
round reported (a test file that *builds* fake credentials flagged on the key name).

Two hooks earned their interrupt in the same session and are recorded so the FP list stays
honest: `per-edit-check` caught a real `F821 Undefined name PRE_R5_GATE_BLOB` the moment I wrote
the H5 cases, and `dup-guard` correctly noticed that `tracked_json` already exists elsewhere in
the repo — a six-line local helper in a different domain, so intentionally separate, but the
nudge was right to fire.