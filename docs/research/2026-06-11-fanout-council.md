---
title: 2026-06-11-fanout-council
type: note
permalink: dqverify-repo-20261013/docs/research/2026-06-11-fanout-council
---

### ctx-eng
(none)

### tool-retrieval
(none)

### systems-pragmatist
(none)

### behavior-ux
I'll critique this from my domain: agent behavior, inquisitiveness, anti-tunnel-vision, proactivity, calibrated communication, and rescuing vague prompts. Let me ground my critique in the specific research provided rather than generalities.

The design is strong on plumbing (discovery, overhead, memory mechanics) but the behavior layer (L0/L4) has real defects when you cross-reference it against the character and antidegen clusters. Here is my hard critique.

---

## WHAT IS WRONG / RISKY

### 1. L0 is a wish-list, not a contract — and the research says wish-lists actively fail
The single most damning evidence against L0 is in the selflearning cluster (C4) and character cluster (Sycophancy 7, Calibration 3): **"be honest / ask questions / don't tunnel" as prompt text is structurally insufficient.** Calibration-3 is explicit: models verbalize calibrated-sounding uncertainty and *almost never act on it, even under extreme penalties*. L0 lists eight aspirational behaviors as a "contract" but a contract with no enforcement mechanism is exactly the CLAUDE.md-as-persuasion layer that hooks/sota C9 say degrades with context dilution. **Every L0 promise needs a named enforcement owner (hook, sub-agent, or routing-layer classifier) or it is theater.** Right now L0 floats above the four layers with no wiring down into them.

### 2. The inquisitiveness design contradicts its own evidence on *timing* and *security*
This is the sharpest internal contradiction. L4 puts inquisitiveness in `UserPromptSubmit`. But:
- **Hooks cluster #4 is unambiguous:** UserPromptSubmit hooks *cannot ask clarifying questions* — they are synchronous transform filters with a 30s timeout and no `AskUserQuestion` access. The hook can only *route to* a skill that asks. The design says "UserPromptSubmit inquisitiveness" as if the hook does the asking. It can't. This is a build-time bug, not a nuance.
- **Character cluster Novel-4 (ASPI, arXiv:2605.17324) is a landmine the design walks straight into:** mid-execution clarification amplifies prompt injection **15-16x** because the trust boundary between user instructions and MCP-retrieved content collapses. The design's "always-ask" + "research-by-default" (which pulls untrusted web/MCP content into context) + asking questions *after* tools have fired = the exact threat geometry. **Clarification must be hard-isolated to a pre-execution phase before any MCP/web tool fires.** The design has no such isolation boundary.

