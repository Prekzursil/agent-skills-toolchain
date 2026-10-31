---
title: PHASE9-COORDINATION
type: note
permalink: dqverify-repo-20261013/platform/coordination/phase9-coordination
---

# Phase 9 — Multi-session and cross-vendor coordination

**Spec anchor:** `C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10965-10983`
**Build root:** `C:/Users/Prekzursil/source/ast-integrate/platform/coordination/` (39 files, 10,307 lines)
**Status: COMPLETE and MEASURED.** Every row below carries the command that produced it.

Companion documents: `ABSTRACTION-LEAKS.md` (the spec's line-10981 requirement, 12 leaks) and
`ADAPTER-CONTRACT.md` (the dispatch contract and the three-way contradiction resolution).

---

## 1. The eleven required surfaces (spec lines 10969-10981)

| # | Requirement | Module | Tests | Verdict |
|---|---|---|---|---|
| 1 | session discovery | `session.py` | `test_session.py` (20) | CONFIRMED |
| 2 | work claims | `claims.py` | `test_claims.py` (24) | CONFIRMED |
| 3 | file leases | `leases.py` | `test_leases.py` (27) | CONFIRMED |
| 4 | conflict detection | `leases.py` (`detect_conflicts`) | `test_leases.py` | CONFIRMED |
| 5 | duplicate-work suppression | `claims.py` (id + fingerprint) | `test_claims.py` | CONFIRMED |
| 6 | crash recovery | `recovery.py` | `test_recovery.py` (15) | CONFIRMED |
| 7 | handoff | `handoff.py` | `test_handoff.py` (20) | CONFIRMED |
| 8 | shared completion reducer — **REUSED, not rewritten** | `reducer.py` → `platform/lib/completion_predicate.py` | `test_reducer.py` (17) | CONFIRMED |
| 9 | capability negotiation | `capability.py` + `CAPABILITY-REGISTRY.json` | `test_capability.py` (14) | CONFIRMED |
| 10 | vendor-specific adapter boundaries | `adapters.py` + `ADAPTER-REGISTRY.json` | `test_adapters.py` (18) | CONFIRMED |
| 11 | explicit documentation of abstraction leaks | `ABSTRACTION-LEAKS.md` (L-01..L-12) | `test_docs.py` (12) | CONFIRMED |

Supporting: `store.py` (atomic records + append-only journal), `oslock.py` (the second liveness
signal), `dispatch.py` (completion AND-gate + 13-check plan audit), `simclock.py`, `errors.py`.
Executable controls: `liveness_control.py`, `single_reducer_gate.py`, `normalize_eol.py`,
`lock_probe_child.py`.

`test_docs.py::test_all_eleven_required_surfaces_map_to_a_real_module` asserts this table's
file mapping mechanically, and `test_integration.py` walks all eleven in ONE end-to-end journey
(14 numbered stages) so composition is proven, not just per-module isolation.

---

## 2. Measurements

```
$ python -m pytest platform/coordination -q
231 passed in 6.19s

$ python -m pytest platform/coordination platform/lib -q
3257 passed, 14 skipped in 177.81s

$ python platform/coordination/single_reducer_gate.py
SUCCESS:single-reducer modules=33 delegate=completion_predicate violations=0

$ python platform/coordination/single_reducer_gate.py <tree containing a second plane>
FAILED:single-reducer second_plane.py:1 CONDITIONS - module-level definition ...
FAILED:single-reducer second_plane.py:2 evaluate  - module-level definition ...
FAILED:single-reducer modules=1 violations=2 delegate=completion_predicate     [exit 1]

$ python platform/coordination/single_reducer_gate.py <empty dir>
FAILED:single-reducer modules=0 violations=0 delegate=completion_predicate     [exit 1]

$ python platform/coordination/liveness_control.py
"all_discriminate": true          B_state_alive=HELD-BY-OTHER  B_state_dead=FREE
                                  B_state_absent=NOT-COMPUTABLE
combined: fresh+held=LIVE  stale+free=DEAD  stale+held=UNVERIFIED  fresh+free=UNVERIFIED

$ ruff --version && ruff check platform/coordination/ && ruff format --check platform/coordination/
ruff 0.15.17 (CI's pin)          All checks passed!          33 files already formatted

$ python platform/coordination/normalize_eol.py --check
SUCCESS:normalize-eol files=38 crlf_fixed=0 worktree==blob for every file
```

### Baseline, and the correction to the pinned number

The pinned baseline of **2,767** is STALE. Measured with `python -m pytest platform -q` before this
unit wrote anything: **3071 passed, 14 skipped, 0 failed** (200.16 s). Sibling defect units
independently measured 2812 / 3026 / 3064 / 3067 as the D-series landed, so the drift is
accounted for.

### The full-platform number is CONFOUNDED — stated rather than smoothed over

Two full-suite runs during this build:

| run | result | attribution |
|---|---|---|
| mid-build | 3692 passed, 14 skipped, **0 failed** | clean |
| final | 3693 passed, 14 skipped, **1 failed, 12 errors** | **all 13 in `platform/marketplace/mkt/test_gates_are_load_bearing.py`** — a sibling lane's file, mid-write during collection |

`grep -cE "^(FAILED\|ERROR).*coordination" PHASE9-SUITE.txt` → **0**. Zero failures in this unit's
surface in either run.

Two honest consequences:

1. **"The full platform suite is green" is NOT a claim this unit can make right now.** It was green
   mid-build and is not green at this instant, and the non-green is entirely outside this surface.
2. **The 3071 → 3693 delta cannot be attributed to this unit.** This package contributes exactly
   **231** tests (counted by `--collect-only`). The remaining ~390 came from concurrently-building
   sibling lanes (`platform/plugin`, `platform/marketplace`, `platform/routing` all appeared during
   this build). Any narrative that credits the whole delta to Phase 9 would be false.

---

## 3. The three-way dispatch contradiction — resolved, and the resolution is a DECISION

The estate's own documents cannot all be obeyed literally, and the collision is **internal to one
file**: `rules/common/cross-vendor-dispatch.md:9` bans `run_in_background` for a barrier-awaited
dispatch, while `:64-66` of the same document mandates `longrun`, whose documented behaviour
(`~/.claude/agents/codex.md:52-55`) is to background its child — and `AGENTS.md:59-64` §4a requires
exactly that above 60 s.

**Resolution adopted: transport and contract are different axes.** Read against its own bullets 2-3
(*"NEVER return a job id … as a work-unit result"*; *"a backgrounded job's result is unreachable …
`sessionId: null`"*), the ban is about the RESULT CHANNEL and the CALLER'S RETURN CONTRACT, not
about OS process topology. So: **logical contract = BLOCKING BARRIER (non-negotiable); transport =
detachment permitted WITH a declared barrier; result channel = a file the dispatcher reads itself;
prompt delivery = a runner script owns the redirect.**

Encoded as data in `dispatch.RESOLUTION` and enforced by `dispatch.audit_plan`'s 13 checks.
`test_dispatch.py::test_every_audit_check_is_reachable` proves each of the 13 can actually fire
(a rule nothing can trip is a dead rule), and the historical `wf_82c5b350-9ba` plan trips 7 of them.

**This narrows a standing estate rule and therefore needs owner ratification.** It is an
interpretive decision, argued from the rule's own evidence, not a measurement — see
`ADAPTER-CONTRACT.md` §1 and `ABSTRACTION-LEAKS.md` L-01/L-02, which record that the transport's
process topology leaking into the prompt-delivery contract IS the abstraction leak the spec asks to
be made explicit.

---

## 4. Degrade loudly and preserve the work artifact (spec line 10983)

Both halves are tested, because an exception handler naturally satisfies the first and drops the
second.

- **Loud:** a refused capability raises typed `CapabilityUnavailable` (adapter id + capability id +
  preserved paths), never a falsy return. `DegradedOutcome.terminal_state` is `BLOCKED` — never
  `FAILED` (which would claim the work was attempted) and never `SUCCESS`; `ok` is a read-only
  property so no construction path can flip it.
- **Preserved:** `test_recovery.py::test_execute_preserves_the_artifact_bytes` and
  `test_handoff.py::test_accept_transfers_the_claim_and_preserves_bytes` compare SHA-256 before and
  after. A MISSING artifact stays on the record and turns the outcome unclean rather than being
  dropped from the list.
- **No silent substitution:** `route()` returns every candidate's negotiation and has **no `chosen`
  field**. `gemini-cli` is registered with empty `offers` AND empty `refuses` on purpose, so it
  refuses every unit with reason `capability-unmeasured` instead of inheriting another vendor's
  capability list — the interchangeability lie, made structurally impossible.

---

## 5. Defects found and fixed DURING this build

| what | how it surfaced | fix |
|---|---|---|
| Cross-host liveness: probing an OS lock for a session registered on another host would read `FREE` = DEAD and reap a live remote session | enumerating leaks for L-06 | `classify` compares `record.host` to `gethostname()` and returns UNVERIFIED; `test_session.py::test_a_session_from_another_host_is_unverified_never_reaped` |
| `accept_handoff` vacated the outgoing claim BEFORE validating the work definition, so a refused handoff would leave the unit unowned | 7 red tests | all refusals moved ahead of every mutation; asserted by comparing the claim record before/after a refusal |
| `FINGERPRINT_MISMATCH` was skipped for VACANT claims, so `takeover=True` could inherit one unit's artifacts under another unit's contract | reading the branch while fixing the above | mismatch checked before the vacant branch and explicitly not waivable by `takeover` |
| 6 files silently became **CRLF** (Python's default text-mode write on Windows) while the rest stayed LF — the `windows-shell.md` §8b class, where a local formatter green measures the wrong bytes | `ruff format --check` diff | `normalize_eol.py`, which normalises AND proves working-tree bytes == the git blob via `git hash-object --path` + `git cat-file` (never `git archive`, which returns CRLF here) |
| 3 doc-drift problems: 5 leaks documented but uncited in code, all 13 audit codes undocumented, and the gate's own anchor splitter turned `C:/…/AGENTS.md:59-64` into `C` | `test_docs.py`, on its first run | citations added to the modules, a 13-row code table added to the contract, and a `_ANCHOR_TAIL` regex with its own control test |

The last row is the point of the doc gate: it caught a bug **in itself** on first execution.

---

## 6. Declared limitations — NOT-CHECKED, with the settling experiment

| id | limitation | experiment that would settle it |
|---|---|---|
| L-12 | the POSIX (`fcntl.flock`) branch of `oslock` is unexercised; only win32 `msvcrt.locking` is measured | run `liveness_control.py` under WSL / linux CI and require `all_discriminate: true` |
| L-08 | claim TAKEOVER is read-then-write, not compare-and-swap; two sessions could both take one abandoned claim | a concurrency harness with N sessions racing one abandoned claim |
| L-05 | file leases are ADVISORY — a non-participating writer is not stopped | instrument a real multi-agent wave and count writes to leased paths by non-participants |
| L-07 | lease-key case folding is a filesystem property; a store written on Windows and read on Linux would fold differently | create a store on Windows, read it from WSL, check for two keys naming one file |
| — | every `codex-cli` capability value is LEDGER-RECORDED from the 2026-07-18 rail smoke-test and was **NOT re-measured here** (`verified_by_this_unit: false` on all 14, asserted by a test) | re-run the named probe against the current codex-cli build |
| — | no fully-COMPLETE 12-condition receipt fixture was driven through `reduce_claim`; the delegate's own suite covers reaching COMPLETE, and object identity (`evaluate is completion_predicate.evaluate`) carries it | build a 12-condition receipt fixture and assert COMPLETE through `reduce_claim` |

## 7. Owner decision needed

**L-11 — a BLOCKED unit has no legal catalog disposition.** `platform/schema/receipt.schema.json`
gives `terminal_state` seven values including `BLOCKED`, but `disposition` has exactly three:
`DONE-VERIFIED`, `DROPPED-BY-OWNER`, `SUPERSEDED`. The degrade-loudly path produces `BLOCKED`, and
every available disposition is wrong (`DROPPED-BY-OWNER` attributes the decision to the owner;
`SUPERSEDED` implies a replacement). Nothing was mapped: `DegradedOutcome` carries no `disposition`
field at all, so no value is fabricated. Adding one is a catalog-contract change, outside this
unit's surface.

**The §3 resolution narrows `cross-vendor-dispatch.md` §1** from "never `run_in_background`" to
"never UNBARRIERED". Argued from the rule's own evidence and fully documented, but it is a change to
a standing cross-tool rule and should be ratified (or the rule amended) rather than left as a
subagent's reading.