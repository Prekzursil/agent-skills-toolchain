---
title: P13-ROUTING-HERMETIC
type: note
permalink: dqverify-repo-20261013/command-center/p13-routing-hermetic
---

# P13 — Routing lane hermeticity

**Unit:** `routing-hermetic` · **Status:** COMPLETE — every section measured

**COVERAGE — MEASURED (all sections):** defect reproduction · fixture build · shrinker losslessness ·
scrub audit · both-states (unit + full suite) · headline-figure delta · adjacent-CI-gate collision ·
lint. **Nothing in this document is unmeasured.**

Residuals that are stated but NOT measured, each flagged inline where it appears: the D-001
dual-write gate could not be run against an uncommitted fixture (§7, its pathspec semantics measured
instead); `MEASUREMENTS.json` was deliberately not regenerated (§6); wiring the lane into a CI
workflow is out of scope (§1). The lane itself has been run on both Windows and Linux (§5).

---

## 1. Defect — REPRODUCED (two mechanically independent signals)

| signal | result |
|---|---|
| Briefed: Linux runner, empty `~/.claude` | 383 records, 22 failures (`command-center/P13-LINUX-SUITE.json`) |
| Mine: Windows, `ROUTING_HOME=<empty tmp>` | 383 records, **the identical 22 failures** |

`platform/routing/index.py:55` binds `HOME`; `Roots.live()` (`index.py:93-97`) hangs five roots off
it. No test and no CI config sets `ROUTING_HOME`.

**Correction to the brief:** the lane is **114 tests**, not 24 — 22 of 114 fail, not 22 of 24.

**Also found:** `platform/routing` has **zero** references in `.github/workflows/` and `ci/`. The
lane is not wired into CI at all today, so the defect has never actually fired in CI. Wiring it is
a follow-up outside this unit's scope.

## 2. Fixture corpus — BUILT and VERIFIED

`platform/routing/fixtures/home/` — 581 files, 2.3 MB, produced by the committed, re-runnable
`platform/routing/fixtures/build_fixture.py`.

| source | fixture | live |
|---|---|---|
| `.agents/skills` SKILL.md | 328 | 328 |
| `.claude/skills` SKILL.md | 79 | 79 |
| `.claude/agents` | 18 | 18 |
| `.claude/commands` | 71 | 71 |
| `.mcp.json` servers | 14 | 14 |
| plugins / with vendor manifest | 98 / 83 | 98 / 83 |
| **TOTAL INDEX RECORDS** | **912** | **912** |

All 34 hand-authored gold ids in `queries.py` resolve; `unresolved_gold == []`.

`.claude/skills` contributes **0 net records** (`skills()` dedups by name, first root wins) but is
kept: a dedup regression would surface as `skill: 407` and blow the floors.

**Shrinker proven LOSSLESS.** Only the bytes the indexer reads are stored — `body[:1500]` plus the
first 14 headings for skills, `body[:900]` for agents/commands — with the cut always *extended* to
the next newline (taking more always satisfies a `[:n]` prefix read; a mid-line cut would silently
re-mine a sliced heading). `verify()` grades this against a second tree built from the same source
with shrinking disabled and the same scrubber, requiring exact equality of `routing_text`,
`desc_source` and `card`. Both sides are scrubbed, so the scrub cancels and any residue is a
shrinker bug. Result: **0 differences, 0 full-copy fallbacks.**

**Floors UNCHANGED — nothing was lowered.** `workflow 97 · protocol 45 · preset 60 · candidate 150 ·
skill 60 · mcp 10 · plugin 5` (`index.py:58-66`), all cleared by the fixture. No assertion in any
test was relaxed.

## 3. Secret / PII scrub — AUDITED

- 67 username replacements (`Prekzursil` → `agentuser`, case-insensitive, plus the `PREKZU~1` 8.3
  form). Independent re-scan of the finished fixture: **31 home-path segments, 100% `agentuser`,
  zero other user names**; `grep -ril prekzursil` → 0 files.
- 0 named-credential matches (OpenAI / Anthropic / GitHub / HF / Slack / AWS / GCP / GitLab / npm /
  JWT / PEM).
- `.mcp.json`: the whole `env` block is **dropped, not redacted** — that is where the live keys sit
  (`EXA_API_KEY`, `FIRECRAWL_API_KEY`, `KAGGLE_KEY`, `MODAL_TOKEN_SECRET`, `RUNPOD_API_KEY`,
  `TAVILY_API_KEY`, `FB_PAGE_ACCESS_TOKEN`, `LIGHTNING_API_KEY`) and `index.mcp()` never reads it.
