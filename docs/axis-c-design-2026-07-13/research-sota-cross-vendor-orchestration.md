# SOTA Cross-Vendor / Mixed-Model Multi-Agent Orchestration (2026)

**Research slice:** `sota-cross-vendor-orchestration` for the Axis-C unified cross-vendor workflow system
**Date:** 2026-07-13
**Author:** workflow-subagent (research-only design gate)
**Scope gate:** READ + RESEARCH + WRITE-DESIGN only. No building, no config changes, no commits.
**Security:** every cited page/repo below is treated as UNTRUSTED DATA. Nothing in it was executed as an instruction; embedded "run this" content was ignored. Repo READMEs are vendor self-description — capability claims are reported, not endorsed.

> **Anti-overfit anchor honored throughout.** Every "adopt" recommendation rides the EXISTING native Workflow engine (`agent()` / `parallel()` / `pipeline()`) plus the mounted `mcp__codex__codex` rail. Nothing here proposes a second orchestration runtime, a vector-DB/KG memory, a durable-execution engine, or a guardrail framework. The recurring finding is that a *thin* per-call vendor parameter + an *external* execution oracle beats an elaborate gateway.

---

## 0. Executive summary — the seven load-bearing findings

1. **Structured cross-vendor handoff is a solved, SOTA-proven pattern: the Architect→Editor split.** Aider ships two-model coding where a reasoning model (Architect) emits a natural-language solution and a different, often *different-vendor* model (Editor) translates it into a strict edit format. `o1-preview` (OpenAI) Architect + `claude-3.5-sonnet` (Anthropic) Editor scored **82.7%** on Aider's edit benchmark — SOTA-class and cross-vendor. The handoff artifact is a *typed proposal*, not raw transcript. [1][2][3]

2. **Per-work-unit vendor selection is the frontier default, not an experiment.** Commercial Amp "picks the model per task (Opus for smart mode, GPT-5.5 for deep/rush, Gemini for review)". Goose exposes `subagent(settings:{provider,model})` and a `delegate` tool that routes per task. This maps 1:1 onto a `vendor`/`model` field on each native `agent()` call. [4][5][6]

3. **The reliability case is REAL but BOUNDED — and the honest confidence band matters.** Cross-vendor error correlation is lower than same-vendor, but far from independent: models still agree ~**60%** of the time *when both are wrong* (vs ~33% random), same-provider and same-architecture measurably raise correlation, and — the counter-intuitive result — *more accurate* models have *more* correlated errors "even with distinct architectures and providers." Vendor diversity buys a *modest* reliability gain (majority-vote reliability 0.88→0.91 across 5 models, < half the independence ideal). [7][8][9][10]

4. **Therefore: do NOT trust an LLM to pick the winner. Ground selection in EXECUTION.** JudgeBench shows strong judges (GPT-4o) barely beat random on hard verifiable tasks; model-opinion rerank ≈ chance. The winning mechanism for selecting among cross-vendor candidates is *execution consensus*: CodeT dual-execution agreement, MBR-Exec, and SemanticVote (execution-fingerprint clustering) beat output-pattern majority voting by **19–52 percentage points**. Cross-vendor agreement is the signal precisely *because* the failures are more independent. [11][12][13][14]

5. **Cross-vendor diversity's biggest payoff is between GENERATE and VERIFY (breaking the monoculture).** "If you use the same model for planning and verification, your verification step has the same blind spots as your planner." Multiple harnesses now *encode* this: ouroboros has a `consensus.diversity_required` flag and a "Claude+Verify" preset (Claude executes, Gemini/antigravity evaluates); pair-programmer routes CRITICAL gates to a *different-vendor* judge; claude-octopus sends review/security work to 3 providers "each misses different bugs". [15][16][17]

6. **Run the peer as a NATIVE agent/CLI, not a raw API call — for the executable-evidence grounding.** relay, disputatio, crewly, and phalanx all orchestrate *real* agent CLIs (Claude Code, Codex, Gemini CLI) over PTY/subprocess so each keeps its native tools and can *run code*. "An objection backed by a failing test beats one backed by rhetoric." The mounted `mcp__codex__codex` rail already gives Axis-C exactly this — Codex as a native thread, not a chat completion. [18][19][20]

