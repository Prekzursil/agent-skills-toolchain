# Lens 13 — User-domain and identity-aware leverage

**Date:** 29.08.2026  
**Mode:** discovery and deduplication only; no capability was installed, enabled, or connected.  
**Users:** Andrei Visalon and Marius “Miky” Visalon are separate people sharing one AI-tool
estate. Estate rules may be shared; personal facts, preferences, work context, learning history,
documents, and research must not cross profiles.

## Executive result

Eight capability deltas survive deduplication:

| Rank | Capability delta | Primary domain | REC | Maturity | Value × effort | Confidence |
|---:|---|---|---|---|---|---|
| 1 | Close identity propagation across Cursor, Fabric, Zotero, Anki, and Windows | profile selection | ADOPT, staged | native components mature; integration custom | very high × medium | high |
| 2 | IDS-based openBIM model assurance with BCF findings | civil engineering | ADOPT as local trial | final standard + established toolkit | very high × medium | high |
| 3 | Profile-separated Zotero evidence cabinet using its local API | documents/research | ADOPT | mature desktop workflow | very high × medium | high |
| 4 | Signed-document-safe Romanian OCR and PDF/A validation | documents/technical service | ADOPT as a fold | mature CLI toolchain | very high × low | high |
| 5 | Offline QGIS/QField inspection and defect dossier | civil engineering/technical service | TRIAL | mature field workflow | high × medium | medium-high |
| 6 | Evidence-to-retrieval learning queue with Anki FSRS | personal technical learning | ADOPT as a fold | mature scheduler/import path | high × low-medium | high |
| 7 | TED v3 procurement watchlists beside the planned legislation watchlist | technical service | ADOPT as a delta | official production API | high × low | high |
| 8 | Profile-and-domain attribution in the existing session rollup | session analytics | ADOPT as a small extension | custom, built on existing buses | high × low | high |

The best first wave is not another general agent framework. It is: make the active person explicit,
then add local document and domain workflows whose artifacts are stamped with that profile.

## Ground and dedup boundary

### Read directly

- `C:\Users\Prekzursil\AGENTS.md`, including the 27.08 estate locks and fail-closed verification
  doctrine.
- Fabric contexts `andrei-core.md`, `miky-core.md`, and `shared-harness.md`.
- `.agents\CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`, including its recovery addendum.
- Current-hunt lenses 06, 07, 09, 10, 11, 14, and 15.
- Relevant vault skills: `continuous-learning-v2`, `format-codex-sessions`,
  `codex-session-reunion`, `study-plan-psychology`, `doc`, `pdf`, `research-ops`, and
  `citation-mapping`.
- A targeted vault search found no existing skill text naming QField, IfcTester, buildingSMART,
  the TED Search API, OCRmyPDF, Zotero, or Anki.

`bd prime --work-type research --keywords ...` was unavailable in the installed CLI. The supported
`bd prime --full` completed successfully but emitted no project knowledge. This is a CLI/version
compatibility constraint, not evidence that no relevant knowledge exists.

### Already present or already found — not re-proposed

- The separate Andrei and Miky Fabric contexts already exist.
- Lens 09 F9 already found the shared-estate/single-owner defect and specified an identity map,
  estate/person scope tiers, exact-name matching, estate-only behavior for unknown users, and
  profile-filtered recall. This lens depends on F9; it does **not** create a second identity store.
- Lens 09 F8 and Lens 11 already specify content-free session analytics, denominators, outcomes,
  metrics, and local rollups. Lens 10 supplies their privacy/destination gate. This lens adds only
  the missing person/domain join.
- Browser automation already has a mandatory per-run choice among live-owner,
  agent-persistent, and agent-ephemeral profiles. That browser choice is orthogonal to the human
  profile and must never be used to infer who is present.
- Portal Legislativ SOAP monitoring and Docling ingest were selected on 27.08. The findings below
  add TED procurement and archival OCR; they do not relabel those earlier items as new.
- Institutional literature access, citation mapping, OA retrieval, DOCX creation, PDF rendering,
  and the `study-plan-psychology` planning skill already exist.
- No OpenTelemetry collector, Langfuse/LangSmith, second memory store, second orchestrator, new
  resident service, or generic database MCP is proposed.
- Offensive-security tools and workflows were excluded from search and recommendations.

