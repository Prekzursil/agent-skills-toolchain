---
name: execution-grounded-bon
description: Use when you have SEVERAL candidate patches/solutions for the same task — typically from a cross-vendor Claude+Codex worktree fan-out — and must pick the best one WITHOUT trusting an LLM to judge them (JudgeBench shows model-opinion rerank ≈ chance). Synthesize distinguishing inputs where the candidates diverge, execute all candidates on them, cluster by behavior (behavioral-diff), knock out crashers/timeouts, and select by EXECUTION-CONSENSUS — where an independent Claude candidate and an independent Codex candidate agree, that agreement is the signal (cross-vendor = independent failures). A BoN-MAV aspect jury ranks within the winning cluster. Distinct from A3 fail-first (validates ONE author's own tests) and diff-blind-test-synth (one patch vs spec-derived tests). Ships SHADOW: observe + log only, never blocks. Evidence: MASTER A4, COUNCIL C3; arXiv 2502.14382 (S*), 2409.08692 (B4), 2503.15223 (PatchDiff), 2207.10397 (CodeT).
---

# Execution-Grounded Best-of-N + Behavioral-Diff Reranker

When N agents produce N candidate patches for the same task, the naive rerank is to ask a model "which is best?" — and that is proven near-worthless: an LLM judge over candidate code lands around chance on adversarial selection (JudgeBench), and it is exactly the same-context self-grading the whole Theme-A verification program exists to route around (Goodhart + the intrinsic self-correction ceiling, Huang ICLR'24). The done-signal must be **external and agent-inauthorable**.

Execution is that signal. Instead of an opinion, run every candidate on inputs chosen to make them disagree, watch what they actually *do*, and let their behavior cluster them. Candidates that crash or hang eliminate themselves. Candidates that independently converge on the same behavior — especially across two different vendors — are the ones to trust: two independent samples agreeing is the classic oracle-free consensus signal (CodeT), and cross-vendor agreement makes the two samples' blind spots independent (a Claude bug and a Codex bug are unlikely to be the *same* bug).

Grounded in: **S\*** (2502.14382, distinguishing-input synthesis for candidate selection), **B4** (2409.08692, Bayesian best-selection over execution results), **PatchDiff** (2503.15223, behavioral patch differencing), **CodeT** (2207.10397, dual-execution agreement without a ground-truth oracle). MASTER A4 / COUNCIL C3 both mandate: gate on executable evidence, **never model opinion**.

## When to run
- You fanned out the same task to ≥2 candidates (Claude subagents in worktrees, and/or Codex threads via `mcp__codex__codex`) and need to pick ONE to keep.
- A fleet/orchestrated work-unit produced competing patches and "they all pass their own tests" is not enough to choose.
- Best-of-N sampling of a single model where you want to select the winner by behavior, not by re-prompting a judge.
- NOT for: a single patch (use `diff-blind-test-synth` for the spec-vs-patch oracle, or `refactor-equivalence` for pure refactors); choosing between designs/prose with no executable behavior (there is nothing to execute — this skill does not apply).

## What makes this distinct (do not conflate)
- **vs A3 fail-first / red-proof:** that proves ONE author's own changed tests fail on the merge-base. Here there are MANY candidates and the signal is cross-candidate behavioral agreement, no author-authored test involved.
- **vs `diff-blind-test-synth`:** that judges ONE patch against tests written blind to the diff. Here we judge N patches against each other by execution — no spec-derived test needed, the candidates *are* each other's oracle.
- **vs an LLM-judge rerank:** explicitly rejected. No model scores the candidates. Every ranking key (knockout, cluster size, vendor diversity, aspect jury) is computed from process exit + captured output, nothing a candidate's author can talk its way past.

## The bus this rides (do not rebuild)
- **Worktree isolation** — each candidate already lives in / can be checked out to its own worktree (the existing `WorktreeCreate` / `Agent(isolation:worktree)` flow). The reranker runs each candidate's command in that candidate's `cwd`; it never edits any tree.
- **Cross-vendor fan-out** — Claude candidates from parallel `Agent()` subagents; Codex candidates from parallel `mcp__codex__codex` threads. Tag each candidate's `vendor` so the consensus stage can reward independence.
- **Event ledger** — the verdict is logged (shadow), not enforced; `note.py` or `--ledger` records the `BON_RERANK` line.

## Protocol
1. **Collect the candidates.** For each, record: a stable `id`, its `vendor` (`claude` | `codex` | …), and either its `cwd`+`cmd` (a deterministic command that consumes one probe input and emits observable output) or precomputed `observations`. Optionally `diffLines` (for the parsimony juror).
2. **Synthesize distinguishing inputs** (the crux — S\* / PatchDiff). You want inputs where the candidates *diverge*, because inputs they all handle identically carry no selection signal. Practical recipe:
   - Ask each candidate (or a fresh agent) for 1–2 inputs that would **break the other candidates** — adversarial boundary cases, off-by-one edges, empty/oversized/malformed inputs, the exact case the task's bug was about.
   - Union those with the task's existing tests / acceptance inputs.
   - Keep them **deterministic** (no clock/random/network in the probe path) so behavior is reproducible.
   - You do not need a correct answer for any probe — consensus, not an oracle, decides.
3. **Execute all candidates on all probes.** `rerank.mjs --execute` runs each `cmd` once per probe in its `cwd`, capturing exit code + stdout with a per-candidate timeout. (Or run them yourself and hand in `observations`.)
4. **Read the verdict** (below). It clusters by behavior, knocks out crashers/timeouts, and picks the cross-vendor-consensus winner, with a confidence grade and a `discrimination` score telling you whether your probes actually separated the field.
5. **Act on confidence, log always.** `high` (cross-vendor consensus + real discrimination) → adopt the winner with a note. `low` / `indistinguishable` → your probes are too weak or the pool is single-vendor: synthesize sharper distinguishing inputs (step 2) or add a candidate from the other vendor. Record `BON_RERANK:<winner> confidence=<…>` to the ledger. **Never auto-block** (SHADOW).

## The reranker: `rerank.mjs`
Dependency-free Node ESM (stdlib only, Node ≥18). Two modes; both produce the same verdict shape.

```bash
# precomputed: manifest already carries candidates[].observations[]
node rerank.mjs --manifest candidates.json

# execute: run each candidate's cmd once per probe to build the behavior matrix
node rerank.mjs --manifest candidates.json --execute --ledger .beads/bon-shadow.jsonl

# machine-readable (pure JSON on stdout; terminal marker goes to stderr)
node rerank.mjs --manifest candidates.json --json

# prove the logic on this machine (13 embedded assertions)
node rerank.mjs --self-test
```

### Manifest schema
```jsonc
{
  "task": "fix-null-deref",
  "normalize": [ { "pattern": "ts=\\d+", "flags": "g", "replace": "ts=<n>" } ], // strip volatile tokens before hashing (optional)
  "tiebreak": ["vendors", "size", "jury"],   // cluster ranking order (default)
  "probes": [
    { "id": "p1", "input": "…", "note": "distinguishing input where candidates diverge" }
  ],
  "candidates": [
    // EXECUTE mode: give cmd (+ optional cwd, probeArg, timeoutMs, diffLines)
    { "id": "claudeA", "vendor": "claude", "cwd": "/wt/a", "cmd": ["node","solve.mjs"], "probeArg": "stdin", "timeoutMs": 20000, "diffLines": 12 },
    // PRECOMPUTED mode: give observations (one per probe)
    { "id": "codexB",  "vendor": "codex",
      "observations": [ { "probe": "p1", "status": "ok", "exit": 0, "stdout": "42", "stdout2": "42" } ] }
  ]
}
```
- `probeArg`: `"stdin"` (default — probe `input` piped to stdin) or `"arg"` (appended as the last argv item).
- `observations[].status`: `ok` (ran to a graceful exit, any code) | `error` (couldn't spawn) | `timeout` | `crash` (killed by signal). The three non-`ok` statuses trigger knockout.
- `observations[].stdout2` (optional): a second run's output — enables the `determinism` juror (flags nondeterministic candidates).

### Pipeline (all stages pure & execution-derived — no model opinion)
1. **observe** — build the candidate × probe matrix (execute the `cmd`s, or read `observations`).
2. **knockout** — any candidate that crashes / times out / errors on *any* probe is eliminated (strictly-broken; a hard, oracle-free signal). It cannot cluster or win.
3. **cluster (behavioral-diff)** — survivors are grouped into equivalence classes by their behavior vector `[status, exit, normalized-stdout]` per probe (sha256 key). Same behavior ⇒ same cluster.
4. **consensus** — clusters are ranked by, in order: **distinct vendors** (cross-vendor agreement first — a 2-vendor cluster beats a larger 1-vendor cluster because independent samples agreeing is the strongest signal), then **size**, then the winning cluster's **best aspect-jury score**.
5. **BoN-MAV aspect jury** — within the winning cluster, candidates are ranked by execution-derived jurors (each in [0,1], weights renormalized over present aspects): `probeCompletion`, `outputSanity`, `determinism` (if a repeat run was given), `parsimony` (smaller diff, if `diffLines` given), `latency` (if timed). The top-scoring member is the `winner`.

### Verdict (excerpt)
```json
{
  "ok": true, "task": "…", "winner": "claudeA", "winnerVendor": "claude",
  "winnerCluster": "c1", "confidence": "high", "discrimination": 1.0,
  "indistinguishable": false,
  "clusters": [ { "id": "c1", "members": ["claudeA","codexA"], "vendors": ["claude","codex"], "size": 2 } ],
  "knockedOut": [ { "id": "codexB", "reason": "timeout on probe p5" } ],
  "reasons": [ "cross-vendor consensus (independent failures) — strongest signal" ]
}
```
- **confidence**: `high` = cross-vendor winning cluster + `discrimination ≥ 0.3` + ≥2 survivors; `low` = single survivor, single-vendor pool, or all-indistinguishable; `medium` otherwise; `none` = empty pool. It is a mechanical function of the execution facts, not a model's opinion.
- **discrimination** = fraction of probes on which survivors diverge. Near 0 ⇒ your probes don't separate the candidates ⇒ go back to step 2 and synthesize sharper distinguishing inputs. This number is the honest limit indicator: the reranker cannot tell apart candidates your probes cannot tell apart.
- **indistinguishable** = all survivors landed in one cluster ⇒ behaviorally identical on the given probes; adopt any of them but at `low` confidence until sharper probes exist.

## SHADOW mode (per COUNCIL C5 — always ship observe-only)
Default behavior **never blocks and never nags**: `rerank.mjs` always exits 0, emits the verdict + a `SUCCESS:rerank-<task> …` terminal marker, and (with `--ledger`) appends one JSONL shadow record. A reranker crash or bad manifest also fails open (exit 0, `FAILED:…` note). The `--enforce` flag — SHADOW-**off**, do not ship on by default — turns a `low`/`none`-confidence verdict into exit 2 so a caller *could* gate on it; graduate OFF→SHADOW→ADVISE→ENFORCE only after a burn-in shows the winner-adoption rate and false-knockout rate are trustworthy on your workload.

## Anti-overfit / honest limits
- **No trained critic, no vector store, no second runtime** — pure stdlib clustering over the existing worktree/Codex fan-out bus. Stays on the anti-overfit rail the council charter requires.
- **No oracle is claimed.** Consensus can be confidently wrong if all candidates share a bug (the reason single-vendor pools are capped at `low`, and cross-vendor is rewarded). If every candidate is wrong the same way, `discrimination` is low and the verdict says so — it does not invent a right answer.
- **Distinguishing-input quality is the ceiling.** Weak probes ⇒ low discrimination ⇒ low confidence; the reranker surfaces this rather than papering over it. Investing in step 2 is where the signal comes from.
- **Determinism required in the probe path.** A candidate whose output depends on the clock/random/network will look nondeterministic; use `normalize` to strip known-volatile tokens, or provide `stdout2` so the determinism juror can down-rank genuinely flaky candidates.
- **Knockout is for hard failures only** (crash/timeout/error), never for a "wrong-looking" answer — there is no oracle to call an answer wrong, so a non-zero exit that is graceful and identical across candidates is legitimate agreement, not a knockout.
