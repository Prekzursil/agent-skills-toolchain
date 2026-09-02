# Gem-hunt 2026-09-02 / hosted models / lens 10: cross-domain borrows + wildcard

Lens id: `10-cross-domain-borrows-wildcard`
Branch: `gemhunt/hosted-models-10-cross-domain-borrows-wildcard` (from `main` @ `5fa34fda1`)
Mode: discovery only. No code changed. No PR.

Status legend used below:

- **[FACT]** sourced claim, cited with URL + tier + date checked.
- **[INFER]** my inference from sourced facts; can be wrong.
- **[REC]** recommendation for this estate.
- Tier A = primary/official docs, standards bodies, regulators, peer-reviewed. Tier B = reputable secondary
  (vendor engineering blogs, well-maintained OSS READMEs, trade press). Tier C = forum / single blog / model-training
  memory. **UNVERIFIED** = I could not fetch a live source in this run.

## 0. Constraints honoured (estate locks, cited as constraints)

- OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never `ANTHROPIC_BASE_URL`, never a new
  OpenRouter MCP.
- No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `auth2api :8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA.
- Ports 8765 / 8812 / 8317 are owned.
- `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- Never rotate credentials. Never remove a feature to buy reliability; present tradeoffs instead.

Dedup-set (exists, not re-proposed): `hosted-model-agents` skill (live-capture/2026-09-02), `tools/mcp/glm53-space`
(to be deprecated), `auth2api :8317`, `.agents/agents.json` + `.agents/local.json`, installed runtimes on the Win11 box.

## Estate surfaces the finds must ride (grounding, read this run)

- Prompt SSOT: `.agents/skills/<skill>/SKILL.md` (Fabric/Goose consume it). Any "policy" below is a skill or a data
  file next to one, not a daemon.
- Registry: `.agents/agents.json` `mcp.servers` (42 entries, each with `targets`, e.g. `huggingface` ->
  `https://huggingface.co/mcp?login` targets `claude`; `glm53-space` -> `uv run ... mcp_server.py` targets `claude`;
  `basic-memory` `:8765`, `agent-mail` `:8812` carry `processMatch`). Secrets by name in `.agents/local.json`.
- Health/quarantine state already exists: `.agents/scripts/mcp_fleet_supervisor.py` writes
  `state/mcp-supervisor.json` and `reports/mcp-fleet-status.json` and keeps a **session quarantine**. Every
  "circuit breaker"-like find below should extend that state file, not add a new one.
- Sidecar: `.agents/scripts/openrouter-complete.py` is the T0 OpenRouter completion (prints generation id + usage,
  never logs the secret). CLI/Codex only, per lock.
- Wrappers in `~/.local/bin` (`ai-mode`, `fabric-cursor`, `claude-cursor`, `codex-cursor`, `grok-mode`) are the
  process-local edge where an endpoint is chosen today. A routing table is *data they read*, not a new process.
- Hooks: Claude/Cursor hook scripts under `.agents/scripts/cursor-hooks/` (`shell-guard.ps1`, `cursor-hook-log.ps1`,
  `bm-session-liveness.ps1`) prove the estate already runs pre/post hooks; a "dispatch release" check is one more
  hook body, not a framework.
- Dedup item (1), `hosted-model-agents` (live-capture/2026-09-02), already fixes the three layers (control plane =
  HF Hub MCP; runtime = `/v1`/Gradio/TGI/llama-server/Cursor Max; harness = local executor) and its hard rule 2
  ("an inference URL is not Hub MCP; do not register every GPU URL as MCP"). Everything below is about **which
  runtime to pick and when to switch**, which that skill does not cover. `[FACT]` (read from branch this run).

## 1. Telecom: least-cost routing + quality-based re-ordering + route advance

### Mechanism (sourced)

- **LCR with a prefix routing table.** Carriers keep a "rate deck" (price per destination prefix) and a routing
  table that lists, per prefix, an ordered set of gateways/carriers. OpenSIPS `drouting` is the reference OSS
  implementation; `qrouting` sits on top of it and **re-orders destinations live** from five signalling KPIs:
  **ASR** (answer-seizure ratio), **CCR** (call completion ratio), **PDD** (post-dial delay: INVITE -> first
  180/183), **AST** (average setup time: INVITE -> 200 OK), **ACD** (average call duration). Each KPI has a
  `warn` and a `crit` threshold and a penalty; per-destination scores are recomputed over a `history_span`
  window, and a destination is not judged until `min_samples_*` observations exist. `[FACT]` Tier A (vendor
  docs, corroborated by two OpenSIPS pages), checked 2026-09-02:
  <https://docs.opensips.org/manual/devel/modules/qrouting/> and
  <https://opensips.org/docs/modules/3.2.x/qrouting.html>.
