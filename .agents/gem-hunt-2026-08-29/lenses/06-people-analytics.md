# Lens 06 — Grounded People Analytics capability and plugin-router audit

**Date:** 29.08.2026  
**Mode:** design and conceptual audit only  
**Execution status:** `NOT-RUN` — no People Analytics metric query was supplied, no authenticated
Looker tool is exposed in this session, and no result is represented below as measured data.

## Executive verdict

The supplied `people-analytics` skill is a useful **context router**, but it is not yet a safe
People Analytics capability. It can select one or more topic guides from keywords and then delegates
to a Looker terminal subskill. It does not, by itself, establish a canonical metric, authorize the
request, prove that the semantic model exists, execute a query, validate data quality, or prevent
small-group disclosure.

**Recommendation: EXTEND, do not directly adopt as an answer engine.**

1. Keep the lightweight domain router.
2. Put versioned metric contracts and a policy gate between routing and Looker.
3. Treat Looker as the canonical execution/authorization boundary if it is the estate's existing BI
   layer; do not add a second BI service, observability SaaS, resident daemon, or generic DB MCP.
4. Permit only exact, allowlisted semantic-model queries through a least-privilege, read-only Looker
   identity.
5. Return `BLOCKED`, `NOT-RUN`, or `UNVERIFIED` when any capability, authorization, semantic,
   freshness, test, or privacy prerequisite is absent.
6. Never infer employee-level recommendations, rankings, disciplinary conclusions, promotion,
   termination, or compensation decisions from this workflow.

This fits the estate decisions: one shared skill SSOT, on-demand tools, no new always-on process,
no second observability system, no secrets in source, and fail-closed completion claims backed by
artifacts.

## Grounding and dedup

### Verified inputs

- The supplied router text names six guide families: foundation/headcount, terminations/attrition,
  office attendance, performance review, compensation, and open positions/planned headcount.
- The router has no cross-vertical redirects and no structured analyses.
- One or more keyword rows may match; all matching guides are to be loaded.
- The terminal step always delegates to `people-analytics-looker/SKILL.md`.
- Its output confidence is derived from whether a guide, exact semantic field, alias, or raw schema
  was used.
- The router is generated from `config/domain_context/domains/people-analytics.yml`; the generated
  file must not be edited directly.
- Direct reads of the router, all six guide files, and the Looker terminal subskill at the plugin
  cache path were attempted in this session and returned `Permission denied`.
- The current tool surface exposes no authenticated Looker query or metadata tool.

The router text is therefore verified from the user-supplied attachment; the guide and terminal
internals are not verified.

### Estate constraints carried forward

- `.agents\skills` remains the single skill/prompt source of truth. Materialized Claude/Codex
  targets are not hand-edited.
- No DB MCP is started merely for a design exercise. A real, authorized data task must exist first.
- No new resident process is justified; the Looker adapter should be invoked on demand.
- Existing event-ledger/AgentsView-style receipts should be reused. Do not introduce a second
  telemetry SaaS.
- Completion is fail-closed: an agent statement, an HTTP exit code, or a loaded guide is not a
  successful analytics result.
- No credentials or result data belong in the repo, skill body, prompt, event ledger, or
  basic-memory.

### Not duplicates of the 27.08.2026 queue

This lens does not re-propose a vector store, second orchestrator, DB MCP, OpenRouter MCP, Sentry,
LangGraph, or a general metric telemetry substrate. It specifies a domain contract and a guarded
adapter that ride the existing skill/tool/ledger buses. Per-hook ISR and general evaluation metrics
remain separate planned work.

## Conceptual audit of the supplied router

