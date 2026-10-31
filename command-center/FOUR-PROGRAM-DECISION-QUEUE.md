---
title: FOUR-PROGRAM-DECISION-QUEUE
type: note
permalink: dqverify-repo-20261013/command-center/four-program-decision-queue
---

# FOUR-PROGRAM DECISION QUEUE — synthesis of 10 lane artifacts

**Lane:** SYNTH · **Owner file:** this file, mine alone · **Measured:** 2026-08-10 23:15-23:40
**Mandate:** consolidate every lane into ONE decision queue. Investigation only. I did **not** write
`WORK-UNIT-CATALOG.json`, did not run `close.py`/`seed.py`, did not commit, push or branch, did not
touch `platform/routing/**`, `tools/measure-guard/**`, `command-center/receipts/**` or
`.github/workflows/**`, and did not run the full `pytest platform` suite.

> If it still reads this way, the unit died before investigating anything and no verdict here may be cited.
*(Mandated sentinel, retained verbatim. It does NOT describe this file: COVERAGE below is 10/10 read
and 5/5 PRODUCE sections measured. The skeleton it guards read `UNKNOWN - not yet investigated` on
every row.)*

**COVERAGE (final): COMPLETE.** 10 of 10 contracted lane artifacts Test-Path'd, then read in full
(not from a digest). 5 of 5 required PRODUCE sections measured. Six cross-lane contradictions
resolved from source, not by vote. **NOT measured by me:** the full `pytest platform` suite
(forbidden); any re-run of the lanes' own executable probes except where named below; the
basic-memory recall probe behind contradiction X6 (a 4th single signal would not settle it — see X6).

---

## 0. HEADLINE — the premise moved WHILE this lane ran, and the apply is already producing violations

**At HEAD `ef6e2c4b` the orchestrator's premise is exactly right: 69 open, ZERO closed.** Measured on
the HEAD blob: `dispositions = {None: 69, DONE-VERIFIED: 26, SUPERSEDED: 5, DROPPED-BY-OWNER: 3}`,
and **zero** `R-*` items carry a terminal disposition. (The 26 DONE-VERIFIED are `T-01..T-26`, a
different id namespace.)

**In the working tree right now it is not.** A serial apply started at **23:29:16** while I was
reading. Seven tracked files are modified and **7 register items have already been flipped to
`DONE-VERIFIED`**: `R-A06 R-A09 R-A10 R-A12 R-A20 R-B06 R-M01`. The derived files were re-rendered at
**23:32:23** and now carry, in `STATUS.md` itself:

```
**62 open / 103 total.** Reachability: 4 VIOLATIONS.
- REACH-1 R-A06: item is closed but depends on still-open R-A03
- REACH-1 R-A09: item is closed but depends on still-open R-A03
- REACH-1 R-A12: item is closed but depends on still-open R-A03
- REACH-6 -: register snapshot sha256 cd894ccba284 != recorded 8b3e44cc3813
```

**Lane A1 predicted this exact failure and it is now measured-true in production.** A1's cross-lane
note: *"R-A11/R-A06/R-A07/R-A08/R-A09's `dependencies: [R-A03]` are all counterfactual — the gated
work shipped without the gate. The dependency edges should be retired or re-scoped, or every future
reachability check will keep reporting a blocker that execution has already walked past."*