- **Two re-ordering algorithms, deliberately different tradeoffs.** `best-dest-first`: all traffic to the
  top-scored destination, provision the list in expected-quality order because it is blind until samples exist.
  `dynamic-weights`: ratings become weights in a weighted-random balance (ratings 1 and 0.5 -> ~67%/33%), which
  OpenSIPS calls "the superior choice" because it **keeps sampling the poor performers at a low rate**, so recovery
  is detected without a manual reset. `[FACT]` Tier B (vendor blog, 2020, corroborated by the module docs above):
  <https://blog.opensips.org/2020/03/17/quality-based-pstn-routing-in-opensips-3-1-lts-part-2/>.
- **Route advance / carrier failover on SIP `503 Service Unavailable`** with an optional `Retry-After` header;
  a proxy receiving 503 should try alternate destinations rather than surfacing the failure. `[FACT]` Tier A,
  RFC 3261 s21.5.4 (2002, stable): <https://www.rfc-editor.org/rfc/rfc3261#section-21.5.4>. Not re-fetched this
  run (standard text, high confidence).

### Exact analogue for choosing a model endpoint

| Telecom | Model routing in this estate |
|---|---|
| Prefix (destination class) | **Task class**: `edit-code`, `agentic-tools`, `long-context-read`, `cheap-classify`, `vision`, `red-team-report` |
| Gateway / carrier | Endpoint: `cursor-*` via `auth2api :8317` (Cursor quota), OpenRouter model id (**CLI/Codex only**), HF Space or Endpoint `/v1`, local `ollama` / `lms` / llama-server |
| Rate deck | Price per 1M tokens (OpenRouter `/models` exposes it; HF Endpoint per-hour; Cursor = quota units) |
| ASR | Completion success ratio: HTTP 200 with non-empty `choices[0]` |
| CCR | **Tool-call well-formedness ratio**: `tool_calls` parse + schema-validate (the estate's harness rule 3 already validates them locally) |
| PDD | Time-to-first-token |
| AST | Time-to-first-`tool_call` (agentic) or time-to-final (non-streaming) |
| ACD | Output tokens per completion; a sudden ACD drop = truncation / silent context cut |
| `503` + `Retry-After` | HTTP 429/503/529 from the provider; `Retry-After` honoured; **route-advance to the next destination for the same prefix** |
| `min_samples` | Do not demote an endpoint on one failure; demote after N |
| `history_span` | Sliding window so a bad hour does not blacklist a provider for a week |

`[INFER]` The two KPIs the software lenses usually skip are **CCR** (format validity, not just HTTP success) and
**ACD** (output-length collapse as a silent-degradation signal). Both are free to compute from responses the wrappers
already have in hand.

### How it rides the existing bus (no new runtime)

- `routes.json` (per task class: ordered destinations, thresholds, penalties, `min_samples`, `history_span`) lives in
  `.agents/` next to `agents.json` so it is under the same SSOT/sync (`sync_shared_state.ps1`). The wrappers in
  `~/.local/bin` and the wrapper that replaces `tools/mcp/glm53-space/openai_proxy.py` **read** it. `[REC]`
- Stats are appended to `.agents/state/` in the same shape `mcp_fleet_supervisor.py` already uses for session
  quarantine; the supervisor's existing `--report` becomes the place a demoted endpoint shows up. `[REC]`
- Route-advance on 429/503/529 is a loop in the wrapper (the `openrouter-complete.py` request function already
  returns `(status, body)` and could try the next destination). No LiteLLM: the table is ~50 lines of JSON and the
  loop is ~30 lines. `[REC]`
- Lock compliance: OpenRouter destinations may only appear in CLI/Codex-side task classes; `cursor-*` destinations
  only via `:8317`. The table makes the lock **inspectable** (a validator like `validate_mcp_control_plane.py` can
  fail closed if an OpenRouter id appears in a Cursor-targeted class). `[REC]`

### Tradeoff (never remove a feature to buy reliability)

`dynamic-weights` buys recovery detection by spending a few percent of traffic on the worse endpoint (cost of
information). `best-dest-first` is cheaper and deterministic but needs a manual "un-quarantine". Offer both as a
per-class flag; default `best-dest-first` for quota-metered Cursor classes (every sample costs quota), `dynamic-weights`
for local/HF classes where samples are cheap. `[REC]`

## 2. Finance: smart order routing + best execution + "regular and rigorous review"

### Mechanism (sourced)

- **FINRA Rule 5310 (Best Execution and Interpositioning).** A member must "use reasonable diligence to ascertain
  the best market" so the resulting price is "as favorable as possible under prevailing market conditions". A firm
  that routes on an automated, non-discretionary basis must run **"regular and rigorous reviews"** of execution
  quality, **at least quarterly**, on a **security-by-security, type-of-order basis**, and must either **modify its
  routing arrangements or justify why it is not modifying them**. Review factors: price improvement, likelihood of
  execution, speed, size, transaction costs, customer needs. A member **cannot transfer its best-execution
  obligation to another person**. `[FACT]` Tier A, checked 2026-09-02:
  <https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310>. Corroborated by Regulatory Notice 15-46
  (<https://www.finra.org/rules-guidance/notices/15-46>) and the 2026 FINRA oversight report, which adds that the
  review should consider "competing markets to which a firm does not send order flow":
  <https://www.finra.org/rules-guidance/guidance/reports/2026-finra-annual-regulatory-oversight-report/best-execution>.
- **"Interpositioning"**: 5310 forbids inserting a third party between the member and the best market when doing so
  worsens the customer's outcome. `[FACT]` Tier A, same rule page.
- **MiFID II Article 27** (EU): "all sufficient steps" for the best possible result, weighing **price, costs, speed,
  likelihood of execution and settlement, size, nature of the order**; a **written execution policy** per instrument
  class, reviewed **at least annually** and on material change. `[FACT]` Tier B (industry regulatory guide,
  checked 2026-09-02):
  <https://www.quodfinancial.com/best-execution-in-institutional-trading-regulatory-requirements-and-the-role-of-technology/>.
  Primary text: Directive 2014/65/EU Art. 27, <https://eur-lex.europa.eu/eli/dir/2014/65/oj> (Tier A, not
  re-fetched this run). The former RTS 28 "top five venues" report was being wound down in the 2024 MiFID review;
  treat the *disclosure* piece as **UNVERIFIED** this run.
- **Smart order routers** are the automation of the duty: a SOR "assess[es] trading venues for the best priced
  quotation and liquidity prior to routing" and is a permissible algorithm precisely because it serves best
  execution. `[FACT]` Tier A (SEC release 34-99488, Feb 2024):
  <https://public-inspection.federalregister.gov/2024-02858.pdf>.

### Exact analogue for choosing a model endpoint

| Finance | Model routing in this estate |
|---|---|
| Security x order type | Task class x invocation shape (interactive vs background, streaming vs batch) |
| Price improvement | Quality above the class baseline at equal or lower cost (from the estate's own evals) |
| Likelihood of execution | Non-refusal, non-timeout, non-truncation ratio |
| Speed | TTFT + total latency |
| Size | Max context / max output the endpoint reliably handles |
| Transaction costs | `$` per 1M tokens **plus Cursor quota units** (quota is a cost, not free) |
| Customer needs | Explicit owner pins ("this class must stay on Claude"), security scope (no third-party exploit playbooks on a Space, per `profiles.md`) |
| Regular and rigorous review | A **scheduled review skill** that compares current routes against alternatives, **including endpoints not currently used**, and writes "changed" or "kept, because ..." |
| Cannot transfer the duty | Using OpenRouter's own provider routing or Cursor's model choice does **not** discharge the estate's review; log the *actual* provider/model used (OpenRouter returns `provider` in the response body) |
| Interpositioning | Do not add a hop (second bridge, LiteLLM, extra proxy) that adds cost/latency without benefit. This is the finance-language justification of the `auth2api`-only and no-LiteLLM locks |

`[INFER]` Best execution is a *multi-factor* duty; a cheapest-token router would fail a 5310 review. That is the
argument, in a regulator's words, against pure LCR.

### How it rides the existing bus

- `review-routing` is a **skill** (prompt in `.agents/skills/`) any runtime can run monthly; input = the stats file
  from s1; output = `.agents/reports/routing-review-<date>.md` with a "modified / justified-not-modified" line per
  task class (the 5310 wording). `[REC]`
- "Competing markets you do not send flow to" = a tiny **shadow-eval** line item: once a month, run the estate's
  existing eval set (dedup item (1) `evals.md` already exists) against one non-routed endpoint. Cost bounded by the
  OpenRouter spend cap for CLI classes and by zero for local models. `[REC]`
- The routing table from s1 gains one column: `justification` (free text, dated). That is the "written execution
  policy". `[REC]`

### Tradeoff

Quarterly is FINRA's floor and many firms review monthly (Notice 15-46). For this estate the cost of a review is one
eval run per class; the cost of *not* reviewing is that `cursor-*` quota keeps going to a model that a cheaper local
one now matches. Keep the cadence a parameter. `[REC]`

## 3. Pharmacy: formulary + therapeutic substitution

_(pending)_

## 4. Aviation: dispatch reliability + MEL/ETOPS

_(pending)_

## 5. Power grid: unit commitment + reserves

_(pending)_

## 6. Wildcard: the find the other lenses would miss

_(pending)_

## 7. Rubric table

_(pending)_

## 8. Ten-line summary

_(pending)_