| Router behavior | Assessment | Required correction |
|---|---|---|
| Generated single routing source | Good provenance pattern, but edits to the generated file will be lost. | Change the YAML generator source, test generated output, and record generator/version hashes. |
| Keyword-first guide selection | Cheap and understandable, but brittle to negation, compound questions, Romanian phrasing, spelling, and unseen synonyms. | Add normalized intents and deterministic router tests; ask one disambiguation question when materially different contracts match. |
| Load all matching guides | Correct for genuine compound questions. It can also load conflicting definitions. | Require every guide to emit canonical `metric_id` candidates; reject conflicting grains, scopes, or denominator definitions. |
| No structured analyses | Honest, but there is no reusable path for common governed requests. | Add request templates only after metric contracts and privacy tests pass. |
| Mandatory terminal step | Unsafe for definition, policy, catalog, and “what can you answer?” questions; it can cause needless data access. | Branch into `DEFINE`, `CATALOG`, `PLAN`, and `EXECUTE`; only `EXECUTE` may invoke Looker. |
| Unmatched request can infer from raw schema | High risk of plausible but inconsistent joins and denominators. | Remove raw-schema answer fallback. Return `UNMODELED` with the missing contract/model element. |
| “High” when a guide was loaded | Conflates routing evidence with metric correctness and successful execution. | Replace with multi-axis confidence and an explicit result state. |
| Alias produces “Medium” | Reasonable as route evidence, but aliases may map to materially different metrics such as attrition versus turnover. | Keep an alias registry with one-to-one mappings; ambiguous aliases require clarification. |
| Low confidence recommends higher reasoning effort | More reasoning cannot fix missing authorization, missing semantics, stale data, or inaccessible tools. | Name the actual settling action: authorize, bind a metric, refresh data, run tests, or clarify scope. |
| Local-path “Context consulted” footer | Useful debugging, but it is not data lineage and leaks implementation paths into normal output. | Emit logical artifact IDs, versions, model commit, metric version, and test timestamp; retain local paths only in restricted debug logs. |
| Feedback points to `#ai-analytics-support` | Organization-specific and not necessarily available in this estate. | Route feedback through the existing issue/event-ledger workflow, without query results or PII. |
| No explicit preflight | Tool presence, auth, model access, policy, and freshness can fail after intent routing. | Add a capability probe and fail before query compilation. |
| No privacy/result validator in the visible router | People data can be identifying even when aggregated. | Enforce row/field access and small-group controls before results reach the model. |

## Proposed capability: one guarded gateway over the existing semantic layer

### Artifact layout if adopted

Create an estate-owned, uniquely named gateway rather than modifying plugin-cache files:

```text
.agents/skills/people-analytics-gateway/
  SKILL.md
  references/
    metric-contracts.yml
    alias-registry.yml
    privacy-policy.yml
    access-matrix.yml
    query-receipt.schema.json
  tests/
    router-cases.yml
    synthetic-workforce-fixture.yml
    expected-metrics.yml
```

The gateway may call the upstream plugin only when that plugin is readable and enabled. Formulas
live in the semantic model and versioned contracts, not in prose prompts. If dbt/MetricFlow already
feeds Looker, the registry references those metric names; it must not create a competing definition.
If Looker is the only semantic layer, LookML remains canonical.

After an approved implementation, synchronize from `.agents` using the existing shared-state
workflow. Do not copy inaccessible plugin internals, edit generated cache files, or store Looker
credentials in these artifacts.

### Request path

```text
natural-language request
  -> intent router
  -> canonical MetricRequest
  -> purpose + role + privacy policy gate
  -> exact metric/model resolver
  -> read-only Looker adapter
  -> schema/freshness/reconciliation validator
  -> semantic-layer small-group enforcement
  -> narrative renderer
  -> metadata-only receipt
```

No step may silently fall back to raw SQL, text-to-SQL, a broader Explore, a less restrictive role,
or unsuppressed rows.

### Capability states

The gateway returns one of these states before any analytical prose:

| State | Meaning |
|---|---|
| `CATALOG_ONLY` | Definitions can be explained; query execution was not requested. |
| `UNMODELED` | No exact approved metric contract or valid join path exists. |
| `BLOCKED_PLUGIN_PERMISSION` | Required plugin guide or terminal subskill cannot be read. |
| `BLOCKED_TOOL_UNAVAILABLE` | No Looker adapter is present in the active session. |
| `BLOCKED_AUTH` | Authentication is absent or rejected. |
| `BLOCKED_ACCESS` | Identity lacks the required model, row, field, or action permission. |
| `BLOCKED_POLICY` | Purpose, privacy threshold, DPIA/legal, or role policy rejects the request. |
| `READY_READ_ONLY` | All preflight checks passed; no query has run yet. |
| `EXECUTED_VALIDATED` | Query ran and result, freshness, semantic, privacy, and tests all validated. |
| `FAILED_TO_RUN` | Execution started but did not reach a validated terminal result. |

Only `EXECUTED_VALIDATED` permits factual statements about current workforce data.

### Canonical `MetricRequest`

The LLM produces a constrained object, not SQL:

