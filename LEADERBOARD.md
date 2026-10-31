---
title: LEADERBOARD
type: note
permalink: dqverify-repo-20261013/leaderboard
---

# Toolchain Leaderboard — best-of hooks, skills & MCPs

**What this is:** an opinionated, *evidence-graded* ranking of the components that most improved real work — drawn from lived experience (the multi-front Battle Cats RE/build marathon, the events-resolution research, the extended-program scoping) and the project's documented history, **not** a feature inventory. Includes **vendored** components, not just home-grown ones.

**Legend:** `[C]` custom (built here) · `[V]` vendored/external · `[P]` plugin (metaswarm/superpowers). Tiers: **S = to-die-for** (changed the outcome, not just convenient) · **A = high value** · **B = solid, reach-for-it often**. Each pick cites *why it earned the rank*.

---

## 🪝 Hooks

### Tier S — to-die-for
- **event-ledger** `[C]` — durable decision/milestone capture (`note.py`) + SessionStart replay. The single biggest reason a days-long, compaction-spanning program stayed coherent: every gate verdict, blocker, and lesson survived because it was on the ledger, not in context. Nothing else gave continuity like this.
- **edit-validate** (Stop hook) `[C]` — validated files touched each turn and blocked on lint (ruff E401/E402/F401, F841). Caught broken scratch files *every* time an agent left debris, and forced fixing the source not weakening the check. Quietly kept the tree shippable.
- **inquisitiveness / falsify-check + recall-first** `[C]` — the PreToolUse falsify nudge ("state your load-bearing assumption + the cheapest test to disprove it") directly triggered the independent greps that caught two HEAD-breaking orphaned-commit defects and verified the "headline is dark" finding firsthand. Recall-first surfaced prior art before re-deriving. Highest defect-catch-per-token of any hook.

### Tier A — high value
- **claim-guard** `[C]` — blocks "done / gates green / ready to merge" claims without evidence. The antidote to a green-suite-≠-delivered over-claim (which a final review later confirmed mattered).
- **precompact-basicmemory** + **precompact-snapshot** `[C]` — auto-checkpoint before compaction; the safety net that makes "nothing is truly lost" real.
- **anti-degen** `[C]` — `(tool,args,output)` fingerprint loop-breaker; stops repeat-action spirals before they burn a cycle.
- **goal-reinject** `[C]` — re-injects the original goal to fight tunnel-vision across long multi-step work.
- **memory-guard** `[C]` — protects curated MCP enabled/disabled state from being wiped by schema-validator noise (load-bearing for the token-reduction harness).

### Tier B — solid
- **sonar-secrets** `[C]` (relevant the moment committed-secrets surfaced) · **test-tamper-guard** `[C]` (prevents gaming the suite) · **tool-preflight** `[C]` (flags dead MCP venvs/CLIs at SessionStart) · **harness-trim** `[C]` (context-rot reduction) · **stopfailure-notify** `[C]`.

---

## 🧠 Skills

### Tier S — to-die-for
- **grill-me** `[V]` + **grill-me-extensive** `[C]` — relentless one-at-a-time decision interviewing. The entire 35-decision extended-program scope was locked through it; the extensive addon (scout → fan-out → categorized list → foundation-first → one-at-a-time → capture → converge, with 8 grill modes) turned a fuzzy "do more" into a decided, auditable program. Best planning tool in the set.
- **brainstorming** `[P superpowers]` + the **fan-out brainstorm pattern** — generated 51 distinct roadmap directions across 8 lenses that one mind would not have. Divergence-on-demand.
- **metaswarm design-review-gate + plan-review-gate** `[P]` — caught what per-unit tests structurally cannot: a real correctness error (the solver was trait-blind), a safety bug (best-effort backup), and the integrated "headline is dark / built-but-unwired" failure. Gates that *find real defects* are worth their cost.

### Tier A — high value
- **simplest-probe-first** `[C/P]` — "cheapest deterministic diagnostic before the expensive path." A `git status` probe caught the orphan defects before they shipped; repeatedly saved a fan-out.
- **fresh-context-verify** `[C/P]` — re-derive a load-bearing claim in a clean context that can't inherit your reasoning. The discipline behind the independent B1 confirmation.
- **using-superpowers** `[P]` — the skill-discovery meta-skill; the reason the right skill gets invoked at all.
- **ci-silent-pass-lint** `[C]` — detects CI that reports green while masking findings (11 silent-pass shapes). Directly defends the "gates green" claim.
- **battlecats-event-unlock** `[C]` — the domain keystone: the proven dual-dependency unlock model + decisive offsets + the approaches proven DEAD (so they aren't re-walked).

### Tier B — solid / domain
- **test-driven-development**, **dispatching-parallel-agents**, **subagent-driven-development**, **executing-plans** `[P superpowers]` (the execution backbone) · **autoresearch** + **consensus-tooluniverse-research** `[C]` (paper harvest) · the RE suite **binary-ninja / ghidra / binja-sigmaker / angr / bindiff** `[C]` · **humanizer / agentic-humanizer** `[V]`.

---

## 🔌 MCP servers

### Tier S — to-die-for
- **basic-memory** `[V]` — the canonical semantic cross-session vault. The memory layer that makes "recall prior work instead of re-explaining" possible; pairs with the precompact hooks as the continuity spine.

### Tier A — high value
- **RE stack — IDA-Pro / Binary-Ninja / Ghidra / Frida MCPs** `[V]` — the entire Battle Cats reverse-engineering effort (offsets, hooks, the guerrilla-window solve) ran on these; irreplaceable for binary work.
- **web research — firecrawl / tavily / exa** `[V]` — powered the 240-mapid events resolution (multi-modal sweep) and the would-be wiki backfill; richer than built-in search.
- **scholarly-access** `[C]` — lawful OA paper resolution/download (the principled replacement for the quarantined Sci-Hub MCP).

### Tier B — solid
- **tooluniverse** `[V]` (biomedical/DDI research front-end) · **repomix** `[V]` (codebase packing for analysis) · **context7** `[V]` (current library docs) · **playwright / chrome-devtools** `[V]` (visual/UI) · **mcp-funnel** `[V]` (lazy MCP proxy that tamed per-session duplication).

---

## 🏅 Cross-cutting patterns that punched above their weight
*(not single components, but the practices that most improved quality)*
- **Parallel-wave build** (per-WU isolated worktrees or shared-worktree disjoint-file writes + serial integrate-gate): ~3–4× faster than serial with the full 4-phase gate intact.
- **Orphan-check post-commit** (`git status` must be clean of untracked source/test): the only thing that catches a committed-module-imports-uncommitted-module broken HEAD — the suite passes *with* the untracked files present, so tests never catch it.
- **Adversarial verify with an EXTERNAL signal**: a fresh reviewer re-running tests / re-deriving a claim beats any amount of self-assessment — every defect this program caught came from an external check, never from introspection.

---
*Basis: lived outcomes + the event-ledger/basic-memory record as of 2026-06-16. Rankings are about demonstrated impact on real work, and are meant to be revised as evidence accrues.*