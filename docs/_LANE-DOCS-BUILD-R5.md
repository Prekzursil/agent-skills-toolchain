---
title: _LANE-DOCS-BUILD-R5
type: note
permalink: dqverify-repo-20261013/docs/lane-docs-build-r5
---

# LANE DOCS — BUILD round 5

Docs-vs-reality reconcile. Every row below is an **executed** probe, not a read.

COVERAGE: rows R5-1 … R5-6 are measured. Explicitly NOT measured, and marked `NOT-CHECKED`
rather than folded into a pass: a real CI run; an actual fresh `claude plugin install` of this
repo; a full `validate-all-skills.ps1` sweep. The prior rounds' table (G1–G8, N1–N2) is CLOSED
and is not re-derived here — see `_LANE-DOCS-BUILD-R4.md`.

Starting state, executed before any edit, at HEAD `3b77c575`:
`python -m pytest ci/tests/test_docs_executable_claims.py ci/tests/test_docs_gate_ci_wiring.py
ci/tests/test_command_doc_promises.py -q` → **35 passed, exit 0**.

**HEAD moved mid-round to `b0e3bf98`, and that commit is the owner's, not mine.** It swept my
in-flight `ci/tests/test_command_doc_promises.py` arm out of the shared working tree into an
owner commit *and fixed a real defect in it* — see §6.5. This is the shared-tree hazard the lane
charter names, observed happening **to** this lane rather than **by** it. Consequence for
citation: the gate arm is at `b0e3bf98`; only the doc fix, the lane doc and the probes are in
this lane's own commit.

---

## 1. What shipped

| # | file | change |
|---|---|---|
| 1 | `commands/sessions.md` | Operator Notes bullet: bare `scripts/hooks/cost-tracker.js` replaced with the root it actually resolves against |
| 2 | `agent-self/config/commands/sessions.md` | byte-identical mirror of (1) |
| 3 | `ci/tests/test_command_doc_promises.py` | **new arm** — command-doc PROSE may not assert a repo path that is absent (+7 tests). **Landed via the owner's `b0e3bf98`, not this lane's commit** (§6.5) |
| 4 | `docs/_lane_docs_r5_bothstates.py` | both-states control against the real pre-fix blob |
| 5 | `docs/_lane_docs_r5_probe{,2}.py` | the R4 §4 settling experiment |
| 6 | `docs/_lane_docs_r5_surface.py`, `_prose.py` | the surface measurement that scoped the gate |

`.github/workflows/quality.yml` was **NOT touched** — R4 already wired this file at
`quality.yml:1481`, so the new arm inherits CI reachability. The named shared hazard was not
re-opened this round.

---

## 2. The doc-vs-reality table

Verdict = what the probe measured. Resolution = fix-doc / fix-code / route, with the reason.

