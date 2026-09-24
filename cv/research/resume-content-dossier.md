# Resume content dossier — Andrei-Mihai Visalon

Written 2026-09-23. This is the *content* file: what actually goes in the two documents,
grounded only in claims that survived verification.

**Labels used throughout.** Every factual line carries one:

- **VERIFIED** — observed this session by an agent that fetched or ran it, with the evidence
  path named. Paths are relative to this scratchpad unless absolute.
- **INFERRED** — reasoning on verified facts. Mine unless attributed.
- **COULD NOT DETERMINE** — nothing on disk settles it. Never filled from general knowledge.

**Checkability marks on bullets.** Every draftable bullet is tagged:

- `[CHECK: public]` — a stranger can verify it from a URL, no login, in under a minute.
- `[CHECK: on request]` — he can demonstrate it live, but a stranger cannot verify it alone.
- `[CHECK: no]` — not independently verifiable. A number must never appear on such a bullet.

**Confidence bands** follow WEP: *likely* 55-80 %, *very likely* 80-90 %, *almost certain* 90-99 %.

**Standing caveat.** The harvest files were written by AI agents about work largely done by AI
agents. Where a number here came only from a harvest or a vault note, it is marked and is not
used in a bullet. Where a verification lane re-measured it this session, that is said.

---

## 0. The four things that must happen before either document is sent

These are not gaps (section 7 has those). They are blockers on the *content* of the documents.

1. **The Experience section cannot be drafted from disk.** The only documented engagement on
   this machine is DINUPLAST SRL, and his two 2023 CVs disagree with each other about the title,
   the dates and whether it was employment or freelance (VERIFIED: `VERIFIED-FACTS.md`
   §Employment). Everything else — salaried, internship and freelance — is undocumented anywhere,
   public or local. Section 2.3 gives the bullet *shape* and the exact facts he must supply; it
   cannot give the bullets.
2. **The ORCID education entry is wrong and public.** It names the University of Bucharest as the
   awarder of the bachelor's; Titu Maiorescu awarded it (VERIFIED: `verified-academic.md` §6;
   `VERIFIED-FACTS.md`). It is attached to the identifier his preprint byline carries, so it is a
   cross-checkable contradiction of any honest CV. Fix before the CV exists, not after.
3. **The Codabench identity question is unanswered.** The GRACE Track-1 entry that scored 0.368
   was filed by account `alexcristea72` under team `bionlp` (VERIFIED: leaderboard pulled live,
   `cb_ph_26223.json`; `verified-academic.md` §4b-4c). His own Kaggle handle is `prekzursil`. Until
   he says whether that account is his or a teammate's, **no placement claim may appear on either
   document**, and neither may the word "solo".
4. **The name is hyphenated.** *Andrei-Mihai Visalon* is the legal and canonical form (owner
   ground truth). ORCID stores "Andrei Visalon", GitHub stores "Andrei Mihai Visalon", and his git
   history carries at least six author identities plus `Test <test@example.com>` as a visible
   contributor on `bilbo-app` (VERIFIED: `verified-github.md` §8). One name, one spelling, on the
   CV, ORCID, LinkedIn, GitHub and every future commit.

---

## 1. Positioning

### 1.1 The three positionings the evidence actually supports

**P1 — "Software engineer who ships and verifies" (backend / developer tooling), with applied-AI
as the specialisation.**

What carries it: a live production system with a real client (momentstudio.ro, VERIFIED by live
HTTP, `verified-github.md` §3); a cross-platform desktop application with 9 published releases and
downloadable installers (VERIFIED, `verified-programs.md` §1.7); a 100 % line-and-branch coverage
gate that is real, enforced and green (VERIFIED, `verified-github.md` §6); 526 test files countable
by anyone in one repo; and a six-month record of 1,016 commits / 351 PRs / 291 merged / 32,500+ CI
runs on one public monorepo (VERIFIED, `verified-tooling.md` §4).

What it costs: the AI-infrastructure work — which is the largest and most distinctive body of work
he has — becomes a *specialisation line* rather than the headline.

**P2 — "Applied AI / agent-infrastructure engineer."**

What carries it: 18 MCP servers written with ~48.7K non-blank LOC and ~85 test files
(VERIFIED by directory-level measurement, `verified-tooling.md` §2.2); three lazy, name-preserving
MCP multiplexers that collapse ~500 backend tools behind three client registrations — and which
the verifying agent could confirm first-hand because all three were live in its own session
(VERIFIED, `verified-tooling.md` §2.3); a 72-module lifecycle hook set (33.8K implementation lines,
27K test lines, 1,076 test functions) wired to 44 hooks across 20 events (VERIFIED, §3.1-3.2); a
provider-neutral harness at 873/890 passing on a restored box (VERIFIED — the agent ran it, §3.3);
~140 authored agent skills surviving every falsification test (VERIFIED, §1.3).

What it costs: this is the lane where the AI-authorship question bites hardest, where nothing has
external adoption (0 stars, 0 forks, 0 watchers on the flagship monorepo — VERIFIED), where the
flagship repo's CI is red on main (9 failures in the last 20 `quality` runs — VERIFIED, §4.1), and
where four of the biggest-sounding numbers in his own notes are unsupported and must be dropped
(section 5). The market is real — but the screen is "show me an eval, a cost figure and a
postmortem", not "show me a fleet" (`research-ai-eng-hiring.md` §4).

**P3 — "Algorithmically strong computer scientist with a research record in flight."**

What carries it: #1 all-time on pbinfo.ro with 4,244 problems solved at full score, third-party
scored, publicly checkable, no login (VERIFIED live + two Wayback captures,
`conflict-resolution.md` Conflict 2); 88 problems authored or co-authored on the same platform; a
sole-author ChemRxiv preprint with an authenticated ORCID (VERIFIED via Crossref,
`verified-academic.md` §1); a CC BY 4.0 Zenodo deposit whose SHA-256 manifest was independently
re-verified at 630/630 files, 0 mismatches (VERIFIED — the agent downloaded and recomputed, §2);
a merged C++ feature in a 282-star SDK (VERIFIED, `verified-github.md` §4).

What it costs: it answers "can you think" and not "can you ship", which is the question the
Romanian junior market is currently asking (`wave2-romania-market.md` H1).

### 1.2 Recommendation

**Lead with P1. Carry P2 as the specialisation inside it. Carry P3 as the opening credential.**
Confidence: *likely* (60-75 %).

Why, and where the confidence comes from:

- Romanian employers in 2026 are buying demonstrated delivery rather than potential: 31 % of ANIS
  members reduced junior roles in 2025, only 18 % of tech postings target entry level, and the
  practitioner reading is that companies "continuă să angajeze juniori, însă într-un ritm mai lent",
  prioritising practical delivery (VERIFIED sources, `wave2-romania-market.md` H1). P1 is the
  positioning that answers that filter directly, and momentstudio.ro is the single artifact that
  answers it best.
- Volume metrics actively discredit adjacent honest claims. A reviewer who sees "1,590 merged PRs"
  next to 7 total stars and 10 external merges discounts the whole document
  (`verified-github.md` §7.6). P2 as a *headline* invites exactly that reading; P2 as a
  *specialisation supported by a verification story* does not.
- The band is 60-75 % and not higher because the decisive input is inference, not measurement.
  Nothing on disk measures how Romanian hiring managers respond to an agent-infrastructure
  headline. The market file's only relevant datum is that recruiters "look mainly at experience and
  studies (>85 %) and location" (BestJobs 2023 survey), which is not broken down finely enough to
  settle this (`wave2-CORRECTION.md` §6). COULD NOT DETERMINE.
- The band is not lower because P1's evidence is the part of his record that survives a hostile
  check best: a live URL, a live health endpoint, a live catalogue, published installers, a green
  badge and a committed threshold file. Those are the five things a reviewer can confirm without
  talking to him.

**Do not use as a title:** "AI orchestrator", "prompt engineer", "vibe coder", "ChatGPT power
user". The last is listed as an automatic red flag by a hiring-manager source
(`research-ai-eng-hiring.md` §4).

### 1.3 How the positioning differs between the two documents

| | Engineering resume | Doctoral CV |
|---|---|---|
| **The question it answers** | "Can you ship, and would you be trusted with a service?" | "Will this person hand me a fabricated result?" |
| **Lead section** | Summary → Experience → Projects | Education → Research |
| **Hero artifact** | momentstudio.ro (live production, real client) | the ChemRxiv preprint (sole-author, DOI, dated) |
| **Register** | argument; quantified outcomes; one specific technical decision per bullet | inventory; no self-description; status labels on everything (`wave2-academic-cv.md` §1.1, §1.3) |
| **Summary paragraph** | yes, 3 lines (90 % of hiring managers say a clear summary speeds evaluation — Resume Genius 2026, `research-format-2026.md` §5) | **no**. Academic CVs carry no objective or summary (UNC TIBBS, Nature 38-tips; `wave2-academic-cv.md` §1.1) |
| **ORCID iD in header** | **omit** while it lists zero works (`research-opensource-credibility.md` §5) | include — but only after the two works are attached (kill item K25) |
| **pbinfo** | one line, high, as raw-ability evidence | one line, low, reframed around the 88 authored problems |
| **Agent infrastructure** | a specialisation, with the verification layer as the point | a *methods* line, not an achievement line |
| **Length** | one dense page, 475-600 words, 18-28 words per bullet (`research-metrics-language.md` §4.8) | 2-3 pages for an application; the master record can be longer (`wave2-academic-cv.md` §1.2) |
| **Photo / DOB / marital status** | never | never in the international rendering; the Europass export follows Europass |

