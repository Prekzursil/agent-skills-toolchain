---
title: P13-BLINDSPOT-REVIEW
type: note
permalink: dqverify-repo-20261013/command-center/p13-blindspot-review
---

# P13 — Completeness and Blind-Spot Review

- **Unit:** `depth/p13-blindspot`
- **Spec:** `_USER-PROMPTS.md:11066-11082`
- **Status:** MEASURED — all 11 spec questions answered; Q01 is the one deliberate NOT-CHECKED
- **Date:** 2026-08-10
- **Receipt:** `command-center/receipts/BLD-0023.json` — validates against
  `blindspot-register.schema.json` with 0 errors from the repo's own resolver, and 5 seeded
  mutants of it are all REJECTED (so the validation is load-bearing, not a rubber stamp)

> Every count below states its search scope. `NOT-CHECKED` means I did not probe, never
> "probed and clean". Two of my own detectors over-counted and were corrected in place —
> those corrections are recorded, not silently dropped.

## COVERAGE

| Spec question | State |
|---|---|
| Q01 what files were never read | PARTIAL — proxy measured, no transcript read-ledger |
| Q02 what clients were never tested | CONFIRMED |
| Q03 what platforms were never tested | CONFIRMED — Linux run completed, 24 failures |
| Q04 what owner requirements disappeared | CONFIRMED |
| Q05 what option IDs were silently dropped | CONFIRMED (no new drop found) |
| Q06 what failures were normalized away | CONFIRMED |
| Q07 what unknowns remain | CONFIRMED (13 carried, none retired) |
| Q08 what existing work was ignored | CONFIRMED |
| Q09 what test could falsely pass | CONFIRMED (latent, not live) |
| Q10 what threat actor was not modeled | CONFIRMED |
| Q11 what would break at 10x scale | PARTIAL |

---

## HEADLINE — the 2,007-unit catalog is an ORPHANED PLAN

**1 of 2,007 catalogued work units has produced the artifact it declared.** Not "a few
hundred executed" — one.

Two mechanically independent signals:

| signal | method | result |
|---|---|---|
| S1 | per-path `stat()` + non-emptiness over every `work_unit.output_path` | 1 present / 2,006 absent |
| S2 | **set intersection** of the 2,007 declared paths against 8,911 git-tracked files | 1 |
| S2b | same intersection against the program's own `ARTIFACT-MANIFEST.json` | **0** |

The one survivor is `command-center/wfa/schema/wfa-schema-pack.json` (WFA-1, phase 1).

The catalog carries **no** status/disposition/receipt field on any of the 2,007 units (20
fields present on 2007/2007; `execution_substrate` is a *plan* field), so the program has no
ledger that could answer "what was dropped". On-disk output existence is the only
mechanically independent execution signal that exists.

**Entire expected output directories were never created:** `command-center/receipts` (1,021
units), `adversarial` (144), `design/council` (128), `research` (128), `confirmation` (127),
`audit` (96), `foundry` (32), `synthesis` (25), `phase3/A1..A9` (7 each).

Delivered work is real (8,911 tracked files, a green local suite, plugin/marketplace/routing
all shipped) — it simply lives in a **different path namespace the catalog never
references**. That disjointness, not idleness, is the blind spot: the plan and the delivery
cannot be reconciled by any artifact in the repo.

Detector controls for S1 (all four passed before any count): known-present file → PRESENT;
known-present directory → PRESENT; known-absent path → MISSING; known-present-but-EMPTY file
→ MISSING.

Evidence: `command-center/P13-EXECUTION-GAP.json`, `command-center/P13-ORPHAN-PLAN.json`.

---

## Q03 — what platforms were never tested

**CONFIRMED, and worse in both directions.**

- **The entire `platform/` tree has ZERO CI coverage.** `platform/` appears **0 times** in
  all 7 workflow files. Detector control: `command-center`→5 hits, `monitorcore`→22,
  `mcpctl`→28 in the same grep, so the zero is real, not a broken matcher. `ci/` likewise
  contains no `platform/` reference. The ~3,847-test baseline is a hand-run,
  single-Windows-box number that **no automated gate anywhere reproduces**.
- **All 13 CI jobs are `runs-on: ubuntu-latest`.** Zero `windows-latest`, zero
  `macos-latest`, no matrix — so the pre-existing packages that *are* gated are gated on
  Linux only, while the program was authored and exercised only on Windows.
