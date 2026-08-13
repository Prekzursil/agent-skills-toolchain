# P2NEXT — BUILD lane round 1: review the satisfiable subset, count the rail-blocked remainder

**Measured 2026-08-12** against `ast-integrate` (worktree of `agent-skills-toolchain`, `main`).

COVERAGE: §1-§6 MEASURED and executed. Every number was produced by a command in §7; nothing here
is recalled. Two residuals carry inline UNVERIFIED tags with their settling experiments named.

> ## ROUND-2 CORRECTIONS — read `P2NEXT-BUILD-R2.md` before citing any number below
>
> An independent auditor CONFIRMED defects in this document. The corrections are applied inline
> below, each keeping the refuted wording verbatim so the error is recorded rather than deleted:
>
> 1. **"41 rail-blocked" was a WORKTREE number.** On the COMMITTED tree it is **42 / 52 blocked**.
>    The difference is `ADV-0041`, which is BLOCKED in every commit since `fb2f477f` but SUCCESS in
>    the shared worktree via a sibling lane's UNCOMMITTED edit. (§0, §1, §2b, §4, §6.)
> 2. **The published reproduce command did not reproduce its own number.** Re-running
>    `vendor_satisfiability.py` printed 47/4, overwrote the committed artifact, and turned this
>    lane's own verifier red. Root cause and fix in R2 §1. (§7.)
> 3. **"137 tag occurrences" is REFUTED** — measured 114 on the committed basis. (§4, §6.)
>
> What survived the audit unchanged: the SATISFIABLE set (the same 10 ids, re-derived from the
> pre-edit blobs), all 10 reviews and their receipts, and the finding that condition 11 — not the
> reviewer — is the last gate.

---

## 0. Headline

1. ~~**The grounding's split is CONFIRMED by re-execution** — 51 blocked, **41 rail-blocked**, 10
   satisfiable, 7 review-only. Not inherited; both scripts were re-run.~~
   **REFUTED in round 2 as to the BASIS, not the arithmetic.** Those figures are true of the
   *worktree*. Committed tree: **52 blocked, 42 rail-blocked, 10 satisfiable, 7 review-only.** The
   satisfiable SET is unchanged and was re-derived from the pre-edit blobs (R2 §1).
2. **All 10 satisfiable units are now REVIEWED and RECEIPTED** by an independent fresh-context
   reviewer that did not author them. 10 of 10 return **PASS**, each on an executed falsification —
   the 7 review-only rows plus `IMP-0440`, `TST-0334` and `TST-0350`, each reviewed on its own
   distinct requirement (a fourth blob-route file, a second Windows shell, and a reproduction of
   the declared NC2 both-states control).
3. **But none of them can reach DELIVERED, and the reason is not the reviewer.** The schema
   hard-rejects `state=SUCCESS` while `manifest_registration.registered` is false, and nothing in
   the repo can set it. **R2 of the grounding plan is REFUTED** (§5).
4. **4 LOW findings**, all of the "the sentence is wider than its evidence" class. One was
   corrected in place; three are scope notes. **Zero headline counts were refuted.**

---

## 1. Independent re-verification of the grounding split — CONFIRMED

| quantity | grounding | this lane re-ran | agree | **round 2, COMMITTED basis** |
|---|---|---|---|---|
| BLOCKED/FAILED units | 51 | 51 | yes | **52** (+`ADV-0041`) |
| RAIL_BLOCKED | 41 | 41 | yes | **42** |
| SATISFIABLE_NOW | 10 | 10 | yes | 10 — same ids |
| required reviewer vendor | 41 openai / 7 anthropic / 3 any | identical | yes | **42 openai / 7 anthropic / 3 any** |
| `vendor_satisfiability.py` selftest | PASS (5 cases incl. the v1 regression) | PASS | yes | PASS (8 cases, +2 v2 regressions) |

Both round-1 columns were measured against the shared **worktree**. The round-2 column is the
**committed** tree, which is what CI and any other reader sees. Neither is wrong about its own tree;
round 1's failure was not naming the tree.

## 2. The split — receipt text quoted per unit

### 2a. SATISFIABLE by an independent Claude reviewer — 10