```json
{
  "request_id": "<opaque-id>",
  "purpose_code": "workforce_planning",
  "metric_ids": ["active_employee_headcount"],
  "metric_versions": ["1.0.0"],
  "time": {"mode": "as_of", "as_of": "YYYY-MM-DD", "timezone": "Europe/Bucharest"},
  "group_by": ["department"],
  "filters": {},
  "comparison": null,
  "output": {"format": "table", "max_rows": 100}
}
```

The adapter fills model/Explore/field names only from the approved registry. Unknown properties,
unapproved filters, individual identifiers, uncontrolled free-form SQL, excessive row limits, and
unsupported joins are rejected.

### Metric-contract schema

Every metric needs all of the following before it can become `approved`:

- `metric_id`, semantic version, status, owner, steward, approval date, change log;
- question answered, unit, grain, primary entity, additivity, and permitted comparisons;
- numerator, denominator, effective-date logic, inclusion/exclusion rules, null policy;
- workforce scope (`core_employee`, `all_worker`, `contingent`, or another explicit class);
- time mode (`event`, `period`, `snapshot`), calendar, timezone, and period boundary convention;
- source models and exact LookML/dbt metric names; approved join path and relationship cardinality;
- allowed dimensions/filters and prohibited combinations;
- legal/purpose codes, minimum role, sensitive/special-category flags;
- minimum distinct-person threshold, complementary suppression, rounding, export policy;
- freshness SLO, reconciliation source/tolerance, tests, known limitations;
- deprecation/supersession link. A version change is required for semantic changes.

## Initial metric contracts

These are proposed definitions, not claims about the inaccessible plugin guides or source data.
Data owners must approve source mappings and policy choices.

### Workforce composition

**`active_employee_headcount`**

- Grain: one employment relationship at an `as_of` date, deduplicated to distinct `worker_id`.
- Normalized date convention: `employment_start_date <= as_of` and
  `employment_end_exclusive_date > as_of` or null. A source storing “last active date” must be
  transformed explicitly.
- Includes active employees on approved leave; excludes candidates, ended relationships, and
  contingent workers.
- Unit: people, integer. Never sum daily snapshots across time.

**`active_all_worker_headcount`**

- Same effective-date convention, but includes approved worker classes defined in the contract.
- Must always expose `worker_class`; it is not a synonym for employee headcount.

**`fte_as_of`**

- Sum of effective scheduled contractual hours divided by locale/calendar-specific standard
  full-time hours at the snapshot date.
- Multiple assignments are consolidated by worker. The contract must declare whether FTE above
  1.0 is valid or capped; no silent cap is allowed.

**`hires`**

- Distinct workers whose effective hire/rehire event falls inside `[period_start, period_end)`.
- First hires and rehires are separate dimensions; backdated corrections follow the source
  effective date and are flagged in restatement metadata.

### Terminations and attrition

**`terminations`**

- Distinct effective termination events in `[period_start, period_end)`.
- Overall, voluntary, involuntary, and regrettable are separate governed measures. “Attrition,”
  “turnover,” and “termination” are not interchangeable aliases.

**`monthly_overall_turnover_rate`**

- Numerator: all terminations effective in the month.
- Denominator: `(active headcount at month start + active headcount at month end) / 2`.
- Annual ISO-style reporting is a separately named metric that sums the twelve monthly rates;
  a rolling-period leavers/average-daily-headcount measure must have a different ID.

**`new_hire_turnover_rate`**

- Numerator: hires from a declared cohort who terminate inside a declared horizon.
- Denominator: eligible hires in that cohort.
- Cohort start, horizon, rehire behavior, and right-censoring must be visible in every output.

### Attendance and absence

**`required_office_days`**

- Worker-local scheduled days designated as office-required.
- Excludes public holidays, approved leave, non-working days, and workers/periods not covered by
  the policy.

**`attended_required_office_days`**

- Distinct `worker_id + local_calendar_date` with at least one qualifying physical-office event on
  a required day. Duplicate badge events do not increase the count.
- Badge/location data are monitoring data; raw events never reach the LLM.

**`office_attendance_compliance_rate`**

- `attended_required_office_days / required_office_days`.
- Day-weighted compliance and “share of workers meeting policy” are different metrics and must not
  be merged.

**`absence_rate_hours`**