- **macOS: never exercised by any route.** The plugin manifest schema explicitly admits
  `platforms: enum ["windows","macos","linux"]` (`platform/plugin/schemas.py:711-716`), so
  cross-platform support is a *declared* capability with no macOS evidence of any kind.
- Spec Phase 12 requires a dedicated **"cross-platform behavior"** refuter
  (`_USER-PROMPTS.md:11050`). All 144 phase-12 ADV units produced nothing.

### Linux measured, not asserted — and the root cause is worse than portability

I ran the full suite on Ubuntu 24.04 / Python 3.12.3 (WSL2), pytest 8.3.3:

| | failed | passed | skipped | collected |
|---|---|---|---|---|
| **Linux (measured here)** | **24** | 3,875 | **37** | 3,936 |
| Windows (carried baseline) | 0 | 3,847 | 14 | 3,861 |

`24 failed, 3875 passed, 37 skipped in 706.79s (0:11:46)`, exit 1. Consistency check: the
summary's 24 equals the 24 parsed `FAILED` lines (a self-disagreeing count would be a
detector failure, so the script refuses to emit unless they match). **22 of 24 failures are
`platform/routing`, 2 are `platform/coordination`.**

Control: `platform/plugin` on the *same* Linux interpreter gives **252 passed** — a disjoint
subpackage is clean, so a blanket "the build breaks on Linux" is **REFUTED**. The failures are
localised.

**Root cause — CONFIRMED, two independent signals.** `platform/routing/index.py:55` reads

```python
HOME = Path(os.environ.get("ROUTING_HOME") or Path.home())
```

and `:93-97` binds `skills`/`agents`/`commands` under it. **The capability corpus under test is
the operator's LIVE `~/.claude` harness, not a committed fixture.** Measured: Windows
`~/.claude` holds **27 agents / 71 commands / 79 skills**; the Linux `$HOME` holds
**0 / 0 / 0**. Linux therefore indexed **383** records and the test's own guard fired:
`corpus implausibly small (383); the walk is probably broken` (`assert 383 > 800`).

Three consequences:

1. **The Phase 8 headline numbers are machine-specific.** "912 capabilities indexed" and every
   derived precision/recall and bytes-per-query figure are properties of *this one box*, not of
   the repo. They are not reproducible on any other host.
2. **This structurally explains the missing `platform/` CI lane.** Those ~21 tests *cannot*
   pass on a runner with no `~/.claude` harness. The absent CI is forced by the design, not
   merely forgotten — which makes BS-03 a design fix, not a config fix.
3. **A fix seam already exists and is unused:** `ROUTING_HOME` is honoured at `index.py:55` and
   no test sets it. Pointing it at a committed fixture makes the lane hermetic
   (`ci-hygiene.md` §2: assert against a committed snapshot, never live state).

**Credit where due:** the routing tests are *well* designed — they assert the POSITIVE form
("N of N", plus an explicit implausibly-small floor), which is precisely why the coupling
surfaced instead of passing vacuously on a 383-record corpus.

Not attributed to that root cause, and **not individually triaged** (residual unknown):
`coordination/test_docs.py::test_every_resolution_source_anchor_points_at_a_real_file`,
`coordination/test_leases.py::test_backslash_and_case_fold_on_windows`, and
`routing/test_descriptions.py::test_corpus_stats_reports_a_real_length_distribution`.

**The one CI job named for routing tests a different router.** `routing-benchmark.yml:53-55`
runs `hooks/harness-bench/*` and `hooks/semantic-router/test_eval.py` — the **pre-existing**
router — and never touches `platform/routing`. Its regression probe at `:95-97` is
`continue-on-error: true`. Corroborating this as a genuine two-implementation split rather
than a naming quirk: register item **T-13**, the `DONE-VERIFIED` "Phase 8 fully shipped"
claim, cites `hooks/semantic-router/{route,embed,build_index,eval,intents,observe,success}.py`
— the older tree. So the completion evidence and the Phase 8 build point at **different
codebases**, and CI gates the one that is not the deliverable, fail-open.

Full data: `command-center/P13-LINUX-SUITE.json`.

## Q02 — what clients were never tested

**CONFIRMED.** The plugin/marketplace surface names exactly two clients: `claude-code`
(12 occurrences) and `antigravity` (1). Codex/OpenAI is a first-class vendor throughout the
program (48 protocols, cross-vendor refuters, `mcp__codex__*` rails) yet is **not** a tested
install target. `min_client`/`max_client` semver gating exists
(`platform/plugin/schemas.py:709-710`) but no test exercises a client other than
`claude-code`. Cursor / Windsurf / Zed / Continue / Copilot: zero references, zero tests.

