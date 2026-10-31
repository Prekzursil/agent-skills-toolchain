---
title: README
type: note
permalink: dqverify-repo-20261013/ci/harness/prebuild-recall/readme
---

# Pre-build recall gate

Fires on **build-shaped work** and injects prior-art hits before the build
starts. Advisory: exit 0 + `additionalContext`, never a block (AGENTS.md §6).

**NOT WIRED.** Nothing here is registered in `hooks.json` or any live
settings file. Wiring is a separate, deliberate step (below).

```
prebuild_recall.py        the gate
test_prebuild_recall.py   34 tests, incl. two known-positive controls
fixture_index.json        61 notes sampled from the real vault
indexer-patch.md          the upstream fix the recall control depends on
```

## Why this is not "just a rule"

The rule already exists — CLAUDE.md says "Recall (pull) — PROACTIVELY,
unasked" — and on 2026-07-18 a harness enshrine was done twice anyway. A rule
that is ignored is evidence that a rule is the wrong mechanism.

But the honest finding is that **recall was not the missing ingredient that
day**, and the artifact accompanying this directory says so at length. The
session timeline shows the prior branch referenced 13+ times from 02:22Z and
tracked as decision item T6. The agent had the memory. What it lacked was a
check that the files it was about to create already existed under a different
path. Hence two mechanisms ship here, and the second is the evidence-backed
one:

1. **recall** — lexical hits from the basic-memory index (the specified build)
2. **branch-overlap** — filenames about to be written that already exist on
   another branch (what would actually have caught 2026-07-18)

## The three problems, in order of load-bearing-ness

### 1. Freshness — the one that actually silenced recall

Both live indexes were frozen at **2026-07-10** when measured on 07-18:

| index | built | notes | contains the 07-13 note |
|---|---|---|---|
| `~/.agents/state/harness/recall-index.json` | 2026-07-10T22:06Z | 422 | no |
| `~/.claude/hooks/recall-inject/index/recall_index.json` | 2026-07-10T22:46Z | 621 | no |
| rebuilt on demand from the same vault | 2026-07-18 | 513 | **yes** |

Cause: `RecallModule` only *reads* (`_notes()` → `read_json`). Nothing
rebuilds. `recall_index.py` is a manual CLI with no scheduled task, no
dispatcher call, no invocation anywhere in `~/.agents/harness`. The legacy
`hooks/recall-inject/inject.py` it replaced *was* self-rebuilding
(`get_or_build_index`); the 2026-07-10 migration dropped that and nothing
replaced it. The live index is also `schema_version: 1` against a builder
emitting `2`.

So this gate treats a stale index as a **loud** condition, not a silent one:
an unusable index still fires, with the rebuild command.

### 2. Trigger — build-shaped, not prompt-shaped

`RecallModule.run()` returns immediately unless
`event.event == "UserPromptSubmit"`. It cannot fire on a Workflow launch, a
plan Write, a worktree creation, or a first Write into a new program dir.
This gate handles exactly those four shapes.

### 3. Query derivation

Measured token document-frequency over the real 513-note vault:

| token | df | % | note |
|---|---|---|---|
| `toolchain` | 0 | 0.0% | dead on its own — splitting destroys signal |
| `rescue` | 1 | 0.2% | |
| `enshrine` | 2 | 0.4% | |
| `runtime` | 4 | 0.8% | |
| `agent-skills-toolchain` | 26 | 5.1% | the compound is the good term |
| `mcp` | 53 | 10.3% | |
| `config` | 57 | 11.1% | |
| `harness` | 62 | 12.1% | |
| `live` | 76 | 14.8% | |
| `build` | 87 | 17.0% | |

Consequences encoded in the code:

- **Emit compounds AND parts; let IDF choose.** `agent-skills-toolchain` is
  discriminative; its part `toolchain` matches nothing. Neither form wins in
  general.
- **Expand compounds on the NOTE side too.** Asymmetric expansion is a silent
  recall hole — a context saying "runtime config" could not otherwise reach a
  note whose only relevant term is `enshrine-runtime-config`.
- **Drop df=0 tokens outright.** They are unmatchable *and* carry the highest
  IDF, so keeping them lets junk (`rescue-plan`, the Windows username, a
  branch datestamp) outrank every real term. This was a measured failure: the
  first working version's query was
  `toolchain, prekzursil, rescue-plan, unversioned, skills, are…`.
- **Drop machine identity.** Home-directory segments are rare in the vault and
  ubiquitous in paths — the worst possible combination for an IDF term.

## Silence is the default

Four gates, each rejecting a different failure mode. Measured against the real
vault (patched index):

| context | fired | rejected by |
|---|---|---|
| enshrine rebuild (true positive) | **yes** | — |
| `acme-invoicing/billing/vat.py` | no | `query-too-thin(1<3)` |
| generic "write the plan" | no | `no-discriminative-token` |
| trivial scratch note | no | `insufficient-coverage(1<3)` |
| unrelated Battle Cats offsets dump | no | `insufficient-coverage(1<3)` |

Each negative is caught by a *different* gate, which is the evidence that the
gates are complementary rather than redundant.

## Calibration

Every threshold is **scale-free**, because two scale-dependence bugs were
found by running the same tests at N=6 and N=513:

- An absolute score floor (`MIN_SCORE = 28`) is meaningless at N=6 — raw
  scores scale with IDF, which scales with vault size. Replaced by a ratio
  against the query's own achievable ceiling.
- An absolute IDF threshold (`MIN_RARE_IDF = 3.0`) is *unsatisfiable* at N=6:
  max achievable IDF there is 1.79. Replaced by a document-frequency ratio.

The primary discriminator is **coverage**, not magnitude. Measured top-hit
matched-token counts: true positive **9**, unrelated project **1**, generic
plan **2**, trivial note **1**. `MIN_MATCHED_TOKENS = 3` clears both sides.

A ratio floor alone does *not* separate: the unrelated invoicing write scored
**0.65** against the real vault, higher than the true positive at **0.48**,
because a one-token query normalises against a one-token ceiling.

## Known limits

- Recall quality is capped by `indexer-patch.md`. Unpatched, the known-positive
  control **fails** (target ranks 12, not 2). The patch is a prerequisite, not
  a nice-to-have.
- `branch_overlap` takes an injected `lister`; the production wiring
  (`git ls-tree -r --name-only <branch>`, bounded + timed out) is **not
  written** — the caller owns it. UNVERIFIED inline: no measurement exists of
  its latency across ~40 local branches; settle it by timing `git ls-tree` over
  `git for-each-ref` on this repo before wiring.
- Per-session dedup (`seen_dirs`) is caller-supplied state. This module does
  not persist it; the dispatcher's `state_root` pattern is the obvious home.

## Wiring (deliberate, not automatic)

Preferred: register as a module on the existing dispatcher bus alongside
`RecallModule`, rather than adding a new hook process — it would otherwise
duplicate index loading, dedup state, and the calibrated-silence gate. See the
artifact's mechanism assessment.

```bash
python -m pytest ci/harness/prebuild_recall/test_prebuild_recall.py -q
```