# Lens 05 — Unified historical AI-session analytics and learning

**Date:** 29.08.2026  
**Scope:** Claude Code, Cursor, Codex, Goose, Gemini CLI, Grok Build, OpenCode,
Aider, and official ChatGPT exports.  
**Method:** local-first tool and format review, deduplicated against
`CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`, `C:\Users\Prekzursil\AGENTS.md`,
and the memory contract. GitHub maturity counts are point-in-time observations
from 29.08.2026.

## Decision

**ADOPT AgentsView as the single read/index/search/analytics plane; EXTEND it
with its existing one-way local DuckDB mirror and a write-through learning gate
to basic-memory.** Do not build another transcript warehouse.

Keep all semantic and generated-insight features in AgentsView **off**. Its
SQLite FTS5 archive is an operational index, not memory. Only curated,
evidence-linked facts and decisions may cross into basic-memory, and only via
`write_note`. Raw transcripts never enter the vault.

Use ccusage only as a temporary reconciliation oracle, txcript only as a
format/continuation tool under an explicit trial, and Gitleaks plus Presidio only
as an on-demand export boundary. Do not install a second recall MCP, vector
store, cloud sync, or resident service.

## Dedup against locked decisions

The following are already decided and are constraints, not new proposals:

- **G-81:** basic-memory is the sole semantic writer; Mem0, Graphiti, LynxMCP,
  and CORE remain banned.
- The event ledger remains the objective turn-history substrate. A normalized
  transcript index is a derived view, not stronger evidence.
- No raw transcript or compaction dump enters basic-memory; checkpoint facts,
  not chat residue.
- No raw transcript goes to free OpenRouter. OpenRouter remains a spend-capped
  CLI/Codex sidecar, not an MCP or analytics backend.
- No cloud memory sync, PostgreSQL sync, remote Quack, remote embeddings, or
  hosted transcript analytics.
- No resident heavy daemon. On-demand foreground processes and short,
  self-terminating maintenance runs are acceptable.
- Planned-unbuilt item **per-hook ISR telemetry** remains the hook-level source.
  This lens adds session-level denominators and outcomes; it does not duplicate
  the ISR collector.
- Verified-resume provenance remains binding: parser or agent claims are not
  completion evidence until the referenced artifact is re-read from disk.
- The EPSS rule remains binding: orchestrators consume structured results, not
  raw subordinate-agent transcripts.

**Net-new contribution from this lens:** a bounded, local analytical read plane
over historical sessions, including official ChatGPT exports, plus an explicit
promotion boundary from session evidence to the existing basic-memory writer.

## Decision queue

| Candidate | REC | Exact integration / borrow line | Value × effort | Confidence |
|---|---|---|---|---|
| **AgentsView 0.41.1** | **ADOPT, bounded pilot** | One local SQLite archive and FTS5/UI for every requested coding agent plus ChatGPT ZIP import. Disable vectors, recall extraction, insights, telemetry, update checks, PostgreSQL, S3/SSH/HTTP sources, Gist publishing, and Quack. | Very high × low–medium | High |
| **AgentsView session intelligence** | **EXTEND** | Reuse `stats`, `health`, outcomes, tool failures, compactions, context pressure, code attribution, parser-malformed counts, and secret findings. Feed only content-free candidate records to the learning gate. | Very high × low | High |
| **AgentsView DuckDB mirror** | **EXTEND** | Use the built-in one-way `duckdb push`; SQLite stays source of truth and the `.duckdb` file is disposable. Never use `--watch`, Quack, or a remote URL. | High × low | High |
| **ccusage 20.0.20** | **KEEP temporarily** | Run one fixed-window JSON report during pilot and reconcile `(day, agent, model, token class)` totals. Retire it as a routine tool after discrepancies are explained. | Medium × very low | High |
| **txcript 0.8.0** | **TRIAL / BORROW, not core** | Borrow its typed Common model, dated format registry, loss accounting, native fixpoint tests, cross-harness preservation tests, and path-safety tests. Use continuation manually only after backup. | Medium × low | Medium |
| **DuckDB itself** | **ADOPT via AgentsView** | Embedded SQL engine for reproducible trend queries; no custom ingestion and no service. | High × low | High |
| **AgentsView secret scanner** | **ADOPT** | Backfill local findings; it stores rule/location/redacted match rather than the raw secret. It detects but does not sanitize transcript exports. | High × very low | High |
| **Gitleaks** | **ADOPT at egress** | Local second-opinion secret scan. A finding blocks export. `--redact` protects the report; it does not rewrite the source transcript. | High × low | High |
| **Presidio Analyzer + Anonymizer** | **EXTEND at egress** | On-demand Python library, not Docker/service. Replace PII in a derivative only; add Romanian recognizers and a test corpus. | High × medium | High on capability; medium on recall |
| **CodeBurn** | **BORROW, do not duplicate** | Borrow deterministic task classes, one-shot-rate concept, waste checks, and git-correlated “yield”; use AgentsView/DuckDB as the implementation substrate. | Medium–high × medium | Medium |
| **deja-vu / cass / AgentGraphed** | **SKIP runtime** | Duplicate indexes/recall surfaces. Borrow format conformance fixtures, dated provenance, redaction-before-index, and legacy Cursor DB coverage where AgentsView lacks it. | Low incremental × medium | High |
| **ChatKeeper** | **SKIP by default** | AgentsView already imports official ChatGPT ZIPs. Use ChatKeeper only if a separate human-edited Markdown archive becomes an explicit requirement. | Low incremental × low | High |
| **Scrubadub / proxy redactors / LLM Guard** | **SKIP** | We need export-time redaction, not a new proxy or resident NLP service. Presidio + Gitleaks cover the boundary with stronger maturity. | Low incremental × medium | High |

