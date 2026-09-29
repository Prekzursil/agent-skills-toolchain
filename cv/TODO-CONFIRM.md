# TODO-CONFIRM — every gap the owner must fill

Ordered by how much each gap **blocks**. Tier 1 stops the research profile (the December
supervisor deadline). Tier 2 stops or damages the engineering documents. Tier 3 improves
quality but blocks nothing. Tier 4 is hygiene to re-check before every submission.

Nothing in this list may be filled by guessing. Every item is either answered by the owner or
stays a marker in `profile.yaml`.

Status legend: `[ ]` open · `[x]` answered (write the answer straight into `profile.yaml`,
then tick it here).

---

## Tier 1 — blocks the research profile (do these first)

- [ ] **1. ORCID record — PARTLY WRONG, not empty (corrected 2026-09-29).** Measured against the ORCID public API: BOTH works are registered and correct. The defect is the EDUCATION entry, which credits the BSc to the University of Bucharest; the diploma on file is Titu Maiorescu (profile.yaml education[1] is right, ORCID is wrong). Owner to fix the ORCID record.
  `0009-0001-8776-8498` has **zero registered works** and an education entry that credits the
  bachelor's to the **University of Bucharest**. The BSc is **Titu Maiorescu University**; UB is
  the master's. Fix the education entry, then register the ChemRxiv preprint and the Zenodo
  deposit as works. *Blocks:* linking ORCID from any document. A supervisor who clicks it today
  sees an empty, factually wrong record — worse than no link.
  → `basics.profiles[ORCID].x_state_warning`

- [x] **2. RESOLVED 2026-09-29 — ChemRxiv preprint.** Title, DOI 10.26434/chemrxiv.15009306/v1, posted 2026-09-22, SOLE author, CC BY 4.0. Crossref API for every field except the licence, which is absent from the deposit and was read off the ChemRxiv page.
  *Blocks:* the research profile's only research-output line, and the ORCID registration above.
  The record currently carries the literal placeholder `"TODO-CONFIRM: exact preprint title"`.
  → `publications[0]`

- [x] **3. RESOLVED 2026-09-29 — Zenodo deposit.** Concept DOI 10.5281/zenodo.22819600 (resolves to v3, 10.5281/zenodo.22836832, 2026-09-18), CC BY 4.0, dataset, sole creator. Zenodo + DataCite APIs. NOTE: the preprint still cites the original deposit 10.5281/zenodo.22819601 (2026-09-17); moving it to the concept DOI is open work.
  *Blocks:* the "Data and software" block, which is the strongest reproducibility signal
  available (a SHA-256 manifest over all 630 files). Without the DOI it cannot be cited.
  → `x_data_and_software[0]`

- [ ] **4. PARTLY RESOLVED 2026-09-29 — GRACE.** Code repository: github.com/Prekzursil/grace-iberlef-2026 (public). The technical report is PUBLISHED: CEUR-WS Vol-4273, ceur-ws.org/Vol-4273/GRACE2026_paper6.pdf, CC BY 4.0, no DOI exists (CEUR mints none; absent from Crossref and DataCite). STILL OPEN: whether the owner wants the repository linked from the CV.
  that repository has a LICENSE file.**
  *Blocks:* the word **open-sourced** in the GRACE bullet. Per the kill list, "open-source" may
  not be applied to a repository with no LICENSE file, so without this answer the bullet must be
  reworded to "released" or the link dropped.
  → `projects[GRACE].url`, `projects[GRACE].x_todo`

- [x] **5. RESOLVED 2026-09-24 from the SmartUMS portal.** Faculty of Mathematics and Informatics; programme **Ingineria software (Software Engineering)**, taught in Romanian; Year 1 of 2 (2025-2026); tuition-based seat; admission grade 8.76; Year 1 = 60 ECTS. Dates 2025-09 -> 2027-07 confirmed by the owner. ~~Master's programme — exact name~~
  `2025-09 → 2027-07` are academic-year defaults and are marked INFERRED, not verified.
  *Blocks:* the education block of every academic document.
  → `education[University of Bucharest]`

- [x] **6. RESOLVED 2026-09-24 — fully, from the thesis PDF itself.** Graduation June 2025; media generala 8.28 (years 8.46/8.26/8.12); media licenta 7.30; 180 ECTS; Faculty of Informatics; programme Informatica; full-time. **Thesis: "Aplicatie de Management Financiar"**, supervisor **Conf. univ. dr. Marinela Nidelea**, session June/July 2025, 54pp, signed 2025-06-12. Repository: `github.com/Prekzursil/Personal-Finance-Management`. Filed at `~/Documents/personal-records/02-education/2025-licenta-titu-maiorescu/`.

- [x] **7. RESOLVED 2026-09-24 — OMIT entirely, including the academic CV.** ~~Babes-Bolyai (2021–2022, incomplete, no degree) — list it or not?~~
  `x_listing_decision: OMIT` is now recorded in `profile.yaml`. `include_ubb: false` on every
  view is unchanged, but it is now a **decision** rather than a default — that distinction is
  the whole point of the edit, since a default that happens to match is not a settled question.
  The owner accepted the stated trade-off: 2021-2022 is left unaccounted for and doctoral
  timelines get scrutinised; if a reviewer asks, he answers in person. Not to be re-litigated.
  The entry stays in the file so a reversal stays cheap.
  → `education[Universitatea Babes-Bolyai].x_listing_decision`

