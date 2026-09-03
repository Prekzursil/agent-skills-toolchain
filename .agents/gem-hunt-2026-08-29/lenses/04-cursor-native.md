# Lens 04 — Native Cursor leverage audit

**Hunt date:** 29.08.2026  
**Recovery audit date:** 01.09.2026  
**Mode:** discovery and deduplication only. No Cursor setting, hook, model, repository,
automation, API key, MCP server, or cloud agent was changed or launched.

## Executive verdict

Cursor already supplies most of the missing execution plane natively: one SDK for local and cloud
agents, account-scoped model discovery, connected-repository discovery, custom subagents,
repository rules and hooks, durable cloud runs, per-run usage and billed cost, artifacts, and
event/schedule automations.

The estate should **ADOPT the SDK as an adapter, not as another orchestrator**, and should
**WIRE live model/repository/usage/artifact receipts into the existing acpx/event-ledger design**.
The highest-risk mistake would be enabling repo-backed Cloud Agents or Automations as though they
were read-only workers. They can edit, commit, push a branch, and open a pull request. The standing
G-68 rule says background/headless agents never commit, so mutating repo-backed cloud runs are
currently **BLOCKED-POLICY** unless the owner explicitly changes that rule.

The second critical correction is scope: `~/.cursor/hooks.json` is local user configuration and
does **not** travel to Cloud Agents. Project hooks committed at `.cursor/hooks.json`, plus
team/enterprise hooks where available, are the cloud policy boundary.

The current GLM integration is correctly an **MCP/direct-Hugging-Face-router tool**. It is not a
Cursor picker model. A raw Gradio Space or the local compatibility proxy cannot be inserted into
Cursor's native model catalog merely by naming it. Cursor model IDs and parameters must be
discovered live from `Cursor.models.list()` or `GET /v1/models`.

## Ground and dedup boundary

Read directly:

- `C:\Users\Prekzursil\AGENTS.md`
- `.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`
- every other completed lens under `.agents/gem-hunt-2026-08-29/lenses`
- live `C:\Users\Prekzursil\.cursor\hooks.json`
- live `C:\Users\Prekzursil\.cursor\mcp.json`
- live `.agents/agents.json`
- `tools/mcp/glm53-space/{README.md,mcp_server.py,glm53_core.py,pyproject.toml}`
- repository-root `AGENTS.md`
- current official Cursor documentation listed in Sources

Already built, selected, or specified, and therefore not re-proposed as new:

- local Cursor user hooks and lifecycle logging;
- the observe-mode guard calibration, log rotation/redaction work, duplicate-fire probe, and
  unread-alarm repair from lenses 08 and 12;
- cloud offload and scheduled automations from the 27.08 queue;
- project hooks, subscriptions, cloud environment manifest, and cloud-return validation from
  lenses 03 and 10;
- event denominators, cloud metrics, usage/cost semantics, and artifact re-read from lens 11;
- basic-memory as the sole semantic writer and the ban on cloud memory synchronization;
- the private-only repository invariant;
- no Cursor BYOK routing lane, OpenRouter MCP, LiteLLM, second orchestrator, or new resident daemon.

This lens adds the exact native Cursor interfaces, their configuration boundaries, the current
on-disk gaps, and the G-68 conflict that the prior cloud recommendation did not close.

## Current-state measurements

| Surface | Current evidence | Verdict |
|---|---|---|
| User hooks | `~/.cursor/hooks.json` exists with `sessionStart`, `beforeShellExecution`, `beforeMCPExecution`, `subagentStart`, `subagentStop`, and `afterFileEdit` entries | **LOCAL-BUILT**; not a cloud control |
| Project hooks | No `.cursor/hooks.json` exists in `agent-skills-toolchain` | **ABSENT** for this repo |
| Project Cursor rules | No `.cursor/rules/*.mdc` exists in this repo | **ABSENT**, but root `AGENTS.md` is present |
| Custom subagent files | No repo `.cursor/agents/*.md` and no user `~/.cursor/agents/*.md` were found | **ABSENT on disk**; built-ins/runtime-provided agents still exist |
| Repo cloud guidance | Root `AGENTS.md` has a substantial “Cursor Cloud specific instructions” section | **PRESENT**, but it does not carry the current G-68 no-headless-commit rule |
| Connected repositories | `~/.cursor/unified_repo_list.json` is `[]` | Weak local evidence only; account/team cloud connectivity is **NOT-CHECKED** |
| GLM MCP | `~/.cursor/mcp.json` launches `glm53-space` over stdio through pinned `uv --locked` | **LOCAL-LIVE** in the current Cursor tool surface |
| GLM backend | Adapter calls `https://router.huggingface.co/v1`, model `zai-org/GLM-5.3:zai-org`; text-only; result wrapped as untrusted output | **DIRECT HF ROUTER**, not Gradio and not native picker inference |
| GLM registry metadata | `.agents/agents.json` marks `glm53-space` `targets:["claude"]`, while Cursor currently loads it | **METADATA DRIFT / intentional-exception status undocumented** |
| SDK/cloud live use | No SDK API call, repository-list call, model-list call, cloud run, or automation was made | **NOT-RUN**, by scope |

