---
title: BUILD-ROUND1-2026-08-13
type: note
permalink: dqverify-repo-20261013/command-center/ssot/build-round1-2026-08-13
---

# LANE SSOT — BUILD lane, round 1

**Status: COMPLETE for round 1.** Every claim below is measured; each names the command that
produced it. Nothing was deleted; no clone, worktree or evidence directory was touched.

COVERAGE: B1–B5 measured. NOT measured, disclosed inline: the mcpctl DIVERGED set is not
resolved (B3), the `mcp-manager` port decision is judgement not measurement (B3), and R4/R5
remain destructive-to-test (unchanged from the inventory).

Baseline at start of round 1: worktree `ast-integrate`, branch `main`, HEAD `f5b596e6`,
`origin/main` `86dde6c1` (5 ahead / 0 behind), 327 dirty `-uall`.
Baseline moved during the round — `origin/main` read `ebe02d62` by the end. See B6.

---

## B1. Commit the SSOT artifacts — DONE

Measured before, with working controls (`git ls-files docs/` = 185; `REPO-TOPOLOGY.md`
tracked, so the zeros were real rather than a broken detector):

| | before | after |
|---|---|---|
| `docs/ssot/` tracked | **0 of 1** | 1 of 1 |
| `command-center/ssot/` tracked | **1 of 24** | 25 of 25 |

Commit `df6377ab`, 25 files, 15,746 insertions, explicit pathspec. The document defining the
SSOT rule had existed only as an untracked file in one working tree holding 327 dirty entries.

**A secret preflight ran first** and is the reason this is not a credential incident:
`inbound-refs.json` was produced by scanning `~/.claude.json`, `~/.mcp.json` and
`settings.local.json`. Two mechanically independent signals agree nothing rode along —
`_secret_preflight.py` over 37 files / 861,639 chars returns **0 credential-shaped findings**,
and the payload schema stores `{file, line, kind}`, i.e. line *numbers*, not line content.

## B2. Fold the corrections into ONE inventory doc — DONE

`docs/ssot/SSOT-CLONE-INVENTORY.md` still holds exactly one document (no second file created).
Three claims corrected in place, refuted wording kept rather than deleted so the dead end is
not re-walked: the §0/§2 data-loss headline (re-scoped, see B3), the §5 retire criterion
(see B4), and R6/R8 (baseline drift, and the untracked-artifact hazard now closed).

## B3. Content-check the stranded work — DONE, and it changes the verdicts

`content_check.py` compares every path in each stranded commit against `origin/main`
**bidirectionally**, because the one-directional read is the measured systematic blind spot
(31 of 47 agent misclassifications were DIVERGED read as safe; 100% of those errors pointed at
data loss). Verdicts that could authorise a deletion were then re-checked by an independent
signal — git's own SHA-1 blob identity, sharing no code path with the line-set comparison —
and **5 of 5 were corroborated** (`_verify_identical.py`).

| location | measured | verdict |
|---|---|---|
| `_wu/CRCP-SEC` (the "security fix") | `auth.py`, `sentinel.py`, **both proving tests byte-identical** on main; `auth_broker.py` main-superset | **REDUNDANT** — not at risk, drop from the reconcile list |
| `_b5-toolchain` | `core/health.py`, `mcp_health.py`, `tests/test_health.py` all **ABSENT from main** | **UNIQUE — preserve** |
| `agent-425276811/ast` (mcpctl) | all 5 files DIVERGED, incl. `safety.py` +17 scratch-only / +11 main-only | **needs judgement — genuinely open** |
| `D:/wt-salvage-probe` staged index | `ci/tests/test_codex_profiles.py`, `tools/monitorcore/r0_monitor_live_gate.py` — **both ABSENT** | **UNIQUE — highest urgency** |

The inventory's headline ("four stranded commits are the fleet's real data-loss exposure") was
an **overclaim**: the commit-object measurement was right, the sentence was wider than its
evidence, because squash-merge guarantees a merged commit keeps a unique SHA forever. The
exposure is smaller and sharper — 5 files in 2 places, plus one open DIVERGED set.
`D:/wt-salvage-probe` is upgraded from "nearly clean, needs a one-file triage" to the fleet's
highest-urgency item: a **staged index is per-worktree and is destroyed by `git worktree
remove`**.

**UNVERIFIED, inline:** line-set divergence does not prove main lacks capability — main may
have evolved past the scratch form. Settling experiment: run the scratch `test_safety.py` /
`test_mutations.py` against main's `safety.py` and see which assertions fail.

## B4. Fix the retire criterion — DONE

The inventory required `git stash list` empty before retiring. Measured across **all five**
store-A checkouts (the grounding checked two): every one reports stash-count 2 and the
*identical* `refs/stash` `d90474213cca...`. `refs/stash` is **store-level, not worktree-level**,
so the criterion was simultaneously false for every store-A checkout — including
`ast-harness-reconcile`, which the same document lists as a RETIRE candidate. The rule
contradicted its own list. Error direction was SAFE (a false blocker, never a false
permission), but it was unusable. Corrected to split by kind: `stash list` empty for
independent clones; `git diff --cached --quiet` for linked worktrees, because removal destroys
the **index**, not the shared stash. Corroborating measurement: `staged` genuinely differs per
worktree (0 / 3 / 0 / 0 / 2), so the index discriminates and the stash cannot.

