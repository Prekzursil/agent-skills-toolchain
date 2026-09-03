# Lens 10 — Security and privacy threat model

**Date:** 29.08.2026  
**Scope:** unified session analytics, Fabric/OpenRouter processing, Cursor Cloud Agents, and
People Analytics.  
**Verdict:** **NEEDS_REVISION before these surfaces share data.** The existing local buses are
usable, but raw transcript content and person-level data need a deterministic destination gate
before any provider or cloud path is enabled.

## 1. Binding constraints and dedup

This lens inherits rather than re-proposes the following locked decisions:

- Never rotate credentials, tokens, keys, or login sessions. An incident response may contain,
  deny, quarantine, revoke a job, or report blast radius, but it must not rotate anything.
- Never print secrets. Canonical files contain environment-variable or keyring names only.
- Never send a raw private transcript to a free OpenRouter endpoint.
- Basic Memory is the sole semantic-memory writer; no cloud memory synchronization and no second
  memory store.
- Browser profiles and login sessions are precious. They are not copied, normalized, scrubbed,
  rebuilt, uploaded, or included in cloud snapshots.
- `agent-skills-toolchain` remains private-only. No workflow may change repository visibility.
- Only Basic Memory, agent-mail, and auth2api may bind `127.0.0.1:8765`, `:8812`, and `:8317`
  respectively. No collision, rebinding, or fallback port.
- OpenRouter remains a spend-capped CLI/Codex sidecar: no MCP, Cursor BYOK, LiteLLM, or global
  provider replacement.
- Cursor Cloud Agents are owner-invoked per job, not an automatic offload path.
- Fabric is a prompt/pattern utility, not an orchestrator, memory owner, or control plane.
- Existing event ledger, typed receipts, local hook logs, session catalog, Basic Memory, and
  monitor surfaces are the buses to extend. Add no observability SaaS or resident collector.
- Cloud/provider status is never completion evidence. Returned artifacts must be re-read locally.

This lens also accepts the 27.08 Wave C provenance doctrine and the Lens 11 additive event schema.
It does not duplicate the metrics catalogue. Security controls below add `content_class`,
`data_subject_class`, `destination`, and policy-decision fields to that same event stream.

## 2. Concrete current-state findings

1. `index-ai-sessions.py` says “pointers only”, but it reads up to 64 KiB from both the head and
   tail of most native transcripts and persists a title/first/last snippet plus the absolute
   transcript path. Regex redaction and 200-character truncation reduce exposure but do not make
   the catalog metadata-only. Names, health details, HR facts, project names, and novel credential
   formats can still survive.
2. The session catalog is local and gitignored, which is correct. It must not become a provider
   prompt, a Basic Memory entity, a cloud-agent input, or a versioned repository artifact.
3. The indexer has a private redaction implementation separate from
   `.agents/harness/redaction.py`. The shared redactor is broader, but neither regex system can
   reliably remove arbitrary personal or confidential prose. Redaction is a backstop, not
   authorization to export a transcript.
4. The shared event ledger already provides locking, project hashing, bounded values, path
   redaction, typed receipts, and append-only JSONL. It is the correct analytics substrate once
   free text is excluded from analytics events.
5. `openrouter-complete.py` receives prompts in `--prompt`, so content can enter process listings,
   shell history, and terminal transcripts. It also prints a response snippet. That interface is
   suitable only for public/synthetic probes, not private transcript or People Analytics content.
6. OpenRouter free endpoints can have provider-specific training/publication policies. Current
   routing documentation already warns that a tested free provider may train on free traffic.
7. Cursor documents that Cloud Agent transcripts are retained indefinitely by default and VM
   snapshots persist for up to 90 days of inactivity; snapshots cannot be deleted on demand.
   Privacy Mode prevents training but does not mean “no cloud persistence”.
8. Provider-neutral design already identifies full Cursor hook payload logging as unsafe and
   requires structural redaction, rotation, retention, and dropped-write counters. Unified
   analytics must wait for that Phase 1 gate rather than ingesting the current raw hook files.
9. People Analytics can become worker monitoring or profiling even when the immediate output is
   called a dashboard. Session activity, latency, tool use, errors, writing style, work hours, and
   inferred sentiment can all become identifiable performance data when joined.

