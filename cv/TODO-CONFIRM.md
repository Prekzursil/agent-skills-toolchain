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

- [ ] **1. ORCID record is empty and wrong.**
  `0009-0001-8776-8498` has **zero registered works** and an education entry that credits the
  bachelor's to the **University of Bucharest**. The BSc is **Titu Maiorescu University**; UB is
  the master's. Fix the education entry, then register the ChemRxiv preprint and the Zenodo
  deposit as works. *Blocks:* linking ORCID from any document. A supervisor who clicks it today
  sees an empty, factually wrong record — worse than no link.
  → `basics.profiles[ORCID].x_state_warning`

- [ ] **2. ChemRxiv preprint — exact title, DOI, posting date, full author list in order.**
  *Blocks:* the research profile's only research-output line, and the ORCID registration above.
  The record currently carries the literal placeholder `"TODO-CONFIRM: exact preprint title"`.
  → `publications[0]`

- [ ] **3. Zenodo deposit — DOI, public URL, deposit title, license.**
  *Blocks:* the "Data and software" block, which is the strongest reproducibility signal
  available (a SHA-256 manifest over all 630 files). Without the DOI it cannot be cited.
  → `x_data_and_software[0]`

- [ ] **4. GRACE — public URL of the technical report, the code repository URL, and whether
  that repository has a LICENSE file.**
  *Blocks:* the word **open-sourced** in the GRACE bullet. Per the kill list, "open-source" may
  not be applied to a repository with no LICENSE file, so without this answer the bullet must be
  reworded to "released" or the link dropped.
  → `projects[GRACE].url`, `projects[GRACE].x_todo`

- [ ] **5. Master's programme — exact name / specialisation, and true start and end months.**
  `2025-09 → 2027-07` are academic-year defaults and are marked INFERRED, not verified.
  *Blocks:* the education block of every academic document.
  → `education[University of Bucharest]`

- [ ] **6. Bachelor's — graduation month, final grade (media), thesis title and supervisor.**
  *Blocks:* the academic CV, which is expected to list the thesis; a doctoral application
  normally states the final grade.
  → `education[Titu Maiorescu University]`

- [ ] **7. Babes-Bolyai (2021–2022, incomplete, no degree) — list it or not?**
  Currently `include_ubb: false` on **every** view pending this decision. If listed, the
  "not completed, no degree awarded" wording is mandatory everywhere; an unqualified line reads
  as a second degree. Listing it explains the gap year honestly; omitting it is also defensible.
  *Blocks:* nothing technically, but the answer changes every dated document, so it is cheaper
  to settle before rendering.
  → `education[Universitatea Babes-Bolyai].x_listing_decision`

- [ ] **8. English — exact CEFR level (C1 or C2), and any certificate to cite.**
  Currently rendered as "Advanced" with no CEFR code. *Blocks:* the Europass language grid,
  which requires a level; and an unevidenced "C2" is precisely the kind of claim this system
  exists to prevent.
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
  What is still missing is only the **end month**. The owner gave a *duration*, not an end date.
  About two years from May 2021 rules version A's Jul-2022 end out and places the end somewhere
  in **2023**, but that is **INFERRED** and must not be typed into `endDate`.
  *Blocks:* **the render still fails closed on the date.** `endDate` remains the literal string
  `TODO-CONFIRM` on purpose, so no document can ship a guessed date; the duration renders as
  prose ("about two years, on and off") in the first highlight instead.
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

- [ ] **13. Reframe — public URL (repository or releases page), whether it has a LICENSE file,
  and one sentence saying what it does for a non-technical reader.**
  *Blocks:* a reviewer cannot verify the nine signed releases or the 100% coverage gate without
  a link, and the coverage claim is one of the strongest engineering signals here.
  → `projects[Reframe]`

- [ ] **14. ZHMModSDK — upstream repository URL and the merged pull-request link.**
  *Blocks:* this is the **only** genuine third-party open-source credit on the profile
  (518 lines across 7 files, merged by the maintainer, 282-star SDK). Unlinked, it is just an
  assertion; linked, it is checkable in seconds.
  → `projects[ZHMModSDK]`

- [ ] **15. Personal-Finance-Management — complete the three remediation items, then supply the
  repo URL.**
  1. Rename package and classes off `com.preethi.thrifty`.
  2. Remove the "all rights reserved" line.
  3. README states it began from an uncredited template and has since diverged.

  *Blocks:* the repo URL. The project stays on the CV either way, described honestly (G-10) —
  no claim of 100% originality, no naming of any other author.
  → `projects[Personal-Finance-Management].x_required_remediation`

- [ ] **16. tracelines — what is it, in one sentence? Status (shipped / prototype / abandoned)?
  Public URL and LICENSE?**
  *Blocks:* **it renders on no view at all** until answered. There is currently no verified
  description of it anywhere. No download or adoption figure may ever be cited for it.
  → `projects[tracelines]`

- [ ] **17. llm-anthology — same three questions as above.**
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

---

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
