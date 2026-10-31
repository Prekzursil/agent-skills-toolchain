---
title: P2NEXT-BUILD-C5
type: note
permalink: dqverify-repo-20261013/command-center/p2-next/p2-next-build-c5
---

# P2NEXT — BUILD: close the two holes that let a gate certify an unexamined review

**Measured 2026-08-13** against `ast-integrate` (linked worktree of `agent-skills-toolchain`, `main`).

COVERAGE: every claim below is MEASURED and executed; §7 is the complete command list, run in this
session. The skeleton marker this file opened with ("if it still reads this way, the unit died
before measuring anything and no verdict here may be cited") is retired: no section is left at
UNKNOWN. Two things are explicitly NOT measured and are tagged inline in §6.

Naming note: this file is `-C5`, not `-R3` — `P2NEXT-BUILD.md` and `P2NEXT-BUILD-R2.md` are the
earlier rounds' artifacts, and a third round number would collide with the round-2 grounding
document that also calls itself R2. Named by content instead.

---

## 0. What I did NOT do, and why that was the right call

The brief told me to split 48 blocked units, review the satisfiable subset, and count the
rail-blocked remainder. **I did not build any of it, because it is already built and CI-wired.** I
verified that by execution rather than by reading the previous round's prose (§1). Re-deriving a
delivered, gated number would have burned the round and risked moving a figure an owner is meant to
price a decision against.

**I ran no same-vendor review anywhere a receipt demands cross-vendor.** The split exists to keep
those populations apart and it is currently clean: 42 rail-blocked / 10 satisfiable, 0 substitutions.

**I built none of the 449 READY units.** They all name an independent cross-vendor reviewer, so
building them manufactures more un-reviewable work behind a rail that is down.

---

## 1. DoD, verified from COMMITTED blobs (`_c3_dod_verify.py`)

| DoD item | Status | Measurement |
|---|---|---|
| 1. split, with the receipt text quoted per unit | **DELIVERED** | 52/52 units carry a non-empty `reviewer_requirement`; 43/52 also carry `blocked_on`; **52/52 carry at least one operative field**. Control: blanking both fields drops it to 0/52, so the check discriminates. |
| 2. satisfiable subset reviewed and receipted | **DELIVERED** | 10 ids, all `verdict=PASS` + `independent=true`, asserted continuously by `rail_count_gate` C5 — which as of this round also checks the PASS has a review behind it (§3). |
| 3. rail-blocked remainder counted exactly | **DELIVERED — 42 of 52** | Fresh derivation through the shipped resolver; the second, mechanically independent instrument (`split_review_gate.py`, classification tags + catalog requirement) returns the same 42/10. |

**THE BRIEF'S TWO NUMBERS ARE STALE, and I confirmed it rather than assuming it** [almost certain,
90-99%]. The brief says *48 self-declared BLOCKED* and *43 of 47 name cross-vendor*. The committed
truth is **52** and **42 of 52**. `43 of 47` summed **tag occurrences**, counting a receipt with
three review tags three times — the use-vs-mention defect, counting the document instead of the
field. Both are already marked `[superseded]` in `CROSS-VENDOR-RAIL-STATUS.md`, and
`rail_count_gate` C2 fails closed on any unmarked copy of them.

---

## 2. FIX A — `claim_gate` certified a CONFIRMED verdict that declared no measurement

`.agents/skills/claim-verify-gate/scripts/claim_gate.py`

`_check_probes` compared the source and verify probe fingerprints to catch a same-probe re-run, but
never required a `source_probe` to exist. An absent source normalises to four empty strings, which
any non-empty verifier trivially differs from — **so `same-probe-rerun` could not fire, and a
`CONFIRMED` claim declaring no producing measurement returned `violations=[]`, `ok=true`, exit 0.**
That contradicts the skill's own prose and `single-signal-verification.md:75` ("an undeclared source
is zero signals, not one").

**Both-states proof, by the same unmodified probe (`_g4_claimgate_hole.py`), before and after:**

| state | before the fix | after the fix |
|---|---|---|
| A well-formed claim | exit 0 | **exit 0** (no false positive) |
| B identical source/verify probes | exit 1 | **exit 1** (pre-existing detector intact) |
| C **CONFIRMED with no `source_probe`** | **exit 0 — certified** | **exit 1 — `no-source-probe`** |
| the probe's own verdict | `CONFIRMED: the hole is LIVE` | `REFUTED: the hole is already closed` |

B is the load-bearing control: it proves the gate was live in the same run where C was silent, so
C's silence was a real hole and not a dead instrument.

