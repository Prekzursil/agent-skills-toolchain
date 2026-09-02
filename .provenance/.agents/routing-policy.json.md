# Provenance for `.agents/routing-policy.json`

The policy is a closed schema (BUILD-CONTRACT section 7): keys carry behaviour, never
rationale, and there is no `$comment` key. The "why" lives here. Validator and router:
`.agents/scripts/routing_policy.py`; red-proof tests: `.agents/tests/test_routing_policy.py`.

## Why the file exists (D11 = A, 2026-09-02)

DECISION-QUEUE D11 chose option A: routing policy and PACE data as a names-only JSON file
read by wrappers with a loud fallback, instead of prose in the skill (option B, "routing
stays unmeasurable"). Every model or endpoint name in the file must resolve in
`.agents/models.json` (`id`, `id@endpoint`, or an alias); the file never repeats a URL,
port, price or credential that the registry already owns (L6: names only). When the file
is missing or fails validation, `load_policy_or_fallback` prints exactly one line
`FAILED:routing-policy <reason>; falling back to registry slots` to stderr and returns
`(None, "fallback")`, so a wrapper degrades to the registry's `slots` instead of guessing.

## The PACE borrow (lens 10, section 6.1, gold gem)

Each class carries a Primary / Alternate / Contingency / Emergency plan taken from US Army
signal doctrine (FM 6-02, FASDC test). The rule that matters is **Distinguishable**: a
backup may not rely on the means that just failed. A chain of four `cursor-*` ids is
P,P,P,P, because every rung dies with the same bridge, which is also this estate's Most
Severe Single Contingency. The validator therefore enforces, per class:

- at most one rung on a `cursor-*` endpoint (V-P5, L3: the bridge is one means);
- at least one of P/A/C on a `local` endpoint or a procedure step (V-P6: one rung that
  survives loss of the network);
- `E` is a `handoff:` procedure naming both `basic-memory :8765` and `agent-mail :8812`
  (V-P7): "gracefully stop with a handoff" is a designed state, not a crash, and the
  estate already owns both ports;
- no two model rungs on the same endpoint (V-P8);
- `P` names the class primary and is a model, never a procedure (V-P14).

**Complete** means written triggers, so every `pace.triggers` list is drawn from the
inference-hub error vocabulary (contract section 4) plus `timeout`.

The means available to this seed registry are: local GPU (`ollama`), hosted router
(`hf-router`), the OpenRouter sidecar (`openrouter`, CLI/Codex only), the Cursor quota
bridge (`cursor-auth2api`), and procedures. `lmstudio` has no models yet and `llamacpp`
is disabled, so neither appears; when a model lands on either, it becomes a second local
means and can replace a cursor or procedure rung.

## Classes, rungs and shares

| class | primary | escalate_to | P / A / C | share |
|---|---|---|---|---|
| `simple` | `qwen2.5-7b` | `glm-5.3` | ollama / hf-router / cursor bridge | 0.05 |
| `code-edit` | `glm-5.3` | `glm-5.2-free` | hf-router / openrouter / ollama | 0.35 |
| `extract-json` | `glm-5.3` | `qwen2.5-7b` | hf-router / cursor bridge / ollama | 0.15 |
| `long-context` | `glm-5.3` | none | hf-router / cursor bridge / procedure | 0.15 |
| `summarize` | `qwen2.5-7b` | `glm-5.3` | ollama / hf-router / cursor bridge | 0.10 |
| `cli-grunt` | `glm-5.2-free` | `qwen2.5-7b` | openrouter / hf-router / ollama | 0.20 |

Every `E` rung is the same handoff procedure with a class-specific note body (what to
save so the owner can resume: question and partial answer, diff so far, schema and
input pointer, command and partial output).

- **`simple`** (short factual turns). Local first because the 7B model on the RTX 4050
  is free and fast enough; `glm-5.3` is the escalation when the answer misses the quality
  floor. C is the Cursor bridge so that a box with a dead GPU and a dead HF token still has
  a route. `features.streaming: declared` is the only floor: a chat turn needs nothing else.
- **`code-edit`** (multi-file edits, tool calls). Highest quality exponent (0.6) and the
  largest share (0.35): edits are where a weak model costs the most human time. A is the
  OpenRouter free slug, a different vendor, credential and network path from the HF
  router, which is what makes it a real alternate; that forces `callers: ["codex","cli"]`
  (L1, V-P9) so a Cursor or Claude caller never sees this class. C is the local model so
  the class survives loss of the internet, at reduced quality.
- **`extract-json`** (schema-valid output). The eval lane grades this class pass^3, so P
  is the model with the best declared structured-output support, A is the bridge (a
  different quota, not a different vendor of the same key), and the escalation and C are
  the local model, which the hub runs with constrained decoding. `MALFORMED_RESPONSE` is
  an extra trigger because a malformed body is the failure this class exists to avoid.
- **`long-context`** (prompts over 8k tokens). Only the hosted 131k rows open to every
  caller can take the prompt whole, so `escalate_to` is empty (the local rows would
  silently truncate, which is worse than failing) and C is a `procedure:` rung: split into
  8k windows, run `summarize` locally on each, stitch. `pinned_until: 2026-10-02` holds the
  procedure rung for one review cycle; the intended replacement is an eval-gated local
  model with a larger context, once one passes the T2 lane.
- **`summarize`** (highest volume, lowest stakes). Same rungs as `simple` with the cost
  exponent highest (0.4): stay local and free unless the quality floor fails.
- **`cli-grunt`** (repetitive CLI/Codex chores). P is the OpenRouter sidecar so the
  spend-capped keys absorb the chatter and the HF router budget stays for edits; that is
  the one class where OpenRouter is primary, and it is closed to `cursor`/`claude`
  callers (L1). `BACKEND_RATE_LIMITED` is an extra trigger because the free slug is the
  rung most likely to hit a daily limit. Escalation goes down to the local model rather than
  up to `glm-5.3`: grunt work must not eat the edit budget when the sidecar is out.

**Spend shares** sum to 1.0 and rank classes by where paid tokens buy the most:
edits 0.35, CLI grunt 0.20 (high volume, but on the capped sidecar), extraction and
long-context 0.15 each (paid by construction: both start on the hosted router), then
summaries 0.10 and simple turns 0.05, which are local-first and should spend almost
nothing. Shares are ceilings for the budget accountant, not targets.

**Exponents** (quality, speed, cost; sum 1.0) weight the score the router uses when a
floor admits several candidates: quality-led for `code-edit`, `extract-json` and
`long-context`; speed-led for `simple`; cost-led for `summarize` and `cli-grunt`.

**Floors** name one capability each in the contract's lattice
(`native > probed > declared > emulated > absent`, V-P11). They are deliberately at
`declared`, not `probed`, because the D9 probe has not run yet; the D9 receipt should
raise `code-edit` and `extract-json` to `probed`.

## Status handling is truthful, not hidden

`cursor-grok-4.6` is `unprobed` until the D9 receipt lands, and `qwen3-*` are
`eval-gated`. Such a model may not be a primary (V-P13 error) but may be an escalation or
a PACE rung, where the validator emits a warning instead. The committed policy therefore
validates with four warnings, one per cursor rung, and `route()` returns those rungs with
`status: "unprobed"` rather than skipping them: the wrapper decides, the policy reports.

## `callers` is the one key beyond the contract's list

Contract section 7 lists `primary, escalate_to, floors, exponents, spend_share, pace,
justification, pinned_until?`. The build instruction for D11 added an optional
`callers[]` so that the L1 rule ("OpenRouter rungs only in CLI/Codex task classes") is
data the validator can check (V-P9: any OpenRouter reference requires `callers` to be a
subset of `{codex, cli}`) instead of a convention in prose. It is the only extension.

## Retire = human write-back only

`review.owner` is `human write-back only`, the same rule D12 states for model retirement.
The autoresearch loop and the probe ladder may PROPOSE a change to this file (a diff, a
message on agent-mail, a note in basic-memory); they never write it. `review.cadence`
is monthly and `last_review` is the date of the last human pass; the validator requires
both, so a policy nobody has reviewed is visibly stale rather than silently trusted.

## Rollback

Delete the file. Every wrapper prints the one loud line and falls back to the registry
`slots`; no port, daemon or secret is touched.
