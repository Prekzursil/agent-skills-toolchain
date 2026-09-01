# Perplexity-Class Workflow Suite — Part 01: Content and Media

Date: 29.08.2026  
Status: DESIGN — implementation-ready documentation only; no code or commits  
Scope: `WF-01`, `WF-02`, `WF-03`, `WF-13`, `WF-14`, `WF-15`, `WF-16`, `WF-24`  
Shared foundation: `PERPLEXITY-WORKFLOWS-PART-00-SHARED_2026-08-29.md`

### WF-01 — Prompt refinement

**Source ref:** `user-spec:WF-01` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** prompt-content  
**Risk tier:** R0 (factors: none; runtime escalation follows `SH-RISK-1`) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/prompt-optimizer`  
· existing assets `skill:.agents/skills/prompt-optimizer`; `skill:.agents/skills/claude-prompt-forge` (long autonomous prompts); no MCP required  
· duplicate surfaces avoided `a second prompt-refinement skill`; `execution of the optimized prompt inside this advisory workflow`  
· delta `Add catalog alias and D9 prompt-injection/secret checks in launcher metadata only.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-01`; `.agents/skills-index.md`; `.agents/skills/prompt-optimizer/SKILL.md`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-01`

#### 1. Purpose and user story
- The owner supplies any AI prompt and receives a safer, clearer, testable prompt whose role, objective, context, constraints, output contract, examples, ambiguity handling, and failure behavior are explicit. The workflow diagnoses underspecification, asks only decision-changing clarifying questions, iterates against a prompt-quality rubric, and returns a concrete before/after package plus a reusable template.
- User story: "As an AI-tool user, I want an ambiguous or ineffective prompt refined without changing its real intent so that I can obtain more reliable, reviewable outputs."
- Boundary: this workflow does not execute the refined prompt, perform message copy-editing handled by `WF-03`, summarize documents handled by `WF-15`, or create social posts handled by `WF-14`.
- Routing: triggers `improve this prompt`, `rewrite my AI prompt`, `make this prompt clearer`, `analyze prompt ambiguity`, `turn this into a reusable prompt`; negative triggers `polish this email` → `WF-03`, `summarize this file` → `WF-15`, `write a social post` → `WF-14`; aliases `/prompt-refine`, `/prompt-optimize`.
- Execution modes: `interactive` for clarifying questions and `background` for a complete supplied specification; no `scheduled` mode because prompt intent is run-specific.
- Success criterion: the final prompt makes assumptions and failure semantics explicit, preserves protected text, includes a machine-checkable output contract, and traces each material edit to an identified defect rather than merely making the prose longer.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `prompt_text` | string | yes | 1–50,000 characters; NFC-normalized; control characters stripped | INTERNAL; may escalate from content | — |
| `target_model_or_surface` | string | no | 1–120 characters; descriptive identifier, not a secret | INTERNAL | `generic` |
| `intended_outcome` | string | no | 0–4,000 characters | INTERNAL | inferred, then confirmed if ambiguous |
| `audience` | string | no | 0–500 characters | INTERNAL | `model` |
| `protected_spans` | list<string> | no | at most 100 exact spans; each must occur in `prompt_text` | inherits source | `[]` |
| `examples` | list<string> | no | at most 20; 10,000 characters each | inherits source | `[]` |
| `custom_constraints` | list<string> | no | at most 50; no executable override semantics | INTERNAL | `[]` |
| `question_policy` | enum | no | `ask_if_material`, `always_ask`, `assume_and_label` | PUBLIC | `ask_if_material` |
| `output_language` | enum | no | `ro`, `en`, `preserve` | PUBLIC | `preserve` |

- Preconditions: `llm.extract`, `llm.rewrite`, and `llm.judge` have healthy adapters; optional internal-pattern files exist before `fs.read`; free-RAM admission follows `SH-ARCH-9`; no credential value is accepted as input.
- Intensity profile — numbers only; preset meanings remain those in §14.1:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 0 | 0 | 1 | 0 | 0 |
| medium | 0 | 3 | 3 | 3 | 1 | 1 |
| high | 0 | 3 | 3 | 5 | 2 | 2 |
| limitless | 0 | 3 | 3 | 5 | 2 | 3 |

- Budget: small `12 / 180 / 2`; medium `30 / 420 / 6`; high `70 / 900 / 14`; limitless `120 / 1,500 / 24` for `max_invocations / max_wall_clock_s / max_cost_units`.
- Deviations from shared input/intensity defaults: source counts are capped at three official prompt-guide families because additional generic guides do not improve a user-specific transform; `limitless` expands critique lenses, not source volume.

#### 3. Data sources and knowledge bases
- Primary external sources, used only when technique claims or target-surface behavior are stated: OpenAI's official Prompt Engineering guide (`platform.openai.com/docs/guides/prompt-engineering`) as `[PR1 §heading]`; Anthropic's official prompt-engineering documentation (`docs.anthropic.com/.../prompt-engineering/overview`) as `[PR2 §heading]`; Google's official Gemini prompting-strategies documentation (`ai.google.dev/gemini-api/docs/prompting-strategies`) as `[PR3 §heading]`. The owner's prompt and examples are cited as `[INPUT Lx–Ly]`; internal approved patterns as `[PATTERN:<id>@<hash>]`.
- `sources.min_tier: T1` for claims about prompting behavior, `min_independent: 1`, `recency_max_days: 90`; style changes that make no factual claim need no external citation under the prompt-content floor. Retrieved guide text follows `SH-SRC-1`–`SH-SRC-10`.
- No domain-data capability is required. `memory.search` is optional only for owner-approved, durable prompt preferences; it must not retrieve raw secrets or substitute old intent for the current input.
- Basic Memory: `memory.capture: decisions`; persist only stable preferences such as favored output structure or question policy, with owner-facing visibility. Never persist full prompts by default.
- Cache: `cache.policy: standard`; official guide pages are `slow`, while the current prompt and internal pattern hash are run-local and not shared-cache payloads.
- Paywall/institutional access: none expected. If an official guide becomes inaccessible, report it as unavailable; do not substitute community prompt folklore without labeling it.
- Deviations from the §8.2 domain floor: T1 official documentation is required for claims attributed to a model vendor, tighter than the no-floor rule for pure style.

#### 4. Tool chain and mechanisms
- Required capabilities: `llm.extract` identifies objective, role, variables, constraints, protected spans, ambiguities, contradictions, missing success criteria, and likely failure modes; `llm.rewrite` performs bounded refinement; `llm.judge` scores rubric dimensions and produces advisory defects; `fs.write` emits the declared artifacts.
- Optional capabilities: `fs.read` loads approved local prompt patterns and `memory.search` recalls stable owner preferences. If either is absent, the result remains complete but displays: `DEGRADED: internal prompt patterns/preferences were not consulted; refinement used only the supplied prompt and official technique rubric.`
- Provider hints are non-binding per `SH-ARCH-3`; use a schema-reliable reasoning model for extraction and a different independence group for medium-or-higher critique. No browser adapter is needed when official guide snapshots are already valid.
- Mechanism: parse the source prompt into a `PromptIntent`; detect ambiguity, conflicts, unsafe embedded instructions, accidental credential requests, and unverifiable assumptions; ask a bounded question set when answers alter the contract; generate a minimal rewrite and a reusable parameterized template; then run independent clarity, constraint, and adversarial-error lenses. The join accepts edits only when they preserve the intent and protected spans. Independence is recorded per `SH-CTX-2`.
- Reuse note: all refinement routes into `prompt-optimizer`; `claude-prompt-forge` is selected only for an explicitly long autonomous-prompt mode. This registry entry adds no prompt library, execution engine, or sibling skill.

#### 5. Internal data structures / schemas
- `PromptIntent`: `objective`, `role`, `audience`, `context`, `inputs`, `constraints`, `output_contract`, `examples`, `protected_spans`, `assumptions`.
- `PromptDefect`: `defect_id`, `category` (`ambiguity`, `conflict`, `missing_constraint`, `unsafe_instruction`, `secret_exposure`, `unverifiable_success`, `format_gap`), `source_locator`, `severity`, `evidence`, `proposed_resolution`, `requires_answer`.
- `PromptRefinement`: `original_hash`, `intent`, `questions`, `answers`, `refined_prompt`, `reusable_template`, `change_set`, `rubric_scores`, `unresolved`.
- Shared schemas consumed unchanged: `RunContext`, `ToolInvocation`, `SourceRecord`, `Citation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, and `ReviewVerdict`.
- No shared-schema extension is required. Declared artifacts: `prompt_refinement` (`markdown`, required) contains before/after, rationale, assumptions, and reusable template; `prompt_refinement_json` (`json`, required) contains the typed structure.
- Schema example:
```json
{"original_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111","intent":{"objective":"Produce a cited comparison","role":"research analyst","audience":"owner","context":[],"inputs":["topic"],"constraints":["Do not invent sources"],"output_contract":{"format":"markdown"},"examples":[],"protected_spans":["Do not invent sources"],"assumptions":[]},"questions":[],"answers":[],"refined_prompt":"You are a research analyst...","reusable_template":"Compare {{topic}}...","change_set":[{"defect_id":"D1","change":"Added citation acceptance criterion"}],"rubric_scores":{"clarity":5,"specificity":5,"testability":5},"unresolved":[]}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; the nodes and one bounded clarification branch are known at authoring time.
- Lifecycle phases used: `discover`, `execute`, `quality-review`, `capture`.
1. `ingest_prompt` (`discover`, `tool`, `llm.extract`) → normalizes intent, variables, protected spans, and hazards → emits `PromptIntent`.
2. `analyze_defects` (`discover`, `llm`, prompt pattern) → performs ambiguity/error analysis against the rubric → emits `PromptDefect[]`.
3. `clarification_gate` (`discover`, `gate`, none) → asks only material questions or records labeled assumptions according to `question_policy` → emits `answers`.
4. `draft_refinement` (`execute`, `tool`, `llm.rewrite`) → adds role, constraints, examples, error handling, and output contract while preserving intent → emits `PromptRefinement`.
5. `critique_lanes` (`quality-review`, `fanout`, none) → at medium or above runs clarity, instruction-conflict, and misuse/secret lenses → emits three independent rubric reports.
6. `reconcile_revision` (`quality-review`, `join`, none) → applies supported changes and preserves unresolved disagreements → emits final `PromptRefinement`.
7. `validate_prompt` (`quality-review`, `gate`, none) → checks schema, protected spans, no secret values, no execution, and before/after traceability → emits `ValidationResult[]`.
8. `export_refinement` (`capture`, `export`, `fs.write`) → writes markdown and JSON, hashes, re-reads, and manifests them → emits `ArtifactManifest`.
- Branches: `clarification_gate` enters `AWAITING_INPUT` only when an unanswered defect is material; otherwise assumptions are labeled. Critique fan-out joins once; loops are bounded by the selected profile.
- Checkpoints occur after clarification, first draft, reconciliation, and export; artifact-emitting nodes are `draft_refinement` and `export_refinement`.
- Approval: gates `deterministic`; `human_required: 0`; `panel_required: false` at base R0. Protected-span mismatch, detected secret value, or any attempt to execute the refined prompt blocks.
- Resume: reuse schema-valid deterministic input normalization and disk-verified artifacts; re-run nondeterministic rewrite/critique only from the first invalid or changed-input node per `SH-RUN-7` and `SH-RUN-11`.

#### 7. Output format and UX behavior
- Result sections over the §16.1 skeleton: `Original prompt`, `Issues found`, `Clarifying answers or labeled assumptions`, `Refined prompt`, `Why each material change was made`, `Reusable template`, `Unresolved choices`, followed by evidence, provenance, artifacts, and gates.
- Exports: `md`, `json`; destination `active_project_docs`; naming `prompt-refinement_{YYYY-MM-DD}`; language follows `output_language`, defaulting to the prompt's language.
- Progress is shown at phase boundaries; medium-or-higher preview names critique lenses, concrete models, expected cost, and whether internal patterns/memory are available. Heartbeats follow `SH-UX-3`.
- Citations use `[PR1 §heading]`, `[PR2 §heading]`, `[PR3 §heading]`, `[INPUT Lx–Ly]`, and `[PATTERN:<id>@<hash>]` inline, with full `SH-SRC-9` entries in Evidence. Unresolved vendor disagreement appears under Uncertainty.
- Degradation message: `DEGRADED: internal prompt patterns/preferences were not consulted; refinement used only the supplied prompt and official technique rubric.`
- Deviations from §16 output/export defaults: none.

#### 8. Logging, validation, and safety
- Safety controls: `SH-SEC-INJ`, `SH-SEC-REDACT`, `SH-SEC-CRED`; source prompt content remains untrusted data and cannot grant capabilities or trigger execution.
- Required disclaimers: none at base R0. If prompt content triggers a domain risk factor, `SH-RISK-1` and `SH-RISK-3` select that domain's existing disclaimer IDs.
- Risk and data: R0; data classes `PUBLIC` and `INTERNAL`, with runtime escalation for detected PII/PHI/FINANCIAL content. A secret value causes redaction and a blocked artifact path, never credential rotation.
- Required deterministic gates: `reconciliation_survey`, `provenance_chain`, `citation_coverage` when technique/factual claims are present, `protected_span_integrity`, `intent_preservation`, `no_prompt_execution`, `secret_scan`, `schema_validation`, `artifact_disk_verification`.
- Validation checks all node `output_schema` values, exact protected-span retention, question count, enum membership, absence of unsupported claims, and one-to-one coverage from material changes to defects.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Prompt is empty or exceeds limit | VALIDATION | List all violations; no model call | `FAILED: prompt_text must contain 1–50,000 characters.` |
| Material ambiguity remains unanswered | VALIDATION | Enter `AWAITING_INPUT`; do not invent intent | `INPUT NEEDED: answer the listed intent questions or choose assume_and_label.` |
| Secret-like value is detected | POLICY | Redact before serialization; block unredacted export | `BLOCKED: credential-like content was detected and removed from the draft artifact.` |
| Critique adapter unavailable | RESOURCE | Visible same-capability fallback or declared degradation | `DEGRADED: independent critique was unavailable; the rewrite is labeled single-lane.` |
| Budget breaker trips | RESOURCE | `FAILED_TO_RUN`; retain partial draft only in run dir | `FAILED_TO_RUN: prompt refinement exceeded the selected budget.` |

