# Verified facts base — resume project

Established 2026-09-23 by direct check in the main session. Every line below was
observed, not inferred, unless marked INFERRED. Downstream agents and documents
must not contradict this file without new evidence.

## Identity

| Fact | Value | How verified |
|---|---|---|
| Legal/display name | Andrei Mihai Visalon | GitHub API `users/Prekzursil` → `name`; ORCID record gives "Andrei Visalon" (no middle name) |
| ORCID iD | 0009-0001-8776-8498 | `pub.orcid.org/v3.0/.../record` returned 200 |
| Institutional email | andrei-mihai.visalon@s.unibuc.ro | ORCID record, `person.emails` |
| Personal email | prekzursil1993@gmail.com | session environment |
| Location | Romania | GitHub profile `location` |
| GitHub | github.com/Prekzursil | API |
| LinkedIn | linkedin.com/in/andrei-mihai-visalon-03141b170 | ORCID `researcher-urls` |

**Name inconsistency, unresolved:** ORCID stores given-names "Andrei", family-name
"Visalon". GitHub stores "Andrei Mihai Visalon". No diacritics appear in either.
Whether the legal Romanian form carries diacritics is unknown and he must confirm.
This must be made consistent across resume, ORCID, LinkedIn and GitHub.

## Education — RESOLVED BY THE OWNER 2026-09-23

**Owner's statement, authoritative:** Titu Maiorescu was the previous university,
where he did the Bachelor's. The graduate degree, a Master's, is at the University of
Bucharest.

So the correct structure is:

| Level | Institution | Status |
|---|---|---|
| Bachelor's, Computer Science | Titu Maiorescu University, Bucharest | Completed. Dates still need confirming, the two CVs say May 2025 and May 2024 |
| Master's | University of Bucharest, Faculty of Mathematics and Informatics | IN PROGRESS. This is why the s.unibuc.ro address is live |
| Bachelor's, Computer Science (incomplete) | Universitatea Babes-Bolyai, Cluj-Napoca, Sep 2021 to Jul 2022 | One year, not completed, preceded Titu Maiorescu. Listing decision pending |

**This changes the positioning materially.** He is not a BSc graduate with no further
study. He is a CURRENT MASTER'S STUDENT at a state university, holding a completed
BSc from a private one. "Current MSc student, University of Bucharest" is a stronger
and more accurate headline than anything derived from the bachelor's alone.

**It also means the stated academic target is probably PhD, not MSc.** He selected
"academic MSc/PhD applications" as a goal while already enrolled in a Master's. The
academic CV should therefore be built for doctoral applications, or for a second or
different Master's. He should confirm which.

**DEFECT FOUND IN HIS ORCID RECORD.** ORCID currently lists the Bachelor's in Computer
Science as awarded by the University of Bucharest, 2022 to 2025. That is wrong on the
institution. The Bachelor's was Titu Maiorescu; UniBuc is the Master's. ORCID is the
identifier his future paper bylines will carry and it is publicly readable, so a
reviewer cross-checking would find a CV that disagrees with his own public record.
He should correct ORCID to show two separate affiliations. Action required, his to
take.

### Superseded conflict record, kept for audit

The following two sources disagreed before the owner resolved it. Retained so the
dead end is not re-walked.

| Source | Institution | Dates |
|---|---|---|
| ORCID record, `educations` | University of Bucharest, Faculty of Mathematics and Informatics | 2022 to 2025 |
| CV #1 (2023-03-06) | Titu Maiorescu University, Bucharest | Oct 2022 to May 2025 |
| CV #2 (hipo.ro, updated 2023-07-05) | Titu Maiorescu, Bucuresti, Licenta Informatica | Oct 2022 to May 2024 |
| CV #1 only | Universitatea Babes-Bolyai, Cluj-Napoca, Bachelor's Computer Science | Sep 2021 to Jul 2022 |

Complications:
- His institutional email is `andrei-mihai.visalon@s.unibuc.ro`, which is a University
  of Bucharest address. Titu Maiorescu is a separate private university and does not
  issue `s.unibuc.ro` addresses. So UniBuc enrolment of some kind is real.