## 3. Assets and required handling

| Asset | Sensitivity | Safe authority / location | Forbidden movement |
|---|---|---|---|
| Native prompts, responses, tool output, diffs, attachments | Restricted by default | Native runtime session store | General ledger, Basic Memory, free OpenRouter, Fabric context, dashboard, Git |
| Session metadata and operational outcomes | Internal; potentially personal | Redacted event ledger and local rollups | Raw IDs, content snippets, absolute paths, provider prompts |
| Event-ledger integrity and typed receipts | Integrity-critical | Local append-only ledger | Model-authored “ground truth”, silent rewrite |
| Secrets, OAuth tokens, cookies, auth databases | Restricted | Existing owner-managed stores and browser profiles | Logs, argv, prompts, Git, cloud snapshot, analytics |
| Browser profiles and persistent login state | Restricted and availability-critical | Dedicated local browser-profile roots | Cloud agents, archives, temporary scrubbing jobs, destructive cleanup |
| `agent-skills-toolchain` source and history | Private business/personal | Private repository and local canonical/export roots | Public visibility, public artifacts, unapproved forks |
| Basic Memory notes and vault | Restricted semantic memory | `127.0.0.1:8765/mcp` only | Direct writes, provider memory, cloud sync |
| People Analytics row-level source | Restricted personal data | Dedicated local project data area with existing OS access controls | Event ledger, session catalog, model prompts, general dashboard |
| People Analytics aggregates and reports | Confidential until disclosure review | Case-specific output with lineage manifest | Small cells, direct identifiers, hidden row-level drill-down |
| Cloud Agent transcript, snapshot, artifacts, configured secrets | Restricted third-party-held data | Cursor service under per-job scope | Browser profile/session material; unrelated project trees |
| Provider/model/routing and cost metadata | Internal | Local telemetry | Prompt/response bodies or key values |
| Local service ports and process identity | Integrity/availability-critical | Assigned loopback listener | Wildcard bind, port substitution, second owner |

## 4. Trust boundaries and allowed flows

| Boundary | Allowed payload | Required gate | Default |
|---|---|---|---|
| Native session store → session catalog | Runtime, date bucket, content-free title hash, local pointer token | Local-only indexer; shared redaction; size bounds | Snippets **off** |
| Native hooks → event ledger | Bounded enums, timings, hashes, counts, reason codes | Schema validation before append | Free text **drop**, not redact-and-keep |
| Event ledger → rollup/dashboard | Aggregates and minimum necessary pseudonymous joins | Deterministic local rollup; source hash/seq manifest | Local read-only |
| Local content → Fabric | Public or explicitly sanitized task payload | Destination policy before process spawn; stdin/file handle, never argv | Shared context **off** |
| Local content → OpenRouter | Public/synthetic; sanitized private extract only after explicit policy pass | Model/provider allowlist, data policy, ZDR, fallback controls | Private raw content **deny** |
| Local repo → Cursor Cloud Agent | Exact private repo/worktree and bounded job context | Owner-invoked manifest, Privacy Mode, ignore/deny list, network allowlist | No home/vault/profile access |
| Cursor Cloud → local | Diff/artifact manifest, hashes, bounded logs | Local secret scan, schema validation, artifact re-read, tests | Provider “complete” = unverified |
| People source → analytics transform | Row-level local data | Case isolation, field allowlist, purpose manifest | Local only |
| People transform → report | Aggregates with disclosure controls and lineage | Direct-ID scan, small-cell and complementary suppression, human review | No individual ranking |
| Any component → Basic Memory | Verified durable fact/decision only | Existing Basic Memory publication path | No transcript or row-level people data |
| Any client → `8765/8812/8317` | Assigned protocol to assigned owner | Loopback and process-owner check | Refuse mismatch; never rebind |

## 5. Abuse paths, impact, and required controls

### T1 — Raw transcript escapes through “summarization”

**Path:** a unified analytics job reads native JSONL, sends it to Fabric or a free OpenRouter model
to classify topics, then stores the summary. The provider receives credentials, personal facts,
private code, and prior tool output before redaction can protect the result.

