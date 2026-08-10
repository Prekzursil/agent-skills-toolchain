# The cross-vendor adapter contract

**Spec anchor:** `_USER-PROMPTS.md:10965-10983`.
**Enforced by:** `platform/coordination/dispatch.py` (`RESOLUTION`, `audit_plan`) and
`platform/coordination/adapters.py`. Every clause below has a test in `test_dispatch.py` or
`test_adapters.py`; a clause with no test is not a clause.

---

## 1. The three-way contradiction, and its resolution

Four estate documents give instructions that cannot all be obeyed as literally written. The
collision is not even across documents only — it is **internal to one file**:

| # | Source | Says |
|---|---|---|
| (a) | `rules/common/cross-vendor-dispatch.md:7-9` | A work-unit dispatch MUST block. Fire-and-forget is banned. NEVER `--background`, `&`, `nohup`, `spawn(detached)`, or **`run_in_background`** for a dispatch whose result a barrier is waiting on. |
| (b) | `rules/common/cross-vendor-dispatch.md:64-66` — **the same document, §7** | Any agent that shells to another agent runtime must set an EXPLICIT timeout (30 min) **and run under `longrun`** (AGENTS.md §4a). |
| (c) | `C:/Users/Prekzursil/.claude/AGENTS.md:59-64` §4a | Anything over 60 s MUST run via `longrun` with **`run_in_background`**/`Monitor` — never a blocking foreground call. |
| (d) | `C:/Users/Prekzursil/.claude/agents/codex.md:52-55` | `longrun` **backgrounds its child**, so `codex … - < prompt.txt` never receives stdin and dies. Put the redirect INSIDE a runner script that `longrun` calls. |

A Codex work-unit dispatch is both "a dispatch a barrier awaits" and "an operation over 60 s", so
(a) and (c) apply simultaneously and contradict. Following (a) literally violates (b) and (c).

### The resolution: **transport and contract are different axes**

Read (a) against its own evidence rather than its headline. Its bullets 2 and 3 say what it is
protecting:

> *"NEVER return a job id, a `started in the background as task-…` string, or a
> `Check /codex:status` receipt as a work-unit result."*
>
> *"A backgrounded job's result is unreachable in practice: jobs written from a subagent carry
> `sessionId: null`, and `lib/job-control.mjs:19` filters `/codex:status` by session id, so
> `null === "<id>"` hides every one of them."*

Both are statements about the **result channel** and the **caller's return contract**. Neither is a
statement about OS process topology, and neither is entailed by the child being detached.

**Therefore:**

| Axis | Contract | Rationale |
|---|---|---|
| **Logical contract** | `BLOCKING-BARRIER` — the dispatch call does not return until the unit reaches a terminal state. Non-negotiable. | This is what (a) actually asks for. |
| **Transport** | Detachment **PERMITTED**, but only WITH a declared barrier. `longrun` + `run_in_background` + a `Monitor` until-loop satisfies (b) and (c). | Detachment without a barrier IS the banned fire-and-forget. |
| **Result channel** | A **file the dispatcher reads itself** (`-o last-message.json`). Never a job store; never the `[codex] …` progress stream. | Closes both of (a)'s stated protections. |
| **Prompt delivery** | A **runner script owns the redirect**, or a `--prompt-file` argument. Never `- < prompt.txt` at the wrapper call site; never inline. | (d) — a detached child has no stdin. Inline hits the 32,767-char Windows limit (`payload_len=34472` → `os error 206`). |
| **Runner script tail** | Must end `rc=$?; …; exit "$rc"`. | A trailing bare `echo` overwrote `$?` and masked a codex exit 1 as SUCCESS in 7 s. |
| **Timeout** | Explicit, 30 min (`1_800_000` ms). The 10-min silent default is itself a violation. | (b). The silent default is what one agent rationalised `--background` to escape. |

`run_in_background` is therefore **not banned outright** — it is banned *unbarriered*. That reading
is narrower than (a)'s headline and is the only one under which (a), (b), (c) and (d) are all
satisfiable. The narrowing is recorded here rather than applied silently, and
`dispatch.RESOLUTION["why_not_a_contradiction"]` carries it as data so a test can assert the prose
and the enforcement agree (`test_dispatch.py::test_the_resolution_is_internally_consistent`).

**This resolution IS an abstraction leak** — the transport's process topology leaks into the
adapter's prompt-delivery contract and into the shell text of the runner script. That is exactly
what the spec asks to be made explicit; see `ABSTRACTION-LEAKS.md` L-01 and L-02.

### The thirteen enforced clauses

`dispatch.audit_plan` runs all thirteen on every plan and reports `checks_run` alongside
`violations`, so a clean audit is *13 of 13 ran and none fired* — never merely "nothing complained".
`test_dispatch.py::test_every_audit_check_is_reachable` proves each code can actually fire; a rule
nothing can trip is a dead rule.

