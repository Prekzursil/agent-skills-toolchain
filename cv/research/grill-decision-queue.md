# Grill decision queue — Andrei-Mihai Visalon CV/dossier programme

Built 2026-09-23 from the artifacts already on disk. **18 questions, walked one at a time, each with a recommended answer.** Nothing here duplicates `wave2-intake-script.md`, which collects the undocumented work history; this queue decides what is *done with* what the evidence already shows.

**Evidence base (all in `C:\Users\PREKZU~1\AppData\Local\Temp\2\claude\C--Users-prekzursil\617b9043-495e-418c-b273-de10a7f7e489\scratchpad\`)** — read for this queue: `wave2-CORRECTION.md` (§0, §1, §4, §5, §6, §7), `wave2-intake-script.md` (§12 Block J, §13 Block K, §14.4, §15), `wave2-system-architecture.md` (§0, §1.1, §7.1), `wave2-gap-closing.md` (R1–R15 table, lines 51–65), `VERIFIED-FACTS.md` (full), `conflict-resolution.md` (Conflict 2 = pbinfo, §Name form), `research-ai-eng-hiring.md` (§0, §4), `research-opensource-credibility.md` (§3–§5), plus the 56-row verified-claims register supplied with the task.

**Labels.** VERIFIED = observed, with the file named · INFERRED = my reasoning on verified facts · CND = could not determine from anything on disk. Confidence bands: *almost certain* 90–99 %, *very likely* 80–90 %, *likely* 55–80 %, *uncertain* 30–55 %.

**How to walk it.** One question per turn. Read the question, then the recommendation, then stop and wait. Do not batch. G-1 and G-2 are the foundation: **do not ask G-3 onward until both are answered**, because roughly half the later recommendations flip on them.

---

## The three tensions this queue exists to resolve

Named plainly, because every question below is a consequence of one of them.

1. **The verifiability inversion.** His single most bulletproof credential — ranked **#1 all-time on pbinfo.ro, 4,244 problems solved at full score vs 4,191 for second place**, checkable by anyone in 30 seconds with no login (VERIFIED: `conflict-resolution.md` Conflict 2, live read + two Wayback captures) — is a **high-school** competitive-programming judge. His most impressive work — the 18 MCP servers, the 72-module hook set, the ~140 authored agent skills, the three multiplexers, the 1,016-commit monorepo — is largely **AI-orchestrated and checkable only by running it on his machine** (VERIFIED: the claims register marks these `checkable: on-request`). The document must carry both without letting either discredit the other.
2. **The doctoral gate is a person, and he has not met them.** The binding requirement is a supervisor's **written agreement**; without it he is rejected regardless of his oral mark (VERIFIED: `wave2-CORRECTION.md` §5.1, UB Art. 20–21 / SDI Art. 10(1)). The publication list is optional in the dossier and only a tie-breaker in the ranking. Target date for the first supervisor contact is **December 2026** (INFERRED deadline, `wave2-CORRECTION.md` §5.2) — about ten weeks away — and there were **three scholarship places** in 2026.
3. **The system is being built before the content exists.** The architecture calls for 17 outputs and ~3–5 focused days of code (VERIFIED: `wave2-system-architecture.md` §0 item 10, §7.1 backlog A–M), while the thing that fills them — his employment and freelance history — **is not documented anywhere on this machine or in any public profile** (VERIFIED: `VERIFIED-FACTS.md` §Declared scope item 1). Step M of the backlog is labelled "weeks"; steps A–L are the fun part.

---

# FOUNDATION

## G-1 of 18 · STRATEGY — Is the doctorate a commitment or an option?

**Ask:** "The UB Doctoral School of Informatics concurs is July 2027. The gate is a supervisor's written agreement, not your marks and not your publication list. To be in position you need a named supervisor by roughly December 2026 and a working relationship with them by February 2027. Is the doctorate something you are committing to — meaning it gets the scarce hours when it collides with the job search — or is it an option you want to keep open?"

**Recommended answer: commit, but to the *cheap half* of it.** Commit to the supervisor path (two candidate supervisors contacted by December, one working relationship by February). Do **not** commit to the expensive half — SemEval-2027 at 80–200 hours — until the supervisor relationship exists and can absorb it as joint work.

**Trade-off.** The supervisor path costs perhaps 20–30 hours across four months and is the only thing that is strictly irreversible on a calendar: if December passes with no contact, July 2027 is gone and the next window is July 2028. The publication path costs an order of magnitude more and moves only a tie-breaker that applies solely when two candidates have identical oral marks (VERIFIED: `wave2-CORRECTION.md` §5.1, SDI Art. 13(8)).

**What changes downstream.** If **committed**: the one-page research profile (view `research-profile`) becomes output #1 of the whole system and is needed in December, before the ATS resume; G-16 and G-18 become live; the academic CV and the memoriu enter the build order; every claim in this document is also read by an admissions committee, which raises the stakes on G-10 and G-11 from "embarrassing" to "disqualifying". If **option only**: the `ub-phd` and `research-profile` rows go dormant, the queue drops to twelve questions, and the whole programme becomes a job search with a research hobby attached.

**Evidence:** VERIFIED `wave2-CORRECTION.md` §5.1–§5.2 (requirements table, month-by-month plan), §4 row 10′. Branch A dating (master's Oct 2025 → mid-2027) is **likely, 65–80 %**, not verified — see Assumption A1.

---

## G-2 of 18 · POSITIONING — Which identity leads the first five lines?

**Ask:** "Three true sentences describe you, and a reader only absorbs one. (a) *Competitive programmer who became a software engineer* — #1 all-time on pbinfo, 4,244 problems, anyone can check it in 30 seconds. (b) *Applied AI / agent-infrastructure engineer* — you build and operate the tooling that makes coding agents reliable: 18 MCP servers, a 72-module lifecycle hook set, ~140 authored skills, three tool multiplexers. (c) *Master's student and researcher* — UB master's in progress, a ChemRxiv preprint, a Zenodo dataset with a DOI, a shared-task system. Which one is the headline, and which two are supporting evidence?"

**Recommended answer: (b) as the headline, (a) as the proof-of-fundamentals line immediately under it, (c) as the third block — and for the academic dossier, swap (c) and (b).**

**Trade-off.** (b) is where the market actually is — the 2026 hire is "a software engineer first who has shipped LLM-backed systems", and orchestrating agents reads as a strength *only when paired with visible verification and ownership*, as a red flag when it is the whole story (VERIFIED: `research-ai-eng-hiring.md` §0). Leading with (b) alone triggers the AI-authorship suspicion immediately; that is exactly what (a) neutralises, because a #1 ranking on a judge that scores 14,228 submissions at full-score-only is the one thing on the page no agent could have produced for him. Leading with (a) alone sells him as a 2019 candidate and wastes the actual differentiator. Leading with (c) in a job document under-sells badly: one preprint and one dataset deposit is a normal, unremarkable position at master's level.

**What changes downstream.** Fixes the summary line, the section order on `ats` / `ats-ai` / `designed` / `ro`, which of the 56 register claims get CV real-estate versus a link, and the answer to G-3 and G-4. Locks the phrase "Applied AI / agent-infrastructure engineer (software engineering first)" and **bans** "AI orchestrator", "prompt engineer", "vibe coder" (VERIFIED: `research-ai-eng-hiring.md` §4, Ergini red-flag list).

**Evidence:** VERIFIED `research-ai-eng-hiring.md` §0 and §4; VERIFIED `conflict-resolution.md` Conflict 2 for the pbinfo figures; the register's `supported` verdicts on the MCP/hook/skill/multiplexer claims.

---

# POSITIONING

## G-3 of 18 · Where does pbinfo sit, and do you say "high-school"?

**Ask:** "pbinfo.ro is Romania's high-school competitive-programming judge. You are #1 all-time on it. Two choices: put it in the top third of page one as a headline credential, or put it in Honors near the bottom. And separately: do you describe what pbinfo is — including the word *high-school* — or do you let the reader assume?"

**Recommended answer: top third, and yes, describe it — including the word.** Wording: *"Ranked #1 all-time on pbinfo.ro (Romania's national high-school competitive-programming judge) by problems solved at full score — 4,244 of 14,228 submissions, as of September 2026; second place 4,191. Author or co-author of 88 published problems on the platform."*

**Trade-off.** Naming it "high-school" costs a little prestige and buys the only thing that matters here: a reader who discovers the denominator himself feels misled, and every honest claim beside it gets re-read with suspicion. A Romanian technical reader already knows what pbinfo is, so concealment buys nothing domestically and costs everything abroad. The "as of <date>" clause is not decoration — the lead over second place is 53 problems and a rank can change (INFERRED, *likely* it holds through the application window, but a dated claim never becomes false).

**What changes downstream.** Sets the honesty register for the entire document: if the single best credential carries its own denominator and its own date, the same discipline on the agent-tooling numbers reads as consistency rather than hedging. Also settles the `academic` view — the same line goes in *Honors*, not in *Research*.

**Evidence:** VERIFIED `conflict-resolution.md` Conflict 2 (live pbinfo.ro/top100 read via Playwright *and* independently via Tavily, no login; Wayback 2022-12-06 #3, 2023-06-06 #2) and §"Bonus, verifiable" (88 problems, 6 articles).

---

## G-4 of 18 · Junior, or "engineer with an unusual portfolio"?

**Ask:** "You graduated in 2025 and your only documented engagement is a small plastics wholesaler. You also have four years of continuous public output, 1,016 commits on one monorepo in seven months, and shipped desktop software. Do you apply as a new graduate, or as an engineer whose experience is self-directed?"

**Recommended answer: junior-to-mid, applying into roles that say "junior" or "1–3 years", presented as a graduate with an unusually deep portfolio.** Never "senior", never a years-of-experience number, never "4+ years" derived from repo dates.

**Trade-off.** Claiming mid-level invites a salary and scope conversation he cannot currently win — the ownership check ("open the migration, change it live") is where a self-directed portfolio is tested hardest, and he has no colleague who can vouch that he passed one (VERIFIED: `research-opensource-credibility.md` §4, ownership-check layer). Applying as a pure new grad into a market where new-grad hiring is down 50–65 % versus 2019 means competing on a dimension where he is average. The portfolio is the tiebreaker inside the junior band, not a ticket out of it.

**What changes downstream.** Sets `x_targets.roles` and the tier list in intake J1, the salary answer at J4 (reference anchor 5,000–8,000 RON net for a first Bucharest AI/software role — VERIFIED in the market wave, some single-source), and whether the summary line contains any duration at all. Recommend it contains none.

**Evidence:** VERIFIED `research-ai-eng-hiring.md` §0 (new-grad contraction figures); VERIFIED `VERIFIED-FACTS.md` §Declared scope; VERIFIED register row (1,016 commits / 351 PRs / 32,500+ CI runs, Mar–Sep 2026).

---

## G-5 of 18 · momentstudio.ro — Experience, or Projects?

**Ask:** "momentstudio.ro is live, bilingual, FastAPI plus Angular, with a real catalogue. Was it paid client work where someone other than you set the requirements — or was it yours? The answer decides whether your CV shows two professional engagements or zero."

**Recommended answer: Experience *only* if money changed hands and a client set requirements; otherwise Projects, with no euphemism.** If it qualifies, the entry is *"Freelance software developer — momentstudio.ro (client project)"*, with the literal-truth sentence chosen at intake K2 ("sole engineer; requirements set by the client").

**Trade-off.** This is the single highest-leverage classification in the document: a Romanian recruiter scanning for *experiență* reads the Experience block and stops. But a project promoted into Experience without a paying counterparty collapses under one question ("who was the client, what did they pay for?"), and the collapse costs more than the block gained. **CND** from disk whether it was paid — the register calls it "built and deployed for a real client", which is an agent's phrasing, not a receipt.

**What changes downstream.** Decides whether the work history reads 0, 1 or 2 engagements before the intake even starts, which in turn decides how hard the DINUPLAST reconstruction has to work. Also gates the link: the repo carries **63,363 remote branches (63,116 `cursor/*`) and 89 `rescue/*` tags** — the Branches tab reads as unattended agent runs and undoes the credit (VERIFIED, register risk note). See G-14.

**Evidence:** register row `momentstudio.ro`, verdict `supported`, `checkable: yes-public`; branch counts VERIFIED in the same row's risk field.

---

# SCOPE

## G-6 of 18 · Build the 17-output system, or three documents first?

**Ask:** "The architecture specifies 17 outputs and three to five focused days of code. The content that fills them — your work history — does not exist in written form anywhere. Do we build the system first, or produce three documents by hand and build the system once the content proves it needs one?"

**Recommended answer: three documents first — (1) an ATS English resume, (2) its Romanian rendering, (3) the one-page research profile — hand-assembled from a single `profile.yaml`, with only backlog steps A and B of the system built.** Everything else deferred until after intake Stop 1.

**Trade-off.** Step B is not optional and must not be skipped: the shipped zero-fabrication lint **fails open** — with no `x_metrics` block a fabricated figure passes with zero warnings, only `work[].highlights` are scanned, and warnings never change the exit code (VERIFIED twice by two agents, `wave2-system-architecture.md` §1.1 row "Zero-fab lint"; `adv-check-zero-fab-lint.md`). A system that silently passes invented numbers is worse than no system for a person whose main risk is invented numbers. Steps C–L buy format breadth he does not need until there is something to format. The cost of deferring: when the doctoral pack, the Europass and the platform packs all become due in spring 2027, he builds them under time pressure.

**What changes downstream.** Turns "3–5 days of code" into "half a day plus the lint rewrite", and moves the released hours to intake and to G-15. The 17-row matrix stays as the design of record (VERIFIED: `wave2-CORRECTION.md` §4) — it is not cancelled, only sequenced.

**Evidence:** VERIFIED `wave2-system-architecture.md` §1.1 (lint fails open; RenderCV 2.8 + Typst 0.15.0 verified installing and rendering in ~31 s / ~2 s), §7.1 (backlog A–M, step M = "weeks"); VERIFIED `VERIFIED-FACTS.md` §Declared scope item 1.

---

## G-7 of 18 · Which three artifacts carry the document?

**Ask:** "You have roughly twenty original repositories and fifty-six assessed claims. A resume holds about twelve lines. Name the three artifacts a stranger should remember — everything else becomes a list, a link, or nothing."

**Recommended answer, for the job track: (1) Reframe** — shipped cross-platform desktop application, 9 releases, signed installers, 100 % line-and-branch coverage as a blocking CI gate with mutation testing kept deliberately non-blocking; **(2) the agent platform** — 18 MCP servers, a 72-module lifecycle hook set, ~140 authored skills, three name-preserving multiplexers collapsing ~500 tools behind three registrations, described in prose with **no repository link yet**; **(3) momentstudio.ro** if G-5 makes it client work, otherwise **the ZHMModSDK merged C++ contribution** (282-star SDK, merged by the maintainer, +518 lines across 7 files) as the only genuine third-party open-source credit on the profile.
**For the academic track: (1) the ChemRxiv preprint + Zenodo deposit with its SHA-256 manifest over all 630 files, (2) GRACE, (3) the FAERS methods line.**

**Trade-off.** Reframe is the safest artifact in the set and the coverage gate is the claim that *rewards* probing — the thresholds file candidly separates what the gate proves from what it does not. The agent platform is the most differentiating and the most fragile: it is where the "checkable on-request" claims live, and it is the reason G-8 exists. ZHMModSDK is small but it is the only contribution a reviewer will count as real open source, so it earns its own line rather than being buried in a repo list.

**What changes downstream.** Everything not in the three becomes either a one-line list entry or nothing. Explicitly **out**: the 1,590-PR aggregate, the 6,432-contribution count, the 556K/345K LOC figure, the "1000-agent audit", the "97-slice / 1,582 findings / 3 critical RCE" claim, the "12,272-record corpus", the "26-repo fleet", "Reframe v1.4.2" (last released is v1.4.0), any Reframe download figure, and any "peer-reviewed publication" wording — all verdict `unsupported` in the register, all already argued, none of them a live question.

**Evidence:** register rows with verdict `supported` and `checkable: yes-public` for Reframe, ZHMModSDK, the coverage gate, the SHA-256 manifest, the monorepo activity figures; `unsupported` for each item in the "out" list.

---

# FRAMING

## G-8 of 18 · AI authorship — proactive, on request, or silent?

**Ask:** "Most of the implementation in your recent repositories was written by coding agents under your direction. Your public GitHub shows 6,432 contributions in twelve months and roughly 1,580 self-merged pull requests, and Co-Authored-By trailers are everywhere, so the question gets asked whether or not you raise it. Do you disclose proactively, answer only if asked, or say nothing?"

**Recommended answer: proactive, in one fixed structural form, in three places** — the README of each linked repo, one clause in the relevant CV bullet, and a rehearsed 30-second interview answer. The form names the tool, the extent, what he owned, and how he verified: *"Implementation largely generated by coding agents under my direction: I wrote the specifications, reviewed every change, own the test and release gates, and can explain any file here without AI tools."*

**Trade-off.** Silence is not available. The green calendar plus the self-merge ratio plus the trailers makes the inference free for any reviewer, and being caught concealing is categorically worse than disclosing — maintainer communities in 2026 run zero-tolerance AI-slop policies and hiring managers explicitly prefer "behind on AI with judgement" over "complex agent setups" (VERIFIED: `research-ai-eng-hiring.md` §0, §4). The disclosure only works if the final clause is true, which is Assumption A7 below and the biggest untested risk in the programme: the live ownership check is "open the migration, change it live".

**What changes downstream.** Licenses the entire (b) identity from G-2. Adds a README section to every repo linked under G-14, adds the drill to interview prep, and makes the honest-number discipline of G-9 mandatory rather than optional — a disclosure paired with an inflated metric reads as a confession, not as candour.

**Evidence:** VERIFIED `research-ai-eng-hiring.md` §0, §4; VERIFIED `research-opensource-credibility.md` §3 items 7 and 10, §5 (README template modelled on Ghostty and the Python devguide); register rows for the 6,432-contribution and 1,590-PR claims.

---

## G-9 of 18 · Scale language — component counts, or no scale at all?

**Ask:** "Your scale claims split cleanly. Some are component counts a reader could verify by watching you run something: 18 MCP servers, 72 hook modules, ~140 authored skills, ~500 tools behind 3 registrations, 1,016 commits, 351 PRs, 32,500 CI runs. Others are aggregates that fall apart on inspection: 556,000 lines, 1,590 merged PRs, 6,432 contributions, 8,000 passing tests, 400+ authored skills. Do we keep the first group, or drop scale language entirely and describe only mechanisms?"

**Recommended answer: keep the first group, drop every item in the second, and attach a verb of provenance to each survivor** — *ships* 8,000 test functions, never *passing*; *curates* a 415-skill tree, *authored* ~140 of them; *operates* an ~88-server MCP fleet, *wrote* 18 of them.

**Trade-off.** Dropping scale entirely wastes the one thing that distinguishes him from every other junior portfolio and leaves the mechanisms sounding like a class project. Keeping the aggregates is self-inflicted: a reviewer runs the `-user:` filter in seconds and sees 1,590 next to 7 total stars, or clones and runs `cloc` and finds a quarter of the tree is a Rust fork he did not write — and each discredited figure re-opens every honest figure beside it. The `curates`/`authored` split is the load-bearing one: an interviewer who opens the 415-skill tree finds Microsoft-authored Azure skills inside it.

**What changes downstream.** Writes the lint rule for G-6 step B: every digit-bearing token on any surface must resolve to a metric tagged **M** (measured) or **E** (estimated) with a `how_known` field; B/U provenance never renders as a number. Also bans four specific words the register flags: *all gates green*, *passing* (of the 8,000), *widely used*, and any download or adoption figure for Reframe, tracelines, llm-anthology, or either MCP repo.

**Evidence:** register rows — `supported` for the component counts, `unsupported`/`overstated` for each aggregate; VERIFIED CI reality check (of the last 20 `quality` runs on `main`: 3 success, 9 failure, 8 cancelled; the two most recent runs on any branch both failed 2026-09-23).

---

# CREDIBILITY

## G-10 of 18 · Thrifty — correct, or make it private?

**Ask:** "`Personal-Finance-Management` is presented as your bachelor's degree project. It is a fork-in-substance of `preethi-sv/Thrifty-app` from 2019 — the package is still `com.preethi.thrifty` — and the README carries an 'all rights reserved by the author' line. One search surfaces the upstream. Do we correct the repository and keep a rewritten claim, or make it private and never mention it?"

**Recommended answer: correct the repository first — restore upstream attribution, remove the rights line, state the derivation in the first paragraph of the README — and then keep it *out of the CV entirely*.** If it must ever be described, only after the correction and only as: *"Extended an existing open-source Android expense tracker (preethi-sv/Thrifty-app) with Google Drive backup, RO/EN localisation, theming and chart rendering — 17 new Java classes."*

**Trade-off.** Making it private is the fast fix and the wrong one if G-1 is *commit*: the repository is already public and indexed, so a private repo is a deletion after the fact, which reads worse than a correction if anyone had already seen it. Correcting costs an hour and converts the worst item in the record into a non-event. Keeping it on the CV even corrected is not worth it — 17 Java classes on someone else's app is not a credential, and the sentence would have to carry a derivation clause that draws attention to the original problem.

**What changes downstream.** This is a **research-integrity** item, not a CV item, once G-1 is *commit*: the "all rights reserved" line converts an attribution lapse into an appropriation claim, and that is a flag a supervisor weighs before signing the written agreement that gates July 2027. Treat it as the highest-priority correction in the programme and do it before any supervisor is contacted (G-16).

**Evidence:** register row `Personal-Finance-Management (Thrifty)`, verdict `unsupported`, `checkable: yes-public`, with the upstream package name and the rights-line wording quoted in the risk field.

---

## G-11 of 18 · GRACE — claim the placement, or claim only the benchmark?

**Ask:** "There is an official GRACE Track-1 Subtask-1 result of 0.368 placing 2nd of 4 teams, filed under the Codabench account `alexcristea72`, team `bionlp`. Your git history shows only you. Two questions in one: is that account yours or a teammate's and were you a registered member — and given the answer, do we claim a placement at all?"

**Recommended answer: claim the *work*, not the placement — regardless of the answer.** Write: *"Built and open-sourced a 27-run controlled benchmark (9 Spanish/multilingual clinical encoders × 3 seeds, one parallel serverless-GPU sweep) and a softmax-averaging ensemble for GRACE @ IberLEF 2026 Track 1, with the full technical report public."* If the account is his and he was a registered member, the placement may be added **only** in the complete form *"2nd of 4 teams on Track-1 Subtask 1 (0.368 vs 0.369 for first)"*.

**Trade-off.** The placement is a real, public, checkable credential and it costs nothing to state correctly — but it opens a question he must then answer well: why does the CV headline 0.743 while the official entry scored 0.368? (Answer, and it is a good one: 0.743 is a dev-set score under the organisers' scoring script for a later system; the official submission was an earlier, weaker one.) Omitting the placement removes that whole exchange and loses little, because "2nd" in a four-team field reads larger than it is and the *engineering* is the impressive part. **Never** "finished 4th overall" — that number came from a document already flagged internally as fabricated and is the one failure mode that ends both a job application and a candidacy.

**What changes downstream.** Decides one bullet in three documents and, more importantly, whether the 0.743 figure needs its qualifier in the same sentence. It does either way: *"0.743 dev strict macro-F1 versus 0.705 for the best backbone averaged over three seeds (best individual run 0.737), chosen without dev-set model selection."* Also blocks the link until the repository has a GRACE-specific README and a licence — it currently lands on a ToolUniverse workspace readme with his name nowhere on it.

**Evidence:** register rows for the 2nd-place claim (`unverifiable`, blocked pending identity), the 4th-place claim (`unsupported`, traced to a fabricated document), the ensemble metric (`overstated`), and the portfolio link (`supported`, with the landing-page problem in the risk field).

---

## G-12 of 18 · Name form — normalise the public record, or keep the short byline?

**Ask:** "Your legal and canonical form is **Andrei-Mihai Visalon**, hyphenated — it is what both 2023 CVs and your institutional email use. But ORCID stores 'Andrei Visalon' with no middle name, and GitHub, pbinfo, Hugging Face and your preprint byline are all inconsistent with each other. Do we normalise every surface to the hyphenated legal form, or keep a short byline and accept the mismatch?"

**Recommended answer: normalise everything to *Andrei-Mihai Visalon*, without diacritics, and do it before the next indexed byline.**

**Trade-off.** A short byline is easier to cite and is already attached to the ChemRxiv preprint, so changing it creates one discontinuity now. Not changing it creates a permanent one: the cross-document consistency gate (G6 in the architecture) exists precisely to stop a reader finding three spellings across CV, ORCID, LinkedIn and GitHub, and an author-name mismatch is the classic way a publication record fragments across Scholar, OpenAlex and Crossref. One discontinuity with two works is cheap; the same fix in five years is not.

**What changes downstream.** Bundles with the ORCID education correction (see Assumption-recorded defaults) into a single 30-minute "public record" task: fix the name on ORCID, fix the education entry (currently attributing the bachelor's to the wrong university), attach the two works, set the GitHub bio and website. This whole bundle is the cheapest credibility win available and should precede any supervisor contact.

**Evidence:** VERIFIED `VERIFIED-FACTS.md` §Identity (name inconsistency, unresolved) and §Recovered from two prior CVs (hyphenated in both CVs and in the institutional email); VERIFIED `conflict-resolution.md` §Name form (surfaces enumerated, no diacritics anywhere); register row for the ORCID identifier (`unsupported` as stated, with the education-entry contradiction called "the single worst artefact in the record right now").

---

# RISK

## G-13 of 18 · The 608-unit Databricks fan-out — publish, hold, or drop?

**Ask:** "The largest orchestration you have run is a 608-unit Codex fan-out on Databricks job clusters. It is also attached to a different person's name and a corporate email on an account you do not own, and it is probably covered by a confidentiality obligation. Do we publish it in a neutral form, hold it pending your confirmation, or drop it?"

**Recommended answer: drop it from every written document; keep it as a *possible* interview story only if he confirms the engagement was his to describe and that nothing in the description is confidential.** If both hold, the only permitted form names no employer, no workspace and no account: *"orchestrated a 600+ unit parallel LLM-agent workload on managed Spark clusters."*

**Trade-off.** It is simultaneously his most impressive scale claim and the only item in the register that carries a *disclosure* risk on top of a credibility risk. Published unconfirmed, it can fail twice: a reviewer who probes finds a workload on infrastructure he cannot show, and a former counterparty finds their confidential workload on a public CV. The scale it would buy is already covered, honestly and checkably, by G-9's component counts and by the fan-out journal claim below.

**What changes downstream.** Also disarms the neighbouring claim: the "500-unit fan-out that found 3 exploit-proven defects" must be rewritten to the harness design plus three *confirmed harness defects, each independently reproduced* — 500 is a config constant, the plan funded roughly 324, and the compute was the same third-party workspace. The honest replacement for the whole scale story is the run-journal line: *"42 workflow runs and 689 agent launches in a representative five-day window, of which 72 % returned a usable result — a gap I instrument deliberately, because a launched agent is not a finished one."* That is reproducible on his laptop in one command in front of an interviewer and is the best differentiator in the set.

**Evidence:** register rows — the 608-unit claim (`unverifiable`, "highest-risk item in the lane"), the 500-unit claim (`overstated`), the run-journal claim (`supported`, `checkable: on-request, reproducible in one command`).

---

## G-14 of 18 · What is the rule for linking a repository?

**Ask:** "Right now a reviewer who sorts your profile by recent activity lands on a red CI badge, a repo with no README, a 403 MB clone with committed browser-profile binaries, and a Branches tab with 63,000 agent branches. What is the rule: do we fix repositories until they are linkable, or do we describe the work in prose and link nothing until they are?"

**Recommended answer: a hard gate, and prose until it is met.** A repository may be linked only when it has (1) a README that answers problem / approach / how to run / how it was evaluated, (2) a licence, (3) a CI badge that is green, (4) the AI-assistance section from G-8. Until then the work is described in prose with no URL. Pin 3–5 repos that pass; never link the bare profile.

**Trade-off.** Fixing is cheap for Reframe and the two MCP repos and expensive for the toolchain monorepo — which is the most recently pushed repo on the profile and therefore the first thing a reviewer meets. Linking nothing feels like hiding, and a portfolio claim with no link is worth measurably less. The gate splits the difference honestly: the strongest artifacts get links this month, the monorepo gets described in prose until the browser profiles are purged and CI is green, and momentstudio.ro gets no link until the 63,116 `cursor/*` branches are pruned.

**What changes downstream.** Turns into a concrete task list under G-15: purge and prune (momentstudio branches, toolchain browser profiles), licence the unlicensed originals — half the originals carry no licence, so nothing is legally reusable — fix the `Airline-Reservations-System` language badge with a `.gitattributes` `linguist-vendored` rule so the badge stops saying Python on a C++ project, and correct the Thrifty README from G-10. Also kills the word **open-source** applied to the unlicensed monorepo: "open-source" with no LICENSE is a factual error a developer spots instantly.

**Evidence:** register risk fields for `agent-skills-toolchain` (403 MB, committed browser profiles, red badge, "Private platform repo" label on a public repo), `WebCoder` (no README, red badge, second-most-recently pushed), `momentstudio.ro` (63,363 branches / 89 rescue tags), `Airline-Reservations-System` (Python badge on a C++ project), `Reframe` (no LICENSE, only NOTICE; installer named `media-studio-1.4.0-win-x64.exe`).

---

# SEQUENCING

*With no deadline on the job track and a hard July 2027 gate on the academic one, order is the whole decision. The four questions below set it.*

## G-15 of 18 · What happens in the next 30 days?

**Ask:** "Four things compete for the next month: the intake interview that unlocks every document, the GitHub cleanup, the public-record fixes, and the first supervisor contact. Which order?"

**Recommended answer, in this order:**
1. **Public-record bundle (half a day, this week)** — ORCID name + education correction + attach both works; Thrifty README correction (G-10); GitHub bio and website. These are the only items that are *reputationally* urgent and they must precede any supervisor contact.
2. **Intake Stop 1 (≈2.5 h across two sittings)** — intake IDs A1/A3/A4/A6, B5/B6, per-stub B16–B20, C1–C9 per engagement, H1/H2, K1/K2. This is the bottleneck: nothing can be drafted without it.
3. **GitHub triage (4–8 h)** — the G-14 gate applied to 3–5 repos, plus the branch and browser-profile purges.
4. **Supervisor short-list and first contact (by mid-November)** — G-16.
5. **Lint rewrite + first three documents (≈1 day)** — G-6.

**Trade-off.** The instinct is to build first because building is tractable and interviewing oneself is not. The evidence says the opposite: step M of the backlog is the multi-week item and everything else is blocked on it, while steps A–L produce nothing a reader will ever see until M is done. The public-record bundle jumps the queue only because it is 30 minutes of work standing between him and a discoverable contradiction.

**What changes downstream.** Fixes the order of everything else and gives a checkable definition of done for month one.

**Evidence:** VERIFIED `wave2-intake-script.md` §15 (Stop 1 = 23 load-bearing IDs, ≈2.5 h with three engagements); VERIFIED `wave2-system-architecture.md` §7.1 (step M = "weeks"); VERIFIED `wave2-gap-closing.md` R4 (GitHub triage, 4–8 h, rated **high** job-track value, immediate payoff).

---

## G-16 of 18 · How do you approach the supervisor?

**Ask:** "You need a supervisor's written agreement and you have not contacted anyone. Do you send a cold email introducing yourself, or do you manufacture a smaller reason to make contact first?"

**Recommended answer: manufacture the smaller reason.** Two concrete openings already exist: ask an FMI NLP faculty member for the **arXiv endorsement** of the GRACE technical report (a specific, five-minute, low-status-cost request that starts a correspondence about your actual work), and align the **master's dissertation topic and supervisor** with the intended doctoral supervisor, or at least with their group. Cold email only as a third resort, and then with the one-page research profile attached, never a CV.

**Trade-off.** A cold email from an unknown master's student with an empty ORCID converts poorly and burns the first impression. The endorsement request is a real request with a real artifact behind it and it makes the first exchange about the work rather than about the ask. It costs one to two weeks of lead time versus a cold email — irrelevant against a December target, fatal if he waits until March. Secure **two** candidate supervisors, not one: a supervisor with no vacant 2027 position cannot admit him regardless of goodwill.

**What changes downstream.** Makes the one-page research profile (`research-profile`, matrix row 10′) due in **December 2026**, ahead of every job-track document, and makes the GRACE arXiv report (R2) a dependency of the first contact rather than an optional credibility item. Also raises the stakes on G-10: the Thrifty correction must land before this, not after.

**Evidence:** VERIFIED `wave2-CORRECTION.md` §5.1 (supervisor agreement mandatory, "none = rejected regardless of mark"; positions advertised only ≥30 days before the concurs), §5.2 (Oct 2026 arXiv-endorsement action; Nov–Dec supervisor meetings), §5.4 risk 3 (two candidates, not one), §4 row 10′.

---

## G-17 of 18 · Start applying now, or wait for the artifacts?

**Ask:** "Your documents will be much better in three months. The market is brutal for juniors and referral-driven. Do you start applying now with a thin but honest CV, or wait until the flagship artifacts and the repo cleanup are done?"

**Recommended answer: start now, at deliberately low volume, through referral channels only — and treat the first ten conversations as research into what the documents are missing.** No mass applications, no volume strategy.

**Trade-off.** Waiting optimises a document nobody has yet reacted to; three months of polish against an untested hypothesis is exactly the failure mode the whole system is supposed to prevent. Applying at volume now spends the finite pool of Bucharest employers on the weakest version of the pitch. Low-volume-through-referrals costs almost nothing, generates the only real feedback available, and matches the structural evidence: communities and referrals over cold applications, because the cold funnel is where the 50–65 % contraction actually bites.

**What changes downstream.** Sets the two calendar commitments already dated in the research: **Angajatori de TOP, 30–31 Oct 2026** and the **DevCon Bucharest CFP closing 27 Oct 2026** — both inside the next five weeks, both in the G-15 month, and the CFP in particular is a deadline that cannot be recovered. Also means the first three documents from G-6 must be usable in October, not perfect.

**Evidence:** VERIFIED `research-ai-eng-hiring.md` §0 and §4 (contraction figures; "communities over cold applications"; ~73 % of Romanian AI openings in Bucharest); VERIFIED `wave2-intake-script.md` J9 and `wave2-gap-closing.md` R8 for both event dates.

---

## G-18 of 18 · SemEval-2027 — commit or skip?

**Ask:** "A SemEval-2027 entry with a system paper is the only realistic way to have a peer-reviewed item on your *lista lucrărilor* before July 2027 — paper in February, notification in March. It costs 80 to 200 hours between now and February, and those are the same hours as the dissertation, the job search and the supervisor relationship. Commit or skip?"

**Recommended answer: conditional commit — decide in January, not now.** Register for a task in October (free, reversible). Commit the implementation hours **only if** by December a supervisor relationship exists and the entry can be framed as joint work with them. If December passes without a supervisor, skip it and put the hours into the dissertation and the job track.

**Trade-off.** The publication list is explicitly optional in the dossier ("dacă există") and functions only as tie-break criterion (ii), which applies solely when two candidates have identical oral marks — so an accepted paper is a hedge against a coin-flip, not a gate. The gate is the supervisor. Committing the hours before the supervisor exists is spending the most expensive resource on the least binding constraint, and the collision with the dissertation is real: a late dissertation defence means no *adeverință* in time, which slips the whole application to July 2028 regardless of publications. Conversely, as *joint* work with the intended supervisor, the same hours buy the paper and the relationship at once — which is why the decision waits for December rather than being made now.

**What changes downstream.** Sets the January–March 2027 block of the calendar and determines whether GSoC 2027 is even considered (it is already downgraded for colliding with both the dissertation and the concurs). Also note what does **not** substitute: an arXiv or Zenodo technical report is excluded from the list by the CNATDCU criteria and belongs in the memoriu instead.

**Evidence:** VERIFIED `wave2-CORRECTION.md` §5.1 (list "dacă există"; tie-breaks at Art. 13(8); "one accepted peer-reviewed item by July 2027 is reachable: SemEval-2027"), §5.4 risk 1 (defence-before-registration), §5.5 (R3 keeps its rank, R11/GSoC downgraded); VERIFIED `wave2-gap-closing.md` R3 and R11 rows.

---

# Recorded as assumptions, not asked (EVPI gate)

Each of these is a decision the evidence already settles. They are the session's defaults; raise them only if he objects.

| # | Decision | Default taken | Why it was not asked |
|---|---|---|---|
| D-1 | Aggregate metrics on the CV (1,590 PRs · 6,432 contributions · 556K LOC · "8,000 passing tests" · "400+ skills authored" · "40+ MCP servers written") | **All dropped.** | Every one is `unsupported` or `overstated` in the register and each is refutable in one click. No trade-off to weigh. |
| D-2 | "Reframe has 1,000+ downloads" · "shipped v1.4.2" · "published researcher" | **All dropped.** Latest release is v1.4.0; the honest download figure for the newest Windows installer is 12. | Public pages refute them directly. |
| D-3 | ORCID iD printed on documents | **Only after the ChemRxiv preprint and the Zenodo concept DOI are attached**, and after the education entry is fixed. | An empty ORCID under a research claim is worse than no ORCID; the fix is a task, not a choice. |
| D-4 | Page size and personal data | A4 everywhere; no photo, DOB, nationality, marital status or street address on any machine-parsed view; RO-market views may carry a photo as a view property, never inside the parsed PDF. | Already resolved as a view property in the architecture (§3.2). |
| D-5 | Romanian-language rendering | Produce it. English master; RO rendering for eJobs / Hipo / BestJobs and any public competition. | The Romanian market runs on those platforms; the cost is near zero once the master exists. |
| D-6 | The "gap" since graduation (June 2025) | **There is essentially no gap.** He has been enrolled in a UB master's since (assumed) October 2025, so the unexplained window is roughly four months, covered by the research output. Never "career break", never invented consulting. | The corrected education premise dissolves the question that the earlier waves built a whole block around. |
| D-7 | Preprint wording | The ChemRxiv item always carries the word **preprint** in the line; the Zenodo item is filed under *Data and software*, never under *Publications*; the second manuscript is "in preparation", never "submitted" or "under review". | Crossref shows no journal version; the convention is not contested. |
| D-8 | The self-verifying-archive claim | Do **not** make it yet. Today's honest form is "deposited the full per-replica input data for all six production free-energy edges with a SHA-256 manifest". The full claim becomes true after a ~10-line packaging fix and a v4 release. | The script currently prints that the deposit is not self-sufficient; the data is complete, so this is a packaging bug with a known fix, not a judgement call. |
| D-9 | Private bachelor's / state master's | Do not pre-empt it. The doctoral regulation is institution-blind and the tie-break uses the licence *average*, not its issuer. Keep the ARACIS "grad de încredere ridicat" line available as a view-level option, never on ATS views. | `wave2-CORRECTION.md` §6: **CND** for current employer practice; no recent measurement exists, so there is nothing to decide on. |
| D-10 | DINUPLAST representation | Pull the **REGES-Online** extract first (intake Session 0 item 1); it settles salaried-versus-freelance definitively and fixes the date. Then commit to that version, one line, no numbers. | The two 2023 CVs contradict each other, and a document beats a recollection. |

---

# Assumption ledger

Load-bearing = something in this queue breaks if it is wrong.

| # | Assumption | Confidence | Load-bearing? | What breaks · how to settle it |
|---|---|---|---|---|
| A1 | Master's began Oct 2025 and ends mid-2027 (Branch A) | **medium** (*likely*, 65–80 %) — LinkedIn index copy "2025–2027", self-asserted | **YES — FLAG** | Every date in G-1, G-15, G-16, G-18 moves +12 months if it is Branch B. Settle at intake F0 with the enrolment contract, in the first session. |
| A2 | Licence 180 ECTS + master's 120 ECTS ≥ 300, so he is eligible | **medium** (INFERRED from typical Romanian cycle lengths) | **YES — FLAG** | If short, he is ineligible for July 2027 entirely and G-1 is moot. Settle by reading both diploma supplements before anything else. |
| A3 | The 2027 FMI dissertation defence precedes the SDI registration window (~1–12 July) | **medium** (2026 analogy only; 2027 calendar unpublished) | **YES — FLAG** | If it does not, the *adeverință* does not exist in time and everything slips to July 2028. Ask the FMI secretariat in October 2026. Adverse-inference default: plan July 2028 as the fallback now. |
| A4 | A supervisor with a vacant 2027 SDI position exists in his area | **medium-low** (CND; 2026 had 3 scholarship places) | **YES — FLAG** | The entire doctoral track. Mitigation is already in G-16: secure two candidates, not one. |
| A5 | He can explain any agent-generated file in his linked repos, live, without AI | **low** (untested; CND from disk) | **YES — FLAG, sharpest risk in the set** | The whole (b) identity from G-2 and the disclosure form in G-8 both end with this sentence. If it is false, the positioning inverts and G-2 should become (a)-led. Settle by a self-test before any link is sent: open a random file in each linked repo and explain it cold. |
| A6 | momentstudio.ro was paid work with a client who set requirements | **low** (CND; the register's phrasing is an agent's, not a receipt) | **YES — FLAG** | G-5, and whether the CV shows 0 or 2 professional engagements. Settle at intake, first session. |
| A7 | The Codabench account `alexcristea72` / team `bionlp` is not his | **unknown** (CND) | **YES — FLAG** | G-11. One question settles it; the recommendation is written to be safe either way. |
| A8 | His two research manuscripts are complete enough to become list items | **low** (drafts UNVERIFIED on disk) | Partly (G-18's fallback) | If the drafts are thin, the only reachable list item is SemEval and G-18's conditional commit becomes the only path. Ask at intake block G. |
| A9 | He has real salaried or internship experience beyond DINUPLAST | **medium** (owner statement, `VERIFIED-FACTS.md` §Declared scope) | **YES** | The entire job track's shape. It is the intake's whole purpose; not a decision. |
| A10 | The pbinfo #1 rank holds through the application window | **medium-high** (53-problem lead, VERIFIED live 2026-09-23) | No (mitigated) | Mitigated in G-3 by the "as of September 2026" clause — a dated claim never becomes false. |
| A11 | The shipped zero-fabrication lint fails open | **high** (VERIFIED, reproduced by two independent agents) | **YES** | G-6's insistence on backlog step B. If the lint were sound, the system could be trusted earlier. |
| A12 | RenderCV 2.8 + Typst 0.15.0 work on this box | **high** (VERIFIED: installed in ~31 s, renders in ~2 s, A4 works) | No | Only the build cost in G-6. |
| A13 | Romanian employers do not materially discount a private bachelor's | **CND** — no measurement after 2015 | Mildly | Adverse-inference default in D-9: assume neutral-to-mildly-negative and do not pre-empt. |
| A14 | The SDI 2027 rules keep the 2026 shape (oral, agreement, 10 topics, ~3 scholarship places) | **medium** (school regulations re-adopted each January) | Yes, for the calendar | Re-read the regulation in February 2027; it is a diarised task, not a decision. |

**Low-confidence and load-bearing — settle these first:** **A5** (can he defend the agent-written code), **A6** (was momentstudio paid), **A7** (whose Codabench account), **A2** (does the ECTS sum reach 300), **A4** (does a supervisor with a 2027 position exist). A1 and A3 are medium but govern every date in the sequencing block; both are answerable with one document and one email respectively.

---

## Walk order at a glance

G-1 → G-2 *(stop; everything below re-reads in light of these)* → G-3 → G-4 → G-5 → G-6 → G-7 → G-8 → G-9 → G-10 → G-11 → G-12 → G-13 → G-14 → G-15 → G-16 → G-17 → G-18.

If G-1 comes back **"option only"**, drop G-16 and G-18 entirely, soften G-10 from research-integrity-urgent to housekeeping, and the queue is fourteen questions.