## Target architecture and hard privacy boundaries

```text
vendor-owned local logs (read-only)
        |
        v
AgentsView SQLite + FTS5 (local derived archive; vectors/recall/insights OFF)
        |
        +--> content-free stats/health/secrets reports
        |
        +--> one-shot local DuckDB mirror --> deterministic SQL/trends
                                                |
                                                v
                                  learning candidates (no raw transcript)
                                                |
                                 evidence/provenance review + recurrence gate
                                                |
                                                v
                              basic-memory write_note (sole semantic writer)
```

### Boundary A — canonical evidence

- Vendor session files are immutable inputs. Never redact or “clean” them in
  place: that can break native resume, invalidate hashes, and destroy evidence.
- AgentsView SQLite and DuckDB are rebuildable derivatives, not canonical
  records. Record parser version and source identity in any analytical receipt.
- A parser’s `completed` outcome or health grade is a heuristic. A promised
  artifact is complete only after an independent disk read.

### Boundary B — local storage

- Keep `%USERPROFILE%\.agentsview\` local and excluded from consumer cloud-sync
  folders, git, backup products that upload by default, and network shares.
- Bind UI only to `127.0.0.1`. Do not configure PostgreSQL, Quack, HTTP/SSH/S3
  sources, Gist publish, or any non-loopback listener.
- AgentsView stores transcripts in plaintext SQLite. Claude Code also documents
  its source transcripts as local plaintext. BitLocker status on the relevant
  volume is **NOT-CHECKED** in this lens; verify it before treating “local” as
  adequate at-rest protection.
- DuckDB 1.4+ has native AES-GCM encryption, but AgentsView’s documented mirror
  path does not expose an encryption-key contract. Do not invent custom ETL
  merely to force this feature. Prefer an encrypted local volume; if that cannot
  be verified, omit the optional DuckDB mirror.

### Boundary C — egress

- Default egress is **content-free** session summaries only.
- Any text excerpt leaving the local machine must be a separately generated
  derivative, structurally minimized first, then scanned with Gitleaks and
  anonymized with Presidio. Preserve only source hash, detector versions,
  redaction manifest, and the sanitized derivative.
- Never send raw transcripts, tool output, reasoning, system prompts, file
  contents, credentials, or unredacted PII to free OpenRouter.
- Do not use AgentsView generated insights, recall extraction, remote embedding
  endpoints, publish-to-Gist, or txcript’s private ChatGPT/Claude web APIs.

### Boundary D — learning

- AgentsView must not become a second memory writer. Leave `[vector]`,
  `[recall.extract]`, and `[insights]` absent/disabled.
- Learning candidates contain session ID, agent, project identity, time window,
  deterministic signal, recurrence count, evidence pointer/hash, parser
  version, and confidence — not transcript bodies.
- Promotion requires either recurrence across at least three independent
  sessions or one independently verified high-severity event. This implements
  the already-adopted anti-one-off/Western-Electric principle.
- Final durable knowledge is a short `- [fact]` / `- [decision]` note with
  wikilinks, written through basic-memory `write_note`; raw source remains
  outside the vault.

## Exact bounded-pilot lines

Discovery only was performed here; these are adoption lines for a later build
wave, not actions taken by this lens.

### Installation and process policy

Use the signed Windows x64 artifact for pinned **v0.41.1** and verify it against
the release `SHA256SUMS`. Avoid an unpinned pipe-to-PowerShell installer.

Process-local privacy defaults:

```powershell
$env:AGENTSVIEW_TELEMETRY_ENABLED = "0"
$env:AGENTSVIEW_DISABLE_UPDATE_CHECK = "1"
```

Minimal `%USERPROFILE%\.agentsview\config.toml` intent:

```toml
disable_update_check = true
daemon_idle_timeout = "1m"
scan_protected_paths = false