- [x] **8. RESOLVED 2026-09-24 — C2, no certificate cited.** ~~English — exact CEFR level (C1 or C2), and any certificate to cite.~~
  `fluency: "C2"` with `x_provenance: OWNER-STATED` is now in `profile.yaml`, unblocking the
  Europass language grid. The level renders **alone** and never as a certified, examined or
  accredited claim; where a surface demands an awarding body, the honest answer is
  "self-assessed against the CEFR scale", not a named exam. Note the original guard here read
  "never claim C2 unevidenced" — that guard was about *inventing* a level, and an owner
  statement is evidence of a different tier, not an absence of one.
  → `languages[English]`

- [ ] **9. (Process, not data) Supervisor choice and the written agreement.**
  G-1 records that the doctorate is committed and that the **binding gate is a supervisor's
  written agreement** — the publication list is optional and only a tie-break. The owner picks
  the supervisor. Nothing in this repository can substitute for that.

---

## Tier 2 — blocks or damages the engineering documents

- [x] **RESOLVED 2026-09-24 (owner: ended mid-2023, ~June). endDate is now "2023-06".** ~~10. DINUPLAST — the exact END MONTH, and nothing else.**
  The old three-way contradiction (title vs end date vs location) is **CLOSED**: the owner gave
  his own account and it supersedes both 2023 CVs — unregistered contract work, Ramnicu Valcea,
  on and off over about two years, covering a website, a multi-computer network with a database
  proxy keeping the machines in sync, workstation configuration, watchdogs, electronic-receipt
  automation, and an accounting-ready data pipeline (decision **G-19**). Do **not** re-open
  version A vs version B, and do not seek a REGES record — the work was unregistered, so none
  exists.
  **This paragraph was stale and is corrected 2026-09-26.** It still described the state BEFORE
  the owner gave the end month, and so contradicted this item's own header. Current truth:
  `profile.yaml` carries `startDate: "2021-05"` / `endDate: "2023-06"`, and the render no longer
  fails closed on the date. Provenance is **OWNER-STATED, not documented** — the work was
  unregistered, so no REGES record exists and none should be sought.
  Kept for history, since knowing why a field was once deliberately blank matters: previously the
  end month was INFERRED only (about two years from May 2021 ruled out version A's Jul-2022 end
  and placed it somewhere in 2023), so `endDate` deliberately held the literal string
  `TODO-CONFIRM` to stop any document shipping a guessed date, and the duration rendered as prose
  ("about two years, on and off") in the first highlight instead.
  → `work[DINUPLAST SRL].endDate`, `work[DINUPLAST SRL].x_dates_note`

- [ ] **11. momentstudio.ro — engagement start and end dates.**
  Both are empty. *Blocks:* every dated view; an experience entry with no dates reads as evasive.
  → `work[momentstudio.ro].startDate/.endDate`

- [ ] **12. momentstudio.ro — may the site be named and linked, and may the work be described
  publicly at all?**
  It is paid client work, so the client's permission governs. Separately, the repository cannot
  be linked until it is pruned (63,363 remote branches, 63,116 of them `cursor/*`, and 89
  `rescue/*` tags). *Blocks:* the only live, client-facing deliverable on the profile currently
  has no verifiable link.
  → `work[momentstudio.ro].x_link_gate`

- [ ] **13. PARTLY RESOLVED 2026-09-29 — Reframe.** URL github.com/Prekzursil/Reframe (public, 4 stars, 10 releases). It has NO LICENSE file — confirmed against both the GitHub licence field and a listing of the repository root — so it must never be called open-source (x_style lock). STILL OPEN: the one-line statement for a non-technical reader.
  and one sentence saying what it does for a non-technical reader.**
  *Blocks:* a reviewer cannot verify the nine signed releases or the 100% coverage gate without
  a link, and the coverage claim is one of the strongest engineering signals here.
  → `projects[Reframe]`

- [ ] **14. ZHMModSDK — upstream repository URL and the merged pull-request link.**
  *Blocks:* this is the **only** genuine third-party open-source credit on the profile
  (518 lines across 7 files, merged by the maintainer, 282-star SDK). Unlinked, it is just an
  assertion; linked, it is checkable in seconds.
  → `projects[ZHMModSDK]`

- [~] **15. Personal-Finance-Management — REPO URL NOW KNOWN: `github.com/Prekzursil/Personal-Finance-Management`.** **And it is not a side project — it IS the licenta thesis**, supervised and defended. That is a stronger, verifiable claim; state it as the thesis. The three remediation items (package rename off com.preethi.thrifty, drop the 'all rights reserved' line, honest README) still gate publishing the link.  — complete the three remediation items, then supply the
  repo URL.**
  1. Rename package and classes off `com.preethi.thrifty`.
  2. Remove the "all rights reserved" line.
  3. README states it began from an uncredited template and has since diverged.

  *Blocks:* the repo URL. The project stays on the CV either way, described honestly (G-10) —
  no claim of 100% originality, no naming of any other author.
  → `projects[Personal-Finance-Management].x_required_remediation`

