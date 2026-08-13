# RULERESEARCH — INTEGRATE

Filled by the BUILD lane, round 1. This file was a skeleton whose every section read
`UNKNOWN - not yet measured`; by its own sentinel nothing in it could be cited. The sentinel
is now discharged — every claim below is measured, and the ones that are not say so inline.

## 1. What state did I inherit?

The lane's Definition of Done was already met and reproduced. Commit `23ee1622` classified all
rules by measured frontmatter, totalled the always-on cost, and corrected nine rule-vs-reality
contradictions; ADV-R4's verdict was "build is SOUND". Reproduced independently this round by
running the producer:

| tree | root | files | always-on | lazy | always-on tok | all tok |
|---|---|---|---|---|---|---|
| repo | `rules/` | 88 | 8 | 80 | 17,107 | 63,294 |
| agent-self | `agent-self/config/rules/` | 78 | 4 | 74 | 1,201 | 38,008 |
| live | `~/.claude/rules/` | 88 | 8 | 80 | 15,141 | 54,426 |

Always-on floor (live rules + the three unconditional memory files) = **23,050 tok**.
Token counts are cl100k_base, i.e. OpenAI's tokenizer, not Anthropic's — treat as estimates
(±10-20%), not receipts. The classification half is tokenizer-independent and exact.

What was NOT inherited: any way to *run* the work. Which is section 2.

## 2. Reachability: was any rule-audit gate wired into CI?

**No. Zero of eight.** Searched every `*.yml`, `*.yaml`, `*.toml`, `*.cfg`, `*.ini` in the repo
and all of `ci/` for the eight gate filenames — no matches.

The absence was controlled in both directions before it was believed:

| probe | result |
|---|---|
| positive control: search for a known-wired name (`test_rules_integrity`) | **fires** — `.github/workflows/quality.yml:768` |
| negative control: search for a bogus token | **silent** — no false positives |
| the eight gate names | **zero matches**, in CI configs and in `ci/` alike |

So four rounds of gate-building never executed. This corroborates ADV-R4 §4 from an
independent instrument.

Why no existing test caught the drift, verified use-vs-mention: exactly two CI tests mention
`.claude/rules`, and **both are mentions, not reads** — `test_rules_common_contracts.py:234` is
a docstring and `test_rules_selector_inheritance.py:109` is a comment. All 167 rules tests read
`rules/` and `agent-self/config/rules/` only. That is the mechanism behind repo↔live drift
growing 28 → 29 files while the suite stayed green.

## 3. The integration shipped

`docs/rule-audit/ci_gate.py` + `.github/workflows/rule-audit.yml`.

**A separate workflow file, not a job in `quality.yml`.** `quality.yml` is a closed gate set
policed bidirectionally by `.quality/charter_check.sh`: a `gate-<slug>` marker with no matching
`- slug:` in `.quality/charter.yml` turns the existing lint job red, and
`ci/tests/test_charter_consistency.py` pins it both ways. `charter_check.sh` reads only
`quality.yml`, so a separate workflow carries no charter obligation. This is the shape
`no-runtime-junk.yml`, `skill-dual-write.yml`, `p2next-rail-count.yml` and `mcp-audit.yml`
already use, and it touches no file a sibling lane is editing.

### The plan was chosen from measurement, not from reading the source

All eight gates were executed. None is unrunnable; two exit non-zero *by design*:

| gate | rc (this box) | wall | meaning |
|---|---|---|---|
| `rule_audit.py --self-test` | 0 | 1.2 s | 19 detector controls |
| `r2_pathrefs.py --self-test` | 0 | 2.8 s | 6 gate-level states |
| `r2_control_count_gate.py` | 0 | 1.6 s | prose == tool == AST == group sum == 19 |
| `r2_failclosed_mutation.py` | 0 | 3.1 s | control fires on mutant, silent on real |
| `r4_receipt_argv_gate.py` | 0 | 0.5 s | 52 documented invocations parse |
| `r4_credential_rule_gate.py` | **1** | 0.2 s | the credential inversion is real and unfixed |
| `r2_pathrefs.py` (bare) | **2** | 110.5 s | known defect tracked, no NEW finding |
| `r3_corpus_parity_gate.py` (bare) | 0 | 89.0 s | 3 trees / 254 files declared == swept |