- Approved/recorded absent scheduled hours divided by eligible scheduled working hours.
- Leave categories, sickness, parental leave, unpaid leave, and unknown absence require explicit
  inclusion rules. Attendance is not a proxy for performance.

### Performance

**`review_completion_rate`**

- Completed final reviews divided by eligible assigned reviews in one named cycle.
- Draft, cancelled, duplicate, and ineligible reviews are excluded by explicit status mapping.

**`performance_rating_distribution`**

- Distinct completed reviews by final rating within one rating scale and cycle.
- Do not average or trend across changed scales without an approved crosswalk.
- No employee-level ranking, inferred “talent density,” promotion recommendation, or disciplinary
  use is permitted through the general gateway.

### Compensation

**`annualized_base_pay_fte`**

- Effective annual base pay normalized to full-time equivalent, retaining source currency and an
  explicitly dated approved FX source for reporting currency.
- Excludes bonus, equity, allowances, employer taxes, and benefits unless a separately named total
  compensation metric includes them.

**`compa_ratio`**

- `annualized_base_pay_fte / effective salary_range_midpoint` for the same job, grade, market,
  currency, and effective date.
- Missing or invalid range midpoints yield null with a counted data-quality exception, never zero.
- Report median and quantiles for groups; no individual salary reaches the general LLM context.

### Open positions and planned headcount

**`approved_open_requisitions_as_of`**

- Distinct requisition IDs approved and in an open/recruiting state at the snapshot date.
- Draft, cancelled, filled, and policy-defined on-hold states are excluded.

**`open_requisition_age_days`**

- Snapshot date minus approved/open date, with pauses handled by an explicit policy.
- Median and age bands are preferred to an unqualified mean.

**`planned_headcount_as_of`**

- Count of approved budgeted positions at the snapshot date.
- It is not automatically `active headcount + open requisitions`; double-counting/backfill rules
  must be defined by Finance and People owners.

## Privacy, legal, and access controls

### Policy baseline

- Apply GDPR purpose limitation, data minimization, accuracy, storage limitation, integrity, and
  confidentiality. Use privacy by design/default and role-based least privilege.
- Perform a DPIA before high-risk worker monitoring, profiling, special-category processing, or
  analytics used for significant employment decisions.
- For Romanian electronic-communication/video workplace monitoring, Article 5 of Law 190/2018
  adds cumulative conditions including justified legitimate interest, complete prior notice,
  employee-representative consultation, proof that less intrusive means were ineffective, and a
  normally 30-day retention ceiling. That 30-day rule must not be carelessly generalized to every
  HR record; legal counsel/DPO must map it to each source and purpose.
- GDPR consent is generally a weak employment basis because of the power imbalance. The controller
  must document the actual lawful basis and purpose.
- Solely automated decisions with legal or similarly significant effects are outside this
  descriptive gateway. EU AI Act employment systems for recruiting, work allocation, promotion,
  termination, or performance monitoring can be high-risk and need a separate governed program.

This is an engineering control proposal, not legal advice.

### Disclosure controls

- Proposed estate baseline, subject to DPO approval: suppress groups with fewer than **5 distinct
  people** for headcount/turnover/attendance and fewer than **10 distinct people or eligible
  responses** for compensation/performance.
- These are policy defaults, not statutory thresholds. Thresholds count unique people, not event or
  review rows.
- Apply suppression in the governed semantic/database layer before the result reaches the model.
- Use complementary/secondary suppression so totals cannot reveal a suppressed cell by subtraction.
- Block repeated differencing attacks across adjacent dates, nested org levels, or filter
  combinations; coarsen dimensions and periods where necessary.
- Hide labels for tiny groups when the category itself is identifying. Round counts for broad
  management audiences where exact counts are unnecessary.
- Null, suppressed, not applicable, and zero are four different states.
- Disable unrestricted downloads, “all results,” public links, external schedules, and arbitrary
  delivery destinations by default. A narrative answer must not include employee IDs, names,
  emails, addresses, exact birth dates, free-text reviews, raw badge events, health data, union
  status, or other special-category data.

### Looker controls

- Use a dedicated non-admin API identity with only `access_data`-equivalent read capability for the
  approved People model/Explores. Credentials remain outside source and execute with that user's
  permissions.
- Restrict datasets with model sets and feature actions with permission sets.
- Put `access_filter` on **every** People Explore requiring row-level organization scope, backed by
  server-controlled user attributes. Missing attributes fail closed.
