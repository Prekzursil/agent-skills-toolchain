# harness-sota-2026-07-18 — Codex analysis corpus

608 analysis artifacts produced by the **harness-sota-2026-07-18** program: an autonomous
multi-unit Codex effort to *ground on everything the workspace has ever run, research the frontier,
and design/build the best agent harness for this owner*. This folder is the grounded, saved copy of
the raw Codex output — the input to the later Claude synthesis pass, not the synthesis itself.

## What these are

Each `<UNIT-ID>.md` is one unit's end-to-end artifact: research, verification against the real
workspace, design proposals, and honesty instrumentation (confidence bands, `UNVERIFIED` tags,
`NATIVE-vs-BUILD` tags). Units are pure Codex (GPT-5.x); Claude's role begins only with the
synthesis that reads across this corpus.

## Provenance & validation

- **`MANIFEST.json`** lists every artifact with its byte size, a truncated SHA-256, its phase, and
  the source tree it was harvested from (local runner vs Databricks cloud lane).
- Every artifact here **passed the program's AND-gate**: file exists, ≥1 KB, and ends with the
  literal `UNIT-COMPLETE: <id>` sentinel. Exit-code-alone was never trusted (a valid artifact with a
  non-zero codex exit still counts; a zero exit with no artifact does not).
- **Secret-scanned before commit** with gitleaks 8.30.1 plus a targeted credential-shape sweep
  (OpenAI / GitHub / AWS / Databricks / JWT / private-key / `access_token` fields) — 0 real
  credentials across all 608. The one gitleaks hit was a false positive on token-budget prose.

## Phases

| Phase | Units | What it covers |
|-------|-------|----------------|
| P1-ground | 52 | normalise & verify the prior 140-unit audit's findings |
| P2-research / P2-research-wide | 242 | frontier research: harness reliability, memory, orchestration |
| P3-coverage | 144 | coverage of corpus-measured defects and red-team surfaces |
| P7-expansion | 123 | expansion into unexplored capability areas |
| P8-partner | 47 | cross-vendor / partner-tool integration analysis |

## A note on the red-team units (F-series)

The red-team units analyse this harness's own attack surfaces for **defensive** hardening. Several
were reframed from an offensive "construct the attack chain" framing to a defensive one
("characterise the exposure + verify the control + give the detection signature"); the models
declined to emit runnable attack playbooks, which is expected and correct. The artifacts here are
therefore defensive analyses, not weaponised exploits, and no live control was weakened or real
secret exfiltrated in producing them.

## Not the deliverable — the input to it

This corpus is deliberately raw and verbose (a unit's dead-ends are kept so a later reader is spared
re-walking them). The decision queue / implementation backlog is produced by the Claude synthesis
pass that consumes this folder.