**Consequence for the remaining apply:** of the 11 not-yet-applied CLOSE proposals, exactly **two**
(`R-A08`, `R-A15`) also declare `dependencies: [R-A03]`. Applying them before the R-A03 edges are
retired adds 2 more REACH-1 violations (6 total). Retiring the edges first costs nothing and needs no
owner. **This is item 2 of the critical path and it is now urgent, not theoretical.**
Confidence: almost-certain (90-99%) — two mechanically independent signals (the catalog blob diff and
the validator's own rendered VIOLATIONS block).

## 0b. Test-Path receipts — every contracted output verified BEFORE any digest was read

| artifact | exists | bytes | mtime | read in full |
|---|---|---|---|---|
| `command-center/CLOSE-PROPOSALS-A1.md` | True | 13,681 | 22:42 | yes |
| `command-center/CLOSE-PROPOSALS-A2.md` | True | 14,144 | 22:50 | yes |
| `command-center/CLOSE-PROPOSALS-A3.md` | True | 26,751 | 23:11 | yes |
| `command-center/CLOSE-PROPOSALS-M1.md` | True | 14,284 | 23:06 | yes |
| `command-center/CLOSE-PROPOSALS-M2.md` | True | 14,001 | 22:50 | yes |
| `command-center/CLOSE-PROPOSALS-M3.md` | True | 14,324 | 22:48 | yes |
| `command-center/PHASE15-16-STATUS.md` | True | 32,074 | 22:37 | yes |
| `command-center/STOPPING-RULE-REDERIVATION.md` | True | 25,227 | 23:06 | yes |
| `command-center/PROMPT-ONE-REVERIFY.md` | True | 15,484 | 22:05 | yes |
| `command-center/PROMPT-1_5-CLOSURE.md` | True | 13,399 | 21:50 | yes |

**Zero missing.** All ten are substantive and none is a skeleton — **but see contradiction X3: lane
A2 reported `PHASE15-16-STATUS.md` as "still an unfilled skeleton (`COVERAGE: 0/N`)" and placed a
hold on two dispositions because of it. That hold is discharged.**

**Detector control (so the EXISTS readings mean something):** in the same invocations,
`command-center/ZZZ-SENTINEL-MUST-NOT-EXIST.json` → ABSENT and
`harness-restore-20260806/ZZ-A3-SENTINEL-MUST-NOT-EXIST.md` → ABSENT, while every known-present
control returned EXISTS with a plausible size. The detector discriminates.

---

## 1. EVERY proposed CLOSE, for serial application

### 1a. Register CLOSEs — 18 of 69 items (the only ids the catalog can accept)

`APPLIED` = already flipped in the uncommitted working tree at 23:29. `⚠` = a caveat the orchestrator
must read before applying.

| # | id | lane | evidence anchor | my independent verification | flag |
|---|---|---|---|---|---|
| 1 | **R-A23** | A3 | `~/.claude/harness-restore-20260806/15-IMPLEMENTATION-PRECONDITIONS.md` | **VERIFIED on disk** — 12,342 B, mtime 2026-08-09 13:47 | clean |
| 2 | **R-A24** | A3 | `…/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md` | **VERIFIED on disk** — 14,618 B, mtime 2026-08-09 13:43 | clean |
| 3 | **R-B05** | M3 | `docs/program-b/{README.md,program-b-receipt.json,mutation_probe.py}` + `ci/tests/test_program_b_register.py` | **VERIFIED — all 4 exist and are tracked** (5,430 / 12,964 / 5,326 / 10,111 B) | clean |
| 4 | **R-A04** | A1 | `command-center/OWNER-DECISIONS.md:47-51` | **VERIFIED** — OQ-4 `state=ANSWERED`, *"NO - the 38-item tranche was NOT an approved substitute"*, dated 2026-08-10 | status is `UNKNOWN`; needs an explicit disposition |
| 5 | **R-B04** | M3 | `scripts/validate-all-skills.ps1:18-22` | **VERIFIED INDEPENDENTLY:** cand1 `Test-Path=False`, **cand2 `%USERPROFILE%\.codex\skills\.system\skill-creator\scripts\quick_validate.py` = True**, `CODEX_HOME` set. Q22's premise (*"resolves a validator … that exists nowhere"*) is REFUTED | ⚠ still formally gated by **Q22 OPEN** → apply the CLOSE *and* retire Q22 as moot, or leave gated by owner choice |
| 6 | **R-A25** | A3 | `…/harness-restore-20260806/diagrams/README.md` | **VERIFIED** — dir exists, 9 `.md` (8 diagrams + README) | ⚠ never rendered (A3's own residual); D1-N4 adds *4 of 8 are <2 KB* under the audit's own triviality rule |
| 7 | **R-A14** | A2 | `wfdsl.validate` exit 0 on `bp-gem-01..05`; mutant → exit 1 | **NOT re-run by me** | ⚠ lane's inline UNVERIFIED: the 5 blueprints were never diffed against `21-GEM-HUNT-COMPOSABLE-SPEC.md` (42,645 B) |
| 8 | **R-A27** | A3 | `OWNER-DECISIONS.md:29-31` (OQ-3/OQ-4 ANSWERED) | **VERIFIED** — 2 of 27 questions ANSWERED | ⚠ **weakest CLOSE in the set** (A3 self-scores *likely 55-70%*). A3 measured `P-02 FAIL` — G-01..G-05 still undecided — and C2 measured `17-DECISION-LOG.md` **is not in this repo**. A3 offers `SUPERSEDED-BY <the OWNER-DECISIONS mechanism>` as the alternative; that is the orchestrator's call |
| 9 | **R-A26** | A3 | `15-preconditions-check.py:88-95` + `:60-66` | **VERIFIED** — the two-root resolver exists | ⚠ **CONDITIONAL CLOSE.** A3's own load-bearing caveat: the 28-row two-root index is **not persisted anywhere**. If the orchestrator requires the index *as an artifact*, this is **STAYS-OPEN, effort S** |
| 10 | **R-A08** | A1 | `BLUEPRINTS-85-96-STATUS.json`; `BLUEPRINTS-BP1-DISTINCTNESS.json` | **VERIFIED both exist** (19,006 / 2,018 B) | ⚠⚠ **HOLD.** (a) trips REACH-1 unless the R-A03 edges are retired first. (b) **Definitional conflict with C2 condition 17** — see X5. A1 self-scores *likely 55-80%* and says the disposition "turns on how EXECUTABLE is read, which is an owner call" |
| 11 | **R-A15** | A2 | `platform/lib/foundry/forge.py:1023-1080`; `fused.cnc07-arc05.TOURNAMENT.json` | **VERIFIED** — TOURNAMENT.json 5,508 B | ⚠ trips REACH-1 unless edges retired. ⚠ lane's inline UNVERIFIED: pairwise over fusion strategies, **not** N-way; only ONE committed instance |
| 12 | R-A06 | A1 | `platform/marketplace/PROOF-e2e.json` | **APPLIED @23:29.** ⚠⚠ **the anchor is NOT VALID JSON** — two independent parsers fail identically (`ConvertFrom-Json`: *Additional text*; `json.load`: *Extra data: line 209 column 1*), caused by a bare `SUCCESS:phase6-marketplace-e2e` sentinel on line 209 of 210 | **APPLIED** · live REACH-1 · defective anchor |
| 13 | R-A09 | A1 | `PROTOCOLS-25-36-VALIDATION.json`; `CONFORMANCE-STATUS.json` | **APPLIED @23:29.** Both verified (58,509 / 9,047 B) | **APPLIED** · live REACH-1 · ⚠ same definitional conflict as X5 vs C2 condition 19 |
| 14 | R-A10 | A1 | `platform/schema/councilspec.schema.json:1476` | **APPLIED @23:29.** File verified, 52,597 B | **APPLIED** · clean |
| 15 | R-A12 | A2 | `platform/plugin/cli.py:104-150,210-326`; `WAVE4-PLUGIN-LIFECYCLE-VERIFY.md:16-24` | **APPLIED @23:29.** ⚠ `platform/plugin/cli.py` is itself **modified in the working tree at 23:32** (+13 lines) — the anchor's line numbers are moving under the apply | **APPLIED** · live REACH-1 · ⚠ 3 successor defects unfiled (§3 A7) |
| 16 | R-A20 | A2 | `PHASE9-COORDINATION.md:25-27`; `ABSTRACTION-LEAKS.md` | **APPLIED @23:29.** Both verified (12,424 / 12,586 B) | **APPLIED** · clean |
| 17 | R-B06 | M3 (+M1, M2 concur) | `D:\basic-memory\projects\harness-restore\Program B …2026-08-09.md` | **APPLIED @23:29.** Three lanes independently confirm the notes exist | **APPLIED** · ⚠ contradiction X6 on the *residual*, not the disposition |
| 18 | R-M01 | M1 (+M2, M3 concur) | `skills/monitor-launcher/monitors.toml:58` | **APPLIED @23:29. VERIFIED: line 58 is literally `[cockpit]`.** Triple-confirmed by three lanes | **APPLIED** · clean |

**Totals: 18 CLOSE proposals of 69 register items (26%). 7 already applied, 11 pending. 2 of the 11
(`R-A08`, `R-A15`) must wait on the R-A03 edge retirement. 2 more (`R-A26`, `R-A27`) are conditional
on an orchestrator/owner reading, not on evidence.**

**Register items with NO CLOSE proposal: 51.** 5 are OWNER-GATED (§2); 46 are STAYS-OPEN, of which
**14 had their scope materially reduced** by this wave (`R-A02 R-A07 R-A11 R-A17 R-A18 R-A19 R-A22
R-A29 R-A30 R-H02 R-H03 R-H05 R-H08 R-H09 R-M02 R-M05 R-M11 R-M15` — a narrowing is not a close but it
is the difference between "unknown work" and "a named S-sized task").
**Lane M2 proposed ZERO closes across its 7 items and said so plainly** — that is a clean result, not a
gap; its yield was four corrections to register evidence.

### 1b. Non-register CLOSEs — 14 proposals in a DIFFERENT id namespace

**These are NOT catalog rows and `close.py` cannot accept them.** They are findings about the
scorecard, the release phases and two prior audits. Applying them means editing
`PROGRAM-STOPPING-SCORECARD.json` / the audit files, which are owned elsewhere.

| id | lane | claim | verified? |
|---|---|---|---|
| scorecard **condition 4** | C2 | FALSE → **TRUE**; all 3 of Phase 14's grounds refuted; every push/PR gate green at `ef6e2c4b` | not re-run by me. ⚠ C2's own disclosure: `main` has **no branch protection**, so "required" is an empty set and the TRUE is *partly vacuous* |
| scorecard **condition 14** | C2 | TRUE, now on 2 signals (`pytest platform/plugin -k rollback` → 2 passed) | not re-run |
| scorecard **condition 16** | C2 | TRUE, reproduced from scratch: 163 kept rows, 0 missing provenance/license | not re-run |
| `P15-spec-locate` | C1 | spec located out-of-repo at `_USER-PROMPTS.md:11100-11133`, `:11135-11150` | plausible; `_USER-PROMPTS.md` confirmed present |
| `P15-oq3-pronly` | C1 | OQ-3 ANSWERED = PR-ONLY, supersedes the scorecard's caveat | **VERIFIED** at `OWNER-DECISIONS.md:32,41-45` |
| `P15-schema-layer` | C1 | 16 of 16 referenced schemas exist | not re-counted |
| `P15-cond14` | C1 | cite-only, stays TRUE at its narrow scope | inherited by C1's own admission |
| `P16-loop-map` | C1 | all 10 spec loop steps map onto P16 units (mapping only) | C1 self-scores *likely 55-80%* (regex recall on step 6) |
| `D1-2`, `D1-3` | D1 | the floor audit's counts reproduce exactly under independent anchors (28/28 union; all 5 corrected probes hold) | not re-run |
| `D2-1`, `D2-2`, `D2-3` | D2 | Prompt 1.5's scope statement, 14 exit criteria and closure basis all exist on disk | not re-run |
| `D2-4c` | D2 | R5 install half: `msys_pathconv.py` live (54,292 B), import resolves, called from a registered hook | not re-run |

⚠ **Flag for the orchestrator:** three of these (`condition 4`, `D1-2`, `D2-2`) CLOSE a *scoring row*
while their own lane discloses that the underlying condition is only partly satisfied. Each is
honestly scoped in its source file. Do not compress them into "condition 4 is done" — carry the
vacuity caveat with it.

---

## 2. The OWNER-GATED set — measured from the catalog's own `owner_gate` field

**25 of 27 owner questions are OPEN** (`OWNER-DECISIONS.md:5`; OQ-3 and OQ-4 ANSWERED 2026-08-10).
**Only 8 of those 25 gate any register item, and each gates exactly ONE item.** The other **17**
(`Q3 Q6 Q9 Q10 Q11 Q12 Q13 Q14 Q15 Q16 Q17 Q18 Q20 Q21 Q23 Q24 Q25`) block **nothing** in the
register — they are real questions but they are not on anybody's critical path.

| gate | directly gates | transitive reach via `dependencies` | total items | verdict |
|---|---|---|---|---|
| **OQ-1 + OQ-2** (option IDs; overrides/priority) | `R-A03` | **11**: `R-A02 R-A06 R-A07 R-A08 R-A09 R-A11 R-A12 R-A13 R-A15 R-A16 R-A17` | **12** | **Deepest fan-out in the register — and provably counterfactual.** 3 of the 11 dependents are already CLOSED and 2 more are CLOSE-proposed. `07-OPTION-UNIVERSE.json` already carries `owner_decisions: 70` as a ready OQ-1 default (A1) |
| **`REL-0003`** — *a work unit, not an owner question* | 42 of 43 Phase-15/16 units | — | **42** | **The single largest owner gate in the whole program, and it has NO row in `OWNER-DECISIONS.md`.** C1 measured exactly **1 of 43** P15/P16 units startable and it is `REL-0003` itself (the only unit with an empty dependency list, `owner_approval_required=true`). OQ-3=PR-ONLY fixed the *mode*, not the *pass condition* for spec `:11125`/`:11131` |
| **OQ-8** (enrol the monitor cockpit, at what priority) | `R-M18` | 1: `R-M06` | 2 | M1: R-M06 is *"the only owned row I cannot dispose of"* — its 7 live gate findings include one R-M05 just re-confirmed, so elapsed time cannot retire it |
| **Q19** (`owner-ops-authorization.md` live-only) | `R-H10` | 0 | 1 | A3 **corrected the register's direction call**: 15 files are REPO-AHEAD (deployable loss-free today), only **3** are LIVE-AHEAD (`owner-ops-authorization.md`, `security.md`, `windows-shell.md` — the last was *not* in the register's list), and `single-signal-verification.md` is a CRLF phantom |
| **Q22** (`validate-all-skills.ps1` unrunnable) | `R-B04` | 0 | 1 | **PREMISE REFUTED by two independent measurements** (M3, and mine). Propose **retire as moot** |
| **OQ-6** (`Diag 1.txt` credentials) | `R-B08` | 0 | 1 | **SECURITY-CLASS.** Unchanged for **20 days** (2,172,114 B, mtime 2026-07-21T14:23:01Z — byte-identical across three independent stat-only readings by M1, M2, M3; **no lane opened it**). Rotation is the owner's alone (AGENTS.md §9) |
| **OQ-7** (Program B renumbering) | `R-B07` | 0 | 1 | The canonical `id_map` now exists in one CI-gated place, so the *ambiguity risk* is gone; the receipt still requires owner confirmation to close |
| **OQ-5** (C22/G-05 vs I3/D07 authority) | `R-A05` | 0 | 1 | Its dependency R-A04 is now resolved, so OQ-5 is no longer *blocked* — merely unanswered |
| **OQ-B1 — MISSING FROM THE CATALOG** | *would gate* `R-B01` | 0 | 1 | M3's finding: `docs/program-b/README.md` + the receipt raise OQ-B1 (*"M1 Defender exclusions and M2 grok-cli residency are owner-only — apply, decline, or defer?"*) and the catalog's 27 questions do not include it. R-B01 cannot be closed by any agent while its two remaining actions are owner-only |

**Also owner-only, outside the question table:** 9 of the 43 P15/P16 units carry
`owner_approval_required=true` (`REL-0003 REL-0012 REL-0013 ADV-0048 ADV-0055 ADV-0142 ADV-0143
CNF-0126 IMP-0373`); D2-6 (a plaintext Databricks PAT in `_USER-PROMPTS.md` transcripts); and C2's
open question of whether `main` should be branch-protected at all.

**Answer to "which gates block the most items": `REL-0003` (42 units) then OQ-1+OQ-2 (12 items).
Everything else gates 1-2 items. The 17 remaining open questions gate zero.**

---

## 3. CRITICAL PATH — smallest ordered set of actions that unblocks the most

Ordered by unblocked-items-per-effort, with the owner batch placed exactly once (the owner asked not
to be interrupted piecemeal — `OWNER-DECISIONS.md:5`).

**A0. Reconcile the in-flight uncommitted catalog write. BLOCKING — do this before anything else.**
7 tracked files modified (`WORK-UNIT-CATALOG.json`, `sources/REGISTER.md`, `STATUS.md`,
`ARTIFACT-MANIFEST.json`, `DEPENDENCY-GRAPH.json`, `platform/plugin/{cli.py,test_cli.py}`), 7 register
items already flipped, **4 live validator violations**. Either finish and commit this batch or revert
it — do not layer 11 more closes onto an unvalidated tree. *Cost: minutes. Unblocks: the whole apply.*

**A1. Retire or re-scope the 11 `dependencies: [R-A03]` edges.** Zero owner input needed; A1 lane
already made the case and the validator has now proven it. *Prevents 2 further REACH-1 violations
(`R-A08`, `R-A15`), clears 3 live ones, and removes a phantom blocker from 8 more A-items.*
**Highest yield of any action in this queue.**

**A2. Re-record the register snapshot sha256** — REACH-6: `cd894ccba284 != 8b3e44cc3813`, because
`sources/REGISTER.md` was rewritten at 23:29:16. *One field. Clears the 4th violation.*

**A3. Apply the 11 pending register CLOSEs, least-coupled first:** `R-A23 · R-A24 · R-B05 · R-A04 ·
R-B04 (+retire Q22) · R-A14 · R-A27 (or SUPERSEDED-BY) · R-A26 (decide the conditional first)`, then
**after A1 only**: `R-A08 · R-A15`. *69 → 58 open.*

**A4. Re-probe the register rows whose evidence is `[inherited]` AND phrased as an absence.** This is
the cheapest remaining source of closes and it is now *proven* productive: contradiction X1 shows
lane A2 declared 4 artifacts absent that exist on disk. **`R-A21` and `R-A22` should move from
STAYS-OPEN to CLOSE-candidate on re-probe.** A2's proposed mechanisation is one `grep -c
'\[inherited\]'` away from countable. *Estimated additional closes: 2-4, at ~minutes each.*

**A5. Repair the 6 dangling bucket tokens `B01 B06 B07 B08 B12 B13`** (20 edges; 17 of 43 P15/P16
units), and extend the catalog integrity checker so a `B\d+` token with zero members FAILS
(both-states control: must fire on B07 today, go silent after). Zero owner input. *Immediately makes
6 units startable in parallel (`ADV-0038 ADV-0055 ADV-0058 ADV-0088 REL-0009 REL-0016`) — the highest
unlocked-work-to-effort ratio C1 found.* Note C1's inline UNVERIFIED: **what a `B\d+` dependency MEANS
is defined nowhere** ("bucket" appears in no `contract`/`defaults`/`tool_policy` key), so define the
semantics as part of this step or readiness stays uncomputable.

**A6. ONE owner batch — the only action that unblocks Phase 15 at all.** Contents:
`REL-0003` (C1's three precise sub-questions: what replaces the `:11131` canary under PR-ONLY; is
`:11125` satisfied by the existing shadow ladder or waived; is the marketplace *listing document* in
scope) · `OQ-1` (recommend accepting the 70 `owner_decisions`) · `OQ-2` · `OQ-5` · `OQ-6`
(security, 20 days old) · `OQ-7` · `OQ-8` · `Q19` (recommend: deploy the 15 REPO-AHEAD rule files,
hold the 3 LIVE-AHEAD) · **retire `Q22`** as moot · **add `OQ-B1`** and attach it to `R-B01`.
*Unblocks 42 P15/P16 units + 12 A-items + 5 gated register rows.*

**A7. File the successor items before their parents close** — otherwise measured defects leave the
register silently, which is what REACH-6 exists to prevent. A2 verified the catalog contains **zero**
hits for each of them. Minimum set: `R-A12a` (`installed.json.archive_sha256` holds the wrong
version's hash after rollback, `platform/plugin/lifecycle.py:496-503`), `R-A12b` (`uninstall` reports
`kept_live_edited: []` while an owner-edited live file survives), `R-A12c` (a hard-killed install
wedges the prefix for a full hour, `journal.py:99,110-126`), the **R-A08 DSL-interpreter gap**,
`OQ-B1`, C1's `C1-D1/D2/D3`, and D1's `N1..N7`. **`R-A12` is already CLOSED with a/b/c unfiled — this
is a live loss right now.**

**A8. Fix the two defective evidence anchors before anything else cites them.**
(a) `platform/marketplace/PROOF-e2e.json` is unparseable JSON and is **R-A06's primary anchor for an
already-applied close** — one-line fix (move the sentinel to a field or a sibling file).
(b) `command-center/RELEASE-CHECKLIST.md:14-15` prescribes `git archive` for a CRLF-vs-LF check, which
on Windows returns the **opposite** of the blob — independently measured by **two** lanes with
identical figures (3,220 B / 52 CRLF via `git archive` vs 3,168 B / 0 CRLF via `git cat-file -p`, and
3,168 is what `ARTIFACT-MANIFEST.json` records). Fix to `git cat-file -p <rev>:<path>`.

**Not on the critical path, and say so out loud:** the published critical path in `STATUS.md:36-45` is
**stale at positions 2 and 3** — `#2 R-B06 "write the basic-memory notes"` and `#3 R-M01 + R-M02 "one
TOML stanza"` are both already done (R-B06 and R-M01 are now DONE-VERIFIED; PR #279 / `fbedcdf6`
landed the stanza on 2026-08-09). Position 1 (`R-B08`) is owner-only. Re-render the critical path
after A0-A3 or the next reader will re-walk two finished items.