### 3. "Always-ask" is the wrong default and the research is loud about it
L0 says "always-ask." The character cluster contradicts this from four directions:
- **EVPI gate (Corroborated #1):** ask only when `E[utility_gain] > cognitive_cost`. "Always" ignores the cost term.
- **Approval fatigue (Corroborated #5):** Anthropic's own production data — **93% of prompts rubber-stamped**, >50% false-positive intervention rate without gating. "Always-ask" trains the user to stop reading, which destroys the signal value of the *important* questions.
- **The 10% trajectory cliff (Novel-1, arXiv:2605.07937):** goal clarification is worthless after 10% of execution. So "always-ask" isn't just costly — asking at the wrong *time* is literally baseline-equivalent to not asking.

The correct primitive is **front-loaded, EVPI-gated, single-best-question** (Shapley-selected per Contradiction-1), not "always."

### 4. Anti-tunnel-vision is named in L0 but has no mechanism anywhere in L1-L4
This is the biggest **MISSING** item relative to how much the research weights it. Tunnel-vision = goal drift, and the evidence is overwhelming:
- Character Corroborated #4 + sota C8 (**65% of 2025 enterprise agent failures are drift, not exhaustion**) + ReflAct (+27.7% from goal-gap framing over ReAct).
- The fix is concrete and **none of it is in the design:** (a) re-inject the goal *verbatim* every N turns via PreToolUse hook; (b) ReflAct "what is the gap between state and goal?" framing as the reasoning backbone; (c) inherited-drift prevention on subagent handoffs (character Novel-2 / orchestration: never pass a subagent's raw output as prefix — only structured summaries with the goal re-anchored at top).

L3 mentions goal in the checkpoint but says nothing about *periodic re-injection during a live session*, which is where drift actually happens. **L0 names anti-tunnel-vision; L4 must own it with a goal-reinjection hook.**

### 5. The Stop-gate verification hook will infinite-loop or rubber-stamp
L4 says "Stop verification gate (honor stop_hook_active)." Honoring the flag prevents the loop (hooks #2 — good), but the *content* of the gate is unspecified and the research says a naive self-verification gate is worse than nothing: selflearning C1 (self-reflection without external signal degrades performance) + antidegen X2 + character Novel-6 (AUQ Delusion Gap: System-2 reflection increases confidence in *wrong* answers 14.3% vs 3.6%). A Stop hook that asks the same model "are you done?" is an echo-chamber amplifier. **The Stop gate must check against an external signal** (tests pass per `.coverage-thresholds.json`, a heuristic rule, or a *fresh-context* reviewer — never the working agent's own judgment).

### 6. Anti-degeneration "debounce" is the wrong fingerprint and will false-positive on your own stack
L4 says "anti-degeneration debounce." The antidegen cluster N1/C3 is emphatic: **exact-match input hashing produces destructive false positives on polling tools** — and this user runs ~40 MCPs with health-check/status tools that have *identical args by design* (`server_health`, `get_binary_status`, `recent_activity`). A plain debounce will block legitimate polling. The correct primitive is the **result-aware triplet `(tool_name, args_hash, output_hash)`** — same args + different output = progress, not a loop. The design says "debounce"; it must say "result-aware triplet."

### 7. "Research-by-default" is in direct tension with the supply-chain and ASPI findings
L0 says "research-by-default" and the workspace auto-discovers community MCPs/skills. Cross three findings: discovery N6 (ToolHijacker: tool selection gameable via description text, 7-12x usage inflation), sota N7 (SKILL.md registry adversarial embeddings, 86% success), character Novel-4 (ASPI). "Research-by-default" with auto-discovered tools = pulling adversarial content into a context that then drives tool selection. **Research-by-default needs a trust tier:** vetted local allowlist vs. untrusted external, with untrusted research results quarantined from the tool-selection decision.

---

## TWO CONCRETE IMPROVEMENTS

### Improvement A: Replace L0's "contract" with a Behavior-Enforcement Matrix that wires each behavior to an owner
A one-line behavior is worthless. Make L0 a table where every behavior names *where* it is enforced and *what external signal* validates it:

| L0 behavior | Enforcement owner | External signal (anti-echo) | Timing |
|---|---|---|---|
| Inquisitive | UserPromptSubmit hook → routes to AskUserQuestion **skill** | EVPI > cost; Shapley single-Q | **Pre-exec only** (10% cliff) |
| No tunnel-vision | PreToolUse goal-reinjection (verbatim, every N) | goal-gap delta vs active-plan.md | Every N turns |
| Self-learning | Stop hook → structured 3-tip write | confidence/source/verified_by metadata | Task boundary |
| Proposes things | Boundary-timed only (PostToolBatch/idle) | — | **Never mid-task** (cognitive load 3x) |

This single change converts L0 from aspiration to architecture and forces the L0↔L4 wiring that is currently absent.

### Improvement B: A dedicated "Intent/Drift Sentinel" sub-agent — the cross-layer synergy
The non-obvious synergy is that **inquisitiveness (L0), anti-tunnel-vision (L0), the curated-sub-agent pattern (L1), and memory (L3) are the same problem viewed four ways, and one component solves all four.** Stand up a lightweight **Intent Sentinel** sub-agent (hooks Novel-5: UA-Multi Intent Agent, arXiv:2603.26233 — **69.4% vs 61.2% resolve on underspecified tasks; mid-task asks are as valuable as pre-task, 43.4% vs 41.8%**):

- It runs with a *tiny* curated toolset (L1's <30 rule) — only AskUserQuestion + read active-plan.md + basic-memory read.
- It owns inquisitiveness *and* drift detection in one loop: monitors for missing info (ask-gate) and for goal-gap divergence (drift-gate), in a context isolated from the main agent's growing history — so it doesn't inherit the main agent's drift (character Novel-2).
- It writes its findings to the checkpoint (L3), so post-compaction the *intent* survives, not just the file state — closing memory-cluster Gap-1 (no compaction-specific clarification protocol).

This resolves the timing contradiction in #2: the Sentinel does the asking the UserPromptSubmit hook cannot, and because it's a separate context it can ask mid-task *without* the ASPI trust-boundary collapse (it never touches MCP/web content). One sub-agent, four layers served.

---

## THE SINGLE CHANGE I'D FIGHT FOR

**Make clarification EVPI-gated AND hard-isolated to a pre-execution phase, and move it out of the UserPromptSubmit hook into a dedicated pre-exec elicitation step — never asking after any MCP/web tool has fired.**

I'd fight for this because it is the one change where the evidence is *triply* convergent and the current design is *actively* wrong, not merely incomplete:
1. **Correctness:** UserPromptSubmit hooks structurally cannot ask (hooks #4) — the design as written does not function.
2. **Efficiency/UX:** the 10% trajectory cliff (arXiv:2605.07937) means asking late is worthless and "always-ask" trains rubber-stamping (93%, Anthropic).
3. **Security:** ASPI (arXiv:2605.17324) makes mid-execution clarification a **15-16x prompt-injection amplifier** — and "always-ask + research-by-default" is precisely the vulnerable configuration.

Everything else in L0 is a quality improvement. This one is a fix for a behavior that, as specified, is broken, wasteful, *and* a security hole simultaneously. That is the one I would not ship without.

### security
(none)

### contrarian
I have enough to mount the critique. The corroborated research and the design's own claims are the evidence base; one memory fact (the user's documented context-rot history) is load-bearing and I already have it in the system context. I won't burn tokens re-reading the vault — that would itself be the "echo-chamber" anti-pattern the design warns about. Critique follows.

---

# CONTRARIAN CRITIQUE: the 4-layer split is the wrong primitive

## The core attack: you organized by mechanism, but failure happens by lifecycle

The 4-layer split (Discovery / Overhead / Memory / Hooks) is an **engineer's decomposition** — it groups things by *how they're implemented* (a setting, a proxy, a file, a hook). But every piece of corroborated research that matters describes failure along a **different axis: the task lifecycle** (pre-execution → execution → compaction → cross-session). The split is orthogonal to where the system actually breaks, and that mismatch is itself a design smell.

Concretely, look at what cuts ACROSS your layers and lands in no single one:

- **The 10% goal-clarification cliff** (character N1, arXiv:2605.07937) is L0 *behavior* + L4 *hook timing* + L3 *what the checkpoint stores* — a single phenomenon smeared across three layers, owned by none.
- **ASPI: clarification amplifies prompt injection 15-16x** (character N4) couples L0 (be inquisitive) directly against L4 (safety) — your two layers are in *direct contradiction* and the split hides it. "Always-ask" and "block dangerous" are not orthogonal; asking mid-execution over MCP-tainted content IS the dangerous thing.
- **HTTP transport bug** (discovery #3) means your L2-tier-A ("shared eager hot-core behind mcp-proxy on 127.0.0.1, all-AIs-HTTP") **silently nukes your L1 discovery** — every tool you put behind the HTTP hot-core is invisible to ENABLE_TOOL_SEARCH and loads 100% upfront. You put L1 and L2 in separate boxes and the L2 decision destroys the L1 mechanism. **This is a latent self-inflicted 120K-token leak baked into the architecture.**

When the most important findings are cross-layer couplings, the layer boundaries are in the wrong place. **A better primitive is the task lifecycle as a state machine** (the research calls this "statewright" / phase-gated tool access, sota C10 — 2/10→10/10 by shrinking visible tool space per phase), with your four mechanisms as *aspects woven through each phase* rather than top-level peers. The user already half-built this (`bc_fsm_redesign` in memory — they replaced a Ralph loop with an enforced phase state machine and it passed every gate). The design ignores their own best prior art.

## What's WRONG (not just missing)

**1. L0 is a hope, not a contract — and the research says so explicitly.** You named it "BEHAVIOR CONTRACT" but every item in it ("disciplined," "proactively-suggestive," "no tunnel-vision," "self-learning," "research-by-default") is a *prose persuasion* that lives in CLAUDE.md. Multiple clusters converge that **CLAUDE.md is advisory, hooks are the only enforcement** (sota C9, hooks #9, selflearning #4: compliance decays near-linearly above ~150 rules). Calling it a "contract" is exactly the Goodhart self-deception the hooks cluster warns about. A contract you cannot enforce is a wish. **Worse: L0's seven virtues are themselves ~7 more rules competing for the same attention budget that's already overflowing** — TDAD (hooks #6) showed adding TDD *instructions* without the test-map *increased* regressions because procedural prose consumed the context budget needed for actual state. L0 as written will make behavior worse, not better.

**2. "Always-ask" + "proactively-suggestive" is a documented anti-pattern at this scale.** The character cluster is brutal here and the design walked straight past it: Anthropic's own production data shows **93% of permission prompts were rubber-stamped** (character #5); frontier models without gating have **>50% false-positive intervention rates** (PRISM). "Always-ask" + "proposes things" = approval fatigue = the user stops reading = signal collapses to zero. The research prescription is the *opposite* of "always": **EVPI-gated, exception-based, front-loaded into a pre-execution phase, escalate only on 3+ denials or risk breach** (character C1, C2, #5). The design's L0 verbs are not just unenforceable — several are *actively wrong* as stated.

**3. L3's "/clear + reload-only-structured-checkpoint" is a known-broken mechanism and a fresh attack surface.** Two independent, sharp problems:
   - **PreCompact does NOT fire on manual `/compact`/`/clear`** (memory N1, GitHub #13572, closed "not planned"). The entire L3 design pivots on a hook event that *does not fire for the manual path L3 mandates*. As written, L3 silently does nothing on the exact action it's built around. The fix (move the checkpoint write to a **Stop hook**, not PreCompact) is in the research and absent from the design.
   - **The checkpoint is a poisoning vector** (memory N5, mempoison). A compromised or drifted agent in the pre-compaction window writes a high-trust note that is read back verbatim post-`/clear` — and `/clear` *guarantees* there's no surviving context to cross-check it against. **L3 doesn't reduce the echo-chamber; it builds a pristine, unsupervised, single-source-of-truth echo chamber and hands it the microphone.** Pull-not-push doesn't help if the one thing you pull is poisoned.

**4. The "no echo-chamber" goal and the "/clear-and-reload-checkpoint" mechanism are in direct opposition.** An echo chamber is *a system re-reading its own prior conclusions as if they were external truth*. `/clear` + reload-only-the-checkpoint is **the definitional echo chamber** — you delete all the messy, contradictory, corrective context (the user's real-time steering, the failed attempts, the dissent) and keep *only the agent's own distilled self-narrative*. The research is explicit that **the corrective signal lives in the failures and the external grounding, not the summary** (selflearning #1, reflexion degeneration-of-thought; character "anti-echo via structural critic diversity"). L3 optimizes for the wrong invariant.

## What's MISSING (the highest-value gaps)

**M1 — No write-discipline schema. This is THE gap, and the design has nothing.** Every memory/selflearning cluster converges on one verdict: **the write path is the bottleneck, not the read path** (selflearning #2, "retrieval failures dominate 11-46% of errors"). L3 is entirely a *read/recall* design ("pull-not-push," "reload checkpoint"). It never specifies *what gets written or in what shape*. The research hands you the schema for free and you dropped it: **conceptual-belief abstraction** (selflearning E/FinCon: "IDA MCP requires binary opened first via select_binary; cold calls return empty without error") + **causal provenance** (antidegen N8: 24.6% retrieval accuracy drop without it, costs one metadata field) + **confidence/verified_by/learned_date** + **failure-derived heuristics preferentially** (selflearning #2, ERL). Without a write schema, L3's "pull" pulls slop.

**M2 — Terminal-state tool redesign is the single highest-ROI anti-degeneration fix and it's nowhere in L4.** L4 lists "anti-degeneration debounce + no-progress-halt" — those are *detectors that fire after the loop starts*. The antidegen cluster's #1 finding (C1, corroborated by FOUR probes) is **prevention**: redesign tool *outputs* to emit terminal `SUCCESS:/FAILED:` strings instead of ambiguous "more results may be available." **7x reduction (14→2 calls), zero infrastructure, before any hook fires.** The design reaches for the expensive detector (L4 hooks, embeddings) and skips the free prevention. Related miss: **result-aware fingerprinting** `(tool_name, args_hash, output_hash)` — your 40-MCP stack is *full* of health-check/status tools with identical args by design (you literally have `server_health`, `get_binary_status`, etc.); an input-only debounce will generate **destructive false positives** that block legitimate polling (antidegen N1, C3).

**M3 — Nothing prevents inherited drift across the Claude→subagent→subagent chain, which is the user's actual architecture.** The design's L1 says "specialized sub-agents." The character cluster (N2, arXiv:2603.03258) and orchestration cluster both flag: **even drift-resistant models absorb drift when conditioned on a prior weaker agent's raw trajectory.** The user runs metaswarm — a multi-hop agent chain — so *every handoff is a drift injection*. The mitigation (never pass raw subagent output as prefix; pass structured summary + re-anchored original goal at top) belongs in the design and isn't there. Given the user's MEMORY explicitly records `feedback_parallel_agent_worktree` (parallel agents contaminate shared state), this omission is doubly glaring.

## Two concrete improvements + the non-obvious synergy

**Improvement A — Replace L0 (prose contract) + L3 (clear-and-reload) with a single CODE artifact: an append-only typed session ledger that survives compaction by construction.** Borrow LogAct (memory N6, arXiv:2604.07988: **+17% work, -41% tokens** from a typed shared log alone) and `weft`'s event-sourced state machine (hooks N4: append-only `events.jsonl` + projected `state.json`, crash-recoverable by replay, 191 tests pure stdlib). The ledger holds decisions/rationale/goal/provenance as *append-only typed events*; post-compaction recovery *replays the log* instead of trusting a lossy summary. This **kills the echo chamber** (you replay ground-truth events, not a self-narrative), **fixes the PreCompact-doesn't-fire bug** (Stop-hook append, not PreCompact), and **provides the write schema M1 demands** — one artifact subsumes three of your layers.

**Improvement B — Phase-gate everything; make ASPI structurally impossible.** Adopt statewright phase-gated tool visibility (sota C10) and put a hard wall between the **pre-execution elicitation phase** (no MCP tools loaded at all — clarification happens against the *user only*) and the **execution phase** (MCP tools live, but goal-clarification questions are now *forbidden* because you're past the 10% cliff anyway). This single structural move simultaneously: front-loads clarification (character C2), neutralizes the 15-16x ASPI injection amplification (character N4 — the trust boundary can't collapse if no untrusted MCP content is in context during elicitation), and shrinks the visible tool space per phase (anti-degeneration, sota C10). L0's "always-ask" becomes "ask *here*, never *there*" — enforced by which tools exist in each state.

**The non-obvious cross-layer synergy you're missing — close the L3→L1 loop with OATS:** Your basic-memory vault already logs session outcomes. The discovery cluster's most underrated finding (N3/OATS, +11.4% Recall@1, **zero serving-infra change, CPU-only**) is that you can shift tool-retrieval embeddings toward *historically-successful query centroids* offline. **Memory (L3) and Discovery (L1) are not separate layers — L3's logs are the training signal that makes L1 smarter every week.** The design treats them as orthogonal boxes; their actual relationship is a feedback loop. Wire the Stop-hook ledger (Improvement A) to emit `(query, chosen_tool, success)` triples, run the ~50-line OATS refinement on a `schedule`/cron, and your discovery accuracy *self-improves from your own usage* — which is also the only item in L0 ("self-learning") that would then be real instead of aspirational.

## The single change I'd fight for

**Delete the "/clear-and-reload-only-the-checkpoint" mechanism. Replace it with an append-only typed event ledger written on the Stop hook and recovered by replay.**

I'd fight for this one because it's the design's load-bearing wrong idea: it's built on a hook event that doesn't fire for the manual path (#3), it constructs the exact echo chamber it claims to prevent (#4), it has no write schema (M1), and it creates an unsupervised single-point poisoning surface (#3). The ledger fixes all four at once, is proven (LogAct/weft, pure stdlib, already in the research), and turns the user's own prior art (`bc_fsm_redesign`'s phase state machine) into the backbone of the whole workspace. Everything else in my critique is an improvement; **this one is a correctness fix** — without it, L3 actively degrades the post-compaction behavior it exists to protect.