## 1. Identity propagation closure

### Gap

The profile facts are now correctly separated in Fabric context files, but selecting a Fabric
context does not bind Cursor, session analytics, Zotero, Anki, or Windows storage to the same
person. Conversely, application “last used” state can silently reopen the other person’s profile.
The existing `continuous-learning-v2` design scopes instincts by project but still shows one global
`identity.json`; project isolation is not user isolation.

### Exact borrow actions

Use Lens 09 F9’s identity map as the **only** person resolver, then propagate its selected
`profile_id`:

1. Add two explicit launch entries, `Andrei` and `Miky`, that set a process-local active profile.
   No surname matching, behavioral inference, voice recognition, workspace guessing, or
   “last user wins”.
2. Fabric invocation mapping:
   - Andrei → `fabric --context shared-harness --context andrei-core`
   - Miky → `fabric --context shared-harness --context miky-core`
3. Create/activate distinct Cursor named profiles for Andrei and Miky. Keep the canonical shared
   rules and skills as shared pointers; user settings, extensions, UI state, and private history
   remain profile-specific. Display the active human profile in the status line.
4. Launch Zotero and Anki with their explicit profile flags, not their last-used defaults:
   `zotero.exe -p Andrei`, `zotero.exe -p Miky`, `anki.exe -p Andrei`, and
   `anki.exe -p Miky`.
5. Treat separate standard Windows accounts as the target privacy boundary. Microsoft documents
   that separate accounts provide separate settings, documents, and applications. Application
   profiles inside the current shared Windows account are an interim attribution control, not an
   OS security boundary.
6. Keep the human selector independent from the browser selector. A tuple such as
   `(person:miky, browser:agent-persistent)` is valid; neither component chooses the other.
7. Unknown/missing profile runs estate-only. Any personal memory write, Zotero write, Anki import,
   professional output default, or profile-specific analytic is blocked until selection.

### Privacy and acceptance

- Store opaque profile IDs in operational events; display names stay in the local identity map.
- Never expose one profile’s recent files, Zotero library, Anki review history, transcript
  snippets, or learned preferences to the other.
- Tests: Andrei receives no Miky job/title/language/research assumptions; Miky receives no Andrei
  assumptions; both retain estate locks; surname-only resolution fails; a profile mismatch blocks
  writes; unknown remains estate-only.
- Zotero has a critical same-Windows-user caveat: its Word plugin cannot be pointed to a specific
  simultaneous Zotero instance on Windows. Until separate OS accounts exist, allow only one Zotero
  instance and require an explicit profile preflight before Word citation work.

**Maturity:** Windows accounts and application profiles are mature; cross-tool propagation is an
estate-specific integration.  
**Value × effort:** very HIGH × MEDIUM.  
**Confidence:** HIGH on the gap and native profile capabilities; MEDIUM-HIGH on a shared-account
interim because application bugs cannot provide OS isolation.

**Authoritative sources**

- Microsoft, user accounts and compartmentalized files/settings:
  <https://support.microsoft.com/en-us/windows/security/identity-signin/manage-user-accounts-in-windows>
- Cursor, profile import/activation:
  <https://cursor.com/docs/configuration/migrations/vscode>
- VS Code, named profile CLI and profile-scoped settings:
  <https://code.visualstudio.com/docs/configure/profiles>
- Zotero, multiple profiles and specific-profile launch:
  <https://www.zotero.org/support/kb/multiple_profiles>
- Anki, profiles and `-p` launch:
  <https://docs.ankiweb.net/profiles.html> and <https://docs.ankiweb.net/files.html>

## 2. Local openBIM assurance: IDS → IFC validation → BCF findings

### Why this user/domain

Miky’s technical-service work can turn contractor/model requirements from prose and spreadsheets
into machine-checkable delivery rules. buildingSMART’s IDS 1.0 is a final standard for
computer-interpretable information requirements; IfcTester can validate IFC files and emit HTML,
JSON, ODS, or BCF reports. bSDD URIs provide stable class/property references.

### Exact borrow actions

Create one routed `openbim-assurance` workflow, not a BIM server:

1. Input manifest: active profile, project, IFC hash, IDS hash/version, expected IFC schema,
   requirement owner, and permitted output location.