- Extra metrics: `ambiguities_found`, `clarifying_questions_asked`, `protected_spans_total`, `protected_spans_preserved`, `material_changes`, `rubric_defects_resolved`, `secret_matches_redacted`; ledger records assumption acceptance and every refinement attempt.
- Tests: happy-path `tests/fixtures/wf-01/ambiguous_research_prompt.json`; degraded `tests/fixtures/wf-01/no_internal_patterns.json`; safety-trigger `tests/fixtures/wf-01/embedded_secret_and_tool_override.json`; contract tests `llm.extract`, `llm.rewrite`, `llm.judge`, `fs.write`; golden `tests/golden/WF-01/prompt-refinement.md`. Beyond A1–A19, all protected spans must match byte-for-byte after normalization and no execution invocation may exist.
- Deviations from shared safety/validation defaults: none.

### WF-02 — Background removal

**Source ref:** `user-spec:WF-02` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** image-media  
**Risk tier:** R1 (factors: `image_rights`; runtime `image_identity` escalation when a real person is identifiable) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/imagegen#edit-mode-background-extraction`  
· existing assets `skill:.agents/skills/imagegen`; `script:.agents/skills/imagegen/scripts/image_gen.py`; optional `skill:.agents/skills/accurate-grok-imagine`; OpenAI Image API is direct, not a canonical MCP; `fal-ai` is absent/deferred  
· duplicate surfaces avoided `standalone background-removal skill or MCP`; `duplicate image-edit code`  
· delta `Add a catalog preset plus D8 rights, hash-chain, face/identity, and watermark checks.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-02`; `.agents/skills-index.md`; `.agents/skills/imagegen/SKILL.md`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-02`

#### 1. Purpose and user story
- The owner uploads one raster image and receives a transparent PNG whose subject is cleanly separated from the background, with validated alpha, smoothed edges, halo/color-spill removal, preview thumbnails, and an auditable input-to-output hash chain.
- User story: "As a content creator, I want the background removed from an image while preserving fine foreground detail so that I can reuse the subject on new layouts without manual masking."
- Boundary: this workflow does not generate new product-photo scenes handled by `WF-13`, create thumbnail compositions handled by `WF-24`, alter a person's identity, remove watermarks, or claim ownership of an uploaded asset.
- Routing: triggers `remove this background`, `make this image transparent`, `cut out the subject`, `export subject as PNG`, `clean the edges`; negative triggers `create product photo variants` → `WF-13`, `make a video thumbnail` → `WF-24`, `generate a headshot` → `WF-28`; aliases `/remove-background`, `/background-extraction`.
- Execution modes: `interactive` and `background`; `owner-present-only` is added at runtime for identity-sensitive or disputed-rights inputs.
- Success criterion: foreground geometry and fine structures remain intact, transparent regions are truly alpha-transparent, edge halos are below the declared threshold, and the owner can inspect both full-resolution output and alpha/matte QA thumbnails.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `source_image` | image | yes | PNG/JPEG/WebP; ≤50 MB; ≤80 MP; decode-bomb guard | INTERNAL; PII/P6 if identifiable person |
| `subject_hint` | string | no | 0–500 characters; descriptive only | INTERNAL | auto-detect |
| `edge_mode` | enum | no | `natural`, `hard`, `hair_fur`, `product` | PUBLIC | `natural` |
| `smoothing_px` | integer | no | 0–8 | PUBLIC | 1 |
| `decontaminate_edges` | bool | no | remove background color spill without changing interior colors | PUBLIC | true |
| `retain_shadow` | bool | no | only naturally connected soft shadow | PUBLIC | false |
| `output_size` | enum | no | `original`, `fit_2048`, `fit_4096` | PUBLIC | `original` |
| `rights_attestation` | enum | yes | `owner_created`, `licensed`, `authorized_edit` | INTERNAL | — |

- Preconditions: source path exists; content-sniffed MIME and decode succeed; `image.analyze`, `image.edit`, `image.transform`, `fs.read`, and `fs.write` are healthy; rights attestation is present; identity check resolves before remote egress.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 0 | 0 | 0 | 0 | 0 |
| medium | 0 | 0 | 0 | 1 | 0 | 1 |
| high | 0 | 0 | 0 | 3 | 0 | 2 |
| limitless | 0 | 0 | 0 | 3 | 0 | 3 |

- Budget: small `10 / 180 / 2`; medium `24 / 420 / 6`; high `60 / 900 / 18`; limitless `100 / 1,500 / 30`.
- Deviations from shared input/intensity defaults: this is tool-only, so external queries/sources/corroboration remain zero. Additional voices compare masks; they are not evidence sources.

#### 3. Data sources and knowledge bases
- No external sources are used to determine image content. The owner-supplied image is the sole run source and is cited by asset hash as `[IMG1 sha256:<prefix>]`; rights are recorded from `rights_attestation` or a supplied license as `[LIC1 <file>@<hash>]`.
- Algorithm documentation is implementation reference only, never evidence about the uploaded subject: U²-Net paper/repository as `[ALG-BR-1 §component]`, MODNet paper/repository as `[ALG-BR-2 §component]`, and the PNG specification as `[ALG-BR-3 §section]`.
- `sources.min_tier: T0` for any rendered rights/licensing claim, `min_independent: 2` for a contested rights claim, `recency_max_days: null`; otherwise no factual-source gate is applicable.
- No domain-data or Basic Memory capability is used; `memory.capture: none` prevents retention of image content or biometric information.
- Cache: `cache.policy: fresh-only` for source pixels, masks, and identity-sensitive imagery. Deterministic transforms may be memoized only within the run by input hash.
- Paywall/institutional access: not applicable.
- Deviations from the §8.2 domain floor: none; rights claims keep the image-media T0/two-source rule.

#### 4. Tool chain and mechanisms
- Required capabilities: `fs.read` ingests and hashes the image; `image.analyze` identifies foreground candidates, faces, watermarks, alpha state, and complexity; `image.edit` runs the existing `BackgroundRemoval` mode; `image.transform` validates/repairs alpha, sizes thumbnails, composites matte previews, and strips unsafe metadata; `fs.write` emits artifacts.
- Optional capability: a local U²-Net or MODNet adapter behind `image.edit`. If absent, the selected healthy `image.edit` adapter is used and the UI states: `DEGRADED: specialized local matting adapter unavailable; inspect hair/fur and translucent-edge QA before use.`
- Provider hints: prefer deterministic/local segmentation when it meets mask quality; use existing `imagegen` edit mode for difficult semantic separation. Never route to a text-to-image capability because that would regenerate rather than preserve the source.
- Mechanism: produce an initial foreground probability map; derive foreground/background confidence and an uncertainty band; refine uncertain boundaries; preserve high-confidence interior pixels; smooth only the alpha edge; decontaminate fringe color using neighboring foreground colors; optionally retain connected shadows; then compare transparent output against white, black, and checkerboard mattes.
- Reuse note: `imagegen` owns image editing and `scripts/image_gen.py` remains the implementation path. This workflow contributes preset configuration and QA contracts only.

#### 5. Internal data structures / schemas
- `BackgroundRemovalRequest`: `source_hash`, `dimensions`, `subject_hint`, `edge_mode`, `smoothing_px`, `retain_shadow`, `rights_attestation`.
- `SegmentationMask`: `width`, `height`, `alpha_path`, `foreground_confidence_mean`, `background_confidence_mean`, `uncertain_pixel_ratio`, `edge_band_px`, `component_count`.
- `AlphaQAReport`: `alpha_present`, `opaque_pixel_ratio`, `transparent_pixel_ratio`, `partial_alpha_ratio`, `halo_score`, `edge_continuity_score`, `subject_bbox`, `watermark_detected`, `identity_detected`, `pass`.
- Shared schemas consumed unchanged: `RunContext`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, and `ReviewVerdict`.
- No shared-schema extension is required. Artifacts: `transparent_png` (`png`, required); `alpha_mask` (`png`, required); `qa_contact_sheet` (`png`, required); `background_removal_report` (`json`, required).
- Schema example:
```json
{"alpha_present":true,"opaque_pixel_ratio":0.42,"transparent_pixel_ratio":0.51,"partial_alpha_ratio":0.07,"halo_score":0.018,"edge_continuity_score":0.97,"subject_bbox":[114,62,1830,1976],"watermark_detected":false,"identity_detected":false,"pass":true}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; segmentation, refinement, validation, and export form a static bounded pipeline.
- Lifecycle phases used: `discover`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `ingest_image` (`discover`, `tool`, `fs.read`) → copies, hashes, MIME-sniffs, and decodes the source → emits `BackgroundRemovalRequest`.
2. `analyze_image` (`discover`, `tool`, `image.analyze`) → locates subjects, faces, watermarks, existing alpha, and likely fine-detail regions → emits analysis.
3. `rights_identity_gate` (`discover`, `gate`, none) → verifies attestation and applies D8 runtime escalation → emits `SafetyDecision`.
4. `segment_foreground` (`execute`, `tool`, `image.edit`) → runs `BackgroundRemoval` and produces probability/alpha data → emits `SegmentationMask`.
5. `refine_edges` (`execute`, `tool`, `image.transform`) → smooths uncertainty-band edges, removes halo/color spill, and preserves interior pixels → emits transparent PNG and alpha mask.
6. `render_qa` (`quality-review`, `tool`, `image.transform`) → renders checkerboard, white, black, and alpha thumbnails → emits contact sheet.
7. `validate_alpha` (`quality-review`, `gate`, none) → checks PNG alpha, dimensions, connected subject, confidence, halo, and watermark rules → emits `AlphaQAReport`.
8. `owner_acceptance` (`acceptance`, `gate`, none) → presents variants when QA is borderline and records the selected mask → emits acceptance record.
9. `export_assets` (`capture`, `export`, `fs.write`) → writes, re-reads, hashes, and manifests all outputs → emits `ArtifactManifest`.
- Branches: pre-existing good alpha skips segmentation and runs validation; a borderline halo/continuity score may loop from `validate_alpha` to `refine_edges` up to the preset bound; watermark-removal requests terminate with `DENY`.
- Checkpoints follow ingest, initial mask, edge refinement, QA render, and export; every image artifact is hashed before downstream use.
- Approval: `deterministic` and `human`; `human_required: 1`; `panel_required: false`. Owner acceptance is required for borderline edges and any identifiable-person image; unconfirmed real-person purpose escalates per `image_identity`.
- Resume: reuse copied source and deterministic transforms when hashes match; re-run nondeterministic segmentation only if its artifact is absent, invalid, or rejected.

#### 7. Output format and UX behavior
- The owner sees the transparent PNG first, then original/transparent/matte thumbnails, alpha mask, QA metrics, rights/provenance status, artifacts, and gates.
- Exports: `png`, `json`; destination `output`; naming `background-removed_{YYYY-MM-DD}` with sibling `-mask` and `-qa`; language `en` for the technical report.
- Progress shows `analyzing`, `segmenting`, `refining edges`, `validating alpha`, and `exporting`; operations over 60 seconds emit heartbeats. Preview shows adapter, locality, estimated variants, identity/rights status, and cost.
- Citations are asset references `[IMG1 sha256:<prefix>]`, `[LIC1 <file>@<hash>]`, and implementation-only `[ALG-BR-n §section]`. Uncertainty is visualized as the uncertain alpha band and quantified in the report.
- Degradation message: `DEGRADED: specialized local matting adapter unavailable; inspect hair/fur and translucent-edge QA before use.`
- Deviations from §16 output/export defaults: image exports use a concise technical JSON sidecar in addition to the shared manifest.

#### 8. Logging, validation, and safety
- Safety controls: `SH-SEC-INJ`, `SH-SEC-REDACT`, `SH-SEC-CRED`, `SH-SEC-IDENTITY`; EXIF/XMP/SVG text is untrusted and never executed.
- Required disclaimers: none at base R1; any runtime-escalated domain disclaimer is resolved only from the registered IDs under `SH-RISK-3`. Identity-like edits carry a provenance/disclosure label, not an invented disclaimer ID.
- Risk/data: base R1 with `image_rights`; `image_identity` raises an identifiable-person run to R2. Data classes `INTERNAL`, `PII`, and identity images treated under the D8 P6 boundary.
- Deterministic gates: `reconciliation_survey`, `provenance_chain`, `rights_attestation`, `watermark_nonremoval`, `alpha_channel_valid`, `dimension_preservation`, `foreground_retention`, `halo_threshold`, `artifact_disk_verification`; `citation_coverage` is `SKIPPED_NOT_APPLICABLE` unless a rights claim is rendered.
- Validation checks schemas, decodability, PNG signature, exact output dimensions or declared resize, nonempty subject bounds, alpha distribution, connected components, confidence ranges `[0,1]`, and no source overwrite.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Unsupported/corrupt image | VALIDATION | Reject before image call | `FAILED: source image could not be safely decoded.` |
| No separable subject | VALIDATION | Preserve diagnostics; request subject hint | `INPUT NEEDED: no stable foreground was detected; mark or describe the subject.` |
| Watermark removal requested/detected | POLICY | Deny the edit | `BLOCKED: this workflow does not remove ownership watermarks.` |
| Specialized matting adapter absent | RESOURCE | Use declared image-edit path with visible degradation | `DEGRADED: specialized local matting adapter unavailable; inspect fine edges.` |
| Alpha or halo QA fails after bound | VALIDATION | Block export; retain partial artifact in run dir | `BLOCKED: alpha QA failed; no final PNG was exported.` |