| unit | quoted requirement | second blocker |
|---|---|---|
| `AUD-0006` | "one **fresh-context Claude reviewer** who has not seen this unit's transcript; the reviewer must try to FALSIFY the headline count before PASS, not re-read the artifact" | none |
| `AUD-0020` | same; `blocked_on`: "fresh-context Claude reviewer (reviewer_requirement)" | none |
| `AUD-0021` | same; `blocked_on`: "one fresh-context Claude reviewer who never saw this transcript" | none |
| `AUD-0030` | same | none |
| `AUD-0041` | same | none |
| `AUD-0051` | same | none |
| `CC-0002` | "**One independent reviewer** who writes a fifth mutant the author did not anticipate and confirms it is rejected." | none |
| `IMP-0440` | "**independent-claude-reviewer** re-measures the three-route comparison on a DIFFERENT file" | cross-tree edit authority (T5 FAIL) |
| `TST-0334` | "One independent reviewer who re-runs the probe under a SECOND Windows shell (pwsh7 and Git Bash)" | a committed consumer of `blobread` |
| `TST-0350` | "One independent adversarial reviewer in a fresh context who did not author the harness under test and who must reproduce the both-states control" | first CI execution of the wired step |

The 6 `AUD` rows and `IMP-0440` name a **Claude/same-vendor** reviewer explicitly — supplying one
is not a substitution, it is the thing the receipt asks for. `CC-0002`, `TST-0334` and `TST-0350`
set **no vendor constraint**.

### 2b. CROSS-VENDOR-REQUIRED (rail-blocked) — 42 committed / 41 worktree

~~41: `ADV-0001`, `ADV-0003`…`ADV-0037`, `ADV-0039`, `ADV-0040`, `ADV-0042` (39 ADV) + `BLD-0023` +
`IMP-0433`.~~ **Round-2 correction:** on the committed tree it is **42** — the same set **plus
`ADV-0041`**, whose committed `blocked_on` reads "cross-vendor Codex refuter + downstream consumer
execution". Round 1 read `ADV-0041` from the worktree, where a sibling lane's uncommitted edit has
it `state=SUCCESS` with `reviewer.vendor=openai`. **Not reviewed by this lane and not receipted.**
Substituting a same-vendor Claude reviewer would satisfy the letter and defeat the purpose. 16 of
the 42 carry a requirement that is internally unsatisfiable (a "cross-vendor Anthropic refuter" on
an Anthropic-produced unit), so they resolve to an `openai` refuter regardless.

## 3. The reviews — 7 of 7 PASS

Each number was re-derived by a route mechanically different from the one the unit recorded, with a
both-states detector control, from the RAW evidence rather than the unit's own conclusion.

| unit | verdict | what falsification actually did | finding |
|---|---|---|---|
| AUD-0006 | **PASS** | 174 re-parsed from the raw porcelain capture by a reviewer-written v2 parser, zero set difference; tally 152/10/12 recomputed from `content_verdict`; all three disagreement buckets 17/8/11 exact | LOW — prose decomposition summed to 36, not its own 37 |
| AUD-0020 | **PASS** | manifest SET byte-identical (23) via the **git index** instead of a disk walk; each of the 93 `declared` names verified present in its own manifest file; every row's count == `len(declared)` | none |
| AUD-0021 | **PASS** | manifest SET identical (26) by **two** enumerations; dev=32, locks=5, without-lock=21, all 5 multi-version keys exact | LOW — `prod=42` is short by 2 |
| AUD-0030 | **PASS (scoped)** | the cycle and its exact members reproduce under **Kosaraju** (unit used Tarjan) and are **invariant across 3 resolver policies** yielding 185/185/1867 edges | LOW — 679/265 are snapshot+policy dependent, unlabelled |
| AUD-0041 | **PASS** | 7 files / 14 jobs / 4 conditional steps / 2 conditional jobs exact; the 143→148 delta decomposes exactly to `test-python` 63→66 and `skill-dual-write` 9→11 with workflow commits after `ended_at`; dirty `quality.yml` ruled out (105 steps in worktree **and** HEAD blob) | LOW — no snapshot caveat |
| AUD-0051 | **PASS** | 1-of-43 gated confirmed by disk rglob **and** the git index; **42 of 42** ungated rows literally carry `NOT-CHECKED` | none |
| CC-0002 | **PASS** | the fifth mutant is the **copy-paste receipt** — schema-valid sentinel bound to a *different* real unit — targeting **C4, the one `admit()` condition no author mutant reaches**. REJECTED on C4 in **both** sentinel grammars; golden still ACCEPTED; shipped `--self-test` still exits 0 | none (2 observations) |
| IMP-0440 | **PASS** | the three-route comparison re-measured on **four** files the unit never used. Control stronger than the row's own: the byte delta equals the archive CRLF count **exactly** (621/621, 220/220, 205/205, 100/100), plus a newline-free negative case | LOW — T5 debt count is a mention-count |
| TST-0334 | **PASS** | probe re-run under **both** Windows shells: 20 fields compared, **0 differing**, all 12 route fields identical, markers identical, both rc=0. Absent-path control exits rc=1 rather than returning empty bytes | LOW — its "committed consumer" blocker is **stale** |
| TST-0350 | **PASS** | declared **NC2 reproduced in-process, both directions**: `collect_count` over an empty dir returns 0 and `require_nonempty(0)` **raises**; on the real suite 3948 ≥ 3900 it stays **silent** and `check_suite` returns ok | none |

