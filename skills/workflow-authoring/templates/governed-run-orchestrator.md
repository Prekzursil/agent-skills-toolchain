---
title: governed-run-orchestrator
type: note
permalink: dqverify-repo-20261013/skills/workflow-authoring/templates/governed-run-orchestrator
---

<!--
PROVENANCE - vendored reusable TEMPLATE (do not fill in place).
Source path: ~/.claude/workflow-runs/parallel-adoption-2026-07-24/prompts/final-workflow-prompt.TEMPLATE.md
Frozen sha256: c38cabd29348812ef19efef27f838252dc452d162b50fead07c6d875c0fe1515 (158689 bytes)
Vendored by: adopt/parallel-adoption-2026-07-24/workflow-harness (agent-skills-toolchain).

This is the PRISTINE reusable orchestrator meta-prompt. The <GOAL> and <DoD> slots below are
INTENTIONALLY UNFILLED. To use it: copy this file, replace ONLY the two slot bodies with a real
goal and numbered DOD-NN rows (remove every [...] instructional sentinel; keep the tag names and
the DOD-NN id format), freeze, and launch via /workflow. See ../SKILL.md, section
"Governed single-shot run". Do NOT fill the slots in this vendored copy - it is the template.
-->

## HOW TO USE

1. Open Claude Code at the root of the checked-out `agent-skills-toolchain` repository on the Windows 11 owner machine (PowerShell 7, Node 22, Python 3.11).
2. Replace only the bodies of `&lt;GOAL&gt;` and `&lt;DoD&gt;` below. Remove every instructional placeholder. Keep the tag names, `DOD-NN` ID format, guardrails, and orchestration contract unchanged. Add as many unique DoD IDs as the goal needs; freeze them when the run starts.
3. Invoke `/workflow ` and paste this entire filled prompt after it as one task-description payload. `/workflow` accepts one raw string; do not invent `--goal`, `--dod`, or JSON-argument flags.
4. `&lt;GOAL&gt;` is the authoritative durable outcome, named scope, resumable starting state, and explicit exclusions. `&lt;DoD&gt;` is the authoritative numbered completion AND-gate. Every downstream unit receives both blocks verbatim plus its assigned DoD IDs. No enhancer, planner, worker, reviewer, or synthesizer may rewrite, weaken, replace, or silently omit either block.
5. The fixed default is `COMPUTE_BACKEND=auto`: ordinary Dynamic Workflow execution is local; the controller may use the canonical Databricks fan-out skill only for a sufficiently large, portable, secret-free subset under the backend policy below. Backend choice changes transport and capacity only, never scope, evidence, write authority, or completion semantics.
6. Treat every starting-state statement as a claim to re-probe. Resume unfinished work and verify already-landed work; do not redo a landed item merely because it remains named.
7. This one-shot invocation authorizes automatic advancement through ordinary reversible in-scope discovery, planning, build, review, integration, verification, reconciliation, focused PR creation, merge-when-green, exact proven cleanup, and memory synchronization. Preserve real dependency and authority barriers, but do not ask the user to order routine next phases. Stop only for missing authority, an outcome-changing ambiguity that cannot safely be inferred, a required undiscoverable secret, or an irreversible shared action not already authorized here.
8. Emit one terminal `SUCCESS:<workflow-id>` only if every DoD ID passes. Otherwise emit `FAILED:<workflow-id> <reason>` with every unmet DoD ID, preserved artifacts/branches/worktrees, the exact blocker, and one resumable next action. A progress report, job ID, “started in the background,” “ready,” or “check status” is never terminal success.

<GOAL>
Outcome:
[State one durable end-state in imperative, outcome language.]

In scope:
- [Name each workstream, repository, external destination, or integration that must reach a terminal state.]

Starting state to re-verify:
- [Name reported-complete, partial, blocked, merged, deployed, or authenticated state that prevents needless rework.]

Out of scope:
- [State exclusions, or: No expansion beyond the named workstreams except a prerequisite required by a DoD item.]
</GOAL>

<DoD>
Every numbered row is required; completion is the logical AND of all rows.

- DOD-01 | State: [One externally observable final condition.] | Evidence A: [first signal/source.] | Evidence B: [mechanically independent signal/source.]
- DOD-02 | State: [One externally observable final condition.] | Evidence A: [first signal/source.] | Evidence B: [mechanically independent signal/source.]
- DOD-03 | State: [One externally observable final condition.] | Evidence A: [first signal/source.] | Evidence B: [mechanically independent signal/source.]

Terminal rule: emit SUCCESS only when every DoD ID and every repeated atomic member is PASS with both evidence records and no unresolved in-scope work remains. Otherwise emit FAILED with every unmet ID/member, blocker, preserved state, required authority, and exact continuation action.
</DoD>

## MAIN INSTRUCTION BODY

You are the owner-level Claude Code controller. Do not merely propose a workflow. In this same invocation, ground the live estate, author one saved Dynamic Workflow (or the live runtime’s equivalent ultracode fan-out), statically validate it, launch it with the frozen raw goal/DoD, monitor and resume it through terminal fan-in, shepherd every authorized repository unit through actual integration, reconcile memory, and print the mechanically derived terminal marker. Work continuously without human babysitting.

The workflow is reusable and discovery-driven. The raw `<GOAL>` and `<DoD>`, constraints, one pre-pinned artifact root, and budgets are the only fixed inputs. Named examples, remembered workstreams, old PR numbers, file paths, memory, and prior agent messages are seed leads, not a static backlog and never user approval.

### 1. Ground first and freeze the run

Before mutation or dispatch:

1. Confirm the current directory is the intended `Prekzursil/agent-skills-toolchain` checkout; read the root `AGENTS.md` and every nearer `AGENTS.md` that governs a candidate path. Read the live versions of:

   ```text
   rules/common/git-workflow.md
   rules/common/development-workflow.md
   rules/common/fan-out-contract.md
   rules/common/single-signal-verification.md
   rules/common/cross-vendor-dispatch.md
   rules/common/harness-vcs-hygiene.md
   rules/common/stale-megapr-reconcile.md
   rules/common/windows-shell.md
   skills/workflow-authoring/SKILL.md
   skills/using-git-worktrees/SKILL.md
   skills/finishing-a-development-branch/SKILL.md
   skills/verification-before-completion/SKILL.md
   commands/pr-shepherd.md
   commands/handle-pr-comments.md
   commands/multi-workflow.md
   commands/start-task.md
   hooks/git-hygiene/README.md
   hooks/_shared/completion.py
   scripts/worktree-isolation/README.md
   skills-claude-only/metaswarm-design-review-gate/
   skills-claude-only/metaswarm-plan-review-gate/
   skills-claude-only/metaswarm-orchestrated-execution/
   agents/code-reviewer.md
   agents/python-reviewer.md
   agents/typescript-reviewer.md
   agents/security-reviewer.md
   .github/workflows/quality.yml
   .quality/charter.yml
   ```

2. Re-probe the installed Claude version and Workflow help/schema before writing JavaScript; compare the official `https://code.claude.com/docs/en/workflows` contract. The read-only 2026-07-24 grounding commit was `a919578f2cdf107ac8f049ae5a97459e25b83440`, but that is a stale lead. At that revision the current runtime contract was `agent()` / `parallel()` / `pipeline()` / `phase()` / `log()`, structured `args`, `budget.total`, `budget.spent()`, and `budget.remaining()`. `skills/workflow-authoring/SKILL.md:23-25,63-71` was stale: it omitted `pipeline()` and `log()`, claimed string-only `args`, and recommended brittle closed schemas. `workflows/rtv-pdr.js:11-15,114-152` and `harness-sota-2026-07-18-corpus/P1C16.md:14,18,24` recorded the newer surface. Adapt to the actually installed runtime and record any delta. If native `pipeline()` is absent, implement the same per-item sequential chain with proven available primitives; do not pretend an unsupported call exists.
3. Capture the live repo/ref/PR/worktree/config/runtime state read-only. Detector failure, denial, timeout, invalid JSON, or inability to find a known-present control is `UNKNOWN`, never an empty census. Never echo `$GITHUB_TOKEN`, a PAT, cookie, JWT, password, private key, or `auth.json`. If a read-only clone is needed, use the token without putting its value in output, set `core.hooksPath` to a safe empty directory, use `--no-checkout`, and never run a cloned repository’s hooks.
4. Generate once, with a tool call outside Workflow JavaScript, a stable `<workflow-id>`, RFC3339 UTC start time, and absolute Windows artifact root:

   ```text
   C:/Users/Prekzursil/.claude/workflow-runs/<workflow-id>
   ```

   Pin that root in the launch args and never recompute it. Do not call `Date.now()`, `new Date()`, `Math.random()`, or a volatile ID generator in Workflow JavaScript or a shared prompt prefix.
5. Create a secret-free frozen grounding pack before fan-out:

   ```text
   python <checkout>/tools/repomap/repo_map.py --root <checkout> --budget 900 --out <artifact-root>/GROUNDING-PACK.md
   ```

   `<checkout>` is the `agent-skills-toolchain` working tree. The bare repo-relative
   `tools/repomap/repo_map.py` only resolves when cwd IS that root; from any other cwd it
   dies with `[Errno 2] No such file or directory`.

   Enumerate the artifact root before launch; freeze that listing, the pack SHA-256, source subject kind/ref/content SHA-256, schemas, common preamble, launcher, and prompt hashes. Inline the frozen pack where the fan-out contract requires it; telling children to reread a mutable path is not equivalent.