2. Author or receive an IDS 1.0 file. Use bSDD identifiers for agreed classifications and
   properties when available.
3. Run IfcTester locally:
   `python -m ifctester requirements.ids model.ifc -r Html -o report.html`.
4. For coordination, emit BCF from the same validated result; for tabular review, emit ODS/JSON.
5. Preserve the original IFC and IDS. Reports are derivatives with hashes and timestamps; the
   workflow never “fixes” the model silently.
6. Start with three bounded templates: asset identifier completeness, maintainable-equipment
   property completeness, and required classification/property-set checks. Domain owners approve
   each requirement before enforcement.
7. Add synthetic pass/fail IFC+IDS fixtures from the official IDS test corpus and verify report
   generation before using a live project.

### Privacy and limits

- Building models and asset registers stay local by default; no upload to free models or cloud
  validators.
- BCF can reveal coordinates, viewpoints, element IDs, project names, and screenshots. Export only
  the issue subset required by the recipient.
- IDS verifies declared information requirements; it does not certify structural safety, code
  compliance, constructability, or correctness of engineering judgment.

**Maturity:** IDS 1.0 is a final buildingSMART standard; IfcOpenShell 0.8.5 documents a working
IfcTester CLI/library and BCF reporting.  
**Value × effort:** very HIGH × MEDIUM.  
**Confidence:** HIGH for technical feasibility; MEDIUM-HIGH for realized value until one real
handover/model use case is selected.

**Authoritative sources**

- buildingSMART, IDS 1.0:
  <https://www.buildingsmart.org/standards/bsi-standards/information-delivery-specification-ids/>
- buildingSMART, bSDD API:
  <https://technical.buildingsmart.org/services/bsdd/using-the-bsdd-api/>
- IfcOpenShell, IfcTester:
  <https://docs.ifcopenshell.org/ifctester.html>
- IfcOpenShell ecosystem and auxiliary standards:
  <https://docs.ifcopenshell.org/introduction.html>

## 3. Profile-separated Zotero evidence cabinet

### Gap

The estate retrieves literature and maps citations, but no durable bibliographic cabinet was found.
Zotero supplies dynamic Word bibliographies and a local API at `localhost:23119/api/` that works
offline without network rate limits. It also supports separate profiles and data directories.

### Exact borrow actions

1. Create separate `Andrei` and `Miky` Zotero profiles and verify that each points to a distinct
   data directory. Never share one sync account between them.
2. Add profile-specific desktop launchers; disallow implicit last-used-profile startup for
   evidence work.
3. Create a small `zotero-local-evidence` skill that calls the local API directly over loopback.
   Do not add an MCP server. Begin read-only: search items, collections, tags, notes, attachment
   metadata, and formatted citations.
4. For Miky, provide collections such as `Technical service`, `Standards`, `Legislation`, and
   project-specific evidence. For Andrei, create nothing from Miky’s taxonomy; Andrei chooses his
   own collections.
5. Every report citation keeps a Zotero item key plus DOI/URL and access date. DOCX generation uses
   Zotero’s Word plugin for dynamic citations and bibliography updates.
6. Gate all writes on `(active person == open Zotero profile)`. With one Windows account, close the
   other Zotero instance before Word work; the documented Windows plugin limitation makes this a
   hard preflight.
7. Keep a content-addressed, metadata-only evidence manifest beside each formal deliverable. PDF
   attachments remain in the selected profile’s data directory.

### Privacy and limits

- Local API traffic stays on loopback, but its key is profile-scoped and can authorize broad
  writes. Never print it, store it in Git, or place it in prompts.
- Sync remains per-user and opt-in. A single AnkiWeb-style shared account assumption must not be
  transferred to Zotero.
- Bibliographic metadata may be shareable; notes and attached PDFs may contain confidential or
  licensed material and remain local unless explicitly released.

**Maturity:** mature desktop/reference workflow; multiple profiles are officially supported but
documented as advanced configuration.  
**Value × effort:** very HIGH × MEDIUM.  
**Confidence:** HIGH.

**Authoritative sources**

- Zotero multiple profiles:
  <https://www.zotero.org/support/kb/multiple_profiles>
- Zotero multiple-instance and Windows Word-plugin caveat:
  <https://www.zotero.org/support/kb/multiple_instances>
- Zotero local API:
  <https://www.zotero.org/support/dev/web_api/v3/local_api>