- The two CVs disagree with each other on the end date, May 2025 versus May 2024.
- The Babes-Bolyai entry appears on CV #1 only, runs one academic year, and is
  labelled a Bachelor's degree. It reads like a started-and-left first year.
- Plausible reconciliations, none confirmed: he transferred between institutions; he
  did the BSc at one and a master's or a second programme at UniBuc; or the ORCID
  entry is aspirational or mis-entered. HE MUST CONFIRM.

**Correction to an earlier entry in this file:** the previous version recorded
University of Bucharest 2022-2025 as verified. What was actually verified is what the
ORCID record *says*. That is not the same as verifying which university he attended.
The distinction matters and the earlier label was too strong.

## Publication position

- **ORCID works count: 0.** Verified directly. Also zero fundings, zero peer reviews.
- INFERRED: unregistered output may exist. Being checked by the academic harvest agent.

## GitHub corpus

- 68 public repos. Account created 2019-08-28. 7 followers.
- Empty bio. No blog or website set. Both are free wins currently unclaimed.
- Highest star count on any repo: 4 (Reframe). Three repos at 1 star. The rest at 0.
- Original (non-fork) repos, most recently pushed first:
  agent-skills-toolchain, TanksFlashMobile, WebCoder, bilbo-app,
  codeblocks-pretty-prints-stable, llm-anthology, momentstudio, pbinfo-scrape,
  Airline-Reservations-System, Reframe, quality-zero-platform, SWFOC-Mod-Menu,
  DevExtreme-Filter-Go-Language, env-inspector, Personal-Finance-Management,
  Star-Wars-Galactic-Battlegrounds-Save-Game-Editor, omniaudit-mcp,
  grace-iberlef-2026, abbyy-finereader-ocr-mcp, tracelines.
- Roughly 48 of the 68 are forks and carry little resume weight unless he made
  substantial contributions to them.

**Known data-quality defect:** `Airline-Reservations-System` is tagged language
Python while its description says "C++ App + GUI". A reviewer who opens it will
notice. Resolve before any link to it appears on a resume.

## Declared scope (owner answers, 2026-09-23)

1. **Work history:** has employment or internship experience AND separately has
   freelance/contract client work. **None of it is documented anywhere on this
   machine or in any public profile.** Must be extracted by interview.
2. **Target:** three purposes at once — software/AI engineering roles, academic
   MSc/PhD applications, and a maintained master kept current.
3. **Geography:** Romania, local market. A4. Photo conventional. Romanian-language
   variant is a live question.
4. **Timeline:** none. Building the system, gap-closing work in scope.

## basic-memory vault on D:

| Metric | Value |
|---|---|
| Note files | 714 (713 markdown) |
| Notes total size | 2.20 MB |
| Cache files inside vault (`.hf`, `.models`) | 169 files, 14,174.85 MB |
| Frontmatter present | 713 of 713 (100%) |
| Permalink present | 713 of 713 (100%) |
| `valid_as_of` present | 86 (12%) |
| `superseded_by` present | 2 |
| `- [decision]` / `- [fact]` observations present | 115 (16%) |
| Wikilinks present | 317 (44%) |
| Notes over the 100 KB contract limit | 0 |

Note mtime distribution: 277 in 2026-06, 121 in 2026-07, 90 in 2026-08, 225 in 2026-09.

**Daemon state:** `127.0.0.1:18765` has no listener. `C:\Users\Prekzursil\.basic-memory`
does not exist, so neither `config.json` nor `memory.db` is present. The vault FILES
arrived today at 12:11 via extraction of `resume-vault.tar` (883 files, per
`C:\suite\import-resume.log`). INFERRED: the ECONNREFUSED is a missing client config
and index after a partial restore, not vault loss. Under audit.

**Contract violations, measured against `~/.agents/memory-contract.md`:**
- The contract states a note with neither observations nor links is a failed write.
  84% lack observations and 56% lack wikilinks.
- The contract states transcripts and compaction dumps stay out of ingest. The vault
  contains `compaction-checkpoints/` (102 files), `sessions/` (35) and
  `claude-memory/` (157). Whether these are the same thing the contract excludes is
  under audit.
