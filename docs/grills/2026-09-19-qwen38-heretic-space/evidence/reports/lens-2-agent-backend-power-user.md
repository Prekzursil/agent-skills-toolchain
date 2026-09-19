<!-- verbatim final report of background subagent a60da60a4c2abaf0c, saved 2026-09-19 -->

## Directions
Path key: `S` = /tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad; `sp/` = S/libsrc/spaces/spaces, `gr/` = S/libsrc/gradio/gradio, `tf/` = S/libsrc/transformers/transformers; bare filenames = S/space-latest/. Nothing was run against the Space.

### 1. Lease end becomes a checkpoint (deadline, stateless resume, client-held jobs)
- What: Pass `max_time` so generation stops itself before the lease expires. Return `finish_reason:"length"` plus a continuation that resumes via `continue_final_message`. A small local OpenAI-compatible sidecar serves all three harnesses. It holds the job journal, routes only an explicit model alias here, sets `max_retries=0`, and drains a batch file overnight.
- Why it matters for this owner: Expiry surfaces only as "GPU task aborted", and a killed worker is never reused. A cleanly ended worker can be reused (`sp/zero/wrappers.py:357-368`). Partial text already streams into the main process (`:442-465`). The container has no storage and restarts often (A4).
- Feasibility and constraints:
  - Verified: `max_time` exists (`tf/generation/stopping_criteria.py:93-115`).
  - Verified: resume works even inside `reasoning_content` (`tf/utils/chat_template_utils.py:544-605`). It rejects `add_generation_prompt` and rstrips the seam.
  - The identity JWT can expire (`sp/zero/client.py:261-262`), so each chained lease needs a fresh request.
  - Unverified: per-lease setup cost is unmeasured.
- Effort: S for deadline and resume, M for sidecar or queue.
- Decision it forces: where do job state and orchestration live?
  - (a) client sidecar with a stateless Space;
  - (b) the same plus an in-memory server `submit`/`poll` queue;
  - (c) a Hub-backed server store.
  - Recommend (a), then (b). Trade-off: full context is resent per lease, mid-think seams may cost quality, and there is one more local process.

### 2. Make `/v1` spend the right quota bucket
- What: Forward the caller's `X-IP-Token` into lease scheduling on the OpenAI route. Log token present yes/no per lease.
- Why it matters for this owner:
  - `spaces` reads identity from `LocalContext.request` (`sp/utils.py:52-57`, `sp/zero/wrappers.py:321`).
  - Gradio sets that variable only inside its event handlers (`gr/utils.py:1136`).
  - The custom route never sets it, so leases carry `token=None` (`sp/zero/client.py:306-324`).
  - Gradio docs say such requests are "treated as unauthenticated" (gradio.app/docs/python-client/using-zero-gpu-spaces). That tier gets 2 minutes a day versus 40 for PRO (huggingface.co/docs/hub/spaces-zerogpu).
  - The MCP path does forward headers (`gr/mcp.py:652-656,802-806`).
- Feasibility and constraints: the client side is verified. Which server-side bucket a private PRO Space draws on is unverified.
- Effort: S.
- Decision it forces:
  - (a) set the context variable around the generator;
  - (b) route `/v1` through a `gr.api` endpoint by loopback, as MCP does;
  - (c) measure first.
  - Recommend (c), then (a) with a test. Trade-off: (a) depends on a private attribute that the weekly dependency bump can break.

### 3. Budget contract and a truthful `/status`
- What:
  - CPU-only `/v1/preflight` returning tokens, lease and reservation seconds, and share of the day.
  - A per-request `budget_seconds`.
  - A rolling 24 h ledger with a hard cap.
  - `/status` reporting ready, busy, queue size, last lease outcome and measured tok/s.
- Why it matters for this owner:
  - Past quota, usage is "automatically billed" at $1 per 10 minutes (HF docs). That is about $185 per million output tokens at the claimed 9 tok/s.
  - A dedicated 48 GB L40S Space costs $1.80/h (huggingface.co/pricing).
  - The OpenAI SDK retries twice and times out at 10 minutes by default (github.com/openai/openai-python README). One request can therefore reserve three leases.
  - Blackwell `large` reserves 1.5x the requested seconds (`sp/zero/configs.json`, `sp/zero/client.py:105-114`). Runtime detection of that config is unverified.