- Zotero Word integration:
  <https://www.zotero.org/support/word_processor_integration>

## 4. Signed-document-safe Romanian OCR and PDF/A validation

### Gap

The existing `pdf` skill renders and extracts text but does not define OCR, Romanian language
handling, PDF/A archival validation, or signed-PDF stop rules. Docling is already selected for
structured ingest; OCRmyPDF is the missing scan-preparation layer.

### Exact borrow actions

Fold an `archival-ingest` branch into the existing `pdf` skill:

1. Preserve the source byte-for-byte and write a versioned derivative; never overwrite.
2. Preflight encryption and digital signatures. If signed, stop. Do not use
   `--invalidate-digital-signatures`.
3. For an unsigned Romanian/English scan, run a bounded local command such as:
   `ocrmypdf -l ron+eng --rotate-pages --deskew --output-type auto --jobs 1 input.pdf output_ocr.pdf`.
   The one-job default respects this machine’s RAM pressure; a measured project can raise it.
4. Run veraPDF independently and retain its validation result. `--output-type auto` may fall back
   to ordinary PDF if compliant PDF/A cannot be produced, so “command succeeded” is not a PDF/A
   claim.
5. Render and visually inspect sampled pages plus the first/last page; compare page count and
   source/derivative hashes.
6. Pass the searchable derivative to Docling or the existing evidence pipeline. The original is
   always the legal/evidentiary source.

### Privacy and limits

- OCR is entirely local; scanned contracts, correspondence, technical books, and personal
  documents never go to a cloud OCR service by default.
- OCR text is fallible, especially tables, stamps, handwriting, and low-quality scans. Quotations
  used in a formal report require page-image verification.
- PDF/A conversion can affect structure. Keep the original and record the conversion path.

**Maturity:** OCRmyPDF 17.10 documentation describes Tesseract OCR, PDF/A output, veraPDF
validation, Windows Tesseract discovery, and signed-document refusal.  
**Value × effort:** very HIGH × LOW.  
**Confidence:** HIGH.

**Authoritative sources**

- OCRmyPDF introduction and PDF/A behavior:
  <https://ocrmypdf.readthedocs.io/en/stable/introduction.html>
- OCRmyPDF advanced PDF/A path:
  <https://ocrmypdf.readthedocs.io/en/stable/advanced.html>
- OCRmyPDF digital-signature behavior:
  <https://ocrmypdf.readthedocs.io/en/latest/pdfsecurity.html>

## 5. Offline QGIS/QField inspection dossier

### Why this user/domain

A reusable mobile inspection project can capture defects, asset IDs, location, severity, notes,
photos, sketches, audio, and linked documents in one portable project. QField supports QGIS
attribute forms, attachments, relative paths, GeoPackage, and manual QFieldSync transfer, so cloud
sync is optional.

### Exact borrow actions

1. Build one synthetic template first: `asset`, `inspection`, `finding`, and `attachment` tables
   with UUID keys, controlled status/severity values, created/modified timestamps, and an opaque
   operator profile ID.
2. Store the QGIS project, GeoPackage, styles, and relative attachment directories inside one
   active-project folder.
3. Configure QField attachment widgets for photos/sketches/documents; use deterministic filenames
   derived from finding UUID and timestamp, not a person’s name.
4. Package with QFieldSync and transfer manually for the first trial. Do not require QFieldCloud
   or any new daemon.
5. On return, validate UUID uniqueness, required fields, attachment existence, geometry validity,
   and row counts before generating an XLSX/DOCX inspection report.
6. Trial on synthetic data, then on one bounded non-sensitive site walk. Only after acceptance
   should a real project schema or cloud synchronization be considered.

### Privacy and limits

- Site photos, GNSS coordinates, floor plans, access-control details, names, and signatures can be
  sensitive. Keep the first workflow local and transfer only the project package.
- EXIF and attachment paths can reveal location and device details. The release/export stage needs
  an explicit metadata policy.
- Do not reuse one operator’s incomplete form state or recent attachments in the other profile.

**Maturity:** QField’s current documentation supports the stated form, attachment, relative-path,
GeoPackage, and manual packaging workflow.  
**Value × effort:** HIGH × MEDIUM.  
**Confidence:** MEDIUM-HIGH; exact schema value depends on Miky’s inspection/asset process.

