---
title: LANE-CASUALTY-ROUND2
type: note
permalink: dqverify-repo-20261013/command-center/casualty/lane-casualty-round2
---

# LANE CASUALTY — BUILD ROUND 2 (re-entry after adversarial refutation)

Build round 2, 2026-08-12. Write-as-you-go: rewritten at every milestone; whatever is on disk is
always truthful.

> If a section still reads `UNKNOWN - not yet measured`, the unit died before measuring it and no
> verdict there may be cited.

**COVERAGE at this write:** R2-A DONE · R2-B DONE (5/5 controls, each proven against the pinned
pre-fix blob) · R2-C DONE (8 sentence repairs) · R2-D DONE — and the fresh-clone leg found a REAL
defect, now fixed and re-proven · R2-E DONE · R2-F DONE (3 commits, 0 foreign paths).

**One command re-runs everything:** `python command-center/casualty/r2_verify_all.py` →
`SUCCESS:r2-verify-all 12 steps executed, all pass`, recorded verbatim in
`R2-FINAL-VERIFICATION.json`. Every step is a real subprocess; nothing in it reads a claim.

---

## R2-A. What the adversarial audit actually confirmed

The audit text handed to this lane was TRUNCATED mid-sentence. I recovered the full record rather
than guessing: `_r2_find_audit.py` scans the workflow journals for it, `_r2_dump_audit.py` dumps
one record. It is `wf_e58dfd3f-7b1` journal line 65, agentId `aa1e83cff63e3c2bd`, saved verbatim
at `_r2_audit_round1.txt` (26,672 B).

Verdict **PARTIAL** — *"ALL SIX DoD ITEMS SUBSTANTIVELY HOLD UNDER MY OWN EXECUTION … Nothing
needs rebuilding"*, with **7 overclaims** and **4 real defects** in ancillary tooling. Round 2
fixes all of them, plus a fifth defect found while fixing the third. Nothing was rebuilt; no probe
was re-authored.

## R2-B. CONFIRMED DEFECTS — fixed, each with a both-states control

`python command-center/casualty/_r2_defect_controls.py` →
`SUCCESS:r2-defect-controls 5 controls, all separate broken-vs-fixed`; machine-readable in
`R2-DEFECT-CONTROLS.json`. Each control materialises the PRE-FIX code from the stored blob at the
**pinned round-1 baseline `4afce4e1`** and requires the defect to REPRODUCE there first.

| id | defect | fix | broken-state proof |
|----|--------|-----|--------------------|
| D1a | re-running `_probe_liveness.py` silently ERASES the `_DO_NOT_CITE` banner on `ADV-LIVENESS.json` and republishes 6 false CASUALTY verdicts | execution refused (rc=2) unless `--i-know-this-is-superseded --out DIR`; importing it for `score()` is unaffected | pre-fix copy with OUT redirected to a temp dir holding a planted banner → rc=0 and **banner survived=False** |
| D1b | same shape, `_probe_census.py` → `ADV-COMPLETENESS-CENSUS.json` | same guard | same: **banner survived=False** |
| D2 | `verify_elided_digest.py` with no args printed nothing and exited **0** — a zero-input run indistinguishable from two passes, in an anti-fabrication tool | fails closed, rc=2, `FAILED:elided-digest no inputs` | pre-fix no-arg run `rc=0 stdout=''`; the fixed tool still emits 4×`MATCH=True` on the real receipts, so it is not merely inert |
| D3 | `liveness_v2.py`'s three-state control was opt-in behind `--selftest`, so the citable tally was produced without ever running it | the control runs unconditionally BEFORE any tally; `--selftest-mutate drop-g3` proves it can still fail | pre-fix default run: control printed=False, tally printed=True. Mutated run: rc=1 and **no tally emitted at all** |
| **D5 — new, found by me while fixing D3** | the control exercised `evaluate()` while the tally came from a **second copy** of the gate logic inside `main()`. The control guarded a different code path than the number it was certifying | one implementation; `main()` calls `evaluate()` | the AND-gate expression `g1 and g2 and g3` appears **2×** pre-fix, **1×** post-fix; tally unchanged at `{'SUBSTANTIVE': 38, 'RECOVERED': 2}`, so the collapse is behaviour-preserving |
| D4 | `adv0022_git_verifier.sh:31` narrated "219 files, of which 12" two lines above the lines that compute it | the delta is computed and printed as `self_match_inflation` | see the sharpening below |