- Use `access_grant`/`required_access_grants` for sensitive Explores, joins, views, and fields,
  especially compensation and restricted performance data. A hidden field alone is not security.
- User attributes used for grants must not be user-editable.
- Correct primary keys and join relationships are mandatory; symmetric aggregates do not repair an
  incorrect key or semantic grain.
- If aggregate tables are used, include access-filter dimensions so aggregate awareness cannot
  bypass row policy.
- API query construction must set opaque `filter_config` to null, use production models, impose a
  bounded row limit/timeout, and request structured results. The adapter must not request SQL
  output or pass arbitrary field names.
- Log metadata only: request ID, actor/role, purpose, canonical metric/version, model commit,
  filter/dimension hashes, execution state, row count, suppression count, freshness, test receipt,
  and timestamps. Do not log tokens, query result values, PII, or secrets.

### Minimum role matrix

| Role | Default access |
|---|---|
| General manager | Suppressed aggregates for authorized org scope; no individual rows or sensitive fields. |
| Line manager | Suppressed aggregates for assigned reporting scope; no compensation unless separately granted. |
| HR business partner | Authorized organization scope; governed aggregates and approved operational drill paths. |
| Compensation/payroll specialist | Restricted compensation Explore and approved fields; exports separately controlled and audited. |
| Recruiter/workforce planner | Requisition/planned-headcount data; no unrelated performance or compensation data. |
| DPO/auditor | Policy, access, and metadata receipts; data values only where independently authorized. |
| Looker API identity | Read-only, approved model/Explore/fields, no admin/develop/write/schedule/external-send permissions. |

Group-based role assignment is preferred; additive individual roles can accidentally accumulate
privilege.

## Tests and acceptance gates

### Router tests

- Positive and negative cases for every keyword family, aliases, Romanian/English equivalents,
  spelling variants, negation, and singular/plural forms.
- Compound requests load all and only relevant contracts.
- “Explain headcount” and “what can you answer?” remain `CATALOG_ONLY`; they do not call Looker.
- Ambiguous “attendance,” “leave,” “turnover,” “performance,” “pay,” and “position” prompts ask one
  targeted clarification instead of choosing a metric.
- Unmatched questions return `UNMODELED`; no raw-schema fallback occurs.
- Generated router output is reproducible from its YAML source.

### Semantic and source tests

- Employment/worker/requisition/review keys are non-null and unique at their declared grain.
- Effective-dated employment and compensation intervals do not overlap unexpectedly.
- Join relationships and referential integrity match the declared cardinality.
- Snapshot headcount reconciles to the HR system of record within a signed-off tolerance.
- Monthly hires and terminations reconcile to event records.
- Currency, calendar, timezone, status mapping, and rating-scale dimensions are complete.
- Freshness timestamps are present and within each metric's SLO.
- LookML Validator, Content Validator, and model data tests pass before production promotion.
- Looker tests cover primary-key uniqueness, invalid date ranges, and impossible values.

### Synthetic golden cases

Use synthetic—not copied production—fixtures covering:

- active worker, same-day hire, end-boundary termination, rehire, concurrent assignments;
- part-time/FTE and leave spanning a snapshot;
- voluntary/involuntary termination and a right-censored new-hire cohort;
- duplicate badge swipes, holidays, PTO, optional office visits, and timezone boundaries;
- review drafts, duplicate cycles, changed rating scales, and missing ratings;
- part-time compensation, effective-dated salary range, missing midpoint, and FX date;
- requisition opened, paused, backfill, filled, cancelled, and reopened states.

Expected outputs are versioned with each metric contract.

### Privacy and authorization tests

- Groups of `k-1`, `k`, and `k+1` unique people prove threshold behavior.
- Duplicate event rows cannot satisfy the distinct-person threshold.
- Primary and complementary suppression prevent reconstruction from totals.
- Adjacent-time, parent/child-org, and nested-filter differencing attempts are rejected or coarsened.
- Two synthetic users with different org attributes receive different authorized rows.
- Missing/invalid user attributes, role accumulation, direct URL access, and API access all fail
  closed.
- Compensation/performance fields remain inaccessible from unrestricted Explores.
- Downloads, schedules, alerts, and external delivery are denied for the API identity.
- Receipts contain metadata but no result values or personal data.

### Adapter/result tests