The empty local repository cache does not prove that the Cursor account has no connected
repositories. The official API is the settling mechanism; no account credential was exercised in
this lens.

## Corrections to stale assumptions

1. **User hooks do not flow to cloud.** Cloud VMs cannot read `~/.cursor/hooks.json`. They load
   committed project hooks and, where supported, dashboard-managed team/enterprise hooks.
2. **Repo-backed cloud agents may commit.** Cursor's normal handoff is a separate branch with
   commits pushed to the repository; API options can also push directly to a starting branch and
   can auto-create a PR.
3. **G-68 still applies.** “Owner-invoked” does not make a background Cloud Agent interactive.
   Under the current contract, repo mutation/commit by that agent is blocked.
4. **Model names in docs are examples, not configuration truth.** Availability, IDs, aliases,
   parameters, presets, plan access, region access, and team restrictions are account-specific.
   Discover them live before each pinned-model change.
5. **Local SDK does not mean a local model.** The agent loop and files are local; inference still
   uses Cursor-hosted models.
6. **Local SDK does not automatically inherit ambient config.** Without
   `local.settingSources`, only inline MCP definitions are loaded. User/project rules, hooks,
   skills, and MCP configuration must be selected deliberately.
7. **A raw Gradio model cannot enter the native picker.** Cursor exposes its account/team model
   catalog and supported-provider BYOK controls, not an arbitrary Gradio prediction endpoint.
8. **GLM is a tool, not a picker model.** The current adapter exposes `glm53_chat` through MCP and
   calls the official HF router. The optional local `/v1` wrapper is for clients that accept a
   custom OpenAI-compatible base URL; it is not evidence of Cursor picker support.
9. **Cloud MCP is a separate configuration plane.** A cloud subagent uses MCP servers configured
   at `cursor.com/agents` or supplied inline to the SDK/API, not the local user's MCP process.
10. **Artifacts are evidence candidates, not verification.** Cloud status or an uploaded demo
    remains `agent-claimed` until downloaded, hashed, parsed, and re-read locally.

## Ranked decision queue

| # | Action | REC | Value × effort | NATIVE-vs-BUILD | Maturity | Confidence |
|---:|---|---|---|---|---|---|
| 1 | Live model/repository preflight receipt | **WIRE** | very high × low | NATIVE reads + tiny ledger adapter | SDK v1 / Cloud API beta | high |
| 2 | Safe local SDK execution profile | **ADOPT bounded** | very high × low-medium | NATIVE SDK config | SDK 1.0.27, fast-moving | high |
| 3 | G-68 cloud admission gate | **WIRE now; mutation blocked** | very high × low | BUILD-light policy over NATIVE cloud | stable estate rule; cloud hosted | very high |
| 4 | Project cloud policy capsule | **EXTEND existing cloud trial** | very high × medium | NATIVE rules/hooks/subagents | official current surfaces | high |
| 5 | Native usage and billed-cost receipt | **WIRE** | high × low | NATIVE SDK/API | current SDK/API | high |
| 6 | Artifact manifest/download verifier | **EXTEND existing verification** | very high × low-medium | NATIVE artifacts + BUILD-light verifier | cloud artifacts current | high |
| 7 | Narrow project custom subagents | **TRIAL 1–2 only** | high × low | NATIVE config | current; model fallback caveats | high |
| 8 | Automation profile without Cursor Memories | **EXTEND, policy-gated** | high × low-medium | NATIVE automation | hosted current feature | high |
| 9 | GLM MCP classification and registry repair | **KEEP + WIRE metadata** | high × trivial-low | NATIVE MCP + existing BUILD adapter | adapter 0.1.0 | very high |
| 10 | Origin API | **WATCH / NO ADOPT** | low current × medium | NATIVE alpha API | alpha | high |

