# P2NEXT — BUILD lane round 1: review the satisfiable subset, count the rail-blocked remainder

**Measured 2026-08-12** against `ast-integrate` (worktree of `agent-skills-toolchain`, `main`).

COVERAGE: §1-§6 MEASURED and executed. Every number was produced by a command in §7; nothing here
is recalled. Two residuals carry inline UNVERIFIED tags with their settling experiments named.

---

## 0. Headline

1. **The grounding's split is CONFIRMED by re-execution** — 51 blocked, **41 rail-blocked**, 10
   satisfiable, 7 review-only. Not inherited; both scripts were re-run.
2. **All 7 review-only units are now REVIEWED and RECEIPTED** by an independent fresh-context
   reviewer that did not author them. 7 of 7 return **PASS**, each on an executed falsification.
3. **But none of them can reach DELIVERED, and the reason is not the reviewer.** The schema
   hard-rejects `state=SUCCESS` while `manifest_registration.registered` is false, and nothing in
   the repo can set it. **R2 of the grounding plan is REFUTED** (§5).
4. **4 LOW findings**, all of the "the sentence is wider than its evidence" class. One was
   corrected in place; three are scope notes. **Zero headline counts were refuted.**

---

## 1. Independent re-verification of the grounding split — CONFIRMED

| quantity | grounding | this lane re-ran | agree |
|---|---|---|---|
| BLOCKED/FAILED units | 51 | 51 | yes |
| RAIL_BLOCKED | 41 | 41 | yes |
| SATISFIABLE_NOW | 10 | 10 | yes |
| required reviewer vendor | 41 openai / 7 anthropic / 3 any | identical | yes |
| `vendor_satisfiability.py` selftest | PASS (5 cases incl. the v1 regression) | PASS | yes |

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

### 2b. CROSS-VENDOR-REQUIRED (rail-blocked) — 41

`ADV-0001`, `ADV-0003`…`ADV-0037`, `ADV-0039`, `ADV-0040`, `ADV-0042` (39 ADV) + `BLD-0023` +
`IMP-0433`. **Not reviewed by this lane and not receipted.** Substituting a same-vendor Claude
reviewer would satisfy the letter and defeat the purpose. 16 of the 41 carry a requirement that is
internally unsatisfiable (a "cross-vendor Anthropic refuter" on an Anthropic-produced unit), so
they resolve to an `openai` refuter regardless.

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

### 3c. Reviewer-instrument honesty

A first pass produced **8 divergences. Five were my own bugs**, not unit defects: a key guessed as
`package`/`thresholds_file` instead of `package_dir`/`has_thresholds_file` (which made a per-row
check **inert** — it passed while matching nothing, the exact "control that cannot distinguish the
two hypotheses" failure), a vendored-path filter stricter than the claim's own wording, and a
`tomllib` parse reading only `project.dependencies`. Comparing **sets instead of counts** resolved
every one. A sixth: the CC-0002 mutant was initially not schema-valid, so it died at C2 and never
reached the condition it was designed to test. All are recorded in the receipts, not hidden.

## 4. Rail-blocked remainder — the price of `codex login`

**41 units.** Re-executed, not inherited. The grounding's correction of the briefed "43 of 47"
stands: that figure was a **tag-sum** (137 tag occurrences over 51 distinct units), not a unit
count.

**Caveat that must travel with the number [likely, 55-80%]:** 41 is what the receipts *demand*, not
what would *pass*. And §5 changes the price — even a successful Codex review leaves every one of
the 41 behind the same condition-11 wall the 7 just hit.

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
- **NOT DONE, deliberately:** no `codex login`; no same-vendor review of any of the 41; no
  `render.py` run (shared surface, wrong tool for the job); **no edits to `blocker_census.py` or
  `CROSS-VENDOR-RAIL-STATUS.md`** — both are outside the declared file scope, so their counting
  defects are handed over rather than patched: `blocker_census.py:185-190` prints a tag-sum under a
  unit count, and `CROSS-VENDOR-RAIL-STATUS.md` still says **43** where the measured figure is
  **41 of 51**. No READY units were built — 449 are READY behind the same gates.

## 7. Reproduce

```
python command-center/p2-next/split_review_gate.py          # 51 units, counted once each
python command-center/p2-next/vendor_satisfiability.py      # the 41/10 split, selftest-gated
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