**D4 is worse than the audit found, and the sharper version is the one recorded.** The audit read
it as drift ("live values are now 225 and 208"). Measured: the stored capture computes
`raw=219 / excluding-lane=208` → delta **11**, while its own narrative says **12**. It was wrong
**at capture time**, not merely stale — and the stray 12 is the *C3* block's
`raw_including_this_lane=12`, a number borrowed from the wrong block. Independent recomputation
today: raw=225, excluding-lane=208, delta=17; the fixed probe prints exactly 17.

**Three of my own round-2 detectors failed and are recorded, not hidden.**
1. the D5 duplicate-implementation counter counted the literal `verdict = "MID-FLIGHT"` — a syntax
   form that `evaluate()` writes as a ternary. It scored pre-fix=1 / post-fix=0, i.e. reported the
   defect ABSENT and the fix as having DELETED the logic.
2. the D4 control demanded `raw_including_this_lane=225` inside the OLD capture; 225 is today's
   value and the old capture holds 219, so it required a number the broken state never contained.
3. the ADV-0021 routing recount searched the WHOLE cell object for an ADV id and returned 24/6
   over unmitigated+partial — the use-vs-mention error, and not comparable with the audit's count
   over unmitigated cells. Field-scoped to the `disposition`, it reproduces the audit's 17 exactly.

All three are the count-the-form-not-the-thing shape. Every number above comes from the corrected
instruments. A fourth self-catch: my first ADV-0022 defect record used
`status: "closed-in-round-2"`, and the gate rejected the whole receipt as `schema-invalid` — the
enum is `['open','resolved','waived-by-owner','superseded']`. The gate caught me; that is what it
is for.

## R2-C. Overclaim repairs — 8 sentences, each recorded as REFUTED beside its scoped replacement

Located with a controlled corpus scan (`_r2_scan_overclaims.py`, 72 files, every pattern paired
with a known-present control token; 0 failed controls).

| # | refuted wording | what was actually measured | where it is fixed |
|---|---|---|---|
| OC1 | "every unmitigated cell routed to a **NAMED** existing catalog unit" | **17 of 21** route to a named unit; **4** are accepted residuals with owner-visible impact. The requirement is a disjunction and both arms are used | receipt `tests_required_closure.routing_split_recounted_in_round2`; `LANE-CASUALTY-REPORT.md` §2 |
| OC2 | "Probe 2 executes the bypass for every 'mitigated' cell … All satisfied" | TB3/Tampering had **no executed bypass against its own boundary** | **DATA fix:** cell downgraded `mitigated`→`unmitigated` per the spec's literal rule; counts 20/2 → **21/1** |
| OC3 | "c1/c5 = family convention" | c1 fails **41/42 (97%)** — holds. c5 fails **25/42 (59%)** — common, not universal; 17 siblings satisfy it | `LANE-CASUALTY-REPORT.md` §4; `_probe_census.py` docstring |
| OC4 | "c3 … cannot be satisfied" | unsatisfiable only for a receipt declaring ITSELF as primary artifact (40/42). ADV-0010 and ADV-0005 satisfy c3 by declaring external files | `LANE-CASUALTY-REPORT.md` §4 |
| OC5 | "a fresh clone reproduces both declared digests" | **no clone was made**; on a clean tree blob == worktree by construction | tool now HAS a real `--fresh-clone` mode (R2-D); wording fixed in the tool, the report and `COMMIT-PROVENANCE.md` |
| OC6 | "ADV-0002 … never dispatched" | round-1 probe read 2 runs / 100 transcripts / 1 session | **widened, not narrowed** — see below |
| OC7 | two stale pasted numbers: `transcripts scanned: 98`; "219 files, of which 12" | live 100; and the 12 was wrong at capture time | `ADV-0002-ACCOUNTING.md`; D4 fix |
| OC8 | "a **sibling agent** committed the whole index" | all commits share one author identity, so git cannot attribute it **in either direction** | `COMMIT-PROVENANCE.md` header + report §8 |

**OC6 was widened rather than narrowed, and it survived.** `_r2_adv0002_recheck.py` re-ran the
question with `rg` — a mechanically different tool — over **every `*.jsonl` in every session of
every project** under `~/.claude/projects`, not the census's two named runs:

- `YOUR WORK UNIT: ADV-0038` → **0 occurrences anywhere**.
- `YOUR WORK UNIT: ADV-0002` → occurrences exist and **every one is a MENTION** (an agent quoting
  a `uniq -c` tally, an agent quoting this investigation, and self-match from this round's own
  transcript). **Zero transcripts carry ADV-0002 as their own dispatched unit.**
