# Lens 08 - eval-harness + autoresearch for model endpoints

*Gem-hunt lens (discovery, not a build). Repo: Prekzursil/agent-skills-toolchain. Hunt: 2026-09-02 hosted-models.*
*Status: SKELETON - sections are filled and pushed incrementally; a section marked `[pending]` has not been researched yet.*

## 0. Scope, dedup-set and estate locks (constraints this lens designs under)

**Legend used throughout.** Each claim carries `[tier.corroboration.date]`: tier A = primary/official/peer-reviewed, B = reputable secondary (GitHub README, major docs mirror), C = blog/wiki/aggregator; `corrob` = 2+ independent sources agree, `single` = one source, `UNVERIFIED` = recalled or not fetched this run. `FACT` = sourced; `INFER` = my inference from sourced facts; `REC` = recommendation. Today = 2026-09-02.

**What this lens is.** A design for (a) an eval suite that grades *any endpoint registered in the estate* on seven axes and (b) an autoresearch loop that tunes the *routing policy* (which endpoint serves which task class) to maximize a routing score under a spend cap. Discovery only; nothing here is built.

**Dedup - what already exists and is NOT re-proposed (verified on disk this run):**

- `skills/hosted-model-agents/evals.md` on `origin/live-capture/2026-09-02` is a **skill-pressure eval** (5 pressures, "would the agent repeat the 29.08.2026 miss") plus disk checks - it grades agent *behaviour under a prompt*, not an endpoint's tool-call/JSON/latency/cost. `[A.single.2026-09 - read from git]` This lens grades *endpoints*; the two compose (the pressure evals become one task class in Section 2). `INFER`
- `tools/mcp/glm53-space` (one tool `glm53_chat`, mini OpenAI proxy, hardcoded `router.huggingface.co/v1` + `zai-org/GLM-5.3`) - owner has decided to deprecate it in favour of a general integration layer. It is **not on `origin/main`** today (`ls tools/mcp/glm53-space` is empty), but `glm53-space` is still a key in `.agents/agents.json` `mcp.servers` (42 servers). `[A.single.2026-09 - read from disk]` The eval suite below is exactly the acceptance test any replacement integration layer must pass. `INFER`
- `platform/routing/MEASUREMENTS.json` + `hooks/semantic-router/{eval.py,test_eval.py,route.py,success.py,observe.py}` already implement a **retrieval-quality eval** (precision@k / recall@k / gold-hit-rate over a 60-query L1-L4 set, 912-item index) for the *skill/command* router. `[A.single.2026-09 - read from disk]` That is routing of *prompts to skills*; this lens is routing of *tasks to model endpoints*. Its eval shape (gold set, tiers, `failures[]` with qid+query, floor_violations) is the house style to copy, not a duplicate. `INFER`
- `.agents/skills/autoresearch/SKILL.md` already defines the loop contract (commit-before-measure, log-before-revert, revert on any regression, 3-discards-in-a-row review, ~8-variant plateau rule, `.autoresearch/log.tsv` with `variant sha status <axes...> hypothesis`, `.autoresearch/` git-ignored). `[A.single.2026-09 - read from disk]` Section 4 *instantiates* that contract for a routing-policy file; it does not fork the skill.
- `.agents/skills/eval-harness/SKILL.md` defines grader types (code / rule / model / human), pass@k vs pass^k, thresholds (capability pass@3 >= 0.90, regression pass^3 = 1.00), anti-patterns (flaky graders in release gates, ignoring cost/latency drift). `[A.single.2026-09 - read from disk]` Section 2 reuses that vocabulary verbatim.
- `.agents/skills/openrouter-routing/SKILL.md` already has the T0/T1 tiering, "escalate one-way, never mid-tool-call fallback up the tier", and the hard daily+monthly spend-cap checklist. `[A.single.2026-09 - read from disk]`

**Estate locks this lens designs under (hard; cited as constraints from the task brief, not re-litigated):**

1. OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP. => The eval runner may *call* OpenRouter endpoints as one registered endpoint class under the existing cap; it may not become a router in front of Cursor or Claude.
2. No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory. => The eval runner and the autoresearch loop are **plain Python + git + TSV**; no eval SaaS, no proxy layer, no new daemon. (This rules out adopting promptfoo/inspect/DeepEval *as a runtime*; borrowing their *grader ideas* is fine - Section 5.)
3. `auth2api :8317` stays the ONLY Cursor bridge and retires within 7 days of an official Cursor `/v1` GA. => Cursor-quota endpoints (`cursor-*` model ids) are graded through `:8317` like any other OpenAI-compatible endpoint, and the registry entry must carry a `sunset_on: cursor_v1_ga` flag so the loop never "optimizes into" a soon-dead bridge.
4. Ports 8765/8812/8317 are owned. => The runner opens no port; fakes in CI are in-process, not a mock server on a port.
5. `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it). => Grader prompts (model-graded axes) live under a skill folder, not in a Python string.
6. Never rotate credentials; secrets by name only in `.agents/local.json`. => The runner reads secret *names* from the registry and resolves them from env; live runs are opt-in.
7. Never remove a feature to buy reliability - present tradeoffs. => Every routing-policy change the loop proposes is a *tradeoff row* (quality vs cost vs latency), never a "drop endpoint X".
8. Box constraints: Windows 11, 31.6 GB RAM, chronically memory-starved, no GPU assumed. => Local endpoints (ollama, LM Studio `lms`, llama.cpp) are graded on the *same* suite but with a `local` tag; the runner is single-process and streams results to disk so a 12-minute death loses at most one task.

## 1. Prior art - what the field already measures and how (cited)

| Prior art | What it measures / how | What this lens borrows | Grade |
|---|---|---|---|
| **BFCL v4** (Berkeley Function Calling Leaderboard, Gorilla) | Categories *simple / multiple / parallel / parallel-multiple / irrelevance* (+ live variants, multi-turn, format-sensitivity). AST accuracy = parsed call matches gold (function name, every predicted param is real, every gold param value in its acceptable list; `""` in the list marks optional). Parallel = order-independent 1:1 match of all calls. Irrelevance = model must NOT call; relevance = must call. ~2k question-function-answer pairs across Python/Java/JS/REST. | The whole **tool-call fidelity** axis (Section 2.1): AST-style code grader, parallel 1:1 matching, irrelevance-as-refusal. | FACT `[A.corrob.2026]` gorilla.cs.berkeley.edu [S1]; HF dataset overview [S2]; open-source AST-scorer port showing the exact matching rule [S3]; secondary summary [S4] |
| **tau-bench / tau2-bench** (Sierra) | Agent+tools+simulated user; grade by *final database state* vs gold, not by transcript. Introduces **pass^k** = P(all k i.i.d. trials succeed), averaged over tasks; unbiased estimator `E_task[C(c,k)/C(n,k)]`; pass^1 = pass@1 = E[c/n]. GPT-4o < 50% tasks, pass^8 < 25% retail (2024). tau2-bench (2025-06) adds dual-control; leaderboard recommends n >= 4 trials. | **pass^k as the reliability target** for every axis that gates a tier; state-based grading for the tool-loop task class. | FACT `[A.corrob.2024-2025]` arXiv 2406.12045 [S5]; ICLR 2025 paper [S6]; tau2-bench summary [S7-C]; 2026-07 replication with n=8 [S8-C] |
| **HELM** (Stanford CRFM) | Multi-metric by design: 7 metrics (accuracy, calibration, robustness, fairness, bias, toxicity, **efficiency**) x scenarios; all prompts/completions released; living leaderboards (Capabilities, Safety). Open framework with unified model adapters. | The **"never a single number" discipline**: report the vector, derive the scalar (routing score) *from* it, never the reverse. Also: efficiency (latency/cost) is a first-class metric, not an afterthought. | FACT `[A.corrob.2022-2026]` github stanford-crfm/helm [S9]; HELM paper [S10 - 2022, dated]. SEA-HELM (2026-08) adds 8-run averaging + bootstrap CIs + Bradley-Terry Elo [S11-B] |
| **LMArena** (ex-Chatbot Arena) | Crowd pairwise votes -> Bradley-Terry ratings with style control (length/markdown confounders). | Only as a **prior for the initial policy**, never as a grader: arena preference != tool-call fidelity. Pairwise BT is the right aggregator *if* we ever do model-graded pairwise preference between two endpoints on the same task. | INFER on top of `[B.single.2026 - UNVERIFIED this run]` (methodology not fetched; see Section 7) |
| **Artificial Analysis** | API-provider leaderboard over 500+ endpoints: TTFT ("first chunk"; for reasoning models = first reasoning token), output tokens/s (last 80% of chunks for hidden-reasoning models), end-to-end time; **median (P50) over rolling 72h**, default workload **10k input tokens** since 2026-03-02; measured from GCP us-central1-a incl. network. | Definitions for the **latency axis** (TTFT, output speed, E2E) and the honesty that a 1-box home measurement is *our* p50/p95 from *our* network, not theirs. | FACT `[A.single.2026-03]` methodology page [S12]; leaderboard columns [S13]; 2026-08-30 snapshot table [S14-C] |
| **OpenAI Structured Outputs / JSON mode** | `strict: true` + `json_schema` => constrained decoding, 100% schema adherence on the *supported subset*; JSON mode only guarantees valid JSON, not schema. Response carries a separate **`refusal`** field when the model refuses inside a structured call. | The **JSON axis** grades three things separately: valid-JSON rate, schema-valid rate, and *silent fallback* (schema accepted but unsupported => unguided). And: refusal must be detected as a field, not as text. | FACT `[A.corrob.2024-2026]` OpenAI announcement [S15]; current guide [S16]; JSONSchemaBench summaries: OpenAI 100% compliance but low empirical coverage on developer schemas (~29%), Guidance ~96% coverage [S17-C][S18-C] |
| **LLMRouterBench** (ACL Findings 2026 / arXiv 2601.07206) | 33 models x 21 datasets, 1.8B tokens; metrics **PerfGain** (best accuracy over Best-Single), **CostSave** (max cost cut at >= Best-Single accuracy), Pareto frontier + **ParetoDist**. Finding: top routers reach ~+4% PerfGain / ~31.7% CostSave, but several routers **including OpenRouter `openrouter/auto` (-24.7% vs Best-Single)** fail to beat the best single model. | The **routing score** definition and the *null hypothesis the autoresearch loop must beat*: "route everything to the best single endpoint". Any policy that cannot beat Best-Single on our own task set is a discard. | FACT `[A.corrob.2026-01]` arXiv HTML [S19]; ACL PDF [S20]; repo [S21-B] |
| **OpenRouter rankings** | Ranked by aggregate token usage; the brief's DEDUP rules make OpenRouter a sidecar only. Rankings = popularity, not quality. | Popularity is a **weak prior** for candidate ordering in cold-start only; it never enters the score. | INFER; rankings methodology `[C.single - UNVERIFIED this run]` |
| **Karpathy `autoresearch`** (2026-03) | One editable file (`train.py`), one metric (`val_bpb`), fixed 5-min budget, loop: edit -> `git commit` -> run -> read metric -> keep (advance branch) or `git reset --hard HEAD~1`; `results.tsv` untracked, columns `commit val_bpb memory_gb status{keep,discard,crash} description`; soft constraint on peak VRAM; simplicity tiebreak (0.001 gain with 20 hacky lines = discard; equal with simpler code = keep); 10-min kill timeout. | Confirms the house `autoresearch` skill's contract is the field's contract; adds three things we adopt: **fixed measurement budget per variant**, **soft-constraint axis** (here: spend), **simplicity tiebreak** written into the policy diff review. | FACT `[A.corrob.2026-03]` program.md at pinned commit [S22]; repo README [S23]; secondary walk-throughs [S24-C][S25-C] |
| **`pass@k` estimator** (Chen et al. 2021, Codex) | Unbiased `1 - C(n-c,k)/C(n,k)` with n > k samples. | Used for the *capability* thresholds; tau-bench's pass^k for *reliability* thresholds. | FACT `[A.single.2021 - dated, canonical]` cited via tau-bench [S5] |

**Gap the prior art leaves for THIS estate (INFER):** every public harness grades *models*; none grades *our registry entries* - an endpoint = (provider, model id, base URL, auth name, bridge such as `:8317`, quota class, sunset flag). Two entries can share a model and differ in every operational axis (Cursor-bridged Claude vs direct Claude; HF Space vs HF Endpoint for the same weights). The unit of evaluation here is therefore the **registry entry**, and the routing policy is a map `task_class -> ordered endpoint list`, which is exactly the object the autoresearch loop edits.

## 2. The endpoint eval suite - seven axes, graders, pass@k / pass^k targets

[pending]

## 3. The routing score - one number per endpoint per task class

[pending]

## 4. The autoresearch loop over the registry routing policy

[pending]

## 5. CI with fakes vs live keys - what runs where

[pending]

## 6. Per-find rubric table

[pending]

## 7. Sources

[pending]

## 8. Ten-line summary

[pending]