**Likelihood:** high if content summarization is offered. **Impact:** high. **Priority:** critical.

**Controls:**

- Analytics ingestion is event/metadata-only. A transcript parser may derive locally bounded enums
  but may not emit text outside the native store.
- `origin=native_transcript` plus `content_class=restricted` is a hard deny for every free
  OpenRouter model and for Fabric when its backend is remote.
- Redaction never upgrades a restricted payload to public. Only a deterministic field allowlist or
  a human-authored extract can change the class.
- Do not put prompts in argv. Provider wrappers accept stdin or an owner-only temporary file and
  emit metadata-only telemetry. Response bodies do not enter general hook/terminal logs.

### T2 — Session catalog becomes a durable privacy index

**Path:** snippets and absolute paths from many runtimes make sensitive sessions searchable and
linkable in one file; a later sync, model prompt, backup, or dashboard broadens access.

**Likelihood:** medium-high. **Impact:** high. **Priority:** high.

**Controls:**

- Keep the catalog gitignored and outside the Basic Memory vault.
- Change the analytics-facing view to content-free fields: runtime, coarse time bucket, project
  hash, session hash, terminal state, and native pointer token. Do not expose absolute paths.
- Preserve the current rich catalog only as a local operator index until a migration decision;
  do not feed it into unified analytics. No silent destructive rewrite.
- Use one shared redactor and a `redaction_version` field. A redaction failure drops the event and
  increments a visible counter.

### T3 — Cross-project or cross-person linkage

**Path:** stable native session IDs, absolute paths, usernames, timestamps, and project names are
joined across providers and People Analytics, revealing identity, work patterns, health/research
interests, or performance proxies.

**Likelihood:** high. **Impact:** high. **Priority:** high.

**Controls:**

- Use separate keyed local pseudonyms for operational sessions and People Analytics cases. Never
  reuse a join key across these domains.
- Coarsen timestamps in released rollups; keep exact timing only in the restricted local ledger.
- Dashboards have no “join people to AI sessions” feature. Such a join is a new processing purpose,
  not a convenient filter.
- Do not export project names, Windows usernames, raw session IDs, prompt hashes of low-entropy
  text, or absolute paths.

### T4 — Prompt injection turns analytics input into instructions

**Path:** transcript, code comment, imported document, or employee free-text field tells an LLM to
reveal other sessions, call tools, or emit secrets. A summarizer obeys because instructions and
data share one prompt.

**Likelihood:** medium. **Impact:** high. **Priority:** high.

**Controls:**

- Provider processing receives no tools and no ambient memory; Fabric remains a pure transform.
- Put untrusted text in a structurally delimited data field and validate the output against a
  narrow schema. Treat every output as untrusted data.
- Model output cannot choose user/project IDs, file paths, destinations, retention, provider,
  cloud execution, or tool arguments.
- Apply deterministic output guards for forbidden markers and direct identifiers. A model judge
  may advise but never authorize release.

### T5 — Forged or poisoned analytics changes decisions

**Path:** malformed hook payloads, duplicated retries, model-authored labels, or edited JSONL make a
runtime/person appear more or less productive, safe, or reliable.

**Likelihood:** medium. **Impact:** high for People Analytics; medium otherwise. **Priority:** high.

**Controls:**

- Ledger events remain append-only and mechanically sourced. Agent prose is `agent-claimed`.
- Every rollup records source-file SHA-256, first/last sequence, record count, parser version,
  dropped count, and denominator version.
- Reject duplicate event IDs, backward sequence movement, impossible durations, missing terminal
  states, and unrecognized enums; preserve `unknown`/`failed-to-run`.
- People Analytics never consumes self-reported agent quality as an employee-performance fact.

### T6 — Cloud Agent retains more than the job requires

**Path:** an owner sends a broad repository/home context; setup captures `.env`, tokens, browser
state, or private datasets. Cursor retains transcript and snapshots beyond job completion.

**Likelihood:** medium. **Impact:** critical. **Priority:** critical.

**Controls:**

- Per-job manifest lists exact repo, branch/worktree, input files, required secret names, outbound
  domains, expected artifacts, and retention action.
- Deny home roots, `.agents/secrets`, `local.json`, native transcript stores, browser-profile
  roots, cookie jars, password stores, People Analytics source, and Basic Memory paths.