| # | claim | probe (executed) | verdict | resolution + reason |
|---|---|---|---|---|
| **R5-1** | R4 §4, tagged UNVERIFIED [55-80%]: `hooks/hooks.json` is live-wired as *this* plugin's entry point rather than an inert vendored snapshot. R4's named settling experiment: does `install.py` deploy it, and does `${CLAUDE_PLUGIN_ROOT}` resolve to the repo root? | **half 1 settled:** `install.py` never names `hooks/hooks.json`; its only hooks target is `~/.codex/hooks.json`. **half 2 structurally confirmed, not observed:** repo root holds `.claude-plugin/plugin.json` (name `agent-skills-toolchain`), whose 6 keys declare **no** component paths, so components resolve by convention; `hooks/hooks.json` sits at exactly that conventional path | **PARTIALLY SETTLED — and the severity is LOWER than R4 framed it** | **route (unchanged), with a corrected magnitude.** See §3. |
| **R5-2** | R4 §4: "24 name `scripts/hooks/*.js`, and all 24 are absent from VCS" | literally true, but the **loader-resolved** surface is **3 distinct** targets — the other references are run-with-flags *label* arguments, not paths the loader resolves | **R4's sentence is ACCURATE; the actionable count is 3, not 24** | **fix the sentence's scope, not the code.** Recorded so the next round does not size the work at 24. |
| **R5-3** | `commands/sessions.md:289` presents `scripts/hooks/cost-tracker.js` as a repo path | absent from VCS (`scripts/hooks` = **0** tracked files) while `scripts/` itself has **86** — so the *parent* is real, which is exactly what makes the reference mislead. Every OTHER reference to that tree in the same document is wrapped in a 3-root runtime resolver (`${CLAUDE_PLUGIN_ROOT}` → `~/.claude/` → ECC plugin cache) | **REFUTED — the bullet is under-qualified relative to its own document** | **FIX DOC.** See §4 for why fix-code is wrong here. Gated by (3) + a both-states control on the real blob. |
| **R5-4** | *(new)* the whole `scripts/hooks/` tree is this repo's missing work | the file's own SessionStart command hunts `~/.claude/plugins/everything-claude-code*` for a root and warns *"could not resolve ECC plugin root"*; 27 files exist live under `~/.claude/scripts/hooks/`; 61 tracked files name `everything-claude-code` | **REFUTED — third-party (ECC) origin, not unreconciled owner work** | **no harness-vcs-hygiene action.** That rule covers live-authored work; importing 27 files of another plugin to satisfy one sentence is the wrong scope. |
| **R5-5** | *(new)* dangling `scripts/...` refs in command docs are systemic and worth a broad gate | **20 bare refs / 16 unresolved, measured at `67137879` — the PRE-FIX parent.** From the fix `5d573583` onward the same probe returns **19 / 15**. Of the 16, **13** sat inside fenced code blocks (invocations against the deployed harness, not claims about this repo). *Correction (round 6): this cell originally read "20 bare refs, 16 unresolved" with no anchor, which reads as CURRENT. That wording was **REFUTED** — an independent audit measured 19/15 at HEAD, and `docs/_lane_docs_r6_pinned_counts.py` reproduced 20/16 at the parent and 19/15 at the fix, from committed blobs, with a parity control. The delta of 1 is exactly the line R5-3 fixed.* | **the gateable surface is PROSE only** | **scope the gate narrowly.** Gating code blocks would fire on every vendored command doc — the false-positive class that gets a gate disabled. |
| **R5-6** | *(new)* the 3 remaining prose refs are all defects | read individually: `sessions.md:289` genuine; `orchestrate.md:204` is `` `node scripts/… plan.json --execute` `` (an invocation); `update-docs.md:18` is the **English phrase** "scripts/commands" in "Extract all scripts/commands with their descriptions" — not a path at all | **only 1 of 3 is a defect** | **no action on the other 2.** Reporting 3 would have been a 3x overclaim; reporting 16, a 16x one. |

---

## 3. R5-1 — what was actually settled, and what was not

R4 asked two questions. The first is now closed; the second is not, and saying otherwise would be
the overclaim this program keeps producing.

**Closed:** `agent-self/harness/install.py` does not deploy `hooks/hooks.json` as an entry point.

