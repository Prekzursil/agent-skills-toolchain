# Lens 09 — Memory, provenance, corrections, knowledge promotion

> Gem-hunt 29.08.2026. **Discovery + decision queue, NOT a build.** Nothing installed, nothing
> edited, no secrets touched, no daemon started, no vault write. Read-only audit of the live
> harness on disk.
> Architecture lens: where does a *fact* enter the estate, how is it *attributed*, how is it
> *corrected*, and how does it get *promoted* from raw session → ledger → semantic store → rule.

## Binding constraints honored (not re-litigated)

| Constraint | How this lens complies |
|---|---|
| basic-memory `127.0.0.1:8765` is the SOLE semantic writer (G-81) | Every proposal writes through `write_note` or writes a **non-semantic** control-plane JSON under `~/.agents/state/harness`. No second store. |
| Hybrid search stays ON; semantic never disabled to buy RAM | No proposal touches `default_search_type`, the reranker, or FastEmbed. Ranking changes are in the **consumer** (recall index / injection), not the server. |
| Event ledger is objective turn history | All ledger proposals are **additive fields on existing event kinds**. No kind is redefined, no reducer semantics change. |
| Raw sessions remain evidence | Analytics stay **pointers + counts**. No transcript ingest into the vault (EPSS doctrine, already adopted 27.08). |
| Agent claims require disk verification | F5/F6 make the fail-closed doctrine *machine-checkable* instead of prose. |
| No competing vector / KG / cloud memory | Nothing proposed adds a vector index, a graph DB, a resident process, or a cloud sync. A3 (HippoRAG PPR) auto-apply stays DEFERRED. |
| No credential rotation, ever | Not touched. The expired HF token "Reframe" stays unrotated (launcher blanks it for the BM process only). |
| Never silently remove a feature | Every proposal is additive or shadow-first via the existing `stage()` ladder. |

## GROUND — dedup set actually read this pass (disk-verified)

**Doctrine / decisions**
- `C:\Users\Prekzursil\AGENTS.md` (behavior SSOT) — verification doctrine (Wave C), estate locks block, memory pointers, cross-tool behavior floor.
- `.agents\memory-contract.md` (memory SSOT, Lane Q2 28.08) — transport, recall, write, supersede, writer lock, reliability, WHERE table.
- `.agents\memory-map.md` (WHERE-map 28.08) — control-plane paths, 10 load-bearing vault notes, live plans S0/S1/S3/S4/Q3/Q4.
- `source\agent-skills-toolchain\.agents\CONSOLIDATED-GEM-DECISIONS_2026-08-27.md` (+ its pass-3 ADDENDUM, VERIFY-2, waves A–D, SKIP wall).
- `docs\agentic-perfection\AGENTIC-PERFECTION-PLAN.md` (T1–T3, round-2 reasoning spine, round-3 wildcards, skip list).
- `docs\agentic-perfection\OPEN-THREADS.md` (ACTIVE / QUEUED / build backlog incl. GEM-REFINEMENTS a0–c).
- `Cowork\output\basic-memory-sota-implementation_2026-08-28.md` + `_v2.md` — the current live memory state (0.23.2, hybrid default, Jina reranker ON, PPR deferred, gold-paraphrase MISS).