- 1 high-entropy string REPORTED (never auto-replaced) then inspected by hand:
  `9605648b86c9176283f620b6…` at `fixtures/home/.agents/skills/battlecats-event-unlock/SKILL.md:15`
  — a `so_sha256` content hash of a game binary. **Not a credential.**
- `installed_plugins.json`: `installPath` → `__FIXTURE_HOME__` token, timestamps dropped, only
  `name`/`displayName`/`description`/`keywords`/`version` copied per manifest.
- **For the owner:** a report-only harness sweep raised `POTENTIAL-CREDENTIAL sha256:5b60b42df5e9`
  and `sha256:a22563f06ca5` on my edits. Both fire on files whose content is the *credential-prefix
  regexes themselves* (`build_fixture.py`, `test_fixture_hermetic.py`) — a use-vs-mention match, no
  value present. Surfaced per AGENTS.md §9; no agent action taken.

**Two defects I introduced and fixed** (recorded rather than quietly dropped):
1. The first `emit_mcp` basename'd any argument containing a slash, destroying real routing tokens:
   `@playwright/mcp@0.0.78` → `mcp@0.0.78` (npm scope) and `http://127.0.0.1:9222` →
   `127.0.0.1:9222` (URL scheme). Neither carries user identity. `command`/`args` are now verbatim
   after the username scrub.
2. My first version of `test_the_lane_is_bound_to_the_committed_fixture` was **tautological** — it
   resolved anchors against `$ROUTING_HOME` and asserted they sat under it, which the walk
   guarantees by construction. The mutation run (`ROUTING_HOME=<real home>`, marker forced on)
   **PASSED**, i.e. the guard was blind to exactly the state it exists to catch. It now pins the
   session tree to the committed one by `.mcp.json` content and re-fires correctly.

## 4. `platform/routing/conftest.py`

Renders the fixture to a session temp dir and binds it at conftest MODULE level — before any test
module imports `routing.index` — setting `ROUTING_HOME` **and** rebinding `index.HOME` directly
(`Roots.live()` reads it as a module global at call time, so the rebind survives any import order;
relying on the env var alone would be an import-order bet). `pytest_report_header` prints which
corpus is bound so a hermetic run and a live run can never be confused in a log. Escape hatch:
`ROUTING_FIXTURE=0`.

The render exists for one field only: `index.plugins()` follows `installPath` to a vendor manifest
and an absolute path cannot be committed.

## 5. Both-states control

| state | expectation | measured |
|---|---|---|
| (a) fixture ON, full suite | PASS | **121 passed / 0 failed** in 323s, exit 0 |
| (a2) fixture ON **+ `ROUTING_HOME=<empty>`** | PASS | **22/22** on `test_index.py` |
| (b) `ROUTING_FIXTURE=0` + `ROUTING_HOME=<empty>`, full suite | FAIL w/ corpus guard | **22 failed / 90 passed**, `assert 383 > 800`, "corpus implausibly small (383)" |

(a2) is the sharpest arm: identical empty `ROUTING_HOME` to (b), opposite verdict — so the fixture,
not the host, supplies the corpus. Header confirmed live:
`routing corpus: HERMETIC FIXTURE -> …\routing-fixture-home-…\home`.

### Cross-platform arm — RUN ON LINUX, not inferred