**Structurally confirmed but NOT directly observed:** that a fresh install wires dead hooks.
All the preconditions hold — the repo root is a plugin root, the manifest declares no component
paths, and the file sits at the conventional `hooks/hooks.json` location — and the file's own
description records a loader behaviour (*"Codex's plugin-hooks parser … silently loads ZERO hooks
from this plugin"*) that could only have been observed if something loads it. That behaviour is
independently corroborated by the ledger entry of 2026-07-23 (*`hooks.json $schema` made Codex
load ZERO hooks*).

UNVERIFIED [likely 55-80%], inline: **that a fresh `claude plugin install` of this repo would
wire 3 dead plugin-root targets.** Neither ECC nor `agent-skills-toolchain` is currently installed
as a plugin on this box (measured, read-only), so the end state could not be observed.
**Settling experiment:** install the plugin into a throwaway `CLAUDE_CONFIG_DIR` and read whether
the 3 targets resolve. That is a live-harness mutation and is deliberately left to the owner.

**Severity correction, in R4's favour and against my own first framing.** Of the 26 hook entries:
1 is `npx block-no-verify` (root-independent, works); 1 is SessionStart, which carries a fallback
chain and degrades to a stderr warning; the remaining 24 route through **3** distinct absent
targets. So the blast radius is 3 files, and one of the two most-visible entries fails soft.

---

## 4. R5-3 — why FIX DOC, not FIX CODE

The lane charter prefers fixing the CODE when the promise is right and the code is wrong, citing a
charter whose ratchet was fixed in code *"because weakening the doc would make the document true
and the estate no safer."* The discriminating question is whether the fix leaves the estate more
capable or merely more consistent.

Here the capability is **already real and unaffected**: the hook is deployed (27 files measured
live) and does emit the metrics. Only the *path presentation* was wrong. FIX CODE would mean
importing another plugin's 27-file tree into this repo to justify one sentence — which would not
add a capability, would import third-party code under a false provenance, and would leave **22**
equally-referenced siblings behind.

> *Correction (round 6): that figure read "20" and matched nothing measurable. Three candidate
> referents were measured and none is 20 — `hooks/hooks.json` names **23 distinct**
> `scripts/hooks/*` targets across **51** occurrences (so 22 siblings once `cost-tracker.js`
> itself is excluded, which is the number now in the sentence); `~/.claude/scripts/hooks/` holds
> **27** files (26 siblings); `commands/*.md` names **2** distinct such tokens. The regex was
> controlled against a known-absent token (`scripts/hooks/zzz-not-real` -> 0 matches), so the
> zero-arm is not a broken matcher. The argument the sentence makes is unaffected by which of
> these three it meant — but an unanchored number that reproduces to nothing is the same defect
> as the refuted 20/16 above, in the same document, and is corrected rather than left standing.*

The fix also makes the bullet **internally consistent with its own document**, which already
resolves this exact family of paths across three roots:

    - ... the cost metrics emitted by the `cost-tracker` stop hook. That hook ships with the
      deployed harness rather than this repo, so -- exactly like the `session-manager` and
      `session-aliases` requires above -- it resolves at runtime as
      `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/cost-tracker.js`, falling back to `~/.claude/`.

---

## 5. Detector controls — what proves each probe fires when broken

Every control distinguishes **two hypotheses**. A control whose PASS looks identical under both is
inert — the failure this repo measured four times on `manifest["events"][ev]`.

| control | H1 vs H2 | result |
|---|---|---|
| `test_control_prose_claim_fires_on_a_missing_path` | predicate discriminates **vs** always silent | absent path → **fires** |
| `test_control_prose_claim_is_silent_on_a_present_path` | predicate discriminates **vs** always fires | `scripts/longrun.ps1` (asserted present first) → **silent** |
| `test_control_an_invocation_span_is_not_a_path_claim` | whitespace-aware **vs** whitespace-blind | SAME absent file, two spans → bare fires (1), invoked silent (0). A whitespace-blind predicate returns 2 |
| `test_control_fenced_code_is_excluded` | fence-aware **vs** fence-blind | same token inside/outside a fence → **different answers** |
| `test_control_the_arm_is_eol_agnostic` | offset-correct **vs** `\r`-swallowing | LF verdict == CRLF verdict |
| `test_prose_span_extraction_is_not_empty` | real corpus **vs** collapsed-to-zero | floor 150; measured well above |
| `docs/_lane_docs_r5_bothstates.py` | on **real committed bytes**, using the **shipped** predicate | blob `3bfb914d` → **fires once at line 289**; fixed tree → **0** |
| `_lane_docs_r5_surface.py` 3-state | extractor discriminates **vs** collapses | RESOLVES / PREFIXED / ABSENT land in three different buckets |
| `_lane_docs_r5_probe.py` P5 (metaswarm) | resolver discriminates **vs** broken matcher | metaswarm 1 target, **0** absent, while root plugin is 3 absent |

The both-states script imports the predicate **from the gate** rather than re-implementing it — a
probe that re-implements the gate can only ever agree with itself. It is pinned to an immutable
blob sha, not a moving HEAD, so a later commit cannot silently redefine "broken". Its precondition
asserts the blob actually contains the pre-fix sentence; without that it could be comparing the
fixed file against itself.

---

## 6. My own detector failures this round — five, all self-inflicted

Disclosed because the raw numbers would each have been a finding.

1. **P4 (fixture-store natural experiment) was INERT.** It returned `0` on *both* arms and I
   nearly recorded that as evidence. A second probe showed all 83 fixture plugin roots contain
   **only** `.claude-plugin/` — the zero measured fixture shape, not the ecosystem. **Discarded,
   not cited.**
2. **Substring-matched paths (16x overclaim).** v1 of the surface probe anchored on `scripts/`
   anywhere in a path, so `${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py`
   was reported as a missing `scripts/instinct-cli.py`. It also read prose as paths
   (`scripts/hooks/lib.`). Raw **34 → 16** after the fix, and **1** genuine after §2 R5-6.
3. **My own fix introduced a new dangling token.** The first patch wrote *"exactly like the
   `scripts/lib/*` requires above"* — a bare `scripts/lib/` that the prose probe immediately
   flagged. Reworded to name the modules (`session-manager`, `session-aliases`). Caught by
   **running** the probe, not by inspecting the sentence. A tool built to fix a defect class
   committing that class is now a 4th recorded instance in this program.
4. **`RUFF_EXIT=$?` after a pipe read `tail`'s exit**, briefly showing `0` for a
   `ruff format --check` that had actually failed with **6 files would be reformatted**. This is
   verbatim the defect BUILD-R3 §5 already recorded; re-measured with the exit captured before
   the pipe. The real state was fixed, then re-verified `exit 0 / 7 files already formatted`.
5. **A green local suite that would have been RED in CI — my worst error this round.** My arm
   used `Path.read_text(encoding=..., newline="")`, copied from the convention already in the
   file at line 166. That `newline=` kwarg is **Python 3.13+**; CI runs **3.11**. This box runs
   3.14, so all 17 tests passed locally and would have raised
   `TypeError: Path.read_text() got an unexpected keyword argument 'newline'` on the runner. The
   owner caught it in `b0e3bf98` and converted every call site to `io.open(...).read()`.
   Two lessons recorded rather than smoothed over: (a) **copying the file's existing convention
   propagated its bug** — the pre-existing line 166 had the same defect; (b) **`py_compile` is
   blind to it** because it is a runtime `TypeError`, not a `SyntaxError`, so compile-checking is
   not version-checking. I then found the SAME defect in two of my own probes
   (`_lane_docs_r5_bothstates.py`, `_lane_docs_r5_fix.py`), fixed both, and re-verified by
   **executing under the CI interpreter**: `py -3.11 -m pytest … -q` → **17 passed**, and the
   both-states control returns the identical verdict under 3.11 and 3.14.

---

## 7. Evidence (executed, verbatim markers)

```
starting state   35 passed, exit 0        (3 pre-existing docs suites at 3b77c575)
new arm          17 passed, exit 0        ci/tests/test_command_doc_promises.py (was 10)
three suites     42 passed, exit 0
siblings         40 passed, exit 0        test_deploy_doc_consistency, test_rules_doc_coherence,
                                          test_command_env_deny_awareness
both-states      SUCCESS:docs-r5-bothstates broken_state_fires=1 fixed_state_fires=0 blob=3bfb914d
                 blob CR=0 vs tree CR=333 -> EOL-agnosticism exercised on REAL bytes
settling probe   SUCCESS:docs-r5-probe plugin_root_targets_absent=3 control_metaswarm_absent=0
independent      SUCCESS:docs-r5-probe2 fixtures_stub_only=True origin_settled=False
surface          SUCCESS:docs-r5-surface control=3-state-ok bare_refs=20 missing=16
                 scripts_tracked=86 scripts_hooks_tracked=0
                 ^ REFUTED AS WRITTEN (round 6). 20/16 is the PRE-FIX reading, taken at the
                 parent 67137879 before R5-3 landed; this block presented it as the state
                 AFTER the fix. From 5d573583 onward the same probe returns 19/15. The
                 sibling "prose split" line below did disclose its own before/after and this
                 one did not -- inconsistent hygiene inside one evidence block, not a
                 systematic convention. Settled by docs/_lane_docs_r6_pinned_counts.py:
                 SUCCESS:docs-r6-pinned controls=C1,C2,C3-ok pre_fix=20/16 post_fix=19/15
prose split      SUCCESS:docs-r5-prose control=ok prose_missing=2 code_block_missing=13
                 (was 3 before the fix; the 2 remaining are the measured non-defects)
published-cmds   SUCCESS:published-cmds 0 NEW unrunnable (1 inherited)
ruff 0.15.17     check exit 0 "All checks passed!"; format --check exit 0 "7 files already
                 formatted" -- exits captured BEFORE the pipe
CI-VERSION       py -3.11 -m pytest ci/tests/test_command_doc_promises.py -q -> 17 passed
                 py -3.11 docs/_lane_docs_r5_bothstates.py -> SUCCESS, broken=1 fixed=0
                 i.e. the arm and its control were EXECUTED under the interpreter CI uses
                 (3.11.9), not merely under this box's 3.14.6 -- the only detector that
                 finds the runtime TypeError class of §6.5
mirror           commands/sessions.md == agent-self/config/... (sha e9b4adf360b9, identical)
EOL              both files CR=333 LF=333 before AND after; diff = 1 line each
CI wiring        quality.yml:1481 already runs this file (R4). quality.yml NOT edited.
```

---

## 8. Residual, disclosed

1. **No real CI run.** Everything above is local. The commit is not pushed by this lane.
   Settling experiment: push and read the `gate-tests-coverage docs executable claims` step.
2. **R5-1 half 2 is NOT-CHECKED by direct observation** — see §3 for the inline UNVERIFIED tag,
   the band, and the settling experiment. It is routed to hook-audit, not gated red here: a gate
   I cannot keep green is a gate the next lane disables.
3. **`commands/orchestrate.md:204` and `commands/update-docs.md:18` are left alone**, deliberately
   and with the reason measured (R5-6). They are non-defects, not deferred work.
4. **The 13 code-block invocations are out of scope by design** (R5-5), not overlooked.
5. **Scope widened into `commands/` and `ci/tests/`**, continuing the precedent R4 recorded in its
   §7.6. No sibling owns either file; both were clean before the edit. `docs/**` currently holds
   untracked in-flight artifacts from at least three sibling lanes, so the commit uses explicit
   paths only.
6. **Full `ci/tests` sweep NOT-CHECKED here.** Prior rounds measured 4 Windows-only failures at
   parent `96362031` that reproduce with an empty tree and are not this lane's. I ran the 6 suites
   that touch what I changed.
7. **`skill-dual-write.yml` still has no `push:` trigger** — carried forward from INTEGRATE §6.1,
   unchanged and not mine to fix.
8. **This lane's gate arm was not carried by this lane's own commit** — it landed in `b0e3bf98`.
   The bytes at HEAD are the corrected 3.11-safe version and all 17 tests pass there, so nothing
   is lost — but the commit surface of this lane is smaller than its work, and anyone auditing
   "what did DOCS R5 ship" must read `b0e3bf98` as well as this lane's own commit.
   *Correction (round 6): this item originally read "committed by someone else (`b0e3bf98`,
   **owner**)". That attribution is **UNFALSIFIABLE** and is withdrawn — every one of the last 60
   commits carries the single identity `Andrei Mihai Visalon
   <54636077+Prekzursil@users.noreply.github.com>` (`git log -60 --format="%an <%ae>" |
   Sort-Object -Unique` -> 1 row), so no git-metadata signal separates agent-authored from
   owner-authored. What IS falsifiable, and true, is the scoped form now in the heading: this
   lane's own commit action did not produce it.*
9. **The pre-fix blob pin `3bfb914d` remains valid** — but the probe originally cited for it was
   wrong. *Correction (round 6): this item read "`git rev-parse HEAD:commands/sessions.md` still
   returns it". It does not, and it must not: `HEAD:commands/sessions.md` is `df9d9d76` (the
   FIXED blob), while `3bfb914d` is the blob at the parent `67137879`. Had the stated probe been
   true, the fix would not have been at HEAD at all — the sentence contradicted this same
   document's "the fixed line still present at HEAD". The **conclusion** survives on a correct
   probe: `git rev-parse 67137879:commands/sessions.md` -> `3bfb914d`, and that blob contains
   **0** occurrences of the fixed `${CLAUDE_PLUGIN_ROOT}/...cost-tracker.js` line against **1**
   at HEAD — so the both-states control is still comparing against genuinely broken bytes.*