[vector]
enabled = false

# Add Aider roots explicitly and narrowly; it has no safe default discovery root.
aider_dirs = ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain"]
```

Do **not** add `[recall.extract]`, `[insights]`, `[pg]`, `[proxy]`, DuckDB
`url`, remote source paths, or any embeddings server.

One-shot refresh and verification:

```powershell
agentsview sync
agentsview parse-diff --fail-on-change
agentsview secrets scan --backfill
agentsview stats --format json --since 2026-08-01
agentsview export sessions --format ndjson --since 2026-08-01
agentsview daemon stop
```

The last export is content-free. Store its `schema_version`; reject unknown
versions rather than silently accepting a changed contract.

On-demand UI:

```powershell
agentsview serve --host 127.0.0.1 --no-update-check
```

Run in the foreground and stop it when the review is complete.

ChatGPT official-export import:

```powershell
agentsview import --type chatgpt "C:\path\to\chatgpt-export.zip"
agentsview daemon stop
```

Use the complete official ZIP, not txcript’s private web API. Re-import is
idempotent by skipping existing ChatGPT conversation IDs, but this also means a
conversation continued after the first import may remain stale; test this in the
pilot and retain the original ZIP.

Optional local analytical mirror:

```powershell
agentsview duckdb push
agentsview duckdb status
agentsview daemon stop
```

Do not use `duckdb push --watch`, `duckdb serve`, or `duckdb quack serve` as a
resident process. Query the local file directly with DuckDB, then exit.

Temporary ccusage reconciliation:

```powershell
npx ccusage@20.0.20 daily --all --offline --json
```

Run over the same fixed timezone and date window as AgentsView. Accept a parser
only when total differences are zero or have a documented reason (missing usage
records, provider-estimated tokens, subagent roll-up, or price-catalog drift).
ccusage is not an authoritative bill.

Secret egress gate:

```powershell
gitleaks stdin --redact=100 --report-format json --report-path -
```

Pipe only the proposed **sanitized derivative** to this command. Any finding
blocks egress. Presidio then replaces PII with typed placeholders; it runs as a
library invocation and exits, with no local web service.

### Exact borrow lines

1. **From txcript:** `Common = metadata + ordered typed content blocks +
   tool-call/result pairing + usage + attachments + parent/child lineage +
   explicit conversion losses`.
2. **From txcript:** every format adapter gets a dated provenance note, native
   load/save fixpoint fixture, cross-format preservation test, malformed-input
   fixture, and path-traversal test.
3. **From AgentsView:** parser upgrades must run `parse-diff --fail-on-change`
   against the real archive; malformed lines are visible and never silently
   counted as full fidelity.
4. **From CodeBurn:** derive task category deterministically from tool patterns;
   correlate session windows with git outcomes, but label attribution as
   correlation, not causation.
5. **From deja-vu:** redact credentials before building any shareable/search
   derivative and keep a dated session-format registry. Do not adopt its MCP,
   auto-recall, or separate index.
6. **Into planned ISR telemetry:** join only content-free
   `(session_id, agent, project, started_at, ended_at, outcome, health signals)`
   to event-ledger hook records. Hook efficacy remains ledger-derived.
7. **Into `/self-reflect`:** add a session-intelligence input that consumes
   recurring deterministic candidates and writes selected facts only through
   basic-memory. No transcript ingestion.

## Transcript-format and fidelity matrix

| Source | Native location / shape | What survives | Main risk | AgentsView action | Confidence |
|---|---|---|---|---|---|
| Claude Code | `~/.claude/projects/`, plaintext JSONL per session | Prompts, replies, tools, results, usage and lineage where emitted | Default source retention is 30 days; plaintext may contain credentials and code | Auto-discover; sync before source cleanup | High, official |
| Cursor | `~/.cursor/projects/**/agent-transcripts/`, JSONL or text; older IDE chats also live in `%APPDATA%\Cursor\User\{globalStorage,workspaceStorage}\state.vscdb` | Recent agent transcripts are readable; SQLite has richer/older composer bubbles and checkpoints | Closed, drifting schema; transcript-only indexing may miss pre-transcript IDE history | Pilot recent coverage; borrow txcript/deja Cursor-desktop fixtures or upstream an AgentsView extension if legacy gaps are measured | Medium–high |
| Codex | `${CODEX_HOME}\sessions\...` rollout JSONL plus archived sessions; `history.jsonl` is separate local state | State-change events, items, tool activity, usage depending on mode | Custom `CODEX_HOME`, archives, and ephemeral runs can escape discovery | Honor canonical `C:\Users\Prekzursil\.codex`; include archived sessions; ephemeral sessions are intentionally absent | High, official |
| Goose ≥1.10 | `%APPDATA%\Block\goose\data\sessions\sessions.db` SQLite | Metadata, messages, tool calls/results, tokens and relationships | Legacy JSONL remains after migration and can be double-counted by naïve tools | Treat `sessions.db` as source of truth; legacy JSONL is migration evidence only | High, official |
| Gemini CLI | `~/.gemini/tmp/<project_hash>/chats/`; append-only JSONL with metadata, messages and update records; legacy monolithic JSON remains readable | Prompts, responses, tools, token updates, reasoning summaries when emitted | Update records must be folded in order; retention can be age/count bounded | Use current parser and `parse-diff` after Gemini upgrades | High, official |
| Grok Build | `${GROK_HOME:-~/.grok}/sessions/<encoded-cwd>/<uuid>/`; `updates.jsonl`, `chat_history.jsonl`, `summary.json`, sidecars | ACP display log, model-protocol history, usage signals, plans and lineage | Two conversation views can diverge; `updates.jsonl` is authoritative for resume while some readers prefer `chat_history.jsonl` | Verify both-view reconciliation and summary-only fallback on local fixtures | High, official/open source |
| OpenCode | `~/.local/share/opencode/opencode.db` SQLite; legacy storage JSON; native `opencode export` JSON | Session/message/part tables, subagents and usage where present | Undocumented schema has already migrated; built-in export can omit subagent trees | Let AgentsView own parsing; use `opencode export --sanitize` as a recovery/export path, not primary ingestion | Medium–high |
| Aider | Per-repository `.aider.chat.history.md`, append-only Markdown; `.aider.input.history` separately | User/assistant text, diffs and command output; multiple sessions separated by headers | No global root, no native IDs, weak structured token/tool data, sensitive file is inside repo | Explicit narrow `aider_dirs`; derive IDs from boundaries; never commit history | High on format, medium on analytics |
| ChatGPT | Official export ZIP containing `conversations.json` or numbered files and assets; each conversation is a branching `mapping` DAG with `current_node` | Active branch, alternate generations, metadata, citations and assets depending on exporter | Undocumented changing schema; naïve linear parse duplicates/loses branches; later import skips existing IDs | Use AgentsView official ZIP importer; preserve ZIP and test branch/update behavior | High on export procedure, medium–high on schema |

## Tool assessments and maturity

### AgentsView

- **Observed maturity:** v0.41.1, MIT, ~5,522 stars / 625 forks, created
  19.02.2026, active on 29.08.2026. Signed Windows artifacts and checksums.
- **Strengths:** all requested coding-agent sources; official ChatGPT ZIP
  import; local SQLite/FTS5; usage; health/outcomes; secret detection;
  content-free NDJSON export; parser-drift comparison; one-way DuckDB mirror.
- **Risks:** young and fast-moving; provider formats are partly reverse
  engineered; release history shows frequent schema/parser changes. The
  optional vectors, generated insights, recall extraction, PostgreSQL, Quack,
  Gist, and telemetry all violate or weaken this estate’s boundaries if enabled.
- **Verdict:** best ADOPT/EXTEND fit, provided the negative configuration is
  treated as part of the feature.

### ccusage

- **Observed maturity:** v20.0.20, MIT, ~18,217 stars / 814 forks and ~77k
  weekly npm downloads; active on 29.08.2026.
- **Strengths:** very mature token/cost normalization, broad CLI coverage,
  offline pricing cache, stable JSON and date/timezone filters.
- **Limits:** reparses source files, focuses on usage rather than learning,
  cannot know subscription quota or authoritative billing, and duplicates
  AgentsView’s usage surface.
- **Verdict:** one-time cross-check and regression oracle, not a second routine
  analytics stack.

### txcript

- **Observed maturity:** v0.8.0, Apache-2.0, 14 stars / 4 forks, created
  25.06.2026. Young, but unusually strong unit/integration/regression/property
  test taxonomy and format provenance.
- **Strengths:** typed canonical model; native round trips; cross-harness
  continuation; detailed Claude/Codex/Cursor/OpenCode/Grok format documents.
- **Limits:** writing native stores has higher blast radius than reading them;
  conversions can be semantically lossy; ChatGPT is an undocumented private
  API source and official export ZIPs are unsupported.
- **Verdict:** borrow its schemas/tests and trial manual continuation only.
  Explicitly forbid `--from chatgpt` and unattended writes.

### DuckDB

- **Observed maturity:** MIT, ~40,797 stars, active since 2018; embedded and
  non-resident. Native NDJSON readers and analytical SQL are mature.
- **Strengths:** excellent for local reproducible aggregates and portable
  derived snapshots; AgentsView already supplies the mirror.
- **Limits:** another full-text search layer is unnecessary; mirror may duplicate
  sensitive content; encrypted-mirror integration is not documented by
  AgentsView.
- **Verdict:** use only as a disposable on-demand AgentsView mirror.

### Redaction stack

- **AgentsView secrets:** first pass, zero additional runtime. Definite matches
  are found during sync; candidate heuristics require explicit backfill. Raw
  matches are not stored in `secret_findings`. Detection is not sanitization.
- **Gitleaks:** MIT, ~29,008 stars, active since 2018; local single binary.
  Strong secret egress gate. It does not detect ordinary PII and `--redact`
  protects findings output rather than rewriting a transcript.
- **Presidio:** MIT, ~10,676 stars, active since 2018. Mature Analyzer and
  Anonymizer support replace/redact/mask/hash/encrypt. Automated detection has
  no completeness guarantee; defaults are English-centric. Romanian names,
  addresses, CNP patterns, phone numbers, institutions, and engineering project
  identifiers need explicit recognizers, localized context, and false-positive
  tests.
- **Verdict:** structural minimization → AgentsView/Gitleaks secrets check →
  Presidio typed replacement → second secrets check. Run on demand only and
  never mutate canonical logs.

## Learning queries worth adding after the pilot

All are deterministic and should operate on content-free fields first:

1. Recurring failure signatures by agent/project/tool category.
2. Failure-to-rescue rate: errored or abandoned sessions followed by a
   completed session on the same project/problem window.
3. Retry and edit-churn distribution before versus after a skill/hook change.
4. Compaction count and context-pressure association with outcome.
5. Tools-per-turn, first-response latency, and turn-cycle time by agent/model.
6. Cache economics and output-token efficiency by task class.
7. Parser-malformed and truncated-session rates by source/version.
8. Secret-leak findings by location (`message`, `tool_input`, `tool_result`) and
   rule, without revealing values.
9. Git-correlated yield with explicit caveat that commits/LOC are not quality.
10. ISR join: hook fired/acted-on/cost versus session outcome, sourced from the
    event ledger rather than inferred from transcript text.

Do not promote a “learning” merely because one health score changed. Require a
predeclared metric, adequate recurrence, direct evidence, and a reversible
action/kill criterion.

## Risks and mitigations

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Raw secrets/PII duplicated into SQLite and DuckDB | High / high | Local ACL + verified encrypted volume; no sync; omit DuckDB if protection is unverified; run secret inventory |
| AgentsView optional semantic/insight features create a second memory plane or egress | Medium / high | Explicit negative config and adoption test; no vector/recall/insights sections |
| Fast parser/schema drift silently changes metrics | High / medium–high | Pin version; `parse-diff --fail-on-change`; retain malformed/truncated counts; reconcile with ccusage |
| Legacy Cursor database-only sessions are missed | Medium / medium | Measure against `state.vscdb`; borrow existing txcript/deja fixtures or upstream parser support only if a real gap exists |
| ChatGPT re-import skips continued conversations | Medium / medium | Preserve dated ZIPs; test update semantics; never delete the prior archive on importer claims |
| Heuristic outcome/health becomes false “truth” | Medium / high | Keep event ledger/artifact reads authoritative; label inferred fields and confidence |
| On-demand daemon remains alive under failure | Low–medium / medium | Foreground UI, one-minute idle timeout, and explicit `agentsview daemon stop` |
| PII detector misses Romanian/contextual entities | High / high at egress | Custom recognizers, known-entity denylist, test corpus, manual review for external sharing |
| Cross-harness conversion damages resumability | Medium / high | Backup-first, one session trial, native fixpoint and target resume test; no bulk writes |

## Adoption gate

Adopt after a 14-day bounded pilot only if:

- all eight coding-agent sources and one official ChatGPT ZIP are inventoried;
- recent source-session counts reconcile with native lists, with legacy Cursor
  coverage explicitly measured;
- ccusage and AgentsView token totals reconcile or every difference has a
  documented parser/roll-up reason;
- `parse-diff --fail-on-change` is non-vacuous and clean;
- unknown/malformed/truncated records are visible, not silently dropped;
- no network connection occurs except the deliberately disabled update/telemetry
  checks (verify mechanically);
- no vectors, recall extraction, generated insights, cloud sync, Quack, Gist, or
  remote source is configured;
- the daemon exits after each run;
- BitLocker or equivalent at-rest protection for source and derived archives is
  verified, or the DuckDB mirror is omitted;
- a candidate learning reaches basic-memory only through `write_note`, with no
  raw transcript body.

## Sources

Primary or project-maintained sources:

- AgentsView repository, configuration, commands, import, stats, session
  intelligence, secret scanning, and DuckDB mirror:
  <https://github.com/kenn-io/agentsview>,
  <https://agentsview.io/configuration/>,
  <https://agentsview.io/commands/>,
  <https://agentsview.io/chat-import/>,
  <https://agentsview.io/stats/>,
  <https://agentsview.io/session-intelligence/>,
  <https://agentsview.io/duckdb/>
- AgentsView v0.41.1 release:
  <https://github.com/kenn-io/agentsview/releases/tag/v0.41.1>
- ccusage repository and JSON output:
  <https://github.com/ryoppippi/ccusage>,
  <https://github.com/ryoppippi/ccusage/blob/main/docs/guide/json-output.md>
- txcript repository, crate docs, and test taxonomy:
  <https://github.com/skillsynchq/txcript>,
  <https://docs.rs/txcript/latest/txcript/>,
  <https://docs.rs/crate/txcript/latest/source/tests/README.md>
- DuckDB JSON loading and encryption:
  <https://duckdb.org/docs/current/data/json/loading_json>,
  <https://duckdb.org/2025/11/19/encryption-in-duckdb>
- Anthropic Claude Code data usage:
  <https://docs.anthropic.com/en/docs/claude-code/data-usage>
- OpenAI Codex configuration and non-interactive JSONL:
  <https://developers.openai.com/codex/config-advanced>,
  <https://developers.openai.com/codex/non-interactive-mode>
- Goose local session storage:
  <https://github.com/block/goose/blob/main/documentation/docs/guides/logs.md>
- Gemini CLI session management:
  <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md>
- xAI Grok Build session format:
  <https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/17-sessions.md>
- OpenCode CLI export/database commands:
  <https://opencode.ai/docs/cli/>
- OpenAI official ChatGPT export procedure:
  <https://help.openai.com/en/articles/7260999>
- Gitleaks:
  <https://github.com/gitleaks/gitleaks>
- Microsoft Presidio:
  <https://github.com/microsoft/presidio>,
  <https://microsoft.github.io/presidio/analyzer/languages/>,
  <https://presidio.dataprivacystack.org/anonymizer/>

Secondary alternatives reviewed:

- CodeBurn: <https://github.com/getagentseal/codeburn>,
  <https://codeburn.app/docs>
- deja-vu: <https://github.com/vshulcz/deja-vu>
- coding_agent_session_search:
  <https://github.com/Dicklesworthstone/coding_agent_session_search>
- AgentGraphed: <https://github.com/sudomichael/agentgraphed>
- ChatKeeper: <https://martiansoftware.com/chatkeeper/>
- Aider format implementation reference:
  <https://docs.rs/cross_agent_session_resumer/latest/casr/providers/aider/>

UNIT-COMPLETE: lens-05