## F1 — Live model and repository discovery is a mandatory preflight

**Recommendation:** WIRE.

Cursor exposes `Cursor.models.list()` in the SDK and `GET /v1/models` in the Cloud Agents API.
The response contains model IDs, supported parameters, and preset variants available to the
calling account/team. The catalog is affected by plan, region, admin restrictions, and Router
availability.

Cursor also exposes connected repositories through `Cursor.repositories.list()` and a REST
repository endpoint. The REST repository endpoint is explicitly strict-rate-limited and can take
tens of seconds for large accounts, so it is a preflight/cache input, not a per-turn call.

**Exact action**

1. Add one read-only `cursor-capability-receipt` step to the existing provider-health/acpx
   preflight.
2. Record SDK version, account/team identity hash, discovery time, available model IDs and allowed
   parameter values, repository URL hashes, and source response hash.
3. Select only an ID and parameter combination present in that receipt.
4. Prefer `model: inherit` in portable subagent files unless a measured task requires pinning.
5. On absent model/repository, report `UNAVAILABLE` or `NOT-CHECKED`; never invent a slug, silently
   substitute GLM, or guess that a dashboard connection exists.
6. Cache repository discovery within the documented rate limits; expose receipt age.

**Value × effort:** VERY HIGH × LOW.  
**NATIVE-vs-BUILD:** NATIVE discovery; BUILD-light receipt writer into the existing ledger.  
**Maturity:** SDK is at 1.0.27; Cloud Agents API v1 is public beta.  
**Confidence:** HIGH from current official SDK/API documentation.

## F2 — Use the Cursor SDK as an execution adapter, not a control plane

**Recommendation:** ADOPT as one acpx backend.

The SDK presents the same `Agent.create` / `send` / run lifecycle for:

- a local agent loop over files on disk; and
- a Cursor-hosted isolated VM with one or more cloned repositories, or no repository.

It supports cancellation, resume/state inspection, model discovery, token streams, billed usage,
cloud artifacts, custom subagents, file-based hooks, MCP configuration, and local custom tools.
That is enough to implement a Cursor adapter without adding another scheduler or orchestration
runtime.

The default local quickstart auto-approves tool calls. Current SDK 1.0.27 adds local tool
allowlists/denylists, but they do not persist across resume. Local custom tools also skip
interactive approval. Therefore a bare quickstart is incompatible with the estate's headless
safety assumptions.

**Exact action**

1. Register `cursor-sdk-local` and `cursor-sdk-cloud` as executor kinds in the already-planned
   recipe/workspace contract; do not create a new queue.
2. Local profile: set `sandboxOptions.enabled:true`; select `settingSources` explicitly; load
   `project` plus `user` only when the job is allowed to inherit local rules/hooks/MCPs.
3. Pass local `tools`/`disallowedTools` on create **and every resume**; record the effective set.
4. Require project hooks for command-level policy because SDK capability groups cannot express
   every estate deny.
5. Use idempotency/request IDs, cancellation, and terminal receipts already defined by the acpx
   schema.
6. Do not re-wrap the existing GLM MCP as an SDK custom tool; that would duplicate one working
   interface and its safety boundary.

**Value × effort:** VERY HIGH × LOW-MEDIUM.  
**NATIVE-vs-BUILD:** NATIVE SDK, thin adapter only.  
**Maturity:** SDK 1.0.27; unified TypeScript/Python releases since 1.0.24; active rapid cadence.  
**Confidence:** HIGH on capability, MEDIUM-HIGH on Windows reliability until one bounded smoke.

## F3 — Repo-backed Cloud Agents conflict with the headless no-commit rule

**Recommendation:** WIRE a hard admission decision; do not dispatch mutating repo jobs yet.

Official behavior is unambiguous:

- the cloud agent clones a connected repository;
- it works on a separate branch by default;
- it can make changes and push commits;
- `workOnCurrentBranch:true` can push directly to the starting ref;
- `autoCreatePR:true` can open a pull request;
- repo-backed Automations can also change code and open pull requests.

This corrects the stale assumption that cloud agents merely return diffs. Lens 10's proposed
“cloud jobs never commit” is not the native default and cannot be claimed without an enforced
read-only profile.

**Exact action**