## B5. Close the latent execution-drift hazard — DONE, gate shipped

`ssot_drift_gate.py` fails when code the live MCP fleet **executes** has fallen behind `main`.
The estate edits in `ast-integrate` and executes from `agent-skills-toolchain`, which is
permanently detached and **173 commits behind** (159 → 161 → 173 across three readings).

Current reading: **0 files** under the 5 executed directories differ from `origin/main` — the
running fleet is executing current bytes. Corroborated independently: all five commits that
ever touched the executed surface are **ancestors** of the executed HEAD, and the diff is 0 in
**both** directions, so a diff-direction bug is not hiding behind the zero.

*Correctly scoped:* that says nothing about the other 173 commits — only that none touched the
executed directories. **The hazard is latent, not absent**, and the next `tools/mcp/**` commit
is what the gate exists to catch.

## Detector controls — what proves each probe fires when broken

| probe | known-BROKEN state | result |
|---|---|---|
| `_secret_preflight.py` | 5 credential families planted (assembled at runtime, never literals, so the file itself cannot poison future scans) | all 5 **FIRE** |
| `_secret_preflight.py` | clean path, and the measured needle-path false positive | both **SILENT** (0 hits) |
| `_secret_preflight.py` | opaque value under a sensitive key | **FIRES** — proves the FP fix did not disable the detector |
| `content_check.py` blob reader | fabricated path | returns `None`; a real path returns content |
| `_verify_identical.py` | same file vs two different real files | **MATCH** / **DIFFER** |
| `ssot_drift_gate.py` | ref = parent of a real commit that touched `tools/mcp/**` | **exit 1**, names `tools/mcp/qdx-rush-mcp/uv.lock` |
| `ssot_drift_gate.py` | live config | exit 0 — and **discrimination confirmed: exit 0 vs exit 1**, so the gate is not inert |
| `ssot_drift_gate.py` | ref = executed HEAD (degenerate) | exit 0 **and says so explicitly** rather than claiming a meaningful pass |
| `_ci_surface.py` | tracked-set plausibility | 10,438 paths; fails closed below 100 |

Two of my own detectors were wrong first and were fixed, not explained away:

1. **12 false HIGH secret findings.** All one file, all beginning `sour`, all entropy
   3.88–3.90. That uniform cluster was the tell: the key `"token"` in `refs-verified.json`
   means a *search needle* and its value is `source/agent-skills-toolchain`. A use-vs-mention
   failure at the field level, inside the detector meant to prevent exactly that.
2. **A 68-file "CI is red" reading that overstated the surface.** `ruff format --check .` walks
   **untracked** files; CI checks out from git and never sees them. True CI-visible count: 14.

## B6. Blast radius of my own commit — found and remediated

`df6377ab` committed 6 files that were format-dirty, moving them from untracked (invisible to
CI) to tracked (gate-visible). Attributed mechanically by `_ci_surface.py`:

- 51 format offenders locally → **14 TRACKED** (the real CI surface) → **6 introduced by me**,
  8 pre-existing from commit `1e9cfe81` (a different lane).
- Plus one lint error I carried in: `E402` in `verify_refs.py`.

All 7 fixed: `command-center/ssot/` is now **0 lint errors, 20/20 formatted** under the
CI-pinned ruff 0.15.17 honouring the committed `ruff.toml`. I formatted **only my own scope**
and did not touch `ruff.toml` or another lane's files. Verified no digest-lock existed on the
probe bytes before reformatting them (the frozen-evidence directories named in the charter are
`command-center/casualty/probes/` and `command-center/p2-wave/probes/*/control/` — neither is
`command-center/ssot/`).

The gate was already red tree-wide before this lane; **8 tracked offenders from `1e9cfe81`
remain and are outside my file scope.** Reported, not touched.

## Definition of Done

| DoD item | status | evidence |
|---|---|---|
| every clone classified worktree-vs-clone by measurement | **PASS** | inventory §1 — 25 checkouts / 18 stores, two independent signals agreeing on all 25 |
| unique-content measured per clone | **PASS** | §2 objects + §2b content (new this round; changes 2 verdicts) |
| inbound-reference measured per clone | **PASS** | §3 — 8 field-level refs, 23 of 25 referenced by nothing |
| a one-sentence SSOT rule written | **PASS** | §5, with the retire corollary corrected this round |
| nothing deleted | **PASS** | read-only against every checkout; only writes were to `docs/ssot/**` + `command-center/ssot/**` |

## What round 2 should do, ranked

1. **Rescue `D:/wt-salvage-probe`'s 2 staged files** onto a pushed branch. Only copy of that
   content; a worktree removal destroys the index holding it.
2. **Rescue `_b5-toolchain`'s 3 absent files**, then decide the `mcp-manager` port by diffing
   its graded-evidence logic against main's `claude_adapter.py` detector — judgement, not a
   differ.
3. **Settle the mcpctl DIVERGED set** by running the scratch tests against main's `safety.py`.
4. **Wire `ssot_drift_gate.py` into CI or a hook** so the latent hazard becomes enforced rather
   than merely measured. It is currently a script that must be run by hand.
5. **Do not retire anything yet**, and never run a `worktree` subcommand from the Codex plugin
   cache: `git worktree repair` rewrites links *bidirectionally*, so running it there would
   repoint the real live worktrees at the cache.