- [x] **16. RESOLVED 2026-09-29 — tracelines.** Description taken verbatim from the repository's own public description; AGPL-3.0, tagged v0.2.0 (July 2026), 10 commits. It is the smallest entry on the profile and is scoped out of the two tight templates.
  Public URL and LICENSE?**
  *Blocks:* **it renders on no view at all** until answered. There is currently no verified
  description of it anywhere. No download or adoption figure may ever be cited for it.
  → `projects[tracelines]`

- [x] **17. CLOSED 2026-09-29 — llm-anthology.** Owner decided not to mention it at all; removed from profile.yaml. No description needed.
  *Blocks:* same — renders nowhere until answered.
  → `projects[llm-anthology]`

- [ ] **18. The "8,000 test functions" figure — which repository does it describe?**
  Held `renderable: false` only because the scope is unrecorded. Once confirmed, it renders as
  **"ships 8,000 test functions"** — never as "8,000 passing tests", which is on the kill list.
  → `x_metrics[test-functions]`

- [ ] **19. Agent platform — is the repository going to be cleaned up (≈237 MB (measured), committed
  browser profiles, red CI badge), or does it stay prose-only permanently?**
  *Blocks:* the decision of whether the platform work ever becomes linkable. As it stands the
  strongest engineering narrative on the profile has no artefact a reviewer can open.
  → `projects[Agent platform].x_link_gate`

---

## Tier 3 — quality, blocks nothing

- [ ] **20. A durable personal email address.**
  `andrei-mihai.visalon@s.unibuc.ro` is institutional and may lapse after the master's.
  Anything long-lived — ORCID, Zenodo, a preprint correspondence address — should carry an
  address the owner controls for life.
  → `basics.x_email_note`

- [ ] **21. Personal site or portfolio URL, if one is wanted.**
  `basics.url` is empty. Optional, but it is the natural home for the `designed` view and for
  the artefacts that cannot be linked as repositories yet.

- [ ] **22. Second manuscript — working title and target venue, if it is to be listed at all.**
  If listed it renders as **"in preparation"** only. Never "submitted", never "under review".
  → `publications[1]`

- [ ] **23. Other programming languages (C, Java, …) — confirm real use before listing.**
  Only Python, C++, TypeScript and SQL are currently listed, each traced to a specific project.
  → `skills[Languages].x_todo`

- [ ] **24. AI#CONNECT programme — what did you actually do, and when?**
  Pre-filled from `utm.ro/proiect-aiconnect`: official name *"Stagii de practica in Centrul
  Academic de Inteligenta Artificiala in Cloud si la parteneri"* (AI#CONNECT), grant
  **SMIS 312737**, call `PEO/71/PEO_P7/OP4/ESO4.5/PEO_A49`, Programul Educatie si Ocupare.
  *Still needed:* what YOU built or did, dates/duration, whether a certificate or credited
  `practica` was issued, and whether a partner company was involved.
  *Placement:* "Programmes and placements", NOT the research section — the public page
  describes socio-emotional skills training and vocational testing alongside the AI cloud
  centre, so listing it as research would overstate it without the specifics above.
  *Blocks:* nothing today. With the specifics it becomes a real bullet; without them the
  honest version is one sentence naming the programme and grant code.

---

- [x] **27. RESOLVED 2026-09-29 — OMIT: the teacher-training module (DPPD Level I, 2025) and ECDL (2019).** Owner: "not eligible for or worth mentioning in the CV".
  Both certificates surfaced in the 2026-09-28 personal-records audit and are filed there as records only
  (`02-education/2025-modul-psihopedagogic/`, `02-education/2019-ecdl/`). Do not propose them again. Closes OPEN-LOOPS L-30.

## Tier 4 — re-check before each submission

- [ ] **24. pbinfo numbers move.** The profile states 4,244 solved of 14,228 submissions against
  4,191 for second place, and 88 authored problems, **as of September 2026**. Re-read the live
  page before any submission and update both the figures and the "as of" date together.
  → `awards[0]`, `x_metrics[pbinfo-*]`

- [ ] **25. Name spelling on every external surface.**
  "**Andrei-Mihai Visalon**" — hyphenated, no diacritics — on ORCID, Zenodo, the preprint byline,
  LinkedIn, GitHub and every PDF. A mismatch between surfaces costs credibility and breaks
  author-identity matching.

- [ ] **26. Re-read the kill list before shipping any document.**
  18 forbidden claims in `x_forbidden`. The highest-severity three: **"finished 4th overall at
  GRACE"** (traces to a fabricated document — this one ends a candidacy), **"peer-reviewed
  publication"** (there is none; preprints only), and the **608-unit Databricks fan-out**
  (a different person's account in a corporate workspace — a confidentiality risk, not just an
  overclaim).