| code | fires when | source |
|---|---|---|
| `V-01` unbarriered-detach | the transport detaches and no barrier is declared | (a) |
| `V-02` job-store-result | the result channel is a job store (`sessionId: null` hides it) | (a) |
| `V-03` stdout-result | the result channel is the progress stream | `cross-vendor-dispatch.md:29-33` |
| `V-04` stdin-under-detach | `stdin-redirect` prompt delivery under a detached transport | (d) — leak L-01 |
| `V-05` inline-prompt | the prompt is inlined into the command line | `:34-40` |
| `V-06` missing-timeout | no explicit timeout | (b) |
| `V-07` silent-default-timeout | `timeout_ms == 600000`, the silent default | (b) |
| `V-08` missing-ignore-user-config | codex-cli invoked without `--ignore-user-config` | `:42-47` |
| `V-09` long-run-in-foreground | expected duration > 60 s in the foreground | (c) |
| `V-10` runner-trailing-echo | the runner script does not end `exit "$rc"` | leak L-02 |
| `V-11` backgrounding-token-in-argv | `--background` / `nohup` / `&` in the argv | (a) |
| `V-12` inert-sandbox-flag | codex-cli plan relies on `--sandbox workspace-write` | leak L-04 |
| `V-13` no-output-path | no output file declared, so limb 2 cannot be evaluated | `:29-33` |

`V-11` has a **declared detector gap**: `start` (cmd.exe) and `Start-Process` also detach and are
deliberately NOT matched, because as bare argv tokens they collide with legitimate subcommands and a
matcher that fires on a mention rather than a use is worse than one with a known hole. The hole is
covered by `V-01` via the caller's explicit `background` declaration; the token scan is a second,
independent signal for the case where the caller declares foreground and the argv detaches anyway.

### What is still banned, unchanged

- Returning a job id, a `started in the background as task-…` string, or a `Check /codex:status`
  receipt as a work-unit result. (`Limb.NOT_A_JOB_RECEIPT`.)
- Parsing the `[codex] …` progress stream as a result. (`V-03`.)
- Returning nothing on failure. Every path ends in `SUCCESS:<id>` or `FAILED:<id> <reason>`.

---

## 2. The completion AND-gate

Exit code zero alone is never success (`_USER-PROMPTS.md:10646`;
`cross-vendor-dispatch.md:29-33`). `verify_dispatch` requires **all five limbs**:

1. `exit-zero` — process exited 0.
2. `artifact-present` — the declared output file exists and is at least `min_bytes`.
3. `artifact-parses` — it decodes as UTF-8 and parses as JSON.
4. `schema-valid` — it validates against the caller's schema. **No schema ⇒ `NOT-CHECKED`, which
   BLOCKS.** An unmeasured limb is never folded into a pass.
5. `not-a-job-receipt` — no fire-and-forget receipt signature.

Classification is specific, because the repair differs: `SEVERED` (exit 0, no usable artifact) is
not `EXIT-NONZERO`, and neither is `SCHEMA-INVALID`.

`min_bytes` defaults to 2 (the shortest legal JSON document) because this gate measures the
**transport envelope**. The artifact's *meaningful minimum size* is condition 3 of the shared
completion predicate, with its own per-class floors — a different plane, deliberately not duplicated
here.

---

## 3. Adapter boundaries

- **Capabilities belong to the ADAPTER, not the vendor.** `codex-cli` on this Windows box refuses
  `sandbox.enforced`; the same vendor's hosted API has no such concept.
- **Three-valued support.** `OFFERS` (measured true) / `REFUSES` (measured false) / everything else
  **UNMEASURED**, which negotiation treats as a refusal. `gemini-cli` is registered with both lists
  empty precisely to demonstrate this: it refuses every unit rather than inheriting another vendor's
  capability list.
- **A refusal raises a typed `CapabilityUnavailable`**, carrying the adapter id, the capability id
  and the preserved artifact paths. Never a falsy return.
- **A refusal is `BLOCKED`, never `FAILED` and never `SUCCESS`.** BLOCKED is a routing fact; FAILED
  would claim the work was attempted and would burn a retry.
- **The artifact survives the refusal.** Nothing in `adapters.py`, `handoff.py` or `recovery.py`
  deletes, moves or truncates an artifact, and a MISSING artifact stays on the record rather than
  being dropped from the list.
- **No fallback chain.** `route()` returns EVERY candidate's negotiation and has no `chosen` field.
  A substitution the caller did not ask for is the interchangeability lie the spec forbids.

---

## 4. Provenance of the adapter facts

Every `codex-cli` value in `ADAPTER-REGISTRY.json` is **LEDGER-RECORDED** from the 2026-07-18
cross-vendor rail smoke-test (transcribed into `~/.claude/agents/codex.md`) and was **NOT
re-measured** by this build unit. `CAPABILITY-REGISTRY.json` carries
`verified_by_this_unit: false` on every entry, and
`test_capability.py::test_no_capability_claims_to_be_verified_by_this_unit` asserts it — so
promoting any entry to a fresh measurement requires flipping the flag AND that assertion, which
forces the claim to be made deliberately instead of by drift.