## Q04 — what owner requirements disappeared

**CONFIRMED — the three owner-input slots in the governing spec were never filled.**

| spec line | slot | state today |
|---|---|---|
| 10516 | `[PASTE SELECTED OPTION IDS HERE]` | still literal |
| 10520 | `[PASTE OWNER OVERRIDES HERE]` | still literal |
| ~10524 | `[PR-ONLY / PRIVATE CANARY / PUBLIC MARKETPLACE RELEASE — choose or ask]` | still literal |

**All 27 owner questions are OPEN. Zero answered** (`OWNER-DECISIONS.md:5` — "27 open of 27").

Two consequences the program has been running on without an owner decision:

1. **OQ-3 (release mode) is OPEN** and `OWNER-DECISIONS.md:32` records that "Phase 15
   branches entirely on it". My wave brief states "Release mode PR-ONLY is binding" — I
   could find **no owner decision record** for that anywhere in `command-center/`. On the
   evidence, PR-ONLY is an **executor assumption**, not an owner selection. I am flagging
   the contradiction rather than adopting either side (AGENTS.md §7).
2. **OQ-4 is OPEN:** "Was the 38-item harness tranche an APPROVED substitute for the
   ≥2,048-unit Prompt Two? **No approval record exists anywhere I searched.**"
   (`OWNER-DECISIONS.md:33`.) This is the direct owner-facing form of the headline finding:
   a scope substitution of 2,048 → a few dozen units, never approved, never recorded.

## Q05 — what option IDs were silently dropped

**CONFIRMED, and the answer is "none newly".** `OPTION-ID-RESOLUTION.json` already measured
this lane: 283 options, MD↔JSON symmetric difference **0**, no title mismatches, 70
owner-decided in exact agreement across three independent encodings. The historic 31-way
`M-NN` collision was re-prefixed to `MECH-NN`. Residual (that lane's, re-stated not
re-measured by me): `17-DECISION-LOG.md:175` still describes the collision in present tense.
The live gap is not dropped IDs — it is that **OQ-1 was never answered, so no option ID was
ever *selected*.**

## Q06 — what failures were normalized away

**CONFIRMED.** Full suppression-construct census over 355 in-scope deliverable files
(`platform`, `command-center`, `.github/workflows`, `ci`, `tools/command-center`; 321
underscore-prefixed scratch files excluded; 13 regex patterns, each proven to fire on a
known-positive and stay silent on a known-negative line before any count):

| construct | count | note |
|---|---|---|
| `# pragma: no cover` | 112 | coverage tooling deliberately blind to these branches |
| `pytest.skip(...)` | 33 | mostly "artifact absent" guards — see Q09 |
| `\|\| true` | 16 | 9 of them in CI |
| `2>/dev/null` \| `2>$null` | 8 | |
| `\|\| echo` | 7 | |
| `contextlib.suppress(` | 5 | |
| `pytest.mark.skipif` | 4 | |
| `pytest.mark.skip` / `bare except:` / `-ErrorAction SilentlyContinue` | 2 each | |
| `pytest.mark.xfail` | 1 | |
| **TOTAL constructs** | **488** | |

**Two of my own counts were wrong and are corrected here, not quietly dropped:**

- `except…:` matched **290** lines, but that regex matches *every* except clause including
  correct handlers. Narrowed to handlers whose body is literally `pass`/`...`/`continue`:
  **29**, and most of those sit in scratch `wave3_*` audit scripts and `ci/harness/ledger.py`,
  not in the shipped `platform/` library.
- `continue-on-error: true` matched **3**, but **2 are inside YAML comments**
  (`codex-runner.yml:319,323`). Exactly **1 is live**:
  `routing-benchmark.yml:96`, on a step self-labelled "shadow" — legitimately advisory.
  This is the use-vs-mention trap firing inside the tool built to find it.

## Q09 — what test could falsely pass

**CONFIRMED as a latent mask; REFUTED as a live one.** The dominant shape is
*absence-is-not-failure*:

```python
# platform/lib/wfdsl/test_catalog_conformance.py:33-34
if not CATALOG.is_file():  # pragma: no cover - environment guard
    pytest.skip(f"catalog not present at {CATALOG}")
```

