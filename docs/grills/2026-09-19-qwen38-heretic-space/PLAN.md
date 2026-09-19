# PLAN — rebuild of `Prekzursil/qwen38-27b-heretic-chat` (2026-09-19)

Companion to `DECISION-QUEUE.md` (decisions, evidence) and `evidence/orchestration/design-v2-final.md`
(sha256 `7742a9c8…`, 2,563 lines — **the build standard**). Nothing here overrides those; this is the launch view.

## 1. Goal
One production release, built through a gated multi-agent pipeline, of: a CPU-only UI/API Space (Gradio workbench +
OpenAI-compatible gateway + narrow MCP) with hosted inference first (`router.huggingface.co` over curated `models.yaml`),
one ZeroGPU worker Space as fallback, expanded tool use behind safe defaults, cleaned+extended personas, hardened
in-container `python_eval`, and a CI-only promotion path (GitHub source of truth → staging Space + canary → production).

## 2. Why this shape (evidence chain, all durable under `evidence/`)
50 verified code-review findings (45 verdicts) · 6 lens + 3 scout reports · 5 orchestration research reports (doctrine,
tool-native, 2× external SOTA, 47 failure modes) · 3 independent designs → 3 judges (unanimous: minimal-scaffold base) →
synthesis v1 → critic (38 gaps) → v2 → final critic (3 majors) → **v2.1: drive 107/107 across 41 scenarios, dry run 22/22,
document byte-identical to artifacts**. Production stays DOWN until the pipeline promotes (owner decision G-2).

## 3. Owner prerequisites (before R0; none can be done by the workflow)
1. **Revoke the HF token pasted in chat on 2026-09-18** (it also sits in 11 local subagent transcripts).
2. **Stop the other agent**: stop-notice + disable its Windows scheduled tasks (keepalive + weekly dep-update) so nothing
   pushes to the Space during the build; record the Space HEAD at that moment.
3. **Resize the Codespace** (Q1): 16–32 cores → Workflow cap 14–16 instead of 2; do it BEFORE R1 (mid-run resize = cache-cold).
4. **Create (or approve me creating via `gh`) the private GitHub repo** that becomes the source of truth, with the
   `production` environment + required reviewer for promotion workflows.
5. **Provide setup inputs when prompted**: a read-scoped token for cloning the private Space at setup; the fixture #1
   metered hosted call (one streamed request through the router — decides where the tool-call parser lives; recorded as
   conformance fixture #1); approval of the persona-boundary fixture hash the gate pins.
6. Answer (or accept defaults for) the ten questions in §6.

## 4. Local setup I run before R0 (no owner action needed)
Durable build root (per design, NOT inside this synced folder) · re-download pinned wheels
(gradio 6.26.0 / spaces 0.51.3 / transformers 5.16.1) to a durable `libsrc/` · re-clone the Space + HEAD/sha check ·
Python 3.12 gate venv · copy `gate.sh` out of the design, pin its sha256 in `args`.

## 5. Run sequence (from design-v2 §2/§13; every run ends in a typed checkpoint, nothing outward inside a run)
- **R0 plan** (≈11 agents): grounding trio (findings symbolizer w/ executed reproduction of critic-1..5 · API ledger from
  pinned wheels with `known_bad[]` · catalog provenance), decision sheet, 22 PR-sized cards + DAG + journeys, plan critics,
  plan verifier. → owner approves the frozen plan hash.
- **R1 build** (≈296 agents, cap 2 ≈28–29 h in 5–7 invocations / cap 14 ≈18–20 h in 2–3): per card
  author(tests) → confirm-RED → builder → gate (timestamp-free digest, oracle-lock, mutants, claim-vs-diff, secrets) →
  fresh verifier (re-runs the gate; digests must match) → bounded fixer (≤3, fingerprint pivot) → serial single-writer
  integration (gate per merge, lost-hunk checks, bundles) → clean-clone wave gate with journeys. Owner stops built in:
  fixture #1 before the seam card merges; persona-boundary fixture; worker-checkpoint decision (Q7).
- **R2 stage** (≈25–30): five review lenses → refute-with-reproduction → fix cards through the same chain → `satisfied`
  needs 3/3 veto-only judges + deterministic preconditions. Staging promotion request is a checkpoint; CI deploys to the
  staging Space, canary (16 tokens per backend), logs fetched by CI only.
- **R3 promote** (≈8): synthesizer reads only mechanical ledgers + git; emits the production promotion request; the owner
  (or the `production`-environment workflow) executes. Rollback = redeploy last known-good sha.

## 6. The ten questions (defaults in bold — veto by number, or say "all defaults")
Q1 **resize to 16–32 cores before R1** · Q2 **remove the `presence_penalty` placebo** (no torch wheel in the gate venv;
a LogitsProcessor card returns only if you insist on the knob) · Q3 **keep MCP** as the narrow `ask/poll/status/preflight`
surface · Q4 **two scoped tokens** (router token in the UI Space; separate read-scoped token for the worker Space) ·
Q5 **web tools default OFF; `http_request` GET-only while the bench holds files** · Q6 **gate on local 3.12.3, CI on the
image's 3.12.12** · Q7 **resident worker = FP8 prequant** (`magiccodingman/…-fp8`, pinned sha); if it lacks
`model.visual.*` tensors, the VLM-class export HF Job needs your approval (billed, owner-started) · Q8 **R2/R3 budgets:
default reserves from design §11** · Q9 **approve the two recorded clarifications** (pending catalog entries hidden until
one entry passes the harness; token-level Continue) · Q10 **confirmed medium/low staging findings warn, critical/high block**.

## 7. Exit criteria (production promotion request is emitted only when all hold)
Staging canary green per backend (hosted + worker) · catalog ships only `admitted` entries with pinned revisions and
provenance · `python_eval` red-proofs pass (env allowlist, `/proc/<ppid>` unreadable, rlimits, operator flag, absent from
every API/MCP surface) · README/UI/commit claims generated from the same constants · clean-clone gate green from the
promoted sha · rollback drill executed on staging.

## 8. Parallel track (after R1 or interleaved, owner-paced)
`gem-hunt` pass → PR to `Prekzursil/agent-skills-toolchain` with the 20 candidate skill upgrades from
`evidence/orchestration/research-1-doctrine.md` (implementation-loop template for workflow-authoring, shared
`unit_done` reducer, missing sdd templates, commit-claim-vs-diff lint, gate-zero-enforcer vendoring, …).

## 9. Living state
Everything auto-syncs to PR #336 (`save-to-repo.sh`, every 5 min, retries unpushed commits). After any session restart,
relaunch the loop and re-check the Space HEAD before planning against it.