- Enforce standard Privacy Mode. Use no BYOK and approve only required models.
- Use Cursor Runtime Secrets only when indispensable; never place secret files in snapshots.
- Outbound network is allowlisted to exact package/source endpoints needed by the job.
- After local acceptance, present the owner-triggered Delete Agent action for transcript/artifact
  deletion. Because snapshots cannot be deleted on demand, restricted material must never enter
  them in the first place.

### T7 — Cloud return compromises the private repository

**Path:** a cloud job returns prompt-injected code, dependency changes, hidden generated files, or
artifacts containing secrets; automation merges or publishes them.

**Likelihood:** medium. **Impact:** high. **Priority:** high.

**Controls:**

- Cloud jobs never commit or change visibility. Return a diff and content-addressed manifest.
- Local verification runs secret scanning, scope check, dependency/config review, tests, and
  artifact re-read before any completion or merge decision.
- A read-only preflight verifies that `agent-skills-toolchain` is private. Any `public` or
  `unknown` result blocks cloud dispatch and delivery.
- Repository visibility, collaborators, deploy keys, secrets, and branch protection are outside
  cloud-job mutation scope.

### T8 — People Analytics becomes covert worker surveillance

**Path:** workflow-quality metrics are reused to rank people, infer performance or sentiment, or
support promotion, discipline, allocation, or termination without notice or meaningful review.

**Likelihood:** medium-high because reuse is easy. **Impact:** critical. **Priority:** critical.

**Controls:**

- Safe default is **workflow and deliverable quality only**, not person scoring. No employee
  leaderboard, “productivity score”, sentiment score, behavioral profile, or individual risk flag.
- Each case declares purpose, lawful basis, population, fields, retention, recipients, and
  prohibited secondary uses before data ingestion.
- Run a DPIA before worker monitoring/profiling or systematic evaluation. If output may materially
  influence employment decisions, obtain specialist legal/DPO review and treat the AI Act
  high-risk classification as applicable until documented otherwise.
- Automated output cannot make or silently drive a significant employment decision. Provide human
  review, contestability, and correction against source data.
- Do not infer protected or special-category traits from proxies, text, names, schedules, location,
  health clues, union activity, or browsing/session history.

### T9 — Aggregate report re-identifies a person

**Path:** small teams, rare roles, time slices, cross-filters, complementary totals, filenames, or
chart metadata reveal row-level facts despite removed names.

**Likelihood:** high in small organizations. **Impact:** high. **Priority:** high.

**Controls:**

- Default minimum publishable cell is `n >= 10`; make it stricter for sensitive attributes.
  Suppress complementary cells so totals cannot reconstruct a hidden value.
- Disable row drill-down and arbitrary cross-filter combinations in released views.
- Direct identifiers, free text, exact timestamps, and rare-role labels stay out of reports.
- Suppression is deterministic and tested across tables, charts, CSV/XLSX, filenames, comments,
  hidden sheets, document metadata, and cached exports.
- A qualified human reviews whether the data is sufficiently aggregated for the actual workforce;
  `n=10` is a safe default, not a legal safe harbor.

### T10 — Browser-session theft or accidental loss

**Path:** analytics/cloud tooling scans, packages, “cleans”, modifies, or copies a persistent
browser profile; credentials leak or the owner is logged out.

**Likelihood:** medium. **Impact:** critical operationally. **Priority:** critical.

**Controls:**

- Browser-profile roots are hard-denied inputs for analytics, Fabric, OpenRouter, and cloud jobs.
- Browser automation retains the mandatory per-run choice: live owner override, agent-persistent
  default, or agent-ephemeral. The choice is logged as an enum only.
- No cookie dump, CDP credential extraction, profile migration, cleanup, or auth database access.
- Retention/cleanup jobs explicitly exclude browser profiles and sessions. No rotation or logout
  is proposed as remediation.

### T11 — Local service impersonation or port collision

**Path:** another process binds a reserved port, a client silently follows a new port, or a service
listens on all interfaces, exposing memory, agent messages, or quota traffic.

**Likelihood:** medium. **Impact:** high. **Priority:** high.

**Controls:**