1. Add `may_commit` and `execution_surface` to the existing Workspace/recipe admission record.
2. Resolve current policy as:
   - `headless/cloud + may_commit:true` → `BLOCKED_POLICY_G68`;
   - `headless/cloud + no repository` → eligible for non-repo analysis subject to data routing;
   - `headless/cloud + repository + read-only task` → trial only after project hooks deny edits and
     git writes, with no artifact asserting mutation;
   - mutating cloud execution → requires an explicit owner decision that amends or creates an
     exception to G-68.
3. Force `workOnCurrentBranch:false` and `autoCreatePR:false` in every trial. These reduce blast
   radius but do not override the no-commit rule.
4. Never use a Cloud Agent to change repository visibility; private-only remains a blocking
   invariant.
5. Do not represent a prompt instruction as enforcement. A repo hook/permission receipt must show
   that write and git paths were actually denied.

**Value × effort:** VERY HIGH × LOW.  
**NATIVE-vs-BUILD:** BUILD-light policy wrapper around NATIVE cloud behavior.  
**Maturity:** Cloud Agents are a current hosted feature; API v1 remains public beta.  
**Confidence:** VERY HIGH: official overview and API both describe branch push/PR behavior.

## F4 — Project-native configuration is the portable cloud capsule

**Recommendation:** EXTEND the already-selected cloud-offload trial.

The repo has cloud-specific `AGENTS.md` instructions, but no `.cursor/hooks.json`,
`.cursor/rules/*.mdc`, or `.cursor/agents/*.md`. The local user's hooks and MCP processes are not a
substitute.

**Exact action**

1. Keep repository-specific setup/testing facts in root/nested `AGENTS.md`; do not copy the full
   home contract into the repo.
2. Put narrow file-scoped conventions in `.cursor/rules/*.mdc` only when metadata/globs add value.
   Keep ordinary instructions in `AGENTS.md`; avoid a second prose SSOT.
3. Carry estate-wide cloud rules through a Cursor Team Rule where the plan supports it, or through
   a generated, hash-checked repo policy fragment if a dashboard rule is unavailable. Unknown
   policy load is `NOT-CHECKED`, not “inherited from home.”
4. Add a project `.cursor/hooks.json` only for the existing cloud trial. Use scripts committed
   under `.cursor/hooks/` and paths relative to the repo root.
5. Do not depend on cloud `beforeMCPExecution`: current hook documentation marks MCP pre/post hooks
   deferred for cloud. Use `preToolUse` matching `MCP:<tool>` for cloud MCP policy.
6. Do not depend on IDE-only `workspaceOpen`, Tab hooks, or `sessionEnd` in cloud.
7. Add a direct G-68 statement to cloud policy and a mechanical git-write deny before any
   repo-backed trial. The current repo `AGENTS.md` does not carry that standing rule.

**Value × effort:** VERY HIGH × MEDIUM.  
**NATIVE-vs-BUILD:** NATIVE project rules/hooks/agents, small scripts only.  
**Maturity:** rules and command hooks are current supported features; cloud hook support is a
documented subset.  
**Confidence:** HIGH.

## F5 — Custom subagents are useful only as a thin project layer

**Recommendation:** TRIAL one read-only verifier and at most one project specialist.

Cursor loads custom subagents from `.cursor/agents/*.md` in the repository and makes them
available in editor, CLI, SDK, and Cloud Agents. A project file can specify `readonly`,
`is_background`, `model`, description, and prompt. User-level subagents are local-user scope;
project files are the portable cloud form.

The estate already exposes many specialist subagents and has 380 shared skills. Mirroring them all
into `.cursor/agents` would create prompt drift and a second catalog.

**Exact action**

1. Start with `.cursor/agents/project-verifier.md` only when the repo-backed cloud trial is
   approved.
2. Set `readonly:true`, `model:inherit`, and a narrow description; require structured evidence
   pointers and `UNIT-COMPLETE`, but do not let it self-certify.
3. Keep implementation roles in the existing orchestrator. Add a second project subagent only
   after a measured recurring context-isolation need.
4. Run `Cursor.models.list()` before replacing `inherit` with a model ID.
5. Use `subagentStart`/`subagentStop` project hooks for lifecycle receipts. A background subagent
   is still headless and remains subject to G-68.

**Value × effort:** HIGH × LOW.  
**NATIVE-vs-BUILD:** NATIVE Markdown configuration.  
**Maturity:** official current feature; model override may fall back under plan/admin restrictions.  
**Confidence:** HIGH.