- Extra metrics: `input_pixels`, `uncertain_pixel_ratio`, `halo_score`, `edge_continuity_score`, `mask_attempts`, `foreground_confidence_mean`, `background_confidence_mean`; ledger records rights/identity decisions and mask selection.
- Tests: happy-path `tests/fixtures/wf-02/product_simple.png`; degraded `tests/fixtures/wf-02/hair_no_specialized_adapter.png`; safety-trigger `tests/fixtures/wf-02/watermarked_identity.jpg`; contracts `fs.read`, `image.analyze`, `image.edit`, `image.transform`, `fs.write`; golden `tests/golden/WF-02/qa-report.json`. Beyond A1–A19, alpha matte must pass against white/black/checkerboard and source interior-color drift must stay within the declared tolerance.
- Deviations from shared safety/validation defaults: none.

### WF-03 — Message polish

**Source ref:** `user-spec:WF-03` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** prompt-content  
**Risk tier:** R0 (factors: none; outward use remains owner-controlled) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `MERGE_ALIAS` (matrix label `MERGE/ALIAS`) · canonical owner `skill:.agents/skills/humanizer`  
· existing assets `skill:.agents/skills/humanizer`; `skill:.agents/skills/agentic-humanizer` only for explicit five-pass/voice mode; no MCP required; optional Slop-or-Not surface is absent from the canonical registry  
· duplicate surfaces avoided `a third polish/rewriter skill`; `treating draft generation as permission to send`  
· delta `Alias “message polish” to light editing; escalate to agentic-humanizer only by explicit mode; never send.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-03`; `.agents/skills-index.md`; `.agents/skills/humanizer/SKILL.md`; `.agents/skills/agentic-humanizer/SKILL.md`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-03`

#### 1. Purpose and user story
- The owner supplies a draft plus tone, formality, audience, length, and custom constraints and receives a polished message that is clearer and more natural while preserving legal/technical meaning, factual commitments, numbers, citations, and protected spans.
- User story: "As a professional communicator, I want a draft adapted to its audience and channel so that it reads naturally without changing what I am asserting or authorizing."
- Boundary: this workflow does not send or post the message, create a social campaign handled by `WF-14`, refine an instruction prompt handled by `WF-01`, or provide legal/factual clearance.
- Routing: triggers `polish this message`, `make this email more formal`, `rewrite for this audience`, `shorten without changing meaning`, `improve the tone`; negative triggers `improve this AI prompt` → `WF-01`, `create social posts` → `WF-14`, `final QA this document` → `WF-20`; aliases `/message-polish`, `/humanize`.
- Execution modes: `interactive` and `background`; five-pass `agentic-humanizer` mode must be selected explicitly. Sending is never an execution mode.
- Success criterion: every changed proposition is traceable, protected spans are exact, legal/technical modality and quantities are preserved, the target length is met, and the owner sees a diff rather than receiving an unexplained rewrite.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `draft` | string | yes | 1–100,000 characters | INTERNAL; may become PII/PHI/FINANCIAL |
| `tone` | enum | no | `neutral`, `warm`, `direct`, `diplomatic`, `persuasive`, `technical` | PUBLIC | `neutral` |
| `formality` | enum | no | `casual`, `standard`, `formal`, `official` | PUBLIC | `standard` |
| `audience` | string | no | 0–500 characters | INTERNAL | `general` |
| `length_target` | string | no | `preserve`, percentage `30–150`, or max words `1–5000` | PUBLIC | `preserve` |
| `channel` | enum | no | `email`, `chat`, `memo`, `letter`, `announcement`, `other` | PUBLIC | `email` |
| `protected_spans` | list<string> | no | ≤200 exact spans present in source | inherits source | `[]` |
| `custom_constraints` | list<string> | no | ≤50; contradictions are surfaced | INTERNAL | `[]` |
| `rewrite_mode` | enum | no | `light`, `standard`, `five_pass` | PUBLIC | `standard` |
| `output_language` | enum | no | `ro`, `en`, `preserve` | PUBLIC | `preserve` |

- Preconditions: healthy `llm.extract`, `llm.rewrite`, `llm.judge`, and `fs.write`; brand/style guide paths, if supplied through approved context, exist and are readable; no send capability is granted.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 1 | 1 | 1 | 0 | 0 |
| medium | 0 | 3 | 3 | 3 | 1 | 1 |
| high | 0 | 4 | 4 | 5 | 2 | 2 |
| limitless | 0 | 4 | 4 | 5 | 2 | 3 |

- Budget: small `10 / 180 / 2`; medium `28 / 420 / 6`; high `60 / 900 / 14`; limitless `100 / 1,500 / 24`.
- Deviations from shared input/intensity defaults: sources are style authorities, not factual corroboration; `five_pass` is opt-in regardless of intensity.

#### 3. Data sources and knowledge bases
- Primary authorities: an owner-supplied brand/style guide, cited `[BRAND §heading@<hash>]`; Microsoft Writing Style Guide, cited `[STYLE1 §heading]`; Google developer documentation style guide for technical prose, cited `[STYLE2 §heading]`; the source draft, cited `[DRAFT Lx–Ly]`. If legal/technical source attachments govern wording, cite exact spans as `[SRC1 p.<n> ¶<n>]`.
- `sources.min_tier: T2` for any factual style assertion, `min_independent: 1`, `recency_max_days: 365`; the owner brand guide is authoritative for that brand until its hash changes. Pure rewriting needs no external factual citation.
- No domain-data capability is required. `memory.search` may retrieve an approved brand voice or stable owner preference; it may not supply facts absent from the draft.
- Basic Memory: `memory.capture: decisions`; persist only explicitly approved voice preferences, never message bodies, recipients, or sensitive facts.
- Cache: `cache.policy: standard`; official style guides are `slow`, owner guides invalidate on hash change, and message bodies remain run-local.
- Paywall/institutional access: none.
- Deviations from §8.2: none.

#### 4. Tool chain and mechanisms
- Required capabilities: `llm.extract` creates a proposition/constraint ledger; `llm.rewrite` performs the multi-pass `TextRewrite`; `llm.judge` compares semantic equivalence, tone, audience fit, and constraint compliance; `fs.write` exports.
- Optional capabilities: `fs.read` for brand/style guides and `memory.search` for approved voice preferences. Missing guides produce: `DEGRADED: no brand/style guide was available; the rewrite uses only the selected tone, formality, audience, and constraints.`
- Provider hints: use a schema-reliable extraction lane, a rewrite lane, and at medium+ an independent semantic-preservation lane. No `browser.act` or messaging/posting adapter may be attached.
- Mechanism: pass 1 extracts propositions, modality, obligations, dates, figures, defined terms, protected spans, and audience; pass 2 corrects structure and clarity; pass 3 adjusts tone/formality; pass 4 enforces length/channel; pass 5, only in explicit mode, removes generic AI phrasing and performs independent semantic-drift review. A token/segment diff and rationale are generated from the accepted version.
- Reuse note: light/standard routes to `humanizer`; only explicit `five_pass` routes to `agentic-humanizer`. The workflow never creates a third rewriter or a send surface.

#### 5. Internal data structures / schemas
- `MessageConstraintSet`: `tone`, `formality`, `audience`, `channel`, `length_target`, `custom_constraints`, `protected_spans`.
- `MeaningLedger`: `propositions`, each with `id`, `source_span`, `kind`, `modality`, `entities`, `numbers`, `dates`, `defined_terms`, `must_preserve`.
- `TextRewriteResult`: `source_hash`, `polished_text`, `passes`, `diff_hunks`, `rationales`, `meaning_checks`, `constraint_checks`, `unresolved`.
- Shared schemas consumed unchanged: `RunContext`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, and `ReviewVerdict`.
- No shared-schema extension. Artifacts: `polished_message` (`markdown`, required); `message_diff` (`markdown`, required); `rewrite_report` (`json`, required).
- Schema example:
```json
{"source_hash":"sha256:2222222222222222222222222222222222222222222222222222222222222222","polished_text":"Please submit the signed report by 17:00 on 30.08.2026.","passes":["structure","tone","length"],"diff_hunks":[{"before":"Send report tomorrow.","after":"Please submit the signed report by 17:00 on 30.08.2026.","rationale":"Applied owner-supplied deadline and formal tone."}],"meaning_checks":{"protected_spans":true,"numbers":true,"modality":true},"constraint_checks":{"length":true,"tone":true},"unresolved":[]}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; passes and a single repair loop are statically bounded.
- Lifecycle phases used: `discover`, `execute`, `quality-review`, `capture`.
1. `ingest_draft` (`discover`, `tool`, `llm.extract`) → identifies content class, audience signals, constraints, and protected spans → emits `MessageConstraintSet`.
2. `extract_meaning` (`discover`, `tool`, `llm.extract`) → builds proposition, modality, numbers, dates, defined terms, and commitment ledger → emits `MeaningLedger`.
3. `resolve_conflicts` (`discover`, `gate`, none) → asks when tone/length/custom constraints conflict with protected meaning → emits resolved constraints.
4. `rewrite_structure` (`execute`, `tool`, `llm.rewrite`) → improves organization and clarity → emits draft pass 1.
5. `rewrite_voice` (`execute`, `tool`, `llm.rewrite`) → applies tone, formality, channel, audience, and brand guidance → emits draft pass 2.
6. `enforce_length` (`execute`, `tool`, `llm.rewrite`) → meets length without deleting must-preserve propositions → emits candidate.
7. `meaning_review` (`quality-review`, `tool`, `llm.judge`) → independently compares source and candidate → emits semantic-drift findings.
8. `repair_and_diff` (`quality-review`, `join`, none) → repairs one bounded round and creates diff/rationale → emits `TextRewriteResult`.
9. `validate_rewrite` (`quality-review`, `gate`, none) → checks protected spans, numbers, dates, modality, length, and no-send boundary → emits validations.
10. `export_message` (`capture`, `export`, `fs.write`) → writes, hashes, re-reads, and manifests artifacts → emits `ArtifactManifest`.
- Branches: conflict enters `AWAITING_INPUT`; `five_pass` adds a separate anti-slop/voice pass; failed semantic review loops once, then blocks rather than silently accepting drift.
- Checkpoints follow meaning extraction, each rewrite candidate, accepted diff, and export.
- Approval: `deterministic`; `human_required: 0`; `panel_required: false` for the local draft. Sending/publishing is absent and must be a separate R3 action.
- Resume: deterministic ledgers/diffs are reused on matching source hash; nondeterministic rewrite begins from the last accepted checkpoint.