**Code actually read (not inferred)**
- `.agents\harness\ledger.py` (1543 lines) — `EventLedger`, typed receipts (SI-1), `argv_fingerprint`, `derived_from` → `taint_dependents` (B4), per-session goal isolation, state reducers.
- `.agents\harness\modules.py` (~3.7k lines) — `LedgerModule`, `RecallModule`, `SanitizedCheckpointModule`, `ClaimWarningModule._basic_memory_nudge`, `SubagentLifecycleModule`, `_write_session_spool` / `_flush_spool_to_vault`, `stage()` / `shadow_log()` ladder, `_session_flag` carriers.
- `.agents\harness\recall_index.py` — `SCHEMA_VERSION = 2`, importance heuristic, `superseded_by` / `is_failure_head` / `poisoned`, `_slim_note`, digest writer.
- `.agents\scripts\index-ai-sessions.py` — cross-AI session catalog indexer (pointers only, incremental state file).
- `.claude\plugins\cache\claude-reflect-marketplace\claude-reflect\3.1.0\` — `capture_learning.py`, `lib\reflect_utils.py` (pattern banks, queue schema, memory hierarchy helpers).
- `.agents\skills\agent-as-judge\SKILL.md` — kappa calibration against the claude-reflect corrections corpus.
- `.agents\skills\social-corpus-extraction\SKILL.md` + `scripts\isolate_messenger.py` / `isolate_whatsapp.py` — owner-identity handling (argv/env only).

**Already-decided → NOT re-proposed here.** Memory decay + lot-recall (`confidence/last_verified/expires` frontmatter) = consolidated STRONG-TECHNIQUES, REC TRIAL. Eviction landmarks / typed-episode eviction = pass-2 gem 8, ADOPT-later. Experience-compression tiers (note→skill→rule) = REC ADOPT. Hearsay/provenance grading on agent-mail = REC ADOPT. Verified-resume / spoliation = Wave C doctrine (this lens supplies its **missing mechanical half**, F5/F6, and says so explicitly). Per-hook ISR telemetry = planned-unbuilt prerequisite. A3 PPR auto-apply = DEFERRED (M2). Spool content-capture = OPEN-THREADS GEM-REFINEMENT a0 (this lens supplies the specific unbuilt slice, F10, and credits the thread).

---

## Findings at a glance

| # | Delta | Carrier it rides | Value × Effort | Conf |
|---|---|---|---|---|
| F1 | SessionStart/first-prompt **digest** read path has no poison filter and no supersession flag — the conditional lexical path has both | `recall_index._slim_note` + `modules._filter_digest_notes` | very H × L | HIGH |
| F2 | Supersession is flagged but the **successor is never named** in any injection | `RecallModule._composite_recall` + digest renderer | H × trivial | HIGH |
| F3 | Importance model has **no correction / preference / directive class**, and observation categories are never parsed at all | `recall_index._HIGH_IMPORTANCE_TAGS` + `_quality_factor` | very H × L-M | HIGH |
| F4 | **Romanian corrections are invisible** to claude-reflect → owner's native-language corrections never enter the corpus, and bias the judge's kappa | own `UserPromptSubmit` module writing the plugin's queue schema | very H × L | HIGH (gap) / MED (path) |
| F5 | Evidence hashes cover **argv, not artifacts** — "artifact exists on disk" is an existence test, not a content test | `LedgerModule._append_mutation` / `_append_task` / `_append_subagent` | very H × M | HIGH |
| F6 | `disk-verified` vs `agent-claimed` **exists only as prose**; no field in any record; its named carrier (`.beads\context\`) does not exist at `~` | `SanitizedCheckpointModule` frontmatter + ledger field + contract §write | H × L | HIGH |
| F7 | **`derived_from` / `taint_dependents` is fully built with ZERO live producers** — retraction cascade is dead-lettered | `ledger.taint_dependents` (already tested) | H × L | HIGH |
| F8 | Session **analytics never reach memory**; the indexer's own docstring is stale about it | `index-ai-sessions.py --digest` + existing SessionStart carrier | H × L-M | HIGH (gap) |
| F9 | **Shared estate, single-owner model** — Marius and Andrei are two people, but every fact in `AGENTS.md` is stated as universal, so an Andrei session inherits Marius's facts by default | `AGENTS.md` marker split + new `~/.agents/identity-map.json` consumed by 3 existing readers | very H × L-M | HIGH (owner-verified 29.08) |
| F10 | A **failed `write_note` is not spooled** — the spool captures a generic session stub, never the lost payload | `LedgerModule._append_failure` + `RecallModule._retry_spool_flush` | very H × L | HIGH |

---

## F1 — The primary read path is the *unguarded* one

**Measured.** Two recall paths exist and they disagree about safety.

The **conditional** path, `RecallModule._composite_recall`, skips any note with `poisoned is True`
(index-time prompt-injection detection via `injection_grammar.looks_poisoned` over
`DIRECTIVE_CATEGORIES`) and renders a ` *contradiction*` marker when `superseded_by` or
`is_failure_head` is set. It only runs on `UserPromptSubmit`, only when the prompt is ≥40 chars and
yields ≥4 tokens, and only when lexical relevance clears 16.

The **unconditional** path — the vault digest injected on **every** SessionStart *and* on the first
UserPromptSubmit, which `memory-map.md` designates as *the* READ ("SessionStart / first prompt READ
comes from the slim digest") — does neither:

- `recall_index._slim_note()` emits exactly `title, path, permalink, mtime, importance, summary`. It **drops** `superseded_by`, `is_failure_head` and `poisoned`.
- `modules._filter_digest_notes()` filters on path exclusion only.
- `RecallModule._session_vault_digest()` renders `- {title} | {path}` under a banner that says UNTRUSTED.

Net: a poisoned note is silently promoted into the always-on read path, and a superseded note is
indistinguishable from live knowledge there. "UNTRUSTED historical context" is a label, not a guard —
the same reasoning the codebase already applied in P1C22 when it started refusing undatable indexes.

**Wire actions**
1. `recall_index.py::_slim_note` — add three optional keys, only when truthy: `superseded_by` (str), `is_failure_head` (bool), `poisoned` (bool). **Do not bump `SCHEMA_VERSION`** — `_RECALL_INDEX_SCHEMA_VERSION = 2` is the consumer ceiling and the added keys are optional; an old digest without them must keep serving (that is already the documented degradation contract for the SI-5 fields).
2. `modules.py::_filter_digest_notes` — `continue` on `item.get("poisoned") is True`, mirroring `_composite_recall` verbatim so the two paths cannot drift.
3. `modules.py::_session_vault_digest` — render the flag: `- {title} | {rel}{flag}` where `flag` is ` [SUPERSEDED→{target}]` / ` [FAILURE-HEAD]`. Keep the 2400-char cap.
4. `_notes_are_keyword_free()` is unaffected (it only rejects a `keywords` list) — assert that in a test so nobody "fixes" it later.

**Tests**
- `test_digest_drops_poisoned_note` — build a digest containing one `poisoned: true` note; assert it never reaches `additional_context`.
- `test_digest_renders_supersession_target` — assert the successor permalink appears in the injected line.
- `test_digest_serves_v2_index_without_si5_fields` — old-shape notes still inject (no regression).
- `test_digest_and_composite_agree_on_poison` — parametrized over one fixture note, both paths must exclude it.

**Value × effort:** very HIGH × LOW (~30 lines, 2 files). **Confidence: HIGH** — read directly from source, both paths, this pass.
**Risk:** none material; strictly reduces what is injected. Ship in ENFORCE, not shadow — a poison filter that only observes is pointless.

## F2 — Supersession without a successor is a trap

The contract is explicit: *"Keep the old note. Do not silently rewrite history. Recall must still
find the dead-end."* Correct. But `_composite_recall` renders a bare ` *contradiction*` and never
prints `superseded_by`'s target, and `_quality_factor` **boosts** exactly those notes by 1.6×
(contradiction-first). So the highest-boosted recall result is a dead fact with no forwarding
address. An agent that trusts the boost re-adopts the retracted knowledge.

**Wire actions**
1. `_composite_recall` — when `superseded_by` is set, append `→ {superseded_by}` to the rendered line (before the summary, inside the existing 2400-char budget).
2. Same for the digest (folded into F1 action 3).
3. **Referential integrity report (read-only).** `bm-graph-ppr.py` already copies `memory.db` without binding `:8765` and reports **810 entities / 751 relations / 310 resolved directed edges / 439 unresolved `to_id` null**. Add a `--dangling` mode to that existing script that lists `superseded_by` targets which resolve to nothing. Report only — **no auto-apply** (respects the A3/M2 deferral and the false-link risk already recorded).

**Tests** — `test_recall_names_supersession_target`; `test_dangling_report_flags_unresolved_superseded_by` (fixture DB copy, asserts exit 0 + a count, never a write).
**Value × effort:** HIGH × TRIVIAL (F2.1/F2.2), MED × LOW (F2.3). **Confidence: HIGH** (code + the 439 figure is a disk-verified receipt from 28.08).

## F3 — Corrections do not outrank status updates

`recall_index._HIGH_IMPORTANCE_TAGS` = `{current, keystone, important, critical, decision,
milestone, star, starred, pinned, canonical, high}`. Absent: **correction, preference, requirement,
directive, lock, owner-rule, never**. A note recording a HARD owner rule ("NEVER rotate
credentials", "never silently remove a feature") lands at the default 0.5 unless a human remembered
to tag it — while a fresh routine status note gets +0.15 for being ≤7 days old. Recency currently
outranks bindingness.

Worse: the contract *mandates* observation categories — `- [decision]`, `- [fact]`,
`- [requirement]`, `- [preference]`, `- [bug]` — and calls a note without them "a failed write". The
indexer **never parses observations at all**. `_keywords()` is built from title/permalink/summary;
the single most semantically load-bearing convention in the whole memory contract is invisible to
ranking. The same is true of `[[wikilinks]]`.

**Wire actions**
1. `recall_index.py` — add `_observation_categories(body)`: one bounded regex `^\s*-\s*\[([a-z_-]{2,20})\]` over the first N lines (cap ~400 lines / 64 KB, notes are already ≤100 KB by Q5), returning a small sorted set. Store as `obs` on the note.
2. Extend `_HIGH_IMPORTANCE_TAGS` **and** treat `obs ∩ {correction, requirement, preference, directive, decision}` as a high-importance signal in `_default_importance` (a second `+0.2`, still `_clamp01`-bounded, so an explicit `importance:` value keeps winning — `_explicit_importance` short-circuits first).
3. `modules.py::_quality_factor` — add a **binding multiplier** (start 1.3, below the 1.6 contradiction boost so contradiction-first is preserved) when `obs` carries `correction`/`requirement`/`directive`. Route it through the existing `stage()` ladder as gate name `correction_priority` so it lands SHADOW → ADVISE → ENFORCE with `shadow_log` evidence rather than as a blind ranking change.
4. Fold `obs` into `_slim_note` (one short list) so the digest path can order by bindingness too.

**Tests**
- `test_observation_categories_parsed_and_bounded` (incl. a 200 KB adversarial body → parser stops at the cap).
- `test_correction_note_outranks_fresher_status_note` — two notes, equal lexical relevance, assert order.
- `test_explicit_importance_still_wins` — `importance: 0.1` + `- [correction]` stays 0.1.
- `test_contradiction_boost_still_dominates` — 1.6 > 1.3 invariant asserted numerically.

**Value × effort:** very HIGH × LOW-MED (~60 lines, 2 files + a reindex run). **Confidence: HIGH** on the gap; **MED** on the exact multipliers — which is precisely why they go through the shadow ladder instead of straight to ENFORCE.
**Note:** requires one `recall_index` rebuild to populate `obs`. That is an existing offline path (embeddings stay off the request loop), not a new process.

## F4 — The owner's Romanian corrections never enter the corpus

`claude-reflect` 3.1.0 is enabled. Its capture bank is `CORRECTION_PATTERNS` (English-only:
`^no[,. ]+`, `^don't`, `^stop|^never`, `that's wrong`, `^actually`, `^I meant/I said`,
`^I told you`, `use X not Y`), `GUARDRAIL_PATTERNS` (English), `CJK_CORRECTION_PATTERNS`
(Japanese / Chinese / Korean), and `EXPLICIT_PATTERNS` = **`remember:` only**. Romanian: absent.

The plugin's own design note says non-English corrections "are caught by semantic filtering during
/reflect" — true but weaker in two measurable ways: live `UserPromptSubmit` capture (with its
confidence and `decay_days`) never fires, and the queue is the **kappa ground-truth corpus** for
`agent-as-judge` (`LABEL_CORPUS = ~/.claude/learnings-queue.json`, `KAPPA_BAR = 0.6`,
`MIN_LABELED = 30`). So the judge is calibrated on a corpus that systematically under-samples the
owner's native-language corrections. A caught-error corpus that is also language-skewed is a
narrower license to speak than it looks.

**Do NOT fork the plugin.** It lives under `~\.claude\plugins\cache\...\3.1.0\` — a versioned cache
directory, clobbered on update, and `~\.claude` is a materialized sync target (G-97/G-98). Editing
it is exactly the drift the estate locks forbid.

**Wire actions**
1. Add `RO_CORRECTION_PATTERNS` to a harness-owned module (`.agents\harness\modules.py`, or a small sibling imported by it) on the existing `UserPromptSubmit` seam — **no new hook**. Strong openers: `^nu[,. ]`, `^nu\b.*\bnu\b`, `^ba nu`, `^greșit|^gresit`, `^nu (așa|asa)`, `(ți|ti)-am (zis|spus)`, `^de fapt[,. ]`, `^opre(ște|ste)|^nu mai`, `folose(ș|s)te .{1,30} nu\b`, `nu (adăuga|adauga|modifica|atinge) .{1,40} (dacă|daca) nu`. Explicit markers: `re(ț|t)ine:`, `(ț|t)ine minte:`.
2. Mirror the plugin's **false-positive discipline** — Romanian question/task openers must be excluded or every request becomes a "correction": `^po(ț|t)i\b`, `^ai putea`, `^te rog`, `^vreau\b`, `^am nevoie`, `^cum\b.*\?$`, trailing `?`. Also the polite non-corrections: `^nicio problem(ă|a)`, `^nu-i nimic`, `^nu conteaz(ă|a)`, `^nu te (îngrijora|ingrijora)`.
3. Write items in the plugin's **exact** schema (`create_queue_item`: `message, type, patterns, confidence, sentiment, decay_days, timestamp`) so `/reflect`, `read_queue.py` and the judge's `read_label_corpus()` consume them unchanged. Ceiling `MAX_CAPTURE_PROMPT_LENGTH = 500`, `remember:`-style markers exempt — mirror both.
4. **Pre-flight, do not assume:** `reflect_utils.get_queue_path()` is *project-scoped* (plus `migrate_global_queue`), while `agent-as-judge` hardcodes `HOME/.claude/learnings-queue.json`. Under home-as-workspace these may or may not be the same file. Resolve the live path by import (`get_queue_path()`), never by hardcoding, and log which file was written. Marked **NOT-CHECKED** in this lens.
5. Emit a `SUBSET-USED`-style one-liner naming the language bank that fired, so the corpus records language provenance and kappa can be computed **per-language**.

**Tests**
- `test_ro_correction_detected` / `test_ro_explicit_marker_detected`.
- `test_ro_polite_request_is_not_a_correction` (the false-positive wall — the expensive failure mode).
- `test_queue_item_schema_matches_plugin` — assert key-for-key against `create_queue_item`'s output.
- `test_queue_path_resolved_by_import_not_hardcoded`.
- `test_diacritics_and_cedilla_variants` (`ș/ş`, `ț/ţ` — the same Romanian cedilla trap already handled in `social-corpus-extraction`; reuse that normalization, do not re-derive it).

**Value × effort:** very HIGH × LOW. **Confidence: HIGH** on the gap (pattern banks read verbatim); **MED** on the live queue path (item 4).
**Sources (external, NOT re-verified live this pass):** plugin behavior is from the installed 3.1.0 source on disk, which is authoritative for this box. Cohen's kappa ≥ 0.6 = "substantial" (Landis–Koch) is inherited from `agent-as-judge\SKILL.md`, not independently re-checked.

## F5 — Evidence hashes cover the command, never the artifact

The receipt layer is genuinely strong: `argv_fingerprint` = sha256 of whitespace-normalized argv,
`receipt_status` refuses to mint green on exit-code laundering (`|| true`, `| tee`), on
informational flags (`--version`, `--collect-only`), on read-only heads (`echo`, `cat`), and on
zero-tests-ran; `_is_command_tool` fails closed so only an executing tool may mint a receipt. That
is a well-built gate and this lens proposes nothing against it.

The gap is one layer over. `_append_tool_result` stores `result_hash` (hash of the tool *output*).
`_append_mutation` stores `path` — which the ledger's own `_sanitize_value` then redacts to
`[PATH]`, and the code says so explicitly (that is why `canonical_tree` is stamped at append time as
a redaction-surviving alnum token). `_append_task` / `_append_subagent` store `output_hash` — a hash
of the assistant **message**, i.e. of the *claim*. Nothing anywhere hashes the **artifact**.

So the Wave C doctrine — *"a completion claim is credited only when its promised artifact exists on
disk"* — is satisfied by an empty file, a truncated write, or a stub. Existence is not content.
Wave C is deliberately doctrine-only pending Wave B's observe-mode latency evidence; this is the
mechanical half, and it can land in SHADOW so it costs nothing until that evidence arrives.

**Wire actions**
1. `LedgerModule._append_mutation` — additive fields `artifact_sha` (first 12 hex of sha256) and `artifact_bytes`. Bounded: skip files > 1 MiB (record `artifact_bytes` only), single stat + single read, wrapped in the existing `try/except` (the caller already swallows — keep F3's lesson from that file: give the new code its **own** guard so a raise cannot discard the ledger row below it). Pure hex + an int survive `_sanitize_value` untouched — the same property `receipt_fp` already depends on.
2. `_append_task` / `_append_subagent` — additive `artifact_paths` (canonical-tree tokens, redaction-safe) + `artifact_sha` list, and `provenance` (F6).
3. Add `EventLedger.artifact_matches(cwd, path_token, sha) -> bool` next to `has_fresh_receipt`, same bounded chronological scan, same fail-open. Resume flows call it instead of `Path.exists()`.
4. Honor the **grace window**: the comparator returns `PENDING` (not `FAIL`) on a first miss and records `recheck_after_s: 60`. The doctrine already names transcript-flush lag under RAM pressure; the code must not draw an adverse inference the doctrine forbids.
5. Register as gate `artifact_evidence` in the `stage()` ladder → SHADOW first, `shadow_log` only.

**Tests**
- `test_mutation_stamps_artifact_sha_and_bytes`; `test_large_file_records_bytes_without_hashing`.
- `test_artifact_sha_survives_sanitizer` (the redaction property, asserted not assumed).
- `test_empty_artifact_fails_content_check_but_passes_existence` — the whole point of the finding.
- `test_first_miss_is_pending_not_fail` (grace window) and `test_second_miss_after_window_is_fail`.
- `test_append_mutation_row_survives_hash_exception` (the F3 own-guard lesson).

**Value × effort:** very HIGH × MED. **Confidence: HIGH.**

## F6 — `disk-verified` vs `agent-claimed` has no field and no live carrier

`AGENTS.md` says checkpoints and execution-state records **carry** a provenance tag. On disk:
`grep provenance` across `.agents\harness` returns `LedgerModule._provenance` (which emits
`parent_id` lineage — useful, but a *different* thing) and test names. No record carries the tag.
And `AGENTS.md` itself already measured that `.beads\plans\` and `.beads\context\` **do not exist**
at `~` — so the doctrine's named carrier is absent while the ledger, which does exist and is
append-only and locked, is not named.

`SanitizedCheckpointModule` writes frontmatter `type/provider/project/timestamp/session_hash` plus a
ledger pointer. Notably it re-reads `.remember\now.md` and the ledger state from disk on every run —
so its checkpoints are *legitimately* `disk-verified` and can say so truthfully today, for free.

**Wire actions**
1. `SanitizedCheckpointModule` — add `provenance: disk-verified` to the frontmatter, plus `artifacts_read:` listing what was actually re-read this run. Truthful by construction; never hardcode the string where the re-read did not happen.
2. `ledger.append` call sites for `task` / `subagentstop` — add `provenance` = `disk-verified` when F5's `artifact_matches` returned true, else `agent-claimed`. One field, existing rows.
3. `memory-contract.md` §"Write — durable decisions" — add `provenance: disk-verified | agent-claimed` to the required frontmatter block. It is the SSOT; adding it there propagates to every runtime by pointer, with **no second copy** (Q2 rule).
4. **Retarget the doctrine at the real carrier.** Amend the `AGENTS.md` verification-doctrine paragraph to name the event ledger as the provenance carrier and demote `.beads\context\execution-state.md` to "write-on-first-use, absent at `~`, treat as `NOT-CHECKED`" — which is what the same file already says two paragraphs later. This is the cheapest correctness win in the lens: it deletes a claim about a carrier that does not exist, in a file paid for on **every turn of every agent** (the same token-per-turn argument that made TIER-0 #3/#5 the best returns of the 27.08 hunt).

**Tests** — `test_checkpoint_frontmatter_carries_provenance`; `test_provenance_agent_claimed_when_artifact_missing`; `test_contract_pointer_files_have_no_second_copy` (guards the Q2 no-fork rule).
**Value × effort:** HIGH × LOW. **Confidence: HIGH.**

## F7 — The retraction cascade is built, tested, and has zero producers

`EventLedger.taint_dependents(cwd, falsified_ref)` walks a 200-event window for events whose
`derived_from` list contains a falsified reference, appends a `kind="taint"` marker, and is
fail-open. It is covered by named tests (`test_ledger_receipts_and_taint.py`,
`test_cov_ledger.py`). And `derived_from` is written **only inside those tests** — no production
module emits a provenance edge. The single-level design is deliberate (the docstring says the
external trigger owns DAG traversal by re-invoking) — but that trigger does not exist either.

This is the TMS auto-retraction gem from the plan's round-3 list, **already half-built and idle**.
That makes it the cheapest high-value item here: the expensive part shipped; only the producers are
missing.

**Wire actions**
1. Emit `derived_from` at three existing append sites where the edge is already known: (a) `_append_task` / `_append_subagent` → `derived_from=[parent claim ref]` (`parent_id` is already resolved by `_provenance`); (b) `decision` events written after a receipt → `derived_from=[receipt_fp]`; (c) `mutation` events whose rationale cites a prior note permalink → `derived_from=[permalink]`.
2. One trigger, on an existing seam: when a `superseded_by` is written (F2) or a `receipt_status` flips `pass → fail` for a known `receipt_fp`, call `taint_dependents` with that ref. No new hook, no DAG engine — one call, single level, exactly as designed.
3. Surface `kind="taint"` rows in the existing `_recovery_replay` injection (it already renders `decision`/`failure`/`milestone`) so a resumed session learns its premises were retracted.

**Tests** — `test_task_event_carries_derived_from_parent`; `test_receipt_flip_triggers_taint`; `test_taint_rows_surface_in_recovery_replay`; `test_no_producer_no_taint` (absence of edges stays silent — fail-open preserved).
**Value × effort:** HIGH × LOW. **Confidence: HIGH** (grep evidence: production writers = zero).

## F8 — Session analytics never reach memory, and the indexer says otherwise

`index-ai-sessions.py` opens: *"a catalog of pointers … so past sessions are searchable from
basic-memory. It deliberately does NOT ingest transcripts."* The second sentence is correct policy
and must stay. The first is **stale**: line ~38 of the same file records that on 27.08.2026 the
catalog moved **out** of the vault, `~\.basic-memory\.bmignore` now ignores `session-catalog.md`,
and the only vault presence is a dated pointer note `sessions\sessions-catalog-2026-08-27.md`
(itself a snapshot pointer to a 378 KB blob that regenerates constantly and previously blew up to
~1,482 chunks). So the catalog is reachable by a human following a pointer, and unreachable by
recall.

The larger gap is that the **analytics** — which runtimes ran, which sessions froze, which subagents
died mid-work (the standing failure mode), how many corrections landed — are computed nowhere, so
the estate's single richest evidence source feeds nothing. Note the existing primitive:
`SubagentLifecycleModule._stalled_sentinel` already defines the frozen-transcript rule (mtime age
> 25 min). The same predicate over the catalog's incremental state file yields a fleet-level number
for free.

**Wire actions**
1. Fix the docstring (one line): state that the catalog is a **control-plane** artifact outside the vault, reachable via the dated vault pointer, and deliberately `.bmignore`d.
2. Add `--digest` to `index-ai-sessions.py` emitting `~\.agents\state\harness\session-analytics.json`: per-runtime session counts, last-7-day counts, and `stalled_recent` using the **same** >25-min frozen-mtime rule as `_stalled_sentinel` (one predicate, two consumers, no drift). Pointers and integers only — never snippets, never transcript text.
3. Surface it through the **existing** SessionStart carrier, threshold-gated (inject only when `stalled_recent > 0`), routed through `stage()` as gate `session_analytics`, SHADOW first. No new hook, no new process — the local-models-audit constraint ("nothing in this hunt may add a resident process") binds here.
4. Promotion path stays owner-gated: `/reflect` may turn a recurring analytic pattern into a `write_note` decision. The **script never writes the vault** — G-81 keeps `write_note` as the sole semantic write, and the indexer is not a semantic writer.

**Tests** — `test_digest_emits_counts_not_snippets` (assert no prose leaks); `test_stalled_rule_matches_sentinel_predicate` (shared-predicate guard); `test_digest_is_idempotent_on_rerun`; `test_indexer_never_writes_vault`.
**Value × effort:** HIGH × LOW-MED. **Confidence: HIGH** on the gap; the "1,482 chunks" and `.bmignore` facts are disk-verified receipts from 28.08, not re-measured this pass.

## F9 — Two people share this estate, and every fact defaults to Marius

**RESOLVED — owner-verified in-session, 29.08.2026 (provenance: `owner-stated`, not `disk-verified`;
no disk artifact records it yet, which is itself wire action 0 below).**

> **Andrei Visalon is a separate person — the son of Marius Valentin Visalon. This is a shared
> AI-tool estate.** They are **never** aliases of one another, and Marius-specific facts,
> preferences, and defaults **never** inherit into Andrei.

This inverts the finding. The earlier open question ("alias or distinct person?") assumed the risk
was *fragmentation* — one human split across two profiles. The real risk is the opposite and it is
live right now: **conflation plus silent inheritance**, in a store that already holds professional,
research, and credential-adjacent material.

**What is actually on disk (unchanged, re-stated against the correct model).** `AGENTS.md` declares
exactly one identity — *"My name is Miky (Marius Valentin Visalon). I am a civil engineer and Head of
Technical Service in Romania."* — and then, unconditionally, an entire behavioral profile keyed to
that one person: Romanian for work documents, DD.MM.YYYY, Romanian civil-engineering terminology,
Sonnet/Opus routing preferences, the phenibut research lane, institutional e-nformation credentials,
and a `## Learned User Preferences` block written from Marius's frustrations. Every one of those is
injected on **every turn of every agent**, with no person predicate. `social-corpus-extraction`
hardcodes no identity (`--owner-name` repeated, `--me`) but takes it purely from argv, and its
self-test normalizes `" Andrei   Visalon "` to the owner key — i.e. the one place in the estate that
has ever seen Andrei's name treats it as *the* owner. Nothing in the harness, the recall index,
`redaction.py`, `identity`-anything, or `memory-contract.md` has a person dimension at all.