- Tool absent, plugin unreadable, 401, 403, unknown model, unknown Explore, unknown metric,
  timeout, stale cache, and malformed response each map to the correct non-success state.
- The emitted API request uses only registry-bound model/Explore/fields, `filter_config: null`,
  bounded filters, production semantics, and a row limit.
- Response schema, metric units, null states, totals, suppression, freshness, and reconciliation
  are validated before narrative generation.
- Mutation tests break a primary key, remove an access filter, lower the privacy threshold, and
  alter a denominator; the suite must go red and return no result.
- A successful query with stale data or failed tests is not `EXECUTED_VALIDATED`.

### Initial acceptance threshold

Production execution remains disabled until:

1. all guide and terminal artifacts are readable and reviewed;
2. at least one exact metric contract is approved and bound to real semantic fields;
3. Looker identity, model set, permission set, access filters, and access grants are independently
   tested;
4. synthetic, semantic, privacy, and mutation suites pass;
5. freshness/reconciliation receipts are current;
6. the DPO/data owner approves purpose, thresholds, retention, and role matrix for the first use
   case.

## Confidence semantics

Do not collapse route quality, authorization, and data validity into one “High/Medium/Low” label.
Return the following axes:

| Axis | Values |
|---|---|
| `route` | `EXACT_INTENT`, `ALIAS`, `AMBIGUOUS`, `UNMATCHED` |
| `semantic_binding` | `EXACT_VERSIONED_METRIC`, `APPROVED_ALIAS`, `UNMODELED` |
| `authorization` | `AUTHORIZED`, `DENIED`, `NOT_CHECKED` |
| `execution` | `NOT_RUN`, `SUCCEEDED`, `FAILED_TO_RUN` |
| `data_quality` | `CURRENT_TESTED`, `WARNING`, `STALE`, `NOT_CHECKED` |
| `privacy` | `ENFORCED_TESTED`, `BLOCKED`, `NOT_CHECKED` |
| `provenance` | `disk-verified`, `agent-claimed` |

The overall result is the weakest required axis, never an average:

- **High**: exact versioned metric, authorized, successful execution, current tests/freshness,
  validated reconciliation, privacy enforced/tested, and disk-verified receipt.
- **Medium**: no factual result claim; an approved alias or non-material data-quality warning is
  disclosed. Authorization, execution, and privacy must still pass.
- **Low**: not a permission to improvise. Return no workforce fact and name the missing contract,
  validation, or clarification.
- **Blocked/Not run**: use explicit state, not a confidence adjective.

For this lens:

```text
route: EXACT_INTENT
semantic_binding: UNMODELED
authorization: NOT_CHECKED
execution: NOT_RUN
data_quality: NOT_CHECKED
privacy: NOT_CHECKED
provenance: disk-verified (design artifact only)
overall: BLOCKED — no factual People Analytics result exists
```

## Useful governed query templates

These are candidate questions, not executed queries or claims:

1. Monthly active employee headcount and FTE by authorized department, with month-over-month
   change and explicit snapshot dates.
2. Monthly overall, voluntary, and involuntary turnover rates by authorized organization, with
   denominator and suppressed-group counts shown.
3. New-hire cohort turnover within an approved horizon, with right-censoring and cohort definition.
4. Required office days, attended required days, and compliance trend, excluding holidays and
   approved leave; no raw badge events.
5. Absence-rate hours by broad authorized organization and month, with leave taxonomy disclosed.
6. Review completion rate and suppressed rating distribution for one named cycle and scale.
7. Median/p10/p90 annualized base pay and median compa ratio by approved job family/grade, using
   the stricter compensation threshold and complementary suppression.
8. Approved open requisitions, median age, and age bands by authorized function; separate backfill
   from incremental roles.
9. Planned headcount versus active FTE and approved open requisitions, only after Finance/People
   double-counting rules are approved.
10. Data-quality dashboard: stale sources, unmapped statuses, overlapping effective dates, missing
    range midpoints, reconciliation variance, and suppressed cell counts—without employee details.

Every answer should show metric IDs/versions, workforce scope, as-of/period, timezone, denominator,
suppression policy, freshness timestamp, source/model commit, and validation receipt.

## What remains BLOCKED