## F6 — Use native usage and billed cost; do not infer dollars from token events

**Recommendation:** WIRE into lens 11's existing usage schema.

The SDK exposes:

- live/cumulative token counts on run streams/results; and
- `agent.getUsage()` / `agent.get_usage()` for server-derived billed usage and dollar cost.

Cloud usage is per run; current SDK 1.0.27 also supports local per-turn billed usage. Billing can
take a short time to settle. SDK runs share Cursor pricing pools and appear under the SDK tag in
the usage dashboard.

**Exact action**

1. Emit live token events as `source=cursor-run`, `cost_semantics=token-count-only`.
2. After terminal status plus a bounded settlement retry, fetch billed usage and cost; emit
   `source=cursor-getUsage`, currency, run ID, and receipt timestamp.
3. Keep failures and unverified runs in the cost numerator.
4. Record the resolved model returned by the run, not merely the requested model.
5. Do not merge Cursor subscription pool usage, billed API cost, and ccusage estimates into one
   number.
6. Set dashboard spend limits before cloud/automation trials; no automatic spend-limit mutation is
   proposed here.

**Value × effort:** HIGH × LOW.  
**NATIVE-vs-BUILD:** NATIVE usage APIs, existing ledger adapter.  
**Maturity:** current SDK/API; cost settlement is eventually consistent.  
**Confidence:** HIGH.

## F7 — Cloud artifacts should be downloaded, authenticated, and kept out of public PR embeds

**Recommendation:** EXTEND the existing disk-authentication/verification work.

Cloud Agents create screenshots, videos, and logs. The SDK/API can list and download agent-scoped
artifacts under the workspace `artifacts/` directory. Local agents do not implement artifact
download.

Cursor can optionally embed artifact links in GitHub PR descriptions. The official docs state that
GitHub's image proxy requires public URLs, so those links are long and unguessable but viewable
without authentication. That is a poor default for a private repository containing personal
harness material.

**Exact action**

1. Keep “Allow posting artifacts to GitHub” disabled for `agent-skills-toolchain`.
2. Require a cloud completion manifest listing expected relative artifact paths, type, byte count,
   and producer run ID.
3. Download via the SDK/API; enforce the `artifacts/` path boundary; hash and parse each expected
   artifact locally.
4. Apply type-specific predicates: valid image/video/log structure, required sentinel/schema,
   nonempty content, and run/timestamp linkage.
5. Record `disk-authenticated` only after those checks. Provider status, PR attachment, or
   `artifact_created` is not completion evidence.
6. Keep sensitive screenshots/videos local; do not publish a public-URL embed merely for a nicer
   PR description.

**Value × effort:** VERY HIGH × LOW-MEDIUM.  
**NATIVE-vs-BUILD:** NATIVE artifact transport; BUILD-light validator on the existing provenance
bus.  
**Maturity:** current Cloud Agent/SDK capability.  
**Confidence:** HIGH.

## F8 — Automations are powerful, but their defaults conflict with two estate rules

**Recommendation:** EXTEND the existing automation decision; do not activate one from this lens.

Automations can trigger on schedules, GitHub/GitLab/Bitbucket events, Slack, webhooks, Linear,
Sentry, and PagerDuty. They can run with no repository, one repository, or a multi-repo
environment. Repo-backed runs can edit code and open PRs.

Cursor Automation Memories are enabled by default and let the agent read/write persistent notes
outside the working filesystem. That is a second semantic writer and conflicts with G-81.

**Exact action**

1. For every new automation, set `cursor_memories:false`; persistent knowledge must remain in
   basic-memory through the existing approved publication path.
2. Classify automation identity as Private, Team Visible, or Team Owned and record who pays and
   which external identity acts.
3. Under current G-68, permit only no-repo or mechanically read-only automations. A repo-mutating
   automation is `BLOCKED_POLICY_G68`.
4. Require explicit tool allowlists, event provenance/deduplication, repository selection, spend
   ceiling, terminal artifact contract, and external-send scope.
5. Do not create an automation merely to duplicate native Cloud Agent subscriptions or `/loop`.
6. Multi-repo long-running support is currently limited; do not infer feature parity from
   single-repo agents.