The binding gate on the doctoral side is a **supervisor's written agreement** — without one he is
rejected regardless of mark (VERIFIED: SDI Art. 10(1), UB Art. 21, read from the scans;
`wave2-CORRECTION.md` §5.1). The publication list is optional in the dossier ("dacă există") and is
only a tie-breaker in the ranking. So the doctoral CV is not a scoring document. It is a document
whose entire job is to make one named academic reply to one email. Build it for that.

---

## 2. The engineering resume, section by section

**Structure and order** (from `research-format-2026.md` §5 and §8, adjusted for the corrected
education): Header · Summary · Experience · Projects · Open-source contributions · Competitive
programming · Skills · Education · Languages. Headings exactly `Experience`, `Projects`, `Skills`,
`Education` — every parser and every source recognises them.

Single column. A4 for EU/RO, Letter for US. 10.5-11 pt standard font. Name and contact as body
text on line one, never in a header or footer or text box. Text-based PDF under 1 MB.
(All VERIFIED-PRIMARY vendor guidance, `research-format-2026.md` §7.)

### 2.1 Header

```
Andrei-Mihai Visalon
Bucharest, Romania  ·  +40 7xx xxx xxx  ·  <name-based email>
linkedin.com/in/andrei-mihai-visalon-03141b170  ·  github.com/Prekzursil
```

Decisions baked in:

- **No photo** on the default version. Practice in Romania is genuinely split and declining in
  tech; 9 independent Romanian sources say optional, and every verified multinational portal has
  no field for it (VERIFIED, `research-romania-eu.md` §1). A second photo-bearing variant is a
  choice for traditional local employers, not a requirement.
- **No date of birth, no place of birth, no address beyond the city, no marital status, no gender,
  no nationality line, no CNP, no driving licence, no salary expectation.** All of these appear on
  his 2023 CV #1 (VERIFIED, `VERIFIED-FACTS.md`) and all must come off. eJobs hides candidate age
  from employers by design; age, sex and family responsibility are protected criteria under Labour
  Code art. 5(2) and OG 137/2000 art. 7 (VERIFIED primary texts, `research-romania-eu.md` §2-3).
- **Nationality appears only as a work-authorisation line on international versions:**
  "EU citizen (Romania); no visa sponsorship required." (`research-romania-eu.md` §11.)
- **Email.** Both addresses on record read as personal: `prekzursil1993@gmail.com` and the 2023
  `a_visalon@yahoo.com`. Use a name-based address. Do **not** use `andrei-mihai.visalon@s.unibuc.ro`
  as the only address on an engineering resume: it signals current UB affiliation, which is true and
  useful, but it lapses when the master's ends (INFERRED). Listing both is acceptable.
- **No ORCID** on this document while the record holds zero works. A reviewer who clicks sees an
  empty page (VERIFIED: `/works` returned zero groups live, `verified-academic.md` §6).
- The phone number is from the 2023 CV. He must confirm it is still live before it ships.
  COULD NOT DETERMINE.

### 2.2 Summary (3 lines)

**Default / backend-and-tooling version:**

> Software engineer working on backend services and developer tooling. MSc Computer Science
> student at the University of Bucharest; BSc Computer Science, Titu Maiorescu University, 2025.
> Built and deployed a bilingual production e-commerce platform for a client (FastAPI + Angular,
> live at momentstudio.ro) and a cross-platform desktop application released under a 100 %
> line-and-branch CI coverage gate; ranked first all-time on pbinfo.ro with 4,244 problems solved
> at full score (Sep 2026).

`[CHECK: public]` — every clause resolves to a URL: momentstudio.ro, the Reframe releases page,
the committed `.coverage-thresholds.json`, pbinfo.ro/top100.

**Applied-AI version** (use when the posting is an AI/ML/agent role):

> Software engineer specialising in agent infrastructure and the verification layer around
> AI-generated code. MSc Computer Science student, University of Bucharest; BSc Computer Science,
> Titu Maiorescu University, 2025. Wrote 18 Model Context Protocol servers (~49K lines, ~85 test
> files), including three lazy multiplexers that collapse several hundred backend tools behind
> three client registrations, and enforce a closed six-gate deterministic CI across the platform.

`[CHECK: on request]` for the LOC and test-file counts (measured on his machine — he can rerun the
count live); `[CHECK: on request]` for the multiplexers (he can start a session and show the tool
surface — `verified-tooling.md` §2.3 calls this the best-evidenced claim in the whole lane).

Do **not** write "passionate", "results-driven", "dynamic", "leveraged", "spearheaded". Do not
write a generic objective. (`research-metrics-language.md` §4.6, §4.11.)

### 2.3 Experience — the blocked section

This section is the one every source ranks first and it is the one that cannot be written from
disk. Nothing beyond DINUPLAST exists anywhere on this machine or in any public profile
(VERIFIED absence, `VERIFIED-FACTS.md` §"Declared scope").

**Entry 1 — DINUPLAST SRL. He must pick one variant; his two 2023 CVs disagree.**

| | CV #1, Mar 2023 | CV #2, hipo.ro, Jul 2023 |
|---|---|---|
| Title | Web Developer | Freelancer Informatică |
| Dates | May 2021 – Jul 2022 | May 2021 – Jun 2023 (stated as "2 years 1 month" — which matches neither range) |
| Work | built a website; customised a ledger software | contracted for site development and building the management software network |

The company is real: DINUPLAST SRL, CUI 16367462, registered 26 April 2004, Râmnicu Vâlcea,
"în funcțiune" (VERIFIED across eight business directories, `conflict-resolution.md` Conflict 3).
It has **no findable website** and the site he built is not recoverable (VERIFIED absence). So this
entry can never carry a link; it must carry specifics instead.

Bullet shape, with the facts he must supply in braces:

```
Web Developer  (or: Freelance Developer — DINUPLAST SRL, client) — Râmnicu Vâlcea, Romania
{May 2021 – Jul 2022}

- Built and launched the company's first website: {what it replaced}, {stack}, {pages/sections},
  {who maintained it afterwards}.                                              [CHECK: no]
- Customised the {named} ledger/ERP software for {the specific operation it had to support};
  {what changed for the people using it}.                                      [CHECK: no]
- {If true} Set up {the network / the deployment / the backups}: {what was there before}.
                                                                               [CHECK: no]
```

Three rules for this entry. (a) No number goes on any of these bullets — nothing is measurable and
nothing is verifiable, and a number he cannot source is worse than no number
(`research-metrics-language.md` §4.3). (b) The *nouns* carry the credibility: the ledger software's
actual product name, the actual hosting, the actual thing the network connected. A reviewer can
tell whether a person did the work from the nouns alone
(`research-opensource-credibility.md` §3 item 3). (c) He settles the dates and the employment form
once and uses that everywhere, including LinkedIn — the resume is cross-checked against LinkedIn
routinely (`research-opensource-credibility.md` §4).

**Entry 2 — everything else. Blocked pending interview.** The intake script for extracting it is
already written at `wave2-intake-script.md`. For each engagement he needs: legal employer name,
city, his exact title, start and end month, employment form (contract de muncă / PFA / SRL /
internship / unpaid), what the thing was, what he personally owned, one measurable outcome, and
whether anyone there would confirm it.

**Entry 3 — the independent-work entry. Use it, but only under a strict frame.**

A self-declared entry for the 2025 – present period is the recommended shape for a
portfolio-heavy new grad (`research-new-grad-2026.md` §12), and it is defensible here because every
bullet under it points at a public artifact. It is *not* a job and must not be titled as one.

```
Independent Software Engineer and Open-Source Maintainer — Bucharest  ·  2025 – present

- Designed, built and deployed momentstudio.ro, a bilingual RO/EN e-commerce platform in
  production for a client: FastAPI backend and Angular storefront, a live catalogue of 16
  products with SEO metadata, inventory thresholds and backorder handling; interactive API
  docs disabled in production.                                              [CHECK: public]
  (catalogue size and schema read live from /api/v1/catalog/products — verified-github.md §3)

- Author and maintainer of Reframe, an offline-first desktop video application (Electron/React
  renderer over a Python sidecar via stdio JSON-RPC): 9 published releases carrying installers
  for Windows, macOS and Linux.                                              [CHECK: public]
  (GitHub releases API: 9 published releases, 17 tags — verified-programs.md §1.7)

- Enforce 100 % line-and-branch coverage as a blocking CI gate on that codebase (526 test files
  across the Python and TypeScript trees), with mutation testing (mutmut/Stryker) kept
  deliberately non-blocking and surviving mutants documented as equivalent rather than
  suppressed.                                                                [CHECK: public]
  (public repo tree: 264 Python + 262 TS/JS test files; .coverage-thresholds.json committed at
   repo root — verified-programs.md §1.9, verified-github.md §6)

- Sole author and maintainer of a public agent-platform monorepo: 1,016 commits, 351 pull
  requests (291 merged) and 32,500+ CI runs between March and September 2026.  [CHECK: public]
  (GitHub REST: commits Link rel=last page 1016; search/issues; actions/runs total_count
   32,554 — verified-tooling.md §4)

- Published two Python packages on PyPI (tracelines, llm-anthology) and a companion npm CLI
  (tracelines).                                                              [CHECK: public]
  (verified-github.md §5 — PyPI and npm both return 200; make no adoption claim, see K1)
```

Note on the fourth bullet: 61 of those 1,016 commits are from `cursoragent`, his own AI background
agent (VERIFIED, `verified-tooling.md` §4). That is fine and does not change the line — but it
pairs with the disclosure discipline in section 6, and he should volunteer it rather than be found
out.

### 2.4 Projects (3-4, reordered per posting)

Order by relevance to the posting. Each: name, one-sentence purpose, stack, a measured outcome, a
plain-text link **only where section 5.3 clears the link**.

