# Wave 2 — Intake script: the questions that extract what is not on disk

Owner: Andrei Mihai Visalon (GitHub `Prekzursil`, ORCID 0009-0001-8776-8498). Written 2026-09-23.
Purpose: the ready-to-walk question script that extracts his undocumented employment, internship and freelance history, plus every other master-profile field that cannot be read off this machine or a public profile. It operationalises the protocol in `wave2-history-extraction.md` (§3–§12: sessions, interviewer rules, type modules, numbers ladder, YAML record) — that file holds the evidence and citations; this one holds the questions, in order, one per turn, with defaults and load-bearing marks.

Labels used on every question:

| Label | Meaning |
|---|---|
| **LB** | Load-bearing for every rendering: no truthful first resume (English ATS master, Romanian variant, Europass export) can be drafted without it. |
| **LB-A** | Load-bearing for the academic track only (academic CV, FMI master dossier, doctoral `memoriu`, SOP). The job resume can be drafted without it. |
| **ENR** | Enrichment. Improves bullets, numbers, defensibility or tailoring; the resume exists without it. Tier 2 (Block D) is the enrichment that turns a scope-only resume into an achievement resume. |
| **CITED** | The question or rule follows published guidance; the source is named (mostly via the S-numbers of `wave2-history-extraction.md` §15, which that wave read and graded). |
| **DESIGN** | I designed the question, wording, default or rule. Not published guidance. Say so if challenged. |
| **VERIFIED / INFERRED / UNVERIFIED** | Status of any factual claim, per the hard rules. |

Provenance tags on every answer (CITED, `wave2-history-extraction.md` §10 rule 10): `M` measured from an artifact · `E(enum)` enumerated episodes · `E(rate)` rate × period · `E(delta)` before/after computation · `B` bracketed range · `U` unknown. Dates also carry `sure` / `doubtful`.

Count: **39 distinct load-bearing question IDs** — 23 LB (every rendering) + 16 LB-A (academic only). Fourteen of them repeat per engagement (B16–B18, B20, C1–C9, K2), so the walked total is 25 + 14 × (number of engagements). The other 109 IDs are ENR. §15 lists the load-bearing path in walking order.

---

## 0. How to walk this script (runbook)

The owner's stated strong preference is one question at a time. Rules 1–10 are CITED from the interviewer block in `wave2-history-extraction.md` §4 (ABE 2023, Memon 2010, Flanagan 1954, Levashina 2014, OPM, Mathiowetz & Duncan 1988); rules 11–14 are DESIGN for the one-at-a-time mechanics.

