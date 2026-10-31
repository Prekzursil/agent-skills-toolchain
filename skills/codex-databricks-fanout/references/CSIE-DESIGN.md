---
title: CSIE-DESIGN
type: note
permalink: dqverify-repo-20261013/skills/codex-databricks-fanout/references/csie-design
---

# Continuous Self-Improvement Engine (CSIE) — Design Spec

**Status:** design (brainstormed 2026-07-24; awaiting plan-review gate before implementation).
**Owner directive:** use the Codex-on-Databricks fan-out to continuously, automatically improve
ITSELF and the toolchain, plus reconcile/fix the fleet (72 active repos; generation targets the QZT-enabled set — §11) — in parallel isolated
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
| **External** | the fleet — generation reads the QZT `codex-targets.yml` ENABLED set (~5–7, fail-closed); reconcile spans the ~24–29 repos with open PRs, NOT all 72 (§11 data-fix). coverage/mutation/security/docs/lint gaps → fix to green | auto-adopt safe · PR structural |
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

Engine + lanes call the ROLE-SPLIT backends (`BuildBackend` / `VerifyBackend` — §11 R6), never a vendor SDK
directly; role-branching (build vs verify) is legitimate (the earlier "100% backend-agnostic / single Backend"
claim is RETRACTED — see §11 R6). Fleet integration (QZT/codex-fleet dispatch + dashboard) is an ADAPTER, not a coupling.

## 4. Pluggable compute backend (the portability core)

`backends/base.py` defines TWO role protocols (split per §11 R6 — the old single `Backend` was a leaky
abstraction: `harvest→dict[uid,Path]` fits a BUILD backend but not the github_actions VERIFY tier, whose
"harvest" is a CI-matrix verdict):
```
class BuildBackend(Protocol):          # databricks (built), codex_cloud
    def submit(self, units: list[Unit], meta: dict) -> Job: ...
    def poll(self, job: Job) -> str: ...                        # RUNNING | terminal
    def harvest(self, job: Job, dest) -> dict[str, Path]: ...   # uid -> artifact (+ branch ref)
    def cancel(self, job: Job) -> None: ...
    def teardown(self, job: Job) -> None: ...

class VerifyBackend(Protocol):         # github_actions (returns a verdict, not artifacts)
    def verify(self, repo: str, branch: str) -> MatrixVerdict: ...   # per-platform pass/fail
```
`Job` + `MatrixVerdict` are serializable (resumable waves — §11 R8). The 5-clause AND-gate lives in a
backend-agnostic `engine/verify.py`.

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
   Auto-adopt is *exclusively* for low-risk EXTERNAL-repo fixes (docs/lint ONLY — NEVER test code, `.github/**`,
   or any gate/threshold config; §11 R2 hard path+AST fence). The self-modifying
   part is never hands-off.
3. **Live `~/.claude` / `~/.agents` change only via curated merge + the existing toolchain sync** — the
   engine proposes to the agent-skills-toolchain repo; it never writes live config directly.

## 8. Tiered curation + adoption

Every unit → isolated `agent/` branch + adversarial-critic verdict + **full verification**:
- **QZP 6-gate lean CI** (the fleet contract, honored EXACTLY): (1) `ruff==0.15.17` check + `format --check`;
  (2) `basedpyright==1.39.8` standard (or caller cfg); (3) tests + **100% line+branch** cov; (4) opengrep SAST;
  (5) gitleaks; (6) osv-scanner. Plus (7) the repo's **full platform matrix** (ubuntu+windows+macos).
- **Auto-adopt** (external only): change is inside the §11-R2 path+AST allowlist (docs/lint; NEVER test code, `.github/**`, or gate config) AND N adversarial critics agree
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

## 11. Review revisions v2 (2026-07-24 adversarial gate — verdict REVISE; these close the 9 blockers)

The 5-lens adversarial gate (2 BLOCK: security, completeness) returned REVISE with source-cited blockers. The
DIRECTION holds (pinned-runner, always-PR-self, tiered curation, two-tier verify); these revisions are mandatory
before any build, then re-gate.

**R1 (SECURITY-CRITICAL) — no long-lived write token on the agent/test node.** The fan-out injects a fleet-wide
WRITE `github_token` as a plaintext node env var onto the same node that runs untrusted LLM code + the repo suite
(run_E.py:145/151, coverage.py:28, submit.py:31): one misbehaving unit exfiltrates a fleet-wide credential
(AGENTS.md §9). FIX: BUILD/test step gets NO write token (read-only clone); pushing a unit's `agent/` branch is a
SEPARATE step using a SHORT-LIVED, SINGLE-REPO `contents:write` token minted per unit (GitHub App installation
token, ~1h). Rotate the existing scope token (treat as exposed); redact S3 cluster logs (submit.py:33) + the digest.