**P-1 · momentstudio.ro — production e-commerce (FastAPI, Angular, PWA)**
> Bilingual RO/EN storefront built and deployed for a client and live in production. FastAPI
> backend with a live health endpoint and a real commerce schema (SKU, base price, currency,
> low-stock threshold, backorder flag, SEO title/description, featured collections, dimensioned
> products); Angular storefront with critical-CSS inlining and a PWA manifest. Interactive API
> docs disabled in production.
>
> `[CHECK: public]` — momentstudio.ro, /api/v1/health, /api/v1/catalog/products.
> **Do not send the GitHub link until the branches are pruned** (63,363 remote branches, of which
> 63,116 are `cursor/*`, plus 89 `rescue/*` tags surfacing on the Releases page — VERIFIED,
> `verified-github.md` §3). The live site is the better link anyway.

**P-2 · Reframe — cross-platform desktop video application**
> Local-first desktop application: Electron/React renderer over a Python sidecar communicating by
> stdio JSON-RPC. 9 published GitHub releases across two product lines, each carrying downloadable
> installers for Windows, macOS and Linux. 100 % line-and-branch coverage enforced as a blocking
> CI gate; 526 test files; mutation testing tracked separately and non-blocking.
>
> `[CHECK: public]` — releases page, `quality.yml`, `.coverage-thresholds.json`.
> Two things a reviewer will notice and he should pre-empt: the repo has **no LICENSE** (only a
> `NOTICE` file), and the v1.4.0 Windows installer is named `media-studio-1.4.0-win-x64.exe`, so
> the shipped binary carries a different product name than the repo (both VERIFIED,
> `verified-github.md` §1, §2). Add a LICENSE and rename the artifact, or expect the question.

**P-3 · GRACE @ IberLEF 2026, Track 1 — Spanish clinical argument mining** *(AI/ML postings only)*
> 27-cell controlled sweep — 9 Spanish and multilingual clinical encoders × 3 seeds — run in one
> parallel pass on serverless GPU, scored with the organisers' script, with mean and standard
> deviation reported per model rather than a best seed. A softmax-probability-averaging ensemble
> chosen without dev-set model selection reached **0.743 dev strict macro-F1**, against 0.705
> ± 0.035 for the best backbone averaged over three seeds (best individual run 0.737). Produced a
> fully offset-validated blind-test prediction file: 11,752 components over 2,474 abstracts, zero
> offset mismatches.
>
> `[CHECK: on request]` — the JSON is in a public repo, but the repo's front page is a different
> project's README, so until that is fixed the link costs more than it returns
> (`verified-academic.md` §4e).
> **Never** "competed in", "placed", or any rank. **Always** say "development set". **Always**
> carry the seed-mean qualifier — the raw JSON is public and an ML interviewer who opens it finds
> 0.737 and asks why the headline says +3.9 points. Say it first.
> Scale caveat he should volunteer before being asked: dev is 50 abstracts and the ensemble's
> MajorClaim cell is tp=4 / fp=4 / fn=5 (VERIFIED, `verified-academic.md` §4e).

**P-4 · Agent infrastructure** *(prose; no repo link)*
> Wrote 18 Model Context Protocol servers in Python and TypeScript (~49K non-blank lines, ~85 test
> files) spanning cloud, social, search, scientific-computing and OCR backends, plus two hardened
> forks of community servers. Three of them (cloud, search, social) are lazy, name-preserving
> multiplexers that collapse roughly 500 backend tools behind three client registrations, cutting
> per-session MCP process and context overhead.
>
> `[CHECK: on request]` — he can start a session and show the tool surface. This is the most
> demonstrable claim in the whole tooling lane (`verified-tooling.md` §2.3).
> **Do not link `agent-skills-toolchain`**: CI red on main, 237 MB (measured), committed browser-profile
> binaries, and a public repo whose own description opens "Private platform repo"
> (VERIFIED, `verified-github.md` §8; `verified-tooling.md` §4.1).
> Use "about 500" for the tool count, never an exact figure — the number comes from the servers'
> own READMEs and was not enumerated independently.

**P-5 · WebCoder — online judge platform** *(prose only, no link, until a README exists)*
> Django backend, React/Next.js frontend, containerised code-judging sandbox. Led an
> AI-agent-assisted modernisation from Create React App to Next.js 15 (App Router, TypeScript, 14
> routes), containerised the judging sandbox, added CI coverage gates, and fixed a latent
> object-permission defect (`obj.author` → `obj.user`) that raised an `AttributeError` on every
> submission retrieve.
>
> `[CHECK: no]` as prose; `[CHECK: public]` only if he links the PR — and the PR is a **draft**
> whose title and body disagree by 11 tests (VERIFIED, `verified-programs.md` §1.10). Merge it or
> close it before linking. Never quote "295 tests"; never quote any line count from it (the 1.08 M
> deletions are a purged vendored `venv`).

### 2.5 Open-source contributions (short section, only merged or clearly labelled)

```
- ZHMModSDK (OrfeasZ/ZHMModSDK, 282 stars) — contributed TitaniumBullets, a C++ feature mod,
  merged by the maintainer on 11 Jan 2026 (+518 / -2 across 7 files, 6 commits). PR #241.
                                                                            [CHECK: public]
- metaswarm (dsifry/metaswarm, 419 stars) — submitted a performance fix: a session-start hook ran
  an unconditional plugin-cache scan whose result is only consumed inside a branch gated on a file
  that usually does not exist; reordering the check took it from ~140 s to ~0.3 s with identical
  behaviour inside real projects. Pull request #51, open.                    [CHECK: public]
- 10 pull requests merged into repositories owned by others.                 [CHECK: public]
```

Rules, all VERIFIED-derived:

- ZHMModSDK #241 is the **only** contribution on the profile a reviewer will count as genuine open
  source. It deserves its own line, not burial in a repo list (`verified-github.md` §4).
- metaswarm #51 is **open, not merged**. Say "submitted" or "open". Never "contributed to" or
  "merged" (`verified-programs.md` §1.11).
- For metaswarm, quote **~350** plugin.json files — the number in the public PR body. His local
  note says 529. He cannot quote 529 next to a link to a PR that says 350.
- "10 merged PRs into repos owned by others" replaces the 1,590 aggregate. 1,580 of the 1,590
  merges are on his own repositories where he is author, reviewer and merger (VERIFIED by four
  GitHub search queries, `verified-github.md` §4). Anyone who knows GitHub runs the `-user:` filter
  in seconds.

### 2.6 Competitive programming (one line — see section 4 for the full treatment)

```
- pbinfo.ro — ranked #1 all-time by problems solved at full score: 4,244 as of Sep 2026 (second
  place: 4,191); top three since 2022. Author or co-author of 88 problems published on the
  platform and 6 technical articles.                                          [CHECK: public]
```

### 2.7 Skills

Grouped on four plain lines, in the posting's exact terms. Skills lists are cheap talk — their job
is recruiter search, not persuasion (`research-metrics-language.md` §4.9; 76 % of recruiters filter
by skills). Everything listed must have a project story behind it.

```
Languages      Python · TypeScript / JavaScript · C++ · C# · Java · Kotlin · SQL
Backend / Web  FastAPI · Django · REST APIs · Angular · React · Next.js · Electron · Tauri
AI / ML        HuggingFace transformers · Modal (serverless GPU) · Model Context Protocol (MCP) ·
               agent harnesses (Claude Code, Codex CLI) · evaluation and ensembling
Testing / CI   pytest · vitest · Googletest · GitHub Actions · CodeQL · coverage and branch gates ·
               mutation testing (mutmut, Stryker) · ruff · basedpyright · gitleaks · osv-scanner ·
               Semgrep/opengrep · Docker
```

Grounding, so nothing here is invented (all VERIFIED from the `/languages` byte census,
`harvest-github.md` §3.2, and the per-repo table §2):

- Python 54.0 MB and TypeScript 15.6 MB dominate his own code; C# 4.7 MB (SWFOC-Mod-Menu), C++
  4.6 MB (SWFOC 4.4 + Airline 0.19), Kotlin 1.2 MB (bilbo-app), Java 0.31 MB (the Thrifty fork —
  see K22), Go 0.26 MB and Rust 0.49 MB.
- **Go and Rust are thin.** Go is one repo (DevExtreme-Filter-Go-Language) and Rust is the
  `llm-anthology` Tauri shell. Listing them invites a question he may not want. INFERRED
  recommendation: leave both off the default resume; add either only when the posting names it and
  he is willing to be asked.
- **Do not list PyTorch.** No verified evidence of it anywhere in the corpus. The GRACE work is
  described as transformer fine-tuning on Modal; say that.

### 2.8 Education

```
MSc Computer Science (in progress) — University of Bucharest, Faculty of Mathematics and
Computer Science, Bucharest  ·  Oct 2025 – expected 2027

BSc Computer Science — Titu Maiorescu University, Bucharest  ·  Oct 2022 – 2025

Computer Science (first year completed; transferred, no degree awarded) —
Babeș-Bolyai University, Cluj-Napoca  ·  Sep 2021 – Jul 2022
```

Decisions and their grounds:

- **The master's leads.** "Current MSc student at a state university, holding a completed BSc" is
  a materially stronger and more accurate headline than anything derived from the bachelor's alone
  (`VERIFIED-FACTS.md` §Education). It also explains the live `s.unibuc.ro` address.
- **Keep the Babeș-Bolyai year, explicitly labelled.** His LinkedIn already shows it
  (`conflict-resolution.md` Conflict 1). Omitting it from the CV creates a discrepancy a
  cross-checker sees, and an unexplained 2021-2022 reads worse than a stated incomplete year.
  Confidence: *likely*. The alternative — omit from both the CV and LinkedIn — is defensible but
  requires editing LinkedIn first.
- **The BSc end month is unresolved.** CV #1 says May 2025, CV #2 says May 2024, ORCID says
  2025-06-04. COULD NOT DETERMINE. He reads the diploma and uses one date everywhere.