### 3a. Why CC-0002's mutant is the right one

`admit()` has four reject conditions. The author's four mutants cover C1 (m4), C2 twice (m1, m2)
and C3 (m3). **C4 — "sentinel embeds the unit id" — had zero coverage**: `m1` deletes the sentinel
and dies at C2 first, `m3` rewrites the sentinel to match its own forged id. The reviewer's mutant
is parseable, schema-valid, and for a real catalog unit, so C4 is the only condition left that can
reject it — and it does. Verified in the bare `SUCCESS:<ID>` grammar too, which matters because
**1,911 of 2,007** catalogued sentinels use that form.

Two adversarial extras, filed as observations not defects: C4's substring binding would admit a
superstring id in isolation, but the schema's fixed-width id pattern rejects that at C2 and **0**
catalog ids are a strict prefix of another (load-bearing if the pattern is ever relaxed); and a
receipt asserting `exists=true` with a fabricated `sha256` for a path not on disk **is admitted** —
in scope for an admission-only module, whose schema design notes assign that check to the layer-2
reducer. Filed for another owner.

### 3b. Findings in full — 4, all LOW, none refuting a headline

1. **AUD-0006 · summary-prose-arithmetic.** "disagrees on **37**" then "LOSE 17 … KEEP 8 … plus
   11" = **36**. The reviewer cross-tab found a fourth cell the prose never named:
   `UNDECIDED → SCRATCH`, 1 row. **Corrected in place**; the original wording is preserved verbatim
   in `reviewer.notes` so the correction is not a silent deletion.
2. **AUD-0021 · silent normalisation.** `platform/marketplace/fixture/packages/dep-consumer-1.0.0/package.json`
   declares `dependencies` as a **JSON array of 2**; the unit records `"dependencies": {}`,
   `counts.dependencies: 0`, while reporting `parse_errors=0`. `prod=42` should be 44 or the shape
   anomaly should be disclosed. Repo impact nil — deliberate test fixture.
3. **AUD-0030 · unscoped snapshot.** `module_count=679` not reproducible today (692 tracked;
   two-signal reconstruction at `ended_at` brackets **[674..675]** on tracked files only).
   `edge_count=265` is resolver-policy dependent. The **cycle** is invariant.
4. **AUD-0041 · unscoped snapshot.** 143 was right at `ended_at`; today 148. AUD-0006 labels its own
   count a snapshot under INDEX CONTENTION; this row does not.
5. **TST-0334 · LOW · stale blocker.** Its `blocked_on` still names "a committed consumer of
   `blobread`" as outstanding. **No longer true:** an AST import check finds **6** real importers,
   **5 non-test**, including the CI-wired `tools/measure-guard/unitgate.py` and `vendordrift.py`.
   `git grep` matched 15 candidates, so **9 were mention-only** — the use-vs-mention correction
   applied to the reviewer's own first probe.
6. **IMP-0440 · LOW · mention-count debt.** T5's "files that implement their own `cat-file` read"
   is now 62 by `git grep -l`, but that is a *mention* count by the same method the row used for
   its 37. **UNVERIFIED [likely, 55-80%]** that the true debt is near 62. *Settling experiment:*
   run the AST import check over those 62. Either way T5 is not closed.

None of the six refutes a headline. All six are the "sentence wider than its evidence" class — fix
the sentence, disclose the residual.

### 3c. Reviewer-instrument honesty