- Feasibility and constraints:
  - No quota-read call exists (`sp/zero/api.py:85-170`). Ground truth arrives only in a 429 (`:51-53`), so the ledger is an estimate.
  - Non-streaming `/v1` generates inside an `async def` (`openai_api.py:37`, `openai_protocol.py:671`), stalling `/healthz` for minutes. Fix that first.
  - A canary generation costs a lease setup. Make it passive plus on-demand only.
- Effort: M.
- Decision it forces: what happens to a request that will not fit?
  - (a) 429 with `retry_after`;
  - (b) clamp and return a resumable partial;
  - (c) spill into credits.
  - Recommend (a), with (b) opt-in, and never (c) by default. Trade-off: an estimated ledger sometimes refuses wrongly.

### 4. Agent-shaped MCP surface
- What: Typed `ask`, `poll(job_id, wait_s<=45)`, `status` and `preflight`. Make `chat` and the UI listeners non-public.
- Why it matters for this owner:
  - Every named API endpoint becomes a tool (`gr/mcp.py:554-577`).
  - `chat` defaults to web tools on and up to 8 lease rounds (`app.py:80,984-986`).
  - `chat` exposes `python_eval` as a caller-settable flag. Its subprocess inherits the Space environment (`web_tools.py:440-445`; secrets per A7).
  - Codex's tool timeout defaults to 60 s (developers.openai.com/codex/mcp). That is a few hundred tokens.
- Feasibility and constraints: `gr.api` (`gr/events.py:1067-1080`), `api_visibility` (`gr/chat_interface.py:104`) and `?tools=` (`gr/mcp.py:521-535`) are verified. Harness progress-token support is unverified.
- Effort: S-M.
- Decision it forces: may MCP callers reach the in-Space agent loop?
  - (a) no, model only;
  - (b) a separate opt-in tool without `python_eval`;
  - (c) keep as is.
  - Recommend (a), which matches the design doc's non-goals. Trade-off: agents lose one-call web research.

### 5. Output reliability with an eval set behind it
- What:
  - Schema-aware argument coercion.
  - JSON Schema validation for tool arguments and `response_format`.
  - CPU-side repair before any re-lease.
  - Notes moved out of `content`.
  - `length` as the finish reason on an unterminated `<tool_call>`.
  - `reasoning_content` returned and accepted.
  - All of it pinned by an offline corpus of recorded outputs.
- Why it matters for this owner:
  - A 500-token retry costs about 3% of the day at the claimed rate.
  - Reproduced locally on `tool_parse.py`:
    - A string parameter holding JSON becomes a dict.
    - Enum violations and unknown arguments pass validation.
    - A truncated call leaks markup into `content`.
    - A literal `</parameter>` truncates the value.
  - JSON-mode failure appends prose to `content` (`openai_protocol.py:435-458`).
  - `/v1` never forwards or returns `reasoning_content` (`:202-205,467-474`).
- Feasibility and constraints: this is pure Python and offline-testable. Constrained-decoding hooks exist (`tf/generation/utils.py:1128,1239`). Grammar-library fit is unverified.
- Effort: M.
- Decision it forces: what happens to invalid tool arguments?
  - (a) drop silently (today);
  - (b) forward flagged;
  - (c) repair or refuse with a structured error;
  - (d) constrained decoding.
  - Recommend (c). Trade-off: it rejects calls that lenient harnesses would accept.

## Killed ideas
- Shipping KV cache across leases: it is 64 KiB per token plus recurrent state (hf://models/heretic-org/Qwen3.8-27B-heretic-ara/config.json), and the kill is unannounced, so re-prefill wins.
- Autonomous server-side overnight drainer: identity tokens expire and the in-memory queue dies on restart, so drive it from the client.
- Hub-backed job store: it puts another write-scoped secret beside model-authored code.
- Counting on speculative decoding: `_is_stateful = True` (`tf/models/qwen3_5/modeling_qwen3_5.py:812`) makes `generate` raise for assisted decoding (`tf/generation/utils.py:1578-1583`). The app's fallback decodes plainly and silently (inferred, `app.py:389-423`).
- Live quota read-out: no such call exists in `sp/zero/api.py`.
- Lease packing (many short jobs per lease): parked until a queue exists. Prefix-state copy on a stateful model is unverified.

## Biggest unknown
Which bucket does a tokenless `/v1` lease draw on: 40 minutes or about 2? After recovery, make one short `/v1` call and compare the ZeroGPU usage meter in HF billing before and after. Alternatively read the quota error wording: "Space app has reached its GPU limit" is the tokenless branch (`sp/zero/client.py:174-179`).