---

## 4. CONTRADICTIONS between lanes — every one resolved from source, none by vote

### X1 — R-A21 / R-A22 artifact existence. **A2 is REFUTED; A3 is correct.** *(almost-certain 90-99%)*
A2: *"`01-BLOCKER-REPRODUCTION.md` absent from both trees"* and *"[R-A22's] three named files absent
from both trees"*. A3: all four now exist, written by lane `prompt-one-gaps` on 2026-08-09.
**Measured by me, both roots, in one invocation with a sentinel control:**

| file | `harness-restore-20260806` | `platform-redesign-2026-07-19` |
|---|---|---|
| `01-BLOCKER-REPRODUCTION.md` | **EXISTS** 9,584 B, 08-09 13:41 | ABSENT |
| `08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json` | **EXISTS** 344,197 B, 08-09 13:29 | ABSENT |
| `10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json` | **EXISTS** 161,920 B, 08-09 13:29 | ABSENT |
| `10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md` | **EXISTS** 18,633 B, 08-09 13:31 | ABSENT |
| `ZZ-A3-SENTINEL-MUST-NOT-EXIST.md` *(control)* | ABSENT | ABSENT |

**Root cause of A2's error, mechanically established:** A2's own controls were
`02-BLOCKER-ROOT-CAUSE.md` and `10-WORKFLOW-FORGE-SPEC.md`, both of which I measure **present in
`platform-redesign` and ABSENT from `harness-restore`**. A2's detector therefore fired in the *wrong
root* and its "both trees" claim is unsupported by its own control. This is the same two-root union
defect A3's `R-A26` and D1's `N2` both measured. **Action: R-A21 and R-A22 go to CLOSE-candidate on
re-probe by their owner; A2's framing of R-A22 as "a documentation task, not a build" is wrong —
the documents already exist.**