If the artifact a test exists to validate disappears, the test **skips** — the suite still
reports success. The same shape guards "the certified fusion has not been emitted", "no
forged artifacts on disk", "the executable blueprint corpus is not populated yet", and four
`test_schema_resolver.py` sites that skip with the reason *"not in HEAD; cannot verify
(NOT-CHECKED)"*.

Correctly scoped: **right now none of these fire** — a targeted run of the guarded modules
gave **221 passed, 0 skipped**, so nothing is currently being masked. The risk is latent and
compounds with Q03: the guard branch carries `# pragma: no cover`, so a 100%-coverage claim
cannot see it, and because `platform/` has **no CI at all**, a deletion that flipped 100+
conformance tests from PASS to SKIP would be caught by nothing.

My first attempt to prove this by in-process monkeypatching **failed twice** and returned
`masks_found=0`. That zero was a **detector failure, not a finding** (`platform/` shadows the
stdlib `platform` module, so the import never resolved). I pivoted per AGENTS.md §4b rather
than trying a third variant; the source text above plus the real 221/0 run are the evidence.
The un-run experiment that would settle the live case: delete `WORK-UNIT-CATALOG.json` in a
throwaway clone and confirm the suite stays green — **NOT-CHECKED**, deliberately not run
against the working tree.

Independent of the above, `UNKNOWNS-REGISTER.md` U-4 records that **only 7 of 46 named
failure classes are demonstrably seeded as regressions**; the other 39 are unmeasured. That
is a carried claim I did **not** re-verify.

## Q07 — what unknowns remain

**CONFIRMED: 13 unknowns (U-1…U-13) are on the register and not one has been retired.**
`UNKNOWNS-REGISTER.md` is well-formed — each row names its settling experiment. Load-bearing
ones: U-1 (the OQ-4 approval question), U-4 (39/46 failure classes unseeded), U-8
(**everything** marked `[inherited]` was never re-probed by its own author), U-13 (live vs
repo harness copy never compared).

Beyond the register, **Phase 13's own contracted artifact does not exist.** Three schemas
ship with **zero instances anywhere in the repo** — `blindspot-register.schema.json`,
`contradiction-register.schema.json`, `prior-art-register.schema.json`. Seven catalogued
units (BLD-0001, 0003, 0018, 0023, 0025, 0026, 0027 — all phase 13) declare
`blindspot-register` as their `output_schema`. None ran. This review is the first execution
of the phase, and it emits the missing instance (below).

## Q08 — what existing work was ignored

**CONFIRMED.** The repo already contains the machinery the program re-implemented around:
`UNKNOWNS-REGISTER.md`, `RISK-REGISTER.md`, `OPTION-ID-RESOLUTION.json`, `CLAIM-REGISTRY.json`,
`TEST-REGISTRY.json`, `COMPLETION-GATES.json`, `DEPENDENCY-GRAPH.json` and a
`tools/command-center/close.py` + `render.py` pipeline whose generated header
(`OWNER-DECISIONS.md:1`) says dispositions are closed by running `close.py` and re-rendering.
**That pipeline was never used for the 2,007 units** — hence zero receipts and no disposition
field. The 103-item register has the disposition machinery; the 2,007-unit catalog does not
use it.

Also ignored: the 2,048-unit target itself. `work_units_meta` records `target: 2048`,
`work_unit_count: 2007`, `shortfall: 41` — a declared 41-unit shortfall never closed, on top
of the 2,006 unexecuted.

## Q01 — what files were never read

**PARTIAL.** BLD-0001 specifies the real method — build a read-ledger from every
`Read`/`Grep`/`Glob`/`Bash`-cat path in the session JSONL transcripts and diff it against
declared scope. **I did not build that ledger; no transcript read-ledger exists.** Reported
as NOT-CHECKED rather than approximated, because a proxy here would be indistinguishable
from the real answer while being wrong.

What I can state from structure: the corpus at
`harness-sota-2026-07-18-corpus` holds **610 tracked files** and the spec restricts reading
to `_USER-PROMPTS.md:10473-11437` of a **~11,400-line** file, so ~90% of the governing
prompt document is out of declared scope by construction. `platform/corpus/test_corpusnorm.py:51`
carries a `corpus_present` skipif, i.e. corpus tests are themselves conditionally inert.

## Q10 — what threat actor was not modeled

