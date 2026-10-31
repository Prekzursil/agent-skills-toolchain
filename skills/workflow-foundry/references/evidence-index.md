---
title: evidence-index
type: note
permalink: dqverify-repo-20261013/skills/workflow-foundry/references/evidence-index
---

# Evidence index — every claim in this skill, with a path that resolves

Read this before citing any rule path from workflow-foundry.

## Cite the REPO copy of a rule, not the live path

```
C:/Users/Prekzursil/source/agent-skills-toolchain/rules/common/<name>.md
```

19 files at commit `64340915`. The repo is the source of truth; the live tree
(`~/.claude/rules/common/`, 20 files) is a deploy target that a deploy or a concurrent
lane can rewrite underneath you. `owner-ops-authorization.md` is currently live-only —
present in the live tree, absent from the repo — which is exactly the live-only drift the
harness-vcs-hygiene rule exists to catch.

### REFUTED, recorded rather than deleted (L10)

An earlier revision of this file asserted that `~/.claude/rules/common/` **is empty** and
built the repo-citation advice on that. **That sentence was wrong and is retracted.**

- What was observed: at ~02:17 on 2026-08-08 the directory contained zero files. Git Bash
  `ls -la` returned `total 12` and PowerShell `Get-ChildItem -Force -Recurse` listed
  `common` with no children.
- What refuted it: `check_no_regression.py`'s own `INV-6-rules-common` — whose
  `inv6_rules()` at `:445` globs **that exact live path** — reported
  `n=20 missing=[] extra=[]`, and an immediate re-probe listed all 20 files.
- Root cause: a concurrent lane was mid-write. The directory was **transiently** empty.

**The generalisable lesson, and it sharpens the single-signal rule.** Two mechanically
independent probes (different shell, different API) were run *at the same instant*. For a
**mutating** resource that is **one observation, not two** — independence must hold across
**time** as well as mechanism. The correct sentence was never "the directory is empty" but
"the directory was empty at 02:17". A standing property inferred from a single time point
is an overclaim even when the instrument is perfect, which is the 5-of-8 pattern (§C2)
reproduced by the very lane documenting it.

**Second lesson: read the instrument you are already running.** The refuting answer was in
the gate this lane was required to run anyway. It cost nothing and was available the whole
time.

## Anchors, by law

Repo root `agent-skills-toolchain` @ `64340915`.

| law | claim | anchor |
|---|---|---|
| L1 | freeze the preamble/launcher; contradictory live instructions measured | `rules/common/fan-out-contract.md:54` (§A10) |
| L2 | 3/3 agents returned plausible digests for files that do not exist | `fan-out-contract.md:70-71` (§B1) |
| L2 | reject `started in the background` / `Check /codex:status` | `fan-out-contract.md:72` (§B2) |
| L2 | never return a background job id as a work-unit result | `rules/common/cross-vendor-dispatch.md:12` |
| L3 | `DONE = artifact >=1024B AND ends with UNIT-COMPLETE: <id>`; ignore idle/mtime/exit | `~/.claude/workflows/codex-auth-research-fanout.mjs:27-28` |
| L3 | "CODEX THREADS IDLE is NOT done — only disk UNIT-COMPLETE is done" | same file `:63` |
| L4 | `pipeline()` is not a cacheable unit; resuming re-runs stage 1 | `~/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.md:1767` |
| L5 | 70 min / 691 KB / wrote nothing / unrecoverable; relaunch truthful in 3 min | `fan-out-contract.md:91-95` (§C1) |
| L6 | both-states test; a probe silent in both states measures nothing | `rules/common/single-signal-verification.md:40` (rule 3b) |
| L7 | 86% (291/338), 47 disagreements, 31 dangerous, 0 over-cautious | `fan-out-contract.md:140-165` (§C4), table at `:146`, direction at `:159` |
| L8 | role-aware discriminator; `USE / MENTION / UNKNOWN` | `~/.claude/hooks/_shared/use_vs_mention.py` — 41,045 B; `Judgement` :164, `audit_subject_rule` :571, `classify` :602, `is_real_occurrence` :788 |
| L9 | adversarial reviewers get siblings' FULL text | `fan-out-contract.md:80` (§B6) |
| L9 | probe-wins over agent count | `fan-out-contract.md:76` (§B4) |
| L9 | never score on output volume | `fan-out-contract.md:84` (§B7) |
| L10 | 5 of 8 refutations were overclaims, code was correct | `fan-out-contract.md:110` (§C2) |
| preamble | honesty instrumentation does not spill over | `fan-out-contract.md:8` (§A1) |
| preamble | enumerate the vocabulary; bare tag = 33% adoption | `fan-out-contract.md:12` (§A2) |
| preamble | UNVERIFIED inline | `fan-out-contract.md:17` (§A3) |
| preamble | a path carries its access method | `fan-out-contract.md:33` (§A5) |
| preamble | inject a shared grounding pack | `fan-out-contract.md:59` (§A11) |
| preamble | EVIDENCE block exempt from the word cap | `fan-out-contract.md:74` (§B3) |