### X2 — R-M09 probe artifact. **M3 is REFUTED; M2's numbers stand.** *(almost-certain 90-99%)*
M3: *"A prior lane wrote `_b2_m09_probe.py` and `_b2_m09_probe2.py` but **neither has an
`_out.json`** — written, never run to an artifact."* Measured: `_b2_m09_probe2_out.json` **exists**,
3,546 B, mtime 22:11, and carries `control_present_reports_present: true`,
`control_absent_reports_absent: true`, `bak_file_count: 31`, `bak_names_not_in_live: []`, 23
raw-byte-identical files. M3's own filename hypothesis is what failed, not the probe.
**Disposition unaffected:** M1 and M2 independently measured the same 23/8 split (both refuting the
register's 25/6) and both agree the deletion is loss-free. M2's `STAYS-OPEN` is the correct
disposition because the *deletion* is the work and it has not happened; M1's "CLOSE-eligible" refers
to the *precondition*. Not a real conflict once scoped — but M3's sentence must not be cited.

### X3 — `PHASE15-16-STATUS.md` "unfilled skeleton". **A2's hold is DISCHARGED.** *(almost-certain)*
A2 §3 refused to let an `R-A16`/`R-A17` disposition be applied *"until C1 lands"*, on the basis that
C1's file was an empty skeleton. C1's file is complete (32,074 B, `COVERAGE (final): COMPLETE`, 19
proposal rows), written 22:37 — before A2 was finalised at 22:50, so A2 read a stale snapshot.
**No disposition changes:** `R-A16` and `R-A17` remain STAYS-OPEN under both lanes, and the two
findings are compatible (C1: all 10 P16 loop steps *are* decomposed into catalog units, 0 artifacts
exist; A2: no keep-or-revert *engine* exists among the 115 blueprints). **Release the hold.**

### X4 — "tracked tree CLEAN". **C2's premise was true when measured and is FALSE now.**
C2 anchored its whole re-derivation on *"tracked tree CLEAN (`git status --short | grep -v '^??'` is
empty)"*. I measure **7 tracked files modified**. The writes are timestamped 23:29:16 / 23:32:23,
*after* C2's file was written at 23:06 — so this is a live race, not a C2 detector failure.
**Consequence: any lane re-using C2's cleanliness premise must re-probe.** C2's condition-5 claim
(*"12/12 killed on a tracked tree with zero modifications — so this is committed HEAD, not an
uncommitted orphan"*) survives: `platform/lib/` is not in the modified set (only
`platform/plugin/cli.py` and `test_cli.py` are).