A first pass produced **8 divergences. Five were my own bugs**, not unit defects: a key guessed as
`package`/`thresholds_file` instead of `package_dir`/`has_thresholds_file` (which made a per-row
check **inert** — it passed while matching nothing, the exact "control that cannot distinguish the
two hypotheses" failure), a vendored-path filter stricter than the claim's own wording, and a
`tomllib` parse reading only `project.dependencies`. Comparing **sets instead of counts** resolved
every one. A sixth: the CC-0002 mutant was initially not schema-valid, so it died at C2 and never
reached the condition it was designed to test. All are recorded in the receipts, not hidden.

Reviewing the last three added **four more**, each caught before it became a false finding:

1. The cross-shell comparison ran `json.loads` over the whole stdout. `blobread` prints JSON **then**
   a `SUCCESS:` marker, so it raised `Extra data`, both parses returned `None`, the equality guard
   evaluated `False` — and a **MEDIUM cross-shell-divergence finding that does not exist** was one
   step from being filed against TST-0334.
2. The IMP-0440 control predicted `git archive` diverges only where the **worktree** has CRLF.
   **Measured wrong:** an all-LF file still returned 220 CRLF, because archive applies export-time
   conversion regardless. Replaced with the exact byte-delta test, which does discriminate.
3. The first NC2 attempt used a temp dir **outside** the repo, died on `FileNotFoundError WinError 2`
   and measured nothing. Reporting its silence as a pass would have been the inert-control failure.
   The re-run also had to fix two wrong signatures (`collect_count` returns a tuple).
4. The corrected AUD-0006 decomposition checker searched the **whole** summary, where
   `repos_scanned=1` supplied a standalone "1" — so it passed on the broken text too. **Its own
   both-states control caught that**, which is the only reason it is not still wrong.

## 4. Rail-blocked remainder — the price of `codex login`

~~**41 units.** Re-executed, not inherited. The grounding's correction of the briefed "43 of 47"
stands: that figure was a **tag-sum** (137 tag occurrences over 51 distinct units), not a unit
count.~~

**ROUND-2: 42 units on the committed tree** (41 on the worktree — see the §2b correction). The
"43 of 47" correction still stands as a correction, but **the 137 figure is REFUTED** — and the
replacement has to be stated with its definition, because the occurrence sum is not one number:

| definition | value |
|---|---|
| `failure.classification` + top-level, deduped per unit, committed (52 units) | **114** |
| same, auditor's measurement on the worktree (51 units) | 113 (+1 = `ADV-0041`'s single tag) |
| every `classification` key anywhere in the receipt, NOT deduped (`split_review_gate.py`) | **132** |
| round-1's claim | ~~137~~ — not emitted by any instrument here |

The 132-vs-114 gap is **18 tags inside one receipt** (`ADV-0009`) plus 1 (`ADV-0007`)
(`R2-RECONCILE.json`). An "occurrence sum" that one receipt's internal nesting can move by 16% is
the argument against quoting it at all. The answerable number is **31 distinct units carrying a
review/refut-naming tag** — *less* than the 42 the ladder resolves, because 11 rail-blocked units
express their cross-vendor demand only in `blocked_on` prose and never tag it. Counting the
structured field alone therefore **under**-reports this gate by 11 units.

**Caveat that must travel with the number [likely, 55-80%]:** 42 is what the receipts *demand*, not
what would *pass*. And §5 changes the price — even a successful Codex review leaves every one of
the 42 behind the same condition-11 wall the 10 just hit.

## 5. R2 IS REFUTED — `render.py` does not do what the plan assumed

The grounding's R2 was "run `python tools/command-center/render.py` once; clears
`manifest_registration:false` on all 10." Measured, three independent signals:

- `render.py` writes only the **13 charter docs** (`STATUS.md`, `OWNER-DECISIONS.md`,
  `ARTIFACT-MANIFEST.json`, …). It never opens a unit receipt, so it cannot change a receipt field.
- `ARTIFACT-MANIFEST.json` holds **14 entries, all charter docs, 0 unit artifacts**.
- **0 of 74** real unit receipts carry `registered=true`. The only 12 documents that do are
  `IMP-0433`'s own test fixtures under `p2-wave/fixtures/`.

And the field is a hard bar: simulating `state=SUCCESS` on all 7 yields
`manifest_registration/registered: True was expected`. So the reviewer gate was **not** the last
gate — condition 11 is, for every unit in the program. The repo already half-knows this:
`platform/architecture/marketplace-first.md:327-333` (FM-7) says condition 11 "has never been
exercised at scale". This lane sharpens that from *never exercised* to **not currently satisfiable
by the only tool that writes the manifest**.