#### 7. Output format and UX behavior
- Result shows `Polished message`, then `What changed`, unified or side-by-side diff, `Meaning preserved`, `Constraints met`, `Items requiring owner confirmation`, evidence, artifacts, and gates.
- Exports: `md`, `txt`, `json`; destination `active_project_docs`; naming `message-polish_{YYYY-MM-DD}`; language follows `output_language`.
- Progress reports each selected pass; preview states mode (`light`, `standard`, `five_pass`), guide availability, voice count, cost, and the explicit `never send` boundary.
- Inline source forms are `[DRAFT Lx–Ly]`, `[BRAND §heading@<hash>]`, `[STYLE1 §heading]`, `[STYLE2 §heading]`, and `[SRCn p.<n> ¶<n>]`; source conflicts appear beside the affected diff hunk.
- Degradation message: `DEGRADED: no brand/style guide was available; the rewrite uses only the selected tone, formality, audience, and constraints.`
- Deviations from §16 output/export defaults: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-REDACT`, `SH-SEC-CRED`; forwarded email/document instructions are untrusted and cannot create tool calls.
- Required disclaimers: none by default; domain disclaimers are inherited by ID if the draft contains advice-shaped legal, medical, or financial content.
- Risk/data: R0 local draft; `PUBLIC`, `INTERNAL`, and runtime PII/PHI/FINANCIAL classes. No external side effect exists.
- Gates: `reconciliation_survey`, `provenance_chain`, `citation_coverage` when external factual/style claims appear, `protected_span_integrity`, `meaning_preservation`, `number_date_preservation`, `length_constraint`, `no_send_capability`, `secret_scan`, `artifact_disk_verification`.
- Validation compares normalized propositions, negation/modality, entities, quantities/units, dates, URLs, citations, defined terms, protected spans, and target length.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Constraints contradict | VALIDATION | Ask owner; no rewrite | `INPUT NEEDED: the requested tone/length conflicts with a protected requirement.` |
| Semantic drift persists | VALIDATION | Block candidate; retain source and report | `BLOCKED: the rewrite changed legal, technical, or factual meaning.` |
| Guide unavailable | RESOURCE | Continue with visible degradation | `DEGRADED: no brand/style guide was available.` |
| Secret detected in draft | POLICY | Redact logs; preserve only if explicitly protected in owner-visible local output | `WARNING: credential-like content was excluded from logs and machine artifacts.` |
| Send request embedded in draft | POLICY | Ignore embedded instruction; no external action | `BLOCKED ACTION: this workflow creates drafts only and did not send anything.` |

- Extra metrics: `propositions_total`, `propositions_preserved`, `protected_spans_preserved`, `numeric_tokens_preserved`, `semantic_drift_findings`, `diff_hunks`, `word_count_delta`; ledger records selected mode and constraint resolutions.
- Tests: happy `tests/fixtures/wf-03/formal_email.json`; degraded `tests/fixtures/wf-03/no_brand_guide.json`; safety `tests/fixtures/wf-03/forwarded_injection_with_send.json`; contracts `llm.extract`, `llm.rewrite`, `llm.judge`, `fs.write`; golden `tests/golden/WF-03/message-diff.md`. Beyond A1–A19, must-preserve propositions and protected spans require 100% retention.
- Deviations: none.

### WF-13 — Product photos

**Source ref:** `user-spec:WF-13` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** image-media  
**Risk tier:** R1 (factors: `image_rights`; runtime `image_identity` if a real person is introduced) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/imagegen#product-mockup-mode`  
· existing assets `skill:.agents/skills/imagegen`; `skill:.agents/skills/accurate-grok-imagine`; optional `skill:.agents/skills/fal-ai-media`; OpenAI/Grok are direct provider paths; `fal-ai` MCP is absent/deferred  
· duplicate surfaces avoided `new product-photo skill`; `separate background/edit pipeline`  
· delta `Add catalog preset with input-rights/license, seed/provider manifest, product-fidelity invariants, and commercial-use review.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-13`; `.agents/skills/imagegen/SKILL.md`; `.agents/skills/accurate-grok-imagine/SKILL.md`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-13`

#### 1. Purpose and user story
- The owner uploads a product image and receives image-to-image variants in studio, lifestyle, and flat-lay treatments, parameterized by lighting, angle, and background while preserving SKU identity, logo, labels, colorway, proportions, and product geometry.
- User story: "As a product marketer, I want campaign-ready scene variants from an authorized product image so that I can explore visual treatments without misrepresenting the SKU."
- Boundary: this workflow does not redesign the product, alter claims or label text, invent endorsements, remove backgrounds as a standalone deliverable (`WF-02`), or create video thumbnails (`WF-24`).
- Routing: triggers `create product photo variants`, `put this product in a studio scene`, `make lifestyle product shots`, `generate flat-lay versions`, `change product lighting/background`; negative triggers `only remove background` → `WF-02`, `make thumbnail` → `WF-24`, `brand inspiration deck` → `WF-11`; aliases `/product-photos`, `/product-mockup`.
- Execution modes: `interactive` and `background`; owner acceptance is required before any variant is labeled approved for commercial use.
- Success criterion: variants look intentionally art-directed but retain measurable product identity, exact visible logos/labels where feasible, declared limitations for generated text, and complete seed/provider/source provenance.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `product_image` | image | yes | PNG/JPEG/WebP; ≤50 MB; ≤80 MP | INTERNAL |
| `sku_id` | string | yes | 1–120 characters; stable owner identifier | INTERNAL |
| `scene_types` | list<enum> | no | subset `studio`, `lifestyle`, `flat_lay`; 1–3 | PUBLIC | all three |
| `lighting` | list<enum> | no | `softbox`, `high_key`, `low_key`, `daylight`, `warm`, `custom` | PUBLIC | `softbox` |
| `angles` | list<enum> | no | `front`, `three_quarter`, `side`, `top_down`, `custom`; ≤6 | PUBLIC | source-compatible |
| `background_prompt` | string | no | ≤1,000 characters; no unauthorized brand imitation | INTERNAL | scene default |
| `variants_per_scene` | integer | no | 1–8 | PUBLIC | 3 |
| `identity_anchors` | list<string> | no | logo, label, shape, color, dimensions; ≤30 | INTERNAL | auto-extracted |
| `rights_attestation` | enum | yes | `owner_created`, `licensed`, `authorized_commercial_edit` | INTERNAL | — |
| `commercial_use_review` | bool | no | cannot be auto-confirmed | PUBLIC | true |

- Preconditions: source decodes and hashes; rights attestation present; `image.analyze`, `image.edit`, `image.generate`, `image.transform`, `fs.read`, `fs.write` healthy; commercial provider terms available for review.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 0 | 0 | 1 | 0 | 0 |
| medium | 0 | 0 | 0 | 3 | 0 | 1 |
| high | 0 | 0 | 0 | 5 | 0 | 2 |
| limitless | 0 | 0 | 0 | 5 | 0 | 3 |

- Budget: small `18 / 420 / 8`; medium `60 / 1,200 / 28`; high `160 / 2,700 / 75`; limitless `260 / 4,500 / 120`.
- Deviations: source and full-text counts remain zero because this is a tool-only generative transform; variant count and fidelity-review lenses provide breadth.

#### 3. Data sources and knowledge bases
- No external factual sources are used to define the product. The owner image and SKU metadata are the primary source, cited `[SKU1 sha256:<prefix>]`; a license is `[LIC1 <document>@<hash>]`; optional owner brand guide is `[BRAND §heading@<hash>]`.
- Algorithm/provider documentation is implementation reference only: selected image-to-image adapter documentation `[ALG-PP-1 §feature]`, deterministic color/geometry comparison method `[ALG-PP-2 §method]`, and C2PA specification `[ALG-PP-3 §section]`.
- `sources.min_tier: T0` for commercial-rights claims, `min_independent: 2` when rights are disputed, `recency_max_days: null`.
- No domain-data capability. `memory.capture: none`; do not retain proprietary SKU imagery or brand assets semantically.
- Cache: `fresh-only` for source/outputs; seed/provider metadata and local deterministic feature summaries stay in the run.
- Paywall/institutional access: not applicable.
- Deviations from §8.2: none.

#### 4. Tool chain and mechanisms
- Required: `fs.read` ingests assets; `image.analyze` extracts identity anchors, bounding shape, colors, logo/label regions, and faces; `image.edit` performs image-to-image scene editing; `image.generate` is allowed only for scene/background elements, never replacement of the product anchor; `image.transform` normalizes size, builds contact sheets, and runs comparisons; `fs.write` exports.
- Optional: a second healthy image-edit adapter for independent variants. If absent: `DEGRADED: only one image-generation family was available; visual diversity is reduced, but SKU-fidelity gates remain unchanged.`
- Provider hints are non-binding. Never use pure text-to-image to recreate the SKU from description alone; never use a face/likeness adapter unless explicitly introduced and approved.
- Mechanism: lock source-product pixels/features as identity anchors; separate permissible scene edits from forbidden product edits; generate scene plans; run bounded variants per scene/lighting/angle; compare logo OCR, color difference, silhouette overlap, aspect ratios, label layout, and geometry landmarks; reject drifted candidates; create a manifest with source hash, prompt, negative constraints, provider/model, seed, edit strength, and QA scores.
- Reuse note: all pixels route through `imagegen` product-mockup mode. `accurate-grok-imagine` or `fal-ai-media` can be an adapter, not a new owner.

#### 5. Internal data structures / schemas
- `ProductIdentitySpec`: `sku_id`, `source_hash`, `silhouette`, `landmarks`, `dominant_colors`, `logo_regions`, `label_regions`, `geometry_constraints`, `forbidden_changes`.
- `SceneVariantPlan`: `variant_id`, `scene_type`, `lighting`, `angle`, `background_prompt`, `negative_constraints`, `seed`, `edit_strength`.
- `ProductFidelityReport`: `variant_id`, `silhouette_iou`, `color_delta_e`, `logo_match`, `label_match`, `landmark_error_px`, `geometry_pass`, `identity_pass`, `manual_review_reasons`.
- Shared schemas: `RunContext`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, `ReviewVerdict`.
- No shared extension. Artifacts: `product_variants` (`png[]`, required); `contact_sheet` (`png`, required); `product_identity_spec` (`json`, required); `fidelity_report` (`json`, required); `provenance_manifest` (`json`, required).
- Schema example:
```json
{"variant_id":"studio-softbox-01","silhouette_iou":0.96,"color_delta_e":1.8,"logo_match":0.99,"label_match":0.94,"landmark_error_px":3.2,"geometry_pass":true,"identity_pass":true,"manual_review_reasons":["Generated microtext requires visual confirmation."]}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; variant fan-out and bounded repair are static.
- Lifecycle: `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `ingest_product` (`discover`, `tool`, `fs.read`) → hashes and validates image/rights metadata → emits source record.
2. `extract_identity` (`discover`, `tool`, `image.analyze`) → captures SKU identity anchors and forbidden changes → emits `ProductIdentitySpec`.
3. `commercial_rights_gate` (`discover`, `gate`, none) → records license/attestation and identity status → emits `SafetyDecision`.
4. `plan_scenes` (`plan`, `llm`, prompt pattern) → creates bounded scene/lighting/angle plans without changing product claims → emits `SceneVariantPlan[]`.
5. `generate_variants` (`execute`, `fanout`, `image.edit`) → creates image-to-image variants by plan → emits candidate PNGs with seeds.
6. `render_scene_elements` (`execute`, `tool`, `image.generate`) → generates only missing non-product scene assets when needed → emits compositing assets.
7. `measure_fidelity` (`quality-review`, `tool`, `image.analyze`) → compares each candidate to identity anchors → emits `ProductFidelityReport[]`.
8. `reject_or_repair` (`quality-review`, `join`, none) → rejects drift or retries with lower edit strength up to bound → emits accepted set.
9. `build_contact_sheet` (`quality-review`, `tool`, `image.transform`) → normalizes previews and labels scene metadata → emits contact sheet.
10. `owner_select` (`acceptance`, `gate`, none) → owner approves variants for commercial consideration → emits selection.
11. `export_variants` (`capture`, `export`, `fs.write`) → writes and disk-verifies images/manifests → emits `ArtifactManifest`.
- Fan-out is bounded by `scene_types × variants_per_scene`; each branch joins at fidelity review. Failed variants do not reduce the required selected count silently.
- Checkpoints after identity extraction, plan, each fan-out batch, fidelity join, selection, and export.
- Approval: `deterministic`, `human`; `human_required: 1`; `panel_required: false`. Commercial review and any identity escalation must cover final hashes.
- Resume: reuse source/identity spec and deterministic QA with matching hashes; do not silently regenerate accepted variants.

#### 7. Output format and UX behavior
- Owner sees contact sheet grouped by studio/lifestyle/flat-lay, each variant's lighting/angle, fidelity pass/fail, source comparison, caveats, selection control, provenance, and artifacts.
- Exports: `png`, `webp`, `json`; destination `output`; naming `product-photos-<sku_id>_{YYYY-MM-DD}`; language `en` for technical metadata.
- Preview shows exact scene count, variants, provider/model, estimated cost, source locality, rights state, fidelity thresholds, and any degraded adapter.
- Inline references: `[SKU1 sha256:<prefix>]`, `[LIC1 <document>@<hash>]`, `[BRAND §heading@<hash>]`; algorithm references `[ALG-PP-n §section]` appear only in technical provenance.
- Degradation: `DEGRADED: only one image-generation family was available; visual diversity is reduced, but SKU-fidelity gates remain unchanged.`
- Deviations: image deliverables include a contact sheet and C2PA/provenance sidecar where supported.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-REDACT`, `SH-SEC-CRED`, `SH-SEC-IDENTITY`.
- Required disclaimers: none at base R1; any runtime-escalated disclaimer is resolved only from the registered IDs under `SH-RISK-3`. Synthetic/commercial imagery carries provenance and review labels.
- Risk/data: R1 `image_rights`; R2 if `image_identity` is introduced. Source and outputs are `INTERNAL`, with PII classification if people appear.
- Gates: `reconciliation_survey`, `provenance_chain`, `rights_attestation`, `sku_identity_preservation`, `logo_geometry_integrity`, `color_fidelity`, `no_claim_invention`, `seed_provider_manifest`, `commercial_owner_acceptance`, `artifact_disk_verification`; `citation_coverage` applies to rights/claim text only.
- Validate schema; each QA metric range; expected dimensions; exact SKU ID; source-output hash inequality; no source overwrite; accepted count; provider/seed/prompt metadata; logo OCR/geometry thresholds.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Rights not attested | POLICY | Stop before generation | `BLOCKED: commercial image rights were not confirmed.` |
| SKU identity drifts | VALIDATION | Reject candidate and bounded retry | `REJECTED VARIANT: product identity/geometry changed beyond tolerance.` |
| Generated label text is unreliable | VALIDATION | Mark manual review; never claim exactness | `REVIEW REQUIRED: generated microtext or label detail is not reliable.` |
| Optional adapter unavailable | RESOURCE | Continue visibly with one family | `DEGRADED: visual diversity is reduced; fidelity gates are unchanged.` |
| Required variant count not met | VALIDATION | Block completion rather than pad with failed images | `BLOCKED: too few variants passed SKU-fidelity validation.` |

- Metrics: `variants_requested`, `variants_generated`, `variants_passed`, `silhouette_iou_min`, `color_delta_e_max`, `logo_match_min`, `generation_cost_per_accept`, `repair_attempts`; ledger records all prompts, seeds, provider IDs, and rejection reasons.
- Tests: happy `tests/fixtures/wf-13/bottle_studio.png`; degraded `tests/fixtures/wf-13/single_adapter.json`; safety `tests/fixtures/wf-13/unlicensed_logo_and_person.png`; contracts `fs.read`, `image.analyze`, `image.edit`, `image.generate`, `image.transform`, `fs.write`; golden `tests/golden/WF-13/fidelity-report.json`. Additional acceptance: no accepted candidate may fail any declared identity anchor.
- Deviations: none.

### WF-14 — Post creator

