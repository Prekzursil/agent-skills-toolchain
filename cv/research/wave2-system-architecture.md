# Wave 2 — System architecture: one maintained source, every document

Owner: Andrei Mihai Visalon (Bucharest; BSc CS, University of Bucharest FMI 2022–2025; ORCID 0009-0001-8776-8498, zero works; GitHub Prekzursil; no CV exists yet; undocumented salaried + internship + freelance history to be extracted; three research outputs in flight).
Purposes served at once: (a) software/AI engineering applications in Romania, (b) MSc then PhD applications (Romanian dossiers, EU vacancies, US-style admissions), (c) a maintained master record with no active hunt.
Date: 2026-09-23. Host: Windows Server 2025 (OFFLOAD-W2025), Python 3.14.6 global, Node on PATH, no TeX, no persistent RenderCV install.

Labels used throughout: **VERIFIED** = read in a primary source or executed on this box (two independent origins where the sibling wave was the first). **INFERRED** = my design decision or reasoning on top of verified facts. **UNVERIFIED** = fewer than two independent sources. Confidence bands follow WEP (likely 55–80 %, very likely 80–90 %, almost certain 90–99 %).

Inputs this design is built on (all in this scratchpad unless noted): `wave2-multi-doc-system.md` (toolchain survey), `adv-check-zero-fab-lint.md`, `adv-check-cv-studio-rendercv.md`, `adversarial-check-render-path.md`, `adv-check-cv-studio-not-installed.md` (independent re-derivations), `wave2-history-extraction.md` (intake protocol + engagement-record schema), `wave2-academic-cv.md`, `wave2-ro-language-variant.md`, `wave2-romania-market.md`, `wave2-gap-closing.md`, the cv-studio skill source at `~/.claude/skills/cv-studio/` (792-line `cvstudio.py`, `SKILL.md`, `references/*`, `assets/sample-profile.yaml`), the installed RenderCV 2.8 wheel in `scratchpad/cvs-venv`, and one new probe run for this document (`scratchpad/arch-probe/`, §1.4).

Scope guard: general 2026 resume format/ATS mechanics, bullet language, portfolio surfaces, GitHub curation and the content-mining of his vault/GitHub/disk belong to the parallel wave and are referenced, not redone.

---

## 0. The answer in ten lines