- Detector control: the same matcher with the wildcard id finds **152 occurrences across 52
  files**, ADV-0021 six times — so the zero is a real absence, not a broken pattern.

This started as a genuine scare: a ripgrep sweep surfaced `3 YOUR WORK UNIT: ADV-0002` inside a
sibling's `uniq -c` output, which reads exactly like three dispatches. Reading the raw record
showed it was a count of *occurrences* across all projects, i.e. mentions. Two probes disagreed and
the disagreement was resolved from the raw source, not by vote.

**Residual, inline:** both probes assume a dispatch always carries the literal `YOUR WORK UNIT:`
marker. That held 40/40 for this wave. A launcher using a different template is invisible to both.
*Settling experiment:* read the workflow launcher that composes the spawn prompt and confirm the
marker is unconditional. — **Also measured:** ADV-0041 was dispatched to **three** agents, so
"one agent per unit" is not an invariant of this wave; the grounding lane flagged retry as a
theoretical risk to two-signal identification and it is real.

## R2-D. Re-verification after the fixes

- **Gate vector, both receipts, unchanged by every round-2 edit:**
  `c2, c4, c6, c7, c8, c12 = SATISFIED`; `c1, c3, c5, c9, c10, c11 = UNSATISFIED`. Read as a
  vector, never as the binary marker — the marker is saturated across the family (it prints
  `FAILED` for the known-complete ADV-0024 and for a 1,818 B skeleton alike).
- **Elided self-digests re-converged and re-verified after patching:** ADV-0021 `MATCH=True`
  at 176,468 B, ADV-0022 `MATCH=True` at 114,103 B, both with the mutated-state control still
  changing the digest.
- **Receipt patcher is idempotent** — it rebases on the pinned round-1 blobs at `4afce4e1` before
  applying, so a second run reproduces byte-for-byte instead of double-appending.
### The fresh-clone leg found a REAL defect — round 1's sentence was not merely unproven, it was FALSE

`verify_blob_parity.py --fresh-clone` clones this repo into a throwaway directory and recomputes
each digest from the clone's object store **and** from the clone's checked-out file. Run against
the round-2 receipts commit `ea9a6eee`:

```
ADV-0021  clone blob     176468 B  CRLF    0   digest MATCH=True
          clone CHECKOUT 177741 B  CRLF 1273   digest MATCH=False
ADV-0022  clone blob     114103 B  CRLF    0   digest MATCH=True
          clone CHECKOUT 114776 B  CRLF  673   digest MATCH=False
FAILED:fresh-clone a reviewer who clones this repo cannot reproduce the declared digest
```

**Mechanism:** `core.autocrlf=true` and the root `.gitattributes` covers only `*.sh` and `*.ps1`,
so a checkout converted these LF blobs to CRLF. Each receipt publishes an elided sha256 of its own
bytes and `verify_elided_digest.py` reads with `newline=""` — it hashes what is on disk. A
reviewer cloning on Windows therefore could **not** reproduce either published digest, and the
declared `artifacts[0].bytes` disagreed with the file they actually got. The blob was always fine;
the checkout was not, and the checkout is what a reviewer reads. This is the
worktree-green-vs-clone-green trap landing on the very artifact that claimed immunity to it.

**Fix:** `command-center/casualty/.gitattributes` marks exactly the two digest-bearing receipts
`-text`. Verified safe before applying — all **84** tracked lane blobs are pure LF
(`_r2_blob_eol_scan.py`), so nothing CRLF is frozen in place. Deliberately **not** lane-wide: 30
lane files hold CRLF in the *working tree* while their blobs are LF, and a blanket rule would
surface 30 EOL-only phantom modifications on a worktree siblings commit from.

**Post-fix, same probe, commit `676a65db` — the other half of the both-states control:**

```
ADV-0021  clone blob 176468 B CRLF 0 MATCH=True   clone CHECKOUT 176468 B CRLF 0 MATCH=True
ADV-0022  clone blob 114103 B CRLF 0 MATCH=True   clone CHECKOUT 114103 B CRLF 0 MATCH=True
SUCCESS:fresh-clone both receipts reproduce their declared digest from a clone that never saw
this working tree
```