- `index/WHERE.md` inside the vault states the daemon is on port **8765**, while the
  external WHERE-map and the live config say **18765**. One of them is stale.

## Tooling already on this box

- `cv-studio` skill at `~/.agents/skills/cv-studio` — claims one `profile.yaml`
  (JSON Resume superset) produces an ATS PDF via RenderCV plus tailor, cover letter
  and LinkedIn modes, with zero-fabrication linting that requires every bullet to
  trace to an `x_master` achievement bank and every number to an `x_metrics` block.
  Its stated core insight matches the problem here: a CV is two artifacts with
  opposite constraints, and the submitted one must be typeset single-column rather
  than designed as a graphic. Whether it actually runs on this box is under evaluation.

## Recovered from two prior CVs (2023), supplied by the owner

Files at `C:\Users\prekzursil\Downloads\attachments`. Three files, two distinct
documents: `CV Andrei-mihai Visalon #1.pdf` and `#1-1.pdf` are byte-identical
duplicates, SHA-256 `7354965852D7...`.

**Both CVs are from 2023 and are roughly three years stale.** They predate almost the
entire GitHub portfolio. Treat them as a source of biographical facts and employment
history, not as a model for the new document.

### Personal data
| Field | Value |
|---|---|
| Name as written | Andrei-Mihai Visalon, HYPHENATED in both CVs and in the institutional email |
| Date of birth | 8 June 2002 |
| Place of birth | Ramnicu Valcea, judet Valcea |
| Address on CV #1 | Antim Ivireanu 15, 240113 Ramnicu Valcea |
| Phone | +40 740 935 228 |
| Email then in use | a_visalon@yahoo.com |
| Driving licence | Yes |
| Languages | English advanced across read, write, speak. Romanian native-level |

**Kills an earlier inference.** The design agent reasoned that the personal Gmail
handle broadcasts a birth year of 1993 and therefore signals a non-traditional path.
His date of birth is 2002. That reasoning is dead. The recommendation to use a
name-based address still stands on its own merits, since both the Gmail handle and
the Yahoo address read as personal rather than professional.

### Employment — the first real evidence of work history
Same employer described two different ways across the two CVs:

| | CV #1 (Mar 2023) | CV #2 (hipo.ro, Jul 2023) |
|---|---|---|
| Title | Web Developer | Freelancer Informatica |
| Employer | Dinu Plast, Ramnicu Valcea | Dinu Plast, Bucuresti |
| Dates | May 2021 to Jul 2022 | May 2021 to Jun 2023, stated as 2 years 1 month |
| Work | Built a website, customized a ledger software | Contracted for the duration of site development and building the management software network |
| Sector | not stated | IT Software. Company sells wholesale plastics |

**Two unresolved conflicts he must settle:** the end date, Jul 2022 versus Jun 2023,
and whether this was employment or a freelance contract. The hipo.ro version says
freelance and contracted, which matches his statement that he has freelance work.
Note also that the stated duration of 2 years 1 month does not match either date
range cleanly.

### Achievement worth verifying
Pbinfo.ro competitive programming: CV #1 claims he "ranked 2nd all time solved
problems (currently)" as of March 2023. This is concrete, distinctive, externally
checkable, and unlike most of his portfolio it is third-party scored rather than
self-reported. He also owns `pbinfo-scrape` and `pbinfo-get-unsolved` repos and a
`pbinfo-python-jit` skill. Under verification.

### Stale or discardable
- Salary expectation of 1000 EUR, from 2023 as a student.
- Gender, nationality, marital status, full street address, date of birth. All
  present on CV #1 and all should be removed from the new documents.
- "Looking to work in the IT domain" as a summary line.
- Skills listed as only C, C++, Python. Three years out of date.

## Open questions only the owner can answer

1. Employment and freelance history in full. Blocking; nothing can be drafted without it.
2. Whether his legal name carries Romanian diacritics.
3. Where this project should live permanently on disk.
4. Which MSc/PhD programmes and which job targets, since tailoring depends on it.