Executed in WSL2 (Ubuntu, **Python 3.12.3 / pytest 8.3.3** vs Windows' 3.14), against the same
checkout, on a `HOME` (`/home/prekzursil`) whose `.claude`/`.agents` are the empty ones that
produced the original 383-record failure:

| Linux state | measured |
|---|---|
| fixture ON | **121 passed** in 298s |
| `ROUTING_FIXTURE=0` | **22 failed / 90 passed / 9 skipped** — the briefed failure set, exactly |

So the lane is green on Linux and red on Linux without the fixture. This also clears the two risks
I had flagged as residual (path-case sensitivity across 581 files, `Path.is_relative_to` on a
POSIX temp dir) and shows the fix is Python-version-portable.

One detector failure worth recording: the first Linux attempt forced `HOME=/tmp/empty` and got
`No module named pytest` — pytest lives in the real `~/.local/lib`, so overriding `HOME` removed the
test runner itself. That output was a broken instrument, not a result, and was discarded rather than
reported.

Guard-test controls: `ROUTING_FIXTURE=0` → 7 skipped (not failed); planted-positive scrub detectors
fire on `C:\Users\somebodyelse`, `/home/realperson`, `ghp_…`, `sk-ant-…`, `AKIA…` and stay silent on
`agentuser`.

## 6. Headline-figure delta — essentially ZERO

Both measured with `cli.py metrics`, one bound to the live tree and one to the fixture. Detector
validated first: the two output files have different sha256, and anchors resolve to
`~\.agents\skills\reframe\SKILL.md` vs `…\p13-fixture-home\.agents\skills\reframe\SKILL.md`.

**Identical on the fixture and the live tree:** 912 capabilities · L1 gold-hit@5 **0.75** · L2
**0.4286** · L4 **0.6** · L3 abstain **0.6667** · real recall **0.5463** · shuffled recall **0.0** ·
flood byte-ratio **297.9×** · tail reachable **53/54** · and every bytes-per-query figure
(k=1 161.9/219, k=3 389.6/657, k=5 494.4/1043, k=10 530.2/1322; saving 7.8-8.5×).

**5 leaves move, all raw byte totals, all from the 1-character-shorter username:**

| leaf | live | fixture |
|---|---|---|
| `always_loaded_baseline.total_always_loaded_bytes` | 111980 | 111978 |
| `always_loaded_baseline.total_card_bytes_if_all_injected` | 146361 | 146353 |
| `context_cost.per_k.1.mean_full_description_bytes` | 1268.6 | 1268.5 |
| `context_cost.per_k.3.mean_full_description_bytes` | 3188.2 | 3188.3 |
| `controls.flood_control.everything_router_mean_bytes` | 147272.0 | 147264.0 |

Largest delta 8 bytes (0.006%). **`MEASUREMENTS.json` was NOT regenerated** — it is a published
Phase 8 artifact, the suite is green with it as committed, and the delta is confined to those five
leaves. Regenerating is a one-liner if the owner prefers the hermetic provenance:
`ROUTING_HOME=<render> python platform/routing/cli.py metrics --out platform/routing/MEASUREMENTS.json`.

**The live-tree figures are machine-specific** — they describe this box's `~/.claude`/`~/.agents`.
The fixture figures are not: they reproduce anywhere the repo is checked out. That the two coincide
is a property of this fixture being routing-equivalent by construction, not a general guarantee.

## 7. Adjacent CI gates — checked, none collide

| gate | result |
|---|---|
| `no-runtime-junk` (bad dir segments / `installed.json`) | only `__pycache__`, already gitignored |
| `ci/gen_skills_manifest.py --check` | `OK … skills_tracked=337 manifest_rows=337` |
| `ci/gen_skill_index.py --check --fail-on-drift` | `INDEX DRIFT: no`, undeclared on disk 0 |
| `ci/check_skill_dual_write.py --strict-parity` | OK — but see below |
| `ruff@0.15.17 check` + `format --check` on all new/changed files | clean; fixture is LF-only |
| `basedpyright` lane | scoped to `tools/mcp-manager` + `tools/scholarly-access-mcp`, not `platform/` |

The D-001 dual-write gate reads git refs, so it cannot see the uncommitted fixture. I tested its
pathspec semantics instead, with a control that fires: `git ls-files -- .agents/skills` matches
1887 tracked files and **0 under `platform/`**, while `:(glob)**/.agents/skills/**` matches the
fixture's **328**. Root-anchored pathspecs will not pick up the fixture. Confidence **almost certain
(90-99%)** — direct measurement of the exact pathspec the gate uses; residual risk is only that the
gate is changed later.

## 8. Files touched (all in `platform/routing/`, plus this report)

- `platform/routing/fixtures/build_fixture.py` — NEW, generator + self-verifying gate
- `platform/routing/fixtures/home/**` — NEW, 581 files
- `platform/routing/conftest.py` — MODIFIED, adds the HOME binding
- `platform/routing/test_fixture_hermetic.py` — NEW, 7 standing guards

No commit, no push. Nothing touched under `command-center/` (except this file), `platform/lib/`,
`platform/coordination/`, or any `_p12*`/`_p13*` file.

## 9. Verdict

**SUCCESS.** The Phase 8 routing lane is hermetic: `python -m pytest platform/routing` is
**121 passed / 0 failed** with `HOME` unset or pointing anywhere, and the same command with the
fixture disabled and `HOME` empty is **22 failed / 90 passed** with the corpus guard firing. The
912-record corpus, every floor, every gold id and every published quality figure are reproduced
exactly; only five raw byte-count leaves move, by at most 8 bytes, from the username redaction.

Confidence that this runs green on a clean Linux CI runner: **almost certain (90-99%)** — no longer
an inference. It was EXECUTED on Linux (WSL2, Python 3.12.3, empty `~/.claude`): 121 passed with the
fixture, 22 failed without it. The remaining 1-10% is the ordinary gap between a WSL2 run over
`/mnt/c` and a GitHub-hosted runner doing a fresh clone — chiefly that a real runner checks out the
LF blob rather than reading this working tree, which is why the fixture is written LF-only and was
verified so. Settling it fully needs the lane wired into a workflow, which is out of scope here.