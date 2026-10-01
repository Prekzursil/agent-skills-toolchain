# Workflow tool — authoring reference (verbatim essentials of the `workflow-authoring` skill, saved 2026-09-19)

A workflow structures work across many agents — to be comprehensive (decompose and cover in parallel), to be confident (independent perspectives and adversarial checks before committing), or to take on scale one context can't hold (migrations, audits, broad sweeps). The script encodes what fans out, what verifies, what synthesizes. Often the right move is hybrid: scout inline first to discover the work-list, then call Workflow to pipeline over it.

Common single-phase workflows chained across turns: Understand (parallel readers → structured map) · Design (judge panel of N independent approaches → scored synthesis) · Review (dimensions → find → adversarially verify) · Research (multi-modal sweep → deep-read → synthesize) · Migrate (discover sites → transform each with worktree isolation → verify). For larger work run several in sequence and read each result before deciding the next phase.

Ultracode: exhaustive, correct answers; token cost is not a constraint; multi-phase work often means several workflows in sequence, one per phase, with the orchestrator in the loop between them. Patterns: adversarial verify, multi-modal sweep, completeness critic, loop-until-dry. Solo only for conversational turns or trivial edits.

## Script contract
- Script begins with `export const meta = { name, description, phases: [{title, detail?}], whenToUse? }` — a PURE LITERAL (no variables, calls, spreads or interpolation). Phase titles must match `phase()` calls exactly; add `model` to a phase entry when that phase uses a model override.
- Plain JavaScript, not TypeScript. Async context (use `await` directly). Standard built-ins EXCEPT `Date.now()`, `Math.random()`, argless `new Date()` (they throw — they would break resume); pass timestamps via `args`. No filesystem or Node API.
- Pass the script inline via `script`; it is persisted to a file and the result gives its path; iterate by editing that file and re-invoking with `{scriptPath}`; resume with `{scriptPath, resumeFromRunId}` — the longest unchanged prefix of `agent()` calls replays from cache; the first edited/new call and everything after runs live. Same script + same args → 100 % cache hit. Read `<transcriptDir>/journal.jsonl` before diagnosing empty results.

## API
- `agent(prompt, opts?) → Promise<any>`: spawn a subagent. `opts`: `label`, `phase` (explicit progress group — use inside pipeline/parallel stages to avoid races on global `phase()` state), `schema` (JSON Schema; the subagent is forced to call a StructuredOutput tool and the validated object is returned — root must be `{type:'object', properties}` with `required ⊆ properties`), `model` (omit to inherit the session model; set only when highly confident), `effort` ('low'|'medium'|'high'|'xhigh'|'max'; omit to inherit), `isolation: 'worktree'` (fresh git worktree per agent — EXPENSIVE, only when agents mutate files in parallel; auto-removed if unchanged), `agentType` (custom subagent type, composes with schema). Returns `null` if the user skips the agent or it dies on a terminal API error after retries — `.filter(Boolean)`. Without schema returns the final text.
- `pipeline(items, stage1, stage2, …) → Promise<any[]>`: each item flows through all stages independently with NO barrier; wall-clock = slowest single-item chain. Stage callbacks receive `(prevResult, originalItem, index)`. A stage that throws drops that item to `null` and skips its remaining stages. DEFAULT for multi-stage work.
- `parallel(thunks) → Promise<any[]>`: BARRIER — awaits all; a throwing thunk resolves to `null`; the call never rejects. Use only when stage N genuinely needs ALL of stage N-1 (dedup/merge across the set, early-exit on zero count, prompts that reference "the other findings").
- `log(msg)`: narrator line for the user. `phase(title)`: start a progress group.
- `args`: the Workflow `args` input verbatim (pass arrays/objects as JSON values, never as a JSON-encoded string).
- `budget`: `{total, spent(), remaining()}` — `total` null if no target; the target is a HARD ceiling: once `spent() ≥ total` further `agent()` calls throw. Guard dynamic loops on `budget.total`.
- `workflow(nameOrRef, args?)`: run another workflow inline (saved name or `{scriptPath}`); shares concurrency cap, counter, abort signal and budget; one level of nesting only.
- Subagents are told their final text IS the return value, so they return raw data. They can reach session MCP tools via ToolSearch (schemas load on demand). They get the same CLAUDE.md files injected (except built-in agent types like Explore/Plan).

## Limits
- Concurrent `agent()` calls capped at `min(16, CPUs − 2)` per workflow (this box: 4 CPUs → 2 at a time); excess queue. Lifetime cap 1000 agents per workflow; ≤ 4096 items per parallel/pipeline call.
- Smell test: `const a = await parallel(...); const b = transform(a); const c = await parallel(b.map(...))` — the middle transform does not need a barrier; use pipeline with the transform inside a stage.

## Patterns
- Loop-until-count: `while (bugs.length < 10) { push(await agent(...).bugs); log(...) }`.
- Loop-until-budget: `while (budget.total && budget.remaining() > 50_000) { … }`.
- Exhaustive review: `seen` set + `dry` counter; each round barrier-collect finders, dedup vs `seen` (NOT vs `confirmed`, else judge-rejected findings reappear forever), judge each fresh item with 3 distinct lenses concurrently, majority → confirmed; stop after 2 dry rounds.
- Adversarial verify: N independent skeptics per finding prompted to REFUTE ("default to refuted=true if uncertain"); kill if majority refute.
- Perspective-diverse verify: distinct lenses (correctness, security, perf, reproduces) instead of N identical refuters.
- Judge panel: N independent attempts from different angles, parallel judges score, synthesize from the winner grafting the best of runners-up.
- Loop-until-dry: for unknown-size discovery keep spawning finders until K consecutive rounds add nothing new.
- Multi-modal sweep: parallel agents each searching a different way.
- Completeness critic: a final agent asking "what's missing — modality not run, claim unverified, source unread?"; its output becomes the next round of work.
- No silent caps: if a workflow bounds coverage (top-N, no-retry, sampling), `log()` what was dropped.
- Scale to the ask: "find any bugs" → few finders, single vote; "thoroughly audit" → larger pool, 3–5 vote adversarial pass, synthesis stage. Compose novel harnesses when the task calls for it (tournaments, self-repair loops, staged escalation).

## Observed in this session (empirical)
- A `general-purpose` Agent-tool subagent without `model` ran on a different model than the session's and was terminated by a platform safeguard while reading a repo with security-tool code; retried successfully with `model: "fable"` and a narrower reading list.
- Schema-validated returns worked reliably across 11 workflow agents (0 errors, 0 empty results); verifiers found 0 refuted / 19 partially-confirmed / 26 confirmed — the "corrected_claim / corrected_recommendation" fields carried the most valuable content.
- Pipeline (finder → verifier per dimension) kept wall-clock ≈ 52 min for 11 agents at concurrency 2.
- Findings cited `file:line` of a snapshot that later commits shifted; snapshot the exact revision agents read, and re-map lines before acting.