**R2 (CRITICAL) — auto-adopt fenced + reversible, never near CI-executing code.** Auto-adopt applies ONLY to a hard
path+AST allowlist EXCLUDING all test code, `.github/**`, and any gate/threshold/coverage-config/CODEOWNERS file —
"low-blast-radius" is now MECHANICALLY defined by that allowlist, not prose. Every auto-adopt writes an
adoption-ledger entry and arms auto-revert-on-main-red. Anything outside the allowlist → PR only.

**R3 (CRITICAL) — an explicit RECONCILE lane (Goal 2 was undesigned).** CSIE only GENERATED new branches; existing
PRs were a gap-finder input only, so the engine grew the backlog. ADD a `reconcile` lane
(triage → rebase → resolve/close-stale/dedup → merge-under-curation) + a dedup step checking every proposed unit
against open/in-flight/rejected PRs before spawning. Either the engine owns reconcile or it delegates to QZT via a
defined interface — never silently skip it.

**R4 (SECURITY-HIGH) — mandatory auto-load-config neutralization in the Backend contract.** Before any backend
clones + runs an agent in a repo, a sanitize stage neutralizes auto-loading agent config (`.claude/`, `.codex/`,
`.mcp.json`, hooks, `AGENTS.md`/`CLAUDE.md`) as untrusted DATA (CVE-2026-47751 class). Applies to codex_cloud,
github_actions (runs the repo's own CI), and the revalidation A1 fresh clone.

**R5 (SECURITY-HIGH) — untrusted issue/PR text never drives privileged action.** Backlog ingestion parses only
allowlisted STRUCTURED fields (labels, changed paths, failing-check names) — never free text as a directive.
Issue/PR-derived units are gated to the no-token BUILD tier; a write-capable unit requires an OWNER-authored
backlog entry. CI `GITHUB_TOKEN` is read-only; any unit branch modifying `.github/workflows/**` is rejected.

**R6 (HIGH) — Backend protocol split by ROLE (drop the false "100% agnostic" claim).** `harvest→dict[uid,Path]`
fits artifact-producing BUILD backends but not the github_actions VERIFY tier (whose harvest is a CI-matrix
verdict). Split into `BuildBackend` (submit/poll/harvest artifacts + branch ref) and `VerifyBackend`
(verify(repo,branch)→matrix verdict); branch ref first-class; serializable `Job`+`Result` (for R8); add
`cancel`/`teardown`. The 5-clause AND-gate moves into a backend-agnostic `engine/verify.py`. §3's "never branches on
vendor" is deleted — role-branching is legitimate.

**R7 (HIGH) — github_actions trigger: PR-open + correlate-by-HEAD-SHA is primary.** GHA triggering was inconsistent
(workflow_dispatch 204→list-runs race AND push-triggered) and, because units "never open a PR," would not fire
`on: pull_request` CI. FIX: the unit opens a DRAFT PR; correlate check-runs by exact HEAD commit SHA (no race);
`workflow_dispatch` (per-run UUID in run-name) only for repos lacking push/PR CI; detect each repo's trigger first.

**R8 (HIGH) — idempotent, resumable, merge-queued nightly wave.** A persisted wave-state/run journal keyed by the
deterministic `agent/E-<repo>-<slug>` branch; on restart, re-attach to in-flight jobs instead of re-spawning.
Engine dedup (R3) + a per-repo MERGE-QUEUE that rebases each green branch onto latest main and re-runs VERIFY
immediately before merge (mergeStateStatus=CLEAN is isolation-only and hides pairwise overlap — C3).

**R9 (HIGH) — a MANDATORY wave ceiling for the unattended cron.** "budget-capped" had no mechanism (the 2026-07-24
CHANGELOG made the driver + per-unit timeouts OPT-IN — correct for interactive/opt-in Databricks runs, UNSAFE for a
cron). The CSIE ENGINE adds its OWN hard ceiling independent of the harness default: wave wall-clock ceiling +
max-units + max-concurrent-jobs + a MANDATORY per-unit watchdog + a $/quota gate checked BEFORE fan-out. Nightly
stays OFF until the ceiling exists. (The harness `submit_and_gate` no-timeout default is unchanged; the engine
supplies the ceiling for autonomous runs.)

**Data fix — fleet size.** "28 repos" is stale. LIVE (gh, 2026-07-24): 72 active repos, ~29 with open PRs (89 open
PRs total). The engine reads the fleet list from the QZT `codex-targets.yml` (source of truth), not a hardcoded count.

---
*Design co-located with the engine (harness repo), versioned. v2 = post-review revisions above (close R1–R9). Next: re-gate → writing-plans.*