1. **One question per turn. Wait. Record. Then the next.** Never stack, never pre-announce the next question.
2. **Open before closed.** Blocks that start with "Tell me…" or "Walk me through…" are not to be replaced by their closed sub-questions; the closed ones are only for what the narrative left out.
3. **Past tense, second person singular, concrete.** "What did *you* do next?"
4. **Say the no-guessing rule aloud at the start of every session**, verbatim: *"If you don't remember, say 'I don't know' — that is a good answer. I will never write a number you did not give me, and I will tag every number with how we got it."* (Memon et al. 2010 — CITED.)
5. **Reinstate context before asking for events** (Block C0) and **do not interrupt the free account.**
6. **Quantifying questions are asked once, as scripted, then dropped.** "How many / how often / how long / compared to what" — yes. "Was it about 40%?" — never. Brackets only after two open attempts fail. (Levashina 2014 "planned neutral probes" — CITED; the adversarial check `adv-check-probe-types.md` found the paper's probe typology is a proposal, not an established taxonomy, and that in *selection* interviews probing can increase faking. This is intake, not selection, and the transfer is INFERRED; the mitigation is that probes are pre-written here, asked equally for every engagement, and "I don't know" ends the probe. Truth is established by artifacts and verifiers, never by probing.)
7. **Verifying question for everything that will appear on a resume:** "Who saw this? What proves it without a person?" (OPM Accomplishment Record — CITED.)
8. **Tag every date and number** with the provenance tag and every date with `sure`/`doubtful`.
9. **Ask for low points and for the routine** ("a normal Tuesday") explicitly; salience bias hides both.
10. **Reflect back at the end of each block** in his words; correct, do not embellish. **Never draft a resume bullet during intake.**
11. **Turn template** (DESIGN). Each turn is exactly:
    ```
    [C4 · LB · engagement eng-2024-03-xyz · 17/39 LB done]
    How many people worked on the same code or product, including you — and what share of it was yours?
    Default: none. Reply "idk" if unknown, "skip" to defer, "back" to revisit the previous answer, "stop" to save and pause.
    ```
12. **Commands** (DESIGN): `idk` records `U`; `skip` records `deferred` and the ID goes to the end of the block; `back` reopens the last answer; `stop` writes `intake-state.yaml` (answered IDs, deferred IDs, current engagement) so any later session resumes at the right question. `later` on any ENR question is always allowed.
13. **Defaults are for rendering decisions and already-verified facts only.** A default is never a number for a metric; suggesting a number is a forbidden move (CITED, §9 forbidden moves).
14. **Language:** ask in whichever language he thinks in for that engagement; record the answer verbatim in the language given; translate at rendering time (CITED, `wave2-history-extraction.md` §3).
15. **Stop when tired**; recall keeps surfacing for days — Block K9 is the 48–72 h follow-up (CITED, §4 rule 14, INFERRED extension there).

**Session mapping** (CITED table in §3 of the prior wave; times are its estimates): Session 0 = artifact harvest, owner alone (§2 below tells him what to fetch); Session 1 = Blocks A + B (≈75–100 min); per engagement = Block C then Block D then the type module E (≈65–105 min each); Session 4/5 = Blocks F, G, H, I, J, K (≈2 h).

---

## 1. Session 0 — what he fetches before any memory question (artifact harvest)

Not questions — a checklist he does alone, CITED from `wave2-history-extraction.md` §5 (S31–S36) and `harvest-academic.md`. Every item turns a later memory answer into an `M` value.

1. **REGES-Online extract** of all employment contracts (employer, CUI, COR title, start/end, contract type, hours) — via ROeID or at the ITM (Ordin MMSS 1107/2025; HG 295/2025, VERIFIED by the prior wave). Fixes every salaried and formal-internship date at `M`.
2. Any *adeverință de vechime* held; written request to each former employer (15 working days).
3. *Certificat de internship* (Legea 176/2018), *certificat de voluntariat* + *raport de activitate* (Legea 78/2014), practice *convenție* / *portofoliu* / grade (Legea 258/2007) — all can be requested after the fact.
4. ANAF: *Declarația unică* filings, PFA or *drepturi de autor* income statements — date freelance income by year and payer.
5. Bank and platform statements (all accounts, Revolut, PayPal/Wise/Upwork): each incoming non-family line = client + date.
6. Mail and chat searches in both mailboxes with the Romanian and English keys listed in §5 C of the prior wave (`contract`, `factură`, `invoice`, `ofertă`, `deviz`, `livrare`, `predare`, `plată`, `stagiu`, `practică`, `voluntar`, `angajare`, `NDA`, `confidențialitate`, `deploy`, `hosting`, `domeniu` …).
7. Private repos: `git log --reverse --format='%ad %s' | head` for first/last commit dates; hosting/domain invoices; store listings; analytics properties; boards.
8. Recognition residue: every thank-you, review, referral, bonus or promotion message → start the kudos file (Ask a Manager "keep a kudos file", VERIFIED as readable by `adversarial-check-search-rails-2026-09-23-resume.md`).
9. Academic paperwork: diploma, diploma supplement / *foaie matricolă* (general average, English semesters, thesis title, supervisor), any language certificate, any scholarship or competition proof, the ID card (for Block A2).
10. ORCID inbox: grant the pending Crossref auto-update permission (request dated 2026-09-23 10:32 UTC per `harvest-academic.md`) so the ChemRxiv preprint attaches; Search & link the Zenodo DOI. Two works appear; no question needed.

Output: `evidence/index.md` — artifact, what it evidences (engagement, date, number), confidentiality (client data → cite by description only).

---

## 2. Do not ask — already VERIFIED by the parallel harvest (confirm in one line, then move on)

From `VERIFIED-FACTS.md`, `harvest-academic.md`, `harvest-github.md`, `harvest-local-disk.md`, `wave2-ro-language-variant.md` §5.4:

- Name as displayed on every profile he controls: "Andrei Mihai Visalon", no diacritics anywhere; ORCID stores "Andrei" / "Visalon" (drops "Mihai") — fix, not a question.
- ORCID iD; institutional email andrei-mihai.visalon@s.unibuc.ro; personal prekzursil1993@gmail.com; GitHub `Prekzursil` (68 public repos = 20 originals + 48 forks; account since 2019-08-28); LinkedIn slug `andrei-mihai-visalon-03141b170`; Hugging Face user `Prekzursil` (VERIFIED by the connector's authenticated identity this session).
- BSc Computer Science, University of Bucharest, Faculty of Mathematics and Computer Science, 2022-10-01 → 2025-06-04 (self-asserted on ORCID; diploma not seen).
- ChemRxiv preprint 10.26434/chemrxiv.15009306/v1 (sole author, posted 2026-09-22); Zenodo deposit 10.5281/zenodo.22819600; GRACE @ IberLEF 2026 repo (blind-test submission, 10-page internal report, no CEUR paper source, no team/affiliation named); ORCID works = 0 today.
- Skills, tooling, MCP servers, hooks, skill counts, repo-by-repo verdicts: in the harvest files. Do not re-ask what a file already measures; ask only what changes its *framing* (Blocks I and K).

Confirm line (one turn, ENR): *"I have your name, emails, GitHub, LinkedIn, ORCID, HF and the BSc dates from your public profiles — anything wrong in that list?"* Default: all correct.

---

## 3. Block A — Identity, contact, personal data (Session 1, ≈10 min)

Basis: schema `basics` block (cv-studio `references/schema.md`), the Romanian personal-data conventions (`wave2-romania-market.md`, `wave2-ro-language-variant.md` §5–§7, `wave2-academic-cv.md` §7). Question wording is DESIGN unless marked.

**A1 · LB** — `basics.name`, `identity.display_en`
Ask: "Which exact form of your name goes on every English document and web profile — 'Andrei Mihai Visalon' or 'Andrei-Mihai Visalon'?"
Default: **"Andrei Mihai Visalon"** (matches GitHub; ASCII; pick one and keep it identical on GitHub, LinkedIn, ORCID and every paper byline — the bylines index forever). Basis: `wave2-ro-language-variant.md` §5.5 decision rule (INFERRED there from VERIFIED facts).

**A2 · LB-A** — `identity.legal_surname`, `identity.legal_given`, `identity.diacritics`
Ask: "Take your identity card and read me the surname and given names exactly as printed in the visual zone: is there an ș in VIȘALON, and is ANDREI-MIHAI written with a hyphen?"
Default: none — the card is the only authority (1993 birth record predates the HG 64/2011 no-hyphen rule; VERIFIED by the prior wave). If the card is not at hand: record `pending`, use A1 for now, and do not produce any legal-form document until answered. Used only on documents that must match identity papers (Europass for state/university competitions, UB dossiers, grants, notarised items).

**A3 · LB** — `basics.phone`
Ask: "Which mobile number should recruiters call? International format, +40 …"
Default: none — must be given. (Romanian screening happens by phone and the salary question comes there — `wave2-romania-market.md`, VERIFIED practitioner accounts.)

**A4 · LB** — `basics.email`, `identity.email_academic`
Ask: "Which email goes on job applications, and which on academic documents?"
Default: **jobs → prekzursil1993@gmail.com; academic → andrei-mihai.visalon@s.unibuc.ro while it works.** Both are stored; the renderer picks per view.

**A5 · ENR** — `identity.email_academic_expiry`
Ask: "Does the s.unibuc.ro mailbox still receive mail now that you have graduated, and have you seen any deactivation notice or date?"
Default: unknown → assume it may lapse (INFERRED; student-domain mailboxes commonly expire); keep the Gmail as the secondary address on ORCID and on every paper's corresponding-author line.

**A6 · LB** — `basics.location.city`, `countryCode: RO`
Ask: "Which city do you live in now, and is it the city you would state on the resume?"
Default: **city only, no street, no postcode** on every rendering (`wave2-romania-market.md`: city-only address; personal data minimised). Country code RO.

**A7 · ENR** — `basics.url`
Ask: "Do you have, or want, a personal website URL for the header?"
Default: none yet; the gap-closing backlog (`wave2-gap-closing.md`, `wave2-academic-cv.md` §8 item 7) plans a one-page GitHub Pages site; add the URL when it exists.

**A8 · ENR** — `basics.profiles[]`
Ask: "Besides GitHub, LinkedIn, ORCID and Hugging Face, is there a Google Scholar, Kaggle, Codabench or other profile you want listed?"
Default: the four verified ones; Google Scholar only once it exists with the two works.

**A9 · ENR** — `private.date_of_birth` (RO/Europass-only block)
Ask: "Your date of birth — held in the private block for Romanian and Europass forms only, never rendered on any resume by default. Agreed?"
Default: **omit from every rendering** (age bias measured: 1 in 3 recruiters admit it, eJobs hides age — `wave2-romania-market.md` VERIFIED; US/UK academic CVs forbid it — `wave2-academic-cv.md` §7).

**A10 · ENR** — `private.citizenship`
Ask: "Citizenship(s)?"
Default: Romanian (INFERRED from the institutional email and location; confirm). RO/Europass-only field.

**A11 · ENR** — `private.driving_licence`
Ask: "Driving licence category, if any?"
Default: omit unless an ad or a Europass form asks (Europass optional field).

**A12 · ENR** — `identity.photo_available`
Ask: "Do you have a plain, recent head-and-shoulders photo you would put on eJobs, LinkedIn and a traditional Romanian variant?"
Default: **no photo on the master or on anything that goes through a multinational ATS; yes on platform profiles and the traditional Romanian variant** (CONTESTED in Romanian sources; rule from `wave2-romania-market.md`).

**A13 · ENR** — `meta.storage`
Ask: "Where should the master profile live on disk, and do you agree the private block (phone, DOB, citizenship, client names under NDA) is kept in a separate file that never enters a public repo?"
Default: `~/source/cv-master` as a private git repository; `profile.yaml` + `engagements/*.yaml` tracked; `private.yaml` untracked or encrypted. (DESIGN; open question 3 in `VERIFIED-FACTS.md`.)

**A14 · ENR** — `meta.interview_language`
Ask: "Romanian or English for the interview? You can switch per engagement."
Default: whichever he thinks in; answers recorded verbatim.

---

## 4. Block B — Landmark calendar and engagement inventory (Session 1, ≈60–90 min)

Basis: Event/Life History Calendar (Belli; PSID adoption — CITED S17–S19, VERIFIED-P in the prior wave), with the known over-reporting failure mode controlled by B20. Say the no-guessing rule first. The calendar starts at the earliest legal working age, not at university (DESIGN, from the prior wave's §6).

**B1 · ENR (confirm)** — `calendar.education`
Ask: "Give me the year and month each stage of your education started and ended — high school, the bachelor's, anything else."
Default: BSc 2022-10 → 2025-06 (VERIFIED on ORCID, self-asserted). High-school years unknown.

**B2 · ENR** — `calendar.semesters`
Ask: "Which semesters or exam sessions were the heaviest, and which were light?"
Default: none. (Paid work tends to sit in the light ones — parallel retrieval cue, CITED S17.)

**B3 · ENR** — `calendar.residence`
Ask: "Where have you lived since high school, and when did you move?"
Default: none. (Residence is the calendar domain with the strongest recall gains, CITED S17.)

**B4 · ENR** — `calendar.landmarks`
Ask: "Name a few personal events you can date exactly — a trip, a device you bought, the 2020 lockdown weeks, a hospital stay."
Default: none.

**B5 · LB** — `engagements[].stub` (paid)
Ask: "Now list every time anyone paid you for work, from the earliest to now — even one weekend, even cash, even a relative's business. Just the list; details come later. I will not interrupt."
Default: none. One stub per item; do not interrupt (CITED ABE free-narrative phase).

**B6 · LB** — `engagements[].stub` (unpaid but serious)
Ask: "Now every time you worked for someone for free but seriously — an internship, university practice, volunteering, a friend's startup, a maintainer role with duties."
Default: none.

Exhaustion cues — one per turn, each a retrieval cue from a different domain (DESIGN, from the prior wave's §6 step 8; ask at least B7 and B8):

**B7 · ENR** "Who has ever sent you money for something you built or fixed?"
**B8 · ENR** "Which companies have you ever had a badge, an email address, a Slack or Teams account, or a VPN for?"
**B9 · ENR** "Which repos exist that are not yours but you committed to for someone?"
**B10 · ENR** "Which websites or apps are live today with code you wrote for someone else?" (momentstudio's live domain is a known case — `harvest-github.md` §4.2; route it to an engagement.)
**B11 · ENR** "Who has ever asked you to sign anything — a contract, an NDA, a *contract de voluntariat*, a practice *convenție*?"
**B12 · ENR** "Did you ever tutor, teach, or coach competitive programming for money?" (pbinfo tooling on his GitHub suggests the domain; ask neutrally.)
**B13 · ENR** "Did you ever do reverse-engineering, modding, save-editing or automation work that someone paid for or that had a 'client'?"
**B14 · ENR** "In each summer break from 2019 on, what did you do for money?"
**B15 · ENR** "Think of your bank statement from oldest to newest — which incoming names are not family?"

Per stub (repeat B16–B21 for every stub before leaving Session 1):

**B16 · LB** — `type`
Ask: "For <stub>: was this a salaried contract (CIM), an internship contract (Legea 176/2018), university practice (*convenție*, Legea 258/2007), volunteering (Legea 78/2014), freelance as PFA, *drepturi de autor*, a platform such as Upwork, informal cash, or unpaid?"
Default: none. (Type decides which artifact can fix the dates and whether the period is legally *vechime* — CITED S32–S35.)

**B17 · LB** — `dates.start`, `dates.end`, `confidence`
Ask: "Start month and end month? If you are not sure, give the season and which semester it overlapped, and I will mark it 'doubtful'."
Default: none. Month granularity; `sure`/`doubtful` on each end (CITED LHC practice).

**B18 · LB** — `hours_per_week`
Ask: "In a typical week, how many hours did it take?" then "Which weeks were untypical?"
Default: none. Tag `E(rate)`. Needed for the "part-time, during BSc" label (§14.2).

**B19 · ENR** — `paid_how`
Ask: "Paid how — bank transfer, cash, platform payout, none?"
Default: none. (Evidence rail for B20.)

**B20 · LB** — `evidence[]` (inflation control)
Ask: "Name one thing that proves this engagement existed — a repo, a payment line, a contract, an email, or a person who would remember."
Default: none. **Rule (CITED S17 over-reporting control):** no stub becomes a record without at least one artifact or one independent second recollection; two stubs for the same client merge into one engagement with phases.

**B21 · ENR** — calendar consistency
Ask: "Placed against your semesters — does <stub> still feel right? It overlaps the exam session you called heavy."
Default: none; resolve inconsistencies now, they are the calendar's signal.

Output: `calendar.md` and `engagements.yaml` stubs (`id`, `type`, `dates{start,end,confidence}`, `hours_per_week`, `evidence[]`).

---

## 5. Block C — Per-engagement core (run once per engagement; ≈20–30 min)

Basis: Cognitive Interview context reinstatement and free narrative (Memon 2010 — CITED S20–S22), then specific-closed questions from the noun list (ABE — CITED). C0 is method, not data. Everything in C is load-bearing: these nine answers are the minimum for a truthful scope-only entry.

**C0 · method (always)** — context reinstatement, then free narrative
Say: "Picture where you were physically working on this — which room, which desk, which laptop; which editor, terminal and chat app were open; who would message you; what season it was." Then: "What was the very first thing you did on day one?" Then: **"Tell me everything about this engagement from the beginning to the end, in as much detail as you can, including things that seem trivial. I won't interrupt."** Keep a noun list (systems, people, tools, numbers) for later probes.

**C1 · LB** — `counterparty{name|null, industry, size_marker, geography, kind}`
Ask: "Who was this for — a company, a founder, an agency subcontracting you, or a private person? What industry, roughly how many people, which city and country?"
Default: none. (For freelance add: "B2B or B2C?") Name may be `null` pending C9.

**C2 · LB** — `dates.evidence`
Ask: "Which artifact fixes the start, and which fixes the end — the REGES line, a contract, the first invoice or transfer, the first or last commit?"
Default: for salaried and formal internships the REGES extract or certificate overrides memory; for freelance, first evidence to last evidence (CITED S31; dating rules INFERRED in the prior wave §10).

**C3 · LB** — `role{as_hired, actual, title_formal, cor_code, title_resume}`
Ask: "What were you hired to do, in the words they used? What did you actually end up doing most of the time? What title is on the contract or in REGES (with its COR code if you know it)?"
Default: **`title_resume` = the real-role title; if the formal title is misleading it goes in parentheses** (DESIGN honesty rule, prior wave §8.1). COR 2512 titles listed in `wave2-ro-language-variant.md` §4.2 for the Romanian rendering. An internship is always titled "Intern" (prior wave §8.2 rule 7).

**C4 · LB** — `team{size, composition, your_share, reported_to}`
Ask: "How many people worked on the same code or product, including you — and what share of it was yours? Who did you report to?"
Default: none. Verbatim quantifying example from Levashina et al. 2014 p. 272 ("How many members were in your team?") — CITED, with the caveat in §0 rule 6.

**C5 · LB** — `summary` (what he built)
Interviewer writes 2–3 sentences from the C0 narrative and reads them back: "Is this literally what you built and did there?"
Default: none; correct, do not embellish.

**C6 · LB** — `stack.claimable`, `stack.exposure_only`
Ask: "Of the technologies you used there, which would you be comfortable being interviewed on for an hour today? Which did you only touch?"
Default: none. (Protects against skill-list inflation — DESIGN, prior wave §7 D-last.)

**C7 · LB** — `outcomes.live_url`, `outcomes.status`
Ask: "What was live or in use when you left? Is it still live — where (URL, store listing)?"
Default: "unknown" is acceptable and recorded as `U`.

**C8 · LB** — `verifiers[]`
Ask: "Who could confirm you did this, and what specifically could they confirm? And what artifact proves it without a person — repo, invoice, contract, certificate, live URL, extract?"
Default: none. Status per verifier: `reachable-consented` / `reachable-not-asked` / `lost` / `artifact-only` (CITED OPM Accomplishment Record, S4; statuses DESIGN in the prior wave §11). Anything on a resume needs at least `artifact-only`.

**C9 · LB (freelance and any engagement with a signed document)** — `nda{exists, covers[], sunset, copy_held}`, `counterparty.disclosure_tier`
Ask: "Did you sign anything with a confidentiality clause? Do you have the copy? Read me what it covers — the client's name, the existence of the engagement, the details, the code, a time limit."
Default: **Tier B until the contract is read or the client consents in writing** (adverse inference: unknown = restricted). Tiers and wording in §14.1.

**C10 · ENR** — `interview_prep.why_ended`
Ask: "How did it end, and why — your choice, theirs, contract end, study?"
Default: none; never on the resume, always prepared for the interview.

---

## 6. Block D — Per-engagement achievement layer: passes, events, numbers (Tier 2 ENR; ≈45–60 min per engagement)

Run immediately after Block C while context is reinstated (INFERRED, prior wave §3). This is the block that answers "I don't have any numbers". All ENR, but nothing achievement-shaped goes on the resume without it.

### D-I. Additional retrieval passes (CITED, CI mnemonics 3 and 4 — S20–S22)

**D1 · ENR** "Now start from the last thing you did there and go backwards to the first."
**D2 · ENR** "Now tell it from the client's or your manager's side: what did they see change between when you arrived and when you left?"
**D3 · ENR** "Describe a normal Tuesday there." (routine; salience correction — Mathiowetz & Duncan, Flanagan — CITED; wording DESIGN)

### D-II. Scope and ownership map (specific-closed from the noun list; DESIGN)

**D4 · ENR** — `ownership{yours, shared, not_touched}` "Which parts of the system were yours alone, which shared, which did you never touch?"
**D5 · ENR** — `decisions{yours, given}` "What did you decide yourself, and what was decided for you — requirements, stack, deadlines, design?"
**D6 · ENR** — `trust_scope` "What did you have access to — production, customer data, billing, deploy keys, the client's accounts?" Record categories, never values.
**D7 · ENR** — `stack.by_layer` For each layer: "What did you use for … ?", "Which did you set up yourself vs inherit?", "Which did you use daily vs touch once?" — languages · frameworks · data stores · queues/caches · APIs and integrations (payments, maps, auth, LLM providers) · infra/hosting/containers · CI/CD · testing and coverage practice · observability · security practices · dev process (tickets, reviews, branching) · AI/ML specifics (models, fine-tuning, eval, vector stores, MCP/agents).

### D-III. Behavioural events (CITED: Flanagan 1954 critical-incident; Spencer & Spencer BEI five probes via secondary quotation — VERIFIED-S in the prior wave)

**D8 · ENR** — `events[kind=high]`
Ask: "Tell me about two or three moments in this engagement you are most proud of." For each, in this order, one per turn:
1. "What was the situation, and what led up to it?"
2. "Who was involved?"
3. "What were you thinking, and what did you want to happen?"
4. "What did *you* actually do or say — step by step?"
5. "What was the outcome — what happened next, and how did you know?"

**D9 · ENR** — `events[kind=low]`
Ask: "Now two moments that went badly — a bug that hurt, a missed deadline, a client who was unhappy." Same five probes. Then: "What did you change afterwards?" (Low points carry the most concrete, defensible detail — CITED BEI practice.)

**D10 · ENR** — counterfactual (DESIGN; feeds ladder rung R5)
Ask: "What would have happened to the product or the client if nobody had done what you did?"

**D11 · ENR** — the mediocre-person test (CITED: Ask a Manager, VERIFIED readable per `adversarial-check-search-rails-2026-09-23-resume.md`)
Ask: "How would a mediocre person have done this job differently?" (The gap between that and what he did is the achievement.)

**D12 · ENR** — `outcomes.recognition[]`
Ask: "What did anyone say or write about your work — a message, a review, a bonus, a repeat request, a referral? Do you still have it?"

**D13 · ENR** — `outcomes.after_you_left`
Ask: "What happened after you left — did they keep it, replace it, hire someone, call you back?"

### D-IV. The numbers ladder (rungs DESIGN in the prior wave §9, grounded in the enumeration-vs-estimation evidence — CITED S23–S25; climb one rung, stop at the first defensible value, tag it)

Each number gets two follow-ups: "How do you know?" and "Who or what could confirm it?"

**D14 · ENR · R0** "What happened after it shipped, and how did anyone know it worked?" (numbers often appear unprompted)
**D15 · ENR · R1 → `M`** "Is there anything we can *read* the number from — git log or commit count, CI runs, database row counts, analytics, install counts, invoice totals, ticket counts, a client email saying 'we now process ~N a day'?" Prefer this rung for anything that will be on a resume.
**D16 · ENR · R2 → `E(enum)`** For irregular, distinct events (incidents, launches, clients, integrations, features, migrations, releases): "Name them one by one — payment integrations first, then auth, then reporting …" (decomposition *helps* here — CITED S23)
**D17 · ENR · R3 → `E(rate)`** For regular activities (deploys, tickets, support requests, reviews, data jobs, invoices): "In a typical week, how many? Which weeks were untypical? How many weeks did it run?" Do **not** split regular activities into sub-categories — that inflates (CITED S23). Record rate, period, product.
**D18 · ENR · R4 → `B`** Only after R1–R3 fail: "More than 10? More than 100? More than 1,000?" Record the range, never a midpoint.
**D19 · ENR · R5 → `E(delta)`** "What was the state before you touched it — time per task, error rate, response time, manual steps? After? How often did that task occur?" Time saved = minutes per occurrence × occurrences per week × weeks; tag each factor.
**D20 · ENR · R6 → scope** When impact is unknowable: users or accounts, records, endpoints, screens, integrations, data volume, services, environments, team size and share, duration, clients served, uptime commitments, on-call load. "Sole engineer for a 12-screen app with 4 integrations used by ~200 staff" is honest and specific (CITED S7–S8 engineering-scope pattern).
**D21 · ENR · R7 → `M(third-party)`** Repeat contracts, referrals, an offer to stay or return, a raise, a bonus, a written review, a grade, a certificate with hours.
**D22 · ENR · R8 gate** For each number: "Say in one sentence how you got it." Cannot → downgrade (`E`→`B`, `B`→drop). Resume rule (DESIGN, prior wave §9): only `M`, and `E` values he can explain in one sentence with "~", go on the resume; `B` stays in the master; `U` is never written as a number.

Recovery probes for "I don't have any numbers" (planned, neutral, verbatim; DESIGN in the prior wave §9):
- "How many people would have been affected if it had broken?"
- "How long did the old way take? How long did your way take?"
- "How many times a week did someone ask you for that?"
- "How many clients, tenants or environments did the same code have to work for?"
- "What was the biggest number on any dashboard you looked at there?"
- "How big was the data — rows, files, gigabytes, requests per day?"
- "How long from your first commit to first production use?"
- "How many of the things that shipped in your time there were yours?"
- "What did they pay for — hours, a fixed deliverable, a monthly retainer — and for how long?"
- "If you had to defend this number to a sceptical engineer in an interview, what would you say?"

Forbidden moves (CITED S9 Jobscan warning; DESIGN list): suggesting a number; averaging two guesses; converting a bracket into a percentage; using a team's number as his own without stating his share; quantifying something that was never measured "because bullets need numbers".

---

## 7. Block E — Type-specific modules (run the one that matches `type`; ENR unless marked)

Wording DESIGN from the prior wave §8; legal facts CITED (S31–S36).

### E-S · Salaried employment (CIM)

**ES1 · ENR** "What title did your teammates actually use for you, versus the contract title?" (both recorded; C3 rule applies)
**ES2 · ENR** "Full-time or part-time — hours on paper and hours in reality?"
**ES3 · ENR** "Was there a probation period, an extension, a raise, a title change, or an offer to stay? When?" (each is a dated outcome → R7)
**ES4 · ENR** "Were you on call? Did you deploy to production? Did you review others' code, and did others review yours?"
**ES5 · ENR** "Was there a performance review or written feedback? What did it say?" (kudos file)
**ES6 · ENR** "Would your manager pick up the phone for a reference? What would they say you were good at?"
**ES7 · rule** Dates: reconcile against the REGES extract; record any mismatch; the extract wins. Employer identity, title and duration are always claimable — an employer must certify them (Codul muncii art. 34(5), VERIFIED in `adversarial-check-nda-resume-job-duties.md`).

### E-I · Internships, university practice, volunteering

**EI1 · ENR** "Was this a *contract de internship* (Legea 176/2018), practice under a *convenție* (Legea 258/2007), volunteering (Legea 78/2014), a normal employment contract labelled 'intern', or informal?"
Default: none. (Legea 176/2018 caps at 720 h over 6 months — a longer "internship" was probably a job; the certificate hours are `M` values; internship and in-field volunteering are legally recognised experience — VERIFIED S32–S34.)
**EI2 · ENR** "Paid or unpaid? Hours per week, and for how many weeks?"
**EI3 · ENR** "Who was your mentor or tutor? What did they let you do in week one versus the last week?" (growth of trust is the internship's outcome)
**EI4 · ENR** "What did you deliver that survived after you left — a feature, a tool, a report, a test suite?"
**EI5 · ENR** "Was there an evaluation, a grade, a certificate, or an offer to return or convert?" (an offer is a strong outcome even if declined)
**EI6 · ENR** "What did the team say you were unusually good at, compared with other interns?"
**EI7 · rule** Title "Intern" / "Software Engineering Intern"; scope in the bullets; never upgraded to "Software Engineer" (DESIGN, prior wave §8.2).

### E-F · Freelance and contract clients

**EF1 · ENR** "How did this client find you, or you them?" (referrals are outcomes of earlier work — link the engagements)
**EF2 · ENR** "What was the legal wrapper — PFA invoice, *contract de cesiune drepturi de autor*, a platform, an agency contract, or informal?"
Default: none. Evidence follows the wrapper: invoices or withheld-tax statements → `M` dates; platform → platform records; informal → chats and bank lines only, mark `doubtful` (CITED S35–S36).
**EF3 · ENR** "What was the agreed scope, and what did the scope become?" (scope creep is a story with numbers: features added, weeks extended)
**EF4 · ENR** "Who wrote the requirements, and who made the technical decisions?" (sole-engineer flag → K2)
**EF5 · ENR** "Fixed price, hourly, or retainer? Total contract value, or number of hours?" (contract value and duration are legitimate scale metrics; exact rates need not appear on a resume — DESIGN)
**EF6 · ENR** "What did you hand over — code, docs, hosting, credential rotation, training?"
**EF7 · ENR** "Is it live? Do they still use it? Did they come back, refer you, or leave a review?" (repeat business and referrals are the freelancer's promotion — R7)
**EF8 · ENR** "Would this client (a) let you name them, (b) confirm the engagement in writing if a background check asks, (c) act as a reference?" → plan the written ask (§14.1 template); record the answer date.
**EF9 · ENR** "Can any code, screenshots or a demo be shown? If not, what could you rebuild as a sanitised sample?" (portfolio without breach — DESIGN)
**EF10 · ENR** "Which invoice, transfer or message marks the start, and which the end?" If none: anchor to the calendar and mark `doubtful`.

---

## 8. Block F — Education beyond the bare degree (Session 4; ≈20 min)

Basis: academic-CV structure (`wave2-academic-cv.md` §1, VERIFIED, 6 sources); FMI master methodology 2026 (`gap_fmi_master_method.txt`, VERIFIED primary: N1 = BSc average + 0.25 per proven achievement, max 3 per criterion; employment, hackathons, volunteering, courses score zero; top-5% cohort admitted without exam; English-taught AI / Data Science / NLP tracks need a B2 certificate from a recognised body, baccalaureate certificates rejected, or two semesters of English in the BSc per the FMI page); UB doctoral regulation 2026 tie-breakers (licence GPA, CNATDCU-scored publications, baccalaureate GPA — VERIFIED in `wave2-ro-language-variant.md` §3.1). Question wording DESIGN.

**F1 · LB-A** — `education[0].thesis{title_ro, title_en}`
Ask: "What was the exact title of your bachelor's thesis (*lucrarea de licență*), in Romanian as submitted and in English? Was it the Thrifty Android personal-finance app, or something else?"
Default: none. (The Thrifty link is INFERRED from the repo README — `harvest-academic.md` row 28; confirm, do not assume.)

**F2 · LB-A** — `education[0].supervisor{name, title, department, email}`, `letters.candidates[]`
Ask: "Who supervised the thesis — full name, academic title, department? Would they plausibly write a recommendation letter, and when did you last speak?"
Default: none. (Letters are the decisive input for any PhD file — `wave2-academic-cv.md` §2, VERIFIED.)

**F3 · ENR** — `education[0].thesis.grade`, `education[0].licence_exam_average`
Ask: "The thesis grade, and the final licence-exam average?"
Default: record always; render only if strong (DESIGN threshold: ≥ 9/10; `wave2-academic-cv.md` says "grade if strong").

**F4 · LB-A** — `education[0].score` (media generală a anilor de studiu)
Ask: "What is your general average over the three years, as printed on the diploma supplement or *foaie matricolă*?"
Default: none — read it off the supplement; it is the base of the FMI dossier score (40% weight). If unknown, the supplement scan from Session 0 answers it.

**F5 · ENR** — `education[0].cohort_rank`
Ask: "Do you know your rank in the cohort, and whether you were in the top 5%? Did the faculty publish a ranking?"
Default: unknown → ask the FMI secretariat in writing (gap-closing item; top-5% = admission without exam).

**F6 · LB-A** — `education[0].english_semesters`
Ask: "Does your diploma supplement list two semesters of English (*Limba engleză*) with passing grades?"
Default: unknown → read the supplement. (The FMI page's exemption wording came from the web page only — UNVERIFIED in the regulation text; confirm with the secretariat.)

**F7 · LB-A** — `certificates[]` (language)
Ask: "Do you hold any English certificate — Cambridge, IELTS, TOEFL, UB FLLS / Ariel — with level, score and date?"
Default: none. (Without one, book a recognised B2+ exam before the July 2027 dossier — `wave2-gap-closing.md` R9. A self-assessment is not evidence for the dossier.)

**F8 · ENR** — `education[0].courses[]`
Ask: "Which four to six courses best match AI, NLP or data roles — names and grades?"
Default: not listed on the international CV; listed on the Romanian/Europass rendering or when a programme asks.

**F9 · LB-A** — `awards[]` (scholarships)
Ask: "Any scholarship — *bursă de merit, de performanță, de excelență*, Erasmus, or a competition-based scholarship — which years, and do you have the proof?"
Default: none. (Competitive scholarships score +0.25 each in the FMI dossier, proof required.)

**F10 · LB-A** — `awards[]` (competitions)
Ask: "Any competitions — olympiads, ACM/ICPC, Kaggle medals, hackathons — with placing and proof?"
Default: none. (Hackathons score zero at FMI but belong on the job resume.)

**F11 · LB-A** — `presentations[]`
Ask: "Have you ever presented at a student scientific session, a conference or a workshop — anything with a programme entry or certificate?"
Default: none (the harvest found none). Each is a +0.25 item and the first line of "Presentations".

**F12 · ENR** — `education[1]` (high school), `private.baccalaureate_average`
Ask: "High school name, profile, years, and your baccalaureate average?"
Default: omitted from the international CV (school qualifications rarely necessary — Imperial tipsheet, CITED); kept in the master for Europass and because the SDI doctoral tie-breakers use the baccalaureate GPA.

**F13 · ENR** — practice placement
Ask: "Did the BSc include a mandatory practice placement (*practică de specialitate*)? Where, when, who was the tutor, what grade?"
Default: none. If yes, it is also an engagement → Block C.

**F14 · ENR** — `evidence.academic_scans`
Ask: "Do you have scans of the diploma, the diploma supplement and the *foaie matricolă*?"
Default: obtain them; every dossier needs them.

**F15 · ENR** — other studies
Ask: "Any other courses or certifications (online or otherwise) you consider substantive?"
Default: omitted from the academic track (zero points); on the job resume only if substantive (`wave2-gap-closing.md` R14: certifications are theatre for this profile).

---

## 9. Block G — Research status, manuscripts, shared task, witnesses (Session 4; ≈20 min)

Basis: status-labelling conventions (`wave2-academic-cv.md` §3 — separate subsections, stage stated, no target journal for in-prep work; APA 7 §10.8 descriptors); the ChemRxiv preprint now exists (`harvest-academic.md`, VERIFIED via Crossref), so the brief's "unpublished pharmacology manuscript" framing is stale — the script asks for current status.

**G1 · LB-A** — `publications[phenibut].status`
Ask: "The phenibut preprint on ChemRxiv — has it been submitted to a journal? If yes, submission date and current status. (I will not write the journal's name on the CV.)"
Default: **"[Preprint, not peer-reviewed]" with the DOI** until submitted; then "[Manuscript submitted for publication]".

**G2 · LB-A** — `publications[paper_b].status`
Ask: "Paper B, the one the FAERS analysis belongs to — what is its state: outline, partial draft, complete draft, ready to post? Expected submission month?"
Default: "[Manuscript in preparation; <stage>, expected submission <month>]"; the FAERS work is a methods line, not a publication, until then.

**G3 · LB-A** — `publications[grace].status`
Ask: "GRACE at IberLEF 2026 — did you submit a system-description paper by 24 May 2026? Was it accepted? Did anyone present it on 22 September 2026?"
Default: none. If no paper: label "shared-task participation; technical report on GitHub; no proceedings paper" and follow `wave2-gap-closing.md` R2 (arXiv/Zenodo technical report). Never call it a publication without the CEUR volume.

**G4 · LB-A** — `projects[grace].team[]`
Ask: "Who else was on the GRACE team — names and roles — and who is 'alexcristea72' on the Kaggle dataset?"
Default: none. **Do not write 'solo' or 'team' until answered** (`harvest-academic.md` gap 6).

**G5 · ENR** — `projects[grace].official_result`
Ask: "What did Codabench or the organisers report as your official test score and rank? Do you have the email or a screenshot?"
Default: none. The circulating "36.83 / 4th overall" figure is UNVERIFIED and originates in a document his own notes call fabricated — never use it without the artifact.

**G6 · LB-A** — `research.witnesses[]`
Ask: "Which researcher or faculty member has actually seen any of this work — the phenibut study, the FAERS analysis, GRACE — and what did they see?"
Default: none → gap-closing item R1 (recruit a witness); without one, no letter can describe the research.

**G7 · LB-A** — `letters.candidates[]`
Ask: "Name up to three people who supervised or closely observed your work — any work — and would plausibly write a letter: name, role, what they witnessed, when you last spoke."
Default: none.

**G8 · LB-A** — `research.direction`
Ask: "In one sentence, what research direction would you put at the top of a statement of purpose?"
Default: none. The two candidates the waves found in his output are computational pharmacology / pharmacovigilance and Spanish clinical NLP — offered as a menu, not an answer.

**G9 · ENR** — `talks[]`, `teaching[]`, `service[]`, `memberships[]`
Ask: "Any talks, posters, teaching or tutoring, reviewing, or memberships (ACM, IEEE, SEPLN)?"
Default: none.

**G10 · ENR** — `software[].doi_plan`
Ask: "Which of your repositories do you consider research instruments worth a DOI and a research-style README — question, method, result, limitation?"
Default: grace-iberlef-2026, the FAERS pipeline, Reframe, tracelines, llm-anthology (gap-closing R1 list).

**G11 · ENR** — `artifacts.hf_kaggle`
Ask: "Does a GRACE model or dataset exist on Hugging Face or Kaggle under your control?"
Default: unknown.

**G12 · ENR** — `identity.affiliation_string`
Ask: "Confirm the affiliation string for every byline: 'Faculty of Mathematics and Computer Science, University of Bucharest'?"
Default: yes — the Zenodo record's "Faculty of Mathematics and Informatics" is the form his own note calls a mistranslation (`harvest-academic.md` §7); fix on the next version.

---

## 10. Block H — Languages with honest proficiency levels (≈10 min)

Basis: CEFR levels are the convention on Romanian CVs and in Europass (`wave2-ro-language-variant.md` §7; Europass self-assessment grid, Council of Europe). The can-do ladder below is my paraphrase of the CEFR global-scale descriptors (DESIGN wording; the framework itself is CITED). Rules are DESIGN.

**H1 · LB (default)** — `languages[0]`
Ask: "Romanian — native?"
Default: "Română — limba maternă / Romanian — native".

**H2 · LB** — `languages[1]` (English) with per-skill evidence
Ask, one skill per turn: "For English, which line on the ladder is literally true for (1) listening, (2) reading, (3) spoken interaction, (4) spoken production, (5) writing?" Then: "Have you worked or studied in English daily — an English-speaking team, English-taught courses, English-language client calls?"
Default: none. **Rules:** the resume states one CEFR level = the *lowest* of the five unless the rendering splits skills (Europass does); a certificate (F7) overrides self-assessment and is cited next to the level; the master stores all five levels plus the evidence; for the FMI English tracks only a recognised certificate counts.

Ladder (paraphrased CEFR descriptors):
- **A2** — understands and produces simple, routine exchanges on familiar matters.
- **B1** — handles most situations while travelling or at work; produces connected text on familiar topics; describes experiences and gives brief reasons.
- **B2** — follows complex technical discussion in own field; interacts fluently and spontaneously with native speakers without strain; writes clear, detailed text and argues a viewpoint.
- **C1** — understands demanding, longer texts and implicit meaning; expresses ideas fluently without obvious searching; uses language flexibly for professional and academic purposes; writes well-structured, detailed text.
- **C2** — understands virtually everything heard or read; summarises across sources; expresses spontaneously, precisely, with fine shades of meaning.

**H3 · ENR** — `languages[]` (Spanish)
Ask: "Can you hold a conversation in Spanish, or is your Spanish reading-only from the IberLEF corpus work?"
Default: **do not list Spanish as a language unless at least A2 in spoken interaction**; reading-only ability is a note inside the GRACE project entry, not a language line (DESIGN).

**H4 · ENR** — other languages
Ask: "Any other language — French, German, Italian, Russian — with a level you would defend in an interview?"
Default: none.

**H5 · ENR** — `languages[].certificates_plan`
Ask: "If you have no English certificate, are you willing to sit a recognised B2/C1 exam before mid-2027?"
Default: yes, per `wave2-gap-closing.md` R9 (gating for the English-taught master tracks).

---

## 11. Block I — Projects, open source, authorship disclosure (≈20 min)

Basis: the GitHub and disk harvests already measure the repos; this block asks only what changes their framing (`harvest-github.md` §9 gaps; `harvest-local-disk.md` §5 caveat 1; `wave2-gap-closing.md` R4/R7 on AI-assisted contributions). Wording DESIGN.

**I1 · ENR** — `projects[momentstudio].engagement_link`
Ask: "momentstudio — who is the client, is it live and in use, and may the client be named?"
Default: treat as a freelance engagement → Blocks C, E-F; Tier B until consent (§14.1).

**I2 · ENR** — private repos
Ask: "Are there private repositories that are client work or substantial products the public profile does not show?"
Default: none listed; each becomes an engagement stub or a project entry.

**I3 · ENR** — commit identities
Ask: "Who are 'Daria Grama' and '917-Andrei-Visalon' in your commit history — a collaborator, a second account, a university identity?"
Default: none. (Needed before any repo is linked: a reviewer sees the contributor list.)

**I4 · ENR** — `projects[].authorship{ai_assisted_share, your_decisions}`
Ask, per showcase project: "Roughly what share of the code was generated by AI tools under your direction versus written by hand, and what did you personally decide — architecture, tests, review gates, releases, licensing?"
Default wording: **"designed, built and maintains"** (the disk harvest's caveat: the estate was produced through Claude Code / Codex sessions he designed and orchestrated; never imply solo hand-written code). Disclose AI use where a project's policy asks (maintainer policies 2026, VERIFIED in `wave2-gap-closing.md`). DESIGN rule.

**I5 · ENR** — `projects[].pinned`
Ask: "Which four to six repositories do you want pinned and linked?"
Default: the harvest's A-tier — Reframe, momentstudio (after its mandatory cleanup), llm-anthology, env-inspector, tracelines, quality-zero-platform — plus grace-iberlef-2026 once fixed (`harvest-github.md` §4).

**I6 · ENR** — external contributions
Ask: "Which pull requests to other people's projects would you defend in an interview as real contributions?"
Default: the merged ZHMModSDK PR; peer-project PRs described as collaboration, not as contributions to established projects.

**I7 · ENR** — `projects[thrifty].provenance`
Ask: "Was Thrifty built on top of an existing open-source app (the harvest flags preethi-sv/Thrifty-app)? If so, how was that disclosed to the university, and what did you write yourself?"
Default: none. If derived: describe as "extended and rebuilt from an open-source base" and never as from scratch (honesty rule; `harvest-github.md` §4.19 provenance problem).

**I8 · ENR** — coursework repos
Ask: "Which public repos are coursework or one-offs that should be archived rather than shown?"
Default: the harvest's C-tier plus contribution-less forks (unfork or archive — `wave2-gap-closing.md` R4).

---

## 12. Block J — Targets, availability, logistics (≈15 min; all ENR — tailoring, not the master)

Basis: `x_targets` in the cv-studio schema; `wave2-romania-market.md` (market facts VERIFIED there, single-source figures marked); `wave2-gap-closing.md` calendar. Wording DESIGN.

**J1 · ENR** — `x_targets.roles`, `x_targets.companies`
Ask: "Which roles first — AI engineer, ML engineer, backend, platform, research engineer — and which five companies?"
Default: tier-1 fits from the market wave — UiPath, Adobe (agentic/Firefly services), Bitdefender ML platform, Druid AI, Accenture early-career AI — plus the bank/fintech captives (ING Hubs, Deutsche Bank Technology Centre, LSEG) as the under-applied volume tier.

**J2 · ENR** — `x_targets.mode`, `x_targets.city_constraint`
Ask: "On-site, hybrid or remote — and Bucharest only, or also Cluj/Iași/Timișoara?"
Default: Bucharest-first (≈47% of postings); Cluj only for AI-dense employers.

**J3 · ENR** — `availability.start`, `availability.notice`
Ask: "Earliest start date? If you are currently employed, what is the notice period (*preaviz*) in your contract?"
Default: none. (If an inventory stub is current, the notice clause is in that CIM.)

**J4 · ENR** — `availability.salary_answer`
Ask: "When the screener asks for a net monthly figure, what will you say?"
Default: have a number ready; never on the resume. Reference only (VERIFIED by the market wave, some single-source): first AI/software role in Bucharest anchored at 5,000–8,000 RON net; eJobs/Salario IT average 8,000 RON net H1 2026. This is context, not a suggested answer.

**J5 · ENR** — `x_targets.academic`
Ask: "Which FMI master track — Artificial Intelligence, Data Science, NLP, other — and which session? Any other university, in Romania or abroad?"
Default: FMI English-taught AI / NLP / Data Science, July 2027 session (the 2026 sessions are closed; PhD requires the master's first — VERIFIED).

**J6 · ENR** — `x_targets.relocation`
Ask: "Would you take a salaried EU PhD position or MSc abroad if offered?"
Default: none. (EU PhD positions are jobs applied to with CV + cover letter — `wave2-academic-cv.md` §6.3.)

**J7 · ENR** — `evidence.background_check_ready`
Ask: "Have you pulled the REGES extract and requested *adeverințe* yet?"
Default: do the Session 0 checklist first.

**J8 · ENR** — `verifiers.consent_outreach`
Ask: "May I draft the written consent requests to the clients and managers you named, for you to send?"
Default: yes — §14.1 template.

**J9 · ENR** — `x_targets.events`
Ask: "Will you attend Angajatori de TOP (30–31 Oct 2026, Sala Palatului) and submit a DevCon talk (CFP closes 27 Oct 2026)?"
Default: yes to both (market and gap-closing waves; dates VERIFIED there).

---

## 13. Block K — Reconciliation and honesty pass (Session 5; ≈30 min)

Basis: prior wave §10–§11 (dating rules, concurrent work, gaps, short stints INFERRED there from F1/F2/F12; sole-engineer table INFERRED; NDA tiers from practitioner sources S27–S29, with the enforceability claim dropped per `adversarial-check-nda-resume-job-duties.md`).

**K1 · LB** — `timeline.since_graduation[]`
Ask: "From June 2025 to today, month by month, what were you doing — study, the phenibut and FAERS work, the IberLEF entry, open source, job search, paid work?"
Default: none. The honest line for this period is the research and open-source work itself; never "career break", never invented consulting (CITED S38–S39).

**K2 · LB (per engagement)** — `team.your_share` literal-truth test
Ask: "For <engagement>, which of these sentences is literally true: 'sole engineer'; 'wrote ~X% of the code'; 'part of an N-person team'; 'requirements set by the client'; 'led a team of N'?" Then: "What was *not* yours — design, requirements, ops, QA?"
Default: **the scope sentence with numbers; never "led" without people who followed** (§14.4 table).

**K3 · ENR** — `interview_prep.who_reviewed_code`
Ask: "Who reviewed your code there? If nobody, what did you do to compensate — tests, CI, linters, external review?"
Default: none; prepared answer, never a resume line.

**K4 · ENR** — short tenures
Ask, for each engagement under three months: "Was it designed to be short — an internship, a fixed-scope contract, a practice placement? If not, is there one accomplishment from it?"
Default: designed-short → keep with a label; unplanned with an accomplishment → keep, one bullet; unplanned without → omit from the resume, keep in the master with `omitted_reason`, prepare the one-sentence explanation; **never shift dates** (§14.3).

**K5 · ENR** — concurrent-work representation
Ask: "For the roles that overlapped your studies, do you prefer separate entries labelled 'part-time, during BSc', or one umbrella entry 'Independent software developer, <year>–present' with client sub-entries?"
Default: umbrella for freelance clients; separate labelled entries for salaried or internship roles (§14.2).

**K6 · ENR** — NDA tier confirmation with the document in hand
Ask: "Now with the contract open: confirm the tier for <client> — A, B or C — and the exact public wording."
Default: as recorded at C9; wording per §14.1.

**K7 · ENR** — `interview_prep.weakest_claim`
Ask: "Which claim in this record would you least like to defend to a sceptical engineer?"
Default: none; whatever he names is re-tagged or softened before it reaches a rendering.

**K8 · ENR** — `representation{on_resume, on_academic_cv, on_europass}`
Ask: "Which engagements go on the job resume, which on the academic CV, which only in the master?"
Default: job resume = all substantive engagements with `M`/`E` numbers; academic CV = only what was built and is verifiable, after the research entries; FMI dossier = none (employment scores zero — do not spend proof effort on it).

**K9 · ENR** — 48–72 h follow-up
Ask: "What has surfaced since we last spoke — a client, a number, a date, a person?"
Default: none; append as delta notes with provenance.

**K10 · ENR** — kudos file going forward
Ask: "Where will you keep the running kudos file from now on, and what goes in it?"
Default: `cv-master/kudos.md`; every thank-you, review, referral, merged PR, launch email and "what happened after launch" note, dated (Ask a Manager, VERIFIED readable; brag-document practice CITED S5, S9, S10).

---

## 14. Special handling — the four cases

### 14.1 Freelance client confidentiality and NDA work

Decision tree per client (DESIGN; grounded in practitioner guidance S27–S29 and the legal findings in `adversarial-check-nda-resume-job-duties.md`, which VERIFIED Codul muncii art. 26 and 34(5), OUG 25/2019 art. 1(3)(b), and 2026 practitioner sources on freelance client-name bans):

1. **Is there a signed document?** Yes / no / unsure. **Unsure = yes** (adverse inference).
2. **Read the clause together** (C9). Record what it covers: client identity; the existence of the engagement; details and metrics; code, screenshots, demos; a sunset date.
3. **Assign the tier:**
   - **Tier A — named.** Only with written consent (one email; record the date). Entry names the client.
   - **Tier B — existence yes, details no.** Entry reads: *`<Industry> <size marker>, <city/country> (client name withheld under NDA)`* — e.g., "Bucharest logistics SME, ~40 staff (client name withheld under NDA)". Describe the technical patterns and public-scale magnitudes ("a multi-tenant booking system serving three sites"); keep exact internal metrics out. Avoid the phrase "no further details available" (practitioner dissent, S29).
   - **Tier C — nothing public.** Omit from public documents; keep the full record in `private.yaml` with the sunset date; consider a sanitised rebuild as a portfolio piece (EF9).
4. **Never rely on an NDA being unenforceable.** The only source saying so was US marketing and never mentioned resumes; Romanian and EU law treat a signed client-name or portfolio ban as potentially enforceable. What *is* always claimable for **salaried** roles: employer identity, title and duration — the employer must certify them (Codul muncii art. 34(5)); art. 26 binds an employee only to information designated confidential in the contract or internal rules. For **freelance** work the contract governs. (All VERIFIED in the adversarial check; the CV-specific application is INFERRED.)
5. **Default when the document cannot be found:** Tier B.
6. **Even under B or C the master keeps everything** — `nda{exists, covers[], sunset, copy_held}` — so a future consent or sunset upgrades the tier without re-interviewing.
7. **Consent request template** (DESIGN; send from his own address, one client per email):
   > Subject: A short favour — listing our work together
   > Hi <name>, I am putting together my CV. Could I (a) name <company> as a client for the <period> engagement, described as "<one-line scope>"? (b) If a future employer's background check asks, would you confirm the engagement and dates by email? (c) Would you be willing to be a reference? Any "no" is completely fine. Thank you — Andrei
   Record the answer and date under `verifiers[].status`.

### 14.2 Concurrent work overlapping study

Facts captured: hours per week (B18, `E(rate)`), overlap against semesters and exam sessions (B21), month-level dates with `sure`/`doubtful` (B17). Rules (dating rules INFERRED in the prior wave §10; F12 practitioner sources CITED S40: overlapping roles are acceptable, freelance may be grouped, ATS reads tenure not overlap):

- **Engineering resume:** either separate entries each labelled "(part-time, during BSc)" or one umbrella entry "Independent software developer, <first year>–present" with client sub-entries; dates MM/YYYY where `sure`; where a freelance engagement is `doubtful` to the month, show the year and put the duration in the bullet ("~3 months") rather than invent a month.
- **Academic CV:** concurrent work is unremarkable; it sits under "Professional experience" after the research entries; the reader cares what was built and whether it is verifiable.
- **FMI master dossier:** employment scores zero — list nothing, spend proof effort elsewhere.
- **Europass:** every role is its own entry (no umbrella concept); the hours-per-week field can carry the part-time fact.
- **Never** round part-time up to full-time, and never present a study-period freelance client as a salaried job.

### 14.3 Short tenures

Rules (CITED S37 Ask a Manager, S38 AARP, S31 REGES; representation choices DESIGN):

- **Designed short** (internship, practice, fixed-scope contract, seasonal): keep and label the design — "3-month internship", "fixed-scope contract, 6 weeks".
- **Unplanned short with an accomplishment:** keep, one bullet.
- **Unplanned short without one:** omit from the resume ("a marketing document, not a comprehensive accounting"); keep in the master with `omitted_reason`; prepare the one-sentence explanation for K4; **never shift or blur dates** — salaried dates are checkable through REGES and an employer's certificate.
- **Gaps under six months rarely need explanation**; years-only dates that hide duration are a known red flag — use MM/YYYY.
- **Post-graduation period (June 2025 → now):** the research manuscripts, the IberLEF entry and the open-source work are the line; not a career break, not "consulting".

### 14.4 Solo-engineer work (and AI-assisted authorship)

Literal-truth table (INFERRED in the prior wave §11, aligned with Kaplan-Moss's contribution-share pattern S7; the AI-assistance rows are DESIGN, consistent with the disk harvest caveat and 2026 maintainer policies):

| Allowed when literally true | Not allowed |
|---|---|
| "Sole engineer", "only developer", "designed, built and shipped end-to-end" | "Led a team", "managed developers", "we" without a we |
| "Wrote 100% of the application code; requirements set by the client" | "Led development" when nobody followed |
| "Owned architecture, implementation, deployment and support" | "Architected at scale" for a single-tenant app |
| "Part of a 3-person team; wrote ~60% of the backend" | Team outcomes stated as personal outcomes |
| "Sole engineer for a 12-screen app used by ~200 staff" (scope) | Adjectives in place of scope |
| "Designed, built and maintains; directed AI coding agents; wrote the architecture, tests and review gates" | "Hand-wrote 50k LOC" when most was generated; hiding AI assistance where a policy asks for disclosure |

Procedure: K2 per engagement (which sentence is literally true; what was not his), K3 (who reviewed the code; what compensated), I4 (AI-assisted share and personal decisions per project). When impact is unknowable, the honest achievement form is the scope statement (ladder rung R6), not an invented outcome.

---

## 15. The load-bearing path (answer these first, then stop)

Walk in this order. Stop 1 yields a truthful scope-only English resume plus the Romanian variant; Stop 2 adds the academic renderings; everything after is enrichment (Block D is the enrichment that matters most).

| Step | IDs | Count |
|---|---|---|
| Identity and contact | A1, A3, A4, A6 (+ A2 for the academic/legal renderings) | 4 (+1 LB-A) |
| Inventory | B5, B6; then per stub B16, B17, B18, B20 | 2 + 4 × N |
| Per engagement core | C1, C2, C3, C4, C5, C6, C7, C8, C9 (C9 only where a document was signed) | 9 × N |
| Languages | H1, H2 | 2 |
| Honesty | K1; K2 per engagement | 1 + 1 × N |
| **Stop 1 — job resume draftable** | **23 distinct LB IDs; walked = 9 + 14 × N** | |
| Education (academic) | A2, F1, F2, F4, F6, F7, F9, F10, F11 | 9 |
| Research (academic) | G1, G2, G3, G4, G6, G7, G8 | 7 |
| **Stop 2 — academic CV, FMI achievements list, SOP inputs draftable** | **+16 LB-A = 39 distinct load-bearing IDs** | |
| Tier 2 per engagement | D1–D22 and the E module | achievement bullets with tagged numbers |
| Remaining ENR | A5, A7–A14, B1–B4, B7–B15, B19, B21, C10, F3, F5, F8, F12–F15, G5, G9–G12, H3–H5, I1–I8, J1–J9, K3–K10 | tailoring, defensibility, hygiene |

Estimated time for Stop 1 with three engagements: ≈ 2.5 h across two sittings. Stop 2 adds ≈ 40 min.

---

## 16. Answer record format (DESIGN)

One YAML line per answer, appended to `intake-log.yaml`; the engagement records (`wave2-history-extraction.md` §12 schema) and `profile.yaml` (`x_master`, `x_metrics`, standard JSON Resume blocks per cv-studio `references/schema.md`) are compiled from this log, never edited by hand during intake.

```yaml
- id: C4
  engagement: eng-2024-03-xyz
  field: team.your_share
  value: "part of a 3-person team; ~60% of the backend"
  tag: E(enum)            # M | E(enum) | E(rate) | E(delta) | B | U
  date_confidence: null   # sure | doubtful (dates only)
  how_known: "counted the modules I owned vs the two others'"
  verifier: "founder, reachable-not-asked"
  evidence: []            # artifact ids from evidence/index.md
  verbatim: "eram trei, eu am scris cam 60% din backend"
  lang: ro
  asked: 2026-09-30
  status: answered        # answered | idk | deferred
```

Compilation rules: every `x_master` key is `"<work.name>|<work.position>"` and every bullet later written must trace to an achievement note here; every number in a bullet must appear in `x_metrics` with its tag and `how_known` — and the lint must also cover `projects`, `education`, `volunteer` and `summary` (the shipped cv-studio lint only scans `work[]` and passes silently when the banks are absent — proven holes in `wave2-multi-doc-system.md` §1 rows 5–6; patch before the first real build).

---

## 17. What this script changes relative to the earlier wave (from the adversarial checks)

1. **Probe typology** (`adv-check-probe-types.md`): Levashina et al. 2014 propose "verifying / quantifying" probes as examples in an untested typology; in selection interviews probing has been found to *increase* faking (Levashina & Campion 2007; Melchers 2020; Bill & Melchers 2022). Consequence here: the quantifying and verifying questions are pre-written and asked identically for every engagement (the OPM standardisation point, independently VERIFIED), "I don't know" ends them, and they are never used to judge truthfulness — artifacts and verifiers do that. The "intake is not selection" transfer remains INFERRED.
2. **NDA enforceability** (`adversarial-check-nda-resume-job-duties.md`): the "unenforceable" claim is dropped; §14.1 treats every clause as enforceable as written and records what Romanian law guarantees for salaried roles.
3. **Phenibut status** (`harvest-academic.md`): the manuscript is a ChemRxiv preprint since 2026-09-22; G1 asks for current status instead of assuming "unpublished".
4. **Ask a Manager heuristics** (`adversarial-check-search-rails-2026-09-23-resume.md`): the "mediocre person" test and "kudos file" were found verbatim in the posts, so D11 and K10 cite them as VERIFIED rather than as unverified snippets.
5. **REGES-Online** stays the first artifact (VERIFIED regime); Session 0 item 1.
6. **ORCID**: the empty record is fixed by granting the pending Crossref permission and linking the Zenodo DOI — a checklist item, not a question.

---

## 18. Sources

Evidence base and grading for every CITED rule: `wave2-history-extraction.md` §15 (S1–S40: Belli 2001/2000, Memon 2010, Flanagan 1954, McClelland 1998, Levashina 2014, Conrad 1998, Mathiowetz 1988, Wärneryd 1991, OPM/Hough 1984, UK ABE, Bock 2014, Harvard OCS, Kaplan-Moss, Jobscan, Evans, Legea 176/2018, 78/2014, 258/2007, REGES-Online 2025, Ask a Manager, AARP, LinkedIn career break). I did not re-read those sources in this session; "CITED" means cited as read and graded by that wave.

Additional local sources used here, all in this scratchpad: `VERIFIED-FACTS.md`; `harvest-academic.md`; `harvest-github.md`; `harvest-local-disk.md`; `wave2-academic-cv.md` §1, §3, §7, §8; `wave2-ro-language-variant.md` §3–§5, §7; `wave2-romania-market.md` (phone screening, salary bands, personal-data conventions, event dates); `wave2-gap-closing.md` §5 and R1–R15; `wave2-multi-doc-system.md` §1 (lint holes) and the cv-studio `references/schema.md`; `gap_fmi_master_method.txt` and `pdftext_UB_DOCT_2026.txt` (primary regulations, extracted by earlier waves); `adv-check-probe-types.md`; `adversarial-check-nda-resume-job-duties.md`; `adversarial-check-search-rails-2026-09-23-resume.md`. CEFR: Council of Europe global-scale descriptors as reproduced in the Europass self-assessment grid (framework CITED from general knowledge; my ladder wording is a paraphrase, DESIGN).

Rails note: no web fetches were made for this deliverable; nothing here depends on the search-hub keys that returned 401 earlier in the session. No credential was read, printed or modified.