**Authoritative sources**

- QField attribute forms and attachment widgets:
  <https://docs.qfield.org/how-to/project-setup/attributes-form/>
- QField relative project paths:
  <https://docs.qfield.org/how-to/project-setup/data_source_and_project_paths/>
- QField GeoPackage and manual transfer:
  <https://docs.qfield.org/how-to/project-setup/storage/>

## 6. Evidence-to-retrieval learning queue with Anki FSRS

### Gap

`study-plan-psychology` specifies spacing and retrieval practice, but no concrete review engine or
identity-safe import path exists. Anki explicitly supports separate profiles for separate people,
UTF-8 text imports with headers, and FSRS scheduling optimized from each learner’s review history.

### Exact borrow actions

Fold one exporter reference into `study-plan-psychology`:

1. From a user-selected source, generate **candidate** atomic cards with fields:
   `Question`, `Answer`, `Source`, `Locator`, `Topic`, `Profile`, and deterministic `GUID`.
2. Write a UTF-8 TSV with Anki headers for columns, deck, notetype, and tags. Do not call Anki or
   import automatically.
3. Save the queue under the active person’s project/learning folder. The learner reviews,
   corrects, and explicitly imports it into the matching Anki profile.
4. Launch with `anki.exe -p Andrei` or `anki.exe -p Miky`; a mismatch between TSV profile and open
   Anki profile blocks import.
5. Enable and optimize FSRS separately inside each user profile. Never copy FSRS parameters or
   review history between Andrei and Miky.
6. Card generation favors worked examples, discriminations, failure modes, and “when would this
   not apply?” prompts over verbatim paragraphs.

### Privacy and limits

- Separate Anki profiles have separate collections/settings, while add-ons are shared. Review
  history is personal data and does not enter the general session ledger.
- Each profile needs its own AnkiWeb account if sync is enabled; the official manual warns that
  syncing multiple profiles to one account can overwrite data.
- Licensed standards and confidential project text are linked by locator; do not copy long source
  passages into cards or external models.

**Maturity:** Anki profiles and text import are mature; FSRS is supported across current Anki
clients and should be optimized from the learner’s own history.  
**Value × effort:** HIGH × LOW-MEDIUM.  
**Confidence:** HIGH.

**Authoritative sources**

- Anki profiles and sync warning:
  <https://docs.ankiweb.net/profiles.html>
- Anki FSRS:
  <https://docs.ankiweb.net/deck-options.html#fsrs>
- Anki text import headers:
  <https://docs.ankiweb.net/importing/text-files.html>

## 7. TED v3 procurement watchlists

### Gap and exact borrow action

The 27.08 queue selected an official Romanian legislation watchlist. Add a distinct procurement
adapter to the same future `technical-service-watchlists` umbrella:

1. Define profile-owned watchlists by CPV codes, NUTS/place of performance, buyer, notice type,
   and date window.
2. Query the official unauthenticated endpoint `POST /v3/notices/search` on demand or from the
   estate’s existing scheduler; do not add a service.
3. Store notice ID, publication date, buyer, title, CPV/NUTS, deadline, URL, query version, and
   response hash. Store no bidder/contact enrichment.
4. Deduplicate by notice ID plus version and emit a short Romanian digest only for Miky’s selected
   work profile. Andrei’s profile receives none of these watchlists unless he explicitly creates
   his own.
5. Treat TED as EU procurement coverage, not a complete replacement for Romanian SICAP/SEAP.

**Privacy:** published notice metadata is public, but saved watchlists reveal professional
interests. Keep queries and digests profile-scoped; do not export them to free models.  
**Maturity:** official production v3 Search API; published-notice search requires no key and v2
remains supported during transition.  
**Value × effort:** HIGH × LOW.  
**Confidence:** HIGH on the API; MEDIUM-HIGH on value pending the chosen CPV/NUTS watchlist.

**Authoritative sources**

- TED Search API:
  <https://docs.ted.europa.eu/api/latest/search.html>
- TED API lifecycle and authentication:
  <https://docs.ted.europa.eu/api/latest/index.html>
- TED search-field inventory:
  <https://docs.ted.europa.eu/ODS/latest/reuse/field-list.html>

## 8. Identity-safe domain attribution in existing session analytics