**Value × effort:** HIGH × LOW-MEDIUM.  
**NATIVE-vs-BUILD:** NATIVE automation with existing policy/receipt adapters.  
**Maturity:** hosted current feature; trigger/provider support varies.  
**Confidence:** HIGH from current official Automations documentation.

## F9 — Keep GLM as the current MCP/direct-HF tool

**Recommendation:** KEEP; WIRE registry truth; do not pursue picker injection.

The live integration is well bounded:

- Cursor starts a local stdio MCP server with pinned project dependencies;
- the tool accepts separate user and blank-default system prompts;
- `glm53_core.py` calls Hugging Face's official OpenAI-compatible router directly;
- the third-party Gradio Space is bypassed;
- model output is explicitly wrapped as untrusted;
- the adapter is text-only and forbids private/secrets use in its documentation;
- the optional loopback `/v1` wrapper is manual and nonpersistent.

The remaining issue is control-plane truth. `.agents/agents.json` says `targets:["claude"]`, while
the current Cursor config and tool surface contain `glm53-space`.

**Exact action**

1. Decide in the next sync/config wave whether Cursor GLM is a supported target or an intentional
   local-only exception.
2. If supported, add `cursor` to the canonical target metadata and verify
   `sync_shared_state.ps1` reproduces the same non-secret MCP definition.
3. If exceptional, record `local_cursor_exception:true` in the control-plane receipt rather than
   letting the target list lie. Do not invent a consumer-manifest key if its schema is closed;
   use the established provenance sidecar.
4. Add one conformance receipt: MCP initialize/list-tools, schema check, synthetic public prompt,
   returned upstream model ID, and absence of secret values in output/logs.
5. Keep it local. The current stdio command references a Windows path and a local token
   environment, so it is not cloud-portable.
6. If cloud GLM access ever becomes necessary, review an authenticated HTTP MCP deployment as a
   separate data-egress decision. Do not copy the local stdio token into a cloud VM.
7. Never claim `glm-5.3-custom` is a Cursor model ID. Only the live Cursor catalog can establish
   picker eligibility.

**Value × effort:** HIGH × TRIVIAL-LOW.  
**NATIVE-vs-BUILD:** Cursor's MCP support is NATIVE; the GLM adapter is an existing BUILD.  
**Maturity:** adapter 0.1.0 with tests; HF router is official; local-to-cloud portability is absent.  
**Confidence:** VERY HIGH from direct source/config reads.

## F10 — Rules should be scoped; the home contract is not a cloud payload

**Recommendation:** EXTEND, not duplicate.

Cursor supports:

- project `.cursor/rules/*.mdc`;
- root and nested `AGENTS.md`;
- User Rules;
- Team Rules, with team-managed precedence and enforcement.

Cloud Agents read repository `AGENTS.md` and repo rules. Current official best practices also
describe user/team rules for cloud sessions. None of that means the Windows home
`C:\Users\Prekzursil\AGENTS.md` is mounted into a cloud VM.

**Exact action**

1. Keep the home contract canonical for local runtimes.
2. Keep root/nested repo `AGENTS.md` focused on repository and cloud setup.
3. Put only the minimal estate-wide cloud invariants into an enforced Team Rule where available:
   private-only, no credential rotation, no headless commits, no force/no-verify, no secret
   publication, fail-closed completion.
4. If Team Rules are unavailable, generate a short repo policy projection with source hash and
   drift test. It is a deployment projection, not a second editable SSOT.
5. Do not add `.cursor/rules` merely to copy existing `AGENTS.md`; use it for genuinely scoped
   metadata/glob behavior.

**Value × effort:** HIGH × LOW.  
**NATIVE-vs-BUILD:** NATIVE rule layers, tiny sync/drift adapter.  
**Maturity:** mature Cursor configuration surface.  
**Confidence:** HIGH.

## Native-vs-build boundary

| Need | Use natively | Build only |
|---|---|---|
| Agent execution | Cursor SDK local/cloud runtime | Thin acpx adapter |
| Model selection | `models.list()` / `/v1/models`; `inherit` | Receipt/cache, never model slugs |
| Repository selection | connected-repository list, cloud environments | Admission and privacy policy |
| Specialized workers | built-ins + 1–2 project subagents | Project prompts, no second catalog |
| Policy | Team/User/Project Rules, `AGENTS.md`, project hooks | Generated projection and drift test |
| Shell/MCP gating | supported command hooks / `preToolUse` | Estate classifiers and receipts |
| Usage/cost | run token usage + `getUsage()` | Existing ledger normalization |
| Artifacts | cloud artifact list/download | Hash/schema/content authentication |
| Scheduling/events | Automations and Subscriptions | Existing event authenticity/dedup fields |
| GLM | local MCP tool calling official HF router | Existing adapter only; no picker shim |
| Semantic memory | none from Cursor for this estate | No build; basic-memory remains sole writer |
| Orchestration | none additional | No build; metaswarm/acpx remains owner |