The two that first appeared to "time out" were slow, not hung — a 120 s cap sat almost exactly
on `r2_pathrefs`'s 110.5 s runtime. A cap is not a diagnosis; re-measuring with a 900 s cap
distinguished them.

### What is deliberately NOT wired, and why

| excluded | reason |
|---|---|
| `lazy_predict.py` | reads `~/.claude`; on a runner it fails **closed** (rc 0→1, "live rules tree scanned to zero files") |
| `r3_corpus_parity_gate.py` | same; reports "gate inert, its green means nothing" |
| `rule_audit.py` **bare** | **fail-OPEN**: with no `~/.claude` it prints `SUCCESS:rule_audit` and exits **0** while the entire live tree scanned to zero files. Wiring this would have been a permanently green gate measuring nothing — so the plan uses `--self-test` |

That last row is a genuine new finding of this round, and it is the reason the CI plan's argv
differs from the obvious one. Its three siblings all fail closed on the same input; the
flagship producer does not.

### Two invariants added, because reachability alone was not enough

Wiring the existing gates makes the *corrections* enforceable. It does not protect the audit's
central *measurements*. Two assertions were added, both read only from the two **in-repo**
trees, so they need no `~/.claude` and no tokenizer and mean the same thing on a runner as on
this box:

1. **DoD-1 always-on set.** The repo's always-on rules must be exactly the measured 8. A rule
   that *gains* a `paths:` selector is **demoted** out of every turn-0 prompt — the inverse of
   the intuition, and the exact trap the lane charter names. Nothing in the repo detected this:
   a rule could gain or lose `paths:` and all 167 rules tests would stay green.
2. **Deploy-source load-semantics parity.** `rules/` is deployed by `scripts/sync-rules.ps1`;
   `agent-self/config/rules/` by `agent-self/bootstrap.ps1`
   (`Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force`). **Two deploy sources
   for one live tree, and they disagree on three files** — measured, with identities:

   | file | `rules/` | `agent-self/config/rules/` |
   |---|---|---|
   | `common/git-workflow.md` | lazy (paths-scoped) | **always-on** (no frontmatter) |
   | `common/hooks.md` | lazy (paths-scoped) | **always-on** (no frontmatter) |
   | `common/security.md` | lazy (paths-scoped) | **always-on** (no frontmatter) |

   Running bootstrap therefore silently **promotes three lazy rules into every turn-0 prompt**.
   The three are allowlisted with that reason; a fourth fails the run — and so does one
   *disappearing*, so a repair must be recorded rather than silently absorbed.

Incidental live corroboration of the load model, from inside this agent: reading a `.py` file
mid-round caused the harness to inject the path-scoped `python/*` and `common/` rules,
including `common/git-workflow.md` and `common/security.md` — i.e. the **live** tree treats
them as lazy, matching `rules/` and not `agent-self/`. `common/hooks.md` did **not** arrive
(its selectors are `**/hooks/**`, `**/settings*.json`, `**/.claude/**`, none of which were
touched), which is a firing negative control.

## 4. The end-to-end executable proof (both states)

A gate never seen red is indistinguishable from a no-op, so every check was observed in both
states.

**Self-test — 12/12 pure predicates** (`ci_gate.py --self-test`, rc=0), each asserted to FIRE
on a broken input and stay SILENT on a good one: inventory completeness, an unclassified file,
a planned-but-absent file, a gate going red, **an expected-FAIL gate that started passing**, a
rule promoted, a rule demoted, a new divergence, a repaired divergence. Plus three
shrink-guards: a `CI_PLAN` that shrank, an allowlist that shrank, and the loss of the last
expected-FAIL entry (which would silently degrade the both-states pair into a one-state check).