**Why the shipped suite never caught it:** its missing-probe case omits the **verifier**, not the
**source**. 30 tests were green the whole time the hole was open. Added 5 tests for the
absent-source direction, including one asserting the claim is blocked **by `no-source-probe` and NOT
by `same-probe-rerun`** — otherwise the fix would be an accident of fingerprint equality that
evaporates when the verifier changes shape — and one asserting `UNVERIFIED` stays exempt.
Suite 30 → **35 passing**, self-test 10 → **11 rules firing**, mutation probe **6/6 killed**.

---

## 3. FIX B — C5 proved a review HAPPENED, not that it SAID anything

`command-center/p2-next/rail_count_gate.py`

C5 read only `verdict == "PASS"` and `independent is True`. **Emptying every reviewer note across
all ten satisfiable units changed nothing** (`reviewed=10, problems=0`), while flipping a verdict
fired on all ten — so the probe could see failure and the silence was a genuine gap.

A PASS must now also carry notes over a floor **and** name a falsification attempt.

**Both-states proof on the REAL ten, by the unmodified probe (`_g3_c5_content_probe.py`):**

| state | before | after |
|---|---|---|
| A unmutated receipts | 0 problems | **0 problems** — the ten do not regress |
| B **every reviewer note emptied** | **0 problems** | **10 problems** |
| C verdict flipped to FAIL | 10 problems | **10 problems** |

**The floor is calibrated, not invented** (`_c1_calibrate_floor.py`): the ten committed receipts
carry **1,027–2,092 chars**. The floor is **200** — roughly 5x under the observed minimum — because
the risk being defended against is a false positive on a terse-but-real review, not a tight fit to
today's data. The self-test pins that direction explicitly: a ~250-char genuine review must pass,
and a 444-char note of pure agreement must still fail, so the floor cannot degrade into "long enough
is good enough".

---

## 4. REFUTED — the plan's third clause would have failed all ten receipts

The plan asked C5 to also require **"a resolvable evidence anchor"**. Measured before building it:

```
anchors/unit  : min=0 max=1
RESOLVING     : min=0 max=0        <- 0 of 10, every unit
```

**Enforcing it would have turned CI red on all ten existing receipts on its first run** — and the
only fix available to me would have been rewriting ten reviews I did not perform, which is exactly
the independence this lane protects. So it ships **REPORTED AND NOT ENFORCED**: the gate now prints
`ADVISORY (not blocking): 0 of 10 carry a RESOLVING file:line/URL evidence anchor`, so the gap stays
visible to an owner instead of being silently dropped.

**A second reason not to enforce that shape, found by controlling the detector:** the single
anchor-shaped token in the ten receipts is a **timestamp** — `2026-08-12T05:15:00` in AUD-0041 —
which satisfies `claim_gate`'s `\S+:\d+` anchor rule. **So `claim_gate`'s `no-evidence-anchor` can
today be satisfied by a timestamp.** Disclosed, NOT fixed: it is a second behaviour change to a
shared skill in one round, and unlike the source-probe hole it has no measured false-negative in
this repo yet. *Settling experiment:* require the file half of a `file:line` anchor to resolve on
disk, then re-run the claim-verify suite and count false positives on legitimate URL-only evidence.

---

## 5. Two overclaims found in the instruments themselves

Both are the estate's dominant failure shape — the code was right and the **sentence** was wider
than its evidence.

1. **`rail_count_gate`'s header claimed `--self-test` "runs every check against a KNOWN-BROKEN
   input" while C5 had ZERO self-test cases.** That is how a verdict-shaped check survived review.
   C5 now has 7 cases in both directions; total 23 → **30**.
2. **`p2next-rail-count.yml` said "20 cases" while the gate ran 23.** Corrected to 30, with the C5
   gap named in the comment so the next reader learns what was missing rather than just seeing a
   bigger number.