- Health checks validate loopback address, exact port, expected protocol response, and expected
  process identity. “Something answered” is not healthy.
- A mismatch fails visibly. Do not kill, rebind, scan for a free port, or start a duplicate.
- Clients use only `127.0.0.1:8765/mcp`, `127.0.0.1:8812`, and local-only `:8317`.
- Telemetry records owner/service enum and pass/fail only, never request/response bodies.

### T12 — Retention sprawl outlives the purpose

**Path:** the same content persists in native sessions, catalog snippets, hook JSONL, rollups,
cloud transcripts, snapshots, model-provider logs, exports, backups, and Git.

**Likelihood:** high. **Impact:** high. **Priority:** high.

**Controls:**

- Maintain a data-flow/retention manifest for each derived class. Native sessions and precious
  login state are separate from disposable derived analytics.
- Detailed derived events default to 30 days; approved aggregate trend rows to 13 months. These are
  starting limits subject to project/legal requirements, not grounds to delete native sessions.
- Rotation/expiry acts only on derived analytics and test artifacts. It never touches browser
  profiles, credentials, native session history, or Basic Memory without a separate owner decision.
- Cloud/provider retention state is recorded per run. Unknown retention blocks restricted content.

### T13 — Fallback silently changes the privacy contract

**Path:** a preferred ZDR endpoint fails and routing falls back to a provider that logs, trains, or
publishes requests.

**Likelihood:** medium. **Impact:** high. **Priority:** high.

**Controls:**

- Private/sanitized jobs set `data_collection=deny`, `zdr=true`, explicit provider/model allowlists,
  and `allow_fallbacks=false`.
- Free-model training and publication are disabled by account/guardrail policy; the effective
  eligibility preview is checked before use.
- Any unavailable compliant route is `FAILED_TO_RUN`, not permission to downgrade.
- Fabric must report its effective provider/model. Unknown provider means public/synthetic input
  only.

## 6. Safe defaults

1. **Collection:** content-free events only; no transcript snippets, prompts, responses, tool output,
   diff bodies, people rows, or absolute paths in the analytics stream.
2. **Classification:** `public | internal | private | restricted`, plus
   `none | operator | worker | customer | mixed` data-subject class. Unknown is `restricted`.
3. **Destination matrix:**
   - local ledger/rollup: public/internal and redacted structural private metadata;
   - Fabric remote: public by default; sanitized private only with explicit job policy;
   - OpenRouter free: public/synthetic only;
   - OpenRouter paid: public/internal; sanitized private only with verified ZDR/no-collection and
     owner-approved job policy;
   - Cursor Cloud: exact private repo job only; no transcripts, people source, memory, profiles, or
     home context;
   - Basic Memory: verified durable decisions/facts only.
4. **People Analytics:** local processing, aggregate release, `n >= 10`, no individual ranking,
   no special-category inference, no employment decision automation.
5. **Cloud:** owner-invoked, Privacy Mode, least files/secrets/network, local verification, explicit
   post-acceptance deletion option.
6. **Logging:** enums/counts/hashes only. Diagnostic text stays local, bounded, redacted, and outside
   the metric stream.
7. **Failure:** drop unsafe events and increment `dropped_private`, `redaction_failed`, or
   `policy_denied`; never fail open to provider export.
8. **Memory:** no analytics or provider output is promoted automatically.
9. **Ports:** exact owner and loopback or fail; never remap.
10. **Repository:** private visibility is a blocking invariant, not a warning.

## 7. Minimal additive control design

Extend the existing event/receipt buses with one local deterministic policy decision:

```json
{
  "kind": "data_route_decision",
  "content_class": "restricted",
  "data_subject_class": "worker",
  "origin": "native_transcript",
  "destination": "openrouter_free",
  "decision": "deny",
  "reason_code": "RAW_PRIVATE_TRANSCRIPT",
  "policy_version": "2026-08-29",
  "payload_hash": "sha256-only",
  "payload_bytes": 0
}
```

The event records the decision, not the content. The gate runs before process spawn, network
request, cloud dispatch, dashboard render, or memory publication. It is a small library used by:

- the session rollup command;
- Fabric/OpenRouter wrappers;
- Cursor Cloud job-manifest validator;
- People Analytics export validator;
- Basic Memory publication adapter.

Do not implement five provider-specific classifiers. One destination matrix and one shared
redactor are enough. Model-based PII classification may add warnings later but cannot replace the
deterministic origin/destination deny rules.

## 8. Acceptance tests

### Hard negative tests

1. Seed synthetic API keys, OAuth headers, cookies, email/phone/name, private code marker, and worker
   record marker into a fixture transcript. Assert none appears in catalog, ledger, rollup,
   terminal output, diagnostics, dashboard artifact, Git diff, or provider mock.
2. Mark the fixture `origin=native_transcript`, `content_class=private`; dispatch to a free
   OpenRouter model. Assert no child process and no network call occurs; one metadata-only deny
   event is written.
3. Pass private content through Fabric with a remote backend and no explicit policy. Assert refusal
   before invocation. A public fixture still passes.
4. Verify private OpenRouter requests use stdin/protected file input, never argv; assert process
   command line and terminal record contain no fixture marker.
5. Force the preferred ZDR endpoint unavailable. Assert no fallback, no request to a noncompliant
   provider, and `FAILED_TO_RUN`.

### Session analytics

6. Analytics events contain no fields outside the allowlist. Unknown keys and free text are
   dropped with counters.
7. Catalog-facing analytics contains no snippets, native session IDs, usernames, project names,
   or absolute paths.
8. Concurrent ledger writes remain valid JSONL; duplicate IDs, sequence gaps, malformed lines, and
   dropped events are surfaced. Rollup records source hashes and seq/count bounds.
9. Dashboard process is denied direct access to native transcript roots and row-level People
   Analytics data; it reads only versioned rollups.
10. Cross-project and People/operations pseudonyms differ for the same seeded identity.

### Cursor Cloud Agents and repository

11. A cloud manifest containing any browser profile, cookie jar, `.agents/secrets`, `local.json`,
    native transcript, Basic Memory, or People source path is rejected before dispatch.
12. A read-only repository check proves `agent-skills-toolchain` visibility is private. Public or
    unknown blocks the job; the test never changes visibility.
13. Cloud return marked “complete” without a locally readable manifest and artifact hash remains
    unverified.
14. Returned diff containing a synthetic secret, visibility mutation, unexpected dependency,
    out-of-scope path, or auth/session file fails local acceptance.
15. Cloud job receipt records Privacy Mode, effective model, allowed domains, secret-name list,
    retention state, transcript-deletion eligibility, and snapshot caveat—never secret values.

### People Analytics

16. Direct identifiers and seeded special-category proxies never appear in report data, charts,
    hidden sheets, comments, filenames, metadata, or general telemetry.
17. Cells below `n=10` and complementary cells are suppressed across every export format.
18. A request for employee ranking, sentiment scoring, or a promotion/discipline recommendation is
    denied with `PROHIBITED_SECONDARY_USE`.
19. Every released figure reproduces from an immutable input snapshot and transformation hash;
    every input row is retained, excluded with reason, or aggregated.
20. A worker-monitoring/profile case cannot start without purpose, lawful-basis, notice, retention,
    recipient, human-review, contestability, and DPIA status fields. Missing means blocked.

### Local services and lifecycle

21. Reserved-port tests confirm loopback plus expected owner/protocol. Wrong PID, wildcard bind,
    duplicate listener, or substitute port fails without killing or rebinding.
22. Rotation/retention tests remove only expired derived analytics fixtures. Browser profiles,
    login sessions, native session stores, credentials, and Basic Memory remain byte-identical.
23. Basic Memory outage creates no cloud-memory write and no alternate semantic store.
24. Completion requires the report/output artifact to exist and be re-read; budget/time/RAM aborts
    remain `FAILED_TO_RUN`.

## 9. Prioritized controls