**The three failure modes now open, in severity order.**

1. **Silent inheritance (active, not hypothetical).** An Andrei session inherits Marius's job title, output language contract, date format, research lane, learned preferences, and institutional-access affordances, because those facts are stated as universal rather than person-scoped. Nothing has to go wrong for this to happen — it is the default path today.
2. **Surname collision → accidental alias merge.** Any matcher keyed on `Visalon`, on a last name, on a fuzzy/`in`-substring test, or on "the owner" as a singleton will merge the two people. `norm_name(" Andrei   Visalon ") == owner` is exactly that bug already written down as a passing assertion. Alias resolution must therefore be **exact-full-string against an explicit per-profile list**, never surname-based, never fuzzy, never "contains".
3. **Cross-person leakage in memory and corpus.** Andrei's material surfacing in a Marius work session (or the reverse) in a store that also holds professional and credential-adjacent notes. And `social-corpus-extraction`'s own scope bar — *"NOT for scraping other people's content"* — now binds **per profile**: running it for one person over the other's export is out of scope by the skill's own contract, not merely impolite.

**The architectural correction: scope tiers, not two owners.** "Shared estate" means the split is
three-way, not two-way. Modeling it as two owner profiles would wrongly duplicate the harness locks;
modeling it as one owner is what produced the bug.