## Maturity summary

| Surface | Maturity |
|---|---|
| TypeScript/Python SDK | v1.0.27, official and active; rapid interface evolution |
| Cloud Agents | Current paid hosted capability |
| Cloud Agents REST API v1 | Public beta; schemas may change before GA |
| Hooks | Official current surface; cloud supports a documented command-hook subset |
| Custom subagents | Official editor/CLI/cloud feature; model availability may force fallback |
| Rules / AGENTS.md | Established configuration surface |
| Automations | Current hosted capability; provider/plan/identity differences matter |
| Artifact APIs | Current cloud-only SDK/API surface |
| Origin API | Alpha; unnecessary for this adoption path |
| GLM adapter | Estate-owned 0.1.0 tool; local only; official HF inference backend |

## Adoption sequence

1. **Receipt first:** live models + repositories + SDK version, no agent launched.
2. **Local SDK smoke:** read-only task, sandbox on, explicit setting sources and tool policy,
   usage/cost receipt, no custom tool.
3. **Project capsule:** reconcile root `AGENTS.md`; add the minimal project hooks and one read-only
   verifier only after review.
4. **Cloud read-only trial:** G-68 admission pass, `workOnCurrentBranch:false`,
   `autoCreatePR:false`, no user-hook assumption, no local GLM assumption.
5. **Artifact return:** download, authenticate, and locally verify; keep public PR artifact embeds
   off.
6. **Automation later:** Memories off, no-repo/read-only under current policy, spend and external
   action limits explicit.
7. **GLM metadata repair:** classify Cursor support in the canonical target/provenance record; keep
   MCP/direct-HF routing unchanged.

## Explicit rejects

- **No raw Gradio Space in Cursor's model picker.**
- **No claim that `glm-5.3-custom` is a Cursor model ID.**
- **No hard-coded model ID without a live catalog receipt.**
- **No assumption that user hooks or local MCPs exist in cloud.**
- **No mutating repo-backed Cloud Agent or Automation while G-68 remains unchanged.**
- **No `workOnCurrentBranch:true` in a trial.**
- **No Cursor Automation Memories; basic-memory remains sole semantic writer.**
- **No public GitHub artifact embeds for private harness material.**
- **No duplicate GLM SDK custom tool, model proxy, orchestrator, scheduler, or memory plane.**
- **No adoption of the alpha Origin API merely because it is native.**

## Sources

Official Cursor documentation, accessed 01.09.2026:

- SDK overview and TypeScript API: https://cursor.com/docs/sdk/typescript
- Python SDK: https://cursor.com/docs/sdk/python
- SDK changelog: https://cursor.com/docs/sdk/changelog
- Cloud Agents overview: https://cursor.com/docs/cloud-agent
- Cloud capabilities, MCP, artifacts, subscriptions: https://cursor.com/docs/cloud-agent/capabilities
- Cloud Agent API v1, models, repos, usage, artifacts: https://cursor.com/docs/cloud-agent/api/endpoints
- Cloud setup and repository `AGENTS.md`: https://cursor.com/docs/cloud-agent/setup
- Cloud best practices and rule scopes: https://cursor.com/docs/cloud-agent/best-practices
- Automations: https://cursor.com/docs/cloud-agent/automations
- Hooks and cloud support matrix: https://cursor.com/docs/hooks
- Custom subagents: https://cursor.com/docs/subagents
- Rules and nested `AGENTS.md`: https://cursor.com/docs/rules
- Models and pricing: https://cursor.com/docs/models-and-pricing
- API maturity/availability: https://cursor.com/docs/api
- Region/model availability and supported-provider BYOK boundary:
  https://cursor.com/docs/account/regions
- Enterprise model/BYOK controls:
  https://cursor.com/docs/enterprise/model-and-integration-management

Local evidence is limited to the paths named under Ground. No secret value, account model list,
connected-repository list, cloud run, billed-use record, or automation configuration was read or
changed.

UNIT-COMPLETE: lens-04