| Control | Maturity | Value × effort | Confidence |
|---|---|---|---|
| Hard destination gate for transcript/people data | Proposed small extension | Very high × low | High |
| Content-free analytics event allowlist | Designed; not yet unified | Very high × low-medium | High |
| Shared redactor plus drop-on-failure counters | Existing component; integration needed | High × low | High |
| Remove prompt content from argv and default terminal snippets | Current gap | High × low | High |
| OpenRouter ZDR/no-collection/no-fallback request policy | Vendor-supported; wrapper delta | High × low | High |
| Cursor Cloud exact-path/secret/network manifest | Product controls exist; estate validator needed | Very high × medium | High |
| People Analytics domain separation and no person scoring | Policy gate | Very high × low | High |
| Small-cell/complementary suppression in all exports | Established technique; workflow-specific tests needed | High × medium | High |
| Rollup source hash/seq/count manifest | Existing ledger, small additive receipt | Medium-high × low | High |
| Derived-data retention manifest | Proposed | High × low | Medium-high |
| Owner-triggered cloud transcript deletion after acceptance | Vendor-supported; snapshots remain | Medium × low | High |
| LLM-based PII detector | Optional warning only | Low-medium × medium | Medium |

### Build order

1. Destination/content-class gate and negative tests.
2. Content-free session rollup; do not consume current snippets.
3. stdin/metadata-only Fabric and OpenRouter wrapper paths plus ZDR/no-fallback enforcement.
4. Cursor Cloud manifest validator and private-repository invariant.
5. People Analytics case/export policy and disclosure tests.
6. Retention/rollup views after 30 days of observe-mode evidence.

No cloud/provider processing should precede steps 1–3. People Analytics must remain local and
non-individual until step 5 passes and any required DPIA/legal review is complete.

## 10. Residual risk and scope assumptions

- A local administrator or malware with the owner's privileges can read native transcripts,
  browser profiles, and protected local files. These application controls reduce accidental and
  workflow-mediated disclosure; they are not OS isolation.
- Regex redaction cannot prove prose anonymity. The design therefore relies on data minimization
  and hard destination denial.
- OpenRouter and Cursor controls describe current vendor behavior and must be rechecked at adoption
  time. Provider policy metadata is informative, not a substitute for the governing agreement.
- `n=10` does not guarantee anonymity in a small or highly distinctive workforce.
- If People Analytics is purely synthetic or personal self-analysis, employment-law risk drops;
  the technical separation remains valuable. If it covers employees or contractors, the high-risk
  assumptions above apply.

## 11. Sources

Internal grounding:

- `C:\Users\Prekzursil\AGENTS.md` — canonical estate locks, ports, memory, browser, repository, and
  never-rotate rules.
- `.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md` and
  `.agents/WAVE-ABCD-EXECUTION_2026-08-27.md` — dedup, Cursor observe-mode hooks, fail-closed
  provenance, and existing buses.
- `.agents/scripts/index-ai-sessions.py`, `.agents/harness/redaction.py`,
  `.agents/harness/ledger.py`, and `.agents/scripts/openrouter-complete.py` — current data paths and
  concrete gaps.
- `.agents/docs/plans/2026-08-29-provider-neutral-ai-harness-design.md` — safe telemetry,
  adapter privilege boundaries, local-only runtime data, and transaction receipts.

External authoritative guidance:

- [OpenRouter provider logging and data retention](https://openrouter.ai/docs/guides/privacy/provider-logging)
  and [Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr) — provider policy
  filtering, request-level ZDR, and retention limits.
- [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) —
  `data_collection`, `zdr`, and fallback controls.
- [Cursor Cloud Agent security](https://cursor.com/docs/cloud-agent/security) and
  [Secrets & Network](https://cursor.com/docs/cloud-agent/security-network) — Privacy Mode,
  transcript retention, snapshots, secrets, deletion, and network boundaries.
- [GDPR, Regulation (EU) 2016/679](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02016R0679-20160504) —
  purpose limitation, minimization, privacy by design, automated decisions, and DPIAs.
- [EU AI Act consolidated text, 27.07.2026](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727) —
  employment, worker management, monitoring, evaluation, and profiling risk.
- [ICO worker-monitoring guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/monitoring-workers/data-protection-and-monitoring-workers/) —
  necessity, transparency, consultation, and DPIA practice.
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework) — minimizing observability,
  linkability, identification, and secondary-use risk.
- [OWASP LLM Prompt Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) —
  separating instructions from data, least privilege, and deterministic input/output controls.

UNIT-COMPLETE: lens-10
