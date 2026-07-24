# Continuous Self-Improvement Engine (CSIE) — Design Spec

**Status:** design (brainstormed 2026-07-24; awaiting plan-review gate before implementation).
**Owner directive:** use the Codex-on-Databricks fan-out to continuously, automatically improve
ITSELF and the toolchain, plus reconcile/fix the 28-repo fleet — in parallel isolated
worktrees/branches, curated before adoption. "Keep everything permanently upgradeable."

**Design decisions locked (owner):** tiered-autonomy curation · nightly + on-demand +
event-triggered(opt-in) cadence · extend-the-harness engine + adaptive fleet integration ·
**pluggable compute backend** · deep-research backends first (done → see `research CSIE compute
backends 2026-07-24` in basic-memory).

---

## 1. Goal

One engine that turns "improve X" into: fan out parallel units on a pluggable compute backend →
each proposes a change on an **isolated branch** → adversarial critics + **full CI-matrix** verify →
**auto-adopt** provably-safe EXTERNAL fixes, **PR** everything structural (esp. anything touching the
harness/toolchain) for owner curation. Runs nightly, on demand, or on events.

## 2. Two scopes, one engine

| Scope | Target | Adoption |
|---|---|---|
| **External** | the 28-repo fleet (coverage/mutation/security/docs/lint gaps → fix to green) | auto-adopt safe · PR structural |
| **Self** | the harness + toolchain (agent-skills-toolchain: rules/hooks/skills/MCPs/agents) | **ALWAYS PR — never auto-adopt** |