### X5 — "EXECUTABLE": R-A08/R-A09 CLOSE vs scorecard conditions 17/19 FALSE. **A definitional
conflict, not a factual one — and it is an OWNER call.** *(almost-certain on the facts)*
A1 proposes CLOSE on `R-A08` (*≥96 materially distinct blueprints executable*) while disclosing
inline that **there is no DSL interpreter**. C2 scores condition 17 FALSE on a controlled zero (`grep`
for `def execute|def run_workflow|class WorkflowExecutor|def _execute_stage` → **0 files**; control
`def validate|def resolve` → **6 files**). Same for `R-A09` vs condition 19 (*no council runtime; the
`councilspec/` package is a validator*). **Both lanes measured the same absence and reached opposite
dispositions because they read "executable" differently** — authored-in-an-executable-DSL + schema-
and-semantically-valid + dry-run-tested (A1) versus an-engine-has-run-it (C2). **Do not apply R-A08
until the owner rules**, and if it is applied, the interpreter gap must be filed as its own item (A7).

### X6 — R-B06 recall probe: 1 on-topic hit vs 8 off-target hits. **Unresolved; disposition
unaffected; residual differs.** *(uncertain on the mechanism)*
M1: the register's exact query *"now returns exactly ONE result and it is on-topic"*. M2: that same
probe *"still returns 8 off-target results even though the note exists"*. M3 could not query at all
(`Unable to connect`) and correctly refused to read that silence as zero, switching to the on-disk
vault (736 notes). All three agree the notes EXIST → CLOSE stands. Most likely mechanism: different
`search_type` (M2 states it used `search_type="text"` for its own probe and attributes the 8-result
reading to the *semantic phrase* query) — **but that is inference, not measurement.** I deliberately
did **not** re-run it: a fourth single reading would not settle a disagreement about which probe was
run. **Settling experiment: run BOTH `search_type` values against the register's exact phrase, side by
side, in one invocation — none of the three lanes did that.** Three different residuals are owed and
none is in the register: alias text for recall reachability (M2), a `valid_as_of` + `superseded_by`
amendment on the now-stale monitor note (M1, M3), and a retrievability re-probe (M3).