**Source ref:** `user-spec:WF-14` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: none; `public_publication` and `external_action` apply only to a separate publish action) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `workflow:WF-14` (draft-only post-creator recipe)  
· existing assets `skill:.agents/skills/humanizer`; `skill:.agents/skills/agentic-humanizer`; `skill:.agents/skills/imagegen`; `skill:.agents/skills/x-api` for an explicitly selected platform; X uses a direct API, image provider is direct, and no general social-post MCP exists in the canonical registry  
· duplicate surfaces avoided `one skill per social network`; `auto-publish`; `fake testimonials`  
· delta `Compose copy, voice, optional image, platform constraints, source checks, and owner publish gate; never infer permission to post.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-14`; `.agents/skills/humanizer/SKILL.md`; `.agents/skills/agentic-humanizer/SKILL.md`; `.agents/skills/imagegen/SKILL.md`; `.agents/skills/x-api/SKILL.md`; `.agents/agents.json`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-14`

#### 1. Purpose and user story
- The owner supplies a topic, target platforms, voice, and goal and receives platform-specific post variants containing hook, body, CTA, and hashtags, each labeled by persona and funnel objective (`awareness`, `conversion`, or `engagement`) and never automatically posted.
- User story: "As a brand or professional account owner, I want several platform-appropriate post drafts in my verified voice so that I can choose and publish deliberately."
- Boundary: this workflow does not post, schedule, message, buy ads, fabricate testimonials, create a full campaign strategy, or replace `WF-03` for simple message polishing.
- Routing: triggers `create social post variants`, `draft a LinkedIn post`, `write posts for multiple platforms`, `make awareness and conversion versions`, `add hooks and CTAs`; negative triggers `polish this existing email` → `WF-03`, `make a video thumbnail` → `WF-24`, `launch or schedule posts` → external action outside this workflow; aliases `/post-create`, `/social-drafts`.
- Execution modes: `interactive` and `background`; `scheduled` may prepare drafts but never publish. No `owner-present-only` need until a separate publish action.
- Success criterion: each variant fits current official platform constraints, sounds consistent with the supplied brand voice, separates facts from creative copy, labels its persona/funnel intent, avoids duplicated variants, and leaves publication entirely to the owner.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `topic` | string | yes | 1–5,000 characters | INTERNAL |
| `platforms` | list<enum> | yes | subset `linkedin`, `x`, `instagram`, `facebook`, `tiktok`, `youtube`, `other`; 1–7 | PUBLIC |
| `voice` | string | yes | 1–2,000 characters or approved guide reference | INTERNAL |
| `goal` | enum | yes | `awareness`, `conversion`, `engagement` | PUBLIC |
| `personas` | list<string> | no | 1–8; no sensitive-trait targeting | INTERNAL | `["primary audience"]` |
| `variants_per_platform` | integer | no | 1–10 | PUBLIC | 3 |
| `cta_policy` | enum | no | `none`, `soft`, `direct` | PUBLIC | `soft` |
| `hashtag_count` | integer | no | 0–20; platform validation may lower | PUBLIC | platform default |
| `factual_source_urls` | list<url> | no | ≤20; HTTPS; fetched under `SH-SEC-SSRF` | PUBLIC | `[]` |
| `brand_guide` | file | no | PDF/DOCX/MD/TXT; ≤20 MB | INTERNAL | none |
| `image_option` | enum | no | `none`, `brief_only`, `generate` | PUBLIC | `brief_only` |
| `output_language` | enum | no | `ro`, `en` | PUBLIC | `ro` |

- Preconditions: healthy `llm.extract`, `llm.rewrite`, `llm.judge`, `fs.write`; `web.fetch` for current platform guides and supplied factual URLs; `image.generate` only when selected; brand guide path exists; no `browser.act` or publishing adapter is granted.
- Intensity:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 2 | 2 | 1 | 1 | 0 |
| medium | 0 | 5 | 5 | 3 | 2 | 1 |
| high | 0 | 10 | 10 | 5 | 2 | 2 |
| limitless | 0 | 20 | 20 | 5 | 3 | 3 |

- Budget: small `18 / 300 / 4`; medium `55 / 900 / 14`; high `140 / 1,800 / 36`; limitless `240 / 3,600 / 70`.
- Deviations: platform-guide sources scale with selected platforms; no general web discovery is performed unless factual URLs are supplied.

#### 3. Data sources and knowledge bases
- Primary external platform authorities: LinkedIn Help/Marketing Solutions official posting guidance `[POST-LI1 §heading]`; X Help Center/developer documentation `[POST-X1 §heading]`; Meta Business Help Center for Instagram/Facebook `[POST-META1 §heading]`; TikTok Business Help/Creative Center `[POST-TT1 §heading]`; YouTube Help `[POST-YT1 §heading]`. Current official pages are fetched for selected platforms only.
- Owner brand guide is `[BRAND §heading@<hash>]`; supplied factual pages are `[FACT1 §heading]` etc. No post may turn an unsourced model inference into a product, customer, performance, legal, medical, or financial claim.
- `sources.min_tier: T2`, `min_independent: 2` for competitive/performance claims, `recency_max_days: 30`; official platform constraints tighten to a 7-day refresh. T3 vendor/brand claims are labeled under `SH-SRC-6`.
- No domain-data capability. `memory.search` may retrieve approved voice/brand decisions. `memory.capture: decisions` stores only reusable voice and platform preferences approved by the owner.
- Cache: `standard`; official platform guides are `slow` with 7-day override; owner brand guide invalidates on hash change; factual source pages follow their claim volatility.
- Paywall: not expected. Authenticated platform analytics are out of scope.
- Deviations: official platform rules require T0/T1-style first-party documentation even though D7 normally allows T2/T3 observational sources.

#### 4. Tool chain and mechanisms
- Required: `web.fetch` obtains current official platform rules and owner-supplied factual sources; `fs.read` reads brand guide; `llm.extract` structures claims, personas, and constraints; `llm.rewrite` creates variants; `llm.judge` checks platform fit, voice, duplication, claim support, and fake-testimonial risk; `fs.write` exports.
- Optional: `memory.search` for approved voice and `image.generate` for a selected visual. Missing image generation yields: `DEGRADED: image generation was unavailable; an implementation-ready visual brief is included instead.`
- Provider hints: existing humanizer paths own copy quality, `imagegen` owns optional image creation, and `x-api` is never called for posting. No browser/post adapter is permitted.
- Mechanism: normalize topic and goal; fetch selected platform constraints; build a claim ledger; map each persona to one of awareness/conversion/engagement; draft distinct hook/body/CTA/hashtag structures; run independent voice, platform, and factual-risk reviews; deduplicate semantically; optionally create an image brief or image; package drafts with labels and evidence.
- Reuse note: this recipe composes existing leaves and owns sequencing only. It creates no per-network skill and has no auto-post path.

#### 5. Internal data structures / schemas
- `PostBrief`: `topic`, `platforms`, `voice_rules`, `goal`, `personas`, `cta_policy`, `claims`, `prohibited_claims`.
- `PlatformConstraint`: `platform`, `source_id`, `retrieved_at`, `text_limit`, `hashtag_guidance`, `link_behavior`, `media_constraints`, `stale`.
- `PostVariant`: `variant_id`, `platform`, `persona`, `goal_label`, `hook`, `body`, `cta`, `hashtags`, `citations`, `character_count`, `visual_brief`, `risk_flags`.
- Shared schemas: `RunContext`, `SourceRecord`, `Citation`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, `ReviewVerdict`.
- No shared extension. Artifacts: `post_variants` (`markdown`, required); `post_variants_json` (`json`, required); `visual_assets` (`png[]`, optional); `claim_ledger` (`json`, required).
- Schema example:
```json
{"variant_id":"linkedin-awareness-01","platform":"linkedin","persona":"technical decision-maker","goal_label":"awareness","hook":"What changes when evidence quality becomes the primary metric?","body":"A short evidence-grounded explanation.","cta":"Compare the checklist with your current process.","hashtags":["#ResearchOps"],"citations":["FACT1"],"character_count":173,"visual_brief":"Clean checklist graphic; no fabricated metrics.","risk_flags":[]}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; platform fan-out is bounded and joins once.
- Lifecycle: `discover`, `recall`, `plan`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`.
1. `normalize_brief` (`discover`, `tool`, `llm.extract`) → validates topic, personas, voice, and goal → emits `PostBrief`.
2. `load_voice` (`recall`, `tool`, `memory.search`) → retrieves approved voice preferences when available → emits voice context.
3. `fetch_platform_rules` (`discover`, `fanout`, `web.fetch`) → retrieves official guidance for selected platforms → emits `PlatformConstraint[]`.
4. `fetch_fact_sources` (`discover`, `fanout`, `web.fetch`) → retrieves supplied factual pages and builds source records → emits claim evidence.
5. `plan_variant_matrix` (`plan`, `llm`, prompt pattern) → assigns platform × persona × goal structures and diversity constraints → emits plan.
6. `draft_platform_variants` (`execute`, `fanout`, `llm.rewrite`) → creates hook/body/CTA/hashtags per plan → emits candidates.
7. `generate_or_brief_image` (`execute`, `tool`, `image.generate`) → optionally creates one visual per selected group or emits a brief → emits assets/briefs.
8. `spec_check` (`spec-review`, `gate`, none) → validates current platform limits and required labels → emits validations.
9. `review_lanes` (`quality-review`, `fanout`, none) → checks voice, factual support, platform fit, sensitive targeting, fake testimonials, and semantic duplication → emits findings.
10. `reconcile_posts` (`quality-review`, `join`, none) → repairs once and preserves rejected variants visibly → emits accepted set.
11. `owner_acceptance` (`acceptance`, `gate`, none) → owner selects drafts; no publish action exists → emits selection.
12. `export_posts` (`capture`, `export`, `fs.write`) → writes and manifests drafts/assets → emits `ArtifactManifest`.
- Branches: platforms fan out independently; absence of factual URLs forces factual claims to be removed or marked as owner-supplied assertions; unavailable image generation produces briefs.
- Checkpoints after source capture, plan, candidate batch, review join, owner selection, and export.
- Approval: `deterministic`, `human`; `human_required: 1`; `panel_required: false` for owner-selected outward-facing draft. Publishing would trigger separate R3 controls and is unavailable here.
- Resume: valid current platform rules and source records may be reused within TTL; candidate generation resumes from missing branches only.

#### 7. Output format and UX behavior
- Owner sees a platform tab/group, then each variant with persona, goal label, hook, body, CTA, hashtags, character count, citations, and visual brief/image; rejected or risky claims are listed separately.
- Exports: `md`, `json`, optional `png`; destination `output`; naming `post-variants-<topic-slug>_{YYYY-MM-DD}`; language per input.
- Preview shows selected platforms, variant matrix, sources, voice lanes, image option, cost, and bold `DRAFT ONLY — no post/schedule/send capability`.
- Citations render inline as `[POST-LI1 §heading]`, `[POST-X1 §heading]`, `[POST-META1 §heading]`, `[POST-TT1 §heading]`, `[POST-YT1 §heading]`, `[BRAND §heading@<hash>]`, and `[FACTn §heading]`; stale platform rules block instead of appearing as caveats.
- Degradation: `DEGRADED: image generation was unavailable; an implementation-ready visual brief is included instead.`
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-REDACT`, `SH-SEC-CRED`; no browser/post capability is attached.
- Required disclaimers: none at base R1; registered domain disclaimer IDs are added under `SH-RISK-3` if the draft contains regulated claims. `DRAFT ONLY` is a UX status label, not a disclaimer ID.
- Risk/data: base R1; `public_publication` and `external_action` are deliberately not exercised. Data `PUBLIC`/`INTERNAL`; PII in testimonials or audience data is rejected/minimized.
- Gates: `reconciliation_survey`, `citation_coverage`, `provenance_chain`, `platform_constraint_current`, `brand_voice_conformance`, `claim_support`, `no_fake_testimonial`, `no_sensitive_targeting`, `semantic_variant_diversity`, `no_external_action`, `artifact_disk_verification`.
- Validate schema, per-platform character/hashtag/media bounds, citation existence, persona/goal enums, unique variants, CTA policy, no unsupported numerical claims, and no publish invocation.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Platform guide stale/unavailable | RESOURCE | Block that platform branch | `BLOCKED PLATFORM: current official posting constraints could not be verified.` |
| Unsupported factual claim | VALIDATION | Remove or mark owner assertion; never invent cite | `REVIEW REQUIRED: this claim has no retrievable support.` |
| Fake testimonial/request | POLICY | Reject claim | `BLOCKED: fabricated customer testimony is not permitted.` |
| Image generation unavailable | RESOURCE | Emit visual brief | `DEGRADED: an implementation-ready visual brief is included instead.` |
| Publish instruction appears | POLICY | No action; preserve draft only | `NO ACTION TAKEN: this workflow never posts, schedules, or sends.` |

- Metrics: `platforms`, `variants_requested`, `variants_accepted`, `duplicate_similarity_max`, `claims_total`, `claims_supported`, `platform_rules_age_s`, `image_briefs`, `images_generated`; ledger records the no-publish boundary and owner selection.
- Tests: happy `tests/fixtures/wf-14/multiplatform_brand_post.json`; degraded `tests/fixtures/wf-14/no_image_adapter.json`; safety `tests/fixtures/wf-14/fake_testimonial_and_autopost.json`; contracts `web.fetch`, `fs.read`, `memory.search`, `llm.extract`, `llm.rewrite`, `llm.judge`, `image.generate`, `fs.write`; golden `tests/golden/WF-14/post-variants.md`. Additional acceptance: invocation ledger contains zero `side_effects: external`.
- Deviations: none.

### WF-15 — Document summary