6. Run a clean read-only repository preflight and preserve unrelated user changes. Do not reset, checkout over, stash, clean, delete, or rewrite them. If an overlap cannot be safely isolated, fail that unit with the exact owner decision required.
7. For a net-new design, enforce the five-reviewer design gate before implementation: fresh read-only Task-mode Product Manager, Architect, Designer/API-DX, Security, and CTO/TDD-readiness reviewers; each returns `APPROVED|NEEDS_REVISION`, `blockers[]`, `suggestions[]`, and `questions[]`; Security adds the threat model and PM adds use-case coverage. Missing/null is `NEEDS_REVISION`; all five must approve. Revise and rerun all five fresh, at most three rounds. Pass the explicit design path because conventions drift between `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and `docs/plans/*-design.md`; never trust `--latest`. If round three is not unanimous, persist findings and return FAILED requiring the real owner decision prescribed by the gate.
8. For two or more work units or three or more touched files, enforce the plan gate. Mechanically require at most five scoped paths per repo-code unit, no ownership overlap, and an acyclic dependency graph. Inspect `~/.claude/harness-meta/plan_lint_stage0.py` before using it: its documented `PLAN_LINT:clean|dirty|na` field, not exit zero, determines the result. Then send the full plan and original request to three fresh read-only reviewers:
   - Feasibility verifies real paths, dependency DAG/order, codebase compatibility, critical assumptions, and executable validation commands.
   - Completeness maps every requirement to a unit and requires an independent verification method, edge/error/boundary cases, and every integration point.
   - Scope & Alignment maps every unit to request/prerequisite and blocks creep, under-scope, divergence, overlap, and unjustified abstraction.

   Each returns binary `PASS|FAIL` with file:line evidence; missing/null or any blocker is FAIL, while warnings alone do not fail. Fix or evidence-rebut every finding and rerun all three fresh, at most three rounds. After a failed third round, persist the review history and return FAILED requiring the real owner decision. Saved `/design-gate` and `/plan-gate` workflows were documented as SHADOW/advisory and cannot satisfy a hard gate unless the live implementation proves otherwise. `auto_activate` metadata is not proof that a trigger fired. Reviewer consensus is not user authority for a new destructive or materially expanded design.

### 2. Parse and freeze the two authoritative slots

`/workflow` supplies one raw `$ARGUMENTS` packet. A saved Workflow may expose it as a string `args`, an object `args.task`, or a structured object supplied by the launcher. Never call `.match()` on an unchecked value. Preserve the raw captures byte-for-byte and use trimmed copies only for validation:

```js
const structured =
  typeof args === 'object' && args !== null && !Array.isArray(args) &&
  typeof args.goal === 'string' &&
  (typeof args.dod === 'string' || Array.isArray(args.dod))
const packet =
  typeof args === 'string' ? args :
  (typeof args === 'object' && args !== null && typeof args.task === 'string') ? args.task :
  ''
const goalMatches = structured ? [] : [...packet.matchAll(/<GOAL>([\s\S]*?)<\/GOAL>/g)]
const dodMatches = structured ? [] : [...packet.matchAll(/<DoD>([\s\S]*?)<\/DoD>/g)]
const goalMatchCount = structured ? 1 : goalMatches.length
const dodMatchCount = structured ? 1 : dodMatches.length
const goalRaw = structured ? args.goal : (goalMatches.length === 1 ? goalMatches[0][1] : '')
const dodRaw = structured
  ? (Array.isArray(args.dod) ? args.dod.join('\n') : args.dod)
  : (dodMatches.length === 1 ? dodMatches[0][1] : '')
const goalForValidation = goalRaw.trim()
const dodForValidation = dodRaw.trim()
```

Fail before mutation if `goalMatchCount` or `dodMatchCount` is not exactly one; a validation copy is empty; an exact instructional sentinel such as `[State one durable end-state` remains; the goal has no observable outcome or scope boundary; the DoD has duplicate/malformed IDs; or the existing requirement preflight is below 7/10 clarity. Do not reject arbitrary square brackets. DoD rows must be atomic states, not activities such as “investigate,” “try,” “proceed into,” or “work on.” If alternatives are acceptable, define their equivalence in the row. A repeated-set condition requires two signals for every member.

Preserve `goalRaw` and `dodRaw`, including boundary whitespace, in a byte-stable common prefix. An enhancer may append non-authoritative context but must reproduce both bodies verbatim. Freeze DoD IDs at launch. Every worker receives the complete frozen bodies plus its exact assigned IDs; only final synthesis may mark a parent DoD PASS.

When the saved Workflow is launched through structured args rather than the raw slash packet, use this exact logical launch shape and preserve the raw goal/DoD values:

```json
{
  "goal": "<raw goal>",
  "dod": "<raw DoD or array of raw clauses>",
  "artifact_root": "<one absolute, pre-pinned run root>",
  "max_agent_calls": 900,
  "scout_page_size": 100
}
```

The controller must accept either the single raw `/workflow` packet or this structured wrapper, never accidentally stringify an object. The raw slash payload remains authoritative for this invocation. Clamp the agent count and require positive bounded page size; an arbitrary page boundary is not dry.

For unreliable agent transport, follow the measured `tools/fanout-schema` convention: exactly one always-producible required narrative/JSON string, all conditional fields optional, and `additionalProperties:true`. The measured result was 0 failures in 130 calls for one required string versus 727/2,742 failures for other shapes; 30 were rejected only for an extra property. Put machine-critical content as canonical JSON inside that required string and validate it deterministically. Where a strict shape is required, such as the final result below, treat it as the inner JSON contract rather than forcing every leaf to satisfy a brittle closed outer schema.

Strict final inner contract:

```js
const FINAL_INNER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['terminal', 'summary', 'dod_results', 'workstreams', 'blockers'],
  properties: {
    terminal: {
      type: 'string',
      pattern: '^(SUCCESS:[A-Za-z0-9._-]+|FAILED:[A-Za-z0-9._-]+ .+)$',
    },
    summary: { type: 'string', minLength: 1 },
    dod_results: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'status', 'evidence_ids'],
        properties: {
          id: { type: 'string', pattern: '^DOD-[0-9]{2,}$' },
          status: { type: 'string', enum: ['PASS', 'FAIL'] },
          evidence_ids: {
            type: 'array',
            minItems: 2,
            items: { type: 'string', minLength: 1 },
          },
        },
      },
    },
    workstreams: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'status'],
        properties: {
          id: { type: 'string', minLength: 1 },
          status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
          artifact: { type: 'string' },
          blocker: { type: 'string' },
        },
      },
    },
    blockers: { type: 'array', items: { type: 'string' } },
  },
}
```

The outer final agent schema still has only `final_json` as its required string. Parse it, validate `FINAL_INNER_SCHEMA`, and independently recompute `terminal`; the synthesizer may explain but never upgrade the computed status.

### 3. Author one dynamic, ledger-driven controller

Use one stable `meta.name` and these fixed top-level phases. Re-scout and repair rounds are `log()` messages inside `Work Loop`, never dynamically invented phases:

```js
export const meta = {
  name: 'goal-e2e-dynamic',
  description: 'Discover and drain a live GOAL+DoD backlog through verified integration.',
  phases: [
    { title: 'Ground', detail: 'Validate authority, runtime, source, and frozen contracts' },
    { title: 'Scout', detail: 'Atomize requirements and census the live relevant estate' },
    { title: 'Work Loop', detail: 'Normalize and run dependency-ready units until dry' },
    { title: 'Integrate', detail: 'Reconcile all surviving explicit commits and live state' },
    { title: 'Final verify', detail: 'Falsify the combined end state and exact-SHA gates' },
    { title: 'Closure', detail: 'Persist memory and return the mechanical terminal result' },
  ],
}
```

Workflow JavaScript has no direct filesystem or shell access. Agents perform probes and writes; the controller only validates structured data, computes exact set/DAG/state logic, and routes frozen prompts. Inline schemas; do not assume imports work in the isolated Workflow realm.

Runtime limits from the grounded v2.1.218-era implementation were up to 16 concurrent native agents (`min(16,max(2,cpuCores-2))` in that implementation), 1,000 total calls per run, and 4,096 inputs to one `pipeline`/`parallel`. Re-probe. Clamp `max_agent_calls` to at most 900, reserving at least 10% for pagination, contract repair, dependency diagnosis, two closure sweeps, final verification, and closeout. A ceiling is a failure circuit breaker, never dryness. Do not hand-shrink a required frontier to 16; let the runtime queue it. Do not confuse native 16 with Databricks’s separate 48-process rail.

Declare:

```js
const DISCOVERY_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    discovery_json: {
      type: 'string',
      description: 'Complete canonical Discovery JSON, no Markdown fence; the only required field.',
    },
    coverage_markdown: { type: 'string' },
  },
  required: ['discovery_json'],
}

const WORK_RESULT_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    receipt_json: {
      type: 'string',
      description: 'Complete canonical WorkReceipt JSON, no Markdown fence; the only required field.',
    },
    result_markdown: { type: 'string' },
  },
  required: ['receipt_json'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    verification_json: {
      type: 'string',
      description: 'Canonical verification JSON; the only required field.',
    },
    verification_markdown: { type: 'string' },
  },
  required: ['verification_json'],
}

const FINAL_TRANSPORT_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    final_json: {
      type: 'string',
      description: 'Canonical JSON satisfying FINAL_INNER_SCHEMA; the only required field.',
    },
    final_markdown: { type: 'string' },
  },
  required: ['final_json'],
}
```

#### Dynamic discovery is load-bearing

Do not encode examples, entity names, paths, PR numbers, MCP names, corpus sources, or a remembered workstream count as `WORKSTREAMS=[...]`, `TASKS=[...]`, `COHORTS`, `ALL_WUS`, or another execution list. They are leads and coverage hints. Before the first work `pipeline()`, call a synchronous, read-only, schema-typed Scout against the live environment:

```js
const MAX_AGENT_CALLS = Math.min(900, validatedRequestedMaxAgentCalls)
let calls = 0
async function countedAgent(prompt, opts) {
  if (calls >= MAX_AGENT_CALLS) {
    throw new Error('agent-call-reserve-exhausted')
  }
  calls += 1 // attempted calls count even when they throw or return null
  return agent(prompt, opts)
}

phase('Scout')
const initialRaw = await countedAgent(SCOUT_PREFIX + frozenRawGoalDodAndConstraints, {
  label: 'scout:initial',
  phase: 'Scout',
  schema: DISCOVERY_SCHEMA,
  effort: 'xhigh',
})
```

The Scout must:

1. Atomize raw goal and DoD into stable obligation IDs, preserving each original clause and conjunct and giving each an observable terminal predicate.
2. Derive relevant search surfaces from the actual nouns and verbs: repo/ref/PR state, tracked plans/task registries, scoped files/config, memory/state ledgers, declared output destinations, and reachable control planes. Do not perform an unrelated disk census or machine-wide MCP reap.
3. Re-probe inherited narrative, prior plans, memory, named workstreams, and peer messages before classifying them. Mark already-satisfied obligations with fresh closure evidence; changed fingerprints may reopen them.
4. Use read-only probes and record locator, exact probe, redacted observation, freshness, related DoD IDs, timestamp generated inside the agent tool call, and stable fingerprint. Before reporting absence, prove the detector on a known-present control. Denied/timed-out/unparseable/unreachable is `unknown` or `inaccessible`, never empty.
5. Split open work into concrete independently executable units: one observable state transition, bounded ownership/targets, independently checkable acceptance, real prerequisites, venue, risk/effort, and at least one DoD mapping. Separate prerequisite probes from mutations whose safety depends on them; separate unrelated venues/outcomes; repo-code units normally own at most five files.
6. Emit a bounded page with `has_more` and cursor. Exhaust all relevant pagination before the first work wave.
7. Perform no edit, install, commit, push, merge, message, config write, or deployment.
8. Immediately write a truthful scan receipt with unmeasured portions exactly `UNKNOWN - not yet measured`, then rewrite after each source/page.

Every obligation `id` and every `dod_ids` reference uses the exact frozen `DOD-NN` ID. If one DoD row intentionally quantifies repeated members, keep `parent_dod_id:"DOD-NN"` and a separate collision-free `member_id`; never replace the parent with an invented `D1`-style ID. Final set equality is over the frozen parent IDs plus the required member matrix.

`discovery_json` has this exact logical shape:

```json
{
  "obligations": [
    {
      "id": "DOD-01",
      "text": "verbatim normalized requirement",
      "success_observable": "externally checkable terminal predicate",
      "status": "satisfied|open|unknown|inaccessible",
      "evidence": ["Evidence objects"],
      "settling_probe": "exact next probe, empty only when settled"
    }
  ],
  "items": [
    {
      "semantic_key": "kind|authority|normalized-target|desired-state",
      "title": "short human label",
      "objective": "one terminal postcondition",
      "kind": "probe|change|reconcile|external",
      "dod_ids": ["DOD-01"],
      "evidence": ["Evidence objects"],
      "acceptance": ["observable predicate"],
      "targets": ["bounded path, object, or control-plane target"],
      "read_scope": ["bounded source"],
      "write_scope": ["bounded owned target"],
      "depends_on": ["other semantic keys"],
      "conflict_keys": ["exclusive resource or overlapping write scope"],
      "venue": "host-local|repo-worktree|remote-portable|external-readonly",
      "mutates": true,
      "risk": "low|medium|high",
      "effort": "small|medium|large",
      "state": "ready|needs_probe|blocked|already_satisfied|split_needed",
      "discovered_from": "goal clause, source, or parent unit"
    }
  ],
  "sources": [
    {
      "locator": "source identity",
      "probe": "exact read-only probe",
      "status": "ok|denied|error|not_applicable",
      "positive_control": "known-present control and result",
      "fingerprint": "stable state fingerprint"
    }
  ],
  "coverage_gaps": ["unmapped or unproved obligation IDs and reason"],
  "unscannable": ["material source, reason, and settling access/probe"],
  "has_more": false,
  "cursor": "",
  "scan_artifact": "<absolute receipt path>"
}
```

Evidence object:

```json
{
  "locator": "path:line, command-result identity, API object, or immutable URL",
  "probe": "exact mechanism used",
  "observation": "redacted bounded result",
  "freshness": "live|stale-lead|unverified",
  "fingerprint": "stable hash/ref/status when available",
  "settles_dod_ids": ["DOD-01"]
}
```

Work receipt:

```json
{
  "unit_key": "the exact input semantic_key",
  "status": "done|already_satisfied|blocked|failed|needs_recheck",
  "summary": "bounded result",
  "closure_evidence": ["Evidence objects"],
  "new_leads": ["Item-shaped leads, not silently executed"],
  "changed_fingerprints": ["target=fingerprint"],
  "blocker": "authority or unsatisfied prerequisite, if any",
  "artifact_path": "<contracted unit artifact>"
}
```

The open transport may additionally carry `branch`, `commit_sha`, `pushed`, `files_changed`, `tests`, `evidence`, and `blockers`. They remain optional in the outer schema for reliability, but deterministic controller code makes `artifact_path`, terminal status, and postcondition evidence mandatory for every unit, and for a mutating unit also requires nonempty branch/40-hex commit, `pushed:true`, exact changed paths, validation receipts, remote visibility, PR/merge, and cleanup evidence. A missing conditional field is failure, not permission to infer it from prose.

Every `verification_json` must decode and validate to this controller-owned inner contract:

```json
{
  "subject_id": "<exact semantic unit key or exact final verifier role>",
  "stage": "candidate-validation|independent-postcondition|critic-check|post-publish|final",
  "verdict": "PASS|FAIL|UNVERIFIED",
  "artifact_path": "<absolute canonical artifact>",
  "artifact_exists": true,
  "artifact_sha256": "<64-hex>",
  "postcondition_met": true,
  "scope_exact": true,
  "tested_subject": {
    "kind": "worktree|commit|integration-head|live-state",
    "path_or_ref": "<exact locator>",
    "sha": "<40-hex or content hash>"
  },
  "signals": [
    {
      "signal_id": "A",
      "tool": "...",
      "engine": "...",
      "shell": "...",
      "field": "...",
      "command": "exact command",
      "exit_code": 0,
      "evidence": ["path:line or immutable URL"]
    }
  ],
  "vcs": {
    "branch": "<branch or empty when N/A>",
    "commit_sha": "<40-hex or empty pre-publish/N/A>",
    "remote_ref_matches": false,
    "pr_state": "<MERGED|OPEN|N/A>",
    "merge_oid": "<40-hex or empty>",
    "merge_oid_on_main": false,
    "exact_head_ci": false,
    "cleaned": false
  },
  "blockers": [],
  "receipt": "SUCCESS:<subject-id>-verify PASS|FAILED:<subject-id>-verify <reason>"
}
```

The controller validates subject identity, enums, SHA formats, required signal independence, and stage-specific fields. Candidate stages require the exact persistent worktree and candidate content hash but leave publish fields false/empty. A mutating `post-publish` PASS requires branch/commit, remote ref match, actual merged PR, merge OID on current main, exact-head CI, and cleanup even if the feature branch was deleted. A final-role result uses its role as `subject_id`, proves the final integration SHA/live locator, and keeps VCS N/A only when truly non-repository. `combineProducerAndVerifierOrFail()` maps these fields mechanically; opaque prose cannot drive state.

Use `JSON.parse` and deterministic validation for required arrays, enums, booleans, key identity, and `has_more/cursor`. Missing output, wrong type, invalid JSON, malformed unit, or identity mismatch is a failed receipt, never an empty list. Retry once with a contract-repair prompt containing validation errors. A second failure is terminal `FAILED:discovery-contract-invalid` or a failed work unit and cannot advance dryness.

#### Deterministic normalization and scheduling

Use a workflow-local `Map` keyed by the full canonical:

```text
normalize(kind) | normalize(authority) | normalize(target) | normalize(desired postcondition)
```

Normalize Unicode, path separators, case of vocabulary components, and collapsed whitespace. Never use an array index, round, timestamp, random value, prose-only title, or lossy `_slug()` as identity (`a_b.py` and `a-b.py` can collide). Keep the full key; derive only a separately escaped bounded telemetry label. Sort serialized sets and ledger entries by key for byte-stable resumes.

The intake code must default optional arrays to `[]`; reject self-dependencies, malformed keys, unbounded scopes, duplicate artifact identities, missing DoD mappings, and acceptance without an observable; exact-key dedupe by set-union of evidence/acceptance/DoD/provenance/dependencies/conflicts; near-dedupe only through a typed semantic reconciler returning `same|overlap|distinct`, merging only equal authority/target/desired-state while preserving aliases, dissent, and all evidence; treat shared resources as scheduling conflicts rather than automatic duplicates; resolve aliases before dependencies; mechanically detect dangling dependencies and cycles (for example Kahn sorting); turn a dangling edge into a targeted discovery lead and a cycle into decomposition; retain terminal history; do not redispatch a stale recurring terminal lead, but reopen it on a contradictory live fingerprint; mark evidence-free leads `needs_probe`; order ready units by true prerequisite/unblocker, uncovered DoD atoms, risk/effort, then canonical key; select the maximal dependency-ready conflict-free frontier. No-ready-with-pending triggers diagnosis, never success.

Exact comparisons, SHA/hash/bytes, counts, membership, path-prefix overlap, set intersections, DAG checks, and sorting are code decisions. Agents judge only semantic equivalence, behavioral intent, or decomposition.

#### Per-item pipelines, not global stage barriers

`pipeline(items, ...stages)` is the default for independent multi-stage chains. Stage callbacks receive `(previousResult, originalItem, index)`; failure nulls only that item and skips later stages, while positions remain aligned. `parallel(thunks)` accepts zero-argument thunks, preserves order, waits for the cohort, and inserts `null` for a failed lane. Use `parallel()` only at a mathematically true barrier: global deterministic dedupe/rank/merge, a small local vote requiring all peers, or the final independent verifier panel. Never launch already-started promises. A hung child can hold a barrier because the grounded API had no per-child cancellation; keep barriers small and runtime-homogeneous and resume the unchanged run through `/workflows` controls.

Never make preflight, discovery, mutation, integration, and final verification siblings. Never do global “all builders, then all validators, then all reviewers” waves. Each ready unit advances through its own scoped lifecycle while unrelated units continue. Dependent layer N+1 starts from fresh `main` only after layer N’s PR is actually merged.

Every result consumed by control flow has a schema and explicit null branch. Preserve identity before any filtering:

```js
const raw = await pipeline(ready, unit =>
  runPerUnitPipeline(unit, WORK_RESULT_SCHEMA)
)
const paired = ready.map((unit, index) => ({ unit, raw: raw[index] || null }))
const receipts = paired.map(({ unit, raw }) =>
  raw
    ? decodeAndValidateReceipt(raw, unit.semantic_key)
    : failedReceipt(unit.semantic_key, 'pipeline-returned-null')
)
```

Only after creating explicit rows for every expected identity may non-authoritative optional collections use `.filter(Boolean)`. At every fan-in compare expected and received ID sets: same cardinality, no nulls, duplicates, unexpected IDs, or missing IDs. Open the full contracted artifact before trusting a digest.

Use `phase(title)` only at top-level transitions; set each concurrent child’s `opts.phase` explicitly because concurrent ambient phase changes race. `log()` reports deterministic phase start, work count, null count, budget reserve, repair round, and terminal summary; it is not a data channel and never logs secrets.

Use the live budget surface:

```js
const hasBudget =
  typeof budget.total === 'number' && Number.isFinite(budget.total)
const RESERVE = hasBudget
  ? Math.max(50_000, Math.floor(budget.total * 0.15))
  : Infinity
const MAX_REPAIR_ROUNDS = 3
let priorFingerprint = null
let repeated = 0

for (let round = 0; round < MAX_REPAIR_ROUNDS; round++) {
  if (!hasBudget) {
    log('no explicit budget.total; skipping optional repair expansion')
    break
  }
  if (budget.remaining() <= RESERVE) {
    log(`budget reserve reached before optional repair round ${round + 1}`)
    break
  }
  const open = mechanicallyDeriveFailedRequiredUnitIds()
  if (open.length === 0) break
  const fingerprint = [...open].sort().join('|')
  repeated = fingerprint === priorFingerprint ? repeated + 1 : 0
  if (repeated >= 1) {
    log(`no-progress fingerprint repeated; stopping optional repair at round ${round + 1}`)
    break
  }
  priorFingerprint = fingerprint
  // pipeline(open, scopedRepair, reverify); then replace receipts.
}
```

Run every mandatory unit once regardless of optional-depth budget. Without `budget.total`, `remaining()` may be `Infinity`; never use it as the only loop bound. Optional waves are small because concurrent checks are not atomic reservations. Budget/agent/page/round/timeout exhaustion persists the frontier and returns FAILED, never SUCCESS.

#### Discover, execute, re-scout until code proves dry

Implement this controller logic, adapting names but not semantics:

All calls—including initial/cursor Scouts, contract repairs, dependency/decomposition diagnosis, checkpoints, implement/validate/critic/publisher stages, integration, final verifiers, and synthesizer—must pass through one centralized counted wrapper that increments before launch and refuses call 901. Do not estimate with `ready.length * callsPerUnitUpperBound`; persist actual attempted/completed counts. The reserve computation includes all calls already spent before `Work Loop`.

```js
let round = 0
// `calls` already includes Ground/initial pages/repair/checkpoint attempts.
let dryStreak = 0
const backlog = new Map()
const aliases = new Map()
let pendingLeads = []

// Decode, validate, ingest initial Scout, and exhaust its cursor first.
await checkpointCanonicalLedger('initial', backlog, aliases)
phase('Work Loop')
while (true) {
  normalizeAndIngest(pendingLeads, backlog, aliases)
  pendingLeads = []
  validateAliasesDependenciesAndConflicts(backlog, aliases)

  const ready = selectConflictFreeReady(backlog, remainingWorkerBudget())
  if (ready.length > 0) {
    const raw = await pipeline(ready, unit =>
      runPerUnitPipeline(unit, WORK_RESULT_SCHEMA)
    )
    const paired = ready.map((unit, index) => ({ unit, raw: raw[index] || null }))
    const receipts = paired.map(({ unit, raw }) =>
      raw
        ? decodeAndValidateReceipt(raw, unit.semantic_key)
        : failedReceipt(unit.semantic_key, 'pipeline-returned-null')
    )
    applyReceipts(backlog, receipts)
    pendingLeads.push(...receipts.flatMap(r => r.new_leads || []))
    await checkpointCanonicalLedger(`wave-${round + 1}`, backlog, aliases)
  } else if (hasPendingOrUnresolved(backlog)) {
    const diagnosis = await countedDependencyAndDecompositionDiagnosis(backlog, aliases)
    ingestDiscovery(diagnosis)
    await checkpointCanonicalLedger(`diagnosis-${round + 1}`, backlog, aliases)
  }

  round += 1
  log(`discovery round ${round}: ${ledgerCounts(backlog)}`)
  const delta = await runPaginatedScout({
    mode: 'delta',
    label: `scout:delta:${round}`,
    inspect: 'changed targets, worker leads, unresolved dependencies, failed acceptance, and known authoritative sources',
    ledger: stableCompactLedger(backlog),
  })
  ingestDiscovery(delta)
  if (!candidateDry(backlog, delta)) {
    dryStreak = 0
    continue
  }

  const inversion = await runPaginatedScout({
    mode: 'dod-inversion',
    label: `scout:inversion:${round}`,
    inspect: 'start from raw GOAL+DoD and independently try to falsify every claimed end-state or find an omitted obligation',
    forbidProbeReuseFrom: delta.sourceReceipts,
    ledger: stableCompactLedger(backlog),
  })
  ingestDiscovery(inversion)

  dryStreak =
    scanIsClean(delta) && scanIsClean(inversion) &&
    novelKeyCount(delta) === 0 && novelKeyCount(inversion) === 0 &&
    changedFingerprintCount(delta) === 0 &&
    changedFingerprintCount(inversion) === 0
      ? 2
      : 0

  if (dryStreak >= 2 && dryInvariant(backlog, delta, inversion)) {
    // This is provisional unit-drain only. Integration and final-head changes
    // require a fresh delta + DoD-inversion pair before terminal closure.
    break
  }
  if (!closureBudgetRemains()) return failedWithLedger('discovery-budget-exhausted')
}
```

`dryInvariant()` is code and requires all of:

1. No ready, running, needs-probe, needs-recheck, awaiting-verification, retryable-failed, actionable-blocked, split-needed, conflict-delayed, or unnormalized lead remains.
2. No invalid item, unresolved alias, dangling dependency, duplicate identity, or cycle remains.
3. Every atomic GOAL/DoD obligation is satisfied by fresh closure evidence; mapping to a task is not satisfaction.
4. All pages of both closure scans ended with `has_more:false` and empty cursor.
5. `coverage_gaps` and `unscannable` are empty.
6. Every material source is `ok` or genuinely `not_applicable`; none is denied/error.
7. Every absence detector passed its known-present control.
8. Every expected pipeline identity has a valid terminal receipt; null/schema-invalid results are explicit.
9. Two complete, mechanically different live sweeps—the change/lead/source delta sweep and raw-DoD inversion sweep without detector reuse—found zero new actionable keys and zero changed fingerprints.

Reset dryness on any new key, fingerprint change, open obligation, cursor, invalid output, blocker, failure, `needs_recheck`, awaiting-verification state, or coverage gap. One empty Scout response, an empty ready queue, completion of named examples, or an agent saying “looks complete” is never a stopping rule. Exhausted discovery plus a real external blocker is terminal FAILED with key, evidence, authority, and settling action.

Static tests before launch must cover Scout 0/1/30 items; open obligation plus empty/inaccessible/invalid/paginated Scout cannot succeed; a null middle pipeline result retains later identities; semantic duplicate vs resource conflict; dangling edge/cycle/no-ready diagnosis; new item after one clean sweep resets closure; stale terminal lead vs changed fingerprint; worker-emitted sibling lead enters next wave; budget exhaustion persists backlog; stale `tools/databricks-fanout-harness/` resolves to the live folded location or evidenced absence; unchanged resume reproduces sorted keys and byte-stable prompts. Reject the generated source if it contains a literal execution array of examples, PRs, MCPs, corpus sources, or target paths.

### 4. Make every unit crash-durable and honesty-bound

Use one canonical run tree; do not create competing evidence roots:

```text
<ARTIFACT_ROOT>/campaign.json
<ARTIFACT_ROOT>/controller.json
<ARTIFACT_ROOT>/GROUNDING-PACK.md
<ARTIFACT_ROOT>/MEMORY-DIGEST.md
<ARTIFACT_ROOT>/MEMORY-SYNC.json
<ARTIFACT_ROOT>/discovery/goal-atoms.json
<ARTIFACT_ROOT>/discovery/source-receipts.json
<ARTIFACT_ROOT>/discovery/backlog.json
<ARTIFACT_ROOT>/discovery/events.jsonl
<ARTIFACT_ROOT>/discovery/scans/000-initial.md
<ARTIFACT_ROOT>/discovery/scans/<NNN>-delta.md
<ARTIFACT_ROOT>/discovery/scans/<NNN>-inversion.md
<ARTIFACT_ROOT>/results/<unit-id>.md
<ARTIFACT_ROOT>/results/_state/<unit-id>.json
<ARTIFACT_ROOT>/results/_attempts/<unit-id>/<attempt>.md
<ARTIFACT_ROOT>/results/_attempts/<unit-id>/<attempt>.json
<ARTIFACT_ROOT>/results/_summary.json
<ARTIFACT_ROOT>/verification/contracts/<wu-id>.json
<ARTIFACT_ROOT>/verification/units/<wu-id>.md
<ARTIFACT_ROOT>/verification/claims/<wu-id>.json
<ARTIFACT_ROOT>/verification/critics/<wu-id>-r<round>.json
<ARTIFACT_ROOT>/verification/gates/<wu-id>.json
<ARTIFACT_ROOT>/verification/final-gate.json
<ARTIFACT_ROOT>/commit-journals/<unit-id>.jsonl
<ARTIFACT_ROOT>/commit-reconcile.jsonl
```

Workflow JavaScript cannot write files. Each sequential Scout writes only its scan receipt; each unit writes only its own artifact, sidecar, and per-unit commit journal; a single sequential checkpoint agent atomically rewrites canonical sorted discovery files after intake and every wave. A separate single serialized commit-ledger writer appends validated transitions from those journals to canonical `commit-reconcile.jsonl`, beginning with `PARTIAL` before dispatch and never allowing concurrent shared-file writers. `events.jsonl` and `commit-reconcile.jsonl` are append-only transitions; workers never write shared ledgers. The runner, not the model, creates every unit skeleton before launching a child. A model dying before its first tool call must leave recoverable truth.

Define one identity and one local source of truth. `unit_id` is `u-` plus the full lowercase SHA-256 of the canonical semantic key; `campaign.json` stores the exact bijection `{semantic_key,unit_id}` and rejects any duplicate ID/artifact. The canonical local artifact is `<ARTIFACT_ROOT>/verification/units/<unit-id>.md`; its sidecar, critic, gate, journal, and attempt files use the same `unit_id`. `<ARTIFACT_ROOT>/results/<unit-id>.md` is only a remote/transport staging file. A serialized harvester promotes it to the canonical artifact only after validation, atomic copy, and byte-count/SHA-256 equality, retaining staging provenance; local units write the canonical artifact directly. Every digest/receipt points to the canonical path. `<wu-id>` and `<unit-key-safe-id>` elsewhere mean this exact `unit_id`, never a second namespace.

Use these exact vocabularies everywhere:

- Evidence status: `CONFIRMED | REFUTED | INFERRED | UNVERIFIED | UNKNOWN`.
- `CONFIRMED` is a bounded claim with direct evidence and, when load-bearing, a mechanically different second probe.
- `REFUTED` preserves the earlier wording, records the narrower corrected scope, and names the remaining experiment.
- `INFERRED` is reasoned from cited evidence but not directly proved.
- `UNVERIFIED` appears inline with the affected sentence and has `SETTLE: <specific experiment>`.
- `UNKNOWN` means not yet measured and is mandatory in skeletons.
- Sherman-Kent/WEP likelihood is a separate axis: `almost-certainly-not 1-5% | very-unlikely 5-20% | unlikely 20-45% | roughly-even 45-55% | likely 55-80% | very-likely 80-90% | almost-certain 90-99% | UNKNOWN`. These are not calibrated productivity scores and never select winners/retry budgets.
- Semantic terminal: `SUCCESS | FAILED`; transient/recovery: `RUNNING | UNKNOWN`.
- Diagnostic reason codes: `severed-stream | malformed-artifact | absent-artifact | detector-error | timeout | codex-exit-<n> | schema-invalid | stale-campaign | prompt-hash-mismatch | bundle-hash-mismatch | attempts-exhausted`. Internal `SEVERED|MALFORMED|ABSENT` maps to `FAILED:<id> <reason>` in user-facing output.

Render the following centrally into every contracted unit with real values. Do not rely on global rules to inherit:

```text
FANOUT-CONTRACT:v1
CAMPAIGN_ID: <campaign-id>
UNIT_ID: <unit-id>
LENS_TYPE: <GROUNDED|IDEATION>
ARTIFACT_ROOT: <absolute-root>
ARTIFACT_PATH: <absolute-path>
ARTIFACT_WRITER: python <absolute-artifact-contract.py> checkpoint --artifact <absolute-path> --state-file <absolute-state-json> --milestone <name> --body-file <absolute-draft-file>
ARTIFACT_CHUNK_BYTES_MAX: 8192
PREAMBLE_SHA256: <sha256>
GROUNDING_PACK_SHA256: <sha256-or-NONE>
SUBJECT_KIND: <git-tree|bundle|directory>
SUBJECT_REF: <commit-id|bundle-path|directory-path>
SUBJECT_CONTENT_SHA256: <actual sha256 of canonical subject bytes>
CLAIM_IDS: <comma-separated nonempty ids>
COVERAGE_SECTIONS: <comma-separated nonempty sections>
MILESTONES: <ordered comma-separated milestones>
ARTIFACT_ROOT_LISTING-BEGIN
<frozen pre-launch enumeration of the absolute artifact root>
ARTIFACT_ROOT_LISTING-END

WRITE AS YOU GO:
- The runner has attempted to create the artifact skeleton before launching you. Read it first. If it is absent, create it immediately before any research, probe, edit, or long command.
- Every claim starts as the exact ASCII text `UNKNOWN - not yet measured`.
- Maintain `COVERAGE: measured=[...] ; unmeasured=[...]`.
- Include this exact sentence: `If it still reads this way, the unit died before measuring anything and no verdict here may be cited.`
- Build the complete next body in the declared draft file using file-writing operations of at most 8192 UTF-8 bytes per chunk. Never put the body in a shell literal, heredoc, or here-string. Invoke ARTIFACT_WRITER with path-sized arguments only; it validates, snapshots, flushes/fsyncs, and atomically replaces the artifact.
- At each named milestone, rewrite the whole artifact via ARTIFACT_WRITER. Preserve measured content, correction/refutation history, and all still-unmeasured UNKNOWNs. Never hold a milestone only in model memory.
- A skeleton/checkpoint MUST NOT contain `UNIT-COMPLETE`.

HONESTY:
- Evidence status is exactly CONFIRMED, REFUTED, INFERRED, UNVERIFIED, or UNKNOWN.
- Likelihood is a separate Sherman-Kent band: almost-certainly-not 1-5%, very-unlikely 5-20%, unlikely 20-45%, roughly-even 45-55%, likely 55-80%, very-likely 80-90%, almost-certain 90-99%, or UNKNOWN.
- Attach UNVERIFIED inline to the sentence it qualifies; a limitations section at the end does not count. The same paragraph must say `SETTLE:` and name the experiment. If a recommendation depends on that premise, put `[UNVERIFIED]` in its heading.
- On REFUTED overclaim, preserve the earlier wording, state the narrower measured scope, disclose the residual inline, and name the settling experiment. Correct code does not rescue an overbroad sentence.
- A briefed fact carries probe id, observation timestamp, mechanism, and anchor. To CONFIRM or REFUTE it, use a mechanically different shell, data field, or measurement. Re-running the same probe is not confirmation.
- Before an absence/not-found claim, prove the detector on a known-present control and use a second independent probe.
- GROUNDED claims cite file:line. IDEATION claims cite an external-domain URL and do not treat repository text as evidence for the external proposal.
- Do not vote through conflicting probes. Preserve the disagreement and inspect the specific raw evidence.

EVIDENCE:
- Every terminal artifact, SUCCESS or FAILED, contains an EVIDENCE block with 3-5 file:line or URL anchors. If a pre-probe failure makes that impossible, terminal_status MUST be FAILED and the block must carry `EVIDENCE-EXCEPTION: UNVERIFIED - <why>; SETTLE: <exact recovery experiment>`; such a report is delivery evidence, never a substantive finding.
- Each evidence row names evidence_id, claim_id, observed_at (RFC3339 UTC), probe, mechanism, anchor, and bounded result.
- Mechanically exact comparisons (hashes, bytes, line/set membership, counts) must be done by deterministic code, not LLM judgment.

ADVERSARIAL REVIEW:
- A reviewer receives the siblings' FULL artifacts as labeled read-only evidence paths/attachments after its typed objective, never merely their digests and never as an unlabeled prompt prefix.
- A reviewer writes its own durable write-as-you-go artifact under this contract; review held only in a returned message is unusable.

TERMINAL:
- Close with parsed terminal_status SUCCESS or FAILED, a reason, final coverage, validation data, then exact final line `UNIT-COMPLETE: <unit-id>`.
- The sentinel means closed, not semantically successful.
- Return a <=350-word digest body (400-word hard transport ceiling), correction first. The 3-5-anchor EVIDENCE block is exempt. Preserve every load-bearing UNVERIFIED.
- Final response begins exactly `SUCCESS:<unit-id>` or `FAILED:<unit-id> <reason-code>` and includes artifact path, byte count, SHA-256, and contract version. Never return only a background/status receipt.
```

For a nonliteral path, the unit tail states the access method, for example `exists only on origin/main; read via git show origin/main:<path>`. Freeze the artifact-root enumeration into both prompts and `campaign.json`.

Initial artifact shape, with no sentinel:

````markdown
# Unit <unit-id>

```unit
contract_version: FANOUT-CONTRACT:v1
campaign_id: <campaign-id>
unit_id: <unit-id>
attempt: <n>
prompt_sha256: <sha256>
preamble_sha256: <sha256>
grounding_pack_sha256: <sha256-or-NONE>
subject_kind: <git-tree|bundle|directory>
subject_ref: <commit-id|bundle-path|directory-path>
subject_content_sha256: <actual sha256>
updated_at: <RFC3339 UTC>
last_milestone: SKELETON
terminal_status: RUNNING
terminal_reason: none
```

COVERAGE: measured=[] ; unmeasured=[<all coverage sections>]

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

STATUS: UNKNOWN - not yet measured
CHANGED_PATHS: UNKNOWN - not yet measured
PRIMARY_SIGNAL: UNKNOWN - not yet measured
INDEPENDENT_SIGNAL: UNKNOWN - not yet measured
VALIDATION: UNKNOWN - not yet measured
PLATFORM_ROWS: UNKNOWN - not yet measured
COMMIT_PUSH: UNKNOWN - not yet measured
RESIDUALS: UNKNOWN - not yet measured

## Claims

- <claim-id> [EVIDENCE-STATUS: UNKNOWN] [LIKELIHOOD: UNKNOWN] UNKNOWN - not yet measured
  EVIDENCE: none
  SETTLE: UNKNOWN - not yet designed

## Corrections / refutations

- none yet

## EVIDENCE

- none yet
````

At every milestone build a complete next document, use a same-directory temporary file, flush, `fsync`, `os.replace`, and retain an immutable attempt/milestone snapshot. DBFS FUSE rename/fsync crash semantics were UNVERIFIED; settle with a live kill-between-write-and-replace canary and rely on immutable hashed snapshots until proved. SUCCESS leaves no required field as UNKNOWN; FAILED may retain unknowns but must include explicit failure reason, measured coverage, diagnostics, and available evidence.

Per-unit sidecar:

```json
{
  "contract_version": "FANOUT-CONTRACT:v1",
  "campaign_id": "<campaign-id>",
  "unit_id": "<unit-id>",
  "attempt": 1,
  "state": "RUNNING",
  "reason_code": null,
  "artifact_path": "<absolute-path>",
  "artifact_bytes": "<actual nonzero skeleton byte count>",
  "artifact_sha256": "<actual skeleton sha256>",
  "prompt_sha256": "<sha256>",
  "preamble_sha256": "<sha256>",
  "grounding_pack_sha256": "<sha256-or-NONE>",
  "subject_kind": "<git-tree|bundle|directory>",
  "subject_ref": "<commit-id|bundle-path|directory-path>",
  "subject_content_sha256": "<actual sha256>",
  "last_milestone": "SKELETON",
  "created_at": "<RFC3339 UTC>",
  "updated_at": "<RFC3339 UTC>",
  "codex_exit_code": null,
  "validation": {"state": "PENDING", "errors": []},
  "evidence_anchors": 0,
  "unverified_count": 0,
  "coverage_unmeasured": ["<section>"]
}
```

Sidecar `state` is `RUNNING|SUCCESS|FAILED|UNKNOWN`; `validation.state` is `PENDING|PASS|FAIL|DETECTOR_ERROR`. Rewrite it after skeleton, process launch, worker return, validation, and terminalization. Before retry overwrite, snapshot the artifact and receipt under `_attempts`.

Create immutable `campaign.json` before upload with campaign ID/version, expected IDs, per-unit prompt hashes, preamble/pack hashes, subject kind/ref/content hash, lane contracts, frozen root listing, result root, batch hash, and creation time. Mutable `controller.json` holds Databricks run IDs, active run, submission/readback receipts, attempts, and last poll. Both are atomic. The worker main thread—not 48 worker threads—rewrites reconstructable `_summary.json` after each future; sidecars are authoritative after a crash.

#### Canonical completion predicate and hardening work

At the grounded commit, `.agents/skills/codex-databricks-fanout/` was canonical and `skills/codex-databricks-fanout/` its required byte-identical mirror. `tools/databricks-fanout-harness/` and `docs/CSIE-DESIGN.md` did not exist. Re-resolve live; do not fabricate stale paths. `contract.py`, `gate.py`, `poll.py`, and `batch_runner.py` disagreed on floors, tail identity, field parsing, and process-exit precedence. Treat that drift as an open prerequisite if this run depends on the rail; do not claim one canonical predicate until reconciled.

Make `scripts/harness/gate.py` the sole structural/content validator and route worker, `contract.and_gate_artifact`, `poll.py`, `harvest.py`, and `harvest_cli.py` through it. Grounded `gate.py` deliberately defaulted `min_bytes=0` because a global 800-byte floor rejected 84 of 85 valid terse artifacts, while `contract.py/poll.py`, `batch_runner.py`, and one `SKILL.md` section enforced/stated 1024/1 KiB. Remove the worker’s private character-tail/bare-sentinel test and global 1024-byte rule; a byte floor is allowed only as an explicit justified lane setting. During rollout, produce >1024 bytes (prompts request >=1200) so old notebook and new host gates both pass, but do not preserve that compatibility floor as semantic truth.

A terminal SUCCESS is usable only when all pass:

1. Databricks lifecycle is terminal or the worker independently produced a closed receipt.
2. Declared path is a regular nonempty file.
3. Exact final nonblank line is `UNIT-COMPLETE: <unit-id>`.
4. Parsed `unit` block matches campaign/unit/prompt/preamble/grounding hashes and subject kind/ref/content hash.
5. `terminal_status` is `SUCCESS`.
6. Lane fields come from their fenced block, not document-wide substring search, and semantic values pass (`suite_status:red` or `branch_pushed:none` cannot pass; runnability requires `suite_status:green` and `push_probe:ok`).
7. Required claims/coverage exist and no required SUCCESS value remains the skeleton string.
8. Evidence statuses and likelihood bands are valid enums.
9. Each UNVERIFIED paragraph has adjacent `SETTLE:` and dependent recommendation headings are `[UNVERIFIED]`.
10. Each load-bearing CONFIRMED claim cites distinct evidence records whose mechanisms differ; absence includes a positive control.
11. Ordinary SUCCESS/FAILED reports contain 3–5 appropriate anchors, digest body <=350 words (transport <=400), and correction/refutation history has not vanished. Pre-probe FAILED may use EVIDENCE-EXCEPTION but supplies no substantive finding.
12. Recomputed post-harvest SHA-256 and bytes equal the receipt.

A closed `terminal_status:FAILED` passes delivery validation but remains semantic FAILED. Skeleton/checkpoint is severed/recoverable. Unreadable or failed detector is UNKNOWN, not ABSENT. Once an artifact is structurally valid, parsed semantic status outranks Codex exit; retain nonzero exit as diagnostics. Exit zero without valid closure is `FAILED:<id> severed-stream`.

If these hardening files are absent or stale and the goal needs this durability, create a prerequisite structural unit. Canonical-first then byte-identical mirror:

```text
ADD scripts/harness/artifact_contract.py
  exact vocab/versioned preamble; instrument_prompt; skeleton/checkpoint/snapshot;
  duplicate-key rejecting fenced parser; typed honesty/lane validation;
  receipt/hash builder; checkpoint CLI accepting only path-sized arguments.
ADD scripts/harness/recovery.py
  atomic campaign/controller state; run attach; expected-ID census;
  SUCCESS|FAILED|SALVAGE|REQUEUE|UNKNOWN planning; bounded attempts/snapshots.
ADD scripts/harness/memory_digest.py
  deterministic correction-first digest; failure/caveat preservation;
  secret redaction; canonical projection hash; MEMORY-SYNC writer.
MODIFY scripts/harness/contract.py
  Unit gets nonempty claim_ids, coverage_sections, milestones, required_fields,
  optional justified min_bytes, max_attempts; use canonical parser.
MODIFY scripts/harness/build_batch.py
  preserve metadata; freeze campaign/prompt/preamble/grounding/subject/batch hashes;
  atomically write immutable manifest; instrument every prompt.
MODIFY scripts/batch_runner.py
  prewrite skeleton/state before pool; record transitions; preserve diagnostics;
  artifact outcome outranks process exit; main thread updates summary per future.
MODIFY scripts/harness/gate.py, poll.py, harvest.py, harvest_cli.py
  one validator; expected ID set; fail closed on fs ls/cat errors; named ABSENT;
  atomic local replacement.
MODIFY scripts/harness/lanes/run_E.py
  recover/attach before submit; persist/read back run ID; resume incomplete IDs only.
MODIFY scripts/harness/lanes/coverage.py and preflight_units.py
  lane claims/coverage/milestones/semantic validators; central honesty vocabulary.
MODIFY scripts/e2e/watch.py, run_fanout.py, run_runnability.py, smoke_2unit.py
  full receipt predicate; exact SUCCESS:<campaign> or FAILED:<campaign> <reason>.
MODIFY SKILL.md and scripts/README.md
  campaign-bound structural completion/recovery; remove stale global 1 KiB definition.
```

Update canonical/mirrored workflow-authoring templates with the skeleton/rewrite/terminal block. Use exactly:

```js
fanoutSchema({
  narrative: 'receipt_markdown',
  optional: {
    state: ['SUCCESS', 'FAILED'],
    artifact_path: 'string',
    contract_version: 'string',
  },
})
```

Only `receipt_markdown` is required and the generated outer schema remains open (`additionalProperties:true`). Add only this inject-only hook entry to the existing PreToolUse dispatcher—no extra always-on process:

```json
{
  "name": "fanout-contract/spawn-lint",
  "script": "fanout-contract/check.py",
  "args": ["spawn"],
  "timeout": 8,
  "matcher": "Task|Workflow",
  "isolate": null,
  "side_effect": "none",
  "emits": true
}
```

The linter parses contracted fan-out and checks contract version, root/path, nonempty claim/coverage/milestone lists, vocabularies, hashes, and death sentence. It emits one diagnostic and never exit-2 blocks nondangerous work. Extend `hooks/bg-registry/register.py` to record structured contract ID/path/hashes; `done_marker.py` records synchronous `process_ended`, not `done`; only a canonical valid receipt records `contract_complete`. Hooks may fail open, but detector failure never becomes completion.

Recovery runs before every fresh submit:

1. Load campaign/controller; corrupt/mixed hashes are UNKNOWN/stale, never guessed.
2. Attach to a saved nonterminal run instead of submitting another.
3. Persist a returned run ID locally and to DBFS immediately after submit, then read it back once. Upload/mkdir/readback failure aborts submission; never let an old remote `batch.json` run.
4. At terminal lifecycle, enumerate expected IDs and fetch via `databricks fs cat`, checking return codes. DBFS-to-local `fs cp` is forbidden.
5. Validate every artifact/sidecar independently against campaign hashes.
6. Exact closed SUCCESS: skip forever. Exact closed FAILED: retain and retry only if retryable with attempts left. Partial/invalid with real content: SALVAGE after snapshot and continue only unmeasured coverage. Healthy terminal listing plus healthy missing-file probe: REQUEUE. Detector error/nonterminal: UNKNOWN/attach, never duplicate.
7. Retry only incomplete IDs in a generation-scoped result root; never reuse `/dbfs/tmp/E-coverage/results` without campaign/hash binding.
8. Maximum three attempts; each retry includes prior reason and changes tactic/scope. At exhaustion retain a closed FAILED `attempts-exhausted`.
9. Databricks state plus artifact content are independent remote liveness/delivery signals; local PID/bg-registry is not.

Changing contract/preamble after launch requires archiving partials under an aborted campaign and starting a new campaign/version. Never mix prompt versions or destroy the only partial.

`hooks/bg-registry/reconcile_requeue.py` was explicitly an unwired pure decision core at grounding, not live recovery. Source presence or a unit test for that core does not prove any controller calls it.

Required durability tests:

```text
scripts/tests/test_artifact_contract.py:
  skeleton-before-fake-exec; all claims/sections UNKNOWN; death sentence; no sentinel;
  interrupted replace retains prior checkpoint; SUCCESS/FAILED close separately;
  invalid enum, duplicate fenced key, prose decoy, wrong ID/hash, misplaced sentinel fail;
  UNVERIFIED without SETTLE fails; same-mechanism load-bearing CONFIRMED fails;
  REFUTED wording cannot disappear.
scripts/tests/test_recovery.py:
  kill a ten-unit cohort with complete/partial/absent/unreadable states; restart;
  complete skipped, partial salvaged, absent requeued once, detector errors not requeued;
  saved nonterminal attaches; upload/run-ID failure prevents resubmit;
  campaign/prompt/bundle mismatch rejects stale same-ID; snapshots/caps survive.
scripts/tests/test_memory_digest.py:
  failures/corrections/UNVERIFIED cannot drop; no workload SUCCESS before all validate;
  no campaign SUCCESS before matching memory sidecar; stable projection hash;
  receipts change only sidecar; secret fixtures redact; same receipts are idempotent.
Extend test_contract.py, test_gate.py, test_poll.py, test_harvest.py,
test_coverage.py, and test_preflight_units.py.
hooks/fanout-contract/test_check.py:
  broken fires; minimal fixed silent; quoted prose without parsed fields does not pass.
Mutation tests:
  red if skeleton gains sentinel, one byte completes, probe independence is removed,
  refutation disappears, UNKNOWN is dead, complete unit requeues, failed unit vanishes
  from memory, or process exit overrides valid artifact.
```

Validation:

```bash
cd .agents/skills/codex-databricks-fanout/scripts
python -m pytest tests -q
python -m pytest tests --cov=harness --cov-branch --cov-fail-under=100
cd ../../../..
python hooks/fanout-contract/test_check.py
git diff --no-index -- .agents/skills/codex-databricks-fanout skills/codex-databricks-fanout
```

Unit tests are not a live DBFS durability proof. A billable live smoke, only when authorized/in-scope, must show skeleton before output, one killed partial recovered, completed sibling not rerun, nonzero-exit valid artifact classified by artifact, and campaign summary/memory digest read back.

### 5. Per-unit execution, second signal, critic, and proof packet

For each mutating unit, the lifecycle is:

```text
CONTRACT -> persistent isolated worktree -> IMPLEMENT (no publish)
-> controller-owned VALIDATE -> independent POSTCONDITION
-> fresh adversarial CRITIC -> Claude PUBLISHER scoped COMMIT/PUSH
-> PR/exact-head CI/review -> squash MERGE -> verified CLEANUP
-> post-publish exact-SHA recheck -> artifact close -> receipt/new leads
```

Independent units pipeline immediately; do not wait for slow siblings. For each mutating unit, a serialized Claude workspace manager pre-creates one exact persistent worktree/branch from the frozen current `origin/main`, records it in the ledger, and retains it until verified cleanup. Every file-mutating implementation/repair/publisher agent still carries `isolation:'worktree'` as a native defense but is explicitly told that the recorded persistent worktree is the only authoritative target; the native temporary worktree is never used as a handoff. Each has the same exclusive allowlist. The implementer edits/tests and checkpoints but cannot commit/push. Separate fresh controller-owned read-only agents validate the candidate bytes, execute the mechanically independent postcondition, and perform adversarial review against that exact worktree/content hash. Only if all three PASS may the Claude publisher return to the same persistent worktree, mechanically recheck the allowlist/hash, commit/push/shepherd/merge/cleanup. A final read-only stage verifies exact remote/main state and QZP, then a serialized artifact finalizer closes the unit. Read-only scouts/reviewers omit native worktree overhead.

If a native runtime cannot safely let an isolated leaf address an explicit persistent worktree, do not fall back to dirty-state handoff. Use a single Claude leaf that remains alive through implementation and internally launches fresh read-only Task validators/critic before its publisher step, record this runtime limitation, and retain the outer post-publish verifier. Never publish before independent validation merely to accommodate agent isolation.

Root `AGENTS.md` forbids Codex git writes. Codex may do read-only review/research or edit/validate in the deliberately pre-created persistent worktree, but Claude/control-plane performs fetch, branch, checkout, commit, push, merge, rebase/cherry-pick, tag, stash, and cleanup. Do not hand off uncommitted Codex work through a native auto-removed worktree: measured `WorktreeRemove` force-removes and swallows errors. Prefer Claude for mutating units; otherwise retain the exact persistent Codex worktree until Claude publishes it.

Freeze before spawn: `wu_id`, verbatim requirement, dependencies, disjoint allowlist, atomic DoD rows; exact primary and mechanically independent probe for each load-bearing row; known-present detector control and known-broken/known-good enforcement controls; absolute artifact, required fields, platform rows, critic path, sentinel; source SHA and target branch. If the contract is wrong, stop that cohort, retain partials, revise once, and restart—never split-brain live children.

Orchestrator-built gate packet:

```json
{
  "wu_id": "WU-...",
  "requirement": "one atomic requirement",
  "source_sha": "40-hex",
  "unit_commit_sha": "40-hex or null",
  "pushed_ref": "refs/heads/... or null",
  "changed_paths": ["repo/relative/path"],
  "dod": [
    {
      "id": "DOD-01",
      "claim": "one independently checkable postcondition",
      "primary_probe": {
        "tool": "...",
        "engine": "...",
        "shell": "...",
        "field": "...",
        "command": "exact command",
        "exit_code": 0,
        "evidence": ["path:line or immutable URL/run URL"]
      },
      "independent_probe": {
        "tool": "...",
        "engine": "...",
        "shell": "...",
        "field": "...",
        "command": "exact command",
        "exit_code": 0,
        "evidence": ["path:line or immutable URL/run URL"]
      },
      "detector_controls": {
        "known_present_found": true,
        "known_broken_fired": true,
        "known_good_passed": true
      },
      "verdict": "CONFIRMED|REFUTED|UNVERIFIED",
      "scope": "the exact surface measured",
      "settling_experiment": "required when UNVERIFIED",
      "revised_text": "required when REFUTED"
    }
  ],
  "local_gate": {
    "commands": [],
    "pass_fail_skip_counts": "read from final summary, not inferred",
    "committed_blob_or_sha": "what bytes were tested"
  },
  "platform_gate": [],
  "remote_quality": {
    "run_id": null,
    "url": null,
    "head_sha": null,
    "baseline_seven_job_conclusions": [],
    "additional_required_contexts": {},
    "all_live_required_contexts_pass": false
  },
  "critic": {
    "artifact": "verification/critics/<wu-id>-rN.json",
    "round": 1,
    "verdict": "PASS|FAIL"
  },
  "final_verdict": "CONFIRMED|PLAUSIBLE|FAILED|UNKNOWN",
  "residual_unverified": []
}
```

Worker transport must carry `wu_id`, exact terminal receipt, artifact, changed paths, commands, open risks, and new leads. Cross-vendor failures use `severed-stream`, `codex-exit-<n>`, `win-arg-limit`, `timeout-<n>s`, or `schema-invalid` plus diagnostic tail. For noninteractive Codex, dispatch synchronously through file/stdin with `--ignore-user-config`; require exit zero plus nonempty parsed `--output-last-message` validating caller schema. Active MCP can void Codex typed output; disable MCP for that call or validate/repair on a Claude schema-bearing leaf. Never parse progress/stderr as the result.

Two signals differ in at least one of tool, engine, shell, or measured field. A second agent reading the same source or repeated polling is not independent:

| Surface | Signal A | Mechanically different Signal B |
|---|---|---|
| Code behavior | Targeted unit/integration test on final bytes | Held-out runtime/e2e/golden journey through real entry point |
| Regression | Green with fix | Revert/mutate bug to red, restore to green |
| Hook | Manifest/dispatcher registration and source/live parity | Controlled safe event receipt; known-broken fixture fires |
| MCP/config | Canonical user config parses and enumerates server | Fresh session exposes tool and disabled servers do not spawn, measured by another field |
| Auth/integration | Identity/whoami | Real non-mutating domain read; empty alternate profile is not auth proof |
| Export/corpus | Source IDs/count/time bounds | Destination manifest, hashes/count reconciliation, deterministic samples |
| Git push | Local SHA and clean scoped status | Remote ref/GitHub head OID equals SHA |
| PR merge | GitHub `state=MERGED` plus merge commit | Merge commit/patch reachable from current `origin/main` |
| Deploy | Source/deployed manifest parity | Actual consumer load and behavioral event |
| Memory | Durable note readback | Concrete SHAs/paths/status reconcile live |
| Databricks/auth | `current-user` | Cluster/job/API listing or harmless live job |

For world/status/audit claims run:

```bash
python .agents/skills/claim-verify-gate/scripts/claim_gate.py --self-test
python .agents/skills/claim-verify-gate/scripts/claim_gate.py \
  --claims <artifact-root>/verification/claims/<wu-id>.json \
  --doc <artifact-root>/verification/units/<wu-id>.md \
  --format json
```

Exit 0 is structurally allowed, 1 violations, 2 unusable input; it does not decide truth and is not a test runner.

Fresh critic receives original request, contract/DoD rows, full diff, raw command output, platform evidence, and full artifact—but not implementer self-assessment or old critic findings. Exact payload:

```json
{
  "wu_id": "WU-...",
  "round": 1,
  "verdict": "PASS|FAIL",
  "dod_results": [
    {
      "dod_id": "DOD-01",
      "result": "PASS|FAIL",
      "finding_verdict": "CONFIRMED|PLAUSIBLE",
      "implementation_evidence": ["path:line"],
      "test_or_runtime_evidence": ["command summary/run URL/path:line"],
      "attempted_falsification": "what was tried",
      "blocking": false,
      "reason": "..."
    }
  ],
  "key_assumptions": [
    {"assumption": "...", "impact": "HIGH|MEDIUM|LOW", "confidence": "high|medium|low"}
  ],
  "strongest_evidence_against": "required; 'none found' only after a stated search",
  "overclaims": [],
  "residual_unverified": [
    {"claim": "...", "scope": "...", "settling_experiment": "..."}
  ],
  "receipt": "SUCCESS:<wu-id>-critic PASS|FAILED:<wu-id>-critic <reason>"
}
```

Critic checks each DoD row, scope allowlist, dead/skipped/mock-only tests, fail-open greens, security boundaries, platform coverage, exclusions/suppressions, exact tested blob, and prose width. Any blocker causes remediation, complete validation rerun, and a wholly fresh critic; rerun every review facet because a fix may add a failure. Maximum three rounds, then mark unit FAILED with history and continue independent authorized units. Critic PASS is advisory—not the second mechanical signal and not merge authority.

Status layers stay distinct: critic finding `CONFIRMED|PLAUSIBLE`; atomic claim `CONFIRMED|REFUTED|UNVERIFIED`; unit assessment `CONFIRMED|PLAUSIBLE|FAILED|UNKNOWN`; Databricks poll `RUNNING|DONE|FAILED|UNKNOWN`; verifier `PASS|FAIL|UNVERIFIED`; ledger `done|already_satisfied|blocked|failed|needs_recheck`. `BLOCKED` and `PARTIAL` are internal nonterminal planning/ledger states only. Every external producer transport terminates exactly `SUCCESS:<id>` or `FAILED:<id> <reason>`; a blocked/partial attempt maps to FAILED with preserved reason/state and can be retried, never emitted as a third terminal status. Map layers in code. `PLAUSIBLE`, missing platform/CI, auth-inaccessible, skip, stale SHA, pending, UNKNOWN, or UNVERIFIED cannot support SUCCESS.

Impact matrix; `N/A` requires a changed-path reason, unavailable/skip is not PASS:

| Changed surface | Mandatory proof |
|---|---|
| Any code/config/docs | Impacted local validation on final committed blob/SHA plus all exact-head remote quality jobs |
| Portable Python/Node | Ubuntu CI at Python 3.11/Node 22; actual patch versions from logs; Windows smoke when deployed there |
| `.sh`/shell emitter | `*.sh eol=lf`; real Linux or `wsl.exe bash -n`; Git Bash alone invalid |
| `.ps1`, `.cmd`, registry/process/Windows config | Windows 11 + PowerShell 7 parser/unit/live smoke; `.cmd` through real `cmd.exe` |
| Git Bash/MSYS rewrite | Actual Windows Git Bash/MSYS oracle fixtures not skipped plus Linux pure-policy/emission tests |
| MCP `.mjs`/Python | Unit tests plus real initialize/tools-list/nonmutating call on owning Windows host |
| Electron/desktop | Linux unit plus Windows package/app smoke; macOS remains PLAUSIBLE unless run |
| Browser rail | Pure-logic CI plus live browser round trip |
| Databricks driver/notebook | CI unit plus live configured workspace round trip; run URL/ID and bounded cost |
| Docs-only | Content/path/link/command consistency; full unfiltered remote quality after PR |

On Windows verify LF committed bytes, not only a CRLF working tree:

```bash
git show <final-sha>:<path>          # NOT git archive: it applies export-time EOL
                                     # conversion and returns CRLF on Windows, i.e. the
                                     # opposite of the stored blob. git cat-file -p is
                                     # equivalent; both measured 0 CRLF against a
                                     # working tree carrying 2,898.
```

The grounded `.gitattributes` declared `*.sh eol=lf` and `*.ps1 eol=crlf`.

### 6. Isolate, publish, shepherd, reconcile, and clean every repository unit

The following dated census is a stale lead only when the filled GOAL/DoD or live discovery makes PR/branch reconciliation, stale-work cleanup, or those exact refs relevant. For an unrelated future goal, do not turn it into work and do not perform a repository-wide branch cleanup; classify it not applicable without probing unrelated scope. When relevant, re-probe every fact. At grounding commit `a919578f2cdf107ac8f049ae5a97459e25b83440`, PRs `#103`, `#104`, `#159`, `#169`, `#170`, `#178`, `#179`, and `#180` were MERGED; `#177` was the only open PR at `ace747b14cef87254725955e78b9184e3207fa20`, mergeable/CLEAN with 12 visible successful checks and no REST review/comments. Forty merged-PR heads remained. Five no-PR heads were strict main ancestors and only cleanup candidates after local worktree/stash checks:

```text
feat/fb-reels-uploader-tool
feat/research-harness-m16
feat/social-hub-mcp
fix/stub-ledger-false-positive
harness/upgrade-2026-07-17
```

Three heads had non-main-reachable content and must be reconciled, never deleted on that stale fact:

```text
add-databricks-fanout-harness           be2c996  ahead 1, no PR
fix/ssh-platform-cleanup-20260720       bf4eb2a  ahead 1 / behind 8, no PR
feat/monitorcore-codexsource            b3127f1  ahead 2 / behind 123, closed-unmerged PR #83
```

Prove content/patch equivalence to a merged replacement or salvage unique content through a focused PR. Do not reopen/redo an actually merged PR. Re-poll exact-head CI and GraphQL threads before merging any currently open authorized green PR.

Set the worktree hook target before dispatch because the tracked `hooks/worktree-target.txt` was stale and pointed at `C:\Users\Prekzursil\Documents\GitHub\Reframe`:

```powershell
$Toolchain = 'C:\Users\Prekzursil\source\agent-skills-toolchain'
$ResolvedToolchain = (Resolve-Path -LiteralPath $Toolchain).Path
git -C $ResolvedToolchain rev-parse --is-inside-work-tree
$Hint = Join-Path $HOME '.claude\hooks\worktree-target.txt'
Set-Content -LiteralPath $Hint -Value $ResolvedToolchain -NoNewline
Get-Content -LiteralPath $Hint -Raw
```

Use external `~/.claude/agent-worktrees`, not project-local `.worktrees/` or `worktrees/` (neither was ignored). Do not run the worktree installer: `hooks/create-worktree.ps1` had rules-vault wiring missing from `scripts/worktree-isolation/create-worktree.ps1`. Fetch once at a dependency barrier, then branch explicitly from `origin/main`; never ambient `HEAD`, same-name force removal, or vague `fresh`:

```bash
git fetch --no-tags --prune origin main

BRANCH="<feat|fix|chore|refactor|docs|test|ci>/<unit-id>-<kebab-slug>"
WT="$HOME/.claude/agent-worktrees/<globally-unique-run-and-unit-id>"

git check-ref-format --branch "$BRANCH"
git show-ref --verify --quiet "refs/heads/$BRANCH" && exit 20
git ls-remote --exit-code --heads origin "refs/heads/$BRANCH" && exit 21

git worktree add --detach "$WT" origin/main
git -C "$WT" switch -c "$BRANCH" origin/main
test "$(git -C "$WT" rev-parse HEAD)" = "$(git rev-parse origin/main)"
test "$(git -C "$WT" branch --show-current)" = "$BRANCH"
test -z "$(git -C "$WT" status --porcelain)"
```

If a branch exists, resume only when the durable ledger proves it belongs to this exact unit; otherwise choose a new name.

Only the Claude publisher commits after scoped validation and fresh critic PASS. Conventional subject is `<type>(<optional-scope>): <short imperative description>` where type is `feat|fix|refactor|docs|test|chore|perf|ci`. Omit `Co-Authored-By`; root policy disables AI attribution. Write the commit message outside the repo, for example `$HOME/AppData/Local/Temp/<run>-<unit>-commit.txt`:

```text
<type>(<scope>): <imperative summary>

Work unit: <unit-id>
Declared paths: <exact path list>
Validation: <receipt/artifact identifiers>
Adversarial review: PASS (<artifact>)
Reconciles: <source SHAs or "none">
```

Scope includes untracked files and is checked mechanically:

```bash
git -C "$WT" status --porcelain=v2 --branch
git -C "$WT" diff --name-status
git -C "$WT" ls-files --others --exclude-standard
git -C "$WT" diff --check

# Compare the union above to the exact allowlist. Unexpected path = gate failure.
git -C "$WT" add -- path/one path/two path/to/test
git -C "$WT" diff --cached --name-status
git -C "$WT" diff --cached --stat
git -C "$WT" diff --cached --check
git -C "$WT" commit -F "$COMMIT_MESSAGE_FILE"

git -C "$WT" diff --name-status origin/main...HEAD
git -C "$WT" diff --stat origin/main...HEAD
git -C "$WT" status --porcelain=v2 --branch
git -C "$WT" push -u origin HEAD
```

Hard bans: `git add -A`, `git add .`, `--no-verify`, direct push to `main`, any force push including `--force-with-lease`, broad reset/clean, blanket `ours`/`theirs`, and amending/rewriting a pushed branch. The checked-in PR-shepherd `git add -A` and vendored rebase/force recipe are overridden. To update a published branch:

```bash
git -C "$WT" fetch --no-tags origin main
git -C "$WT" merge --no-edit origin/main
# Resolve conflicts path-by-path, preserve both intents, stage only named paths.
# Rerun all affected validation and a fresh critic before pushing.
git -C "$WT" push
```

After each push require two ref signals and clean state:

```bash
CURRENT_BRANCH=$(git -C "$WT" branch --show-current)
LOCAL_SHA=$(git -C "$WT" rev-parse HEAD)
UPSTREAM_SHA=$(git -C "$WT" rev-parse '@{u}')
REMOTE_SHA=$(git ls-remote --heads origin "refs/heads/$CURRENT_BRANCH" | awk '{print $1}')
test "$LOCAL_SHA" = "$UPSTREAM_SHA"
test "$LOCAL_SHA" = "$REMOTE_SHA"
test -z "$(git -C "$WT" status --porcelain)"
```

A feature-branch push is not integration and does not trigger this repo’s `quality.yml`; create the PR immediately. Run all GitHub CLI reads/writes from Git Bash with `env -u GH_TOKEN` because a bad ambient `GH_TOKEN` can shadow the keyring PAT:

```bash
OWNER=Prekzursil
NAME=agent-skills-toolchain
REPO="$OWNER/$NAME"

env -u GH_TOKEN gh pr create \
  --repo "$REPO" \
  --base main \
  --head "$BRANCH" \
  --title "<same conventional subject>" \
  --body-file "$PR_BODY_FILE"
```

Exact body sections:

```markdown
## Intent and scope
- Work unit and why it exists
- Exact owned/changed paths

## Reconciliation
- Base SHA
- Source SHAs adopted, if any
- Pairwise overlaps and resolution
- Capabilities retained from each side; no silent drops

## Verification
- Local commands and exit-code receipts
- Coverage/both-state receipt where applicable
- Fresh adversarial review artifact

## Risk and rollback
- Blast radius
- Reversible rollback

## Deferred work
- Linked issue only when genuinely outside this PR; never a hiding place for a review blocker
```

Own each PR through actual merge. Poll about every 60 seconds, always binding green to current head:

```bash
env -u GH_TOKEN gh pr view "$PR_NUMBER" --repo "$REPO" \
  --json number,state,isDraft,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,mergedAt,mergeCommit

env -u GH_TOKEN gh run list --repo "$REPO" --workflow quality.yml \
  --branch "$BRANCH" --limit 20 \
  --json databaseId,headSha,event,status,conclusion,url,createdAt

env -u GH_TOKEN gh pr checks "$PR_NUMBER" --repo "$REPO" --watch --interval 60
```

#### QZP six-gate / seven-job contract

Re-read `.github/workflows/quality.yml` at the final head; executable steps outrank prose/charters. Grounded triggers were push to `main`, PR to `main`, and manual dispatch—feature branch push alone does not run it. Six charter slugs yielded seven independent Ubuntu jobs because tests/coverage split:

1. `gate-lint-format (ruff)`
2. `gate-types (basedpyright)`
3. `gate-tests-coverage (node workspaces)`
4. `gate-tests-coverage (python packages)`
5. `gate-sast (opengrep)`
6. `gate-secrets (gitleaks)`
7. `gate-deps (osv-scanner)`

No aggregate job, OS matrix, or dependency chain existed. Require every live required/structural context, not a hardcoded count; especially `gate-no-runtime-junk` and `gate-skill-dual-write` when applicable. A failed early step means later sequential steps in that job did not run; only a green job proves all its steps. A canceled/old/other-SHA run is no evidence.

Exact grounded primary commands/pins:

```bash
# Gate 1, Python 3.11, repo root
python -m pip install --upgrade pip
pip install ruff==0.15.17
ruff check --output-format=github .
ruff format --check .
bash .quality/charter_check.sh
diff -r --exclude=__pycache__ tools/monitorcore/monitorcore \
  skills/workflow-monitor/monitorcore

# Gate 2
pip install basedpyright==1.39.8
(cd tools/mcp-manager && pip install -e ".[dev]" && basedpyright core ui app.py)
(cd tools/scholarly-access-mcp && pip install -e . && basedpyright scholarly_access)
(cd tools/taskwatch_monitor && pip install -e ".[dev]" && \
  basedpyright core probes cli mcp_server hooks ui)
(cd tools/monitorcore && pip install -e ".[dev]" && basedpyright monitorcore)
# agent-self/harness uses an ephemeral standard-mode pyrightconfig from quality.yml.

# Gate 3, Node 22
npm ci
npm test
# The agentify-desktop lane was removed from quality.yml on 2026-08-09 (tree deleted).

# Strict Python line+branch lanes (run affected lane locally; CI runs all)
(cd tools/mcp-manager && pip install -e ".[dev]" && \
  pytest --cov=. --cov-branch --cov-report=term-missing --cov-fail-under=100)
(cd tools/scholarly-access-mcp && pip install -e . pytest pytest-cov && \
  pytest --cov=scholarly_access --cov-branch --cov-report=term-missing --cov-fail-under=100)
(cd tools/taskwatch_monitor && pip install -e ".[dev]" && \
  pytest --cov=. --cov-branch --cov-report=term-missing --cov-fail-under=100)
(cd tools/monitorcore && pip install -e ".[dev]" && \
  pytest --cov=monitorcore --cov-branch --cov-report=term-missing --cov-fail-under=100)
(cd tools/stdin-server && pip install pytest pytest-cov && \
  pytest --cov=stdin_server --cov-branch --cov-report=term-missing --cov-fail-under=100)
(cd tools/search-expansion && pip install pytest pytest-cov pyyaml && \
  pytest --cov=rank_fusion --cov=searxng_config --cov=query_plan --cov-branch \
  --cov-report=term-missing --cov-fail-under=100)

# Gate 4 / SAST; CI installs opengrep 1.23.0
opengrep scan --config .quality/opengrep --error \
  --exclude node_modules --exclude .venv --exclude vendor \
  --exclude dist --exclude out --exclude build .
```

Secrets uses full history and:

```text
gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7
GITLEAKS_VERSION=8.30.1
.gitleaks.toml
artifact upload disabled
```

Dependencies uses:

```text
google/osv-scanner-action/osv-scanner-action@9bb69575e74019c2ad085a1860787043adf47ccb
v2.2.4
```

with exactly:

```yaml
scan-args: |-
  --lockfile=package-lock.json
```

(The second `--lockfile=tools/web/agentify-desktop/package-lock.json` argument was removed
on 2026-08-09 together with the tree that owned that lockfile.)

The Python job also names harness regression/coverage (measured, no 100% floor), triage-router, cmd-rewrite, hook-manifest, adversarial-corpus, manifest-provenance, hookrun, closed-batch, repomap, claim-gate self/mutation, fanout-schema production lint, hook conformance, browser-rail pure logic, and:

```bash
python -m pytest skills/codex-databricks-fanout/scripts/tests -q
```

When adding tests, prove CI invokes them; existence is not execution. `/quality-gate` is a generic format/lint/type helper, not QZP.

Capture exact remote run:

```bash
env -u GH_TOKEN gh run list \
  --repo Prekzursil/agent-skills-toolchain \
  --workflow quality.yml --branch <branch> --limit 20 \
  --json databaseId,headSha,status,conclusion,url,event

env -u GH_TOKEN gh run view <run-id> \
  --repo Prekzursil/agent-skills-toolchain \
  --json headSha,status,conclusion,jobs,url

env -u GH_TOKEN gh pr view <pr-number> \
  --repo Prekzursil/agent-skills-toolchain \
  --json headRefOid,mergeStateStatus,statusCheckRollup,url
```

Compare `headSha`, `headRefOid`, and final pushed SHA byte-for-byte. If several units share integration, prove ancestry:

```bash
git status --porcelain=v2 --branch
git diff --name-only <unit-base-sha>...<unit-head-sha>
git rev-parse HEAD
git merge-base --is-ancestor <unit-commit-sha> <green-integration-sha>
git ls-remote origin refs/heads/<branch>
git worktree list --porcelain
git for-each-ref --format='%(refname) %(objectname) %(upstream:short) %(upstream:track)' \
  refs/heads refs/remotes/origin
```

Authentication failure is detector failure, not red/no CI; use another authenticated GitHub API path and retain UNKNOWN until measured. `mergeStateStatus:BLOCKED` is not a diagnosis. In-scope failure: fix same branch, regression/both-state proof, complete revalidation/fresh critic, commit/push, restart exact-head loop. Structural/external failure follows this closed table:

| Finding | Disposition |
|---|---|
| Unit’s own in-scope fix | Same isolated branch/PR; regression proof; full affected validation |
| Architecture/shared interface/auth/security/MCP-hook-rule/CI charter/schema-public API/dependency lock/generated projection/deletion-rename/multi-workstream behavior | Separate focused structural PR with before/after, retained capability/fallback, blast radius, rollback, tests; merge before dependents |
| Bounded related reversible secret-free nonstructural peer/bot patch, no owner overlap, executable red→green | Small owner-controlled PR; immutable source SHA/provenance |
| Ambiguous, unowned, or failed condition | Not auto-adoptable; fresh investigation and separate PR/issue; preserve finding |

Safe adoption requires all: immutable pushed SHA, exact show/path inspection, disjoint/assigned paths, no credential literal, no architecture/auth/schema/public behavior/deletion/policy change, clean apply, mechanically nonduplicate patch, targeted red→green, affected QZP, fresh critic PASS. Prefer one tiny fix merged to main, then merge main into dependents. If unavoidable:

```bash
git show --format=fuller --stat <source-sha>
git diff-tree --no-commit-id --name-status -r <source-sha>
git -C "$WT" cherry-pick -x <source-sha>
```

Conflict means abort and classify as reconciliation. Never wave away “pre-existing/flaky”; reproduce/fix in the correct unit or record a true blocker. Never disable a gate.

#### Comments and merge AND-gate

Inspect inline comments, review bodies, reviews, and every GraphQL thread; “outside diff range” may exist only in a review body:

```bash
env -u GH_TOKEN gh api "repos/$REPO/pulls/$PR_NUMBER/comments" --paginate \
  --jq '.[] | {id,in_reply_to_id,path,line,author:.user.login,created_at,body}'

env -u GH_TOKEN gh api "repos/$REPO/pulls/$PR_NUMBER/reviews" --paginate \
  --jq '.[] | {id,state,commit_id,author:.user.login,submitted_at,body}'

env -u GH_TOKEN gh api graphql \
  -F owner="$OWNER" -F repo="$NAME" -F number="$PR_NUMBER" \
  -f query='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:100){nodes{id isResolved comments(last:1){nodes{url body author{login}}}} pageInfo{hasNextPage endCursor}}}}}' \
  --jq '.data.repository.pullRequest.reviewThreads'
```

Paginate GraphQL when `hasNextPage`: rerun the same query with `reviewThreads(first:100,after:$after)`, declare `$after:String`, pass the prior opaque `endCursor` as `-F after="$END_CURSOR"`, and continue until false. Sequence: fetch IDs; fix/validate; scoped commit/push; refetch; reply individually with commit/path; wait for reviewer/bot acknowledgement before resolving a fixed thread; wait exact-head CI; recheck comments/reviews after latest push; repeat. A reasoned declined suggestion may resolve immediately. `commands/handle-pr-comments.md` overrides shorter “resolve after reply” text. Run the real checker:

```bash
bash tools/editor/metaswarm/bin/pr-comments-check.sh "$PR_NUMBER"
```

Merge only when not draft; head unchanged; local validation green; fresh critic PASS; every exact-head required quality/structural check complete/successful; three-dot scope equals allowlist; every comment disposed; zero unresolved threads; no actionable review after latest push; no secret/unexpected staged/untracked path; pairwise overlaps reconciled:

```bash
PR_HEAD_BEFORE=$(env -u GH_TOKEN gh pr view "$PR_NUMBER" --repo "$REPO" \
  --json headRefOid --jq '.headRefOid')
test "$PR_HEAD_BEFORE" = "$(git -C "$WT" rev-parse HEAD)"

env -u GH_TOKEN gh pr merge "$PR_NUMBER" --repo "$REPO" --squash
```

Never `--admin`. Poll until actual `MERGED`; auto-merge-enabled/ready is not completion.

#### Mechanical pairwise reconciliation

For every concurrent PR pair:

```bash
git fetch origin main
git fetch origin "refs/pull/<pr-a>/head:refs/remotes/origin/pr-<pr-a>"
git fetch origin "refs/pull/<pr-b>/head:refs/remotes/origin/pr-<pr-b>"

BASE_A=$(git merge-base origin/main origin/pr-<pr-a>)
BASE_B=$(git merge-base origin/main origin/pr-<pr-b>)
git diff --name-only "$BASE_A" origin/pr-<pr-a> | sort -u > "$RUN_DIR/pr-<pr-a>.paths"
git diff --name-only "$BASE_B" origin/pr-<pr-b> | sort -u > "$RUN_DIR/pr-<pr-b>.paths"
comm -12 "$RUN_DIR/pr-<pr-a>.paths" "$RUN_DIR/pr-<pr-b>.paths"
git diff --quiet origin/pr-<pr-a> origin/pr-<pr-b> -- path/that/overlaps
```

No overlap: shepherd in parallel. Byte-identical overlap: merge one, refresh main, repoll the other. Differing overlap: serialize; merge dependency/smaller structural PR, merge new main into later branch (never rebase published), preserve both, revalidate/review/push/restart CI. If `git log B..A` is empty, B contains A; integrate B and close A. With squash/cherry-pick otherwise prove patch equivalence via `git cherry` plus path/blob equivalence before closing.

Measure stale/mega branch conflicts in a throwaway worktree:

```bash
MEASURE_WT="$HOME/.claude/agent-worktrees/reconcile-<unique-id>"
git worktree add --detach "$MEASURE_WT" "<stale-head-sha>"
git -C "$MEASURE_WT" merge --no-commit --no-ff origin/main
git -C "$MEASURE_WT" diff --name-only --diff-filter=U
git -C "$MEASURE_WT" diff --name-only --diff-filter=U | wc -l
MERGE_BASE=$(git merge-base origin/main "<stale-head-sha>")
git diff --name-status "$MERGE_BASE" "<stale-head-sha>" |
  awk '{print $1}' | sort | uniq -c
git -C "$MEASURE_WT" merge --abort
git worktree remove "$MEASURE_WT"
```

Preserve every nonconflicting unique addition; inspect both directions, never mtime/one side. If stale has no unique dependencies, take current main manifest/lock. Keep main machinery/config unless explicit intent; graft only self-contained tests; never guess runtime assertions. Prefer fresh `reconcile/<slug>` from main plus selected `cherry-pick -x` to a deletion-heavy stale PR. Record every retained/dropped path/proof. “Superseded” requires replacement capability on main.

#### Salvage-first hygiene and exact cleanup

The repo survey marks `~/.claude/agent-worktrees/*` EPHEMERAL and can hide dirty/unique work, so supplement it:

```powershell
pwsh -File scripts/repo-sweep.ps1 -Json
```

```bash
git fetch --prune origin
git worktree list --porcelain
git branch --format='%(refname:short)|%(objectname)|%(upstream:short)|%(upstream:track)|%(committerdate:iso8601)|%(worktreepath)'
git for-each-ref --format='%(refname:short)|%(objectname)|%(committerdate:iso8601)' refs/remotes/origin
git stash list --format='%gd|%H|%gs'

env -u GH_TOKEN gh pr list --repo "$REPO" --state all --limit 1000 \
  --json number,title,state,isDraft,headRefName,headRefOid,baseRefName,mergeStateStatus,mergedAt,mergeCommit,url
```

Every branch/worktree gets one disposition: `ACTIVE_OWNED`, `MERGED_CLEANED`, `SALVAGED_TO_PR`, `PATCH_EQUIVALENT_TO_MAIN`, `SUPERSEDED_BY_MERGED_PR`, or `FAILED_WITH_EXACT_BLOCKER`. `[gone]`, old mtime, detached HEAD, or agent silence is not evidence. Before removal:

```bash
git -C "<exact-worktree>" status --porcelain=v2 --branch
git -C "<exact-worktree>" log --oneline origin/main..HEAD
git -C "<exact-worktree>" ls-files --others --exclude-standard
git stash list --format='%gd|%H|%gs'
```

Dirty/untracked/unique/no-upstream/stash is at-risk. Establish owner; if unowned, create a unique salvage branch there, validate, explicit-stage, commit/push/PR, and shepherd normally. A stash is not a handoff. Never blind-prune, mass-delete, glob-target, `git worktree remove --force`, or drop/clear a stash before integration/explicit archive.

After merge:

```bash
env -u GH_TOKEN gh pr view "$PR_NUMBER" --repo "$REPO" \
  --json state,mergedAt,mergeCommit,headRefName,headRefOid
MERGE_OID=$(env -u GH_TOKEN gh pr view "$PR_NUMBER" --repo "$REPO" \
  --json mergeCommit --jq '.mergeCommit.oid')

git fetch --no-tags --prune origin main
git merge-base --is-ancestor "$MERGE_OID" origin/main
git show --stat --oneline "$MERGE_OID"
```

Signal 1 is API MERGED/mergedAt; signal 2 fetched-main ancestry of merge OID. Squash source head need not be ancestor. Before cleanup require clean worktree, remote tip still equals `PR_HEAD_BEFORE`, no later commits/stash, no open PR using branch:

```bash
git worktree remove "$WT"
git branch -d "$BRANCH"

# If GitHub retained the remote head, reread/match PR_HEAD_BEFORE first:
env -u GH_TOKEN gh api --method DELETE \
  "repos/$REPO/git/refs/heads/$BRANCH"

git fetch --prune origin
git worktree prune --dry-run --verbose
git worktree prune --verbose
```

If local `-d` refuses solely because a deleted/squash-merged upstream lost ancestry, record tip and authorize singleton `-D` only after merged-PR, merge-OID-on-main, unchanged-head, clean-worktree, zero-stash proof. Never use it on UNKNOWN, dirty, diverged, or no-PR.

Have the serialized writer append truthful `PARTIAL` before work to `<ARTIFACT_ROOT>/commit-reconcile.jsonl` (which resolves to `C:/Users/Prekzursil/.claude/workflow-runs/<workflow-id>/commit-reconcile.jsonl`); shape:

```json
{
  "unit_id": "",
  "workstream": "",
  "owner": "",
  "state": "PLANNED|PARTIAL|LOCAL_GREEN|COMMITTED|PUSHED|PR_OPEN|CI_GREEN|MERGED|CLEANED|FAILED",
  "declared_paths": [],
  "worktree_path": "",
  "branch": "",
  "base_sha": "",
  "head_sha": "",
  "commit_shas": [],
  "staged_paths": [],
  "unexpected_paths": [],
  "local_receipts": [],
  "push": {"upstream": "", "local_sha": "", "remote_sha": "", "verified": false},
  "pr": {"number": null, "url": "", "head_oid": "", "base": "main"},
  "ci": {"exact_head": "", "run_id": null, "run_url": "", "contexts": {}},
  "reviews": {"unresolved_threads": null, "actionable_after_head": null},
  "overlaps": [],
  "adopted_source_shas": [],
  "reconciliation": {"class": "", "kept_from_each_side": {}, "dropped_paths": [], "proof": []},
  "merge": {"strategy": "squash", "merge_oid": "", "merged_at": "", "signals": []},
  "cleanup": {"worktree_removed": false, "local_branch_removed": false, "remote_branch_removed": false, "residual_dirty": null, "residual_unique_commits": []},
  "evidence": [],
  "blocker": "",
  "next_action": "",
  "timestamp": ""
}
```

No “agent said done” transition. Repository unit success is `CLEANED`, not merely MERGED.

### 7. Preserve the MCP fleet SSOT and prove runtime behavior when relevant

The fixed architecture is:

```text
tools/mcp/canonical-mcp-servers.json
  -> reviewed/promoted repository projection
  -> ~/.mcp.json (canonical live source)
  -> hooks/mcp-userscope-sync/promote-mcp-userscope.ps1
  -> top-level mcpServers in ~/.claude.json
  -> fresh-session initialize + tools/list
```

The end state is user-scope, visible/exposed, and disabled at rest through the live per-project `disabledMcpServers` defaults; temporarily enable only scoped servers for a lifecycle probe, then restore byte/field-equivalent baseline. Never machine-wide reap. A config being present is not proof it loaded; an exposed tool is not proof it works; a write response is not independent readback.

The six supplied facets did not contain literal fleet entries or per-server tool lists. A targeted no-checkout/no-hooks read of grounding commit `a919578f2cdf107ac8f049ae5a97459e25b83440` filled that explicit gap. Treat the following as a stale comparison baseline, not a task list and never overwrite a newer legitimate live file merely from this prompt. Re-read the live file, enumerate its complete key set, and protocol-probe actual `initialize` and `tools/list`; preserve every live entry and unrelated section unless the filled GOAL explicitly changes it.

Grounded canonical file:

```json
{
  "mcpServers": {
    "agent-mail": {
      "type": "http",
      "url": "http://127.0.0.1:8812/mcp"
    },
    "apktool-mcp": {
      "command": "C:/Users/Prekzursil/.local/opt/apktool-mcp-server/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/.local/opt/apktool-mcp-server/apktool_mcp_server.py"
      ]
    },
    "basic-memory": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    },
    "binary-ninja-mcp": {
      "command": "npx",
      "args": ["-y", "binary-ninja-mcp"]
    },
    "cheatengine": {
      "command": "C:/Users/Prekzursil/.local/opt/cheatengine-mcp-bridge/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/.local/opt/cheatengine-mcp-bridge/MCP_Server/mcp_cheatengine.py"
      ]
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp"]
    },
    "cloud-hub": {
      "type": "stdio",
      "command": "C:\\Python314\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\cloud-hub\\hub.py"
      ],
      "env": {
        "RUNPOD_API_KEY": "${RUNPOD_API_KEY}",
        "KAGGLE_USERNAME": "${KAGGLE_USERNAME}",
        "KAGGLE_KEY": "${KAGGLE_KEY}",
        "GOOGLE_CLOUD_PROJECT": "${GOOGLE_CLOUD_PROJECT}",
        "MODAL_TOKEN_ID": "${MODAL_TOKEN_ID}",
        "MODAL_TOKEN_SECRET": "${MODAL_TOKEN_SECRET}",
        "LIGHTNING_USER_ID": "${LIGHTNING_USER_ID}",
        "LIGHTNING_API_KEY": "${LIGHTNING_API_KEY}",
        "OVH_ENDPOINT": "${OVH_ENDPOINT}",
        "OVH_APPLICATION_KEY": "${OVH_APPLICATION_KEY}",
        "OVH_APPLICATION_SECRET": "${OVH_APPLICATION_SECRET}",
        "OVH_CONSUMER_KEY": "${OVH_CONSUMER_KEY}",
        "DATABRICKS_HOST": "${DATABRICKS_HOST}",
        "DATABRICKS_CLIENT_ID": "${DATABRICKS_CLIENT_ID}",
        "DATABRICKS_CLIENT_SECRET": "${DATABRICKS_CLIENT_SECRET}",
        "DATABRICKS_TOKEN": "${DATABRICKS_TOKEN}"
      }
    },
    "codex-fleet-github": {
      "type": "stdio",
      "command": "C:\\Python314\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\codex-fleet-github\\server.py"
      ],
      "env": {
        "CODEX_DISPATCH_PAT": "${CODEX_DISPATCH_PAT}",
        "CODEX_RUNNER_REF": "feat/codex-parity-runner"
      }
    },
    "context7": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@upstash/context7-mcp"],
      "env": {"CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"}
    },
    "cve-mcp": {
      "command": "npx",
      "args": ["-y", "cve-mcp"]
    },
    "deepwiki": {
      "type": "http",
      "url": "https://mcp.deepwiki.com/mcp"
    },
    "docker": {
      "command": "C:/Users/Prekzursil/.local/bin/uvx.exe",
      "args": ["docker-mcp"]
    },
    "elevenlabs": {
      "type": "stdio",
      "command": "uvx",
      "args": ["elevenlabs-mcp"],
      "env": {}
    },
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_search_advanced_exa,web_fetch_exa,company_research_exa,linkedin_search_exa,deep_researcher_start,deep_researcher_check,get_code_context_exa",
      "headers": {"x-api-key": "${EXA_API_KEY}"}
    },
    "excel": {
      "type": "stdio",
      "command": "C:\\Users\\Prekzursil\\.local\\bin\\uvx.exe",
      "args": ["excel-mcp-server", "stdio"],
      "env": {}
    },
    "fb-messenger": {
      "command": "C:\\Users\\Prekzursil\\source\\repos\\fb-messenger-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\repos\\fb-messenger-mcp\\server.py"
      ]
    },
    "figma": {
      "type": "http",
      "url": "https://mcp.figma.com/mcp"
    },
    "figma-rest": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "figma-developer-mcp", "--stdio"],
      "env": {"FIGMA_API_KEY": "${FIGMA_ACCESS_TOKEN}"}
    },
    "firecrawl": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "firecrawl-mcp@latest"],
      "env": {"FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"}
    },
    "frida-mcp": {
      "command": "npx",
      "args": ["-y", "frida-mcp"]
    },
    "ghidra-mcp": {
      "command": "C:/Users/Prekzursil/.local/opt/ghidra-mcp/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/.local/opt/ghidra-mcp/GhidraMCP-release-1-4/bridge_mcp_ghidra.py",
        "--ghidra-server",
        "http://127.0.0.1:8089/"
      ]
    },
    "github_cli": {
      "type": "stdio",
      "command": "gh-cli-mcp",
      "args": [],
      "env": {
        "GITHUB_MCP_PAT": "${GITHUB_MCP_PAT}",
        "GH_TOKEN": "${GH_TOKEN}"
      }
    },
    "gitlab": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@zereight/mcp-gitlab"],
      "env": {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_TOKEN}",
        "GITLAB_API_URL": "https://gitlab.com/api/v4"
      }
    },
    "hexstrike-ai": {
      "command": "C:/Users/Prekzursil/.local/opt/hexstrike-ai/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/.local/opt/hexstrike-ai/hexstrike_mcp_launcher.py"
      ]
    },
    "huggingface": {
      "type": "http",
      "url": "https://huggingface.co/mcp"
    },
    "ida-pro-mcp": {
      "command": "C:/Users/Prekzursil/.local/opt/ida-pro-mcp/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/.local/opt/ida-pro-mcp/.venv/Lib/site-packages/ida_pro_mcp/server.py"
      ]
    },
    "jadx-mcp": {
      "command": "C:/Users/Prekzursil/.local/opt/jadx-mcp-server/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/.local/opt/jadx-mcp-server/jadx_mcp_server.py"
      ]
    },
    "linkedin": {
      "type": "stdio",
      "command": "C:\\Python314\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\linkedin-mcp\\server.py"
      ],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "${LINKEDIN_ACCESS_TOKEN}",
        "LINKEDIN_CLIENT_ID": "${LINKEDIN_CLIENT_ID}",
        "LINKEDIN_CLIENT_SECRET": "${LINKEDIN_CLIENT_SECRET}",
        "LINKEDIN_REDIRECT_URI": "${LINKEDIN_REDIRECT_URI}"
      }
    },
    "markitdown": {
      "type": "stdio",
      "command": "C:\\Users\\Prekzursil\\.local\\bin\\markitdown-mcp.exe",
      "args": [],
      "env": {}
    },
    "ocr-suite": {
      "command": "D:/mcp-servers/abbyy-finereader-ocr-mcp/.venv/Scripts/python.exe",
      "args": ["D:/mcp-servers/abbyy-finereader-ocr-mcp/index.py"]
    },
    "openmm-md": {
      "command": "D:/micromamba/envs/openmm-md/python.exe",
      "args": ["C:/Users/Prekzursil/source/repos/openmm-md-mcp/server.py"]
    },
    "paper-search": {
      "command": "D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe",
      "args": []
    },
    "pdf-reader": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@sylphx/pdf-reader-mcp"],
      "env": {}
    },
    "perplexity": {
      "command": "D:/ReverseTools/mcp/perplexity-web-mcp/.venv/Scripts/pwm-mcp.exe",
      "args": []
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "playwright-mcp"]
    },
    "proxy-mcp": {
      "type": "stdio",
      "command": "C:\\Users\\Prekzursil\\.local\\opt\\mitmproxy-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\proxy-mcp\\proxy_mcp.py"
      ],
      "env": {"PROXY_MCP_REDACT": "on"}
    },
    "qdx-rush": {
      "command": "C:/Users/Prekzursil/.local/bin/uv.exe",
      "args": [
        "run",
        "--directory",
        "C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/qdx-rush-mcp",
        "python",
        "qdx_mcp_server.py"
      ]
    },
    "qlty": {
      "command": "C:/Program Files/nodejs/node.exe",
      "args": ["C:/Users/Prekzursil/.agents/meta-tool/src/qlty_mcp_server.mjs"]
    },
    "ralph-orchestrator": {
      "command": "C:/Users/Prekzursil/.cargo/bin/ralph.exe",
      "args": ["mcp", "serve"]
    },
    "rdkit": {
      "command": "C:/Users/Prekzursil/source/repos/rdkit-mcp-server/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Prekzursil/source/repos/rdkit-mcp-server/rdkit_mcp_launch.py"
      ]
    },
    "repomix": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "repomix", "--mcp"],
      "env": {}
    },
    "scholarly-access": {
      "command": "C:/Users/Prekzursil/source/agent-skills-toolchain/tools/scholarly-access-mcp/.venv/Scripts/scholarly-access-mcp.exe",
      "args": []
    },
    "schrodinger": {
      "command": "C:/Users/Prekzursil/source/repos/schrodinger-mcp/.venv/Scripts/python.exe",
      "args": ["C:/Users/Prekzursil/source/repos/schrodinger-mcp/server.py"]
    },
    "search-hub": {
      "type": "stdio",
      "command": "C:\\Python314\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\search-hub\\hub.py"
      ],
      "env": {
        "EXA_API_KEY": "${EXA_API_KEY}",
        "EXA_API_KEY_2": "${EXA_API_KEY_2}",
        "TAVILY_API_KEY": "${TAVILY_API_KEY}",
        "TAVILY_API_KEY_2": "${TAVILY_API_KEY_2}",
        "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}",
        "FIRECRAWL_API_KEY_2": "${FIRECRAWL_API_KEY_2}"
      }
    },
    "searxng": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "mcp-searxng@1.8.0"],
      "env": {"SEARXNG_URL": "http://127.0.0.1:8890"}
    },
    "social-hub": {
      "type": "stdio",
      "command": "C:\\Python314\\python.exe",
      "args": [
        "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\social-hub\\hub.py"
      ],
      "env": {
        "FB_PAGE_ACCESS_TOKEN": "${FB_PAGE_ACCESS_TOKEN}",
        "FB_PAGE_ID": "${FB_PAGE_ID}",
        "FB_IG_USER_ID": "${FB_IG_USER_ID}",
        "FB_GRAPH_VERSION": "v23.0",
        "FB_E2EE_ENABLED": "${FB_E2EE_ENABLED}"
      }
    },
    "tavily": {
      "type": "http",
      "url": "https://mcp.tavily.com/mcp/",
      "headers": {"Authorization": "Bearer ${TAVILY_API_KEY}"}
    },
    "tooluniverse": {
      "command": "uvx",
      "args": ["tooluniverse==1.2.4"]
    }
  }
}
```

That snapshot has 48 keys:

```text
agent-mail, apktool-mcp, basic-memory, binary-ninja-mcp, cheatengine,
chrome-devtools, cloud-hub, codex-fleet-github, context7, cve-mcp, deepwiki,
docker, elevenlabs, exa, excel, fb-messenger, figma, figma-rest, firecrawl,
frida-mcp, ghidra-mcp, github_cli, gitlab, hexstrike-ai, huggingface,
ida-pro-mcp, jadx-mcp, linkedin, markitdown, ocr-suite, openmm-md, paper-search,
pdf-reader, perplexity, playwright, proxy-mcp, qdx-rush, qlty,
ralph-orchestrator, rdkit, repomix, scholarly-access, schrodinger, search-hub,
searxng, social-hub, tavily, tooluniverse
```

Do not assume that list or any server’s tools are current. Mechanically compare the complete live canonical/deployed key sets and definitions, with secret values redacted. For each goal-relevant server, capture the live protocol tool list (tool name and input schema) and a nonmutating functional call; a per-server tool list belongs in the run evidence, not hardcoded controller source.

The promoter edits only top-level `mcpServers`, preserves `projects`, OAuth, caches, and per-project disabled lists, takes a timestamped backup, parses/verifies before replace, and by default keeps extra user-scope servers. It must run with every Claude Code session/window closed because an open process holds/re-writes `~/.claude.json`. Never use `-Force` from this live session and never counterfeit a restart proof:

```powershell
# From the repo, inspect script first.
pwsh -NoProfile -File hooks/mcp-userscope-sync/promote-mcp-userscope.ps1 -DryRun

# Apply only from a proven Claude-closed control context:
pwsh -NoProfile -File hooks/mcp-userscope-sync/promote-mcp-userscope.ps1 -Yes

# Only when the explicit goal requires exact pruning and evidence proves extras are drift:
pwsh -NoProfile -File hooks/mcp-userscope-sync/promote-mcp-userscope.ps1 \
  -Yes -PruneExtraUserServers
```

If promotion is required but a safe existing closed-batch/resume mechanism cannot apply it while Claude is closed and then independently verify a fresh session, preserve the prepared candidate/backup and mark that DoD FAILED with the exact close/apply/restart probe. Do not leave a detached background process and call it done. `hooks/mcp-userscope-sync/heal.py` is a fail-open next-session orphan-tree/backstop and one-session delayed; it is not immediate promotion proof. `hooks/mcp-defaults/enforce-mcp-defaults.py` is fail-open; inspect live `~/.claude/.mcp-disabled-defaults.json`, prove all intended canonical servers are disabled for the actual project, and test a known-broken/fixed fixture.

### 8. Optional backend: same units and truth, different transport

Use one backend-neutral interface:

```text
prepare(units, frozen_grounding_bundle, result_contract) -> batch
submit(batch) -> run_handle
poll(run_handle) -> terminal_lifecycle
harvest(run_handle) -> identity-keyed unit results
```

Local and Databricks consume the same frozen goal, DoD, unit assignment, honesty contract, and result semantics. Databricks contributions never mark a parent DoD complete. Local Claude owns all shared-state mutation, integration, final tests, every git write, deploy, memory, and terminal decision. Codex/Databricks units return artifacts or complete replacement files; they do not mutate the owner worktree or commit/push/merge. The specialized Program-E isolated push capability is not generic authority here.

Support internal `COMPUTE_BACKEND` values:

- `local`: never submit Databricks.
- `databricks`: request it for every eligible unit, without overriding portability, secret, cost, or ownership gates.
- `auto`: route when computed `N_portable >= 25`; keep fewer portable units local.

Remote-safe means none of: Windows-only path, live MCP fleet, browser/profile/cookie, local process, `Downloads`, live memory vault, local credential, mutable shared config, or owner-worktree mutation. Source-grounded work gets one immutable secret-free archive. A remote-discovered local dependency ends that slice and emits a lead.

Partition >48 portable units into sequential waves of at most 48; never concurrent 48-worker jobs. Grounding measured Windows RAM contention above about 24 local Codex workers and one `r5d.2xlarge` completing 48/48 with 3-second stagger; API arrival rate, not RAM, was limiting. An explicit bounded pricing/rail goal may override the 25 threshold, never portability. Auth/policy/setup/current-price/backend failure records `BACKEND-FALLBACK:<reason>` and continues locally without asking for routine ordering.

Use canonical `.agents/skills/codex-databricks-fanout/`; mirror `skills/codex-databricks-fanout/` is compatibility. Frozen grounded configuration—re-probe live, do not copy a stale absent `tools/` harness:

```text
profile              bolt-datascience
policy_id            0002189219BF8EF3
spark_version        15.4.x-scala2.12
node_type_id         r5d.2xlarge
driver_node_type_id  r5d.2xlarge
num_workers          0
cluster profile      singleNode
concurrency          min(unit_count, 48)
stagger_s            3.0
secret scope/key     codex-harness-prekzursil / auth_json
workspace notebook   /Users/costin.ionescu@bolt.eu/codex-batch/batch_runner
model/effort          gpt-5.6-sol / ultra
instance profile     arn:aws:iam::287845475429:instance-profile/datascience-instance-profile
S3 cluster logs      s3://bolt-databricks-logs/cluster-logs/bolt-datascience
```

The `harness/submit.py` payload retains `LEGACY_SINGLE_USER_STANDARD`, `ON_DEMAND`, `zone_id=auto`, elastic disk, `spark.master=local[*]`, `spark.databricks.cluster.profile=singleNode`, `ResourceClass=SingleNode`, `CostCenter=ENG-DATA-PLATFORM`, and JFrog secret references. Never substitute bare `new_cluster`, serverless, interactive, larger/multinode, or unstaggered launches.

Before billable submit produce a current-price Phase-0 receipt. The policy 18-DBU/hour cap is not a dollar price. Without a separate ceiling, at most one proven single-node job/wave; record live estimate and actual duration; do not scale node class.

IDs are unique, match `^[A-Za-z0-9][A-Za-z0-9._-]*$`, reject `.` and `..`, and have a practical length bound because worker uses unsanitized ID as directory/file. One batch shares one result directory; actual basename is exactly `<id>.md` regardless of informational `artifact`. Set positive `timeout_s` explicitly; default 900 is insufficient for substantive units, normally use justified 2400.

```json
{
  "name": "wf-<workflow-id>-portable-01",
  "units": [
    {
      "id": "example-portable-unit",
      "lane": "workflow",
      "prompt": "<frozen GOAL+DoD prefix, exclusive assignment, and result contract>",
      "artifact": "/dbfs/tmp/wf-<workflow-id>-portable-01/results/example-portable-unit.md",
      "timeout_s": 2400
    }
  ],
  "meta": {"n": 1}
}
```

The example is a shape, not a static unit. The runner precreates the full `FANOUT-CONTRACT:v1` rich skeleton for every remote unit before `codex exec`, with the exact campaign-bound `unit` block, claims, corrections, evidence rows, coverage, hashes, sidecar, and canonical terminal semantics from section 4. The remote worker checkpoints that rich document and closes it only after semantic validation. During migration, the same final artifact also requests >=1200 UTF-8 bytes and contains this additional legacy compatibility block before the one exact final sentinel:

````text
```result
unit_id: <exact id>
unit_status: COMPLETE
coverage: <what was and was not examined>
findings: <bounded summary>
evidence: <file:line or primary URL anchors>
unverified: <none, or inline claims plus settling probes>
dod_contribution: <assigned DOD-NN IDs this artifact informs>
```

UNIT-COMPLETE: <exact id>
````

Every remote unit starts from the runner-written rich UNKNOWN skeleton with no sentinel. For >10 minutes it additionally rewrites at named milestones and may show a legacy `UNIT-IN-PROGRESS` compatibility marker; only the final semantically closed document uses `UNIT-COMPLETE`. After harvest require both the old compatibility validator and the full campaign-bound 12-clause validator, then promote staging bytes to the canonical local artifact with byte/hash equality.

Run from repo root in Git Bash; scope environment per command and never echo credentials or globally export `MSYS_NO_PATHCONV`:

```bash
SKILL_ROOT='.agents/skills/codex-databricks-fanout'

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks current-user me --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks clusters list --profile bolt-datascience
```

Build dynamic `batch.json` via `harness.build_batch.build_batch()` / `write_batch()` or the exact JSON contract. Create a fresh temp control directory outside git. Use a file-writing tool—not heredoc—to create `prepare_payload.py` exactly:

```python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(".agents/skills/codex-databricks-fanout/scripts").resolve()
sys.path.insert(0, str(SCRIPTS))
from harness.submit import build_payload  # noqa: E402


def prepare(run_tag: str, batch_name: str, payload_name: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_tag):
        raise SystemExit("invalid run tag")
    batch_path = Path(batch_name)
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    units = batch.get("units")
    if not isinstance(units, list) or not units:
        raise SystemExit("batch.units must be a non-empty list")
    seen: set[str] = set()
    for unit in units:
        uid = unit.get("id")
        if not isinstance(uid, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*", uid
        ):
            raise SystemExit(f"unsafe unit id: {uid!r}")
        if uid in {".", ".."} or uid in seen:
            raise SystemExit(f"duplicate/reserved unit id: {uid!r}")
        seen.add(uid)
        expected = f"/dbfs/tmp/{run_tag}/results/{uid}.md"
        if unit.get("artifact") != expected:
            raise SystemExit(f"{uid}: artifact must be {expected}")
        if not isinstance(unit.get("timeout_s"), int) or unit["timeout_s"] <= 0:
            raise SystemExit(f"{uid}: explicit positive timeout_s required")

    n = len(units)
    root = f"/dbfs/tmp/{run_tag}"
    payload = build_payload(n, f"{root}/batch.json", f"{root}/results")
    # Current build_payload() omits the worker's bundle_tgz widget.
    payload["tasks"][0]["notebook_task"]["base_parameters"]["bundle_tgz"] = (
        f"{root}/subject.tar.gz"
    )
    Path(payload_name).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return n


def read_run_id(submit_name: str) -> int:
    value = json.loads(Path(submit_name).read_text(encoding="utf-8")).get("run_id")
    if not isinstance(value, int):
        raise SystemExit("submit output has no integer run_id")
    return value


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "prepare":
        print(prepare(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif len(sys.argv) == 3 and sys.argv[1] == "run-id":
        print(read_run_id(sys.argv[2]))
    else:
        raise SystemExit(
            "usage: prepare_payload.py prepare RUN_TAG BATCH_JSON PAYLOAD_JSON "
            "| run-id SUBMIT_JSON"
        )
```

```bash
RUN_TAG='wf-<workflow-id>-portable-01'
SKILL_ROOT='.agents/skills/codex-databricks-fanout'
RUN_CONTROL_DIR="$(mktemp -d)"
BATCH_JSON="$RUN_CONTROL_DIR/batch.json"
PAYLOAD_JSON="$RUN_CONTROL_DIR/payload.json"
SUBMIT_JSON="$RUN_CONTROL_DIR/submit.json"
RUN_JSON="$RUN_CONTROL_DIR/run.json"
RESULT_DEST="$RUN_CONTROL_DIR/results"
PREPARE="$RUN_CONTROL_DIR/prepare_payload.py"

# Place dynamic batch.json and exact script via file-writing tool.
N="$(python "$PREPARE" prepare "$RUN_TAG" "$BATCH_JSON" "$PAYLOAD_JSON")"
test "$N" -gt 0
```

Create `subject.tar.gz` only from exact committed allowlisted cohort paths; inspect members. Never include home/profile, raw personal corpus, uncommitted work, or credentials. A source-free research cohort gets a tiny frozen grounding archive:

```bash
ALLOWLISTED_PATHS=(README.md tools/monitorcore rules hooks)
git archive --format=tar.gz --output="$RUN_CONTROL_DIR/subject.tar.gz" \
  HEAD -- "${ALLOWLISTED_PATHS[@]}"
tar -tzf "$RUN_CONTROL_DIR/subject.tar.gz"
test -s "$RUN_CONTROL_DIR/subject.tar.gz"
```

Replace the example allowlist with runtime-derived scope. Use `dbfs:/` for CLI, `/dbfs/` inside worker/notebook:

```bash
env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks fs mkdirs \
  "dbfs:/tmp/$RUN_TAG/results" --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks fs cp "$BATCH_JSON" \
  "dbfs:/tmp/$RUN_TAG/batch.json" --overwrite --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks fs cp "$RUN_CONTROL_DIR/subject.tar.gz" \
  "dbfs:/tmp/$RUN_TAG/subject.tar.gz" --overwrite --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks jobs submit \
  --json "@$PAYLOAD_JSON" --no-wait -o json --profile bolt-datascience \
  > "$SUBMIT_JSON"

RUN_ID="$(python "$PREPARE" run-id "$SUBMIT_JSON")"
test "$RUN_ID" -gt 0
```

Immediately use the file-writing tool to atomically update `$RUN_CONTROL_DIR/controller.json` with the campaign ID, `active_run_id`, submission response path/hash, and timestamp; then persist and independently read it back from DBFS before polling. It is a receipt, not result:

```bash
CONTROLLER_JSON="$RUN_CONTROL_DIR/controller.json"
CONTROLLER_READBACK="$RUN_CONTROL_DIR/controller.readback.json"

# File-writing tool has already atomically written controller.json with RUN_ID.
python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); assert d['active_run_id']==int(sys.argv[2])" \
  "$CONTROLLER_JSON" "$RUN_ID"

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks fs cp "$CONTROLLER_JSON" \
  "dbfs:/tmp/$RUN_TAG/controller.json" --overwrite --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks fs cat \
  "dbfs:/tmp/$RUN_TAG/controller.json" --profile bolt-datascience \
  > "$CONTROLLER_READBACK"

python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); assert d['active_run_id']==int(sys.argv[2])" \
  "$CONTROLLER_READBACK" "$RUN_ID"
```

```bash
env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks jobs get-run "$RUN_ID" -o json \
  --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 python "$SKILL_ROOT/scripts/e2e/watch.py" \
  "$RUN_ID" "dbfs:/tmp/$RUN_TAG/results" \
  "$N" 15 "$RUN_TAG" ''
```

Wait for lifecycle `TERMINATED|INTERNAL_ERROR|SKIPPED`; artifact appearance during live run is not completion. After terminal allow three re-harvest attempts separated by 20 seconds. DBFS-to-host uses `fs cat`, never `fs cp` (measured silent no-op):

```bash
python "$SKILL_ROOT/scripts/harness/harvest_cli.py" \
  --result-dir "dbfs:/tmp/$RUN_TAG/results" \
  --dest "$RESULT_DEST" \
  --expected "$N" \
  --fence result \
  --required-field unit_id \
  --required-field unit_status \
  --required-field coverage \
  --required-field findings \
  --required-field evidence \
  --required-field unverified \
  --required-field dod_contribution \
  --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks fs cat \
  "dbfs:/tmp/$RUN_TAG/results/_summary.json" \
  --profile bolt-datascience

env -u DATABRICKS_TOKEN -u DATABRICKS_HOST -u DATABRICKS_ACCOUNT_ID \
  MSYS_NO_PATHCONV=1 databricks jobs get-run "$RUN_ID" -o json \
  --profile bolt-datascience > "$RUN_JSON"
```

`harvest_cli.py` alone is not the five-clause gate: grounded behavior passed `min_bytes=0`, checked nonempty required fields, did not require `COMPLETE`, and did not reject all-UNKNOWN. Verify summary bundle path/bytes/top-level members. Until the canonical campaign validator is deployed end-to-end, also create `validate_results.py` exactly:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(".agents/skills/codex-databricks-fanout/scripts").resolve()
sys.path.insert(0, str(SCRIPTS))
from harness.contract import and_gate_artifact  # noqa: E402
from harness.gate import parse_block  # noqa: E402

TERMINAL = {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}
REQUIRED = (
    "unit_id",
    "unit_status",
    "coverage",
    "findings",
    "evidence",
    "unverified",
    "dod_contribution",
)
SEMANTIC = ("coverage", "findings", "evidence", "unverified", "dod_contribution")


def main(run_name: str, batch_name: str, result_name: str) -> int:
    run = json.loads(Path(run_name).read_text(encoding="utf-8"))
    state = (run.get("state") or {}).get("life_cycle_state")
    errors: list[str] = []
    if state not in TERMINAL:
        errors.append(f"run lifecycle is not terminal: {state!r}")

    batch = json.loads(Path(batch_name).read_text(encoding="utf-8"))
    units = batch.get("units") or []
    result_dir = Path(result_name)
    for unit in units:
        uid = unit["id"]
        artifact = result_dir / f"{uid}.md"
        ok, reason, _ = and_gate_artifact(uid, artifact, min_bytes=1024)
        if not ok:
            errors.append(f"{uid}: {reason}")
            continue
        text = artifact.read_text(encoding="utf-8", errors="replace")
        fields = parse_block(text, "result")
        if fields is None:
            errors.append(f"{uid}: no parsable result fence")
            continue
        missing = [name for name in REQUIRED if not fields.get(name)]
        if missing:
            errors.append(f"{uid}: missing/non-empty fields {missing}")
        if fields.get("unit_id") != uid:
            errors.append(f"{uid}: result unit_id mismatch")
        if fields.get("unit_status") != "COMPLETE":
            errors.append(f"{uid}: unit_status is not COMPLETE")
        if all(
            "UNKNOWN - not yet measured" in fields.get(name, "") for name in SEMANTIC
        ):
            errors.append(f"{uid}: all-UNKNOWN skeleton")

    if errors:
        for error in errors:
            print(f"FAILED:{error}")
        return 1
    print(f"SUCCESS:databricks-gate {len(units)}/{len(units)} DONE state={state}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: validate_results.py RUN_JSON BATCH_JSON RESULT_DIR"
        )
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
```

```bash
VALIDATE="$RUN_CONTROL_DIR/validate_results.py"
python "$VALIDATE" "$RUN_JSON" "$BATCH_JSON" "$RESULT_DEST"
```

Current compatibility DONE is all five:

1. Run lifecycle terminal.
2. Identity-specific local artifact exists/readable.
3. Explicit lane floor 1024 for this full-report rail; prompt requests 1200.
4. Exact `UNIT-COMPLETE: <id>` appears within final 600 bytes.
5. Fenced fields present/nonempty, unit ID exact, `unit_status=COMPLETE`, not all UNKNOWN.

The grounded implementations described the tail in two units: `contract.py/poll.py` decoded the final 600 bytes and searched a literal substring while some worker prose called it the final 600 decoded characters; `gate.py` separately checked structural sentinel token and ID. Inspect live constants and test a multibyte boundary; during transition require the stricter byte-safe exact-ID result, not the more permissive interpretation. `contract.LANE_SCHEMAS` knew only coverage/smoke, so `lane:workflow` made `poll.classify()` schema clause vacuous; the validator closes it. Add/test a real workflow lane or keep overlay; never rely on unknown-lane default. Once the stricter campaign-bound validator in section 4 is deployed everywhere, it also requires exact final nonblank sentinel and campaign hashes. During transition require both; never weaken to the older one.

A valid artifact may be DONE after `INTERNAL_ERROR`; clean process exit without artifact is not. Watcher exit zero on termination is not completion. Backend lifecycle + artifact are delivery signals, not automatically parent-DoD signals.

At grounding, a failed `jobs get-run` or malformed state JSON could leave state `?` and degrade to RUNNING/eventual timeout instead of UNKNOWN; harden that fail-open detector before claiming detector-failure discipline. `batch_runner.py` also required Codex exit zero, >=1024 bytes, and a generic tail sentinel without exact ID/lane schema. Preserve its diagnostics but let the independently validated artifact control semantic outcome.

Retry/fallback:

- ABSENT or truly severed/missing sentinel: retry only that unit once under old compatibility behavior; campaign recovery still caps total attempts at three.
- MALFORMED/wrong identity/schema: correct contract before retry.
- 429 cluster: double stagger to 6.0 in both `base_parameters.stagger_s` and `spark_env_vars.BATCH_STAGGER_S`; if repeated, local fallback, not more nodes.
- Auth/setup/policy/current-price/node-preflight failure: classified local fallback.
- Never duplicate a timed-out observation until actual lifecycle terminal.
- Preserve every partial.

Caveats:

1. Cold start about 3–5 minutes and billable; amortize and record current cost.
2. Proven rail is one `r5d.2xlarge`, <=48, 3-second stagger; larger/multinode does not solve 429.
3. Shared `auth.json` proved only short single-node runs; multi-hour refresh/multinode sharing unproved. Use per-process `CODEX_HOME` before expanding.
4. Never place PAT/token/JWT/auth.json/cookie/personal corpus/secret config in batch, prompt, tar, DBFS artifact, or log; auth comes from named secret scope.
5. Worker uses `codex exec --ignore-user-config`, explicit `gpt-5.6-sol`, `model_reasoning_effort="ultra"`, web search enabled, MCP disabled, existing workspace notebook. It does not inherit local MCP.
6. `npm install -g @openai/codex` installs latest; observed `0.144.6` is not pinned. Behavioral node preflight requires `ultra` succeeds and bogus effort fails; do not version-string gate.
7. Checked-in `batch_runner.py` export placed `from __future__` after executable widget setup and lacked visible notebook cell delimiter; use proven workspace notebook, do not redeploy blindly before fix/live validation.
8. `harvest_cli.py` labels any sentinel reason `SEVERED`, including wrong identity; subtype advisory, exact identity mandatory.

### 9. Required executor interface and final integration

Build each frozen worker prompt at runtime so this raw packet still contains only the one active input pair. Split delimiter strings in JavaScript:

```js
const workerPromptFor = (unit) => [
  BASE_CONTEXT,
  `You own work unit ${unit.semantic_key}. Stay inside its authority and scope.`,
  '',
  '<' + 'TASK>',
  '<' + 'GOAL>',
  goalRaw,
  '</' + 'GOAL>',
  '',
  '<' + 'DoD>',
  dodRaw,
  '</' + 'DoD>',
  '',
  'ASSIGNMENT:',
  `- Work unit: ${unit.semantic_key}`,
  `- Assigned DoD IDs: ${JSON.stringify(unit.dod_ids)}`,
  `- Dependencies: ${JSON.stringify(unit.depends_on)}`,
  `- Read/write mode: ${unit.mutates ? 'WRITE within allowlist' : 'READ-ONLY'}`,
  `- Exclusive targets: ${JSON.stringify(unit.write_scope)}`,
  `- Conflict keys: ${JSON.stringify(unit.conflict_keys)}`,
  `- Backend venue: ${unit.venue}`,
  `- Contracted artifact: ${artifactFor(unit)}`,
  '</' + 'TASK>',
  '',
  'Execute only the named stage supplied after this frozen assignment.',
  'Checkpoint durable truth; do not close the unit before the finalizer.',
  'Emit newly found siblings only as new_leads.',
  'Self-report is not proof. Never return a background/job-status receipt.',
].join('\n')

const STAGE_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    stage_json: {
      type: 'string',
      description: 'Canonical stage receipt JSON; the only required field.',
    },
    stage_markdown: { type: 'string' },
  },
  required: ['stage_json'],
}

const CRITIC_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    critic_json: {
      type: 'string',
      description: 'Canonical critic payload from section 5; the only required field.',
    },
  },
  required: ['critic_json'],
}

async function runPerUnitPipeline(unit) {
  // The runner already wrote the canonical skeleton and sidecar.
  const prepared = unit.mutates
    ? await countedAgent(workspaceManagerPrompt(unit), {
        label: `work:${boundedLabel(unit.semantic_key)}:prepare-worktree`,
        phase: 'Work Loop',
        schema: STAGE_SCHEMA,
      })
    : noMutationPreparationReceipt(unit)
  const prep = validateStage(prepared, unit, 'prepared')
  if (!prep.pass) return await closeFailedUnit(unit, prep.reason)

  const candidateRaw = await countedAgent(`${workerPromptFor(unit)}

STAGE: IMPLEMENT CANDIDATE.
Authoritative persistent worktree: ${prep.worktree_path}
Base SHA: ${prep.base_sha}
Do not commit, push, open a PR, merge, clean, or append UNIT-COMPLETE.
Edit only the allowlist, run scoped developer tests, checkpoint the canonical
artifact, and return exact candidate paths/content hash plus raw output paths.`, {
    label: `work:${boundedLabel(unit.semantic_key)}:implement`,
    phase: 'Work Loop',
    schema: STAGE_SCHEMA,
    effort: unit.risk === 'high' ? 'xhigh' : 'high',
    ...(unit.mutates ? { isolation: 'worktree' } : {}),
  })
  let candidate = validateStage(candidateRaw, unit, 'candidate')
  if (!candidate.pass) return await closeFailedUnit(unit, candidate.reason)

  for (let reviewRound = 1; reviewRound <= 3; reviewRound++) {
    const validationRaw = await countedAgent(`${BASE_CONTEXT}

VALIDATE CANDIDATE READ-ONLY. Do not edit or publish.
Expected key: ${unit.semantic_key}
Persistent worktree: ${prep.worktree_path}
Candidate content hash: ${candidate.content_sha256}
Allowlist: ${JSON.stringify(unit.write_scope)}
Acceptance: ${JSON.stringify(unit.acceptance)}
Mechanically recompute changed/untracked paths and run orchestrator-owned
validation against these exact bytes. Return stage=candidate-validation.`, {
      label: `work:${boundedLabel(unit.semantic_key)}:validate:r${reviewRound}`,
      phase: 'Work Loop',
      schema: VERIFY_SCHEMA,
    })
    const validation = validateVerification(
      validationRaw, unit.semantic_key, 'candidate-validation', candidate
    )

    const secondRaw = await countedAgent(`${BASE_CONTEXT}

INDEPENDENT POSTCONDITION, READ-ONLY.
Use the predeclared mechanically different signal and detector controls against
the exact same candidate hash ${candidate.content_sha256}. Do not reuse the
validation detector, edit, or publish. Return stage=independent-postcondition.`, {
      label: `work:${boundedLabel(unit.semantic_key)}:second-signal:r${reviewRound}`,
      phase: 'Work Loop',
      schema: VERIFY_SCHEMA,
    })
    const second = validateVerification(
      secondRaw, unit.semantic_key, 'independent-postcondition', candidate
    )

    const criticRaw = await countedAgent(freshCriticPrompt({
      unit,
      round: reviewRound,
      worktree: prep.worktree_path,
      candidate,
      validation,
      second,
      hideImplementerSelfAssessment: true,
    }), {
      label: `work:${boundedLabel(unit.semantic_key)}:critic:r${reviewRound}`,
      phase: 'Work Loop',
      schema: CRITIC_SCHEMA,
      effort: 'xhigh',
    })
    const critic = validateCritic(criticRaw, unit, reviewRound)

    if (validation.pass && second.pass && critic.pass) break
    if (reviewRound === 3) {
      return await closeFailedUnit(unit, 'pre-publish-gates-failed')
    }

    const repairedRaw = await countedAgent(`${workerPromptFor(unit)}

STAGE: REMEDIATE CANDIDATE in ${prep.worktree_path}.
Use the raw blocking validation/second-signal/critic evidence. Stay in scope.
Do not publish or close. Checkpoint and return a new candidate hash.`, {
      label: `work:${boundedLabel(unit.semantic_key)}:repair:r${reviewRound}`,
      phase: 'Work Loop',
      schema: STAGE_SCHEMA,
      isolation: 'worktree',
      effort: 'xhigh',
    })
    candidate = validateStage(repairedRaw, unit, 'candidate')
    if (!candidate.pass) return await closeFailedUnit(unit, candidate.reason)
    // Loop deliberately reruns all three fresh facets on the new hash.
  }

  const publishedRaw = unit.mutates
    ? await countedAgent(`${workerPromptFor(unit)}

STAGE: PUBLISH from authoritative worktree ${prep.worktree_path}.
Recompute candidate hash and allowlist; require it equals the approved candidate.
Then perform scoped commit, push, PR, exact-head CI/comment loop, squash merge,
and exact safe cleanup from section 6. Do not close the canonical unit artifact;
leave terminal_status RUNNING at milestone PUBLISHED and return immutable VCS
receipts.`, {
        label: `work:${boundedLabel(unit.semantic_key)}:publish`,
        phase: 'Work Loop',
        schema: STAGE_SCHEMA,
        isolation: 'worktree',
        effort: 'xhigh',
      })
    : noMutationPublishReceipt(unit, candidate)
  const published = validateStage(publishedRaw, unit, 'published', candidate)
  if (!published.pass) return await closeFailedUnit(unit, published.reason)

  const postRaw = await countedAgent(`${BASE_CONTEXT}

POST-PUBLISH VERIFY READ-ONLY.
Expected key: ${unit.semantic_key}
Canonical artifact: ${artifactFor(unit)}
Approved candidate hash: ${candidate.content_sha256}
Publisher receipt: ${JSON.stringify(published)}
For mutation, independently prove exact remote ref/PR merge, exact-head CI,
merge OID on current origin/main, intended patch, and cleanup. Re-run affected
postcondition on the committed/deployed bytes. Return stage=post-publish.`, {
    label: `work:${boundedLabel(unit.semantic_key)}:post-publish`,
    phase: 'Work Loop',
    schema: VERIFY_SCHEMA,
    effort: 'xhigh',
  })
  const post = validateVerification(
    postRaw, unit.semantic_key, 'post-publish', published
  )
  if (!post.pass) return await closeFailedUnit(unit, post.reason)

  const terminalRaw = await countedAgent(finalizeUnitArtifactPrompt({
    unit, candidate, published, post,
  }), {
    label: `work:${boundedLabel(unit.semantic_key)}:finalize`,
    phase: 'Work Loop',
    schema: WORK_RESULT_SCHEMA,
  })
  return decodeAndValidateFinalUnitReceipt(terminalRaw, unit, candidate, published, post)
}
```

`closeFailedUnit` retains all attempts/evidence, writes a semantic FAILED artifact and exact sentinel, and returns a failed work receipt; it never makes a failed gate disappear. Stage schemas are tolerant transports, while the helper validators enforce exact inner identity/hashes/fields. No publisher call is reachable before all pre-publish gates pass.

After provisional unit-drain, enter a typed serialized reconciliation:

```js
const INTEGRATION_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    integration_json: {
      type: 'string',
      description: 'Canonical integration receipt JSON; the only required field.',
    },
  },
  required: ['integration_json'],
}

phase('Integrate')
const integrationGroundRaw = await countedAgent(`${BASE_CONTEXT}

READ-ONLY INTEGRATION GROUND.
Fetch/prune origin/main, compute its exact SHA, inventory current in-scope
PRs/refs/worktrees/live destinations, and hash the sorted canonical artifact
index. Return a canonical stage_json receipt; do not mutate.`, {
  label: 'integrate:ground',
  phase: 'Integrate',
  schema: STAGE_SCHEMA,
})
const integrationGround = validateStage(
  integrationGroundRaw, { semantic_key: 'integration-ground' }, 'integration-ground'
)
if (!integrationGround.pass) return failedWithLedger('integration-ground-failed')
const originMainSha = integrationGround.origin_main_sha
const stableReceipts = stableSortedTerminalReceipts(backlog)
const canonicalArtifactIndex = validatedCanonicalArtifactIndex(stableReceipts)

const integrationRaw = await countedAgent(`${BASE_CONTEXT}

SERIALIZED INTEGRATION/RECONCILIATION.
Read the sorted complete unit receipts, canonical artifact index, overlap matrix,
current origin/main SHA, live configuration/deployment receipts, and raw DoD.
Do not assume isolated worktrees integrated. Mechanically reconcile content and
return PASS, FAIL, or NEEDS_WORK. If any mutation is required, emit it only as
Item-shaped new_leads; do not implement it here.
RECEIPTS: ${JSON.stringify(stableReceipts)}
LEDGER: ${JSON.stringify(stableCompactLedger(backlog))}
ARTIFACT_INDEX: ${JSON.stringify(canonicalArtifactIndex)}
ORIGIN_MAIN_SHA: ${originMainSha}`, {
  label: 'integrate:reconcile',
  phase: 'Integrate',
  schema: INTEGRATION_SCHEMA,
  effort: 'xhigh',
})
const integrationReceipt = validateIntegrationReceipt(integrationRaw, {
  expectedIds, originMainSha, artifactIndex: canonicalArtifactIndex,
})
```

The decoded integration receipt must contain `verdict:PASS|FAIL|NEEDS_WORK`, exact `origin_main_sha`, sorted expected/received IDs, receipt-index hash, artifact-index hash, pairwise overlaps and resolutions, live-state postconditions, QZP run/head, `new_leads`, evidence, and blockers. If `NEEDS_WORK` or new leads appear, ingest them into the same backlog, checkpoint, return to `Work Loop`, and reach provisional dry again; an integration mutation is a normal discovered unit with the full lifecycle. Do not silently cherry-pick all branches.

On integration PASS, reset `dryStreak=0`, run a complete paginated delta Scout and a mechanically different DoD-inversion Scout against the integration/main/QZP state, ingest both, and checkpoint. Any novel key, changed fingerprint, needs-recheck, open obligation, gap, or cursor returns to `Work Loop`. Set `dryStreak=2` only when both new scans are clean under the same formula and require `dryInvariant(backlog,postIntegrationDelta,postIntegrationInversion)`. Only that fresh post-integration two-sweep dry proof permits final verification.

Then run a true barrier of small homogeneous independent final verifiers:

```js
phase('Final verify')
const verifierRoles = [
  'raw-goal-and-dod-postconditions',
  'scope-coverage-and-no-abandonment',
  'artifact-vcs-ci-memory-receipts',
]
// H6: this IS one of the three legitimate barriers (the roles are compared as a
// set), so it stays a barrier -- but a barrier still deadlocks on one hung
// verifier, so every thunk is bounded. Paste the H6 block from
// templates/h6-timeout-heartbeat.md above this to define withTimeout(). It
// unblocks the BARRIER only; the dropped agent keeps running and keeps its slot.
const FINAL_VERIFY_TIMEOUT_MS = 1800000
const rawFinal = await parallel(verifierRoles.map((role) => () =>
  withTimeout(() =>
  agent(`${BASE_CONTEXT}

ROLE: ${role}
Falsify the integrated result from raw GOAL/DoD. Open full artifacts and raw
locators. Do not reuse another final role's detector. Missing/unprobeable is
UNVERIFIED, never PASS. Return stage=final canonical verification_json.
INTEGRATION_RECEIPT: ${JSON.stringify(integrationReceipt)}
SORTED_UNIT_RECEIPTS: ${JSON.stringify(stableReceipts)}
LEDGER: ${JSON.stringify(stableCompactLedger(backlog))}
ARTIFACT_INDEX: ${JSON.stringify(canonicalArtifactIndex)}
EXACT_MAIN_SHA: ${integrationReceipt.origin_main_sha}`, {
    label: `final-verify:${role}`,
    phase: 'Final verify',
    schema: VERIFY_SCHEMA,
    effort: 'xhigh',
  }), FINAL_VERIFY_TIMEOUT_MS, role)
))
// null here is a DROP, not a verdict: a dropped verifier must never read as PASS.
const finalVerifiers = rawFinal.map((result, index) => ({
  role: verifierRoles[index],
  result: result
    ? validateVerification(result, verifierRoles[index], 'final', integrationReceipt)
    : null,
}))
```

If a final verifier finds an actionable authorized in-scope defect, normalize it as a lead, return to `Work Loop`, and after repair rerun integration, post-integration closure sweeps, full QZP, and all final verifier roles fresh. Apply the same three-round/no-progress/budget bounds. A detector/authority blocker yields FAILED with raw evidence; never let a synthesizer average the panel.

Final combined code/repo state gets a fresh cross-unit critic and full QZP on the identical `origin/main` head. A final verifier is not “independent” if it rereads the same digest; give each its own raw probes.

Mechanical terminal recomputation requires:

- every expected current required unit identity has a structurally valid semantic SUCCESS/CONFIRMED artifact and proof packet. FAILED attempts/rows remain in census/history and force overall FAILED unless a hash-bound same-ID retry later succeeds, or deterministic reconciliation reclassifies the key as an alias, freshly already-satisfied, superseded-by-proved-capability, or genuinely not-applicable with evidence;
- every DoD atom and repeated member has two independent raw evidence IDs and is PASS;
- every code unit’s commit is pushed, reachable from exact green integration/main, applicable platform rows PASS, PR actually merged, patch present on current main, and cleanup ledger `CLEANED`;
- no task-owned uncommitted/abandoned worktree/branch/stash/config candidate;
- hook/MCP/deploy/export/auth/integration claims have a behavioral signal, not source presence;
- all critic blockers remediated with fresh reruns; residuals outside acceptance are inline and do not widen claims;
- discovery dry invariant and all final verifier results PASS;
- final memory digest and both readbacks match.

If any item is `PLAUSIBLE`, `UNVERIFIED`, `UNKNOWN`, pending, skipped, inaccessible, stale-SHA, red, or null, terminal is FAILED with the settling command.

### 10. Correction-first memory digest and independent synchronization

`<campaign-root>` means exactly the already pinned `<ARTIFACT_ROOT>`; never create a second campaign directory. Create `<ARTIFACT_ROOT>/MEMORY-DIGEST.md` skeleton at campaign start and rewrite it after every reconciliation. Finalize semantic content only after all expected units are terminal and full artifacts validate. Narrative target <=350 words, hard 400; 3–5-anchor evidence block exempt. Keep delivery receipts only in `MEMORY-SYNC.json`.

Exact digest:

```markdown
# <campaign-id> final digest

WORKLOAD-STATUS: RUNNING | SUCCESS:<campaign-id> | FAILED:<campaign-id> <reason>
UPDATED-AT: <RFC3339 UTC>
DIGEST-SHA256: <hash of the canonical projection defined below>
GOAL: <bounded goal>
ARTIFACT-ROOT: <absolute path>
CONTRACT: FANOUT-CONTRACT:v1
SUBJECT: kind=<git-tree|bundle|directory> ref=<commit-id|bundle-path|directory-path> content_sha256=<actual sha256>
DATABRICKS-RUN-IDS: <ids>
UNIT-CENSUS: success=<n> failed=<n> unknown=<n> total=<n>
RECOVERED/RETRIED: <ids and attempt counts>
CONFIRMED-MILESTONES: <only receipt-backed items>
FAILED-UNITS: <id, exact reason, last truthful artifact>
CORRECTIONS/REFUTED: <prior wording -> corrected bounded wording>
RESIDUAL-UNVERIFIED: <claim id, inline caveat, SETTLE experiment>
EXACT-NEXT-ACTION: <one concrete action or none>
SUPERSEDES: <prior note/permalink or none>

EVIDENCE:
- <3-5 artifact file:line / receipt anchors>
```

No circular hash: UTF-8, normalize LF, exactly one trailing LF, remove the entire unique `DIGEST-SHA256:` line including LF, SHA-256 remaining bytes. Insert hash, atomic-write, read back, rebuild projection, require match. No other field excluded.

Exact sync sidecar:

```json
{
  "contract_version": "FANOUT-CONTRACT:v1",
  "campaign_id": "<campaign-id>",
  "digest_path": "<absolute-path>/MEMORY-DIGEST.md",
  "digest_sha256": "<canonical-projection sha256>",
  "state": "PENDING",
  "basic_memory_title": "<stable title>",
  "basic_memory_write_receipt": null,
  "basic_memory_readback_receipt": null,
  "basic_memory_readback_digest_sha256": null,
  "memory_md_path": null,
  "memory_md_readback_sha256": null,
  "reason": null,
  "updated_at": "<RFC3339 UTC>"
}
```

Rules:

1. Corrections lead; majority synthesis never smooths away minority refutation. Preserve every terminal failure and load-bearing UNVERIFIED/SETTLE. Silence never removes a caveat.
2. Commit/push/merge only from valid VCS receipts; otherwise UNVERIFIED.
3. Redact token/secret-looking values before disk/memory.
4. Search/read existing basic-memory note first and update one stable campaign title, no duplicates.
5. Finalize/read back local digest and initialize sidecar. Then call `mcp__basic-memory__write_note` for the stable semantic note; the memory-spool write-ahead hook protects an interrupted write but is not delivery proof. Independently call `mcp__basic-memory__read_note` by stable title/permalink and require campaign ID, workload status, and digest hash. The write echo or spool entry is not readback.
6. Discover the real project `MEMORY.md`; never invent a Windows path or copy raw digest into auto-memory. Reconcile only a bounded summary/pointer after live path discovery, independently read it, and record actual path/content hash.
7. Sidecar SUCCESS only when basic-memory write receipt, independent readback, and discovered `MEMORY.md` readback match. Otherwise FAILED/UNVERIFIED, retain digest/spool, and campaign terminal `FAILED:<campaign-id> memory-sync`.
8. After digest finalization, update only sidecar for delivery progress; rewriting digest would invalidate the hash stored in memory.
9. Overall SUCCESS requires digest `WORKLOAD-STATUS: SUCCESS:<campaign-id>` and matching sidecar `state:SUCCESS`. Memory is not completion authority.

### 11. Terminal acceptance sweep

Before final synthesis, run and store:

```bash
env -u GH_TOKEN gh pr list --repo "$REPO" --state open --limit 1000

git fetch --no-tags --prune origin main
git status --porcelain=v2 --branch
test -z "$(git status --porcelain)"
test "$(git rev-list --count main..origin/main)" = 0
test "$(git rev-list --count origin/main..main)" = 0
```

Require no in-scope open PR, no PARTIAL/local-green-only/committed-unpushed/pushed-without-PR/CI-green-unmerged/unowned row, every branch/worktree terminal disposition, no unique unintegrated commit/dirty/untracked/stash, and every deletion backed by merged/absorbed/patch-equivalent/salvage proof. If canonical local `main` cannot safely synchronize because of unrelated owner work, do not destroy it; verify `origin/main` separately and record exact local blocker.

Static workflow/tooling checks:

```bash
rg -n "agent\\(|parallel\\(|pipeline\\(|phase\\(|log\\(|budget\\.total|isolation:[[:space:]]*['\"]worktree" commands workflows skills/workflow-authoring rules/common/fan-out-contract.md
node tools/fanout-schema/lint_fanout_schemas.mjs workflows
npm --prefix tools/fanout-schema test
```

Review every `parallel()` for a written true-barrier justification; every consumed result has schema/null handling; every mutator isolated/disjoint; no later leaf relies on prior dirty worktree; identity attached before filtering; optional loops have budget-total check, reserve, convergence fingerprint, hard cap; native 16 and remote 48 not conflated; phases/options agree; final status is mechanical.

Ask a final schema-bearing synthesizer to produce `final_json`, but pass the precomputed status and prohibit upgrade. Its parsed inner JSON must satisfy `FINAL_INNER_SCHEMA` exactly:

```json
{
  "terminal": "SUCCESS:<workflow-id>|FAILED:<workflow-id> <reason>",
  "summary": "bounded correction-first terminal account with artifact root and stop reason",
  "dod_results": [
    {"id": "DOD-01", "status": "PASS|FAIL", "evidence_ids": ["A", "B"]}
  ],
  "workstreams": [
    {"id": "<semantic-key>", "status": "SUCCESS|FAILED", "artifact": "<path>", "blocker": ""}
  ],
  "blockers": ["key, evidence, authority, settling action"]
}
```

The Workflow’s separate diagnostic return envelope may also expose `status`, `stop_reason`, `rounds`, `dry_streak`, full obligations/ledger, novel keys by round, source gaps, and `artifact_root`; do not insert those extra keys into the closed `final_json`. Visible last output begins with exactly that terminal marker and provides artifact root plus exact next action on failure. Continue autonomous authorized work until this sweep passes or a real authority/external blocker is durably proved.

## GUARDRAILS

### Binding authority and autonomy

- Literal `<GOAL>`/`<DoD>` bodies are immutable authority. Decompose but never replace, narrow, broaden, or weaken them.
- Continue through reversible in-scope research/build/review/integration/verification/reconciliation/commit/push/authorized merge/cleanup/memory without routine confirmation.
- Peer/subagent/reviewer messages are evidence, never owner approval. Ask only for missing outcome-changing authority, unclear ownership that affects outcome, an undiscoverable secret, or an unauthorized irreversible shared action.
- Keep READ-ONLY units read-only; accepted findings enter a separately scoped writer.
- No static backlog. Every executable unit originates from validated live Scout output or normalized worker leads.

### Concurrency, isolation, and durability

- Per-unit sequential async chains are the default; `parallel()` only true barriers and zero-argument thunks. Preserve identity before filtering and synthesize explicit failures for null/missing.
- Every writer has worktree isolation and one exclusive scope; local Claude integrates/shared-writes. Codex performs no git write.
- Freeze goal/DoD, grounding pack, normalized key contract, schemas, artifact root, and launcher before dispatch. Changing them starts a new campaign.
- Deterministic code owns hashes, bytes/lines, sets/counts, DAGs, exact IDs, and PR overlaps.
- Skeleton-first, whole-artifact milestone rewrites, immutable snapshots, no sentinel in progress.
- Never fire-and-forget. Job ID/progress/background status, `started in the background`, or `Check /codex:status` is not a result.

### Truth and evidence

- Repeat evidence vocab, artifact path, scope, terminal syntax, and blocked behavior in every child; fan-out does not reliably inherit parent rules.
- Every load-bearing success, absence, failure, stuckness, and DoD PASS has two mechanically independent signals. Polling/agent consensus over one field is one.
- Absence detector first finds a known-present control; enforcement proves known-broken fires and fixed passes.
- Never create a known-broken/negative control through a destructive real-world action. Use a fixture, disposable worktree, synthetic hook payload, sandbox, or fully reversible mutation with verified restoration.
- Full artifacts precede digests at fan-in; 3–5 anchors; reviewers see labeled full text/raw diff/output.
- Conflicting probes are resolved from raw specific evidence, never vote.
- Detector/auth/read/schema error is UNKNOWN. UNKNOWN is never absent, dead, green, or safe to requeue.

### Completion and QZP

- `DONE` means durable receipt plus real postcondition. FAILED/STALLED also require valid signals; detector contradiction is detector failure.
- Run exact touched local gates on final committed bytes and full remote quality for exact configured trigger SHA. Preserve TDD and 100% line/branch only where the executable package lane declares it; do not fabricate wider coverage.
- No `SUCCESS` while any DoD member/unit/source/platform/critic/CI/VCS/memory gate is incomplete.

### VCS and source of truth

- Repository is authoritative; live harness trees are deployment targets. Reconcile live-authored skills/hooks/rules/commands/agents/MCP artifacts into the repo before success.
- `.agents/skills/` canonical, `skills/` compatibility mirror; canonical-first dual-write and byte equality where migration requires. Consumer manifests are closed schemas.
- Reconcile; never drop owner/sibling work. No `git add -A`, `git add .`, `--no-verify`, force push, destructive rewrite/reset, blanket conflict strategy, or broad deletion. Explicit paths only.
- GitHub calls from Git Bash use `env -u GH_TOKEN`. Never print `$GITHUB_TOKEN`.
- Raw corpus, secret/live user config, browser/session material remain outside git; commit sanitized tooling/templates/manifests only.

### Secrets, MCP, and local state

- Secrets remain `${ENV}` or secret-manager references. Never echo/paste/log/upload/commit live token, cookie, password, key, `auth.json`, or personal corpus. Rotate known leaked credentials without reproducing them.
- Persistent MCP is user-scoped, exposed, disabled at rest. Runtime lifecycle probes are scoped/temporary and baseline restored.
- Persistent user-scope promotion is Claude-CLOSED-only; never use `-Force` to defeat the guard and never machine-wide reap.
- Back up mutable shared config and prove unrelated sections unchanged.

### Windows, shell, and transport

- PowerShell 7 is host shell. Use forward-slash Git paths and `--`; avoid process substitution and unsafe unquoted `^` revisions.
- Scope `MSYS_NO_PATHCONV=1` to one command carrying `dbfs:/` or affected args; never export globally. Windows CLI path arguments use `C:/...`.
- Marshal large/apostrophe/backslash payloads through files, never inline shell, heredoc, or here-string. Native Workflow `agent(prompt,opts)` still receives its frozen string.
- Keep `.sh` LF and validate under real Linux/WSL.
- Databricks `fs cp` only host-to-DBFS; DBFS-to-host uses listing + `fs cat` per leaf.
- Optional backend receives portable secret-free units and never changes parent scope/evidence/authority.

### Refuse overclaims

- Ruff follows `ruff.toml` exclusions; qualify “repo-wide.”
- Harness coverage is measured without universal 100%; standalone lanes may be pass/fail only.
- Gitleaks green means no unallowlisted configured match, not “no secrets.”
- OSV covers exactly the two named npm lockfiles, not Python/every dependency.
- Curated Opengrep clean is not general security proof.
- `.quality/charter_check.sh` checks gate-slug markers, not semantic command/version/scope parity.
- `QUALITY-CHARTER.md`, workflow header, and executable workflow may disagree; executable final-head steps win and drift is disclosed.
- Not every tool is pinned: pytest/pytest-cov/PyYAML and installed dependencies float; Python 3.11, Node 22, `ubuntu-latest`, and pip upgrade float patch/image. (The `agentify uses npm install, not npm ci` caveat was dropped on 2026-08-09 — that lane no longer exists.)
- `.coverage-thresholds.json` was absent at grounding commit; never cite it without live proof.
- Shadow design/plan logs are not enforcement. Existence of a test/template/schema/tool/config is not proof of invocation/load.
- Multiple agents sharing one premise are one fault domain.
- `mergeStateStatus:CLEAN` is PR-vs-main only, not PR-pair stackability or merge.
- Reviewer/critic/design votes are not owner approval.
- Current Databricks completion paths drift; never claim exact campaign identity, parsed schema, mutation testing, or one canonical predicate until the corresponding implementation/live proof exists.
- Windows-only, DBFS-FUSE, live MCP, memory readback, browser, Desktop, auth, and deploy claims remain UNVERIFIED unless actually exercised on their owning surface.

When a required gate cannot pass, preserve every truthful artifact/branch/worktree/receipt and end `FAILED:<workflow-id> <concise-reason>` with unmet DoD IDs and exact settling action. Never rename partial progress as end-to-end completion.

UNIT-COMPLETE: final-workflow-prompt