### X7 — register 25/6 vs measured 23/8 on R-M09. **Register wrong, conclusion unchanged.** Two lanes
independently measured 23 identical / 8 differing; both note the register's numbers are stale because
live moved on since 2026-07-27. The overclaim shape from `fan-out-contract §C2`: right verdict,
oversized sentence.

### X8 — the `git archive` defect, cited at `:14-15` (C1) and `:15` (C2). **Not a conflict — a
double-confirmation.** Two lanes, independent measurements, identical byte figures. Treat as
CONFIRMED and fix once (A8b).

### X9 — owner-question id namespaces. Not a contradiction but a live ambiguity worth one decision:
`OWNER-DECISIONS.md` carries **two** prefixes side by side (`Q3..Q25` and `OQ-1..OQ-8`), lanes cite
both interchangeably, and M3's proposed `OQ-B1` would introduce a third convention. Pick one before
adding OQ-B1. *(A3 flagged the identical hazard for option ids: `C16` in `07-OPTIONS-C.md` is a
DIFFERENT option from `C-16` in `07-OPTION-UNIVERSE.json`, and `OPTION-ID-RESOLUTION.md` has zero
`C16` rows — an executor grepping the wrong namespace implements the wrong option.)*

---

## 5. What NO lane covered — coverage gaps, explicitly