- **Grades.** Include the licence general average only if it is strong on the 10-point scale and
  written as "9.1/10" (`research-format-2026.md` §5). It is also SDI tie-break (i) on the doctoral
  side, so he should know the number regardless.
- **Do not name the MSc programme** until he confirms it. LinkedIn's label is a platform string,
  not the programme name (`wave2-CORRECTION.md` §1.1). COULD NOT DETERMINE.
- **Relevant coursework, thesis title and supervisor**: all missing and all worth adding
  (`research-format-2026.md` §5 puts named relevant courses and a thesis title in the Education
  block for a recent graduate). COULD NOT DETERMINE — intake.

### 2.9 Languages

```
Romanian — native  ·  English — C1 (professional working proficiency)
```

His two 2023 CVs both state English advanced across read, write and speak (VERIFIED,
`VERIFIED-FACTS.md`). CEFR levels are expected in RO/EU CVs and cost nothing
(`wave2-romania-market.md` F1). He holds no verified certificate — and the doctoral dossier
requires a UB-accepted B2+ proof from every candidate (VERIFIED, UB Art. 14(1)(l);
`wave2-CORRECTION.md` §5.1), so obtaining one closes two gaps with one action.

Do **not** write "English — fluent" without a level, and do not claim C2 without a certificate.

---

## 3. The doctoral CV

Different document, different hierarchy, different register. Inventory, not argument. No summary
paragraph, no self-description, no photo, no birth date. 2-3 pages for an application.
(`wave2-academic-cv.md` §1.1-1.3.)

Order: **Education · Research experience · Publications and preprints · Data and software ·
Shared tasks and evaluation campaigns · Competitive programming and educational content ·
Technical skills · Languages · Identifiers.**

### 3.1 Education (leads)

Same three entries as §2.8, same order, plus — once they exist — the master's dissertation title
and supervisor, the bachelor's thesis title, supervisor and grade, and ECTS per degree. The ECTS
matter concretely: doctoral eligibility requires at least 300 ECTS cumulative across licence and
master's (VERIFIED, UB 2026 Art. 12(1)(b); SDI Art. 8(1)(b)), expected 180 + 120. He reads both
supplements and records the real numbers.

### 3.2 Research experience

Written as research entries — question, method, result, artifact — not as job bullets.

**Alchemical transfer free-energy validation of the phenibut GABA-B enantiomer preference**
(independent, 2026)

> *Question.* Does computational evidence support R-phenibut as the GABA-B eutomer at the sign
> level? *Method.* Two-sided alchemical transfer free-energy calculations across six production
> edges, each with its full per-replica data (22-23 output files per edge), with UWHAM
> reweighting; a companion validation edge and two controls. *Result.* Sign-level corroboration,
> explicitly scoped — the claim is the sign, not the magnitude. One mechanism was tested, did not
> survive the test, and is withdrawn in the text; the seed that failed to replicate is named.
> *Artifact.* Sole-author preprint (ChemRxiv, doi:10.26434/chemrxiv.15009306/v1) and a CC BY 4.0
> Zenodo deposit of all per-replica inputs with a SHA-256 manifest.
>
> `[CHECK: public]` — Crossref record, Zenodo record.
> Two stored UWHAM results reproduce the published numbers exactly (seed 2 ddG 0.63325 vs
> published 0.633; gabapentin to pregabalin 12.8464 vs 12.846) — VERIFIED by the checking agent,
> `verified-academic.md` §2.

**Pharmacovigilance: disproportionality analysis over openFDA FAERS** (independent, 2026)

> *Question.* Do spontaneous-report data support the candidate drug-safety signals under study?
> *Method.* PRR/ROR disproportionality against the full openFDA FAERS corpus (N = 20,692,690
> reports, queried 2026-09-15), with de-duplication, drug-role (primary-suspect) restriction, an
> exhaustive per-record census of 78,592 reports partitioned to defeat the API's 25,000-skip cap,
> and a monotonicity argument converting a partial census (87.1 % of the relevant reports) into a
> rigorous bound. *Result.* Drug-role restriction collapsed one candidate signal from ROR 2.64
> into a bounded interval containing 1, and strengthened another (6.19 to 20.70); an exact-census
> bound was used to establish a non-signal rather than merely failing to find one.
> *Artifact.* Receipts inside the public Zenodo deposit; manuscript in preparation.
>
> `[CHECK: on request]` — the receipts are public inside the deposit, but they are not indexed and
> a reader has to be told where to look.

Three discipline notes on this entry:

- **Never** "analysed 20 million reports". 20,692,690 is the endpoint denominator, not the record
  count he processed. Say "queried a corpus of that size". Anyone with pharmacovigilance
  experience catches the difference in one question.
- The phenibut signal cell is a = 7 of n = 49. Never present it as a safety conclusion
  (VERIFIED, `verified-academic.md` §5).
- **A live discrepancy inside his own artifacts**: one source gives the collapsed signal as
  "ROR 2.64 to 1.31", the deposit receipt gives a bracket of [0.96, 1.50]. He must quote one form
  and be able to show its source. Do not write both. COULD NOT DETERMINE which is intended.

**Spanish clinical argument mining — GRACE @ IberLEF 2026, Track 1** (independent, 2026)

> *Question.* Which encoder family and ensembling strategy best identifies argumentative
> components in Spanish clinical abstracts, and how much of a reported gain is seed noise?
> *Method.* 27-cell controlled sweep (9 Spanish/multilingual clinical encoders x 3 seeds:
> 42/100/2026) in one parallel serverless-GPU pass; softmax-probability averaging without dev-set
> model selection; per-model mean and standard deviation reported rather than a best seed.
> *Result.* All-9 ensemble 0.743 dev strict macro-F1 against 0.705 +/- 0.035 for the best backbone
> averaged over three seeds (best individual run 0.737); MajorClaim identified as the
> data-scarcity bottleneck at 0.24-0.43 across all backbones, on a development set of 50 abstracts
> containing 9 MajorClaim spans. *Artifact.* Public code and a full technical report; a fully
> offset-validated blind-test prediction file (11,752 components, 2,474 abstracts, 0 offset
> mismatches).
>
> `[CHECK: public]` for the technical report and code, once the repo README and licence are fixed.

### 3.3 Publications and preprints — with honest status labels

Separate, labelled subsections. Stage stated. No target journal named for anything in preparation.
(APA 7 §10.8 descriptors; UNC TIBBS; Cambridge CV book; `wave2-academic-cv.md` §3.1-3.2.)

```
PUBLICATIONS AND PREPRINTS

Peer-reviewed
  None yet.

Preprints (not peer-reviewed)
  Visalon, A.-M. (2026). Computational corroboration, at the sign level, that R-phenibut is the
  GABA-B eutomer: a two-sided alchemical transfer free-energy validation. ChemRxiv.
  https://doi.org/10.26434/chemrxiv.15009306/v1   [Preprint; sole author; not peer-reviewed]

Manuscripts in preparation
  Visalon, A.-M. (2026). KCTD16/KCTD12 Mendelian randomization, colocalization and FAERS
  pharmacovigilance [Manuscript in preparation; analyses complete, draft in progress].
  Faculty of Mathematics and Computer Science, University of Bucharest.
```

Rules, each with its ground:

- The word **"preprint" must be visible in the line**. Crossref shows type `posted-content` /
  subtype `preprint`, zero references, zero citations, no journal relation (VERIFIED,
  `verified-academic.md` §1). Calling it a publication is a one-minute-to-disprove inflation and,
  for a doctoral file, the worst possible category of error.
- **"None yet" under peer-reviewed is the right line, not an omission.** One preprint and one open
  dataset deposit with no peer-reviewed output is normal and expected at master's level.