**CONFIRMED.** The spec requires a threat model "covering all six STRIDE categories" and 14
distinct Phase-12 refuter lenses (`_USER-PROMPTS.md:11044-11060`) — correctness, stale
assumptions, security, privacy, legality, supply chain, cross-platform, performance,
operational recovery, marketplace abuse, workflow prompt injection, source manipulation,
benchmark gaming, synthesis distortion.

**No STRIDE threat-model artifact exists.** `STRIDE` appears only in catalog *declarations*
(`catalog-slices/ADV-1.json`, `BLD-1.json`, the catalog itself) and one unrelated
design command — never as a produced deliverable. All 144 phase-12 ADV units produced
nothing, so **all 14 refuter lenses are unexecuted as catalogued**.

Specifically unmodeled, with a live counterpart already found by a sibling lane: the
`verify/marketplace-lifecycle` unit CONFIRMED two revocation escapes (a stale offline bundle
import that *deletes* the destination revocation list, and a `verify-always` mirror serving a
revoked version). That is the **malicious/compromised publisher + stale-mirror** actor — the
exact actor class the missing marketplace-abuse refuter was meant to own.

The actor I judge least modeled: **the operator's own fan-out.** A grep hit in the catalog
states it directly — *"a threat model that excludes the operator's own fan-out is incomplete
by construction"* — and it connects to the live authorization gap below.

**Open owner decision, not silently gated:** 239 of 261 units holding an `mcp__` token are
UNAPPROVED — `tool_policy.require_owner_approval` lists only `Task` and `AskUserQuestion`
(catalog `tool_policy`: default `deny`, 57 allow, 19 deny, 2 require-approval). Surfacing per
the D2 lane; **this is an owner decision, not mine to close.**

## Q11 — what would break at 10x scale

**PARTIAL.** Measured structural facts, not a load test (no load test was run — NOT-CHECKED):

1. **The catalog is a 5.36 MB single JSON blob** read whole (`json.loads` of the entire file)
   by conformance tests, the schema resolver, the authorization gate and the renderer. At 10x
   (20,070 units, ~54 MB) every one of those becomes a full-file parse per invocation. There
   is no index, no streaming reader, and no pagination anywhere in the catalog path.
2. **`platform/` shadows the Python stdlib `platform` module.** Proven, not inferred: a
   dotted import raises `No module named 'platform.lib'; 'platform' is not a package`. It is
   survivable *only* because no `__init__.py` exists. Any future packaging step that adds one
   would shadow stdlib `platform` process-wide — a latent, high-blast-radius packaging defect.
3. **Suite wall-clock is already the binding constraint:** ~211 s on Windows for ~3.0k tests,
   and the same tree on Linux over `/mnt/c` took **~2 min for the 252-test plugin subset
   alone**. With zero CI, 10x the units means a hand-run suite nobody will run.
4. A hard-killed plugin install **wedges the prefix for 1 hour** (sibling
   `verify/plugin-lifecycle` finding). At 10x install concurrency that becomes the dominant
   failure mode.

---

## BLIND-SPOT REGISTER — work unit or accepted residual risk

Owner named as acceptor for every accepted risk: **Prekzursil**. Nothing below is closed by me.

