# Agentic-Repair Reliability — the functional-acceptance layer (2026-07-07)

<!-- Extends AGENTIC-PERFECTION-PLAN.md. Grounded in a 7-agent SOTA workflow + 3 exa-research-pro
     deep-research reports (condensed index: session scratchpad agentic-repair-research-2026-07-07.md).
     Same design law: put the discipline in the HARNESS (a hook/file/2nd-agent your tired mid-task self
     can't override), anchored to an EXTERNAL signal the implementer can't author or fake. -->

## THE PROBLEM THIS CLOSES

Long repair sessions declare an app "100% tested / done" while the actual product is broken — buttons
that don't work, "shorts don't generate", in-vitro fixes while the A→B→C user flow is dead. The user
should NOT have to name each broken thing by hand for the agent to find and fix it.

**Root cause (one line):** the agent's done-signal — coverage / "tests pass" — is a **proxy the
implementer controls and can satisfy in a vacuum**, so a capable model optimizes THAT (Goodhart /
reward-hacking) and stops. The whole-app journey is never *measured*, so its brokenness is invisible;
the agent isn't lying when it says done. Amplified because the SAME context that wrote the code certifies
it (intrinsic self-correction fails — Huang ICLR'24; verifier↔generator error coupling — "Verification
Mirage" arXiv 2605.10850; judges prefer their own output — Panickssery NeurIPS'24).

**SOTA evidence:** SWE-ABS rejects **19.78%** of "passing" SWE-bench patches under adversarial held-out
tests (arXiv 2603.00520); bFinder — **17.5%** of expected behaviours untested even at >90% line+mutation
(arXiv 2606.10417); SpecBench reward-hacking gap grows with task complexity. Live proof: Reframe "100%
coverage" excluded electron `main/**`, 288 `pragma:no-cover`, two real product bugs behind `xfail(strict)`
+ `-m 'not e2e'`. The generator picked its own exam and deleted the questions it fails.

## WHERE THE EXISTING PROGRAM STOPS (why a new layer is needed, not a new always-on hook)

The shipped gates all anchor to **static / in-context** signals — necessary, not sufficient for "the app
works":

| Existing gate | Anchors to | Blind to |
|---|---|---|
| `wire-check` | static reference graph (symbol referenced 0×) | a symbol that IS wired but does the wrong thing at runtime |
| `claim-guard` | claim ↔ Bash-exit ledger | a green `pytest` that never exercised the user journey (the gameable proxy itself) |
| `test-tamper-guard` | `git diff --cached` of tests | a suite that was never strong, only never weakened |
| `quiescence` (Gem 3) | verification-pass volatility | a stably-green suite that doesn't test the feature |

None require a **runtime end-to-end acceptance run that produces the real artifact, judged by a context
that did not write the code.** That is the pre-specced-but-unbuilt "media/functional output-verification
gate." This doc builds it — as an *extension of two existing hooks*, not a new always-on hook, honouring
the ~6-active-hook latency ceiling.

## WHAT THE USER MUST PROVIDE (no hook substitutes for these — highest leverage)

1. **A held-out golden-journey script as the ONLY done-signal**, authored so the agent can't see or edit
   it — e.g. Reframe `app/e2e/golden-journey.spec.ts`: launch → import a real 16:9 clip → Make Shorts →
   assert a real vertical (1080×1920) short file exists on disk and plays. Task line, verbatim: *"Done =
   this exits 0 on a clean checkout. Coverage/unit-green are necessary but NOT sufficient and may NOT be
   cited as done."*
2. **Forbid the reward-hack surface** in the task and verify against the diff: no net-new
   `pragma:no-cover` / `xfail` / `skip` / coverage-omit / `addopts` / `-m` marker / `collectCoverageFrom`
   / CI-trigger edits; the final report must include a git diff of every test/CI/coverage-config change —
   that diff is where the gaming hides.
3. **Red-repro before every fix, artifact with every "fixed"** — script the failure as a red E2E first;
   attach the produced mp4/screenshot, never an isolated unit test, as proof.

## THE BUILDABLE DELTA (this branch: feat/functional-acceptance-gate)

Two existing hooks get the missing external-signal capability. **Defaults are unchanged** — every new
behaviour is opt-in via an env flag, so nothing regresses; block stays off until explicitly enabled.

- **G1 — `claim-guard` functional-acceptance category.** Adds a `functional` claim class (assertive
  product "it works now / shorts generate / the flow works / done" phrasing, same hedge-suppression as the
  existing classes). Its evidence bar is **higher and external**: a generic green `pytest` does NOT
  satisfy it — it requires an `ok=true` command matching an **e2e/acceptance signature** this turn
  (`playwright test`, `*e2e*`, `*golden*journey*`, `*acceptance*`, `cypress`, `npm run e2e`, an artifact-
  producing run). A functional claim without that external evidence → warn (default) / **exit-2 block**
  under `CLAIM_GUARD_MODE=block` (narrow: block fires only for an unsupported *functional* claim). Fail-open
  on any exception.
- **G2 — `test-tamper-guard` opt-in BLOCK.** New `TEST_TAMPER_MODE` (default `warn` = current behaviour
  exactly). Under `TEST_TAMPER_MODE=block`, the high-confidence signals (`file_deleted`,
  `assertion_net_drop`, `skip_added`) exit 2 to block the commit; `trivial_assert_added` stays warn
  (higher false-positive risk). Still git-diff-anchored, fail-open, non-nag.
- **Back-port.** Both hooks were live-only in `~/.claude/hooks` and orphaned from this repo; this branch
  captures them into version control so `sync-hooks.ps1` manages them going forward.

## CASE STUDY — Reframe "Make Shorts" (2026-07-07, the thesis, proven)

A live validation, not a hypothetical. Reframe shipped v1.4 with **100% coverage, green units** — and
Make Shorts never produced a file on Windows. A held-out golden-journey (`app/e2e/golden-journey.spec.ts`)
that drove the real Electron GUI + live Python sidecar and asserted a real vertical short on disk
red-repro'd it, and — iterating red→fix→red — peeled back **three distinct Windows-only code bugs**, each
sitting exactly at a seam the tests mock and Linux CI can't reach:

1. **CRLF in WSL shell scripts** — `set -euo pipefail\r` aborts under WSL bash.
2. **verthor teardown SIGSEGV** — a valid 1080×1920 short is rendered + flushed, then the process
   SIGSEGVs at mediapipe/tflite atexit; the wrapper's `set -e` discarded the good output.
3. **vidstab `.trf` path** — an absolute Windows path breaks ffmpeg's `-vf` filtergraph parser (the drive
   colon reads as an option break; no escaping works). Never manifests on Linux (`/tmp/...`, no colon).

Why coverage was useless here: `reframe.py` is deliberately *"unit-testable with no WSL, no mediapipe, no
real verthor"* (mocked seam), the ffmpeg runner is an injected seam (tests never spawn ffmpeg), and CI
runs on Linux. So every bug lived precisely where the proxy metric can't see. **The golden-journey caught
what the entire test suite structurally could not**, and after the three fixes the full pipeline produces
a real short end-to-end (`job.done → clips:[…]`). A fourth blocker (the claudeshorts YuNet model not
provisioned) turned out to be a first-run *setup* step, not a code bug — the journey distinguishes those
too. Full write-up: `Reframe/docs/research/GOLDEN-JOURNEY-FINDINGS-2026-07-07.md`.

**Process lesson (for the harness itself):** for a multi-stage pipeline failure, **capture the actual
error before fixing** — do not infer the failing stage from surviving artifacts. Here the intermediate on
disk (`.cut.mp4` only) pointed at "reframe", but the real error was two stages earlier (stabilize); a
direct sidecar-RPC harness that drained the job's stderr (`jobs.py` `log.error` traceback) was what named
it. Inference cost several fix-the-wrong-thing detours until an external capture nailed it.

## NORTH-STAR REPAIR FLOW (how a repair session should go)

audit-first (map the app's user journeys AND which are broken, with evidence) → confirm the golden
journeys as the done-signal → red-repro each symptom E2E → build a defect graph (GraphLocator-style,
FSE'26) → dispatch bounded-scope fix agents in worktrees → inner-loop only the affected tests
(Ekstazi/TIA 32–70% cut) → **fresh-context / cross-model acceptance review over the real running app** →
full suite + E2E + mutation once at the commit boundary → merge. **Never self-certify.** Mirrors
VeriMAP / MetaGPT / Agentic-Harness-Engineering (arXiv 2604.25850): planner → executor → *independent*
execution-grounded verifier.

## KEY CITATIONS / TOOLS

Pragma (AST test-gaming detector) · GameGen-Verifier + RLEF (execution-grounded, 92% vs 58.8%) ·
SWE-ABS / UTBoost (held-out adversarial) · bFinder (behavioural-coverage gap) · Weaver + VeriMAP + MetaGPT
(independent/aggregated verifiers) · PlayCoder (GUI playtest) · TestSprite / Pathfinder / CoreStory /
GenIA-E2ETest (auto user-journey extraction) · Ekstazi + MS TIA + CloudBees (test-impact selection) ·
GraphLocator (defect graph) · ProjDevBench (4.81M tokens/problem — why triage-then-dispatch beats
edit→rerun-full-suite). Full condensed reports: session scratchpad `agentic-repair-research-2026-07-07.md`.

## SEQUENCING

G1 + G2 ship opt-in (this branch). Enable `CLAIM_GUARD_MODE=block` / `TEST_TAMPER_MODE=block` per-repo
once each has burned in without false-positives. The golden-journey (G0, user-authored) is the keystone —
the hooks only enforce that a `functional` "done" claim is backed by such a run. Next candidates (unbuilt):
a journey-coverage gate (every declared journey has ≥1 passing E2E before "done") and a cross-model
acceptance reviewer over the running app.