**Scope of that claim, stated exactly:** measured on this Windows host with `core.autocrlf=true`,
cloning over `file://` at depth 1. A Linux CI checkout (`autocrlf=false`) would have produced LF
and matched even before the fix — so the pre-fix failure was reviewer-platform-specific, while the
fix makes it platform-independent. *Settling experiment for the residual:* clone on Linux with
`core.autocrlf=input` and confirm both digests still match.

## R2-E. Census + liveness refresh, with the live-wave caveat demonstrated

Re-run immediately before committing, `2026-08-12T08:28:41Z`:

- `census_v2.py` → control FIRST: **6 pairs, ALL SEPARATE** (complete 6/6 vs skeleton 0/6); 40
  artifacts; raw `{0: 2, 5: 4, 6: 34}`; `SUCCESS:census-v2`. The script exits non-zero and prints
  no tally if any control pair fails to separate.
- `liveness_v2.py` → three-state control PASSES **on the same invocation that reports the tally**
  (that is the D3+D5 fix), then `{'SUBSTANTIVE': 38, 'RECOVERED': 2}` at
  `2026-08-12T11:28:41+03:00`, `SUCCESS:liveness-v2`.
- The two known casualties are RECOVERED, not dead: their finished receipts exist at this lane's
  paths. The canonical `command-center/adversarial/` paths still hold the 2 KB skeletons —
  promotion is an orchestrator action, and until it happens any tool reading only the canonical
  path sees two false casualties.

**The live-wave caveat is not boilerplate — it is still live at this write.**
`git status --porcelain -- command-center/adversarial/` shows ADV-0037, ADV-0040 and ADV-0041
modified by a sibling wave right now. **A low score is never a casualty verdict on its own**, and
this census is stale the moment it is written.

## R2-F. Commits

Three commits, every one a pathspec commit whose foreign-path count was checked as **0** before
committing (`git diff --cached --name-only | grep -cv '^command-center/casualty/'`). No
`git add -A`, no `git add .`, no `git commit -a`, no force-push, no `--no-verify`, no history
rewrite. `command-center/adversarial/` was READ-ONLY throughout. Unlike round 1, each commit
carries this lane's own message.

| commit | files | lane | foreign | what |
|---|---|---|---|---|
| `ea9a6eee` | 31 | 31 | **0** | the 5 defect fixes, the receipt data fix, the 8 overclaim repairs, the round-2 probes |
| `676a65db` | 3 | 3 | **0** | the EOL pinning that the fresh-clone check proved necessary |
| `7f7fb32d` | 9 | 9 | **0** | the one-command verification runner and its recorded output |
| `808dde5e` | 44 | 44 | **0** | ruff-green the lane, minus the 5 provenance-locked originals |
| *(this one)* | — | — | **0** | this artifact's final state |

Round 1's bulk was swept into a whole-index commit whose message belonged to another lane. That
did not recur: all four round-2 commits are lane-only and carry this lane's own message.

## R2-G. What is still NOT done — honestly scoped

1. **No reviewer on either unit, and I cannot be one.** ADV-0021 requires one cross-vendor
   **openai** refuter who re-derives the counterexample from the raw artifact; ADV-0022 requires
   **two different-vendor** reviewers each independently reproducing. Zero have run; both receipts
   carry `reviewer.verdict = NOT-REVIEWED, independent=false`. The round-1 auditor was same-vendor
   and said so explicitly. Reproduction is cheap and needs no credential:
   `probes/adv0022_escape_harness.py` plus a scratch dir.
2. **Both receipts are still parked outside their canonical `output_path`,** at
   `command-center/casualty/`, because this lane is forbidden from writing into
   `command-center/adversarial/` while a sibling wave is active. Each records
   `extensions.canonical_output_path`. Until an orchestrator promotes them, the canonical paths
   hold the 2 KB skeletons and any tool reading only those paths sees two false casualties.
   `census_v2`/`liveness_v2` handle this via a recovery cross-reference; other tools will not.
3. **ADV-0022's disposable-sandbox clause remains PARTIAL.** `%TEMP%` is a weaker substrate than a
   network-namespaced sandbox; Modal returned "Token missing" and no credential was created
   (AGENTS.md §9). Containment holds by construction (loopback only, no egress attempted).
4. **`command-center/recover_failed_agents.py` is still unpatched.** `recover_failed_agents_v2.py`
   is a drop-in with a both-states selftest, but the original is outside this lane's file scope.
   Until someone promotes it, the next casualty triage runs a tool that over-matches 62/92 and can
   report a delivered artifact as a total loss.