| Blocker | Evidence in this session | Settling action |
|---|---|---|
| Plugin guide semantics | Reads of all six guide files returned `Permission denied`. | Grant the parent session read permission or provide the guide contents; review and reconcile them against the proposed contracts. |
| Looker terminal semantics | Read of `people-analytics-looker/SKILL.md` returned `Permission denied`. | Expose the subskill for audit; verify allowed API methods, query construction, limits, logging, and error states. |
| Looker tool presence | No Looker tool is exposed in the active tool inventory. | Enable the approved plugin/tool in the parent session; capability-probe only. |
| Authentication and authorization | No authenticated Looker identity, model set, role, or user attributes are available. | Authenticate a dedicated least-privilege identity and independently test role/row/field access. |
| Real semantic bindings | No instance, model, Explore, field names, metric catalog, source schema, or model commit were supplied. | Export authorized metadata/catalog and bind one approved metric contract; do not infer names. |
| Legal/policy approval | No documented purpose, legal basis, DPIA, DPO decision, retention map, threshold approval, or workforce notice was supplied. | Obtain controller/DPO/data-owner approval for the first concrete use case. |
| Data quality/freshness | No data, source reconciliation, freshness timestamp, or test receipt exists here. | Run the approved test suite after access and model binding; retain metadata-only receipts. |
| Concrete query | The user intentionally supplied no metric query. | Provide a bounded MetricRequest after all earlier blockers clear. |

No query should be run merely to test connectivity. Metadata/capability probes must themselves be
authorized and must not retrieve People data.

## Research basis

Authoritative or primary sources consulted:

- Google Cloud, **Looker API authentication** — API credentials execute as their bound user;
  production integrations should use minimal-privilege non-admin identities:
  https://docs.cloud.google.com/looker/docs/api-auth
- Google Cloud, **Keeping Looker secure** — model sets, permission sets, access filters, access
  grants, and group-based role assignment:
  https://cloud.google.com/looker/docs/best-practices/how-to-keep-looker-secure
- Google Cloud, **access_filter** — filters are Explore-specific and must be applied to every
  restricted Explore:
  https://cloud.google.com/looker/docs/reference/param-explore-access-filter
- Google Cloud, **Aggregate awareness** — access-filter fields must be represented in compatible
  aggregate tables; join correctness and symmetric aggregates matter:
  https://cloud.google.com/looker/docs/aggregate_awareness
- Google Cloud, **LookML model tests and validation**:
  https://cloud.google.com/looker/docs/reference/param-model-test and
  https://docs.cloud.google.com/looker/docs/lookml-validation
- dbt Developer Hub, **MetricFlow and semantic models** — deterministic metrics, entities,
  dimensions, time grains, and validated semantic graphs:
  https://docs.getdbt.com/docs/build/about-metricflow and
  https://docs.getdbt.com/docs/build/semantic-models
- ISO, **ISO 30414:2025** — current human-capital reporting areas and requirements/recommendations:
  https://www.iso.org/standard/30414
- ISO/TS 30421:2021 public sample — monthly turnover using leavers over average monthly workforce:
  https://cdn.standards.iteh.ai/samples/75372/402bdfb0858949569276f5be493fc4f4/ISO-TS-30421-2021.pdf
- EUR-Lex, **GDPR** — Articles 5, 22, 25, 32, 35, and 88:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679-20160504
- Romanian Law 190/2018, Article 5, official-hosted PDF:
  https://edirect.e-guvernare.ro/Uploads/Legi/35906/Lege%20190%202018.pdf
- EUR-Lex, **Regulation (EU) 2024/1689 (AI Act)** — employment, worker management, and performance
  monitoring high-risk context:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02024R1689-20260727
- ICO, **Data protection and monitoring workers** — necessity, proportionality, transparency, and
  DPIA practice:
  https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/monitoring-workers/data-protection-and-monitoring-workers/
- Microsoft Workplace Analytics privacy-threshold helper documents a common default of five; this
  supports, but does not legally mandate, the proposed baseline:
  https://microsoft.github.io/wpa/reference/identify_privacythreshold.html

Research confidence is **high** for the general semantic-layer, Looker access, GDPR, Romanian-law,
and AI Act principles above because they are grounded in vendor or primary legal sources.
Confidence is **medium** for exact estate thresholds and metric-policy choices because those require
the controller, DPO, People, Finance, and data owners. Confidence is **blocked** for plugin-specific
guide/tool semantics and all real data results.

UNIT-COMPLETE: lens-06