**First, the good news, measured:** every one of the 69 register items had an owning lane
(A1: R-A01-11 · A2: R-A12-22 · A3: R-A23-32 + R-H01-10 · M1: R-M01-07 · M2: R-M08-14 · M3: R-M15-19 +
R-B01-08 = 69, no overlap, no orphan). The register itself was fully swept. Every gap below is about
something *outside* that sweep.

1. **The other 1,964 of 2,007 work units are un-audited.** C1 covered only the 43 Phase-15/16 units.
   Its transitive-closure probe found **93 further unbuilt units** across phases 0, 1, 2, 2A, 4, 10,
   11, 12 (largest: 2A=34, 11=21) and nobody looked at them. Any P15 schedule is dominated by phases
   0-12, not by phase 15.
2. **The path-namespace reconciliation itself has no owner.** Every lane names it as the root cause
   (`DELIVERY-RECONCILIATION.md:16-18`), and C2 measured **4 of 2,007 units (0.20%)** with an artifact
   at their declared `output_path`. No lane owns fixing the declared paths or recording the
   reconciliation.
3. **The 8 Phase-15 spec deliverables with NO owning catalog unit** (C1 §3: semantic version,
   marketplace listing, quick-start, advanced examples, security policy, contribution guide,
   governance guide, support policy). 29 of 31 P15 units emit a receipt; **not one emits a `.md`**.
   `ADV-0057` (phase 12) is chartered to *review* three documents nobody is chartered to write.