**Red-proof on REAL file bytes — 6/6** (`_b8_redproof.py`, rc=0). The self-test proves the
comparison logic and says nothing about whether the classifier, reading real files, notices a
changed frontmatter. So both in-repo trees are copied to a temp dir, the copies are mutated,
and `measure_trees()` must fire:

| state | result |
|---|---|
| CONTROL: untouched copies | **silent** |
| demote `common/agents.md` by adding `paths: ["**/*"]` | fires — "always-on set LOST" |
| promote `common/testing.md` by stripping its frontmatter | fires — "always-on set GAINED" |
| new divergence on `common/testing.md` | fires |
| repair an allowlisted divergence | fires |
| empty repo tree | `RuntimeError` (fail closed) |

The repo is never modified: everything happens under `TemporaryDirectory()` and `TREES` is
restored in a `finally`.

**Inventory invariant, end-to-end.** A transient unclassified `.py` was dropped into the
directory: gate → **rc=1**, `FAILED:...new file(s) in neither CI_PLAN nor EXCLUDED`. Removed:
gate → **rc=0**. Both states observed on the real pipeline, not simulated.

**Repo state:** `ci_gate.py --self-test` rc=0, `ci_gate.py` rc=0
(`6/6 gates behaved, always-on=8, divergence=3`); 167 rules tests pass; 28 workflow-contract
tests pass; the workflow YAML parses.

## 5. Residual — what is NOT done, and the settling experiment

- **UNVERIFIED: "installing tiktoken makes Linux go 19/19."** Measured under WSL Ubuntu 24.04
  that *without* tiktoken `rule_audit.py --self-test` fails exactly 2/19 controls
  (`encoder is tiktoken/cl100k_base`, `known string -> known count`) because `Counter` degrades
  to `ESTIMATE chars/4` and `round(len("hello world")/4) == 3 != 2`; and that
  `r2_control_count_gate` and `r2_failclosed_mutation` cascade red off it. Could **not** install
  tiktoken to confirm the repair — this box's WSL has no DNS (`Temporary failure in name
  resolution`). The claim is derived from the mechanism (only the 3-control `encoder` group
  touches tiktoken, and its third control passes either way) plus Windows-with-tiktoken
  measuring 19/19. **Settling experiment: the first run of `.github/workflows/rule-audit.yml`
  on a runner, which has network.** If the self-test step goes red, the derivation was wrong and
  those three CI_PLAN entries must be dropped.
- **Network at gate time.** `tiktoken.get_encoding` fetches the BPE file on first use
  (ci-hygiene §2). Accepted deliberately: the failure mode is loud, not silent — a failed fetch
  makes `Counter` fall back, which makes the encoder control fire and the job go red. The
  alternative is deleting the control that stops estimates being certified as measurements.
- **The credential inversion is still live and is pinned, not fixed.**
  `agent-self/config/AGENTS.md` lacks the §9 rotate-prohibition and carries the inverted
  "rotate, don't just delete"; `agent-self/bootstrap.ps1:45` would deploy it over `~/.claude`.
  Repairing it is the owner's call (AGENTS.md §9 — an agent does not change credential policy),
  so `r4_credential_rule_gate` is wired at **expected rc=1**. It is now tracked by CI instead of
  merely documented, and the day it is repaired the entry goes red and forces promotion to a
  blocking rc=0.
- **Repo↔live drift (29 of 88 files, 7 of 8 always-on) is NOT gated and NOT deployed.** A
  runner has no `~/.claude`, so no CI job can see it. Closing it needs either a local gate or a
  deploy; neither is in this round. The corrected `harness-vcs-hygiene` and
  `cross-vendor-dispatch` rules remain wrong in the live tree.
- **NOT-CHECKED, declared rather than folded into a pass:** the full ~25-step `quality.yml` was
  not run (out of lane, shared-file hazard), so no claim is made that CI overall is green — only
  that the 195 tests named above pass and the new workflow is self-consistent. The workflow has
  never executed on a runner. `rules/` and `AGENTS.md` were not edited.

## 6. Commits

See `RULE-AUDIT-BUILD-R1.md` §6 for the commit and the exact file list.