| Tier | Contents | Applies to |
|---|---|---|
| `estate` | G-81 sole-writer, port ownership (`:8765`/`:8812`/`:8317`), NEVER-ROTATE, never-silently-remove-a-feature, RAM constraints, one-`cursor-agent`, skills SSOT, TDD/coverage discipline, fail-closed verification | **both**, unconditionally |
| `person:marius` | job title + Head of Technical Service framing, Romanian work-document contract, DD.MM.YYYY, RO civil-engineering terminology, phenibut/research lanes, institutional e-nformation access, the `Learned User Preferences` block, model-routing taste | Marius only |
| `person:andrei` | empty until Andrei's own facts are captured — **an empty profile inherits nothing** | Andrei only |

The load-bearing invariant: **`estate` facts are shared; `person:*` facts never cross, and an absent
person profile yields silence, not Marius's defaults.**

**Wire actions**
0. **Record the correction as evidence** (do first — it currently exists only in conversation): one `write_note` capturing `- [fact] Andrei Visalon is a separate person, son of Marius Valentin Visalon` + `- [decision] person facts never inherit across profiles; alias matching is exact-full-name only`, with `[[wikilinks]]` per the contract, and a matching `- [fact]` line in `AGENTS.md`'s identity section. Until this lands, the ruling is unbacked prose and a future agent will re-derive the wrong model from the fixture.
1. `~\.agents\identity-map.json` (control-plane JSON, **not** a vault note, **not** a second memory store — G-81 untouched): `{"schema_version":1,"profiles":[{"id":"person:marius","display_names":["Marius Valentin Visalon","Miky"],"vault_folder":"person/marius","inherits":["estate"]},{"id":"person:andrei","display_names":["Andrei Visalon"],"vault_folder":"person/andrei","inherits":["estate"]}],"never_alias":[["person:marius","person:andrei"]]}`. Gitignore it — it names a second, non-consenting-by-default person. The explicit `never_alias` pair is the machine-readable form of the owner ruling, so a future alias-merge heuristic trips a test instead of a person.
2. **Matching discipline, enforced in code not prose:** exact, case-folded, whitespace-normalized full-string match against `display_names`. Reject surname-only and substring matching outright. An unmatched name resolves to `unknown` → the session runs `estate`-only and **injects no person facts** (fail-closed toward silence, the same direction `_session_flag` already fails for advisories).
3. **Split `AGENTS.md`.** Move the person-scoped block behind a marker (`<!-- person:marius:start -->` … `:end`), mirroring the existing marker-delimited `AgentBridge` / `estate-locks` convention already used in that file, so it is mechanically extractable and re-writable. The `estate` tier stays unconditional. This is the single highest-leverage edit in F9 — it is also the *only* one that stops the inheritance that is happening today.
4. **Three existing consumers read the map.** `social-corpus-extraction` defaults `--owner-name` / `--me` from the active profile (argv still overrides — the skill's no-hardcoded-identity rule is preserved, the map is only a default source) and **refuses** to run one profile's owner key against another profile's export directory. Person-scoped `write_note` calls carry `profile:` frontmatter + the mapped `vault_folder`. `redaction.py` gains a cross-profile check: another profile's `display_names` appearing in this profile's outbound context is a leak signal.
5. **Recall consequence (the payoff, and no feature is lost).** `RecallModule` filters the digest and the composite recall to `profile ∈ {estate, active person}`. Nothing is deleted, nothing is disabled, hybrid search stays ON — this is folder-scoped filtering, exactly the mechanism F1/F3 already touch. Notes with no `profile:` (every note written before this) default to `estate` so recall never goes dark mid-migration; a follow-up pass can reclassify.
6. **Cross-link — do this before F3/F4, not after.** A captured correction must carry its **author profile** or correction-priority will apply one person's correction to the other with a `1.3×` boost, which is worse than not capturing it. So: `create_queue_item` gains `profile`, and F3's `obs`-based binding multiplier only fires for the active profile's corrections plus `estate`. Note the live hazard: `reflect_utils.get_queue_path()` is **project**-scoped, and under home-as-workspace both people would share one queue file. Person scoping of the queue is a prerequisite, not a nicety.

**Tests**
- `test_marius_and_andrei_never_resolve_to_one_profile` — asserts the `never_alias` pair; the direct regression guard on the owner ruling.
- `test_surname_only_match_is_rejected` and `test_substring_match_is_rejected` — the `Visalon` collision, both matcher shapes.
- `test_andrei_session_inherits_no_marius_facts` — parametrized over the person-scoped set (job title, output language, DD.MM.YYYY, phenibut, institutional access, learned preferences); each must be **absent**. This is the test the finding exists for.
- `test_andrei_session_still_gets_estate_locks` — the other half: G-81, ports, NEVER-ROTATE, RAM rules **must** be present. Isolation must not weaken the estate floor.
- `test_empty_person_profile_yields_silence_not_defaults` — an empty `person:andrei` injects nothing, and specifically not Marius's block.
- `test_unknown_name_runs_estate_only`.
- `test_untagged_note_defaults_to_estate` (no recall blackout during migration).
- `test_corpus_script_refuses_cross_profile_owner_key`.
- `test_redaction_flags_cross_profile_name_leak`.
- `test_correction_queue_item_carries_author_profile`.
- `test_identity_map_absent_is_fail_open` — no map → today's behavior exactly, so the change is safely revertible by deleting one file.
- `test_identity_map_is_gitignored` — it names a second person.

**Value × effort:** **very HIGH × LOW-MED.** Value rose from HIGH: this is no longer a latent
attribution gap but a live, default-path inheritance defect affecting a second, real person.
Effort is unchanged and small — one JSON file, one marker split in `AGENTS.md`, and a filter
predicate on carriers F1/F3 already modify.
**Confidence: HIGH on the semantics** (owner-verified this session, supersedes the earlier LOW) /
**HIGH on the absence** (grep + code read of the harness, recall index, and contract).
**Sequencing:** F9 action 0 and action 3 move to **Wave 1** (they delete a false universal claim from
always-injected text — the same token-per-turn argument as F6.4). F9 action 6 gates F3/F4.
**Residual, honestly flagged:** whether Andrei's material should live in this vault at all — versus a
separate profile root — is a **consent and data-minimization question for the owner**, not an
architectural one, and I am not deciding it here. The map above is correct either way: change one
`vault_folder` value and the material relocates without touching the matching or inheritance rules.

## F10 — A failed `write_note` loses its payload

`OPEN-THREADS` GEM-REFINEMENT (a0) flagged this and it is **still open** — credited, not re-claimed.
The specific unbuilt slice, measured this pass:

`_write_session_spool` writes a **generic stub** — title `Session capture {date} {workspace}`, body
"this session mutated files and did not call write_note". It is triggered by
`ClaimWarningModule._basic_memory_nudge`, i.e. by the *absence* of a write. `_flush_spool_to_vault`
best-effort flushes that stub via the `basic-memory` CLI, and `RecallModule._retry_spool_flush`
re-tries unflushed spools at SessionStart. Good machinery — but nothing intercepts an **attempted**
`write_note` that *failed*. If the daemon is down (and 4-hour outages are the documented reason this
spool exists), the model's actual note content is gone; only a stub remains.

The interception seam already exists and already fires: `LedgerModule.run` routes
`PostToolUseFailure` / `PermissionDenied` to `_append_failure`, and `_BM_WRITE_TOOL_NAMES` is
already the shared module-level list read by both the ledger stamp and the nudge.

**Wire actions**
1. In `_append_failure`: if `event.tool.name` matches `_BM_WRITE_TOOL_NAMES`, persist the **full** `event.tool.input` (title + content + tags + folder) to `bm-spool/{session}-{n}.json` verbatim, after `contains_secret()` on both title and body — `_flush_spool_to_vault` already refuses on a secret hit; keep that gate, do not weaken it.
2. Extend `_retry_spool_flush` to flush payload spools with their real title/content instead of the stub. It already iterates `bm-spool/*.json` and marks `flushed` — one branch.
3. Keep the ≤4000-char content cap the CLI path already imposes, and record `truncated: true` when it bites, so a silent truncation is never mistaken for a faithful flush.
4. Do **not** flush during pytest — the existing `PYTEST_CURRENT_TEST` / `HARNESS_BM_FLUSH_IN_TEST` guard must cover the new path too, or a test run writes the live vault.

**Tests** — `test_failed_write_note_spools_full_payload`; `test_spool_refuses_secret_payload`; `test_retry_flush_uses_real_title_not_stub`; `test_truncation_is_recorded`; `test_no_vault_write_under_pytest`.
**Value × effort:** very HIGH × LOW (~20 lines, one file, reuses the entire retry path). **Confidence: HIGH.**

---

## SKIP — anti-overfit wall for this lens

| Skipped | Why |
|---|---|
| Any vector store / embedding index outside basic-memory | G-81 + the SKIP wall of 27.08. Ranking fixes belong in the **consumer**, and F1/F3 prove there is real headroom there. |
| Graph/KG memory, HippoRAG **auto-apply** | A3 apply is DEFERRED (M2) on false-link risk; 439 unresolved `to_id` rows say the graph is not ready to write back. F2.3 stays a read-only report. |
| Forking `claude-reflect` to add Romanian | Plugin cache is clobbered on update and `~\.claude` is a materialized sync target (G-97/G-98). Own the pattern bank in `.agents`, write the plugin's schema. |
| A new hook per finding | The ~6-active-hook latency ceiling and the Stop-event 144s/35s oversubscription already documented. Every proposal above rides an existing seam. |
| Any resident process / daemon / scheduled window | `local-models-audit` constraint; MemGuard already disabled by owner 28.08. |
| Ingesting transcripts into the vault | Raw sessions are evidence; EPSS structured-result doctrine already adopted. F8 emits counts and pointers only. |
| Re-proposing memory decay frontmatter, eviction landmarks, ISR telemetry, note→skill promotion tiers | Already in the 27.08 decision queue with a REC. Duplicating them would be exactly the bloat this hunt is supposed to prevent. |
| Rotating the expired HF token that 401s public FastEmbed fetches | NEVER-ROTATE is absolute. The launcher's token-blanking is the correct fix and is already live. |
| Touching `default_search_type`, the reranker, or the gold-paraphrase miss | Server-side; owned by the sequenced-reindex lever, explicitly not this lens. Disabling anything to buy RAM is forbidden. |

## Sequencing (cheapest correctness first, matching the hunt's own Wave-A logic)

1. **Free corrections, one sitting, all reversible.** F6.4 (delete the false carrier claim from `AGENTS.md`, name the ledger) → F8.1 (fix the stale docstring) → F2.1/F2.2 (name the successor) → F6.1/F6.3 (truthful `provenance` in checkpoints + contract). Two of these delete false claims from always-injected or always-read text.
2. **The two silent-loss fixes.** F10 (failed-write spooling) then F1 (poison filter on the always-on read path). Both are small, both close a documented loss class, both ship ENFORCE.
3. **Correction priority.** F3 + F4 together — the ranking change and the corpus that feeds it, shadow-first, with the reindex run once.
4. **Provenance made mechanical.** F5 then F7 — artifact hashing first (it produces the signal), then the retraction producers (they consume it). Both SHADOW until Wave B's latency evidence lands, per the existing gate on Wave C enforcement.
5. **F9 is unblocked and partly promoted.** The person model is owner-verified (two people, no
   inheritance). Its action 0 (record the fact) and action 3 (marker-split the person-scoped block out
   of `AGENTS.md`) belong in step 1 above — they delete a false universal claim from always-injected
   text. Its action 6 (author profile on captured corrections) **gates** step 3, because
   correction-priority applied to the wrong person is worse than no capture. The remaining actions
   (map, matcher, consumers, recall filter) sit here.
6. **F8.2/F8.3** last: it is the only item whose value depends on the others having produced signal worth reporting.

## Confidence and honest limits

- **HIGH** and disk-verified this pass: every code-level finding (F1, F2.1–2, F3, F5, F6, F7, F10) — read from `ledger.py`, `modules.py`, `recall_index.py`, `reflect_utils.py`, `index-ai-sessions.py` directly, not inferred from documentation.
- **Inherited, not re-measured** (from 27–28.08 receipts, treated as evidence but flagged): 810/751/310/**439** graph numbers, 0 notes >100 KB, `.bmignore` contents, ~1,482 chunks from the catalog blob, the Stop-event 144s/35s oversubscription, reranker ON / gold-paraphrase MISS.
- **NOT-CHECKED, deliberately:** live resolution of `get_queue_path()` at `~` (F4.4 makes it a pre-flight, not an assumption); whether `~\.cursor\hooks.json`'s `sessionStart` `additional_context` actually delivers (already an owner-flag from 28.08 — the sidecar file is the reliable inject, so F8.3 should target the sidecar, not the racy field); current `learnings-queue.json` item count.
- **F9 person semantics: RESOLVED, owner-verified in-session 29.08.2026** (supersedes this lens's
  first pass, which rated it LOW and left it open). Andrei Visalon is a separate person, son of
  Marius Valentin Visalon; shared AI-tool estate; never aliases; no inheritance of Marius-specific
  facts or preferences. Provenance is `owner-stated` — authoritative for intent, but **not yet
  `disk-verified`**, because no artifact records it. F9 action 0 exists to close exactly that gap,
  and until it lands a fresh agent will re-derive the wrong model from the
  `social-corpus-extraction` fixture that maps `"Andrei Visalon"` to the owner key.
- **A single probe is not evidence.** The two absence claims this lens leans on hardest were each corroborated twice: `derived_from` has no production writer (grep across `.agents\harness` returned only test files, and the read of every `ledger.append` call site in `modules.py` found no such field); the digest path lacks poison/supersession guards (absent in `_slim_note`'s emitted keys *and* absent in `_filter_digest_notes`'s filter list *and* absent in the renderer).
- **Nothing here was installed, edited, enabled, or written outside this file.**

UNIT-COMPLETE: lens-09