1. **Verdict on cv-studio: EXTEND** — keep its data model (JSON Resume superset + `x_` honesty blocks), its gate philosophy (schema → zero-fab lint → render → text-layer self-check, `SUCCESS:`/`FAILED:` markers) and its engine (RenderCV/Typst). Replace three components (the lint, the self-check backend, the theme whitelist), add seven (views, sections passthrough, design/locale sidecars, letter typesetting, Romanian dossier generators, Europass emitter, release/verify), and fix two defects found on this box (PDF path resolution; `tailor` writing into the skill folder). Do not adopt as-is (it fails its own acceptance here) and do not replace (every surveyed alternative is worse on single-source, academic sections or toolchain weight).
2. **Toolchain, named:** private git repo `cv/` → `profile.yaml` (JSON Resume 1.0.0 superset) + `engagements/*.yaml` (intake records) + `publications.bib` → extended `cvstudio.py` (deterministic, no LLM inside) → **RenderCV 2.8 + Typst 0.15.0** (pinned, isolated venv) for every CV/resume PDF → the **`typst` Python wheel** (already a RenderCV dependency) for cover letters, SOP, memoriu, dossier lists and the UEFISCDI template → `pdfminer.six`/`pypdf` text-layer and structure gates → JSON Resume export → `linkedin.md` + diff (manual paste) → Europass HR-XML emitter with a mandatory import test → tagged releases with all outputs regenerated from the tag.
3. **One source, three fact layers:** facts (dates, titles, counterparties, numbers, verifiers) live in engagement records and `x_metrics`; prose (achievement notes, bullets, narratives) lives in `x_master`/`x_narratives` and must reference fact ids; presentation (section selection/order, theme, page size, language, heading set, personal-data policy) lives in `x_views` + design/locale sidecars. Nothing is hand-edited in an output.
4. **Zero-fabrication is fail-closed:** every bullet on every surface carries achievement ids; every digit-bearing token resolves to a metric tagged M or E; B/U provenance never renders as a number; inflation words ("led", "team", "we") require `team.size > 1` in the engagement record; Tier-B/C NDA engagements are name-scrubbed or excluded mechanically; the lint errors (not warns) when the banks are absent.
5. **Document matrix (17 outputs):** ATS resume EN (A4, 1–2 p) · ATS-AI variant · designed resume EN · RO modern CV · RO Europass-model CV (signed + anonymised copies) · international academic CV EN (2–3 p) · EU-vacancy academic CV (2 p) + cover letter · gap-free tabular CV (ETH/TUM) · UEFISCDI "CV and track record" (≤4 p, TNR 11) · FMI master dossier pack RO (achievements list + attachments index + thesis summary + oral deck) · UB doctoral pack RO (memoriu + lista lucrărilor + topic proposal skeleton) · cover letters EN/RO · SOP · LinkedIn text + diff · JSON Resume + academic site · platform paste packs (eJobs RO/EN, BestJobs, Hipo) · plaintext/DOCX fallbacks.
6. **Where Romania and ATS genuinely conflict** (photo, DOB/nationality/marital status, Europass layout, COR titles vs English titles, diacritics, page size, section order, signatures) the resolution is always the same: the conflict is a **view property**, stored once in the master with a scope tag, emitted only where the reader's rules require it, and never inside a PDF that a parser will read.
7. **The gate that proves an output is correct before it is sent** is not one gate but three that must all be green on the same tagged release: G2 (every fact traces), G4 (the PDF's extracted text contains exactly the facts the YAML says, in reading order, on the right page size and count, with embedded fonts and no legacy glyphs), and G6 (every output of the release agrees with every other on dates, titles, statuses, name form, ORCID). Plus one manual step that no gate replaces: a human reads the non-numeric claims.
8. **Tailoring never forks the design:** a target is an overlay (selection + order of existing achievement ids, a summary variant id, a keyword map, cover-letter facts) merged at build time onto a named view; if a JD needs a skill not in the bank, the bank grows with evidence first, the overlay never invents.
9. **Honest limits:** no LinkedIn write API; no proof of what Workday/Greenhouse/Taleo do; no proof of truth (only traceability); no PDF/UA or PDF/A; no native DOCX; Europass round-trip unproven; RenderCV cannot tag a PDF `/Lang ro`; the narrative documents (SOP, memoriu, topic proposal, career plan) are written by a human, only typeset and fact-linted here; the multi-week job is the intake of his undocumented history, which no tool shortens.
10. **Effort:** ~3–5 focused days of code (more than the sibling wave's 1–2 days, because this design adds ingest, dossier generators and the cross-document verify) versus weeks of content work; install first (15 min), lint second (it is the only gate that protects him from himself), everything else in the order of §7.

---

## 1. Toolchain and the cv-studio verdict

### 1.1 Component-by-component verdict (VERIFIED unless marked)

| Component of cv-studio | Observed on this box | Decision |
|---|---|---|
| Data model: `profile.yaml` = JSON Resume 1.0.0 superset + `x_master`/`x_metrics`/`x_targets`, `json` export strips `x_*` | Sound; matches the 2026 field convergence (career-ops, yamlresume, ndf14685 resume-as-code, RenderCV's own "resume as code") | **ADOPT**, extend with the blocks in §2 |
| Engine: RenderCV (YAML → Typst → tagged single-column PDF) | RenderCV 2.8 + typst 0.15.0 wheel installed in `scratchpad/cvs-venv` in ~31 s; renders the sample in ~2 s; `--design.page.size a4` works; `harvard` renders when called directly; deterministic output | **ADOPT**, pin `rendercv==2.8`, `typst==0.15.0` |
| Install location `~/.local/share/cv-studio/venv` | Absent; `CV_STUDIO_RENDERCV` unset; not on PATH/uv/pipx (`pipx list` itself is broken here); `cvstudio.py build` → `FAILED: rendercv engine not found` (exit 3). The session venv is ephemeral | **DO step A first** (run `setup.ps1`, add `pdfminer.six`) |
| Gate 4 self-check backend: PyMuPDF | `import fitz` → `DLL load failed while importing _extra` in the venv and in global Python; root cause isolated to **`msvcp140.dll` absent** (vcruntime140/vcruntime140_1 are shipped by python.org Python and resolve; an isolation test with only msvcp140.dll made PyMuPDF work); no VC++ 2015–2022 x64 redistributable installed | **REPLACE** with pure-Python `pdfminer.six` (primary) + `pypdf` (structure/fonts/MediaBox); keep PyMuPDF optional. Pure-Python extraction is also closer to what parsers do |
| Zero-fab lint | Fails **open**: with no `x_metrics` block, `if haystack and …` short-circuits and fabricated figures pass with 0 warnings; with no `x_master`, the role-bank warning is silenced; only `work[].highlights` are scanned (projects, education, volunteer, summary, project description all unscanned); comma-grouped 4-digit values (2,024) are swallowed as years; warnings never change the exit code | **REWRITE** as a fail-closed provenance gate (§4 G2) |
| Theme whitelist `KNOWN_THEMES` (5) | Blocks `harvard`, `ink`, `opal`, `ember` (added in 2.8; 9 themes available at runtime) | **REPLACE** with runtime discovery from the installed package |
| Design passthrough | Emits only `{design: {theme}}`; RenderCV default page is `us-letter` (`classic_theme.py:33`); rendered sample MediaBox 612×792; the skill's own `regional-formats.md` tells the user to set A4 but the script offers no way | **ADD** `-d` design sidecars per view, A4 default |
| Locale | RenderCV 2.8: English + 21 locales, none Romanian; `language` is a closed enum (`romanian` rejected), strings are overridable; `-lc` sidecar and `--locale.X` crash with `KeyError: 'locale'` when the input YAML has no `locale:` block (cv-studio's emitted YAML has none) | **ADD** a `locale:` block to every emitted YAML + `locale/ro.yaml` catalog (probe-verified, §1.4) |
| Arbitrary sections | RenderCV `cv.sections` is `dict[str, Section]` with entry types Bullet/Education/Experience/Normal/Numbered/OneLine/Publication/ReversedNumbered/Text, auto-detected by characteristic fields; `PublicationEntry` = title, authors[], summary, doi, url, journal, date; cv-studio maps only the fixed JSON Resume blocks | **ADD** `x_sections` passthrough + academic mappers |
| Cover letters | Markdown only; upstream RenderCV refuses letters (discussion #24, still open 2026-08-30) | **ADD** a Typst letter template compiled through the `typst` wheel |
| LinkedIn | Guidance only; correct that no write API exists | **KEEP** posture; add `linkedin.md` + release diff |
| `tailor` | Unigram frequency matcher; flags `acme`, `art`, `ci` as "missing"; default `--out` writes `tailor-report.md` **into the profile's directory** (the sibling check had to delete one from the skill folder) | **KEEP** as a checklist, fix default output dir, add phrase matching |
| Render invocation | `-pdf <bare name>` is resolved **relative to the input YAML's directory**, not `--out` — my probe (§1.4) left `probe_ats_ro.pdf` in `adv-skel/`; cvstudio.py masks this with a `glob("*.pdf")` fallback that only works when RenderCV's default name coincides | **FIX**: pass an absolute `-pdf` path |
| Console | Non-quiet runs raise `UnicodeEncodeError` on U+2713 unless `PYTHONIOENCODING=utf-8` | **FIX** in the wrapper's environment |
| Dependency isolation | `rendercv[full]` needs `typer>=0.24.1`; global `docling 2.84.0` pins `typer<0.22.0` | **KEEP** the isolated venv; never `pip install rendercv` globally |
| Three byte-identical copies of the skill (`~/.agents/skills` junction → `C:\suite\payload`, `~/.claude/skills`, `~/source/agent-skills-toolchain/skills`) | One source of truth in practice, three on disk | Edit the toolchain copy, redeploy with the skill-tree sync; never patch a copy in place |

Why not replace: JSON Resume themes need Node + Chromium and have no academic sections (no talks/teaching/grants/service; publications lack DOI/authors); LaTeX classes need a TeX distribution absent here and are one `.tex` per document; Typst CV packages (brilliant-cv, modern-cv, modernpro-cv, basic-resume) are hand-written documents (single-source breaks) and brilliant-cv's hidden keyword layer is a practice its own docs warn is penalised; yamlresume needs Node 22 + XeTeX; Reactive Resume is a GUI with its own data model (second source of truth); career-ops has prompt-only anti-fabrication. RenderCV is the only engine surveyed that gives tagged single-column PDF, PublicationEntry, arbitrary sections, per-file design/locale sidecars and nine themes from one YAML with zero native toolchain (all VERIFIED in `wave2-multi-doc-system.md` §2).

### 1.2 The named toolchain

```
cv/  (private git repo; secrets-free; evidence with client data kept outside git or git-crypt'ed)
│
├─ profile.yaml            JSON Resume 1.0.0 core + x_* blocks (§2)           ← the one maintained source
├─ engagements/eng-*.yaml  intake records (history-extraction schema, §2.3)   ← facts about work history
├─ publications.bib        BibTeX (or Hayagriva YAML) for every output        ← facts about research outputs
├─ evidence/index.md       artifact index (what proves what; confidentiality) ← Session-0 harvest
├─ narratives/*.md         SOP, memoriu, career plan, cover hooks (human-written, fact-linted)
├─ views/*.yaml            named views (§3) — selection/order/language/policy
├─ design/*.yaml           RenderCV -d sidecars (ats, designed, academic, ro, letter tokens)
├─ locale/{en,ro}.yaml     RenderCV -lc sidecars (Romanian catalog probe-verified)
├─ templates/*.typ         letter.typ, sop.typ, dossier-list.typ, memoriu.typ, uefiscdi.typ
├─ targets/<id>/           jd.md (snapshot), overlay.yaml, sent.json (§5)
├─ tools/                  cvstudio.py (extended), ingest.py, bib2entries.py, europass.py,
│                          linkedin_diff.py, verify.py, letter.py, dossier.py
└─ dist/<tag>/             every regenerated output of a release, committed
```

Engines and pins (VERIFIED versions on this box): Python 3.14.6 for the wrapper (needs only a YAML parser: `ruamel.yaml` in the venv, `pyyaml` fallback); isolated venv `~/.local/share/cv-studio/venv` with `rendercv==2.8`, `typst==0.15.0` (cp38-abi3 wheel, no Rust toolchain), `pdfminer.six==20260107`, `pypdf` (add), `bibtexparser` (add), optional `pymupdf==1.28.2` only after the VC++ 2015–2022 x64 redistributable is installed. Node (present) only for the optional `resumed` HTML render. No TeX anywhere.

Deterministic wrapper, LLM outside: exactly as cv-studio's SKILL.md says, the scripts map, render, lint and check; the bullets, narratives and letters are written by the owner or an LLM session and then pass through the same gates. The LLM never gets write access to fact fields.

### 1.3 What each engine is used for

| Output family | Engine | Why this one |
|---|---|---|
| Every CV/resume PDF (ATS, designed, academic, RO modern, tabular) | RenderCV 2.8 → Typst | one engine, one drift surface; single-column themes; A4/Letter per view; tagged PDF; 9 themes; `.typ`/`.md`/`.html` by-products for audit and for the plaintext/DOCX fallbacks |
| Cover letter, SOP, memoriu, dossier lists, UEFISCDI CV | `typst.compile()` on small templates | RenderCV refuses letters upstream; the `typst` wheel is already installed; templates share the CV theme's font/colour tokens; UEFISCDI's fixed typography (A4, Times New Roman 11 pt, 1.15 spacing, 2 cm margins — VERIFIED in the TE 2026 package) is trivial in Typst and impossible to guarantee in RenderCV themes |
| Europass-model CV | Official editor XML round-trip, seeded by `europass.py` (HR-XML 3 Candidate) | "curriculum vitae, model comun european" is a legal term (HG 1336/2022 art. 35(1)(i); HG 611/2008 art. 49(1)(b)); a look-alike is not compliant; the only known JSON→XML mapper (J0ker98/europass-cv, 2 commits) is unproven → mandatory import test, manual fallback |
| HTML site / JSON | `cvstudio.py json` → `resumed` + single-column theme (optional) | portability escape hatch; academic GitHub Pages site recommended by Harchol-Balter and Nguyen |
| LinkedIn, eJobs, BestJobs, Hipo | Text packs (`.md`) + diffs | no write APIs; eJobs/Hipo are structured forms, BestJobs takes the PDF |
| Plaintext / DOCX fallback | RenderCV's Markdown by-product → `.txt`; `pandoc` → `.docx` on demand | second engine, drift risk, only when a portal demands it |

### 1.4 New evidence produced for this document (VERIFIED, 2026-09-23, `scratchpad/arch-probe/`)

Render of RenderCV's own 2.8 skeleton (`adv-skel/Probe_Skel_CV.yaml`) with the two sidecars this architecture prescribes:

- `design-ats.yaml`: `theme: engineeringresumes`, `page.size: a4`, `page.show_footer: false`, `page.show_top_note: false`, `typography.alignment: justified-with-no-hyphenation`, `links.show_external_link_icon: false`, `header.connections.{show_icons: false, display_urls_instead_of_usernames: true, hyperlink: true}`, `sections.show_time_spans_in: []` → all accepted; generated Typst carries `page-size: "a4"`, `header-connections-show-icons: false`, `header-connections-display-urls-instead-of-usernames: true`; PDF MediaBox `595.2756 × 841.8898` (A4); extracted text contains `linkedin.com/in/` and `github.com/` **as visible text** (the ATS rule "URLs visible as text, no icons"), the name, the e-mail and every institution.
- `locale-ro.yaml` (the catalog in §2.7): accepted under `language: english`; `.typ` shows `iun. 2023 – prezent`, `ian. 2023 – prezent`; extracted text contains `prezent`; **`/Lang` remains `(en)`** — the known RenderCV limitation (closed language enum) is confirmed again; the `justified-with-no-hyphenation` alignment is the mitigation for Romanian text under English hyphenation.
- Render time 1.5 s; exit 0; pdfminer text length 4,654 chars; 3 pages (the skeleton is long — a page-count gate would correctly flag this for a 2-page view).
- Defect found: `-pdf probe_ats_ro.pdf` (bare name) wrote the PDF into `adv-skel/` (the input's folder) and nothing into `--out`; an absolute `-pdf` path fixed it. cvstudio.py passes `pdf.name` and would have silently picked up a wrong file via its glob fallback or reported a missing PDF.

---

## 2. The source of truth: schema

### 2.1 Design rules (INFERRED, each tied to a verified constraint)

1. **Strict JSON Resume superset.** Every non-`x_` key validates against JSON Resume 1.0.0 so `cvstudio.py json` always yields a portable file (VERIFIED: schema has `basics, work, education, skills, projects, publications, awards, certificates, languages, volunteer, interests, references`; no academic sections; publications lack DOI/authors — hence the extensions).
2. **Facts are generated, prose is written, presentation is configured.** `work[]` dates/titles/counterparties are generated from engagement records by `ingest` and locked (the lint errors if a `work[i]` fact differs from its `engagement:`); bullets are written by hand/LLM but must cite ids; views/sidecars decide what is shown.
3. **Provenance is a first-class field**, not a comment: every metric carries the M/E(enum)/E(rate)/E(delta)/B/U tag and "how known" sentence from the numbers ladder (`wave2-history-extraction.md` §9, §12); every date carries `sure|doubtful` and its evidence id.
4. **Personal data is scoped.** Fields that only Romanian/Europass readers may see carry `scope: ro_only`; CNP/ID numbers are never stored in the profile at all (Law 190/2018 art. 4 and the market wave's rule: never before an offer).
5. **Publications have their own source** (`publications.bib`) and a status machine; the CV never retypes them and never hand-types a status label.
6. **Identity is written once.** Legal form (from the CI), display ASCII form, hyphenation, ORCID, GitHub, LinkedIn, e-mails; renderers print the same thing everywhere.

### 2.2 `profile.yaml` — annotated skeleton

```yaml
# ---- JSON Resume 1.0.0 core (portable; exported by `json`) -------------------
basics:
  name: Andrei Mihai Visalon              # = x_identity.display_name (lint-enforced)
  label: AI/Software Engineer — agent infrastructure, MCP servers, local-first AI tooling   # headline; per-view overrides come from x_identity.headlines
  email: prekzursil1993@gmail.com         # views choose institutional vs personal (x_identity.emails)
  url: https://<github-pages-site>        # academic site once built
  summary: >-                             # a summary VARIANT id is selected per view/target (x_narratives.summaries)
    ...
  location: {city: Bucharest, countryCode: RO}   # city only; no street address anywhere
  profiles:
    - {network: GitHub,   username: Prekzursil}
    - {network: LinkedIn, username: andrei-mihai-visalon-03141b170}
    - {network: ORCID,    username: 0009-0001-8776-8498}
work:                                     # GENERATED by `ingest` from engagements/*.yaml; bullets hand-written
  - name: "<Counterparty or generic descriptor>"    # Tier-B: "Bucharest fintech startup (~15 staff; name withheld under NDA)"
    position: "<title_resume>"
    location: Bucharest, RO
    startDate: 2024-03
    endDate: 2024-07
    x_engagement: eng-2024-03-acme        # link to the fact record (lint: dates/title/name must match)
    x_titles: {title_en: Backend Developer, title_ro_contract: Programator, cor_code: "251202", title_ro_display: Dezvoltator backend}
    highlights:
      - text: "Built ... (~3 months, sole engineer)"
        text_ro: "..."                    # parallel Romanian text, translated once, reviewed
        from: [ach-acme-01, ach-acme-02]  # REQUIRED: achievement ids in x_master
        metrics: [met-acme-01]            # REQUIRED for every digit-bearing token
        views: [ats, designed, ro]        # optional restriction
education:
  - institution: University of Bucharest, Faculty of Mathematics and Computer Science
    area: Computer Science
    studyType: BSc
    startDate: 2022-10
    endDate: 2025-07
    score: "<general average>"            # rendered only where the view allows (FMI dossier, EU MSc)
    x_academic: {thesis_title: "...", thesis_supervisor: "...", thesis_grade: "...", ects: 180, cohort_rank_pct: null, english_semesters: null}
skills: [...]                             # keyword-literal categories (Python, SQL, Azure/AWS literally present — market wave A4)
projects:                                 # 3–5 curated; each may carry a research block for academic views
  - name: grace-iberlef-2026
    url: https://github.com/Prekzursil/grace-iberlef-2026
    description: "..."
    highlights: [{text: "...", from: [ach-grace-01], metrics: [met-grace-01]}]
    x_research: {question: "...", method: "...", result: "...", limitation: "...", artifact_doi: null, witness: null}
    x_output: out-grace-report            # link to x_outputs (status machine)
publications: []                          # GENERATED from publications.bib by `bib2entries` (never hand-typed)
languages:
  - {language: Romanian, fluency: Native}          # CEFR strings rendered per view ("Engleză – C1")
  - {language: English,  fluency: C1, x_certificate: null}   # B2+ certificate id once obtained (FMI English tracks)
awards: []
certificates: []
volunteer: []

# ---- x_ extensions (stripped by `json`; consumed by the gates) ----------------
x_identity:
  legal_name: {family: "VISALON", given: "ANDREI-MIHAI", source: "CI read on <date>", diacritics: false}   # UNVERIFIED until the CI is read
  display_name: Andrei Mihai Visalon           # ASCII, every English/web surface, every byline
  aka: [Andrei-Mihai Visalon, A. M. Visalon]   # mirror into ORCID "Also known as"
  orcid: 0009-0001-8776-8498
  orcid_registered_name: "Andrei Visalon"      # lint warns until it equals display_name (VERIFIED mismatch today)
  emails: {institutional: andrei-mihai.visalon@s.unibuc.ro, personal: prekzursil1993@gmail.com}
  headlines: {ats: "...", ai: "...", academic: null, ro: "..."}      # the only allowed headline strings
  ro_only:                                     # scope: ro_only — emitted ONLY by views with include_personal_data: true
    date_of_birth: null
    nationality: Română
    photo: assets/photo.jpg                    # optional; never in a parsed PDF
  never_stored: [CNP, ID series/number, marital status]   # documented refusal; asked only at contract stage

x_master:                                      # achievement bank — the ONLY sanctioned bullet source
  "Acme|Backend Developer":                    # key = "<work.name>|<work.position>" (kept for compatibility)
    - id: ach-acme-01
      engagement: eng-2024-03-acme
      event: ev-acme-high-1                    # BEI event in the engagement record
      text: >-
        Long-form note: situation, what he did, outcome (facts + provenance).
      nda_tier: B
      verifier: ver-acme-founder
      claims: {sole_engineer: true, team_size: 1}

x_metrics:                                     # verified figures ONLY; objects, not bare strings
  - {id: met-acme-01, value: "~3 months", tag: "E(rate)", how_known: "first invoice 2024-03-14 to hand-over 2024-07-02", evidence: [inv-2024-03-14, mail-2024-07-02], engagement: eng-2024-03-acme}
  - {id: met-grace-01, value: "27 runs", tag: M, how_known: "sweep manifest in repo", evidence: [repo-grace-manifest]}

x_outputs:                                     # research outputs with a status machine (§2.5)
  - {id: out-grace-report, bib_key: visalon2026grace, kind: technical_report, status: in_preparation, stage_note: "10-page internal report exists; CEUR window closed 2026-05-24", expected: 2026-11, venue_class: technical_report, doi: null, counts_for_fmi_dossier: false, orcid_synced: false}
  - {id: out-phenibut, bib_key: visalon2026phenibut, kind: manuscript, status: in_preparation, stage_note: "computational pharmacology; draft status <owner to fill>", expected: null, venue_class: null, doi: null}
  - {id: out-faers, bib_key: visalon2026faers, kind: manuscript, status: in_preparation, stage_note: "READUS-PV-compliant disproportionality study; draft status <owner to fill>", expected: null}

x_academic:                                    # sections JSON Resume lacks
  presentations: []                            # {title, event, date, kind: talk|poster, proof}  → FMI +0.25 "comunicări"
  research_internships: []                     # {host, supervisor, dates, certificate} → FMI +0.25 "stagii"
  scholarships: []                             # competitive only → FMI +0.25
  competitions: []
  teaching: []
  service: []                                  # reviewing, organising
  memberships: []
  software: []                                 # {name, repo, concept_doi, version_doi, citation_cff: true}
  narrative_cv: null                           # UEFISCDI "Narrative CV" paragraph id in x_narratives
  track_record: []                             # ranked ≤10 output ids (UEFISCDI)

x_evidence:                                    # artifact index (mirrors evidence/index.md)
  - {id: inv-2024-03-14, kind: invoice, proves: [eng-2024-03-acme.dates.start], confidential: true, location: "evidence/ (outside git)"}

x_narratives:                                  # human-written text blocks; fact-linted like bullets
  summaries: {ats: {text: "...", from: [...]}, ai: {...}, academic: null, ro: {...}}
  sop_direction: {text: "...", from: [...]}    # one research direction, what he already did
  memoriu_outline: {text: "...", from: [...]}
  career_plan_ubb: {text: "...", from: [...]}
  cover_hooks: []                              # per-company hooks referencing achievement ids

x_views: {}                                    # §3.3 — or one file per view under views/
x_targets: []                                  # §5 — or one folder per target under targets/
x_release: {version: null, date: null, linkedin_pasted: null, europass_imported: null, notes: null}
```

Backward compatibility: bare strings remain legal in `highlights[]` and `x_metrics[]` only while the profile is in `mode: draft`; `mode: release` requires the object forms. (INFERRED design choice, keeps the sample profile usable during migration.)

### 2.3 Engagement records — the upstream fact source

`engagements/eng-*.yaml` uses the schema delivered in `wave2-history-extraction.md` §12 unchanged (type incl. legal wrapper `salaried | internship_law176 | practice_law258 | volunteering_law78 | freelance_pfa | freelance_drepturi_autor | platform | informal | unpaid`; `counterparty{name, disclosure_tier A|B|C, generic_descriptor, industry, size_marker, geography}`; `dates{start, end, confidence, evidence[]}`; `hours_per_week{value, tag}`; `role{as_hired, actual, title_formal, title_resume}`; `team{size, your_share, reported_to}`; `ownership`; `routine`; `stack{claimable, exposure_only}`; `events[]` with the five BEI probes and per-event `numbers[]`; `outcomes`; `numbers_table`; `verifiers[]` with `status reachable-consented|reachable-not-asked|lost|artifact-only`; `nda{exists, covers, sunset, copy_held}`; `representation{on_resume, on_academic_cv, omitted_reason}`; `interview_prep`; `provenance_log`).

`ingest.py` (new) is mechanical: it creates/updates one `work[]` entry per engagement with `representation.on_resume: true`, using `title_resume`, `title_formal` → `x_titles`, the counterparty name or generic descriptor by tier, month dates (year-only when `confidence: doubtful` — the reconciliation rule), and writes an **empty** `x_master` bank keyed for that role plus skeleton `x_metrics` from the engagement's `numbers_table` filtered to tags M/E. Bullets are never generated. Re-running `ingest` is idempotent and never overwrites hand-written text.

Rules carried from the intake protocol into the lint: internships are titled "Intern" (never upgraded); the Romanian COR title is stored per role because REGES extracts and adeverințe will state it (VERIFIED: Codul muncii art. 17(3)(d)); overlapping freelance work may be grouped under one umbrella entry ("Independent software developer, YYYY–present") with client sub-entries — the umbrella is a `work[]` entry whose `x_engagement` is a list.

### 2.4 Why the engineering resume and the academic CV need different fields

| Need | Engineering resume | Academic CV | Where it lives |
|---|---|---|---|
| Headline/summary | yes, keyword-rich | none (UNC TIBBS, Nature; VERIFIED) | `x_identity.headlines`, `x_narratives.summaries`; view decides |
| Work history | reverse-chronological, XYZ bullets, scope statements | dated tabular entries, no persuasion; industry dates valued by some adcoms (Bowman) | `work[]` + `x_engagement` |
| Projects | product bullets, stars/users | research entries: question → method → result → limitation → artifact/DOI → witness (academic wave Claim 5.3) | `projects[].x_research` |
| Publications | one line if any | status-labelled subsections, APA 7 §10.8 descriptors, no target journal for in-prep | `publications.bib` + `x_outputs` status machine |
| Presentations, research internships, scholarships, competitions | rarely | +0.25 each on the FMI master dossier with proof (VERIFIED, FMI methodology) | `x_academic.*` with `proof` ids |
| Software | GitHub links | Software works with Zenodo DOIs, `CITATION.cff` carrying the ORCID | `x_academic.software` |
| Skills | high in the order, literal tool names | short, folded into research descriptions | view section order + `skills[]` |
| Personal data | none | none internationally; Europass fields for RO dossiers | `x_identity.ro_only` (scoped) |
| Referees | none | 2 (EU vacancy) / 3 letters (US) | `verifiers[]` with `reachable-consented` |
| Narrative | none | SOP / cover letter / memoriu | `x_narratives` |
| Track record | none | ≤10 ranked outputs + narrative CV (UEFISCDI) | `x_academic.track_record`, `narrative_cv` |

### 2.5 Publications: the status machine (VERIFIED conventions → INFERRED encoding)

`status ∈ {in_preparation, preprint, submitted, accepted, published, presented}`; `venue_class ∈ {peer_reviewed_journal, peer_reviewed_conference, workshop_ceur, technical_report, preprint_server, thesis}`; `kind ∈ {manuscript, system_paper, technical_report, software, dataset, talk, poster}`.

Rendering rules encoded in `bib2entries.py`, never typed by hand:
- `in_preparation` → `[Manuscript in preparation; <stage_note>; expected <month>]`, `journal` field **must be empty** (lint error otherwise); affiliation appended (APA 7 §10.8).
- `submitted` → `[Manuscript submitted for publication]`, journal **must be empty**.
- `preprint` → `[Preprint, not peer-reviewed]` + DOI required; listed under "Preprints".
- `accepted` → treated as published for listing purposes (academic wave Claim 2.1 sources), venue named.
- `published` + `workshop_ceur` → `[System description paper, <event> proceedings, CEUR-WS.org, Vol-<n>]` with team rank if any; never called a journal article; carries `cnatdcu_category: D` so a Romanian reader can classify it.
- `technical_report` → `[Technical report, arXiv:<id> / Zenodo DOI]`.
- Subsections emitted in this fixed order: Peer-reviewed · Shared-task / workshop papers · Preprints (not peer-reviewed) · Technical reports · Manuscripts in preparation. Empty subsections are omitted; the CV never prints a publication count.
- `counts_for_fmi_dossier` is set by the owner only after written confirmation from the FMI secretariat (the +0.25 eligibility of a CEUR paper is committee discretion — CONTESTED in the academic wave).
- `orcid_synced` flips when the DOI appears on the ORCID record (DataCite auto-update must be enabled before the first Zenodo release; it is not retroactive — VERIFIED).

The GRACE/IberLEF 2026 case is encoded honestly: the working-notes window closed (paper 24 May 2026; likely no system paper was filed, ~70 % per the gap-closing wave), so its `x_outputs` entry is a `technical_report` in preparation, and the SemEval-2027/IberLEF-2027 entries appear only when they exist.

### 2.6 Identity block and name policy (from the RO-language wave, VERIFIED facts, INFERRED rules)

- `display_name` (ASCII "Andrei Mihai Visalon") on every English and web surface, every byline, LinkedIn, GitHub and — after the fix — ORCID.
- `legal_name` exactly as the CI prints it (hyphen and diacritic status UNVERIFIED until read; his 1993 record predates HG 64/2011's no-hyphen rule) on Europass, dossiers, notarised items, grants.
- Lint: `basics.name == display_name`; RO legal-form views substitute `legal_name`; `orcid_registered_name != display_name` → warning with the fix instruction (add "Mihai"; add Also-known-as variants) until resolved.
- Romanian text uses comma-below code points (U+0218/0219, U+021A/021B); the RO render gate counts cedilla glyphs (U+015E/015F/0162/0163) and fails on any.

### 2.7 Romanian locale catalog (probe-verified strings; INFERRED wording, owner to review)

```yaml
locale:
  language: english            # closed enum; Romanian strings ride on the English tag (VERIFIED limitation)
  last_updated: Actualizat la
  month: lună
  months: luni
  year: an
  years: ani
  present: prezent
  phrases: {degree_with_area: DEGREE în AREA}
  month_abbreviations: [ian., feb., mar., apr., mai, iun., iul., aug., sept., oct., nov., dec.]
  month_names: [ianuarie, februarie, martie, aprilie, mai, iunie, iulie, august, septembrie, octombrie, noiembrie, decembrie]
```

Section-heading sets are a view property (`heading_set`): `en` (Summary, Skills, Experience, Education, Projects, Publications, Languages, Certifications, Awards & Honors, Volunteering); `ro_modern` (Profil profesional, Competențe, Experiență profesională, Educație, Proiecte, Publicații, Limbi străine, Certificări, Premii și distincții, Voluntariat); `ro_europass` (Informații personale, Experiența profesională, Educație și formare, Competențe personale, Informații suplimentare, Anexe — typed with comma-below, never pasted from the official PDF, which is typeset with cedilla glyphs, 390 vs 25 measured). Academic EN headings: Education, Research Experience, Publications and Manuscripts, Presentations, Software, Honors and Awards, Skills.

---

## 3. The document matrix

### 3.1 Every output, its reader, contents, length, format and constraints

| # | Output (view id) | Reader | Contains | Length / page | Format | Hard constraints (VERIFIED source in brackets) |
|---|---|---|---|---|---|---|
| 1 | **ATS engineering resume EN** (`ats`) | Workday (Accenture, Adobe), Greenhouse (Bitdefender), SmartRecruiters (Endava, Deloitte, Bosch, Ubisoft), Ashby (UiPath), proprietary portals (Microsoft, Amazon, Google, Oracle, EPAM, Luxoft), eJobs/BestJobs/LinkedIn parsers; then a recruiter | Summary (ats variant) · Skills (literal: Python, SQL, Azure/AWS, LLM/RAG/agents, MCP) · Experience (XYZ bullets, scope statements) · Education · Projects (3–5) · Publications (only published/accepted) · Languages (CEFR) | 1–2 pages, A4 | PDF < 2 MB, real text, tagged, single column, `engineeringresumes` or `classic`, icons off, URLs as text, no footer | no photo/DOB/nationality/marital/CNP; city only; conventional headings; file `Andrei_Mihai_Visalon_CV_EN.pdf` [market wave B4, C3, C5, F1, G; cv-studio ats-rules] |
| 2 | **ATS-AI variant** (`ats-ai`) | same, for applied-AI/agent roles (UiPath, Adobe agentic, Druid, Bitdefender ML, Accenture early-career AI) | same data; skills/projects reordered toward agents, MCP, evals, local inference; research line about GRACE/FAERS as delivery evidence | 1–2 pages, A4 | as #1 | as #1; overlay-driven (§5) |
| 3 | **Designed human resume EN** (`designed`) | a human: referral contact, hiring manager by e-mail, fair follow-up, portfolio site | as #1 with the `ink`/`opal`/`ember` theme, colour, project links; still single column | 1–2 pages, A4 | PDF | never uploaded to an ATS; no photo (no verified multinational portal has a photo field) |
| 4 | **RO modern CV** (`ro`) | Romanian SMEs, in-house IT at non-tech companies, Romanian-language ads, state-owned employers' inboxes | identical content to #1 in Romanian (`text_ro`), `ro_modern` headings, English stack names and titles with RO gloss, CEFR ("Engleză – C1", "Română – limba maternă") | 1–2 pages, A4 | PDF, comma-below diacritics, `justified-with-no-hyphenation` | one language throughout, never bilingual; no CNP/address; photo only in the `ro-traditional` sub-view if the ad's culture asks; file `CV_RO_Visalon_Andrei-Mihai.pdf` [RO wave §1, §7] |
| 5 | **RO Europass-model CV** (`europass`) | public-sector competitions (HG 1336/2022, HG 611/2008), university hiring (UB FAA 2025, UBB 2025), UBB master portfolio, some other universities' doctoral files (UMF Cluj, UB Geography) | official Europass sections; legal name form; optional photo/DOB where the form asks; Romanian; separate publication list where the methodology asks | ≤ 2 pages (UBB limit) | official editor export (PDF with embedded HR-XML) from XML seeded by `europass.py`; **signed original + anonymised PDF** (name + optional e-mail only, UBB pattern) | never sent to a tech employer; every field must equal the master (G6) [RO wave §2; academic wave §6.1.2, §7] |
| 6 | **International academic CV EN** (`academic`) | US-style PhD adcoms, EU MSc/PhD reviewers, faculty he approaches for a witness | Education (thesis, supervisor) → Research experience (projects as research entries) → Publications and manuscripts (status subsections) → Presentations → Software (DOIs) → Honors → Skills (short) | 2–3 pages; A4 for EU, **Letter for US-style portals** (per-view `page.size`) | PDF, `classic` or `harvard` | no summary, no photo/DOB/marital; ORCID in header; publication statuses machine-labelled [academic wave §1, §3] |
| 7 | **EU-vacancy academic CV + cover letter** (`eu-phd`) | a named supervisor/HR at NL/DE/CH/Nordic universities (salaried PhD positions) | 2-page CV from #6 + vacancy-tailored letter ("they want X, I have Y") + 2 referees | CV 2 p, letter 1 p | PDF | gap-free dates; referees with `reachable-consented`; master's assumed (not before 2029) [academic wave §6.3] |
| 8 | **Gap-free tabular CV EN** (`eu-msc`) | ETH/TUM MSc admissions | full continuous history from high school (education + work), tabular, in the programme's language | as required | PDF | no biographical gaps (ETH), statement of reasons separate [academic wave Claim 6.3.2] |
| 9 | **UEFISCDI CV and track record** (`uefiscdi`) | Romanian grant evaluators (future; needs a PhD for TE/PD, but institutional/student calls reuse the template family) | Name/DOB/gender/nationality (required by the template), ORCID, education, positions, ≤10-output track record, narrative CV | ≤ 4 pages | Typst template: A4, Times New Roman 11 pt, 1.15 spacing, 2 cm margins (parameters "forbidden" to change) | English except Romanian-specific fields [RO wave §2.3] |
| 10 | **FMI master dossier pack RO** (`fmi-master`) | UB FMI admissions secretariat and committee (next window ~1–14 July 2027) | signed *Lista performanțelor extracurriculare* (only items with `proof`: presentations, published articles, research internships, scholarships, competitions — employment/hackathons/courses excluded by rule) + attachments index + signed 2-page thesis summary + 10-minute oral deck outline + B2 certificate slot | list 1 p; summary 2 p | PDF for print + signature | not a CV; scoring = licence average + 0.25/item, max 3 per criterion, 40 % of the mark; English tracks need B2 (bac certificates rejected) [FMI methodology; academic wave §6.1; gap-closing §0] |
| 11 | **UB doctoral pack RO** (`ub-phd`, ≥ July 2029) | Școala Doctorală de Informatică (oral exam, supervisor agreement mandatory) | *memoriu de activitate științifică* (narrative research report), *lista lucrărilor științifice publicate* categorised by tier, written topic proposal + bibliography skeleton, 10-topic list slot, B2 language certificate slot | memoriu 2–4 p; list ≤ 1 p | PDF, Romanian | no CV in the UB dossier (art. 14(1)); list contains only published/accepted items; in-prep work described in the memoriu only [RO wave §3.1; academic wave §6.2] |
| 12 | **Cover letters EN/RO** (`letter`) | hiring manager / recruiter; supervisor (EU) | 3 paragraphs: hook, proof (2–3 achievements by id mapped to the JD), close; JD terminology mirrored | 1 page | Typst → PDF; `.md/.txt` for web forms | every factual sentence maps to achievement/metric ids (G2 applies) [cv-studio cover mode] |
| 13 | **Statement of purpose** (`sop`) | US-style adcoms | one research direction + what he already did + why this department/advisor | 1.5–2 pages | Typst → PDF | writing samples (manuscripts) uploaded alongside regardless of status [academic wave §2] |
| 14 | **LinkedIn text pack** (`linkedin`) | Romanian recruiters (first document most see), sourcing searches | Headline ≤ 220 chars (open-to-work text variant), About ≤ 2,600 (first ~300 front-loaded), Experience entries, Skills ranked, Featured items; secondary RO profile language | n/a | `linkedin.md` + `linkedin.diff` vs previous release | manual paste only (no write API); English primary [multi-doc wave §2.7; market wave C5] |
| 15 | **JSON Resume + academic site** (`json`, `site`) | tooling; anyone who clicks the URL; committees who follow the CV link | `resume.json` (x_ stripped); one-page site: name, research interests, papers with status, DOI'd software, CV PDFs | n/a | JSON; static HTML (GitHub Pages) | statuses identical to the CV (G6) |
| 16 | **Platform paste packs** (`platforms`) | eJobs (RO + EN structured profiles, both sent to employers), BestJobs (PDF ≤ 10 MB, .pdf/.doc only), Hipo (4-step form, up to 5 CVs/5 letters, CV-Barcode for the 30–31 Oct 2026 fair) | field-by-field text in the platform's language | n/a | `.md` blocks | eJobs profiles filled to equal completeness; age hidden by eJobs anyway; attach #1 as the file [market wave C2–C4] |
| 17 | **Fallbacks** (`txt`, `docx`) | forms that need plaintext; old Taleo installs or Romanian employers demanding .docx | text from RenderCV's Markdown; `pandoc` DOCX | n/a | `.txt`, `.docx` | second engine; produced only on demand; G4 re-run on the DOCX's text |

### 3.2 Where Romanian conventions and ATS conventions conflict, and what the system does

| Conflict | Romanian expectation (VERIFIED) | ATS / international expectation (VERIFIED) | Resolution (INFERRED rule) |
|---|---|---|---|
| Photo | Europass template field; national Europass centre and eJobs "Model CV 2026" say include; contested even locally (Hipo, cvmaker say split/unnecessary) | no verified multinational portal has a photo field; EEO statements; images can break parsing | `x_identity.ro_only.photo`; emitted only by `europass` and `ro-traditional`; never in #1–#3, #6–#9; platform profile pictures are the platform's field, not the PDF's |
| Date of birth, nationality, marital status | Europass optional fields; Romanian registration forms collect them; 1 in 3 recruiters admit age bias; eJobs hides age | forbidden by US/UK academic guidance; not requested by portals | stored once with `scope: ro_only`; emitted only when the dossier form demands (UEFISCDI requires DOB/gender/nationality; Europass optional); never in ATS/international views |
| CNP / ID numbers | sometimes listed as recruitment-stage data (Continental notice); public competitions collect them | never | never stored in the profile; documented refusal; supplied only at contract stage |
| Europass layout | legally mandated "model comun european" for public-sector and university competitions; ≤ 2 p at UBB | Europass is table-heavy and disliked by private recruiters; not ATS-shaped | Europass is a compliance output produced via the official editor's XML round-trip, never a design output; never sent to a software employer |
| Language | CV in the language of the ad; Romanian for state/in-house IT/Romanian ads; ~74 % of substantive eJobs IT ads sampled were in English | English throughout at multinationals and outsourcers | language is a view property; two single-language documents from one source; RO bullets are stored as `text_ro` on the same ids; stack names untranslated |
| Job titles | contracts carry COR titles ("Programator 251202"); adeverințe and REGES extracts will state them | market and portals search English titles | dual-title fields; "English title (Romanian COR title, cod COR)" only for state/university readers; English with RO gloss for SMEs; English alone in EN views |
| Diacritics and name form | comma-below orthography; CI may print a hyphen/diacritic; MRZ never does | ASCII everywhere; ORCID recommends no special characters | `legal_name` on dossiers/Europass/grants; `display_name` (ASCII) on every English/web surface; RO views use U+0219/U+021B and the cedilla gate |
| Hyphenation/language tagging | Romanian text | RenderCV tags every PDF `/Lang en` (closed enum) | RO views use `justified-with-no-hyphenation` (probe-verified key); accepted limitation, documented |
| Page size | A4 | US-style portals expect Letter; EU expects A4 | per-view `design.page.size`; A4 default, Letter only for `academic-us` |
| Section order | Europass fixed order; RO guides put "Profil profesional" first | ATS: contact → summary → skills → experience → education; academic: education first, no summary | order is part of the view; three canonical orders (ats, academic, europass) |
| Length | 1–2 p private; ≤ 2 p Europass (UBB); ≤ 4 p UEFISCDI | 1–2 p ATS; 2–3 p early-career academic | `max_pages` per view enforced by G4 |
| Signatures / paper | achievements list, thesis summary, Europass "asumat prin semnătură", sometimes every page | none | views with `signature: true` render a signature line (or a footer via `templates.footer`); print-and-sign is a manual release checklist item |
| "References available on request", hobbies, driving licence | sometimes expected (Europass fields) | omit | omitted everywhere except `europass` where the form has the field |
| Date format | "MM/YYYY" guidance; Romanian month names | "Jan 2024" style | RenderCV locale per view; `doubtful` freelance dates render as year + "~N months" in the bullet, never an invented month |

### 3.3 View definitions (the presentation layer, `views/*.yaml`)

```yaml
id: ats
language: en
audience: ats            # ats | human | academic | dossier | platform
theme: engineeringresumes
design: design/ats.yaml  # -d sidecar (probe-verified keys)
locale: locale/en.yaml
page_size: a4
max_pages: 2
heading_set: en
summary_variant: ats
headline: ats
name_form: display
include_personal_data: false
include_photo: false
sections: [summary, skills, experience, education, projects, publications, languages]
publication_statuses: [published, accepted]
project_mode: product    # product | research
date_precision: month    # month | year (dossiers), doubtful → year
filename: "{display_name_snake}_CV_EN.pdf"
signature: false
```

`academic` differs in `audience: academic`, `theme: classic|harvard`, `sections: [education, research_experience, publications, presentations, software, honors, skills]`, `summary_variant: null`, `headline: null`, `project_mode: research`, `publication_statuses: all`, `max_pages: 3`, `page_size: a4|us-letter`. `ro` differs in `language: ro`, `locale: locale/ro.yaml`, `heading_set: ro_modern`, `filename: "CV_RO_{legal_family}_{legal_given}.pdf"`. `europass` and the dossier packs are not RenderCV views; they are generators that read the same profile and honour the same `include_personal_data`/`name_form` flags.

---

## 4. Build and validation pipeline

### 4.1 Gates, in order, all fail-closed with `SUCCESS:<gate>` / `FAILED:<gate> reason`

**G0 — Environment.** Engine resolves at `~/.local/share/cv-studio/venv` (or `CV_STUDIO_RENDERCV`); `rendercv --version` == pinned; `import typst`, `import pdfminer`, `import pypdf` succeed; `PYTHONIOENCODING=utf-8` set; theme list read from the installed package (no static whitelist); a 1-entry probe CV renders and extracts (font/DLL sanity). Proves: the toolchain is the tested one. (Today: FAILED — persistent venv absent; the session venv passes.)

**G1 — Schema.** YAML parses; the non-`x_` part validates against JSON Resume 1.0.0 (`jsonschema`, official schema vendored); the `x_` blocks validate against a Pydantic model (`tools/schema.py`): enums for `status`, `venue_class`, `tag`, `disclosure_tier`, `verifier.status`, `confidence`; ids unique; every `from`/`metrics`/`engagement`/`bib_key`/`proof` reference resolves. Proves: the file is well-formed and every link points somewhere.

**G2 — Provenance and zero-fabrication (the gate that replaces cv-studio's lint).** Errors, not warnings, on:
- `x_master` or `x_metrics` absent/empty while any `highlights` or `summary` exist (closes the fail-open holes; both `if haystack and` and `if master and` short-circuits are gone);
- any highlight in **any** section (`work`, `projects`, `education`, `volunteer`, `awards`, `basics.summary`, `x_narratives.*`, `x_sections`, project `description`) without `from:` ids, or citing an id that does not exist;
- any digit-bearing token (money, %, ×, K/M/B, comma-grouped, ≥3 plain digits; a 4-digit token counts as a year **only** when not comma-grouped and adjacent to a date context) whose normalised digits are not found in a cited `x_metrics` entry; cited metric with tag `B` or `U` → error ("bounded/unknown values never render as numbers"); tag `E` → allowed only with a `~`/"about" marker in the text;
- inflation lexicon (`led`, `managed`, `team of`, `we `, `scaled`, `architected at scale`, `mentored`) when the cited engagement has `team.size <= 1` or `claims.sole_engineer: true` (the sole-engineer table from the intake protocol);
- Tier-B engagement whose counterparty name appears anywhere in a public view's text; Tier-C engagement referenced by any public view; NDA `sunset` in the future with `covers: [name]` and the name present;
- an achievement whose `verifier.status` is below `artifact-only` used on any view; a referee listed anywhere without `reachable-consented`;
- `work[i]` name/title/dates differing from its engagement record (edit the record, then `ingest`), or month precision on a `doubtful` date;
- `x_outputs` inconsistencies: `in_preparation`/`submitted` with a named journal; `preprint`/`published` without DOI/URL; `counts_for_fmi_dossier: true` without a `proof` id; a hand-typed status label in a bib `note` field;
- identity: `basics.name != display_name`; ORCID checksum invalid; `orcid_registered_name != display_name` (warning, with the fix text);
- per-view policy: `include_personal_data: false` but a `ro_only` field would render; language purity (RO view: no `en` heading strings, no untranslated bullet lacking `text_ro`; EN view: no Romanian diacritics outside names); `max_pages` declared.
Proves: every claim on every surface traces to the owner's own fact record, and nothing the record marks as unverifiable, confidential or unsupported can reach a reader. Does **not** prove the record is true (§6).

**G3 — Render.** For each view: emit `<view>.rendercv.yaml` (with an explicit `locale:` block and the view's sections mapped to RenderCV entry shapes: OneLine for skills/languages/certificates, Experience for work/volunteer/teaching, Education, Normal for projects/software, Publication for outputs, Bullet for honors/service, ReversedNumbered for presentations), run `rendercv render <yaml> -d <design> -lc <locale> -o <dir> -pdf <ABSOLUTE path> -nopng -q`; Typst templates compiled via `typst.compile()` for letters/SOP/dossiers/UEFISCDI; exit codes captured; the `.typ` kept as the auditable source. Proves: the engine produced the artifact from the mapped data, deterministically.

**G4 — Text-layer and structure (replaces the PyMuPDF smoke test).** With `pdfminer.six` + `pypdf` on every PDF:
- presence: name (both forms as applicable), e-mail, every company/counterparty descriptor, every institution, every section heading of the view, every DOI string, every project name, every language line;
- reading order: the sequence of headings in the extracted text equals the view's section order (single-column proof — interleaving would break it);
- page count ≤ `max_pages`; MediaBox equals the view's page size (A4 595.28×841.89 or Letter 612×792);
- fonts: every font embedded with a ToUnicode map (pypdf); no glyph-index-only text;
- glyphs: zero cedilla code points in RO output; comma-below present where the source had them; no U+FFFD;
- policy: no `ro_only` value present in a view with `include_personal_data: false` (DOB string, "Necăsătorit", photo XObject count = 0); no CNP-shaped 13-digit token anywhere, ever;
- file size < 2 MB (LinkedIn Easy Apply guidance) and ≤ 10 MB (BestJobs);
- tagged: `/StructTreeRoot` present (free; unproven benefit); `/Lang` recorded (expected `en` even for RO — documented).
Proves: what the parser will see is exactly what the YAML says, in order, on the right paper, with real text.

**G5 — Parse simulation (optional, honest about its limits).** A local heuristic segmenter over the extracted text (does each heading start a line; do dates parse to `YYYY-MM`; does the first line carry the name; are contact lines separable) plus the manual **copy-paste-to-plaintext test** before every real submission. Optional paid check through a commercial parser (Affinda via Eden AI) if the owner wants a second opinion; it still says nothing about Workday/Greenhouse/Taleo (VERIFIED: RenderCV's own evidence covers only Affinda/Extracta/Klippa).

**G6 — Cross-document consistency.** On a release, `verify.py` extracts facts from every produced artifact (PDF text, `linkedin.md`, `resume.json`, Europass XML, dossier PDFs, site HTML) and asserts one fact set: same engagement dates per role, same titles per language, same publication statuses and DOIs, same name form per policy, same ORCID, same education dates/grades, same skill lists per view policy. Differences are listed as `FAILED:consistency <artifact> <field>`. Proves: no output in the release contradicts another (the failure mode ORCID/CV mismatch warnings exist to catch).

**G7 — Release.** `cvstudio.py release vYYYY.MM[.n]`: G0–G6 green → git tag → regenerate **all** views and packs from the tag into `dist/<tag>/` → `release-notes.md` (fact diff since last tag, LinkedIn diff, Europass field diff, manual checklist: paste LinkedIn, re-import Europass, print-and-sign dossier items, re-upload eJobs/BestJobs/Hipo, update the site) → commit. Anything not regenerated from the tag is stale by definition.

### 4.2 What "correct before it is sent" means here

An artifact may be sent only if, on the same tag: G2 passed (traceable, unfabricated, NDA-safe), G4 passed for that artifact (the PDF is a faithful, parseable rendering), G6 passed (it agrees with every sibling artifact), and the release checklist's human item is ticked: **a person has read every non-numeric claim** (the lint cannot detect "led a team" phrased without digits or an inflated adjective — the market wave's anti-inflation framing owns the wording; this system only enforces the mechanical part). For a tailored variant the same rule applies to `dist/targets/<id>/` (§5).

### 4.3 CLI surface of the extended wrapper (INFERRED)

```
cvstudio.py ingest   engagements/ profile.yaml           # facts → work[]/x_master keys/x_metrics skeletons (idempotent)
cvstudio.py validate profile.yaml [--view V]             # G1 + G2 (all surfaces, fail-closed)
cvstudio.py build    profile.yaml --view V [--target T] --out dist/...   # G3 + G4 for one view
cvstudio.py letter   --target T --lang en|ro             # Typst letter from the overlay's facts (G2 on the body)
cvstudio.py dossier  fmi-master|ub-phd|ubb-portfolio|uefiscdi --out dist/...
cvstudio.py europass --lang ro|en --out dist/...         # XML + import checklist; fails if the editor rejected the last import
cvstudio.py linkedin [--target T] --out dist/...         # linkedin.md + diff vs last release
cvstudio.py json     profile.yaml                        # unchanged: portable JSON Resume
cvstudio.py tailor   profile.yaml targets/T/jd.md --out dist/targets/T/tailor-report.md   # phrase matcher; never writes into the profile dir
cvstudio.py verify   dist/<tag>/                         # G4 (all) + G6
cvstudio.py release  vYYYY.MM                            # G0–G7
```

---

## 5. Tailoring per application without forking the design

### 5.1 The overlay model (INFERRED)

A target is a folder `targets/<id>/` with the JD snapshot (`jd.md`, or the JSON posting pulled from the public Ashby/Greenhouse boards — UiPath and Bitdefender expose them without scraping, VERIFIED) and an `overlay.yaml`:

```yaml
id: uipath-applied-scientist-2026-09
view: ats-ai                     # base view; the design never changes
channel: ashby                   # ashby | greenhouse | workday | smartrecruiters | ejobs | email | fair | linkedin
language: en
headline: ai                     # must be one of x_identity.headlines keys
summary_variant: ai
skills_order: [agents-mcp, python-ml, cloud, data]
projects: [grace-iberlef-2026, <mcp-server-repo>, <local-ai-tool>]     # selection + order of EXISTING project ids
bullets:                         # per role: selection + order of EXISTING achievement ids; never new text here
  "Acme|Backend Developer": [ach-acme-02, ach-acme-01]
keyword_map:                     # JD term → where it is TRUE in the profile (skills | title | bullet id); missing terms stay listed
  "agentic automation": {skills: agents-mcp, bullet: ach-grace-03}
  "LLM evaluation": {bullet: ach-grace-02}
  "Kubernetes": null             # honestly absent → not added
bold_keywords: [agentic, MCP, evaluation]   # RenderCV settings.bold_keywords, human views only
letter: {hook: hook-uipath-01, proofs: [ach-grace-02, ach-acme-02, ach-mcp-01], close: default}
referees: []                     # academic targets only; ids with reachable-consented
```

`build --target T` deep-merges the overlay onto the view at build time; the profile file is untouched; output goes to `dist/targets/<id>/` with the resume, the letter, the tailor report, the JD snapshot and `sent.json` (date, channel, file SHA-256, contact) so every sent artifact is reproducible from a tag + overlay. Overlays reference ids only, so the same overlay renders the RO variant by switching `language`; RO text comes from `text_ro` on the same ids.

### 5.2 The per-application workflow

1. **Capture** the JD (paste, or the board JSON) → `targets/<id>/jd.md`; note the ATS from the market wave's table (Workday/Greenhouse/SmartRecruiters/Ashby/proprietary → all take #1; eJobs → both profiles + PDF; Hipo → form).
2. **Match**: `tailor` (phrase-level: unigrams + bigrams/trigrams, a synonym map "container orchestration ↔ Kubernetes", stop-list) → report of covered/missing terms with the 3-place rule (skills, title line, proving bullet).
3. **Decide truthfully**: for each missing term, either (a) it is real and evidenced → add an achievement/metric to the bank **with evidence** (the bank grows, then the overlay can cite it), or (b) it is real but unevidenced → interview answer only, not on paper, or (c) it is not true → stays missing. The overlay only selects and orders.
4. **Build** `--view ats(-ai) --target <id>`; gates G2–G4 run on the merged result (an overlay cannot smuggle text past the lint because it has no text fields).
5. **Letter**: the LLM drafts three paragraphs from the overlay's `hook`/`proofs`; the draft is linted like bullets (every factual sentence cites ids; numbers resolve; JD terminology mirrored only where the keyword map says it is true) → `letter.py` → PDF (+ `.txt` for web forms).
6. **Send** through the channel; record `sent.json`; for eJobs apply within 1–2 weeks of posting (eJobs's own advice; ~89 applicants per IT ad).
7. **Follow-up** notes and any interview outcome go to the engagement/kudos log, not to the profile.

### 5.3 Academic tailoring uses the same mechanism

- **US-style programme**: overlay on `academic` (Letter page size) selects the research entries and the `sop_direction` variant; writing samples attached regardless of status; three `reachable-consented` referees.
- **EU vacancy**: overlay on `eu-phd` adds a "they want X, I have Y" table to the letter from the vacancy text; two referees.
- **FMI master dossier**: not tailored — generated from `x_academic`/`x_outputs` items with `proof`; the only "tailoring" is choosing the oral-exam subject (IberLEF/GRACE or FAERS) for the deck outline.
- **Supervisor outreach** (the witness the academic wave calls the biggest gap): a one-page RO/EN research profile (`research-profile` view: research entries + outputs with statuses + software DOIs) generated from the same source.

### 5.4 What tailoring must never do (the anti-fork rules)

No hand-edited copies of `profile.yaml`; no per-target theme changes; no text in overlays; no numbers outside `x_metrics`; no hidden keyword layers (excluded by design; brilliant-cv's own docs warn screeners penalise hidden text); no keyword stuffing — the reason is truthfulness, not an unproven "semantic ATS penalty" (CONTESTED in the multi-doc wave).

---

## 6. Honest limits and where manual work remains

**The system will not:**
- **Write to LinkedIn.** The Profile API is restricted and read-only; self-serve apps get OpenID + posting only (VERIFIED). Output is `linkedin.md` + a diff; the paste is manual; the release notes carry the date.
- **Prove what any ATS does.** RenderCV's evidence is a vendor self-test on Affinda/Extracta/Klippa; Workday/Greenhouse/SmartRecruiters/Ashby/Taleo behaviour is unobservable from here; G4/G5 prove a sane, ordered, real text layer, which is the load-bearing property; tagging is free but unproven to matter (CONTESTED).
- **Prove truth.** G2 proves traceability to the owner's own bank and metrics; it cannot know the bank is true, and it cannot see fabrication phrased without digits or an inflated adjective. A human review of non-numeric claims is a release checklist item, not a gate.
- **Emit PDF/UA-1 or PDF/A.** Typst can, RenderCV exposes no flag; the sample carries no `pdfuaid`/`pdfaid` (VERIFIED). Only matters if an employer demands archival/accessibility conformance.
- **Emit DOCX natively.** `pandoc` from RenderCV's Markdown, yamlresume (needs XeTeX) or Reactive Resume import are second engines with drift risk; G4 is re-run on their text.
- **Guarantee the Europass round-trip.** The only JSON→HR-XML mapper is a two-commit unofficial project (UNVERIFIED that generated XML imports cleanly); the design budgets one real import test and falls back to manual entry in the official editor seeded from the master, with the editor's exported XML stored as the canonical Europass artifact and diffed by G6.
- **Tag Romanian output `/Lang ro`.** RenderCV's `locale.language` is a closed enum; RO strings ride on `english`; hyphenation is English (mitigated with `justified-with-no-hyphenation`); a custom Typst theme via `rendercv create-theme` is the escape hatch if a reader ever needs the language tag.
- **Score jobs.** `tailor` is a phrase checklist, not a score; the decision of what is truthfully addable is human.
- **Write the narratives.** The SOP, memoriu de activitate științifică, topic proposal, UBB career plan, cover-letter hooks and the About text are human-authored (LLM-assisted at most); the system typesets them and fact-lints their claims.
- **Shorten the intake.** Extracting his undocumented salaried/internship/freelance history is Sessions 0–5 of the intake protocol (REGES-Online extract, certificates, invoices, calendar, deep dives, numbers ladder, honesty pass) — weeks of owner time; `ingest` only turns the resulting records into skeletons.

**Manual work that stays manual (release checklist items):** read the CI once and fill `legal_name`; fix ORCID (add "Mihai", Also-known-as variants) before the first byline; enable DataCite auto-update, add `CITATION.cff` with the ORCID and cut Zenodo releases; obtain the B2 English certificate or the two-semester evidence before July 2027; read every NDA and set tiers; obtain written consent from Tier-A clients and referees; print-and-sign dossier documents; import Europass in the official editor; paste LinkedIn; fill eJobs RO+EN and the Hipo form; attend the 30–31 Oct 2026 Hipo fair with the Barcode; ask the FMI secretariat in writing whether a CEUR paper counts as "articol științific publicat"; the copy-paste plaintext test before each real submission; script the Ashby/Greenhouse alerts (outside this repo).

**Environmental caveats today (VERIFIED):** the persistent venv does not exist (the working engine is a session scratchpad venv that will vanish); PyMuPDF cannot load until the VC++ 2015–2022 x64 redistributable is installed (msvcp140.dll) — the design does not depend on it; `pipx list` is broken on this VM; the Bash tool has dumped environment secrets before on this box (memory note) — run the toolchain from PowerShell.

---

## 7. Implementation backlog, assumptions, contested points

### 7.1 Backlog (INFERRED estimates; order = value per hour, dependencies respected)

| Step | Work | Est. | Evidence it is needed |
|---|---|---|---|
| A | Persistent install: `setup.ps1` into `~/.local/share/cv-studio/venv`, pin `rendercv==2.8 typst==0.15.0 pdfminer.six pypdf bibtexparser`; set `PYTHONIOENCODING=utf-8` in the wrapper; optional VC++ redistributable | 15–30 min | §1.1 rows 3–4 |
| B | Rewrite `validate` as G1+G2 (Pydantic `x_` schema; bullet objects; all surfaces; fail-closed; year heuristic; inflation lexicon; NDA/verifier/status/identity rules) | 4–6 h | `adv-check-zero-fab-lint.md` (both holes reproduced by two agents) |
| C | Views + design/locale sidecars: `views/*.yaml`, `design/*.yaml`, `locale/{en,ro}.yaml`, runtime theme discovery, explicit `locale:` block in emitted YAML, absolute `-pdf` path, `tailor --out` default fix | 3–4 h | §1.1 rows 6–8, §1.4 |
| D | Section mappers: `x_academic` → RenderCV entry shapes; `x_sections` passthrough; academic/RO section orders; `bib2entries.py` with the status machine | 4–6 h | §2.4–2.5; RenderCV `cv.py`/`section.py` (VERIFIED shapes) |
| E | `ingest.py` from engagement records (idempotent; locked facts) | 3–4 h | §2.3; intake schema |
| F | G4 text/structure gate with pdfminer + pypdf (order, MediaBox, fonts, glyphs, policy, size) | 3–4 h | §4.1 |
| G | Typst templates: letter, SOP, dossier list, memoriu, UEFISCDI (A4/TNR 11/1.15/2 cm); `letter.py`, `dossier.py` | 4–6 h | §3.1 rows 9–13; RenderCV #24 refusal |
| H | `europass.py` (HR-XML 3 Candidate) + one real import test in the official editor; documented manual fallback | 3–4 h + test | §1.3; UNVERIFIED mapper |
| I | `linkedin.py` (`linkedin.md` + diff), platform paste packs | 1–2 h | §3.1 rows 14, 16 |
| J | `verify.py` (G6 cross-document facts) + `release` (G7) | 4–6 h | §4.1 |
| K | `tailor` phrase matching + synonym map + overlay merge in `build` | 2–3 h | §5 |
| L | Optional: `resumed` HTML, GitHub Pages academic site, `pandoc` DOCX path | 2–3 h | §3.1 rows 15, 17 |
| M | **Content**: intake Sessions 0–5 → `engagements/*.yaml`; bullets; RO translations; narratives; `publications.bib` | weeks | owner decision 1; intake protocol |

Total code: ~3–5 focused days (the sibling wave's 1–2 days covered A–D and G–I only). Sync the edited skill back through the toolchain (`~/source/agent-skills-toolchain/skills/cv-studio`) so the three on-disk copies do not drift.

### 7.2 Assumption ledger (per the behaviour contract §1b)

| Assumption | Confidence | Basis / what breaks if wrong |
|---|---|---|
| RenderCV 2.8 + typst 0.15.0 stay installable on Python 3.14 and the pins hold | almost certain | installed today; schema renames happen between minors (2.4) — pin and re-test on upgrade |
| Single-column, ordered, real-Unicode text is what ATS parsers need; tagging is a free extra | likely | vendor self-test + extraction reasoning; no Workday/Greenhouse evidence exists; mitigation: plaintext paste test, optional Affinda check |
| The persistent venv will be created (step A) before any real build | high (owner action) | without it every build fails at G0 |
| `pdfminer.six` is an acceptable substitute for PyMuPDF in the self-check | very likely | it is closer to what parsers do; page count and structure come from pypdf |
| UB/FMI dossiers keep not requiring a CV (master 2027, PhD ≥2029) | medium | regulations are re-issued yearly; re-read each cycle; the Europass/academic views exist regardless |
| Generated Europass XML imports into the official editor | low | single unproven tool → mandatory test + manual fallback designed in |
| The owner runs the intake and fills the banks with evidence | medium | without it the lint has nothing to trace to and blocks every bullet (by design) |
| He applies from Romania: A4 default, English primary, RO on demand | almost certain | owner ground truth + market wave |
| His CI's exact name form is readable and stable | high | UNVERIFIED value; one reading fixes it |
| The +0.25 eligibility of a CEUR paper is committee discretion | high that it is discretionary | ask in writing; the flag stays false until confirmed |

### 7.3 Contested or widely repeated but unevidenced (carried, not resolved)

- Tagged PDF improves ATS parsing — asserted by RenderCV/Typst, no independent A/B; treated as free.
- Keyword stuffing is penalised by "semantic ATS" — no vendor documentation; not stuffing is a truthfulness rule here.
- Hidden keyword layers — contradictory practice; excluded.
- PDF vs DOCX for old Taleo — unresolved; DOCX fallback kept.
- Photo on Romanian CVs — locally contested; resolved as a view property.
- "Europass not accepted in Romania" — segment-specific: legally mandatory in public/university competitions, negative in private tech.
- Whether an empty ORCID hurts — refuted as a general claim (roughly half of active records hold no works; neutral for hiring/admissions), with one real exception: a record created empty the week of a manuscript submission matches a paper-mill indicator editors are told to notice — hence populate Education/Employment/Software before the first submission (from the adversarial ORCID check).
- The Experis Q3 2026 "−11 %" Romania figure — superseded by Q4 2026 (−2 %, 41st of 42); direction (negative, junior squeeze) corroborated independently; irrelevant to the architecture except that evidence beats volume on the boards.
- Whether a GRACE system paper was filed by 24 May 2026 — likely not (~70 %); the outputs record encodes it as a technical report until the owner confirms.

---

## 8. Sources

Local (this scratchpad, all read in full or executed): `wave2-multi-doc-system.md` (S1–S38 upstream references incl. docs.rendercv.com changelog/ATS page, GitHub discussion #24, Typst 0.14/0.15 notes, jsonresume.org, LinkedIn Profile API docs, CTAN moderncv, AltaCV, Typst Universe packages, yamlresume, Reactive Resume, career-ops, ndf14685/resume-as-code, J0ker98/europass-cv, UPB SD-ETTI, FMI SDI page); `adv-check-zero-fab-lint.md`; `adv-check-cv-studio-rendercv.md`; `adversarial-check-render-path.md`; `adv-check-cv-studio-not-installed.md`; `orcid-empty-record-adversarial-check.md`; `adversarial-check-experis-q3-2026-romania.md`; `wave2-history-extraction.md` (§4 interviewer rules, §9 numbers ladder, §11 honesty pass, §12 schema; sources S1–S40 incl. Bock 2014, Harvard OCS, Kaplan-Moss 2020, Levashina 2014, OPM Accomplishment Record, Legea 176/2018, 78/2014, 258/2007, REGES-Online Ordin 1107/2025); `wave2-academic-cv.md` (UB/FMI/UBB/UPB regulations, ETH/TUM pages, CEUR-WS rules, CNATDCU 2016 criteria, ORCID/DataCite/Zenodo docs, faculty accounts Harchol-Balter/Nguyen/Bowman/Andersen/Gasarch/Kuper, APA 7 §10.8 guides); `wave2-ro-language-variant.md` (HG 1336/2022, HG 611/2008, UB FAA 2025, UBB 2025 methodologies, UEFISCDI TE 2026 package, UB doctoral regulation 2025/2026 art. 14, FMI SDI 2026 regulation art. 10/13/14, UB master regulation 2026 art. 4/6, FMI master methodology 2025 §VI/IX, Codul muncii art. 16/17, HG 64/2011 art. 24, COR 2512, Europass RO instructions glyph count, ORCID public API record, ICAO 9303); `wave2-romania-market.md` (eJobs/BestJobs/Hipo/LinkedIn/Greenhouse help pages, ATS API/fingerprint probes, Continental and ANSPDCP notices, Labour Code art. 29(3), Law 190/2018 art. 4, OG 137/2000, BestJobs 2023 age survey, getuhired 2026 dataset); `wave2-gap-closing.md` (FMI 2026 methodology scoring, IberLEF 2026 dates, SemEval-2027 timeline, Zenodo/CITATION.cff mechanics, GitHub profile audit); cv-studio skill files at `C:\Users\prekzursil\.claude\skills\cv-studio\` (`SKILL.md`, `scripts/cvstudio.py`, `references/schema.md`, `references/ats-rules.md`, `references/regional-formats.md`, `assets/sample-profile.yaml`); installed RenderCV 2.8 (`scratchpad/cvs-venv/Lib/site-packages/rendercv/schema/models/{cv/cv.py, cv/section.py, cv/custom_connection.py, cv/entries/publication.py, design/classic_theme.py, locale/other_locales/*}`); `scratchpad/adv-skel/Probe_Skel_CV.yaml` (RenderCV `new` skeleton: every `design`/`locale`/`settings` key); new probe artifacts `scratchpad/arch-probe/{design-ats.yaml, locale-ro.yaml, check.py, out/probe_ats_ro.pdf}`.

Tooling note: basic-memory, codex, firecrawl and most local MCP servers reported connection failures at session start; nothing in this document depends on them. No credential was read, printed or modified.
