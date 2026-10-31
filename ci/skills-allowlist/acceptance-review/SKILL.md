---
name: acceptance-review
description: Use at the done boundary of an app change, before claiming a feature
  works, opening a PR, or accepting a repair as complete.
permalink: dqverify-repo-20261013/ci/skills-allowlist/acceptance-review/skill
---

# Acceptance Review — the cross-model "does it actually work?" verdict

The external-signal verifier for the "done" boundary. A capable model optimizes its
own done-signal — coverage, "tests pass" — and stops, while the real product is
broken (dead buttons, "shorts don't generate", a severed A→B→C flow). The signal is
gameable because the *same context that wrote the code certifies it*: intrinsic
self-correction degrades (Huang, ICLR'24), verifier↔generator errors couple
("Verification Mirage"), and judges prefer their own output (Panickssery, NeurIPS'24).
This skill breaks that loop with **verifier separation** — an evaluator that did NOT
write the code and, when possible, is a **different model** (VeriMAP / MetaGPT), which
demands the real artifact and is forbidden from trusting coverage.

It complements the always-on functional-acceptance hooks (`claim-guard`,
`test-tamper-guard`, `journey-coverage`): those *gate silently on static signals*; this
is the human/orchestrator-facing reviewer that *judges the running-app evidence and
returns a verdict*. See `docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`
(NORTH-STAR REPAIR FLOW: "fresh-context / cross-model acceptance review over the real
running app").

## When to run
- Before claiming an app/feature is done, works, or ships; before opening a PR.
- At the end of a repair session — especially after an assertive "fixed / it works now".
- Whenever "coverage is green" is the only evidence offered that the journey works.

## Procedure

**1. Gather evidence (deterministic).** Run the helper **by its own path** — it ships
beside this SKILL.md, NOT inside the repository under review, and `--repo` (never the
working directory) is what selects that repository. Read `<SKILL_DIR>` as the directory
holding this file: `~/.agents/skills/acceptance-review` once installed,
`.agents/skills/acceptance-review` inside the toolchain repo. It collects the change
set, the declared journeys, the artifact evidence, the reward-hack surface, and probes
which cross-model CLIs are actually on PATH:

```
python <SKILL_DIR>/scripts/acceptance_review.py --repo <REPO> [--base <REF>] [--out <DIR>]
```

Base defaults to the merge-base with a mainline (`origin/main`→`main`→…→`HEAD~1`). It
writes `review-prompt.md` + `evidence.json` under `<REPO>/.acceptance-review/` and prints
a routing line: which reviewer was chosen and why. The gathered evidence is the four
external signals a fresh reviewer needs:
- **Diff** (`git diff <base>...HEAD`) — what actually changed.
- **Declared journeys** — journey/E2E spec files on disk (same globs as `journey-coverage`).
- **Artifacts** — on-disk proof a journey ran (`job.done`, `*.mp4`, `playwright-report/`,
  `test-results/`, screenshots, reports), newest-first, flagged fresh vs. stale relative
  to the change.
- **Reward-hack surface** — net-new `pragma:no-cover` / `xfail` / `skip` / coverage-omit /
  marker-deselect / CI-disable in the diff (where gaming hides).

**2. Dispatch an INDEPENDENT reviewer** (prefer a different model; degrade gracefully).
The helper's routing (`--reviewer auto`, the default) picks in this order:

| Reviewer | When | How |
|---|---|---|
| **Codex CLI** | `codex` on PATH | `--dispatch` runs `codex exec -s read-only -C <repo>` with the adversarial prompt (read-only: it may open the artifact, never mutate the repo). Different model → genuine cross-model verifier. |
| **Gemini CLI** | `codex` absent, `gemini` present | `--dispatch` runs `gemini --approval-mode plan -o text -p <prompt>` (plan = read-only). |
| **Fresh Claude subagent** | neither CLI present (or `--reviewer claude`) | The helper CANNOT spawn it (a Python process can't call the Task tool). YOU spawn a **fresh-context** subagent via the `Agent`/`Task` tool (general-purpose or Explore) whose **only** input is `review-prompt.md` — do NOT paste your own reasoning; fresh context is the whole point (mirrors `fresh-context-verify`). |

To actually run a CLI reviewer, add `--dispatch` (wrap it with `longrun` /
`run_in_background` — a cross-model agentic review routinely exceeds 60s; default
timeout 240s). A timeout or an unparseable reply is treated as **BLOCK**, never a pass.

```
python <SKILL_DIR>/scripts/acceptance_review.py --repo <REPO> --dispatch          # auto → codex/gemini
python <SKILL_DIR>/scripts/acceptance_review.py --repo <REPO> --reviewer gemini --dispatch --model gemini-2.5-pro
python <SKILL_DIR>/scripts/acceptance_review.py --repo <REPO> --reviewer claude   # prints the fresh-subagent instruction
```

**3. Read back the structured verdict.** Every reviewer must end with the machine-parsed
block the prompt mandates:

```
VERDICT: SHIP | BLOCK
UNPROVEN_JOURNEYS: <spec paths with no post-change artifact, or NONE>
GAPS: <concrete runtime failures / severed steps, or NONE>
REWARD_HACK_FINDINGS: <exam-weakening diff changes, or NONE>
DEMANDED_ARTIFACTS: <the real output files required to flip BLOCK→SHIP>
CONFIDENCE: <0.0–1.0>
RATIONALE: <2–4 sentences; coverage / "tests pass" forbidden as evidence>
```

Relay it to the user verbatim. **SHIP only if every declared journey has a real,
post-change artifact proving the flow.** Zero declared journeys is itself a BLOCK-worthy
gap (no held-out done-signal exists) — surface that.

## The adversarial contract (baked into the prompt)
1. Assume green-but-broken; for each journey, name the runtime step that could fail.
2. **Demand the artifact** — the produced file a human could open, not a unit test.
3. **Forbid trusting coverage / "all tests pass"** — those are the gameable proxy.
4. Inspect the reward-hack surface; treat net-new pragma/xfail/skip/omit as suspect.
5. A journey spec with no post-change artifact is **UNPROVEN** (≠ passing) — list it.

## Guardrails
- **Never self-certify.** If `--reviewer` resolves to `claude`, the subagent must be
  fresh-context; do not review your own work in the same window.
- **Read-only.** CLI reviewers run sandboxed read-only / plan mode; this skill never
  edits app source (it judges, it doesn't fix).
- **Fail toward BLOCK.** Missing evidence, a timeout, or an unparseable verdict is
  inconclusive → treat as BLOCK, not a pass.
- **Advisory exit by default.** The helper exits 0 unless `--strict` is set with a
  dispatched BLOCK verdict (then exit 20) — for wiring into a gate.

## Files
```
acceptance-review/
  SKILL.md                          — this skill
  README.md                         — install path + rationale
  scripts/acceptance_review.py      — evidence gather + prompt build + route + dispatch (stdlib)
  scripts/test_acceptance_review.py — unit tests for the pure core
```