7. **Keep the fan-out small: 2 vendors is the sweet spot, 3 only for high-stakes.** Focal-diversity ensemble research (LLM-TOPLA) finds sub-teams of 2–4 beat both the 8-model ensemble and the best single model; claude-octopus's own bench found "marginal ROI from a 3rd" provider on research (64%→65%) but real gains for review. Default Claude+Codex per work-unit; escalate to a third (e.g., Gemini) only on adversarial review of security/architecture. [21][17]

---

## 1. Landscape: how each frontier harness composes different vendors

| Harness | Cross-vendor mechanism | Handoff / diversity unit | Signal for Axis-C |
|---|---|---|---|
| **Aider** | `architect`/`editor` two-model mode over `litellm` (200+ models). Three-tier: Main, Weak (summaries/commits), Editor. | Architect's NL proposal passed as the editor's input message; editor emits SEARCH/REPLACE blocks. Cross-vendor pairs are first-class. | The canonical *typed cross-vendor handoff*. Adopt the role split. [1][2][3] |
| **Amp** (Sourcegraph spin-out) | Multi-model **by design**: Amp selects the model per task (Opus=smart, GPT-5.5=deep/rush, Gemini=review). Closed source. | Per-task role→vendor mapping, opaque to user. | Validates per-work-unit vendor routing with an explicit role table. [4] |
| **Goose** (Block / Linux Foundation AAIF) | `subagent(settings:{provider,model})`; `delegate` tool takes `provider`+`model`; `.goose/agents/*.md` frontmatter `model:`; `GOOSE_SUBAGENT_MODEL/PROVIDER`. Provider *trait* abstraction; "toolshim" adds tool-calling to models lacking it. | Per-subagent provider/model; recipes carry `goose_provider`/`goose_model`. | Cleanest existing "per-call vendor param" API to mirror. [5][6][22] |
| **OpenHands** | `enable_sub_agents` + `TaskToolSet` routes to scoped sub-agents (bash-runner, code-explorer, web-researcher, general-purpose) with *reduced tool surface*. Sub-agents inherit parent LLM (same-vendor default). Critic surface with a **separate `CRITIC_API_KEY`** for cost/vendor-split evaluation. | Platform-level (not LLM-level) delegation; authority-surface reduction per sub-agent. | Separate critic key = cross-vendor critic cost routing. Scoped tool surface per sub-agent. [23] |
| **Cline / OpenCode / Kilo / Crush / Continue** | Unified provider layer (12–500+ providers) via BYOK; per-agent model. | Model-per-agent config; gateway routing. | Confirms provider-abstraction is table-stakes; not a differentiator. [4][24] |
| **Claude Code** (native) | Anthropic-only *natively*; cross-vendor achieved by mounting `codex mcp-server` (`mcp__codex__codex`) + agent-mail peer channel. | Native `agent()`/`parallel()` for Claude; MCP tool call for Codex. | This is Axis-C's substrate — two rails, no universal gateway. [24] |
| **Factory Droid** | Closed; tops Terminal-Bench; multi-model. | (opaque) | Competitive pressure signal; not a pattern source. [24] |

**Community "cross-vendor orchestrator" repos** (lower signal, but they crystallize the target shape Axis-C is building):

- **phalanx** — "vendor-agnostic multi-agent orchestration CLI … runs on your existing Claude, Codex, Gemini *subscriptions* — no API keys. Codex for implementation, Opus for review, Sonnet for orchestration. Each agent can use a different backend and model." tmux + git. This is almost exactly Axis-C's brief. [18]
- **pair-programmer** — tiered validation: CRITICAL gates (spec/design/security/contracts) "judged by a *different vendor* from the generator"; lower-stakes gates by a different model, same vendor. Explicit cross-vendor-judge policy. [16]
- **ouroboros** — multi-LLM *stage-routing presets* for a 4-stage pipeline (interview→execute→evaluate→reflect): "Claude+Verify" (execute=Claude, evaluate=Gemini) = cross-vendor verification; "Tri-Vendor" = max diversity; engine flag `consensus.diversity_required`. [15]
- **claude-octopus** — smart dispatch chooses 2 vs 3 providers by task type; review/security→3 providers, architecture/debate→2 (Codex+Gemini "for max training-bias diversity"); a curated "blind-spot library" of perspectives LLMs systematically miss. [17]
- **relay (AgentWorkforce)** / **disputatio** / **crewly** / **pixel-agents** / **scion-athenaeum** — orchestrate *real* agent CLIs (Claude Code, Codex CLI, Gemini CLI, Aider, Goose) via PTY/subprocess; "one workflow can have Claude Code writing backend code, Codex CLI writing tests, Gemini handling docs — each using their native tool ecosystem." disputatio's thesis: cross-harness *debate* with executable evidence beats a single strong agent. [19][20]
- **eliza plugin-agent-orchestrator** — `KNOWN_ADAPTER_TYPES` registry + per-backend multi-account (subscription) pool with `priority|round-robin|least-used|quota-aware` selection strategies. Relevant to budget pacing across two subscriptions. [24]