**Source ref:** `user-spec:WF-15` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** prompt-content  
**Risk tier:** R0 (factors: runtime `personal_health_data` or `financial_personal_data` when detected) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `workflow:WF-15` (document-summary recipe selecting the existing format leaf)  
· existing assets `skill:.agents/skills/pdf-reader`; `skill:.agents/skills/long-pdf-evidence-synthesizer`; `skill:.agents/skills/doc`; native file readers; `pdf-reader` MCP is parked; `markitdown` is disabled/denied and unnecessary for plain text/DOCX  
· duplicate surfaces avoided `generic summarizer duplicating PDF/DOCX logic`; `treating disabled MarkItDown as available`  
· delta `Dispatch by file type, require page/span grounding, hash source, inherit P4/R2, and use local parsing before cloud.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-15`; `.agents/skills/pdf-reader/SKILL.md`; `.agents/skills/long-pdf-evidence-synthesizer/SKILL.md`; `.agents/skills/doc/SKILL.md`; `.agents/agents.json`; `.agents/mcp-cursor-parked-31.json`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-15`

#### 1. Purpose and user story
- The owner uploads a supported document and receives a grounded hierarchical summary with key metrics, source spans, chart specifications, takeaways, and both a human-readable export and a slide-ready machine outline.
- User story: "As a reader of a long document, I want a concise but traceable summary so that I can understand its structure, claims, metrics, and presentation-ready takeaways without losing the path back to the source."
- Boundary: this workflow does not convert file formats (`WF-16`), perform final-document QA (`WF-20`), create slides (`WF-18`), or add external facts not present in the document.
- Routing: triggers `summarize this document`, `extract key metrics and takeaways`, `make a slide-ready outline`, `summarize this PDF/DOCX`, `show source spans`; negative triggers `convert this file` → `WF-16`, `turn this into slides` → `WF-18`, `proofread/final QA` → `WF-20`; aliases `/document-summary`, `/summarize-file`.
- Execution modes: `interactive` and `background`; owner-present-only at runtime for PHI/FINANCIAL files or approved remote egress.
- Success criterion: every claim about the document has a page/section/slide/sheet locator, metrics preserve units and context, chart specs link to extracted data, omitted/uncertain regions are visible, and the machine outline is ready for `WF-18`.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `source_file` | file | yes | PDF/DOCX/PPTX/MD/TXT; ≤250 MB; local allowed root | INTERNAL; runtime classified |
| `summary_length` | enum | no | `brief`, `standard`, `detailed` | PUBLIC | `standard` |
| `focus_questions` | list<string> | no | ≤20; each ≤1,000 chars | INTERNAL | `[]` |
| `include_metrics` | bool | no | — | PUBLIC | true |
| `include_chart_specs` | bool | no | chart specs only, not invented data | PUBLIC | true |
| `include_source_spans` | bool | no | cannot be false for factual summaries | PUBLIC | true |
| `slide_outline_depth` | integer | no | 1–5 | PUBLIC | 3 |
| `ocr_policy` | enum | no | `auto`, `never`, `required` | PUBLIC | `auto` |
| `output_language` | enum | no | `ro`, `en`, `preserve` | PUBLIC | `preserve` |

- Preconditions: file exists and hashes; MIME is sniffed; `fs.read`, `doc.extract_text`, `llm.extract`, `llm.summarize`, and `fs.write` healthy; local parser supports type; PII/PHI classification resolved before any remote lane.
- Intensity:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 1 | 1 | 1 | 1 | 0 |
| medium | 0 | 1 | 1 | 3 | 1 | 1 |
| high | 0 | 1 | 1 | 5 | 1 | 2 |
| limitless | 0 | 1 | 1 | 5 | 1 | 3 |

- Budget: small `20 / 420 / 4`; medium `80 / 1,800 / 20`; high `220 / 4,500 / 60`; limitless `400 / 7,200 / 110`.
- Deviations: the single uploaded document is one source object, while hierarchical chunks are not counted as independent sources; full-text reads remain one and require coverage of all parseable pages.

#### 3. Data sources and knowledge bases
- No external web source is used by default. The owner-selected document is the primary source and is referenced inline as `[DOC p.12 ¶3]`, `[DOC §3.2 ¶4]`, `[DOC slide 7]`, or `[DOC sheet:<name>!<range>]` according to format. A model inference is `[INFERENCE]` and cannot be load-bearing.
- `sources.min_tier: T2` for any externally asserted factual insert, but the document itself is authoritative only for what it contains; `min_independent: 1`; `recency_max_days: null` because validity ends when the source hash changes.
- No domain-data capability. `memory.capture: none`; summaries and raw document content are not persisted semantically unless the owner separately requests a durable decision capture.
- Cache: `fresh-only` for PII/PHI/FINANCIAL files; otherwise `standard` within the local run keyed by source hash. Extracted text does not enter a shared cache for sensitive classes.
- Paywall/institutional access: not applicable because the input is an owner-selected local file.
- Deviations: source-span grounding is mandatory even where prompt-content style outputs would otherwise need no citation.

#### 4. Tool chain and mechanisms
- Required: `fs.read` hashes/reads; `doc.extract_text` is `FileRead` plus layout-aware extraction; `llm.extract` is the `StructureExtractor` for headings, tables, figures, metrics, and spans; `llm.summarize` is the hierarchical `Summarizer`; `fs.write` exports.
- Optional: `image.analyze` for scanned pages/charts and `doc.convert` for optional DOCX export. Missing OCR yields: `DEGRADED: <n> image-only pages could not be read; they are listed as summary gaps.` Missing DOCX export leaves MD/JSON complete.
- Provider hints: local parsers first; parked `pdf-reader` may be activated only by approved routing, and disabled `markitdown` must not be treated as available. Remote summarization is barred for PHI without explicit per-run approval.
- Mechanism: extract a canonical document tree with stable source spans; summarize leaf chunks; reconcile chunk summaries into section summaries; build a global summary from section summaries while carrying citations; separately extract metrics with units/period/context; derive chart specs only from extracted values; generate takeaways and a slide-ready outline linked to evidence.
- Reuse note: recipe dispatches to `pdf-reader`, `long-pdf-evidence-synthesizer`, `doc`, or native readers by MIME and composes their outputs; it implements no new parser.

#### 5. Internal data structures / schemas
- `DocumentTree`: `source_hash`, `mime`, `page_count`, `nodes[]` with `node_id`, `parent_id`, `kind`, `title`, `locator`, `text_hash`, `children`.
- `SourceSpan`: `span_id`, `node_id`, `locator_kind`, `locator_value`, `quote`, `quote_hash`, `match_verified`.
- `MetricRecord`: `metric_id`, `name`, `value`, `unit`, `period`, `qualifier`, `source_span_ids`, `confidence`.
- `ChartSpec`: `chart_id`, `title`, `type`, `series`, `x`, `y`, `units`, `source_metric_ids`, `caveats`.
- `SummaryBundle`: `executive_summary`, `section_summaries`, `key_metrics`, `chart_specs`, `takeaways`, `slide_outline`, `coverage`, `gaps`.
- Shared schemas: all §6 evidence, invocation, artifact, validation, safety, and verdict schemas unchanged.
- Artifacts: `document_summary` (`markdown`, required); `summary_bundle` (`json`, required); `slide_ready_outline` (`json`, required); `summary_docx` (`docx`, optional).
- Schema example:
```json
{"executive_summary":"The document proposes a three-phase program.","section_summaries":[{"section":"3","summary":"Phase two carries the largest cost.","source_span_ids":["sp-31"]}],"key_metrics":[{"metric_id":"m1","name":"Phase two budget","value":2.4,"unit":"million EUR","period":"2027","qualifier":"planned","source_span_ids":["sp-44"],"confidence":"high"}],"chart_specs":[{"chart_id":"c1","title":"Budget by phase","type":"bar","series":["planned budget"],"x":"phase","y":"EUR million","units":"EUR million","source_metric_ids":["m1"],"caveats":[]}],"takeaways":["Most planned spend occurs in phase two."],"slide_outline":[{"title":"Program overview","evidence":["sp-31"]}],"coverage":{"parseable_pages":48,"summarized_pages":48},"gaps":[]}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; hierarchical foreach and joins are statically bounded by the extracted tree.
- Lifecycle: `discover`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`.
1. `ingest_document` (`discover`, `tool`, `fs.read`) → copies, hashes, MIME-sniffs, and classifies the file → emits source descriptor.
2. `extract_document` (`discover`, `tool`, `doc.extract_text`) → extracts text, layout, tables, figures, and locators → emits raw document tree.
3. `ocr_missing_pages` (`discover`, `tool`, `image.analyze`) → optionally OCRs image-only pages → emits source spans and confidence.
4. `structure_extract` (`execute`, `tool`, `llm.extract`) → normalizes headings, tables, metrics, and source spans → emits `DocumentTree`, `MetricRecord[]`.
5. `summarize_leaves` (`execute`, `foreach`, `llm.summarize`) → summarizes each leaf with mandatory spans → emits leaf summaries.
6. `summarize_sections` (`execute`, `join`, `llm.summarize`) → combines child summaries without losing citations → emits section summaries.
7. `summarize_document` (`execute`, `join`, `llm.summarize`) → produces executive summary and takeaways → emits summary candidate.
8. `build_charts_outline` (`execute`, `tool`, `llm.extract`) → creates chart specs and slide outline from extracted records only → emits machine outline.
9. `grounding_check` (`spec-review`, `gate`, none) → verifies each assertion/metric against stored spans → emits validations.
10. `coverage_review` (`quality-review`, `tool`, `llm.judge`) → finds omissions, distortion, and unsupported takeaways → emits advisory findings.
11. `owner_acceptance` (`acceptance`, `gate`, none) → required for sensitive documents or acknowledged unreadable regions → emits acceptance.
12. `export_summary` (`capture`, `export`, `fs.write`) → exports, hashes, re-reads, and manifests outputs → emits `ArtifactManifest`.
- Branches: OCR only for image-only pages; leaf fan-out joins by section; grounding failure loops once to the affected summary, never the entire document.
- Checkpoints after extraction, each section join, global summary, validation, and export.
- Approval: `deterministic`; `human_required: 0` at R0 and `1` for sensitive/runtime-escalated files; `panel_required: false`. Missing required pages or source-span verification blocks.
- Resume: deterministic extraction/OCR and completed chunk summaries with matching hashes are reused; changed source hash starts a new run.

#### 7. Output format and UX behavior
- Owner sees `Executive summary`, `Document map`, `Key metrics`, `Chart specifications`, `Section summaries`, `Takeaways`, `Slide-ready outline`, `Coverage and unreadable regions`, then source evidence/provenance/artifacts/gates.
- Exports: `md`, `json`, optional `docx`; destination `active_project_docs`; naming `document-summary_<source-stem>_{YYYY-MM-DD}`; language per input.
- Progress reports pages extracted, OCR gaps, chunks/sections completed, grounding coverage, and export. Preview shows local/remote handling, document class, page/chunk count estimate, voice distribution, and optional capability status.
- Citations appear inline using `[DOC p.n ¶n]`, `[DOC §x.y ¶n]`, `[DOC slide n]`, or `[DOC sheet:name!range]`; uncertainty shows OCR confidence, missing pages, ambiguous tables, contradictory sections, and `[INFERENCE]` labels.
- Degradation: `DEGRADED: <n> image-only pages could not be read; they are listed as summary gaps.`
- Deviations: summary exports include a slide-ready JSON outline even when no slide deck is requested.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-REDACT`, `SH-SEC-CRED`; add `SH-SEC-PHI`/`SH-SEC-FIN` when classification triggers.
- Required disclaimers: none at base R0; registered health/legal/finance disclaimer IDs are inherited under `SH-RISK-3` when document content enters those domains.
- Risk/data: base R0; runtime R2 for `personal_health_data` or `financial_personal_data`. Handles `PUBLIC`, `INTERNAL`, `PII`, `PHI`, `FINANCIAL`, with `SECRET` values redacted.
- Gates: `reconciliation_survey`, `citation_coverage`, `provenance_chain`, `source_span_match`, `document_coverage`, `metric_unit_context`, `chart_data_lineage`, `slide_outline_grounding`, `secret_scan`, `artifact_disk_verification`.
- Validate schemas; every source-span quote against stored extraction; metric numeric type/unit/period; chart series references existing metrics; outline evidence references spans; summarized-page coverage equals parseable pages or gaps are explicit.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Unsupported/corrupt file | VALIDATION | Reject before extraction | `FAILED: the document format or file content is unsupported/corrupt.` |
| Image-only pages and OCR unavailable | RESOURCE | Continue only with explicit gaps | `DEGRADED: image-only pages could not be read and are excluded by page number.` |
| Span cannot be verified | VALIDATION | Remove claim or block if load-bearing | `BLOCKED CLAIM: the cited source span was not found in the stored document.` |
| Sensitive file would leave local boundary | POLICY | Require explicit approval or local-only adapter | `AWAITING_APPROVAL: sensitive document content would be sent to a remote model.` |
| Budget ends before full coverage | RESOURCE | `FAILED_TO_RUN`, not partial success | `FAILED_TO_RUN: full-document coverage was not completed within budget.` |

- Metrics: `pages_total`, `pages_parseable`, `pages_ocr`, `chunks_total`, `chunks_summarized`, `source_span_coverage`, `metrics_extracted`, `chart_specs_valid`, `compression_ratio`, `unsupported_claims_removed`; ledger links summaries to spans/chunks.
- Tests: happy `tests/fixtures/wf-15/annual-report.pdf`; degraded `tests/fixtures/wf-15/scanned-pages-no-ocr.pdf`; safety `tests/fixtures/wf-15/injection-and-secret.docx`; contracts `fs.read`, `doc.extract_text`, `image.analyze`, `llm.extract`, `llm.summarize`, `llm.judge`, `doc.convert`, `fs.write`; golden `tests/golden/WF-15/summary-bundle.json`. Additional acceptance: all parseable pages are represented or explicitly excluded, and every metric has unit/context/span.
- Deviations: none.

### WF-16 — Filetype converter