### Non-duplicate delta

Lens 11 already defines the event schema and rollup. Lens 09 already defines the active profile.
Join them without creating a dashboard or store:

1. Add `profile_id`, `profile_resolution=explicit|unknown`, and
   `domain_class=civil_engineering|technical_service|personal_learning|document_research|software|other`
   to the existing bounded event contract.
2. `profile_id` comes only from Lens 09’s resolver. It is never inferred from language, files,
   browsing, model behavior, or professional vocabulary.
3. Produce per-profile local rollups for verified completion, accepted-artifact rate,
   failure-to-rescue, rework, and time to accepted deliverable by domain class.
4. Cross-profile comparison is off. A combined estate view may show only operational totals with
   no person breakdown unless both users explicitly consent.
5. Never join AI session analytics to employee People Analytics, Zotero notes, Anki review
   history, browser history, or site-inspection operator records.
6. Keep unknown sessions in the denominator as `unknown`; do not assign them to Miky because his
   profile is more populated.

**Privacy:** metadata-only, local, opaque profile IDs, no raw prompts/tool output/project names or
absolute paths.  
**Maturity:** small custom extension over disk-verified existing plans; no new runtime.  
**Value × effort:** HIGH × LOW.  
**Confidence:** HIGH.

OpenTelemetry’s GenAI conventions are useful prior art for metadata such as model, duration, and
token use, and their current guidance leaves prompt/tool content off by default. However, Lens 11
already chose a local additive ledger schema and explicitly rejected an OTEL/Grafana stack. Borrow
no collector or second schema now. If interoperability is later required, add a read-only field
crosswalk at export time.

Sources:

- OpenTelemetry GenAI attributes and sensitive-content warning:
  <https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/>
- OpenTelemetry sensitive-data minimization:
  <https://opentelemetry.io/docs/security/handling-sensitive-data/>

## Recommended adoption sequence

1. **Identity first:** adopt Lens 09 F9 and this lens’s cross-tool propagation/selection tests.
   Nothing person-specific should land before this.
2. **Low-effort document win:** archival OCR/PDF-A branch, including the signed-document hard stop.
3. **Evidence spine:** separate Zotero profiles, one-instance Windows preflight, read-only local
   API skill.
4. **Domain trials:** one synthetic IDS/IFC validation and one synthetic QField inspection
   project.
5. **Learning:** reviewed Anki TSV export tied to the selected profile and Zotero/source locator.
6. **Monitoring:** one Miky-owned TED CPV/NUTS watchlist.
7. **Analytics last:** profile/domain fields in the existing rollup after the selector is
   mechanically trustworthy.

## Explicit rejects and cautions

| Item | Decision | Reason |
|---|---|---|
| Infer the active person from language, profession, files, or behavior | REJECT | High-confidence conflation risk; violates the user’s explicit separation rule |
| Treat a Cursor/Fabric/browser profile as an OS privacy boundary | REJECT | Application profiles do not isolate all files/processes under the shared Windows account |
| New Zotero/Anki/QGIS MCP servers | REJECT | Direct local CLI/API/library paths are sufficient; MCP registration adds permanent surface |
| Simultaneous Zotero profiles with Word on one Windows account | REJECT | Official Zotero documentation says Word cannot target a specific same-account instance |
| Cloud OCR or cloud BIM validation by default | REJECT | Technical models and documents are sensitive; mature local tools exist |
| Auto-import generated flashcards | REJECT | Wrong cards poison learning; human review is the quality gate |
| OTel collector, Langfuse, LangSmith, or another telemetry database | REJECT | Duplicates Lens 11 and violates the no-second-observability/no-daemon decisions |
| Re-propose Portal Legislativ, Docling, citation mapping, institutional access, or general session analytics | DEDUP | Already built, planned, or specified |
| Offensive-security capability | OUT OF SCOPE | Explicit user exclusion |

## Bottom line

The highest-leverage pattern is a **profile-stamped local evidence chain**:

`explicit person → domain input → local deterministic transform → hashed derivative → human review → profile-owned library/learning/output`.

That chain gives Miky civil-engineering and technical-service leverage without turning his
professional defaults into Andrei’s identity, and gives Andrei a clean technical-learning lane
without inheriting his father’s work context.

UNIT-COMPLETE: lens-13