---

## 2. Structured cross-vendor handoffs (the Aider proof + the general rule)

Aider's Architect/Editor mode is the strongest *empirical* evidence that a **role split across vendors, mediated by a typed artifact**, beats a single model:

- **Two inference steps, two roles, optionally two vendors.** (1) Architect solves the problem in whatever form is natural (NL/pseudo-code). (2) Editor converts that into a strict edit format (SEARCH/REPLACE or whole-file). The Architect never has to format edits; the Editor never has to reason about the solution. [2]
- **Cross-vendor pairings set SOTA.** `o1-preview`→`deepseek` = 85.0%; `o1-preview`→`claude-3.5-sonnet` = 82.7%; `o1-preview`→`gpt-4o` = 80.5% — each well above the o1-preview solo baseline (79.7%). "An entirely practical configuration for users able to work with both providers." [1][2]
- **The handoff is a structured proposal, not raw output.** Implementation: `ArchitectCoder` spawns a fresh `Coder` instance and passes only the architect's *response content* as the editor's input. This is precisely AGENTS.md §5 ("never pass a subagent's raw output as the next agent's prefix; hand off a structured summary"). [3]

**Rule for Axis-C:** the unit of cross-vendor handoff is a **typed change-spec** (goal re-anchored at top + a schema'd body: files, intent, constraints, acceptance test), never a transcript. This is exactly the workspace's own `orchestration-patterns` "Architect-to-Editor split" gem — an Opus architect emits a typed change-spec, Codex applies it via the codex rail. The literature confirms it is SOTA, not merely tidy.

---

## 3. Per-work-unit vendor diversity (role → vendor mapping)

Every serious harness that supports it converges on the same shape: **the work unit, not the session, carries the vendor.** Observed role→vendor conventions:

- **Amp:** Opus=smart implementation, GPT-5.5=deep/rush, **Gemini=review**. [4]
- **phalanx:** Codex=implementation (volume), Opus=review/judgment, Sonnet=orchestration. [18]
- **Goose multi-provider recipe:** GPT-4o-mini=cheap file ops, Claude Sonnet=complex analysis, local Ollama=privacy-sensitive. [5]
- **claude-octopus:** architecture/debate=Codex+Gemini (max training-bias diversity); review/security=3 providers. [17]
- **agent.ceo (multi-vendor org):** Claude Opus=highest-stakes reasoning/code, Sonnet=high-volume content, Gemini=multimodal/long-context, GPT=structured extraction/planning — plus a **fallback chain per agent** (Claude Opus→Sonnet→GPT-4o) that fired 11× in a month, ~3s reroute each. [25]

**Adoptable mechanics (native-engine-only):**
- Add an optional `{vendor, model}` to each `agent()` spawn. `vendor:"claude"` → native subagent; `vendor:"codex"` → the call body dispatches `mcp__codex__codex`. Default = Claude; Codex is opt-in per unit. (This *is* task-9 "codex-invoke" generalized into the engine — folded piece #1.)
- Keep a small, declared **role→vendor table** in the plan (not a learned router). Learned/RL routing (MMCP's `DomainScoredRouter`, per-domain benchmark scores) is interesting but is exactly the kind of new-infra the anti-overfit anchor forbids for now; a static table is enough and auditable. [26]
- **Budget pacing across two subscriptions** (Claude Max + ChatGPT): borrow eliza's `quota-aware` selection *idea* only — bias vendor choice by remaining weekly quota, advisory not enforced (matches the workspace's retired-AgentBridge posture). [24]

---

## 4. Execution-consensus across vendors (select by RUNNING, not by opinion)

This is the highest-leverage academic block for Axis-C, and it directly powers the reliability case.

**Why not an LLM judge?**
- **JudgeBench:** on 350 objectively-verifiable pairs (knowledge/reasoning/math/code), "many strong models (e.g., GPT-4o) perform just slightly better than random guessing." Best baseline (o1-preview) only 75.4%. A same-vendor judge also *inflates* accuracy for models sharing its errors (see §5). [11][7]
- **"Bias in the Loop" (SE judge audit):** repeated evaluations of the same case disagree; small prompt edits swing verdicts; semantics-preserving perturbations flip decisions. LLM-judge for code is "promising but fragile." [12]

**What works — execution as the oracle:**
- **CodeT (dual execution agreement).** Generate N solutions + M tests from the model(s); execute all N×M; form RANSAC-style *consensus sets* of solutions that pass the same tests; score a set by `|solutions|×|tests|`; pick from the top set. Pass@1 47.0%→65.8% on HumanEval (code-davinci-002). Core assumption: *incorrect solutions are diverse, so two wrong solutions rarely agree by chance* — which cross-vendor generation strengthens. [13]
- **MBR-Exec.** Select the candidate with minimum Bayes risk under an execution-equivalence loss (same outputs on test inputs = 0 loss). Beats all execution-free selectors even without ground-truth outputs. [27]
- **SemanticVote / "Semantic Voting" (2026).** Cluster candidates by *execution fingerprints* on generated inputs. Across 18 configs, the best execution-based selector beats output-pattern majority voting by **19–52 pp**; once you execute, the aggregation rule barely matters — **input quality dominates** (sketch-based inputs > direct > fuzzing). Frames selection as a *signal-quality* problem, not an aggregation-rule problem. [14]
- **SEP (Symbolic Equivalence Partitioning, 2026).** Use public examples as a validity filter, then symbolic execution to partition candidates into bounded equivalence classes; pick the dominant class. N=10: HumanEval+ 0.754→0.826, LiveCodeBench 0.565→0.647 — *no* test generation, learned verifier, or extra LLM call. Explicitly warns: "consensus alone is not sufficient — models can produce correlated wrong solutions." [28]
- **DOCE / ensemble-similarity selection (ICSE 2026).** Generate candidates from *different LLMs*, then vote via CodeBLEU + CrossHair differential-behavior (execution) equivalence: HumanEval 90.2% vs best single (GPT-4o) 83.5%; even free open models reach 80.5%. Trial-unit-test filtering + self-debug on multiple candidates = SOTA reranking. [29][30]

**Adoptable mechanics:** this is the workspace's existing `execution-grounded-bon` skill, and the literature validates it wholesale. For a work-unit with a cross-vendor Claude+Codex fan-out: (1) generate candidate patches from each vendor; (2) synthesize distinguishing inputs / use provided tests; (3) execute all candidates; (4) cluster by behavior; knock out crashers; (5) select where the *independent* Claude candidate and the *independent* Codex candidate agree on execution behavior — that cross-vendor agreement is the reliability signal. Selection is deterministic and external; no model votes.

---

## 5. The reliability case: independent failure modes (calibrated, not hyped)

This is the intellectual core, and it cuts both ways. State it honestly.

**The case FOR cross-vendor diversity (ensemble variance math):**
`Var(ensemble) = ρ·σ² + ((1−ρ)/M)·σ²`, and informally `Ensemble Error ≈ Avg Individual Error − Avg Diversity`. Disagreement (diversity) directly subtracts from error. Measured correlation ρ (security-anomaly setting): [10]
- same model, same prompt, 3 calls: **ρ ≈ 0.90–0.95** (pay 3×, gain ~0)
- same model, different prompts: ρ ≈ 0.6–0.8
- **different models, different prompts: ρ ≈ 0.4–0.7**
- different models + different prompts + **different evidence per agent: ρ ≈ 0.3–0.5** ← the real win.

**The case AGAINST over-claiming (correlated errors are stubborn) — ICML 2025 "Correlated Errors in LLMs", 350+ models, 20k+ questions:** [7][8]
- Models agree **~60%** (Helm) / mean 0.423 (HuggingFace) of the time *when both err* — vs ~33% / 0.127 random. 97.5–100% of model pairs exceed random-disagreement rates.
- **Same provider** raises correlation (+0.066 HF), **same architecture** more so (+0.076, the largest single factor).
- **Counter-intuitive & load-bearing:** conditioning on those, *more individually-accurate* model pairs still have *more* correlated errors (+0.023–0.043). "Larger and more accurate models have highly correlated errors, **even with distinct architectures and providers**… newer models that differ on the surface may be converging under the hood." Concrete: two unrelated models agreed on 0.9987 of the questions both got wrong.
- **Direct multi-agent implication:** a same-vendor (or even any-frontier) judge "systematically inflates the accuracy of models that share its errors" → the LLM-as-judge paradigm and same-model verify-steps are structurally biased.

**Failure-independence in code specifically (2607.02808, 12 models / 224 problems / 5 languages):** solutions show moderate *structural* diversity but "often fail on the same inputs — limited failure independence." Combining models reduces correlation but stays far from independent; N-version majority voting lifts reliability only **0.88→0.91** with 5 models (< half the independence-ideal gain), and **the gain depends much more on *model selection* than on language or prompt.** Many "different" failures trace to the *same underlying fault*. [9]

**Focal diversity (LLM-TOPLA, EMNLP 2024):** don't ensemble everything — a *focal-diversity* pruning metric finds sub-teams of **2–4 models that beat the full 8-model ensemble and the best single model.** Diversity must be *selected for*, not assumed. [21]

**The honest verdict for Axis-C (confidence bands, Sherman-Kent):**
- Cross-vendor diversity **reduces** correlated failure and is **worth doing** — *likely* (≈65–80%) to give a real but *modest* reliability lift on verifiable tasks. Evidence: ensemble math + CodeT/DOCE gains. **[Medium-High]**
- Cross-vendor diversity is **NOT** a correctness guarantee and the gap is **narrowing** as training converges — *almost certain* (≈90%). Evidence: ICML correlated-errors + failure-independence. **[High]**
- The **largest** reliability multipliers, in order: (1) an **external execution oracle** (§4) ≫ (2) **different evidence/context per agent** (ρ→0.3–0.5) > (3) **different vendor** alone > (4) different prompt alone ≫ (5) same-model resampling (~0). Design to the top of this list. **[High]**
- Practical corollary: **spend the diversity budget on the VERIFY step and on the SELECTION oracle**, not on redundant same-vendor generation.

---

## 6. Academic frameworks, taxonomies, and protocol vocabulary

- **LLM ensemble taxonomy (Chen et al. survey):** ensemble-*before*-inference (route/select model per input), ensemble-*during*-inference (token/step-level fusion), ensemble-*after*-inference (generate-then-select — where CodeT/MBR-Exec/DOCE live). Axis-C's cross-vendor work-unit is *before* (route) + *after* (execution-consensus select); *during* (token fusion) is out of scope and needs no new infra. [31]
- **"Team of Rivals" (arXiv 2601.14351):** multi-agent org intelligence; introduces "LLM Chemistry" (collaborative compatibility between specific models) and a two-stage collaborate→**consensus** step that "transforms diverse (sometimes conflicting) outputs into a unified decision." Reframes vendor mix as *deliberate* structured disagreement, not noise. [32]
- **MMCP (Multi-Model Collaboration Pipeline):** frames the gap as "MCP standardizes tool use for *one* model; MMCP standardizes context flow *between* models." Five protocol ops worth stealing as vocabulary: **Chain**, **Fork/Merge**, **Verify (Producer→Challenger→Judge)**, **Shard**, **Handoff** — each producing an inspectable "Context Envelope." Useful naming for Axis-C's pipeline stages; the *implementation* is just native `pipeline()`/`parallel()`, not MMCP's runtime. [26]
- **Adversarial debate pattern (Generator/Critic/Judge):** widely recommended to use *three different models* (diversity as pushback against LLM "yes-man" conformity). Matches the workspace council/design-review pattern. [33]
- **Orchestral (arXiv 2601.02577):** argues the whole value of a cross-vendor layer is a *unified, type-safe message/tool representation* + synchronous, debuggable, deterministic control flow — a caution *against* elaborate async runtimes. Reinforces the anti-overfit anchor. [34]
- **MAST / multi-agent failure modes (why MAS fail):** the dominant failures are architectural/coordination (vague objectives, step repetition, loss-of-history, unaware-stop, task derailment, hallucination propagation / conformity bias / monoculture), **not** base-model capability. Cross-vendor helps *only* the monoculture/conformity axis; the rest need the workspace's existing terminal-state markers, goal re-injection, and two-strikes pivot. [35][36]

---

## 7. Adoptable patterns for Axis-C (mapped to the five folded pieces)

Each pattern is expressed as "ride the native engine + codex rail," never new infra.

**P1 — Per-call vendor scoping (folds task-9 "codex-invoke" + Codex↔Claude mingling).**
Give every `agent()` an optional `{vendor, model}`. `claude`→native subagent; `codex`→the agent body calls `mcp__codex__codex` (start) / `codex-reply` (continue). A static, plan-declared **role→vendor table** (Architect=Opus, Editor/Implement=Codex, Review=cross-vendor) — no learned router. Evidence: Goose `subagent(settings)`, Amp per-task pick, phalanx. [4][5][18]

**P2 — Typed cross-vendor handoff (folds the ULTRACODE orchestration gems + AGENTS.md §5).**
The Architect emits a *typed change-spec* (goal re-anchored + files/intent/constraints/acceptance-test); the Editor/Implementer (often the other vendor) consumes only that spec. Never forward raw transcript. Evidence: Aider `ArchitectCoder` SOTA cross-vendor pairs. [1][2][3]

**P3 — Diversity-required VERIFY (the reliability keystone).**
Encode a `diversity_required` rule on the adversarial-review / VALIDATE phase: the reviewer vendor MUST differ from the generator vendor for high-stakes work units (security, architecture, spec). This is the single change with the best evidence-to-effort ratio. Evidence: ouroboros `consensus.diversity_required`, pair-programmer cross-vendor critical gates, the monoculture literature. [7][15][16][36]

**P4 — Execution-consensus selection, not LLM-judge (folds `execution-grounded-bon`).**
When a work-unit fans out to Claude+Codex candidates, select the winner by *executing* them on synthesized/provided tests and taking the cross-vendor behavioral-agreement cluster (CodeT/SemanticVote-style). LLM opinion never gates. Evidence: JudgeBench, CodeT, SemanticVote (+19–52pp), DOCE 90.2%. [11][13][14][29]

**P5 — Native-CLI peer, not raw API (already true via the codex rail).**
Keep Codex as a native thread (its own tools, sandboxed execution, executable evidence), not a chat completion. Evidence: relay/disputatio/phalanx "executable-evidence beats rhetoric." Axis-C already has this via `mcp__codex__codex` + agent-mail. [18][19][20]

**P6 — Uniform, native-vs-ours-distinguished monitor (folds wfmon).**
One monitor surface over both rails: native Claude subagents (agent-monitor-style, `~/.claude/projects/.../subagents/*.jsonl`) AND Codex threads (codex-monitor). Borrow OpenHands' **separate critic key** idea to attribute cross-vendor verify cost/latency distinctly. The monitor must *label* which rail each unit ran on so "native /workflows" vs "our cross-vendor" work is legible — a stated Axis-C requirement. [23]

**P7 — Small teams + escalation ladder.**
Default 2 vendors (Claude+Codex) per unit; add a 3rd (e.g., Gemini) ONLY for adversarial review of security/architecture, matching claude-octopus's smart-dispatch and LLM-TOPLA's 2–4 sweet spot. Avoid same-vendor 3× resampling (ρ≈0.9, no gain). [17][21]

**P8 — Per-agent fallback chain (resilience, advisory).**
Each role gets an ordered fallback (e.g., Claude Opus→Sonnet→Codex) so a provider outage degrades rather than halts — but keep it advisory/observable, not a hidden auto-swap that hides drift. Evidence: agent.ceo fallback chains (11 activations/month, ~3s reroute). [25]

---

## 8. Anti-patterns — what Axis-C should NOT build (anti-overfit guardrails)

1. **A universal provider gateway / second runtime.** Groklets/Unified-Agents-SDK/MMCP build one; Axis-C must NOT. Two rails (native `agent()` + `mcp__codex__codex`) is sufficient and matches the anchor. Orchestral's own thesis warns elaborate async runtimes hurt debuggability. [26][34]
2. **A learned/RL model router.** MMCP's per-domain RL router is tempting but is new stateful infra. A static, auditable role→vendor table wins for a single-user workspace. [26]
3. **LLM-as-judge as a merge/done gate.** Structurally biased (same-error inflation) and near-random on hard tasks. Use execution oracles; keep any LLM judge strictly *advisory/shadow* (mirrors the workspace `agent-as-judge` posture). [7][11]
4. **Assuming vendor labels = independent failures.** They don't; correlation is high for accurate models even across providers. Never market cross-vendor as a correctness guarantee; pair it with an external oracle and different-evidence design. [7][9]
5. **Max fan-out for its own sake.** 3× same-model = wasted spend; even 8-model ensembles lose to pruned 2–4 teams. Diversity must be *selected*, and verification is where to spend it. [10][21]
6. **A vector-DB/KG memory or durable-execution engine for orchestration state.** Not needed; native Workflow state + the existing event-ledger/basic-memory already cover continuity. (Explicit anchor item.)

---

## 9. Citations

1. Aider — *Separating code reasoning and editing* (Architect/Editor benchmark table). https://aider.chat/2024/09/26/architect.html
2. Aider — *Chat modes* (architect mode, editor model). https://aider.chat/docs/usage/modes.html
3. DeepWiki — *Aider Architect Mode* & *Multi-Provider LLM Integration* (ArchitectCoder, litellm three-tier). https://deepwiki.com/Aider-AI/aider/5.5-architect-mode ; https://deepwiki.com/Aider-AI/aider/7.3-multi-provider-llm-integration
4. Ry Walker — *AI Coding Assistants Compared* (Amp per-task model pick; ecosystem table). https://rywalker.com/research/ai-coding-assistants
5. Goose — *Providers* (subagent settings, multi-provider workflows, toolshim). https://block-goose.mintlify.app/concepts/providers
6. Goose issue #8203 — per-agent model assignment (delegate tool, agent files, GOOSE_SUBAGENT_MODEL). https://github.com/block/goose/issues/8203
7. *Correlated Errors in Large Language Models* (ICML 2025), arXiv 2506.07962 — agreement-when-both-err, provider/arch coefficients, judge inflation. https://arxiv.org/html/2506.07962v1 ; https://icml.cc/virtual/2025/poster/44225
8. (same paper) precise numbers: Helm ~60% / HF 0.423 agreement; same-provider +0.066; same-arch +0.076; accuracy interaction +0.023–0.043; 0.9987 pair example.
9. *A Systematic Methodology for Evaluating Failure Independence in LLM-Generated Code*, arXiv 2607.02808 — NVP 0.88→0.91, model-selection dominates, shared faults. https://arxiv.org/html/2607.02808v1
10. D. Shiebler — *Agents That Disagree* (ensemble error = avg error − diversity; ρ by config; different-evidence ρ 0.3–0.5). https://danshiebler.com/2026-03-22-ensemble-llm
11. *JudgeBench* (Tan et al. 2024), arXiv 2410.12784 — GPT-4o judge ≈ random on hard pairs; o1-preview 75.4%. https://huggingface.co/papers/2410.12784 ; https://www.emergentmind.com/topics/judgebench
12. *Bias in the Loop: Auditing LLM-as-a-Judge for Software Engineering*, arXiv 2604.16790 — judge fragility for code. https://arxiv.org/html/2604.16790v1
13. *CodeT: Code Generation with Generated Tests* (dual execution agreement / RANSAC consensus sets). https://github.com/microsoft/CodeT ; https://openreview.net/pdf/39c039dd3e5f58baafde9d304a11e04a606dda0b.pdf
14. *Semantic Voting: Execution-Grounded Consensus for LLM Code Generation* (2026), arXiv 2605.08680 — execution selectors beat majority voting by 19–52pp; input quality dominates. https://arxiv.org/html/2605.08680
15. ouroboros PR #1484 — multi-LLM stage-routing presets; `consensus.diversity_required`; Claude+Verify cross-vendor. https://github.com/q00/ouroboros/issues/1484
16. pair-programmer — tiered validation, cross-vendor judge for critical gates. https://github.com/lebobo88/pair-programmer
17. claude-octopus PR #166 — smart dispatch (2 vs 3 providers), blind-spot library, OctoBench ROI. https://github.com/nyldn/claude-octopus/issues/166
18. phalanx — vendor-agnostic multi-agent CLI on subscriptions (Codex impl / Opus review / Sonnet orchestrate). https://github.com/creynir/phalanx
19. Hermes-agent issue #413 / AgentWorkforce **relay** — orchestrate external agent CLIs via PTY (Claude backend, Codex tests, Gemini docs). https://github.com/NousResearch/hermes-agent/issues/413
20. disputatio — structured debate between real agent CLIs; executable-evidence grounding. https://github.com/marcomd/disputatio ; crewly https://github.com/stevehuang0115/crewly
21. *LLM-TOPLA: Efficient LLM Ensemble by Maximising Diversity* (EMNLP 2024) — focal diversity; pruned 2–4 sub-teams beat full ensemble & best single. https://aclanthology.org/2024.findings-emnlp.698.pdf
22. Goose PR #8652 — provider inventory & agent/model selection overhaul. https://github.com/aaif-goose/goose/pull/8652
23. OpenHands sub-agent delegation + critic surface (`enable_sub_agents`, TaskToolSet, `CRITIC_API_KEY`). https://frontier.bitter.sh/findings/2026-05-12-partial-cycle-openhands-2026-05-07_2026-05-12-frontier-v0/openhands/
24. RunLocalAI coding-agent ecosystem map (May 2026); eliza plugin-agent-orchestrator (KNOWN_ADAPTER_TYPES, quota-aware account pool). https://www.runlocalai.co/maps/coding-agents-2026 ; https://github.com/elizaos/eliza/issues/9146
25. agent.ceo — *Multi-Vendor AI Strategy* (role→model mapping, MCP abstraction, fallback chains). https://agent.ceo/blog/multi-vendor-ai-strategy-cyborgenic
26. mmcp — Multi-Model Collaboration Pipeline (5 protocol ops, Context Envelope, RL router, multi-verifier). https://github.com/ragavrida/mmcp
27. *Natural Language to Code Translation with Execution* — MBR-Exec (EMNLP 2022). https://aclanthology.org/2022.emnlp-main.231.pdf
28. *Inference-Time Code Selection via Symbolic Equivalence Partitioning (SEP)* (2026), arXiv 2604.06485. https://arxiv.org/html/2604.06485
29. *Enhancing LLM Code Generation with Ensembles: A Similarity-Based Selection Approach* (ICSE 2026), arXiv 2503.15838 — cross-model candidates, CodeBLEU + CrossHair vote, 90.2% HumanEval. https://conf.researchr.org/details/icse-2026/icse-2026-research-track/101/
30. *DOCE: Finding the Sweet Spot for Execution-Based Code Generation*, arXiv 2408.13745 — n-best rerank, trial-test filter, self-debug on multiple candidates. https://arxiv.org/html/2408.13745
31. Chen et al. — *Harnessing Multiple LLMs: A Survey on LLM Ensemble* (before/during/after-inference taxonomy), referenced via arXiv 2601.14351 §2.2.
32. *If You Want Coherence, Orchestrate a Team of Rivals* (2026), arXiv 2601.14351 — LLM Chemistry, collaborate→consensus. https://arxiv.org/html/2601.14351v1
33. A. Ewerlöf — *Multi-Agent System Reliability* (Generator/Critic/Judge with 3 different models). https://blog.alexewerlof.com/p/multi-agent-system-reliability
34. *Orchestral AI: A Framework for Agent Orchestration* (2026), arXiv 2601.02577 — unified type-safe cross-provider interface; deterministic control flow. https://arxiv.org/pdf/2601.02577
35. *LLM-Based Multi-Agent Orchestration: A Survey* (preprints 202604.2147) — vertical/horizontal, A2A+MCP, SWE-bench. https://www.preprints.org/manuscript/202604.2147
36. Redis — *Why Multi-Agent LLM Systems Fail* (monoculture problem, conformity bias, compounding errors); Orq.ai/MAST failure taxonomy. https://redis.io/blog/why-multi-agent-llm-systems-fail

---
*End of research slice. Design-only; no code, config, or commits were produced.*