- **No venue named for Paper B.** The deposit README names medRxiv as the intended server; on a CV
  that is "manuscript in preparation" and nothing more (UNC TIBBS explicitly forbids "in
  preparation for X").
- Never "submitted" or "under review" for Paper B. There is no editorial trail and the claim would
  be indefensible if probed (VERIFIED absence in Crossref, DataCite, OpenAlex, Europe PMC and
  arXiv — `verified-academic.md` §6).
- **He must open his own DOI logged out and confirm a stranger can read it.** doi.org resolves
  correctly, but chemrxiv.org returns HTTP 403 to every automated client tried, including headless
  Chromium — a site-wide bot block, not something wrong with his item, and a human in a browser
  almost certainly sees it fine (INFERRED, ~90 %). Ten seconds to confirm; the CV depends on it.
- Do not quote view or download counts anywhere. Zenodo shows 11 views and 2 downloads (VERIFIED).

### 3.4 Data and software

```
DATA AND SOFTWARE

Visalon, A.-M. (2026). Data and code for two studies of the phenibut GABA-B axis: alchemical
transfer free energies, and KCTD-subunit genetics with FAERS pharmacovigilance [Data set].
Zenodo. CC BY 4.0. Concept DOI: https://doi.org/10.5281/zenodo.22819600
(three versions, 35.5 MB; SHA-256 manifest covering all 630 files, independently re-verified
with zero mismatches)

Open-source MCP servers (MIT): omniaudit-mcp; abbyy-finereader-ocr-mcp — public repositories,
each with its own CI.
Python packages: tracelines, llm-anthology (PyPI). npm: tracelines.
Reframe — offline-first desktop video application; 9 published releases with installers for
Windows, macOS and Linux.
```

- **This section is "Data and software", never "Publications".** It is a dataset deposit, ORCID
  holds zero works, and a committee that cross-checks notices immediately
  (`verified-programs.md` §3 item 13).
- The SHA-256 manifest line is the strongest verifiable craft signal in the whole research record
  and it survives a hostile check: the verifying agent downloaded the archive, confirmed the MD5
  against Zenodo's recorded checksum, and recomputed SHA-256 for all 630 manifest entries —
  630 match, 0 mismatch, 0 missing (VERIFIED, `verified-academic.md` §2).
- **Do not yet claim the archive is self-verifying.** The deposit's own README says the published
  free energies can be re-derived from it alone; the shipped verifier fails immediately on a clean
  machine, because two paths are absolute to his `D:` drive and `atom_openmm` is neither vendored
  nor pinned. Stubbed past the missing import, the script prints `DEPOSIT NOT SELF-SUFFICIENT:
  6 edge(s) failed to reproduce` (VERIFIED — the agent ran it, `verified-academic.md` §3). The
  data is genuinely complete, so this is a packaging bug and a roughly ten-line fix. After a v4
  release this becomes his single strongest line. Until then it is a trap, because the reviewer
  who cares about the claim is exactly the one who will run the script.
- Two affiliation strings disagree across his own records: ChemRxiv says "Faculty of Mathematics
  and Computer Science", Zenodo says "Faculty of Mathematics and Informatics" (VERIFIED). Pick one
  and use it on every future deposit and byline.

### 3.5 Shared tasks and evaluation campaigns

```
GRACE @ IberLEF 2026 (Granular Recognition of Argumentative Clinical Evidence), Track 1 —
participant. Built and open-sourced a 27-run controlled benchmark (9 encoders x 3 seeds) and a
softmax-averaging ensemble; full technical report public.
```

**Blocked content.** A placement line ("2nd of 4 teams on Track-1 Subtask 1, 0.368 vs 0.369, team
bionlp") may be added **only after** he confirms the Codabench account `alexcristea72` / team
`bionlp` is his and that he was a registered member. If it is a teammate's account it becomes a
team credit, not his line. If it is his, "of 4 teams" must stay in the sentence — a bare "2nd
place" implies a far larger field than four.

Two absolute prohibitions here:

- **"4th overall" must never be written.** It is unsupported on any reading of the public
  leaderboard: bionlp is 3rd of 4 on Track-1 overall and 6th of 6 across both tracks (VERIFIED —
  the leaderboard was retrieved live, `verified-academic.md` §4b, §4d). The number traces to a
  document already flagged internally as fabricated. A wrong placement with that provenance is the
  one failure mode that ends both a job application and a doctoral candidacy.
- **The 0.743 system is not the scored system.** Final Evaluation closed 2026-05-17 21:55 UTC and
  there is no post-evaluation phase; the 27-cell sweep and every blind-submission file were
  produced on 2026-06-06/07 (VERIFIED from the competition API and the commit history). So the
  strong number is a post-hoc development result, and "submitted" invites "what did it score?"
  with a 0.368 answer. Say **"produced"**, not "submitted", unless he confirms a separate earlier
  official submission.

No CEUR working-notes paper exists: the CEUR index has IberLEF volumes for 2019-2025 and none for
2026 (VERIFIED, 5.5 MB index fetched). Re-check around Oct-Nov 2026.

### 3.6 Competitive programming and educational content

See section 4. On this document it sits low, and the 88 authored problems carry it.

### 3.7 Identifiers

```
ORCID: 0009-0001-8776-8498
```

Print this **only after** (a) the pending ORCID-Crossref permission is granted so the preprint
attaches, (b) the Zenodo concept DOI is added, and (c) the education entries are corrected. Until
then it is a link to an empty record attached to a wrong institution — the single worst artefact in
the whole file right now (VERIFIED, `verified-academic.md` §6).

### 3.8 What the doctoral CV is for, and what it is not

The UB Scoala Doctorala de Informatica dossier asks for a *memoriu de activitate stiintifica* and a
*lista a lucrarilor publicate*, both explicitly conditional ("daca exista"), plus a topic proposal
with bibliography and a 10-topic examination list. It does not ask for a CV at all. The binding
requirement is the supervisor's written agreement; without it a candidate "vor fi respinsi,
indiferent de rezultatul obtinut" (VERIFIED, SDI Art. 10(1), 10(2), 10(3)h-k; UB Art. 14(1);
`wave2-CORRECTION.md` §2, §5.1). The ranking's tie-breaks are the licence general average, then a
CNATDCU-Informatics publication score, then the baccalaureate average (SDI Art. 13(8)) — and the
only movable one is the middle one, which requires an accepted peer-reviewed item.

So this CV's real job is to be the attachment on the email that makes a supervisor agree to meet.
Build it to be read cold by a stranger in two minutes, lead with the preprint, and let the
hash-verified deposit do the work of proving he is careful.

---

## 4. The pbinfo problem

### 4.1 What is actually true

All VERIFIED from `conflict-resolution.md` Conflict 2 — live pages read in a real browser and
independently via a third-party extractor, plus two Wayback captures:

| | |
|---|---|
| Rank today | **#1** on the public all-time Top 100, read live 2026-09-23 |
| Metric | "Probleme rezolvate" = distinct problems solved **with a full 100-point score** (the site's own help page defines it) |
| His count | **4,244** problems; **14,228** submissions; 6,134 correct solutions; 34.40 % success rate |
| Second place | 4,191 (Adrian Negreanu-Maior) — a 53-problem gap |
| 100th place | 2,328 |
| Trajectory | #3 on 2022-12-06 (3,516) · #2 on 2023-06-06 (3,733) · #1 now |
| Authorship | **88 problems** published on the platform, author or co-author; at least one confirmed co-authored (#2913, with Mirela Mlisan). 6 technical articles (BigInt class, hash maps, STL containers), 2022-2024 |
| Pool | The site has about 5,027 problems, so he has solved roughly 84 % of them (INFERRED from the maximum problem id) |
| What the site is | pbinfo.ro, created by Silviu Candale, informatics teacher at Colegiul Național Liviu Rebreanu, Bistrița; described by teachers as the standard classroom judge in Romanian high-school informatics |
| Reachability | Public, **no login**. Caveat: a one-to-two-second proof-of-work interstitial means `curl` and WebFetch see nothing; a normal browser gets through |

Two things this changes. His 2023 CV claimed "2nd all time" — that is now **understated and
stale**. And he is not merely a user of the platform: he is one of its problem authors.

### 4.2 Does "high-school judge" help or hurt a master's-level candidate?

**Honest answer: it helps, but only because of the authorship line — and it helps unevenly by
audience.** Confidence: *likely* (60-80 %). This is an inference about audience reaction, not a
measurement; nothing on disk measures how any employer or committee responds to pbinfo.
COULD NOT DETERMINE empirically.

The mechanism, stated plainly so he can judge it himself:

- **The hurt is real and specific.** A reviewer who knows the platform knows it is school-level,
  not ICPC or Codeforces. "First all-time on a high-school judge, at 24, while doing a master's"
  can read as *grinding an easy pool* rather than *competing at a hard one*. That reading is
  available and he should expect someone to have it.
- **The 88 authored problems close it.** Authoring problems on the platform is an adult,
  contributor-side role — the same role the teachers who use the site occupy. It converts the line
  from "he solved a lot of school exercises" into "he is one of the people who make the exercises",
  which nobody reads as grinding. **Never print the rank without the authorship clause adjacent.**
- **The 34.40 % success rate is a feature, not a flaw**, if anyone asks: 14,228 submissions for
  4,244 full-score solves is a visible record of iteration, and iteration is what interviewers
  probe for.

### 4.3 Placement, per document

| Document | Where | How prominent |
|---|---|---|
| Engineering resume, international / remote | Named in the Summary (one clause) **and** as a one-line `Competitive programming` section placed after Projects, before Education | High. It is his only third-party-scored credential and the single most checkable line on the page |
| Engineering resume, Romanian employer | Same, but the section may sit after Education — for a Romanian reader the enrolled MSc at UB is also load-bearing | High |
| Doctoral CV | A section titled **"Competitive programming and educational content"**, placed after Data and software and before Technical skills | Low. It scores nothing in the SDI formula. Its value is entirely in the supervisor's read |

Rationale for the resume placement: `research-format-2026.md` §5 puts competitions and awards near
the end for a recent graduate, which is the right default. This is the documented exception —
every other strong line on his page is self-reported, and this one is not. Putting it only at the
bottom wastes the one fact that survives a hostile check.

Rationale for the doctoral placement: the SDI ranking uses the licence average, a CNATDCU
publication score, and the baccalaureate average as its tie-breaks (VERIFIED, Art. 13(8)). pbinfo
appears in none of them. Placing it high would signal that he does not know what the committee
scores. Placing it low, with the authorship emphasised, signals the opposite — and gives the
supervisor a reason to believe he can help teach a seminar.

### 4.4 Exact wording, per audience

**Romanian employer (Romanian-language CV):**
> pbinfo.ro — locul 1 all-time la probleme rezolvate cu punctaj maxim: 4.244 (sept. 2026; locul 2:
> 4.191); în primii trei din 2022. Autor sau coautor a 88 de probleme publicate pe platformă și a
> 6 articole tehnice.

**Romanian employer (English-language CV — the common case: 74 % of substantive Romanian IT ads
are in English, VERIFIED, `wave2-romania-market.md` E2):**
> pbinfo.ro — ranked #1 all-time by problems solved at full score: 4,244 as of Sep 2026 (second
> place 4,191); top three since 2022. Author or co-author of 88 problems published on the platform
> and 6 technical articles.

**International employer who has never heard of the site.** Three things must be inside the
sentence or the number is meaningless: what the platform is, the runner-up gap (calibration), and
the metric definition.
> Ranked first on the all-time leaderboard of pbinfo.ro, the judge used across Romanian school
> informatics (~5,000 problems; public leaderboard, no login): 4,244 problems solved at full score
> as of Sep 2026, against 4,191 for second place. Author or co-author of 88 problems published on
> the platform.

**Doctoral committee / supervisor email:**
> Author or co-author of 88 problems and 6 technical articles published on pbinfo.ro, the judge
> used in Romanian school informatics teaching; ranked first on its all-time solved-at-full-score
> leaderboard (4,244, Sep 2026).

Note the inversion in the last one: authorship first, rank second. For that reader the didactic
contribution is the relevant one, and it is the closest thing he has to teaching evidence.

### 4.5 Five rules that apply to every version

1. **Always date-stamp the rank.** The leaderboard updates periodically and second place is 53
   problems behind — a gap that can close. "as of Sep 2026" is mandatory.
2. **Always say "at full score."** His public profile shows 6,134 correct solutions against 4,244
   problems. A reader who checks and finds two different numbers without the qualifier concludes
   the CV is inflated.
3. **Never write "2nd".** That was March 2023 and is now both stale and understated.
4. **Never imply olympiad medals, a national title, or ICPC.** Nothing on disk supports any of
   those and they are not what the leaderboard measures. COULD NOT DETERMINE whether he has any
   olympiad record at all — if he does, it is undocumented and belongs in the intake.
5. **State the authorship split honestly if asked.** At least one of the 88 is co-authored; the
   split across all 88 was not checked (COULD NOT DETERMINE, `conflict-resolution.md`). "Author or
   co-author of 88" is the safe form, and he can give the exact split himself.

**Privacy note, his action:** the public pbinfo profile currently displays his personal Gmail as
the contact address (VERIFIED). If he is going to point employers and academics at that page, he
should change it first.

---

## 5. The kill list

Nothing below goes in either document. Grouped by *why*, because the reasons differ and so do the
replacements.

### 5.1 Unverifiable or contradicted metrics — drop the number entirely

| # | Kill | Why | Replacement |
|---|---|---|---|
| K1 | "Reframe has 1,000+ downloads" / any adoption claim | The 1,139 total is a mirror/scraper signature: near-uniform counts across mutually exclusive platform artifacts, and a 41-byte auto-update manifest with 99 downloads beside a 227.9 MB installer with 12 (VERIFIED, `verified-github.md` §2) | Make no download or user claim. If pressed: "the newest Windows installer has 12 downloads" |
| K2 | "556,000 lines of code" / "345K+ lines authored" | Includes a ~150K-line vendored Rust fork he did not write, plus metaswarm, hacktricks and ovh-mcp (VERIFIED, `verified-tooling.md` §5). A reviewer who runs `cloc` sees it | Component counts — 18 MCP servers, 72 hook modules, ~140 skills — plus the commit/PR/CI figures |
| K3 | "1,000-agent, 12.1-hour audit; 42 % of 225 findings refuted at 89 % confidence" | The line itself says the audit died pre-synthesis and that 42 % of its findings were wrong. It advertises a failed run with no receipt (`verified-programs.md` §1.2) | Nothing. Drop |
| K4 | "97-slice pure-Codex audit → 1,582 findings including 3 critical RCE" | No evidence anywhere. "3 critical RCE" is precisely what a security interviewer asks to see (`verified-programs.md` §1.3) | If a number is wanted, the reconciled shape is 89 real findings (82 discovered, 24 false positives dropped, 74 fixed in-tree) |
| K5 | "12,272-record conversation corpus" | No evidence; the July journals are gone (`verified-programs.md` §1.4) | The 47 % data-loss finding — a strictly better story, see section 6.2 |
| K6 | "500-unit fan-out" / "500 agents ran" | 500 is a `BUDGET` config constant; the plan funded ~324 (`verified-programs.md` §3) | The measured 42 runs / 689 launches / 72 % figure, see section 6.2 |
| K7 | "34 agents, 3.9M tokens, 96 adversarial verifications" (estate audit) | Contradicted by the run's own on-disk journal: 80 started, 45 returned (`verified-programs.md` §1.14) | The two findings themselves — a stale port range root-caused, a configuration-injection path closed — with no agent count |
| K8 | "Operates a 26-repo autonomous agent fleet with nightly sweeps" | Designed, never activated; setup steps still open; the count is stale (`verified-programs.md` §1.6) | "Researched and designed a secretless model for running autonomous coding agents across my own repositories, after establishing that the obvious approach leaks a full account session via fork pull requests; specified propose-only, human-merge, no self-hosted runners on public repos" |
| K9 | "Reframe v1.4.2 shipped" — and also "v1.4.1 released" | v1.4.1 is a tag with no release; the last *released* version is **v1.4.0** (VERIFIED against the live tag list) | "9 published releases" |
| K10 | "5,733 sidecar tests and 3,448 renderer tests" | Each appears exactly once in the vault, written by an assistant, never corroborated (`verified-programs.md` §1.9) | **526 test files** — countable by anyone from the public tree |
| K11 | "295-test suite" (WebCoder PR #152), and any line count from that PR | The PR body says 295 *collected* while its receipts say 301 passed / 5 failed; the 1.08 M deletions are a purged vendored `venv` | "Backend 301 passing at 99 % coverage; frontend 229/229 at ~91 %" — or no number |
| K12 | "~8,000 tests **passing**" | Nobody ran them; the one suite that was run is at 98.1 % | "Ships roughly 8,000 test functions" — never "passing" |
| K13 | "1,076 tests passing" (the hook set) | The suite was deliberately not executed; several modules mutate live MCP config. 1,076 is a static count | "Ships 1,076 tests" |
| K14 | "metaswarm: 529 plugin.json files" | The public PR body — the thing he is linking — says ~350 | Quote ~350 |
| K15 | "AI makes me N times faster" | METR's RCT (n=16, 246 issues): participants were 19 % *slower* while perceiving themselves 20 % faster. A personal multiplier is unmeasurable without a baseline (`research-opensource-credibility.md` §6 item 8) | Nothing |

### 5.2 Claims that collapse under questioning

| # | Kill | Why |
|---|---|---|
| K16 | "Authored 400+ (or 2,000) Claude Code agent skills" | 415 is a *deployment* count; a further ~1,650 SKILL.md sit in the marketplace plugin cache, authored by other people — including Microsoft-authored Azure skills and ToolUniverse skills sitting inside the 415 (VERIFIED, `verified-tooling.md` §1). Anyone who opens the tree sees it. **Use: "authored ~140 … inside a 415-skill deployed tree"** |
| K17 | "Wrote / built 40+ MCP servers" | 40 is a *config snapshot*; 88 are configured; **18** are written. The fleet is mostly `npx` third-party packages. "Show me two" collapses it immediately, and it would taint the true 18 |
| K18 | "Architected an open-source multi-agent platform used across Claude Code, Codex and Gemini" | Two independent kill shots on one page: `license=NONE` with no LICENSE file (so "open-source" is factually wrong), and "used across" beside 0 stars / 0 forks / 0 watchers (VERIFIED, `verified-tooling.md` §4). Use "public (unlicensed) personal platform monorepo"; claim cross-tool deployment only for Claude Code and Codex CLI, with Gemini as a config target |
| K19 | "All quality gates green" | Of the last 20 `quality` runs on `main`: 3 success, 9 failure, 8 cancelled; the two most recent runs on any branch both failed on 2026-09-23 (VERIFIED). The gate exists and runs — say that, never "green" |
| K20 | "Shipped / released / published" for bilbo-app | Exactly one release, `assets: []`; no downloadable APK or IPA anywhere. "Shipped" invites "where can I install it?" with no answer. Use "built … (tagged v1.0.1)". Also note that `Test <test@example.com>` shows as a top contributor in that repo's graph |
| K21 | "Contributed to metaswarm" / "merged" | PR #51 is **open**. Say "submitted" or "open" |
| K22 | "Personal-Finance-Management — my Bachelor's degree project" | 63 files byte-identical to `preethi-sv/Thrifty-app` at the same paths; the upstream author's name is still the `applicationId` (`com.preethi.thrifty`); zero attribution anywhere in the tree; and the README asserts "all rights are reserved by the author" (VERIFIED by blob-SHA comparison, `verified-github.md` §7.1). One search on that applicationId finds the 2019 upstream. This is the single highest-risk item on the whole profile and, for the July 2027 doctoral file, a research-integrity flag a supervisor would weigh before signing the written agreement. The only defensible rewrite, and only after the README is corrected: "Extended an existing open-source Android expense tracker (preethi-sv/Thrifty-app) with Google Drive backup, RO/EN localisation, theming and chart rendering — 17 new Java classes" |
| K23 | "Solo" or "team" for GRACE | Git history shows only him, but the official Codabench entry was filed under an account that is not his known handle. Until the identity question is answered, neither word may be used |
| K24 | "Published researcher" / any wording implying peer review | Zero peer-reviewed output; checkable in under a minute. Use "one preprint and one open dataset deposit; no peer-reviewed publications yet" — which is normal at master's level |
| K25 | "ORCID with registered research outputs" | Zero works, live-verified today. Print the iD only after the works are attached and the education entry is corrected |
| K26 | "Self-verifying research archive / re-derives the published free energies to within 0.0004 kcal/mol" | The shipped verifier fails on a clean machine and, stubbed past the missing import, prints that the deposit is **not** self-sufficient (VERIFIED — the agent ran it). Today's honest line: "deposited the full per-replica input data for all six production free-energy edges with a SHA-256 manifest". After the ~10-line fix and a v4 release, the full claim becomes true and is then his strongest single line |
| K27 | The Databricks 608-unit fan-out | Simultaneously his most impressive scale claim, attached to a *different personal name* and a corporate email he does not own, and probably covered by an employer confidentiality obligation (`verified-tooling.md` §6). **Hold it back pending his confirmation and disclosure clearance.** If both clear, the neutral form is "orchestrated a 600+ unit parallel LLM-agent workload on managed Spark clusters" with no employer, workspace or account named. Otherwise drop |
| K28 | "Finished 4th overall at GRACE @ IberLEF 2026" | Unsupported on any reading of the public leaderboard, and traced to a document already flagged internally as fabricated. **This is the most dangerous single line in the corpus** |

### 5.3 Repositories that damage him if a reviewer opens them

A reviewer sorting the profile by recent activity lands on the two repos with failing CI badges
first (VERIFIED, `verified-github.md` §6). Fix the top of the profile before sending any link.

| Repo | What a reviewer sees | Verdict |
|---|---|---|
| **Personal-Finance-Management** | Unattributed upstream plus "all rights reserved" | **Never link. Fix the README or remove the repo** |
| **pbinfo-scrape** | 548 MB of scraped third-party educational HTML, committed and public | Never link |
| **WebCoder** | No README on `main` or on **any** of 38 remote branches (each checked individually); red CI; second-most-recently-pushed repo on the profile | Never link until a README lands and the migration branch is merged |
| **agent-skills-toolchain** | Red CI on main; 237 MB (measured); 111 tags all `archive/` or `rescue/`; committed browser-profile binaries; "Private platform repo" as the description of a public repo | Describe in prose only |
| **Airline-Reservations-System** | Description says "C++ App + GUI"; the GitHub language badge says **Python** (43 %) | Fix with `.gitattributes` (`linguist-vendored` on the quality-gate scripts) plus a matching description, or omit the link |
| **momentstudio** (repo, not the site) | 63,363 remote branches (63,116 `cursor/*`); 91 tags, 89 `rescue/*` | Link the **live site**; link the repo only after pruning |
| **grace-iberlef-2026** | Front page is "bionlp — ToolUniverse Workspace", a different project; no licence; the technical report carries no author line, affiliation or team name | Add a GRACE README, a licence and an author line — or move GRACE to its own repo |
| **quality-zero-platform** | No licence; backup tags | Prose only |
| **SWFOC-Mod-Menu** | 473 MB committed reverse-engineering corpus; game-hacking framing | Prose only, and only where it fits |
| **Reframe** | No LICENSE (a `NOTICE` file only); the v1.4.0 Windows installer is named `media-studio-...` | Link it — but add a LICENSE and rename the artifact first |

Also visible and worth fixing: `Test <test@example.com>` appears as a top contributor on
`bilbo-app` (77 commits) and on six other repos; his own commit identity is split across at least
six author strings, none of which is the hyphenated legal name (VERIFIED,
`verified-github.md` §8). Past history cannot be safely rewritten; set one identity going forward.

### 5.4 Anything that reads as AI-inflated

| # | Kill | Why |
|---|---|---|
| K29 | "1,590 merged pull requests" | 1,580 of them are self-merges on his own repos. Any reviewer who knows GitHub runs the `-user:` filter in seconds; presenting 1,590 next to 7 total stars reads as metric inflation and discredits the honest claims beside it |
| K30 | "6,432 GitHub contributions in the last 12 months" | Technically exact and verified — and it invites the AI-authorship question directly. Paired with 1,580 self-merges and pervasive `Co-Authored-By` trailers, the green calendar reads as automation output rather than engineering judgement |
| K31 | Round percentages with no saved measurement | 2025-2026 practitioner consensus is that a round number on every bullet now reads as an AI tell (`research-opensource-credibility.md` §6 item 2). Only numbers he can scope, source and survive a follow-up on |
| K32 | "scalable", "production-ready", "end-to-end", "robust", "10x", "leveraged", "spearheaded", "passionate", "dynamic" | Named as tells by both Romanian recruiters and US hiring managers (`research-metrics-language.md` §4.11); "things to remove before the resume ships" (`research-opensource-credibility.md` §5) |
| K33 | Parallel three-part bullets, every line in identical XYZ rhythm, em-dash-heavy prose | Keep the XYZ *elements*; do not keep the XYZ *rhythm* on every line (`research-metrics-language.md` §4.2). Vary sentence length |
| K34 | "we" / "led a team" on solo work | He is the sole human contributor on the monorepo; the only other commit rows are bots (`verified-tooling.md` §5). Attribute genuine team work precisely instead ("owned the auth layer of a four-person project") |

### 5.5 Personal data and stale items to strip from the 2023 CVs

Date of birth (8 June 2002) · place of birth · full street address · gender · nationality ·
marital status · CNP · driving licence (unless the role needs it) · the 1000 EUR salary
expectation · "Looking to work in the IT domain" as a summary · the `a_visalon@yahoo.com` address ·
the skills line reading only "C, C++, Python" · the "2nd all-time on pbinfo" claim.
(All present on CV #1 and/or #2, VERIFIED, `VERIFIED-FACTS.md`; removal grounded in
`research-romania-eu.md` §2-3, §11.)

---

## 6. The AI-orchestration problem

Much of the work was executed by AI agents under his direction. This is the question the documents
must answer well, because an applied-AI interviewer is exactly the person who will ask it, and
because the evidence is discoverable in one click (`Co-Authored-By` trailers, 61 `cursoragent`
commits, a 6,432-contribution calendar).

### 6.1 The rule that resolves every case

Three classes, from `verified-programs.md` §2 (derived from the artifact record, not from
etiquette):

1. **His own hands — the distinction is irrelevant, write it in the first person with a plain
   verb.** The FAERS method (bucketed census, monotonicity bound, Wald re-check). The release
   engineering. The secretless-agent security decision. The licensing and legal calls. The
   architecture, the gate design, the provenance discipline.
2. **Honest only with an orchestration verb.** The multi-agent programmes, the audits, the WebCoder
   migration, most Reframe lanes, the toolchain itself. Use *designed and ran*, *orchestrated*,
   *specified*, *reviewed*, *adjudicated*, *directed*. Never an unqualified *built* or *wrote*.
3. **The part a reader should actually value is the verification layer — and it is entirely his.**
   Adversarial refuters that must execute; `verify_gate_controls.py`, which runs every gate twice
   (clean input must pass, injected defect must fail) and states what it does not cover; the
   never-self-certify rule.

One note on scope: his standing instruction forbids AI-use disclosure in his *manuscripts'*
declarations. A resume is not a manuscript, and the two cases are different — here the
orchestration verb is simultaneously the honest choice and the more impressive one.

### 6.2 Six phrasings that are honest and strong

Ranked by how well each survives an interviewer pulling on it.

**1. The one where he catches the machine.** This is the best line in the entire corpus for this
problem, because the agents produced the defect and he produced the catch.

> Found and fixed a silent 47 % data-loss defect in an ingest pipeline that reported zero errors
> under a 100 %-coverage gate: 953 of 2,024 files were being overwritten, and 204,987 response
> items lost, measured on the real store rather than on fixtures. Fixed across three commits, with
> two follow-on defects found afterwards by falsifying my own fix against real data once the
> synthetic tests were already green.
>
> `[CHECK: on request]` — the repo is public (`llm-anthology`, renamed from `ai-sessions-render`);
> the commit SHAs should be re-confirmed against the public repo before citing them
> (`verified-programs.md` §1.4, §1.12).

**2. The one that reports the failure rate.**

> Routinely orchestrate parallel agent fan-outs with on-disk run journals: 42 workflow runs and
> 689 agent launches in a representative five-day window, of which 72 % returned a usable result —
> a gap I instrument deliberately, because a launched agent is not a finished one.
>
> `[CHECK: on request]` — reproducible on his machine in one command in front of an interviewer.
> He must say "a five-day window". The differentiator is that he reports the 72 %, not the 689
> (`verified-programs.md` §1.15).

**3. The one about the gates.**

> Enforce a closed six-gate deterministic CI with pinned tool versions (ruff, basedpyright, 100 %
> line-and-branch coverage on the shipped packages, opengrep clean-zero with no baseline, gitleaks,
> osv-scanner), SHA-pinned actions, and an automated check that fails CI if the quality charter and
> the workflow diverge.
>
> `[CHECK: public]` — the charter and the workflow are both in the public repo. Never add "all
> gates green" (K19).

**4. The disclosure sentence, for a README rather than the CV** (modelled on Ghostty and the
Python devguide, `research-opensource-credibility.md` §5):

> AI assistance: code in this repository was produced with Claude Code and OpenAI Codex under my
> direction. I wrote the requirements and design notes, reviewed every diff, and maintain the
> tests, CI and releases. I can explain any file here without AI tools.

**5. The migration line.**

> Led an AI-agent-assisted modernisation of a 2023 project of mine from Create React App to
> Next.js 15 (App Router, TypeScript, 14 routes): I wrote the specification and the acceptance
> gates, reviewed every change, containerised the code-judging sandbox, and found a latent
> object-permission defect (`obj.author` → `obj.user`) that raised an `AttributeError` on every
> submission retrieve.

**6. The one he will not want to use, which is why it works.**

> I have shipped a false claim of my own and then shipped the check that catches it: a README
> asserted that all ten gates were fail-closed when four of them were not. The fix was a script
> that runs every gate twice — clean input must produce zero findings, an injected defect must
> produce a non-zero exit — and that states in its own output what it does not cover.
>
> `[CHECK: on request]`. Interviewers explicitly probe for a "graveyard" — one thing that broke,
> was killed, or was found wrong by your own review (`research-opensource-credibility.md` §3
> item 8, §4 layer 3). Most candidates have nothing. He has a documented one.

### 6.3 Six phrasings that blow up in an interview

| Phrasing | What happens |
|---|---|
| "I built a 72-module, 60,000-line hook system" | "Open one and walk me through it." The tree was agent-produced under his direction; the unqualified *built* is the part that fails, not the work. Say **"designed, built and maintain"** |
| "AI makes me 5x faster" | METR's RCT found 19 % slower with a perceived 20 % speedup. Any personal multiplier is unsupported |
| "I ran a 1,000-agent audit" / "a 500-agent fan-out" | Asked for the run log, he must admit 500 is a config constant and the 1,000-agent run died pre-synthesis. Both are on the kill list (K3, K6) |
| Title: "AI orchestrator" / "prompt engineer" / "ChatGPT power user" | The last is listed as an automatic red flag by a hiring-manager source. The first two signal that the shipping is somebody else's problem |
| "Agent fleet" presented as the achievement | Explicitly named as a thing not to do (`research-ai-eng-hiring.md` §4). The achievement is the eval, the cost per request, the p95, the postmortem — not the fleet |
| Saying nothing about AI use at all | It is discoverable in one click from the contribution calendar, the self-merge ratio and the `Co-Authored-By` trailers. Being found out mid-interview is strictly worse than volunteering it, and volunteering it is the stronger move anyway |

### 6.4 What to have ready before any AI-role interview

From `research-ai-eng-hiring.md` §4 and `research-opensource-credibility.md` §4 — the five layers
an interviewer actually walks:

1. "Walk me through it" — architecture from memory, drawn.
2. "Why that choice, what did you reject?" — the alternative, named, with what it cost.
3. "What broke, how did you find it, what was your first wrong hypothesis?" — the 47 % defect.
4. "Where did that number come from — baseline, method, environment, percentile?" — the boundary
   sentence for every figure on the page.
5. "Would it handle 10x?" — where "I did not test that; here is how I would" is an acceptable
   answer.

And the script when a number is questioned: *"To be precise about what I measured: <metric> on
<setup>, <N> runs, <percentile>. The resume line compresses that; the honest range is A-B and I can
send the saved log tonight."* If it was overstated: *"That wording is imprecise. What I actually did
was X; Y was not mine."* Then move on. Never manufacture a figure.

---

## 7. Honest gaps

### 7.1 Closable this week

Each is a few hours at most, needs nobody else, and each one removes a live contradiction.

| # | Action | Why it is urgent |
|---|---|---|
| G1 | **Correct the ORCID education entries** — Titu Maiorescu BSc 2022-2025; add UB MSc, in progress | Public, self-asserted, attached to the identifier his preprint byline carries. It contradicts any honest CV. The single worst artefact in the record right now |
| G2 | **Grant the pending ORCID-Crossref permission; add the Zenodo concept DOI** | Turns an empty ORCID — which makes the research lines look unbacked to anyone who clicks — into a populated one. The permission request is already sitting in his inbox |
| G3 | **Answer the Codabench identity question** — is `alexcristea72` / team `bionlp` his, and was he a registered member? | Unblocks or kills the only external placement claim he has. Nothing about GRACE can be finalised until this is answered |
| G4 | **Fix the Zenodo verifier** (resolve paths from `__file__`, pin or vendor `atom_openmm`, add `requirements.txt`) and cut a v4 | Roughly ten lines. Converts an overstated claim into his strongest single line. The reviewer who cares about it is the one who will run it |
| G5 | **Prune momentstudio**: 63,116 `cursor/*` branches and 89 `rescue/*` tags | Converts the profile's best asset from a liability. The Branches tab currently reads as unattended agent runs |
| G6 | **Fix or remove the Personal-Finance-Management README**: attribute `preethi-sv/Thrifty-app`, delete "originally developed as a Bachelor's degree project", delete "all rights are reserved by the author" | An attribution lapse becomes an appropriation claim the moment someone searches `com.preethi.thrifty`. Research-integrity consequences for the doctoral file |
| G7 | **Settle the DINUPLAST facts**: title, dates, employment vs freelance | Unblocks the entire Experience section. Nothing can be drafted until he decides |
| G8 | **Add a GRACE-specific README, a licence, and an author line plus affiliation on the technical report** (or move GRACE to its own repo) | A supervisor who clicks currently lands on a ToolUniverse workspace readme, sees no author anywhere, and leaves. The work is good; the landing page hides it |
| G9 | **Add a README to WebCoder; merge or close draft PR #152** | It is the second-most-recently-pushed repo and has no README on any of 38 branches. A draft PR left open is a weaker signal than no PR |
| G10 | **Fix Airline-Reservations-System**: `.gitattributes` plus a description that matches the badge | The first click shows a Python badge on a repo described as C++, which plants doubt about every other technology claim |
| G11 | **Add a LICENSE to Reframe** (and decide the licensing question for the other nine unlicensed originals); rename the Windows installer artifact so it matches the product | "Open source" with no LICENSE is a factual error a developer spots instantly. Ten of twenty originals have none |
| G12 | **GitHub profile hygiene**: real hyphenated name, a one-line bio, location, pin 4-6 repos, remove "Private platform repo" from a public repo's description | 68 uncurated repos with 7 followers currently reads as noise. Cheap, and it is the surface a recruiter actually lands on |
| G13 | **Open his own ChemRxiv DOI logged out** and confirm a stranger sees the page | Ten seconds. The CV depends on that link working for someone who is not him |
| G14 | **Change the pbinfo profile contact** away from the personal Gmail; set one git author identity going forward | He is about to point employers and academics at that page |
| G15 | **Confirm the phone number from the 2023 CV is still live** | It is the only contact route on the document that cannot be tested by clicking |

### 7.2 Closable this year

These need months, an external party, or both. Ordered by what the July 2027 doctoral clock and
the job search actually require.

| # | Gap | Why it matters | Realistic path |
|---|---|---|---|
| H1 | **A supervisor's written agreement for the UB Scoala Doctorala de Informatica** | The binding gate. Without it he is rejected regardless of mark (SDI Art. 10(1)) | Choose by Dec 2026; be visibly working with them by Feb 2027; agreement in principle Mar-Apr 2027; in writing before the July 2027 colloquium. Ideally the same person who supervises the master's dissertation |
| H2 | **Letters from someone who supervised research-like work** | The decisive input in any international application, and adjacent to H1 domestically. Independent work produces artifacts but not letters — this is his largest academic gap | Get the phenibut/FAERS work read or co-supervised by a faculty member; present at an FMI student scientific session; ask a shared-task organiser about the IberLEF contribution |
| H3 | **One accepted peer-reviewed item** | The only movable tie-break in the SDI ranking (Art. 13(8)(ii)); the *lista lucrarilor* is currently empty because a preprint is not a published work | SemEval-2027 is the reachable route: paper Feb 2027, notification Mar 2027, citable as "accepted" before July 2027 |
| H4 | **A UB-accepted B2+ language certificate** | Mandatory for every doctoral candidate (UB Art. 14(1)(l) plus annex, eight accepted types) | Sit a test by Mar 2027, or — if the master's is English-taught — ask the SDI secretariat in writing whether the current-year *adeverinta* satisfies annex item 3. That reuse is UNVERIFIED |
| H5 | **Documented employment with an external party** | The only external party on his record is DINUPLAST, three years stale. Every other line is self-reported | A paid short contract, a research collaboration, or an internship. The single highest-value addition to the engineering resume |
| H6 | **One or two more merged upstream PRs** | He has exactly one contribution a reviewer counts as genuine open source (ZHMModSDK #241) | Target tools he actually uses — MCP SDKs, eval frameworks, agent-harness libraries. Follow each project's AI policy explicitly; never drive-by |
| H7 | **Green CI on `main` for the flagship monorepo** | 9 of the last 20 `quality` runs failed. Until it is green the repo can be described but never linked | — |
| H8 | **An internationally legible algorithm signal** | pbinfo travels inside Romania; outside it the rank needs calibration and does not substitute for a Codeforces rating or an ICPC record | A Codeforces rating, if he wants the algorithmic line to carry weight abroad. Optional — he may reasonably decide the pbinfo line plus the C++ merge is enough |
| H9 | **A deployed flagship with external users** | momentstudio is live but it is a client's site, not his product with users. "Someone other than me has used it for weeks" is the test an applied-AI hiring manager applies | — |
| H10 | **LinkedIn built out** | Ranked the highest-return supporting surface of all — above GitHub curation — on field-experiment plus vendor plus two HR surveys (`research-portfolio-surface.md` §3) | About section over 1,000 characters; 300+ connections; Open to Work with titles and locations; three projects with links; education matching the corrected CV exactly |
| H11 | **The peer-reviewed version of the phenibut work, and Paper B posted** | Turns "preprint, not peer-reviewed" into a publication line, and "manuscript in preparation" into a citable object | — |

### 7.3 What could not be determined, and therefore is not in either document

- The full employment and freelance history. Nothing on this machine or in any public profile.
- The BSc end month (three sources give three answers), the MSc programme name, its language of
  instruction, and the start month.
- Whether "private bachelor's, state master's" carries weight, positive or negative, with Romanian
  IT employers or the SDI committee. The only relevant datum on disk is that recruiters look mainly
  at "experience and studies", unbroken down by institution type.
- Whether he has any olympiad or contest record beyond pbinfo.
- Whether the legal name carries Romanian diacritics.
- Whether "Daria Grama" — a recurring non-owner committer across about twelve repos — is a
  collaborator or a second account of his.
- The real human-versus-AI authorship split inside the commits.
- Whether the Databricks engagement is his, and whether it can be disclosed.

---

## 8. One-paragraph brief, if only one thing is read

Lead the engineering resume with a live production system he built for a client, a shipped desktop
application under a real coverage gate, and a first-place, third-party-scored, publicly checkable
competitive-programming record — and carry the agent-infrastructure work as a specialisation whose
point is the verification layer, not the fleet. Lead the doctoral CV with education, then the
sole-author preprint and the hash-verified deposit, and accept that its job is to get one named
academic to read one artifact before July 2027, because the gate is a signature and not a score.
Drop every aggregate that measures volume rather than reviewed work — 1,590 merged PRs, 6,432
contributions, 556K lines, 400+ skills, 40+ MCP servers, 1,000 agents, 1,582 findings — not
because they are all false but because they sit next to seven stars and would discredit the twenty
claims that are true and checkable.