4. **No engine has ever run a blueprint, and nobody owns building one.** Two lanes measured the
   absence (X5). The definitional question is also unowned.
5. **No Windows CI arm exists.** 14 of 14 jobs are `runs-on: ubuntu-latest`; zero `strategy:`/`matrix:`
   in any of the 7 workflows. A Windows-only regression is red in nobody's gate — on a Windows-primary
   estate. Condition 7's failure; no lane proposed the fix.
6. **The full `pytest platform` suite was run by nobody** (forbidden, and CI-gated). Union of the
   lanes' targeted runs ≈ **1,421 of 3,946** tests (A1 431, A2 638, C2 352).
7. **Scorecard condition 9 was re-measured by nobody.** C2 labelled it `NOT-CHECKED-BY-ME` and scored
   FALSE by deference; Phase 11's 26 claim probes (18 CONFIRMED / 5 PARTIAL / 3 REFUTED and a tripped
   escalation threshold) stand unrefreshed.
8. **Condition 20 — the meta-review — remains undone, and that now includes this file.** C2 explicitly
   refused to score itself as the fix. There is still exactly ONE Phase-14 synthesis. C2 is
   un-reviewed single-agent output; **so is this document.** A third agent must review both.
9. **The 46-failure-class registry** (R-A19's second half). `TEST-REGISTRY.json` seeds 7 classes and
   records the other 39 as the prose string *"the other 39 classes; see R-A19"* — so the gap is still
   not countable, which was the entire point. `UNKNOWNS-REGISTER.md:15` U-4 independently says 7 of 46.
10. **D1-N1: the 4 both-tree artifacts are BIDIRECTIONALLY diverged with no precedence rule, and the
    semantic classification is unowned.** Not line-ending noise. `11-COUNCIL-SPECIFICATION.md`: 308
    lines only in tree1, **1,566 only in tree2**. A naive "read the newer tree" rule silently drops
    1,566 unique lines. D1 measured line-set divergence and flagged the content question UNVERIFIED;
    nobody ran the section-level diff.
11. **R-B08's contents were never re-verified** — correctly (no lane opened it), but the 7 Ed25519
    keys + 24 refresh tokens are an **inherited** count from a 2026-07-23 scan. **And the blast-radius
    question — what indexes `~/Downloads` — is unanswered by all three lanes that touched it** (M2
    eliminated basic-memory only). Two lanes also note the *directory* holds 3-20 further multi-MB
    session dumps, unscanned, so a quarantine scoped to `Diag 1.txt` alone may under-cover.
12. **The catalog's own `known_defects_at_merge` has no owner:** `dependency_cycles: 1`,
    `self_dependencies: [IMP-0274, IMP-0277, IMP-0299]`, `units_missing_bucket_field: 1735`,
    `unknown_form_dependency_refs: 41`. A1 flagged it; no lane claimed it.
13. **R-A30's five residuals:** branch coverage, vendor parity, monitor-live receipt, the 3-unit
    Databricks smoke, independent review. Named by A3, owned by nobody.
14. **Live-vs-repo CONTENT direction for the 328 shared skills.** A3 settled the *name*-level question
    (live-only skills = 0, so a projection is loss-free) and labelled the content direction
    **NOT-CHECKED**, naming the settling probe (per-`SKILL.md` SHA-256, EOL-normalised).
15. **Whether `main` should be branch-protected.** C2 measured `{"message":"Branch not protected"}`
    with an admin token and correctly called it an owner decision, not a measurement. Until it is
    answered, condition 4's TRUE is partly vacuous.
16. **Prompt 1.5's un-tracked tail** (D2): R3, R4, the observation half of R5 (`CLAUDE_MSYS_TELEMETRY`
    unset, sink absent, so `record()` is a no-op), criterion 11's vacuous pass, and 3 required
    artifacts (`ARTIFACT-MANIFEST.json`, `ROLLBACK.md`, `EVENTS.jsonl`). **None of these is in any
    register or backlog** — which is precisely the unreported open lane D2 was sent to find. Filing
    them is unowned.
17. **Mermaid diagrams were never rendered** (A3's R-A25 residual; D1's N4/N5 add the byte facts). The
    settling probe is named in `diagrams/README.md` and was run by nobody, so a syntax error would
    still be undetected.
18. **The semantic (embedding) near-dup scan** — D1's own declared residual — is still NOT RUN.

---

## 6. Probes written by this lane (read-only, gitignored scratch)

- `command-center/_synth_probe.py` — register enumeration, state histogram, `R-A03` dependents, owner
  gates, `owner_questions`.
- `command-center/_synth_probe2.py` — precise `items[]` status/disposition histogram with a
  duplicate-id control; the Q22 validator-candidate `Test-Path` pair.

**Access method, disclosed:** both are ignored by `.gitignore:70` (`command-center/_*.py`), so they
exist in my working tree only and a fresh clone will not have them. Every number above is
reproducible from the commands and file paths cited; the scripts are the recipe, not the evidence.
I wrote nothing else. `git diff --name-only` attributable to this lane: **none**.