The env-inspector pilot (PR #144 merged, #145 cross-platform fix) is External-scope lane-1, proven.

## 3. Architecture (extend the harness)

```
databricks-fanout-harness/
  harness/            # built: contract, preflight, build_batch, submit, poll, harvest
  backends/           # NEW — pluggable compute-backend adapters (see §4)
    base.py           #   Backend protocol: submit(units)->job / poll(job)->state / harvest(job)->artifacts
    databricks.py     #   built (current submit/poll/harvest, refactored behind the protocol)
    github_actions.py #   NEW — the cross-platform VERIFY tier (available)
    codex_cloud.py    #   NEW — native Linux codex BUILD alt (available)
    # modal.py aws_batch.py gcp_batch.py fly.py  <- DEFERRED (interface ready, not built)
  lanes/              # what a unit DOES (coverage built; add mutation/security/docs/lint/gapfind/toolchain)
  engine/             # NEW — backlog + scheduler + curation + adoption + the self-mod guardrail
    backlog.py  schedule.py  curate.py  adopt.py  guardrail.py
```

Engine + lanes are **100% backend-agnostic** — they call the `Backend` protocol, never a vendor SDK
directly. Fleet integration (QZT/codex-fleet dispatch + dashboard) is an ADAPTER, not a coupling.

## 4. Pluggable compute backend (the portability core)

`backends/base.py` defines the protocol every backend implements:
```
class Backend(Protocol):
    def submit(self, units: list[Unit], meta: dict) -> Job: ...
    def poll(self, job: Job) -> str:  ...   # RUNNING | terminal
    def harvest(self, job: Job, dest) -> dict[str, Path]: ...   # uid -> local artifact
    tier: str        # "build" (fast Linux fan-out) | "verify" (cross-platform CI matrix)
    cross_platform: bool
```

**AVAILABLE now (build these):**
- **`databricks`** — BUILD tier, built. Refactor the current submit/poll/harvest behind the protocol.
- **`github_actions`** — **VERIFY tier.** The ONLY backend that runs a repo's real
  `ubuntu + windows-latest + macos` matrix (fixes the proven "Linux-green, windows-latest-red" gap,
  env-inspector #145). Submit via `workflow_dispatch` (⚠ 204 = no run-id → poll `list-runs` to
  correlate); harvest = the unit's own git-push + `pull_request_read get_check_runs` for the matrix
  verdict. **Public repos = free + unlimited** (only concurrency-capped); the estate's repos are
  mostly public + already run GHA CI. Concurrency plan-gated (Team 60; macOS 5/50) → **Depot/Namespace**
  runner resellers are the unlimited-concurrency upgrade if needed.
- **`codex_cloud`** — BUILD tier (native, no infra). `codex cloud exec` submits a task; an OpenAI
  container clones the repo, runs the agent, returns a diff/PR. Linux/amd64-only; runs OpenAI's own
  agent (NOT our pinned gpt-5.6-sol harness) → a niche Linux lane, not the cross-platform backend.

**DEFERRED (interface ready, not set up):** `modal` (fast Linux bulk — sub-0.5s cold start, already
has `modal_sandbox_*` MCP tools; the strongest future BUILD tier), `fly` (cheapest), `e2b`, `aws_batch`,
`gcp_batch`. Adding one later = one new `backends/<x>.py`, zero engine change.

## 5. Two-tier execution (bakes in "node-green ≠ CI-green")

```
BUILD tier  (fast Linux fan-out: databricks | codex_cloud | later modal)
   -> unit writes the change on an isolated agent/ branch, runs the repo suite ON THE NODE (fast pre-filter)
VERIFY tier (github_actions matrix)
   -> the repo's REAL ubuntu+windows-latest+macos CI runs on the pushed branch
   -> adopt ONLY when the full matrix + all QZP gates are green (§8)
```
A Linux BUILD-green is necessary but NOT sufficient; the VERIFY tier is the gate that caught #145.

## 6. Lanes (what a unit does)

`gap-find` (analyze target → propose improvements) → `coverage` (built) · `mutation` (mutmut/cosmic-ray →
kill surviving mutants — the real complement to 100%-covered repos) · `security` (deep per-file review →
fix) · `docs`/`types` · `lint` · **`toolchain-upgrade`** (propose a rule/hook/skill/MCP/agent improvement —
Self scope, always PR). Backlog = gap-finder + open issues/PRs + basic-memory gotchas + owner backlog.

## 7. Self-modification guardrail (safety crux)

1. **The engine runs from a PINNED harness version** (a frozen tag/commit), never its own working copy.
   A bad self-change lands on a branch, tested in isolation; the pin advances ONLY via a curated, tested
   re-pin. The runner cannot be broken by an in-flight self-change.
2. **Anything touching harness/toolchain/hooks/MCPs is ALWAYS structural-tier → PR → owner curation.**
   Auto-adopt is *exclusively* for low-risk EXTERNAL-repo fixes (tests/docs/lint). The self-modifying
   part is never hands-off.
3. **Live `~/.claude` / `~/.agents` change only via curated merge + the existing toolchain sync** — the
   engine proposes to the agent-skills-toolchain repo; it never writes live config directly.

## 8. Tiered curation + adoption

Every unit → isolated `agent/` branch + adversarial-critic verdict + **full verification**:
- **QZP 6-gate lean CI** (the fleet contract, honored EXACTLY): (1) `ruff==0.15.17` check + `format --check`;
  (2) `basedpyright==1.39.8` standard (or caller cfg); (3) tests + **100% line+branch** cov; (4) opengrep SAST;
  (5) gitleaks; (6) osv-scanner. Plus (7) the repo's **full platform matrix** (ubuntu+windows+macos).
- **Auto-adopt** (external only): change is low-blast-radius (tests/docs/lint) AND N adversarial critics agree
  AND every gate + platform is green → squash-merge via GitHub MCP.
- **PR** (structural, or ANY self-scope): open a PR with the critic verdict attached → owner curates.
- **Known trap encoded:** run FORMATTERS not just linters — `ruff check` clean ≠ `ruff format --check` clean
  (Reframe + env-inspector both hit this). A fix is not "green" until all 6 gates + all platforms pass.

## 9. Cadence

- **Nightly** bounded wave (off-peak, budget-capped): gap-find → fan out → critique → adopt-safe/PR-structural
  → morning digest to basic-memory.
- **On-demand:** operator fires a wave anytime.
- **Event-triggered (opt-in):** new tool version / red CI / fresh basic-memory gotcha / new issue.

## 10. Success criteria

- A wave runs end-to-end unattended: proposes N changes, auto-adopts only all-green low-risk external fixes,
  PRs the rest, corrupts nothing, and writes an honest digest.
- The engine never modifies its own running (pinned) version or live toolchain outside a curated PR.
- Adding a deferred backend = one `backends/<x>.py`, no engine change.
- Every adopted change passed all 6 QZP gates + the repo's full platform matrix.

---
*Design co-located with the engine (harness repo), versioned. Next: plan-review gate → writing-plans.*