| # | blind spot | severity | disposition |
|---|---|---|---|
| BS-01 | 2,006 of 2,007 catalogued units produced nothing; no reconciliation exists between plan and delivery | P0 | **WORK UNIT** — either execute, or formally supersede the catalog with the delivered scope and record the substitution |
| BS-02 | Scope substitution (2,048 → a few dozen units) never approved (OQ-4) | P0 | **OWNER DECISION** — cannot be closed by any agent |
| BS-03 | `platform/` has zero CI on any OS; the 3,847-test green is hand-run and unreproducible | P0 | **WORK UNIT** — add a `platform/` pytest lane |
| BS-04 | CI is `ubuntu-latest` only (13/13 jobs); Windows and macOS ungated | P1 | **WORK UNIT** — OS matrix, at minimum windows+ubuntu |
| BS-05 | Linux full-suite failures (~25 observed, run in flight) | P1 | **WORK UNIT** — triage once `P13-LINUX-SUITE.json` lands |
| BS-06 | macOS never exercised, yet declared in the manifest platform enum | P2 | **ACCEPTED RISK (owner: Prekzursil)** — no macOS hardware on this estate; remove `macos` from the enum or accept it as unvalidated |
| BS-07 | Release mode is an executor assumption; OQ-3 open | P1 | **OWNER DECISION** |
| BS-08 | 3 spec owner-input placeholders still literal; 27/27 owner questions open | P1 | **OWNER DECISION** — send as one batch per `OWNER-DECISIONS.md:5` |
| BS-09 | 0/103 register receipts exist; 26 items are DONE-VERIFIED with inline prose evidence but no schema-valid receipt | P1 | **WORK UNIT** — run `close.py` to emit receipts; the evidence exists, the machine-checkable artifact does not |
| BS-10 | No STRIDE threat model; all 14 Phase-12 refuter lenses unexecuted | P1 | **WORK UNIT** |
| BS-11 | 239/261 `mcp__`-bearing units unapproved | P1 | **OWNER DECISION** (D2 lane) |
| BS-12 | Absence-is-skip test guards (33 `pytest.skip`) + 112 `# pragma: no cover`, invisible to coverage and to nonexistent CI | P2 | **WORK UNIT** — convert artifact-absence guards from `skip` to `fail` for artifacts the program claims to produce |
| BS-13 | Only 7 of 46 named failure classes seeded as regressions (U-4, not re-verified by me) | P2 | **WORK UNIT** |
| BS-14 | Codex/OpenAI is a first-class vendor but never a tested install client | P2 | **WORK UNIT** |
| BS-15 | No transcript read-ledger, so Q01 is genuinely unanswerable today (BLD-0001) | P2 | **ACCEPTED RISK (owner: Prekzursil)** unless BLD-0001 is executed |
| BS-16 | 5.36 MB monolithic catalog parsed whole on every consumer path | P2 | **ACCEPTED RISK (owner: Prekzursil)** at current scale; blocks 10x |
| BS-17 | `platform/` shadows stdlib `platform`; safe only because no `__init__.py` exists | P2 | **WORK UNIT** — rename, or add a guard test asserting no `__init__.py` |
| BS-18 | 41-unit declared shortfall against the 2,048 target, never closed | P3 | **ACCEPTED RISK (owner: Prekzursil)** |
| BS-19 | `contradiction-register` and `prior-art-register` schemas ship with zero instances | P3 | **WORK UNIT** |
| BS-20 | `ARTIFACT-MANIFEST.json` lists itself with `bytes: 0, sha256: "(self)"` — cannot verify itself | P3 | **ACCEPTED RISK (owner: Prekzursil)** |
| BS-21 | **`platform/routing` is measured against the operator's live `~/.claude`, so Phase 8's numbers are machine-specific and no CI runner can ever pass those tests.** A `ROUTING_HOME` seam exists and is unused | P1 | **WORK UNIT** — commit a fixture corpus and set `ROUTING_HOME` in the routing conftest |
| BS-22 | **`routing-benchmark.yml` gates `hooks/semantic-router`, not `platform/routing`, fail-open (`continue-on-error: true`).** Two routers exist and T-13's DONE-VERIFIED evidence cites the older one | P1 | **WORK UNIT** — decide which router is the deliverable, retire or gate the other |
| BS-23 | **The receipt predicate cannot express "an audit unit that correctly found defects".** `state: SUCCESS` is forbidden while any P0/P1 defect is open and until an independent reviewer records PASS — so the 144 phase-12 refuter units and 7 phase-13 blindspot units are structurally unable to emit a SUCCESS receipt when they do their job. Proven empirically: this receipt with `state: SUCCESS` drew exactly 7 refusals naming those clauses | P2 | **WORK UNIT** — add an audit/refutation receipt profile whose success criterion is *evidence quality*, not *absence of findings* |

## Artifacts

| path | contents |
|---|---|
| `command-center/P13-BLINDSPOT-REVIEW.md` | this review |
| `command-center/P13-BLINDSPOT-REVIEW.json` | machine-readable companion |
| `command-center/receipts/BLD-0023.json` | schema-conforming blindspot-register receipt |
| `command-center/P13-EXECUTION-GAP.json` | S1: per-path execution measurement + 4 controls |
| `command-center/P13-ORPHAN-PLAN.json` | S2: set-intersection corroboration |
| `command-center/P13-SUPPRESSION-CENSUS.json` | 488 constructs, 13 controlled patterns |
| `command-center/P13-SKIP-MASK-PROOF.json` | the failed monkeypatch attempt, retained as a detector-failure record |
| `command-center/P13-LINUX-SUITE.json` | Linux full-suite result (pending) |