3. **`_r2_blobcheck.py` reported a green that was about the wrong files — caught after my own
   commit.** It carries a HARDCODED `FILES` list (its lines 29-39) naming the round-2 lane's ten
   scripts. Run against this round's commit it still printed `extracted 10 blobs ... All checks
   passed`, and **my commit shares NONE of those ten files**. The tell was the number: "10 blobs"
   happening to equal "10 files changed" is the suspiciously-equal reading that means a control is
   measuring the wrong collection, not that two things agree. Replaced for this round by
   `_c4_blobcheck_mine.py`, which **derives** the file list from `git diff-tree <rev>` (cannot go
   stale), fails closed at zero files, carries `ruff.toml` into the temp tree (without it ruff
   falls back to line-length 88 against this repo's 120 and manufactures a false CI-red), and
   proves itself with a mangled-blob control. Result: **8 python blobs, 0 CRLF, format + check
   both rc=0, control fires.** `_r2_blobcheck.py` is left untouched — it is another round's
   artifact and correct for the files it names.

---

## 6. Residuals, inline

- **UNVERIFIED [likely, 55-80%]** — that a 200-char floor plus falsification vocabulary cannot be
  gamed. It raises the cost of a fake review; it does not make one impossible, and a determined
  author can pad 200 chars containing the word "control". It is a **floor, not a judge**.
  *Settling experiment:* a mutation writing a 250-char plausible-but-vacuous note containing
  "control" and confirming the gate stays green — which it will, and that is the honest limit.
- **UNVERIFIED [uncertain, 20-55%]** — whether the 42 would PASS a Codex review if the rail
  returned. This lane measures what receipts **demand**, never what a review would conclude.
- **NOT-CHECKED** — whether `codex login` clears the `auth.openai.com` agent-registration failure.
  Owner-only credential write (AGENTS.md §9); not attempted, `auth.json` never read.
- **THE CEILING ABOVE THE RAIL, unchanged and still the decisive fact:** all 10 already-reviewed
  units still read `blocked_on_head = "completion condition 11: manifest_registration.registered is
  false"`, and `receipt_schema_gate.py:515-527` hard-rejects `state=SUCCESS` while that flag is
  false. **`codex login` buys review capacity for 42 units and delivers zero of them.** Price the
  two owner decisions TOGETHER; pricing the login alone overstates its value.
- **EXPECTED-RED, DO NOT "FIX":** `rail_count_gate.py --basis worktree` still fails with **14
  problems**, the same count the previous round measured, from the same cause — a sibling lane's
  uncommitted edit flipping `ADV-0041` BLOCKED→SUCCESS, plus `E2E-WAVE-STATUS.md` lines that are
  correct against the committed 42 and wrong against a dirty-tree 41. **My C5 content floor added
  ZERO new problems to that run** (14 before, 14 after), which is the non-regression datum: the new
  check does not fire on the worktree basis either. `--basis committed` is the default and what CI
  runs, and it is green.
- **DEPLOY DRIFT, not mine to resolve:** `claim_gate.py` is edited in the REPO (correct — repo is
  source of truth), so the live copy under `~/.agents/skills/` now differs until a deploy runs. I
  did not run `sync-from-live.ps1` or `sync-skills.ps1 -Prune` (both banned this session).
- **Sensitive-artifact notice** raised by the write hook on `_c2_control_detectors.py`:
  `sha256:f30016f43aa3`, classification POTENTIAL-CREDENTIAL, report-only. The file holds regex
  literals and the example host `https://x.example/a`; no credential. Surfaced per AGENTS.md §9;
  no credential action taken.

---

## 7. Reproduce (every command in this document, in order)

```
python command-center/p2-next/_c3_dod_verify.py            # DoD 1/2/3 from committed blobs + control
python command-center/p2-next/_c1_calibrate_floor.py       # 1027-2092 chars; anchors 0/10 resolving
python command-center/p2-next/_c2_control_detectors.py     # both detectors discriminate, both states
python command-center/p2-next/_g4_claimgate_hole.py        # A pass / B exit1 / C now exit1 -> REFUTED
python command-center/p2-next/_g3_c5_content_probe.py      # A 0 / B now 10 / C 10 -> REFUTED
python command-center/p2-next/rail_count_gate.py --self-test          # 30 cases, both states
python command-center/p2-next/rail_count_gate.py                      # 52 / 42 / 10, green
python command-center/p2-next/vendor_satisfiability.py --basis committed
python command-center/p2-next/split_review_gate.py --basis committed
python .agents/skills/claim-verify-gate/scripts/claim_gate.py --self-test      # 11 rules fire
python .agents/skills/claim-verify-gate/scripts/test_claim_gate.py             # 35 passed
python .agents/skills/claim-verify-gate/scripts/test_claim_gate_mutations.py   # 6/6 killed
uvx ruff@0.15.17 check <changed> && uvx ruff@0.15.17 format --check <changed>
```

All 7 CI-wired steps (4 in `p2next-rail-count.yml`, 3 in `quality.yml`'s claim-verify-gate step)
were run locally and are green. **That is ~7 of ~25 CI steps: a Windows-local green is not CI
green**, and the remaining steps are the ones a shared-tree sibling is most likely to have moved.