**Source ref:** `user-spec:WF-16` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** prompt-content  
**Risk tier:** R1 (factors: none; sensitive-data and irreversible-local factors are prevented or escalated) · **Engine:** simple · **Default intensity:** small  
**Reconciliation:** action `UPGRADE` · canonical owner `skill:.agents/skills/nutrient-document-processing` (local-first conversion dispatcher)  
· existing assets `skill:.agents/skills/nutrient-document-processing`; `skill:.agents/skills/doc`; `skill:.agents/skills/pdf`; `skill:.agents/skills/spreadsheet`; `skill:.agents/skills/slides`; `skill:.agents/skills/video-convert`; `markitdown` disabled/denied; `nutrient-dws` absent/deferred; local CLIs are not MCPs  
· duplicate surfaces avoided `a new converter for each format`; `silently removing Nutrient`; `enabling MarkItDown as a shortcut`  
· delta `Preserve the cloud API benefit but add local-first format routing, PII consent gate, macro refusal, output _v2 naming, hash/round-trip checks.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-16`; `.agents/skills/nutrient-document-processing/SKILL.md`; `.agents/skills/doc/SKILL.md`; `.agents/skills/pdf/SKILL.md`; `.agents/skills/spreadsheet/SKILL.md`; `.agents/skills/slides/SKILL.md`; `.agents/skills/video-convert/SKILL.md`; `.agents/agents.json`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-16`

#### 1. Purpose and user story
- The owner supplies a file, the workflow detects its actual type, selects one or more targets among PDF, DOCX, PPTX, Markdown, TXT, and images, runs the safest local-first pipeline, and returns converted files plus layout/accessibility, animation/macro, loss, hash, and deterministic-validation reports.
- User story: "As a document owner, I want a file converted to one or more formats without silent loss or overwrite so that I can use the result confidently and understand every unsupported feature."
- Boundary: this workflow does not summarize content (`WF-15`), redesign slides (`WF-18`), run macros, convert unsupported media merely because a similarly named skill exists, or overwrite the source.
- Routing: triggers `convert this file`, `export PDF to DOCX`, `turn DOCX into Markdown`, `convert slides to images`, `make PDF and text versions`; negative triggers `summarize this file` → `WF-15`, `create a presentation` → `WF-18`, `final QA` → `WF-20`; aliases `/convert-file`, `/filetype-converter`.
- Execution modes: `interactive` and `background`; sensitive cloud conversion requires `owner-present-only`.
- Success criterion: every output is decodable, hashed, non-overwriting, structurally compared with the input, and accompanied by an explicit loss report covering layout, fonts, links, alt text, notes, animations, formulas, and macros.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `source_file` | file | yes | supported sniffed type; ≤500 MB; allowed root | INTERNAL; runtime classified |
| `target_formats` | list<enum> | yes | subset `pdf`, `docx`, `pptx`, `md`, `txt`, `png`, `jpeg`, `webp`; unique | PUBLIC |
| `layout_priority` | enum | no | `fidelity`, `editable`, `balanced` | PUBLIC | `balanced` |
| `accessibility_priority` | enum | no | `preserve`, `repair_if_safe`, `report_only` | PUBLIC | `preserve` |
| `image_dpi` | integer | no | 72–600 for raster targets | PUBLIC | 144 |
| `page_range` | string | no | validated page/slide range | PUBLIC | all |
| `include_notes` | bool | no | applies to PPTX | INTERNAL | true |
| `cloud_fallback` | enum | no | `deny`, `ask`, `allow_if_public` | PUBLIC | `ask` |
| `output_directory` | dir | no | approved root only | INTERNAL | source directory or active project output |

- Preconditions: source exists, MIME is sniffed, no symlink/root escape, free disk ≥2× estimated outputs, selected local adapters healthy, `doc.convert`, `image.transform`, `fs.read`, `fs.write` available; cloud fallback health/consent checked only if local conversion fails.
- Intensity:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 0 | 0 | 0 | 0 | 0 |
| medium | 0 | 0 | 0 | 0 | 0 | 1 |
| high | 0 | 0 | 0 | 0 | 0 | 2 |
| limitless | 0 | 0 | 0 | 0 | 0 | 3 |

- Budget: small `20 / 900 / 3`; medium `50 / 1,800 / 8`; high `100 / 3,600 / 18`; limitless `180 / 7,200 / 32`.
- Deviations: deterministic tool-only workflow uses zero voices/sources. Loops are alternate conversion/round-trip attempts, not model deliberation.

#### 3. Data sources and knowledge bases
- No external information sources are used. The source file is referenced as `[FILE1 sha256:<prefix>]`; outputs as `[OUT:<format> sha256:<prefix>]`.
- Algorithm/specification references are implementation-only: Pandoc User's Guide `[ALG-FC-1 §section]`, ECMA-376 Office Open XML `[ALG-FC-2 Part/§]`, ISO 32000 PDF specification `[ALG-FC-3 §section]`, and WCAG/WAI document-accessibility guidance `[ALG-FC-4 criterion]`. They do not certify a particular conversion.
- `sources.min_tier: T1` for any standards claim, `min_independent: 1`, `recency_max_days: null`; no citation gate applies to pure conversion receipts.
- No domain-data or memory capability; `memory.capture: none`.
- Cache: `fresh-only` for source and sensitive outputs; deterministic intermediates may be memoized in-run by source hash, target, adapter version, and options.
- Paywall/institutional access: not applicable.
- Deviations: none.

#### 4. Tool chain and mechanisms
- Required: `fs.read` detects and hashes; `doc.extract_text` provides structural baselines; `doc.convert` handles document-family transformations; `image.transform` handles deterministic raster/format operations; `fs.write` writes versioned outputs.
- Optional: cloud Nutrient adapter behind `doc.convert`, preserving its capability when local paths cannot meet a target. If absent or not approved: `DEGRADED: cloud conversion was not used; targets unsupported by the local pipeline are reported as unavailable rather than silently approximated.`
- Provider hints: local-first dispatcher selects format-specific existing leaves; never activate disabled `markitdown`; never ask an LLM to convert layout/format (`SH-TOOL-6`).
- Mechanism: sniff input independently of extension; inspect macros, embedded objects, animations, fonts, links, alt text, notes, forms, formulas, and signatures; choose an explicit route per target; convert in isolated workspace without macros; reopen each output; compare structure/render/text/accessibility against the baseline; optionally round-trip for deterministic loss detection; emit a loss taxonomy and hashes.
- Reuse note: upgrade `nutrient-document-processing` in place as dispatcher and preserve the cloud benefit behind consent. Existing `doc`, `pdf`, `spreadsheet`, `slides`, and relevant transform leaves retain format ownership.

#### 5. Internal data structures / schemas
- `FileInspection`: `source_hash`, `mime_sniffed`, `extension`, `size_bytes`, `pages_or_slides`, `features` (`macros`, `animations`, `embedded_objects`, `fonts`, `links`, `alt_text`, `notes`, `forms`, `formulas`, `signatures`), `classification`.
- `ConversionPlan`: `target`, `route`, `adapter_version`, `locality`, `options`, `expected_losses`, `approval_required`.
- `ConversionResult`: `target`, `path`, `sha256`, `bytes`, `open_valid`, `text_coverage`, `structure_coverage`, `render_similarity`, `accessibility_checks`, `losses`, `round_trip`.
- Shared schemas: `RunContext`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, `ReviewVerdict`.
- No shared extension. Artifacts: `converted_files` (format-specific, required per accepted target); `inspection_report` (`json`, required); `conversion_report` (`json`, required); `loss_report` (`markdown`, required); preview renders (`png[]`, optional).
- Schema example:
```json
{"target":"pdf","path":"out/report_2026-08-29_v2.pdf","sha256":"sha256:3333333333333333333333333333333333333333333333333333333333333333","bytes":482910,"open_valid":true,"text_coverage":0.998,"structure_coverage":0.94,"render_similarity":0.97,"accessibility_checks":{"tagged":true,"alt_text_preserved":false},"losses":[{"feature":"animation","severity":"expected","detail":"Flattened in PDF target."}],"round_trip":{"performed":true,"text_hash_match":true}}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; one bounded target fan-out and alternate-route retry.
- Lifecycle: `discover`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `ingest_file` (`discover`, `tool`, `fs.read`) → copies, hashes, MIME-sniffs, and validates containment → emits source descriptor.
2. `inspect_features` (`discover`, `tool`, `doc.extract_text`) → records structure, macros, animations, accessibility, fonts, links, and embedded objects → emits `FileInspection`.
3. `macro_safety_gate` (`discover`, `gate`, none) → refuses macro execution and records unsupported active content → emits `SafetyDecision`.
4. `plan_targets` (`discover`, `llm`, prompt pattern) → deterministically selects registered routes and expected losses → emits `ConversionPlan[]`.
5. `conversion_consent_gate` (`discover`, `gate`, none) → asks before any nonlocal conversion of non-PUBLIC content → emits approvals.
6. `convert_targets` (`execute`, `fanout`, `doc.convert`) → converts each document target in isolated workspace → emits outputs.
7. `transform_images` (`execute`, `fanout`, `image.transform`) → renders/encodes image targets → emits outputs.
8. `reopen_outputs` (`quality-review`, `gate`, none) → decodes each output and validates type/signature → emits structural validations.
9. `compare_round_trip` (`quality-review`, `tool`, `doc.extract_text`) → computes text, structure, render, and accessibility coverage → emits `ConversionResult[]`.
10. `loss_acceptance` (`acceptance`, `gate`, none) → owner accepts material expected losses or removes target → emits accepted targets.
11. `export_conversions` (`capture`, `export`, `fs.write`) → writes versioned files/reports, re-reads hashes, and manifests → emits `ArtifactManifest`.
- Fan-out is one branch per target. A failed local branch may request cloud fallback; denial or absence remains explicit. Alternate routes are bounded by loops.
- Checkpoints after inspection, plan/consent, each completed target, validation, acceptance, and export.
- Approval: `deterministic`, `human`; `human_required: 1` only for cloud egress or material loss acceptance; `panel_required: false`. Macro execution, source overwrite, invalid output, or undisclosed loss blocks.
- Resume: reuse source inspection and completed valid deterministic targets; do not repeat cloud calls if output hashes are verified.

#### 7. Output format and UX behavior
- Owner sees detected type, selected route per target, converted-file links, thumbnail/render comparisons, accessibility status, loss table, macro/animation warnings, hashes, and gates.
- Exports: selected formats plus `md`, `json`; destination `output`; naming `<source-stem>-converted-<target>_{YYYY-MM-DD}`; language `en` for technical reports.
- Progress reports inspection, each target, reopen/round-trip, and export. Preview shows local vs cloud route, expected losses, data classification, cost, disk estimate, and no-overwrite target paths.
- References use `[FILE1 sha256:<prefix>]`, `[OUT:<format> sha256:<prefix>]`, and implementation-only `[ALG-FC-n §section]`; uncertainty is represented as a specific unverified/lost feature, never generic success.
- Degradation: `DEGRADED: cloud conversion was not used; targets unsupported by the local pipeline are reported as unavailable rather than silently approximated.`
- Deviations: outputs may be placed beside the source only when that path is approved; collision always gets `_v2`, `_v3`, etc.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-REDACT`, `SH-SEC-CRED`; add sensitive-class controls at runtime. Office macros, links, and embedded content are never executed.
- Required disclaimers: none at base R1. Material conversion loss is rendered as a blocking/acceptance finding, not an invented disclaimer ID; runtime domain disclaimers resolve under `SH-RISK-3`.
- Risk/data: base R1; sensitive inputs escalate. `irreversible_local` is prevented through no-overwrite/versioning.
- Gates: `reconciliation_survey`, `provenance_chain`, `mime_signature_match`, `macro_nonexecution`, `output_reopen`, `text_coverage`, `structure_coverage`, `accessibility_report`, `loss_disclosure`, `no_overwrite`, `round_trip_validation`, `artifact_disk_verification`; `citation_coverage` is `SKIPPED_NOT_APPLICABLE` unless standards claims are rendered.
- Validate plans/results schemas; target membership; hashes; file signatures; reopen success; page/slide counts; text and structural thresholds; links; fonts; tags/alt text; expected-loss coverage; source path unchanged.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Extension and sniffed MIME disagree | VALIDATION | Use sniffed type only after owner-visible warning; block unsafe mismatch | `BLOCKED: file extension and content type disagree.` |
| Macro-enabled input | POLICY | Preserve inertly where possible; never execute | `WARNING: macros were detected and were not executed; losses are listed.` |
| Local route unsupported, cloud denied | RESOURCE | Mark target unavailable | `DEGRADED: this target requires an unapproved/unavailable cloud converter.` |
| Output cannot reopen | VALIDATION | Delete only run-owned invalid temporary; block target export | `BLOCKED TARGET: converted output failed deterministic reopen validation.` |
| Destination exists | VALIDATION | Allocate next suffix | `NOTICE: existing file preserved; output written with version suffix.` |

- Metrics: `targets_requested`, `targets_succeeded`, `bytes_in`, `bytes_out`, `text_coverage_min`, `structure_coverage_min`, `render_similarity_min`, `features_lost`, `accessibility_failures`, `round_trip_matches`, `cloud_fallbacks`; ledger records route and consent.
- Tests: happy `tests/fixtures/wf-16/sample.docx`; degraded `tests/fixtures/wf-16/local-unsupported-cloud-denied.pptx`; safety `tests/fixtures/wf-16/macro-and-path-traversal.docm`; contracts `fs.read`, `doc.extract_text`, `doc.convert`, `image.transform`, `fs.write`; golden `tests/golden/WF-16/conversion-report.json`. Additional acceptance: source hash/path unchanged and every accepted target reopens.
- Deviations: none.

### WF-24 — Thumbnail creator

**Source ref:** `user-spec:WF-24` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 1 · **Domain family:** image-media  
**Risk tier:** R1 (factors: `image_rights`; runtime `image_identity` when a real person appears) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `MERGE_ALIAS` (matrix label `MERGE/ALIAS`) · canonical owner `skill:.agents/skills/imagegen#thumbnail-preset`  
· existing assets `skill:.agents/skills/imagegen`; `skill:.agents/skills/fal-ai-media`; `skill:.agents/skills/accurate-grok-imagine`; OpenAI/Grok are direct providers; `fal-ai` is absent/deferred  
· duplicate surfaces avoided `dedicated thumbnail skill/MCP`; `duplicate image-provider wrappers`  
· delta `Add aspect/text-safe-area/legibility preset, rights manifest, and platform-size validation.`  
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-24`; `.agents/skills/imagegen/SKILL.md`; `.agents/skills/fal-ai-media/SKILL.md`; `.agents/skills/accurate-grok-imagine/SKILL.md`; `.agents/skills-index.md`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md#WF-24`