`render.py --check` also already reports `STATUS.md differs from its rendering` (drift=1) from other
lanes' catalog edits. **This lane did not run it** — it is a shared surface outside the declared
file scope, and running it would fold in other lanes' changes without achieving R2's purpose.

**AUD-0051 has a second, independent bar:** its `tests[]` records
`enforcement-command-executes → FAIL` (`tools/editor/metaswarm exit=1`), and the schema forbids
`state=SUCCESS` when any test result is FAIL. Honestly recorded by the unit; it simply means a
reviewer alone was never going to move that row.

## 6. Residuals and what this lane deliberately did not do

- **UNVERIFIED [uncertain, 20-55%]** — that the 41 would reach DELIVERED after a Codex review. This
  lane measured what receipts *demand*. Open defects were checked on the 7 only (all zero).
  *Settling experiment:* run the open-defect + `completion_sentinel` check across the 41 — and per
  §5, condition 11 now bounds that answer regardless of vendor.
- **UNVERIFIED [likely, 55-80%]** — AUD-0030's `module_count=679`. The reconstruction brackets
  [674..675] from tracked files; untracked scratch since deleted would push it up toward 679, which
  is the right direction but is not proof. *Settling experiment:* re-run the unit's builder against
  the commit that was HEAD at its `ended_at`.
- **NOT-CHECKED** — whether `codex login` fixes the `agent/register` failure. Owner-only credential
  write; not attempted, not re-probed.
- **NOT DONE, deliberately:** no `codex login`; no same-vendor review of any of the 42; no
  `render.py` run (shared surface, wrong tool for the job); **no edits to `blocker_census.py` or
  `CROSS-VENDOR-RAIL-STATUS.md`** — both are outside the declared file scope, so their counting
  defects are handed over rather than patched. ~~`blocker_census.py:185-190` prints a tag-sum under
  a unit count, and `CROSS-VENDOR-RAIL-STATUS.md` still says **43** where the measured figure is
  **41 of 51**.~~ **Round-2 correction:** the census prints its tag figure at the END of its output
  (`tags naming an independent/cross-vendor REVIEW gate: 33`), not "directly under" the receipt
  count, and the figure this lane attributed to it (137) is not one the tool emits — it came from
  `P2NEXT-GROUNDING.md:43`. The live defect is narrower and still real: **an occurrence sum
  answers a question nobody asked**; the unit-level number is 31 (§4). And
  `CROSS-VENDOR-RAIL-STATUS.md` says **43** where the measured figure is now **42 of 52 committed
  / 41 of 51 worktree**. No READY units were built — 449 are READY behind the same gates.

## 7. Reproduce

```
python command-center/p2-next/split_review_gate.py          # 51 units (WORKTREE basis), counted once each
python command-center/p2-next/vendor_satisfiability.py      # ROUND 2: 42/10 committed + 41/10 worktree.
                                                            # Default is CHECK-only and exits 1 on drift;
                                                            # pass --write to regenerate. Round 1's form of
                                                            # this command silently REWROTE the artifact.
python command-center/p2-next/_r2_control_stability.py      # both-states control: the v2 ladder moves 6 units
python command-center/p2-next/_r2_control_b20.py            # both-states control: the verifier fails closed
python command-center/p2-next/_r2_tagcensus.py              # 114 occurrences / 31 units (refutes "137")
python command-center/p2-next/_b3_falsify_aud0006.py        # AUD-0006 falsification
python command-center/p2-next/_b4_falsify_aud_rest.py       # AUD-0020/0021/0030/0041/0051
python command-center/p2-next/_b5_triage.py                 # instrument-vs-defect triage
python command-center/p2-next/_b6_aud0030.py                # resolver-policy sweep, cycle invariance
python command-center/p2-next/_b8_timeindex.py              # two-signal snapshot reconstruction
python command-center/p2-next/_b9_cc0002_fifth_mutant.py    # the fifth mutant
python command-center/p2-next/_b10_predicate_probe.py       # condition-11 hard bar
python command-center/p2-next/_b11_manifest_gap.py          # 0 of 74 receipts registered
python command-center/p2-next/_b13_write_receipts.py        # writes the 7 receipts, schema-gated
python command-center/receipt_validate.py <the 7 paths>     # 7/7 ADMITTED after the write
```