## Measured by this skill's own lane, 2026-08-08

Reproducers live in `~/.claude/harness-restore-20260806/`:

| finding | probe | result |
|---|---|---|
| `receipt_gate.py` fires on all 6 broken shapes, silent on good | `scripts/receipt_gate.py --self-test` | `CONTROL-OK`, exit 0 |
| prior-art substring trailer accepts a prose MENTION | `_foundry_prior_art_probe.py` | `ok=True reason=and-gate-pass` on text saying it did NOT finish |
| the prior-art module disagrees with itself | same probe | `and_gate_artifact` DONE vs `extract_unit_complete_from_text` -> `None` |
| a directory path is folded into `no-artifact`, not NOT-CHECKED | same probe | `ok=False reason=no-artifact` |
| substring vs line-equality over the REAL corpus | `_foundry_historical_diff.py` | 55 artifacts, substring 54/55, line-eq 54/55, **divergence 0** — latent, not exploited |
| artifact stem != unit id | same probe | **1/55** (`auth-infra/auth-source-map.md` carries `UNIT-COMPLETE: auth-src-map`) |
| gate e2e on the REAL corpus, naive stem-derived ids | `_foundry_conformance_e2e.py` | `FINDING` — 55 units, 54 delivered, **1 NO-TRAILER** (the id-binding trap fires on production data) |
| gate e2e, ids pinned from the anchored marker | same probe | `CLEAN` — 55/55 delivered, plus the L3 rung-3 caveat printed |
| frontmatter conformance across the vault | same probe | 328 SKILL.md parsed, 0 unterminated; dominant shape `name,description` (223); workflow-foundry matches — `CLEAN` |
| "live rules/common is empty" | `check_no_regression.py` INV-6 + re-probe | **REFUTED** — transiently empty only; see the retraction above |

**Detector note, recorded because it nearly shipped:** v1 of `_foundry_historical_diff.py`
used a non-recursive `iterdir()` and printed `artifacts found: 0` while `ls` had reported
8 entries. A self-contradicting output is a detector failure, not a finding. The corpus is
55 files nested one level deep. The v1 "no historical false pass" line was computed over
**zero inputs** and is uncitable. The fixed probe now raises `SystemExit` on an empty
corpus rather than reporting a verdict.

## Related skills on this estate

| skill | owns |
|---|---|
| `workflow-authoring` | writing the `.mjs` — the `agent`/`parallel`/`phase` globals, args-as-string, the `Date.now()` ban, `isolation: worktree` |
| `orchestration-patterns` | architect-to-editor split, sandbox ladder, PageRank repo map, failure-threshold escalation |
| `codex-databricks-fanout` | remote compute placement for a large fan-out |
| `multi-ai-mingle` | the Claude<->Codex transport itself |
| `fresh-context-verify` | re-deriving a load-bearing value in a clean context |
| `09-WORKFLOW-BLUEPRINT-LIBRARY.md` (not a skill) | 108 named blueprint cards, 464 KB, in `~/.claude/harness-restore-20260806/` |