#### 1. Purpose and user story
- The owner supplies a video or title/description and receives multiple thumbnail concepts and final variants whose visual hook, imagery, text overlay, safe areas, small-size readability, channel style, and rights/provenance are explicitly validated.
- User story: "As a video publisher, I want distinct, readable thumbnail variants derived from the actual video's promise so that I can select a compelling visual without misleading viewers or losing text at small sizes."
- Boundary: this workflow does not edit/publish the video, auto-upload the thumbnail, create generic product-photo scenes (`WF-13`), remove a background as the primary output (`WF-02`), or imitate another channel's protected identity.
- Routing: triggers `create thumbnails for this video`, `make YouTube thumbnail variants`, `derive a visual hook from this title`, `add readable thumbnail text`, `use my channel style`; negative triggers `product photo variants` → `WF-13`, `remove background` → `WF-02`, `create social posts` → `WF-14`; aliases `/thumbnail-create`, `/video-thumbnail`.
- Execution modes: `interactive` and `background`; owner selects finals. No upload/publish mode exists.
- Success criterion: each accepted variant communicates one evidence-consistent hook at a glance, passes target-platform size/aspect/safe-area constraints, remains legible at small preview sizes, and carries rights/source/provider provenance.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| `video_file` | file | no | supported local video; ≤4 GB; no execution | INTERNAL |
| `title` | string | conditionally | required if no video; 1–300 characters | INTERNAL |
| `description` | string | no | ≤10,000 characters | INTERNAL |
| `platform` | enum | yes | `youtube`, `vimeo`, `other` | PUBLIC |
| `channel_style` | file | no | image/PDF/MD style reference; ≤50 MB | INTERNAL |
| `source_images` | list<image> | no | ≤20; each ≤50 MB; rights required | INTERNAL; PII if people |
| `concept_count` | integer | no | 2–12 | PUBLIC | 4 |
| `variants_per_concept` | integer | no | 1–6 | PUBLIC | 2 |
| `overlay_text_max_words` | integer | no | 0–12 | PUBLIC | 6 |
| `face_policy` | enum | no | `none`, `owner_supplied_only`, `synthetic` | PUBLIC | `owner_supplied_only` |
| `rights_attestation` | enum | yes | `owner_created`, `licensed`, `authorized_use` | INTERNAL | — |
| `output_language` | enum | no | `ro`, `en`, `preserve` | PUBLIC | `preserve` |

- Preconditions: at least `video_file` or `title`; assets hash/decode; rights attested; `fs.read`, `image.analyze`, `image.generate`, `image.edit`, `image.transform`, `fs.write`, and official-guide `web.fetch` healthy; identity status resolved.
- Intensity:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 2 | 2 | 1 | 1 | 0 |
| medium | 0 | 3 | 3 | 3 | 1 | 1 |
| high | 0 | 5 | 5 | 5 | 2 | 2 |
| limitless | 0 | 8 | 8 | 5 | 2 | 3 |

- Budget: small `24 / 600 / 10`; medium `80 / 1,800 / 35`; high `220 / 3,600 / 90`; limitless `360 / 6,000 / 150`.
- Deviations: external sources are limited to official platform specifications and supplied rights/license records; creative breadth comes from concepts/variants.

#### 3. Data sources and knowledge bases
- Primary external authorities: YouTube Help's official custom-thumbnail guidance and current constraints `[TH-YT1 §heading]`; YouTube Community Guidelines for misleading/prohibited imagery when relevant `[TH-YT2 §heading]`; Vimeo Help thumbnail guidance `[TH-VM1 §heading]`; another platform's official documentation `[TH-PLAT1 §heading]`.
- Primary run sources: video/title/description `[VID1 t=hh:mm:ss]` or `[META title|description]`; owner channel guide `[CHANNEL §heading@<hash>]`; source image `[IMGn sha256:<prefix>]`; license `[LICn <document>@<hash>]`.
- `sources.min_tier: T0` for platform constraints and rights claims, `min_independent: 2` for contested rights, `recency_max_days: 30`; platform specs use a 7-day override.
- No domain-data. `memory.search` may retrieve approved channel-style decisions; `memory.capture: decisions` stores style constraints and preferred safe-area/text rules, never raw face embeddings or video content.
- Cache: `standard` for official platform docs, `fresh-only` for video frames, faces, and generated assets; channel guide invalidates on hash change.
- Paywall: not applicable.
- Deviations: official platform constraints require primary first-party docs.

#### 4. Tool chain and mechanisms
- Required: `web.fetch` retrieves current platform constraints; `fs.read` ingests/hashes video/images/style; `image.analyze` samples frames and extracts visual hooks/style; `llm.extract` derives promise, entities, and non-misleading hook candidates; `image.generate` creates new scene elements; `image.edit` composes source assets; `image.transform` applies exact aspect, text overlays, safe areas, contact sheets, and small-size render tests; `fs.write` exports.
- Optional: `memory.search` for approved channel style and a second image-generation adapter for diversity. Missing channel style yields: `DEGRADED: no approved channel style was available; variants use a neutral platform-safe visual system.`
- Provider hints: `imagegen` owns generation/editing; `fal-ai-media`/`accurate-grok-imagine` remain adapters. Text overlays should be rendered deterministically after image generation, not entrusted to generative text rendering.
- Mechanism: extract the video's/title's central promise and candidate visual moments; create concept cards with hook, composition, imagery, overlay text, and risk; generate/edit visual backgrounds; place deterministic text within measured safe areas; render actual-size and small-size previews; score contrast, OCR, text density, focal hierarchy, crop safety, content alignment, style match, and rights.
- Reuse note: alias routes into `imagegen` thumbnail preset; no new provider wrapper or thumbnail skill is created.

#### 5. Internal data structures / schemas
- `ThumbnailBrief`: `content_promise`, `platform`, `audience`, `channel_style_rules`, `allowed_assets`, `prohibited_implications`, `rights_records`.
- `ThumbnailConcept`: `concept_id`, `visual_hook`, `evidence_ref`, `composition`, `imagery_plan`, `overlay_text`, `safe_area`, `style_tokens`, `risk_flags`.
- `ThumbnailQA`: `variant_id`, `dimensions`, `aspect_ratio`, `safe_area_pass`, `small_preview_width_px`, `ocr_text`, `ocr_match`, `contrast_ratio`, `text_occupancy_ratio`, `focal_saliency`, `crop_pass`, `content_alignment`, `rights_pass`, `identity_pass`, `overall_pass`.
- Shared schemas: `RunContext`, `SourceRecord`, `Citation`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, `ReviewVerdict`.
- No shared extension. Artifacts: `concept_board` (`markdown`, required); `thumbnail_variants` (`png[]`, required); `thumbnail_contact_sheet` (`png`, required); `thumbnail_qa` (`json`, required); `rights_provenance_manifest` (`json`, required).
- Schema example:
```json
{"variant_id":"concept-02-v1","dimensions":[1280,720],"aspect_ratio":1.777778,"safe_area_pass":true,"small_preview_width_px":168,"ocr_text":"BUILD IT RIGHT","ocr_match":true,"contrast_ratio":6.8,"text_occupancy_ratio":0.18,"focal_saliency":0.74,"crop_pass":true,"content_alignment":"supported","rights_pass":true,"identity_pass":true,"overall_pass":true}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; concept and variant fan-out are bounded.
- Lifecycle: `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `ingest_thumbnail_inputs` (`discover`, `tool`, `fs.read`) → validates/hashes video, metadata, style, and image assets → emits source descriptor.
2. `fetch_platform_constraints` (`discover`, `tool`, `web.fetch`) → retrieves current official size/format/policy guidance → emits constraints.
3. `extract_content_promise` (`discover`, `tool`, `llm.extract`) → derives claims, entities, visual moments, and misleading-implication boundaries → emits `ThumbnailBrief`.
4. `sample_visuals` (`discover`, `tool`, `image.analyze`) → selects representative frames/assets and detects faces/logos/watermarks → emits candidates.
5. `rights_identity_gate` (`discover`, `gate`, none) → validates asset rights and real-person use → emits `SafetyDecision`.
6. `plan_concepts` (`plan`, `fanout`, none) → independent hook/composition/style lenses propose concepts → emits `ThumbnailConcept[]`.
7. `generate_visuals` (`execute`, `fanout`, `image.generate`) → creates permissible backgrounds/elements → emits generated assets.
8. `compose_variants` (`execute`, `fanout`, `image.edit`) → combines source/generated imagery while preserving allowed identities/logos → emits image candidates.
9. `render_text_safe_areas` (`execute`, `tool`, `image.transform`) → applies deterministic overlays, exact dimensions, and crops → emits PNG variants.
10. `thumbnail_qa` (`quality-review`, `tool`, `image.analyze`) → tests OCR, small-size readability, contrast, saliency, crop, alignment, rights, and identity → emits `ThumbnailQA[]`.
11. `reject_or_repair` (`quality-review`, `join`, none) → repairs text/layout or rejects visual drift up to bound → emits accepted variants.
12. `owner_select` (`acceptance`, `gate`, none) → owner chooses final candidates; no upload occurs → emits selection.
13. `export_thumbnails` (`capture`, `export`, `fs.write`) → writes and disk-verifies variants, board, QA, and manifest → emits `ArtifactManifest`.
- Fan-out: concept count then variants per concept; all join at QA. Repair changes one failed dimension only and is bounded by preset loops.
- Checkpoints after source/rights gate, concept board, each variant batch, QA join, selection, and export.
- Approval: `deterministic`, `human`; `human_required: 1`; `panel_required: false`. Rights, identity, misleading content, safe-area, or readability failure blocks affected variants.
- Resume: reuse current platform constraints within TTL, sampled frame hashes, accepted concepts, deterministic overlay outputs, and verified variants.

#### 7. Output format and UX behavior
- Owner sees concept cards first, then full-size and small-preview variants, overlay copy, hook rationale, source moment, channel-style fit, QA badges, rights/identity status, and selection controls.
- Exports: `png`, `webp`, `md`, `json`; destination `output`; naming `thumbnail-<title-slug>_{YYYY-MM-DD}`; language follows metadata.
- Preview shows platform, concept/variant counts, source assets, provider/model, rights/identity status, expected cost, target sizes, and any degraded channel-style/provider capability.
- Inline sources: `[TH-YT1 §heading]`, `[TH-YT2 §heading]`, `[TH-VM1 §heading]`, `[VID1 t=hh:mm:ss]`, `[META title|description]`, `[CHANNEL §heading@<hash>]`, `[IMGn sha256:<prefix>]`, `[LICn <document>@<hash>]`. Uncertainty includes ambiguous content promise and rights gaps.
- Degradation: `DEGRADED: no approved channel style was available; variants use a neutral platform-safe visual system.`
- Deviations: each final is always accompanied by a small-size preview and QA JSON.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-REDACT`, `SH-SEC-CRED`, `SH-SEC-IDENTITY`.
- Required disclaimers: none at base R1; runtime domain disclaimers resolve only under `SH-RISK-3`. `AI-generated` and `NOT UPLOADED` are provenance/UX labels, not invented disclaimer IDs.
- Risk/data: R1 `image_rights`; R2 `image_identity` for real people. Inputs/outputs `INTERNAL`; real-person images PII/P6 under D8.
- Gates: `reconciliation_survey`, `citation_coverage`, `provenance_chain`, `platform_constraint_current`, `rights_attestation`, `content_alignment`, `misleading_implication`, `safe_area`, `small_size_readability`, `overlay_ocr_match`, `contrast`, `dimensions_format`, `identity_consent`, `no_upload_action`, `artifact_disk_verification`.
- Validate schema; current platform bounds; exact output signature/dimensions/aspect; overlay text word count and OCR; contrast and occupancy thresholds; crop-safe bounding boxes; source-hook evidence; unique concepts; rights/provider/seed records.

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| No video/title | VALIDATION | Reject before generation | `FAILED: provide a video file or title.` |
| Rights/identity not confirmed | POLICY | Stop affected assets | `BLOCKED: image rights or real-person consent are unresolved.` |
| Platform rules stale | RESOURCE | Block final-size claim/export for that platform | `BLOCKED: current official thumbnail constraints could not be verified.` |
| Text unreadable at small size | VALIDATION | Repair layout/text; reject after bound | `REJECTED VARIANT: overlay text is not readable at preview size.` |
| Upload instruction appears | POLICY | No external action | `NO ACTION TAKEN: thumbnails were generated locally and not uploaded.` |

- Metrics: `concepts_requested`, `variants_generated`, `variants_passed`, `ocr_match_rate`, `contrast_min`, `safe_area_pass_rate`, `small_size_pass_rate`, `content_alignment_failures`, `rights_failures`, `identity_escalations`, `generation_cost_per_pass`; ledger records source moments, prompts, seeds, overlays, and selection.
- Tests: happy `tests/fixtures/wf-24/tutorial-video.mp4`; degraded `tests/fixtures/wf-24/no-channel-style.json`; safety `tests/fixtures/wf-24/unlicensed-face-and-autoupload.json`; contracts `web.fetch`, `fs.read`, `image.analyze`, `llm.extract`, `image.generate`, `image.edit`, `image.transform`, `fs.write`; golden `tests/golden/WF-24/thumbnail-qa.json`. Additional acceptance: every accepted thumbnail passes a real rasterized small-preview OCR/contrast test.
- Deviations: none.