5. **The census axes are tuned, not derived,** and controlled on a bimodal corpus with only two
   distinct skeleton fixtures. A genuinely half-finished artifact could land mid-band.
   *Settling experiment:* build a deliberately half-finished fixture and check it scores 2–4.
6. **Why ADV-0002/ADV-0038 were never dispatched is still unknown.** Round 1 refuted the leading
   hypothesis (the READY-snapshot theory); no replacement has been established.
7. **The liveness AND-gate is not wired into the wave harness.** The grounding lane's scope
   expansion #3 — promote it as the missing watchdog — remains a recommendation. Both casualties
   sat dead ~2.6 h and were found by a human going looking, which is the failure the durable-
   execution literature names: *"no supervisor, no watchdog, no heartbeat … simply dead until
   something external notices."* The instrument now exists and is control-proven; wiring it is an
   orchestrator action outside this lane's file scope.

## R2-I. CI hygiene — the lane's share of a repo-wide red, and one conflict I refused to paper over

Measured with the CI-pinned `uvx ruff@0.15.17`, not the ambient one. Main is broadly red:
**145 files would be reformatted repo-wide and 29 lint errors**, of which this lane owned **41
files and 10 errors**. `_r2_lint_lane.py` fixes the lane's share and leaves a stated residual.

**The conflict.** Five scripts under `probes/` are **byte-identical to the dead agents' scratch
originals** — I re-measured the sha256 against
`%TEMP%/claude/…/30bd50d4-…/scratchpad/` rather than trusting the audit: 5/5 LOCKED,
`adv0021_verifier.py` correctly NOT locked (it was authored in round 1, so it has no scratch
twin). The audit's *"prior work recovered, not redone"* finding rests entirely on that match.
Reformatting them would satisfy a style gate **by destroying the evidence that the work was
recovered rather than re-authored** — and there is no per-file escape from `ruff format` that
does not itself change the bytes.

So: 37 lane python files formatted and lint-clean (`All checks passed!`, `37 files already
formatted`), provenance verified unchanged before AND after, and the 5 locked files deliberately
left red. **The durable fix is one line outside this lane's file scope:** add
`command-center/casualty/probes/` to `extend-exclude` in the ROOT `ruff.toml`. Two E402s in
`_build_adv0021.py` and one in `_r1_rerun_diff.py` are deliberate late imports and now carry a
scoped `# noqa: E402` with the reason, rather than being silenced repo-wide.

**All 12 verification steps still pass after the reformat** — the reformat is behaviour-preserving
and that was checked, not assumed.

## R2-H. Detector failures I caught in MYSELF this round (five)

Recorded because a program whose dominant failure mode is the false green cannot afford a lane
that only reports its successes.

1. **D5 duplicate-implementation counter** counted the literal `verdict = "MID-FLIGHT"` — a syntax
   form `evaluate()` writes as a ternary. Scored pre-fix=1/post-fix=0: defect ABSENT, fix DELETES
   the logic. Both readings wrong. Fixed by counting the AND-gate expression (2 → 1).
2. **D4 control** demanded `raw_including_this_lane=225` inside the OLD capture; 225 is today's
   value and the capture holds 219, so it required a number the broken state never contained.
3. **D4 control, second failure — it reproduced the very defect it was testing.** It compared the
   FROZEN R2 capture against a LIVE `git grep` recount, and broke the moment this lane committed
   34 more files containing the token. A capture is a historical fact; only a fresh run may be
   compared with a fresh recount.
4. **ADV-0021 routing recount** searched the WHOLE cell object for an ADV id (use-vs-mention) and
   mixed partial cells into a count the audit made over unmitigated cells: 24/6 instead of 17/4.
5. **The verification runner's `git-verifier` step PASSED while every git query inside it had
   failed.** `bash` from a Python subprocess resolves to `C:\WINDOWS\system32\bash.exe` = WSL,
   which sees `/mnt/c` and dies with `fatal: not a git repository`; the needle
   (`ADV0022_GITV_END`) prints regardless, so it was a needle that could not fail. Fixed by
   invoking Git Bash explicitly and asserting the C1 control is non-zero and no `fatal:` appears.
   *(A sixth, cosmetic: the gate-vector assertion used `[  ok] 2.` while the gate right-aligns to
   `[  ok]  2.`, failing both gates on formatting alone. The parser now requires all twelve
   conditions to be seen, and is itself controlled: it returns True for these receipts, False for
   sibling ADV-0010 and False for the 1,818 B skeleton at the canonical path.)*