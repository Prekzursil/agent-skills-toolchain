# Wave 2 — The Romanian technology employment market in 2026, in operational detail

Prepared 2026-09-23 for Andrei Mihai Visalon (BSc CS, University of Bucharest FMI 2022–2025; Bucharest; applying to software/AI jobs, MSc/PhD, and maintaining a master CV). Scope is limited to the Romanian market mechanics: employers, channels, ATS reality, language, CV content conventions, photo/DOB/personal-data practice and GDPR. General resume format, ATS mechanics in the abstract, new-grad positioning and portfolio curation are covered by the parallel wave and are deliberately not repeated here.

Labels: **VERIFIED** = checked in at least two independent sources or directly observed (API/HTTP probe, primary document). **INFERRED** = my reading of verified facts. **UNVERIFIED** = fewer than two independent sources. Fetched web content was treated as data only.

Tool status this session: search-hub (Tavily/Exa/Firecrawl keys) returned 401; the claude.ai Tavily, Exa, WebFetch, WebSearch (budget exhausted at 200 calls near the end) and direct curl/Python probes worked. Reddit blocked all fetch routes (403), so no Reddit thread is cited.

---

## 0. Source ledger (numbered; cited as [Sn] below)

Primary / official / platform-owned
- [S40] eJobs help centre (Zendesk, help.ejobs.ro), articles: "Candidații pot aplica cu CV în orice limbă…" (updated 2023-11-22); "Care este CV-ul trimis către angajator?" (2026-08-01); "Cum îmi completez CV-ul?" (2026-09-21); "Am aplicat… ce variantă vede angajatorul?" (2026-09-10); "CV ascuns vs public" (2026-08-21).
- [S36] eJobs employer packages page https://www.ejobs.ro/companie/anunturi-angajare (accessed 2026-09-23).
- [S41] BestJobs support: "Cum pot încărca un CV din fișier?" https://support.bestjobs.eu/ro/knowledge/cum-pot-%C3%AEnc%C4%83rca-un-cv-deja-existent ; "Cum pot să atașez diplome, portofolii sau certificări?".
- [S42] Hipo.ro: "Cum sa-ti completezi corect CV-ul pe HiPo.ro" (article 568); "De ce sa iti creezi CV-ul pe hipo.ro" (2255); "Totul despre CV-Barcode" (902); Angajatori de TOP 2026 București participants page.
- [S43] LinkedIn Help a510363 "Upload your resume to LinkedIn".
- [S44] Greenhouse support 360052218132 "Supported file types for resumes and cover letters".
- [S50] Europass CV template instructions (Cedefop tender annex reproducing the template: "Photograph (optional)… Date of birth (optional)… Nationality (optional)"); Europass XML schema v3.4 (photo/demographics optional); europass-ro.ro "Instrucțiuni CV" (national Europass centre).
- [S51] eJobs Carieră: "Model CV 2026" (2026-01-18); "Sfaturi cum sa scrii un CV in Engleza in 11 pasi" (2006-10-09); "Poate poza în CV să-ți mărească șansele…" (2019, with reader comments and eJobs replies); "Depui CV-uri dar nu ești chemat la interviuri?" (eJobs staff reply: "Vârsta candidatului nu este afișată nici în CV-ul eJobs").
- [S53] Continental România, "Notă de informare privind prelucrarea datelor dvs. cu caracter personal în cadrul procesului de recrutare" (PDF, jobs.continental.com, created 2024-05-14).
- [S54] ANSPDCP, "Informare privind prelucrarea datelor cu caracter personal" for its own hiring competitions (dataprotection.ro ViewDocument?id=2135).
- [S55] Codul muncii (Legea 53/2003) art. 29 alin. (3) — text via codulmuncii.ro / lege5.ro.
- [S56] Legea 190/2018 (GDPR implementing law), art. 4 on national identification numbers — via euroavocatura.ro, dataprivacyblog.tuca.ro, isopedia.ro.
- [S49] FMI UB, "Admitere Master iulie 2026" and "Admitere doctorat 2026 – Școala Doctorală de Informatică" (fmi.unibuc.ro).
- [S26]–[S35] ATS probes (my own, 2026-09-23): Ashby posting API (UiPath), Greenhouse boards API (Bitdefender board `scbitdefendersrl`), SmartRecruiters postings API (Endava, Deloitte Romania, Ubisoft), HTML fingerprints (Accenture → Workday; NTT DATA → Phenom+Workday; Adobe → Workday host `adobe.wd5.myworkdayjobs.com`; Bosch → careers.smartrecruiters.com links), proprietary portals (jobs.careers.microsoft.com, amazon.jobs, careers.google.com/locations/bucharest, careers.oracle.com, careers.epam.com, career.luxoft.com). Control probes: nonexistent slugs return HTTP 200 on SmartRecruiters/Recruitee/Ashby web pages but 404 or `totalFound:0` on their APIs; attributions below rely on the API/fingerprint evidence, not on HTTP 200.
- [S47] My own sample of 40 live eJobs "IT Software" ads (first 40 listing IDs, 2026-09-23) pulled from `api.ejobs.ro/jobs/{id}` and classified by Romanian vs English function-word counts; saved as `ejobs_it_language_sample.json` in this folder.

Market reports and business press (2025–2026)
- [S1] getuhired.co "Tech Hiring Trends in Romania 2026" (9,943 unique tech postings, 2026-06-23 → 2026-09-20; methodology page linked).
- [S2] undelucram.ro, "IT salaries RON 8,000 net in H1 2026…" (2026-07-30, based on eJobs/Salario H1 2026).
- [S3] undelucram.ro, "Romania tech hiring hits −11% vs +35% globally" (2026-07-27, based on Experis Tech Talent Outlook Q3 2026); ManpowerGroup Q3 2026 report page (4,400+ employers, 42 countries) exists but its PDF was not machine-readable.
- [S4] Romania Insider, "eJobs: Bucharest accounts for nearly half of Romania's job openings in 2026" (2026-09-10).
- [S5] Ziarul Financiar, "eJobs: Peste 9 milioane de aplicări… primele 8 luni din 2026" (2026-09-03).
- [S9] Progresiv, "Bilanț eJobs: Peste 260.000 de joburi noi postate în 2025 și 11 milioane de aplicări" (2026-01-15) and [S10] cariera.ejobs.ro "Cum a arătat piața muncii în 2025" (eJobs Review & Trends 2026).
- [S11] Bursa, "Raport BestJobs 2026: numărul de aplicări per post s-a dublat…" (2026-06-10).
- [S12] Ziarul Financiar, "Harta banilor din industria de software şi servicii IT în 2025…" (2026-08-15).
- [S13] Romania Insider, "ANIS cautiously optimistic…" (2025-10-28); [S75] ANIS study coverage (revistabiz, digi24, cursdeguvernare 2025).
- [S14] cursdeguvernare.ro, "ANIS Sentiment Survey" (2025-10-02).
- [S15] termene.ro, "Firme IT România: +12 mld lei afaceri, mai puțini angajați" (2026-06-14; 2023 balance-sheet data).
- [S16] Ziarul Făclia (Cluj), "Radiografia IT-ului clujean în 2025. Top 10…" (2026-07-15; 2025 balance sheets).
- [S17] actualdecluj.ro, top IT companies 2022 (2023-07-08). [S18] listafirme.ro "Top 50 angajatori… (2026)".
- [S19] wall-street.ro, "Top 100 cei mai doriți angajatori din România" (Catalyst study, Nov 2024–Apr 2025, n=12,161); [S76] Romania Insider, Microsoft most desired employer (May 2026).
- [S20] undelucram.ro, "Top cei mai apreciați angajatori 2025".
- [S21] Ziarul Financiar / profit.ro / antena3 / adevarul on Oracle România's 2026 layoffs (526 people, garden leave) after ~400 in 2025.
- [S22] Ziarul de Iași, mediafax, startupcafe on Amazon Iași (504 positions cut in Retail Business Services; 3,424 employees end-2024 vs 4,234 in 2022).
- [S23] Ziarul Financiar / profit.ro on IBM România 2025 (revenue RON 1.26bn; avg 3,281 employees).
- [S24] Romania Insider "Romanian startups raised EUR 103 mln in 2025" (How to Web report) and The Recursive "Biggest Funding Rounds for Romanian Startups in 2025" (2026-01-23).
- [S25] undelucram.ro "10 giganți globali deschid huburi IT și de servicii în România" (2026-08-14, on a ZF analysis) and Forbes/wall-street on the Equans IT hub in Bucharest (2026).
- [S45] NapoleonCat, LinkedIn users in Romania (July 2026).
- [S46] Romania Insider, "Two-thirds of new jobs in Romania require knowing at least one foreign language" (2025-06-05, eJobs data).
- [S57] avocatnet.ro (2020) on the ANSPDCP 2019 annual report and recruitment; juridice.ro, A. Săvescu, "Ce facem cu CV-urile candidaților pentru joburi?" (2022-03-10); avocatnet.ro "GDPR și angajatorii: spețe" (2025-03-21).
- [S58] semnal.eu "Discriminarea la angajare: ce spune legea și cum se reclamă" (2026-09-13); jurnalul.ro and legal-easy.ro on CNCD cases.
- [S59] g4media/news.ro, "Sondaj BestJobs: 1 din 3 recrutori recunoaște că a refuzat… din cauza vârstei" (2023-02-06; n=1,122 candidates, 214 recruiters).
- [S60] business24.ro / ziare.com, "Primul loc de muncă… 2026" (2026-04-18, HR consultant Cristina Profeanu).
- [S61] start-up.ro, "Joburi în IT în 2026… Tudor Dumitrescu" (2026-02-12).
- [S62] hackingwork.ro on Brainspotting "Tech Salary & Employment Behavior 2025" (2025-03-12; n=5,801).
- [S63] academiaprogramatorilor.ro, "Cum să pregătești un CV perfect pentru interviuri IT… 2026" (2025-12-16).

Practitioner accounts
- [S6] Cristian T. (recruiter), LinkedIn post on job-board relevance, 2026-07-14.
- [S48] Camelia Macsim (CV writer) LinkedIn thread on CV language (2020-09-23); Andrei Georgescu LinkedIn post "în ce limbă îmi fac CV-ul?" (2026-06-12); Lexis.ro "CV în engleză"; Jobseeker.com/ro "CV în engleză" (2025-04-30).
- [S68] Talentuch webinar write-up with Rareș Cîrligeanu (2026-08-10). [S69] BrainSource "Why senior hiring in Romania requires a proactive approach" (2026-03-06). [S70] Tallenxis "What to expect in Romanian job interviews (2026)" (2026-06-30). [S67] Wise Step Recruiting "How to hire remote developers in Romania: 2026 playbook" (2026-04-17).
- [S7] Bucharest Balance Sheet (Radu-Ioan Stochiță), "Where are all the IT jobs?" (2026-07-09). [S8] Organisationsdiplomaten whitepaper, T. Winz, "The end of the outsourcing model?" (Feb 2026).

SEO/marketing guides (low weight; used only to document what candidates are being told)
- [S64] taurusid.com "How to write a CV for jobs in Romania" (2026-09-14); [S65] jobera.com (2023), resumeflex.com (2025-04-30), visualcv.com; [S66] ophyai.com "Romania job interview guide 2026" (2026-03-22); [S52] undelucram.ro "7 greșeli legate de poza din CV" (undated); model-cv.ro (2026-01-14).

---

## A. State of the market, 2025 → Q3 2026

A1. **VERIFIED. 2025 was a contraction-and-caution year; 2026 is a high-competition year.** eJobs posted >260,000 new jobs in 2025, about 10% fewer than 2024, while applications rose ~10% to 11 million; >95% of posted jobs required office presence; the 10,000 remote jobs (4%) drew 1.4 million applications (13%) [S9][S10]. BestJobs reported active job offers down by about a third in Q1 2026 (to just over 40,000) while applications passed 3 million (+20%), doubling the average from ~40 to ~80 applications per post [S11]. eJobs recorded >9 million applications in Jan–Aug 2026 (+28% y/y, a ten-year high) against 143,000 postings: 63 applications per job overall, and **89.1 per IT/telecom job**, second only to retail [S5].
   For the owner: every application into the Romanian job boards competes with roughly 60–90 others for the same IT ad; the board is a volume channel, and differentiation must come from evidence (repos, research, referrals), not from being early or numerous alone.

A2. **VERIFIED. IT is still the best-paid sector but the hiring signal is negative.** eJobs/Salario H1 2026: IT average net RON 8,000/month (+5% y/y), the highest sector, while candidates asked for RON 11,993 (a 50% gap, the widest of any sector); June 2026 inflation 10.4% erased the nominal gain [S2]. Industry associations describe a plateau: ANIS counted 195,929 employees in 2024, "a stabilization on a plateau after the boom of 2022" [S13]; in the ANIS survey (Aug–Sep 2025) 54% of member firms held headcount, 31% grew, 15% cut, and **31% said they reduced junior-level roles** while 44% hired advanced skills [S14]. ZF's balance-sheet map of 45,955 firms shows 2025 turnover of RON 90.3bn (+8.2%), with Bucharest producing 56% and Bucharest+Cluj+Timiș+Iași ~85%; Cluj was "the only large pole growing both in business and headcount"; game publishing cut staff sharply [S12].
   For the owner: a junior/early-career AI or software profile is entering the segment employers say they are trimming; the cushion is that the market is not closed but "repositioning" toward AI skills (see A3) and that Bucharest holds most of the volume.

A3. **UNVERIFIED (single primary report, widely repeated). Q3 2026 net hiring intention in Romanian tech: −11%.** The Experis Tech Talent Outlook Q3 2026 (ManpowerGroup; 4,497 tech/IT employers in 42 countries) puts Romania last with Slovakia (−10%) versus a global +35%; employers' top wanted skill is AI modelling/application development (34%), then foundational AI knowledge (30%) [S3]. The ManpowerGroup page confirms the report exists with this sample but the PDF could not be parsed, so the Romanian figure rests on one secondary write-up.
   For the owner: treat 2026 as a buyer's market for employers; skills that the same report says are being bought (applied AI, cloud) are exactly the owner's public repo footprint, which should be foregrounded.

A4. **VERIFIED (observed dataset). What tech employers actually posted, Jun 23–Sep 20 2026:** 9,943 unique tech postings (≈768/week); Bucharest 5,910, Cluj-Napoca 773; 70% mid-senior, 18% entry level, 7% associate, 1% internship; 63% on-site, 20% remote, 17% hybrid; only 1% of tech postings disclose salary (vs ~40% of all eJobs ads in 2025 [S9]); Backend Engineer (2,323) and Full-stack (1,521) lead; Python (2,137 mentions), SQL, Azure lead skills; "consulting/outsource" employers posted 3,794 of the 9,943 [S1].
   For the owner: (i) the realistic entry door is the 18% "entry level" plus "associate" band, largely in outsourcing/consulting and fintech captives; (ii) Python + SQL + Azure/AWS vocabulary must be literally present in the CV because that is what is being searched; (iii) salary is almost never in the ad, so the owner needs an external benchmark (see H).

A5. **VERIFIED. Bucharest concentrates roughly half of all vacancies.** Of ~150,000 eJobs postings between January and 10 September 2026, 71,000 were in Bucharest; ~60% of all ads targeted entry-level candidates (all sectors, not IT-specific) [S4]. Termene's CAEN analysis: 50% of Romania's IT employees (85,109 of 170,201, 2023) work in Bucharest, then Cluj 28,818, Timiș 17,254, Iași 8,445 [S15].
   For the owner: being in Bucharest is the right place; Cluj is the only other pole worth a targeted search (AI-dense per [S67], see contested C7).

---

## B. Who the significant employers are (software and AI), with verified application systems

B1. **VERIFIED. Largest software/IT-services employers by headcount (latest filed figures).** Endava Romania 4,023 average employees in 2025 (Cluj-registered; up 21% per the same article despite −7% revenue) [S16][S18]; Accenture Services SRL 4,505 (2026 listing) [S18]; Oracle România >4,000 before its June 2026 cut of 526 (after ~400 in 2025) [S21]; Amazon Development Center Romania (Iași; also Bucharest) 3,424 at end-2024, down from 4,234 in 2022, minus 504 in 2026 [S22]; Vodafone Romania Technologies 3,567 and IBM România 3,053 (2023) [S15], IBM 3,281 avg in 2025 [S23]; Luxoft Professional Romania 2,409 (2023) [S15]; Cognizant Romania 2,417 (2025, Cluj) [S16]; Eviden (Atos) 2,245 (2023) [S15]; Betfair Romania Development 1,882 (2025, Cluj) [S16]; Continental Autonomous Mobility Romania 1,969 (2023, Timișoara) [S15]; UiPath SRL 1,112 employees and the sector's largest turnover (RON 2.86bn, 2023) [S15]; NTT DATA România 1,017 (2025, down 13%, loss-making) [S16]; Accesa 1,045, Nagarro 835, Darwin 704, Arobs 594 (Cluj, 2025) [S16]; Bitdefender 2,000+ (Wikipedia figure, UNVERIFIED precision).
   For the owner: the headcount leaders are outsourcers/captives (Endava, Accenture, Luxoft, Cognizant, NTT DATA, Eviden, GlobalLogic, EPAM, Capgemini, HCLTech, Inetum, ALTEN, SII) and they are also the top posters [S1]; product/R&D employers (UiPath, Bitdefender, Adobe, Amazon, Microsoft, Google, Oracle) are smaller in postings but are where AI roles concentrate (B3).

B2. **VERIFIED. Top posters of tech jobs in Romania, Jun–Sep 2026** (unique postings): Luxoft 373 + Luxoft Romania 158, NTT DATA 137, Worldline 111, GlobalLogic 93, Accenture 92, ING Hubs Romania 91, ALTEN 86, SII Group 71, Deutsche Bank 69, HN Services 68, HCLTech 67, nLight Media 63, Siemens Energy 63, Inetum 58, VOIS (Vodafone) 54, Capgemini 53, Endava 46, EasyDo 46, Marsh 45, EPAM 45, LSEG 44, Thales 43, Ascendion 42, eMAG 40 [S1].
   For the owner: this is the "volume" tier; bank/fintech captives (ING Hubs, Deutsche Bank Technology Centre, LSEG, Worldline, Marsh) are a distinct, often overlooked sub-market that hires backend/data engineers in Bucharest in English.

B3. **VERIFIED. Where AI/ML engineering roles are posted in Bucharest (2026 postings observed):** UiPath (Senior Applied Scientist, Bucharest, Ashby board, 2026-04) [S26]; Adobe (ML Services / Firefly GenAI Romania services team; Senior ML Engineer Firefly; Principal Engineer, Agentic Builders — all Bucharest, 2026) [S27]; Bitdefender (Lead Data Scientist / production ML+LLM stack, Bucharest; Greenhouse board with 53 open jobs, ~29 in Bucharest) [S28]; Thales (AI/ML Engineer, Bucharest, 2026-04) [S34]; Siemens Energy (Experienced AI/ML Engineer, Bucharest, finance CoE) [S34]; Accenture ("AI/ML Computational Science Associate", Early Career, Bucharest, posted 2026-09-15) [S29]. Product startups with 2025 capital: Druid AI (EUR 27.5M Series C, enterprise AI agents), Digitail (EUR 20M), Bible Chat (EUR 13.4M), Deepstash, dotLumen [S24]. Multinational engineering centres: Amazon Bucharest (Alexa speech/language, AWS EC2 teams) and Iași (20 years in 2025) [S35]; Google Bucharest engineering (post-Fitbit) [S35]; Microsoft Romania Development Center (Bucharest, plus Iași Movial team; ~1,800 staff per ESOP, UNVERIFIED precision) [S35]; Oracle Bucharest (shrinking) [S21].
   For the owner: the owner's profile (agent infrastructure, MCP servers, local-first AI tooling) maps most directly onto UiPath (agentic automation), Adobe's agentic-builders/Firefly services team, Druid AI, Bitdefender's ML platform team, and Accenture's early-career AI track; these are the first-tier targets and all recruit through their own English-language portals (B4).

B4. **VERIFIED by API/fingerprint probe (2026-09-23). Application systems actually in use by relevant employers:**
| Employer | System | Evidence |
|---|---|---|
| UiPath | Ashby | `api.ashbyhq.com/posting-api/job-board/uipath` returns 100 jobs; live Bucharest posting on jobs.ashbyhq.com/uipath [S26] |
| Bitdefender | Greenhouse | board token `scbitdefendersrl` found in careers page; boards API returns 53 jobs, majority Bucharest [S28] |
| Endava | SmartRecruiters | postings API: 183 postings, 43 of the first 100 located in RO [S30] |
| Deloitte Romania | SmartRecruiters | postings API: 6 postings, all RO [S32] |
| Ubisoft (incl. Bucharest studios) | SmartRecruiters | postings API: 300 postings [S32] |
| Bosch (incl. Cluj engineering centre) | SmartRecruiters | jobs.bosch.com links to careers.smartrecruiters.com (46 links) [S31] |
| Accenture Romania | Workday | `accenture.wd103.myworkdayjobs.com/ro-RO/AccentureCareers`; HTML fingerprints [S29] |
| Adobe | Workday (Phenom front) | `adobe.wd5.myworkdayjobs.com/external_experienced` live; careers.adobe.com job IDs `R1xxxxx` [S27] |
| NTT DATA | Phenom front + Workday | 123 Phenom and 1 Workday fingerprints on careers.nttdata.com [S33] |
| Microsoft, Amazon, Google, Oracle, EPAM, Luxoft | Proprietary portals | jobs.careers.microsoft.com; amazon.jobs; careers.google.com; careers.oracle.com; careers.epam.com; career.luxoft.com [S35] |
| Zitec, Tremend, Fortech, Levi9, FintechOS, Druid, Evozon, eMAG, ING Hubs, Cognizant, Thales, Worldline, Capgemini, GlobalLogic | UNVERIFIED | vendor web pages returned 200 but vendor APIs returned zero postings or 404; the careers pages are JS-rendered with no fingerprint |
   Control: nonexistent company slugs also return HTTP 200 on SmartRecruiters, Recruitee and Ashby web pages, so any "X uses Y" claim based only on a 200 was discarded.
   For the owner: (i) one ATS-safe English PDF (single column, real text, standard headings) covers Workday, Greenhouse, SmartRecruiters and Ashby; (ii) Workday (Accenture, Adobe) and Greenhouse parse the file into fields, so section headings must be conventional ("Experience", "Education", "Skills", "Projects", "Publications"); (iii) Ashby/Greenhouse boards expose public APIs, so the owner can script alerts for "Bucharest" + "machine learning|applied scientist|agent" without scraping.

B5. **VERIFIED. Restructuring is concentrated in a handful of multinationals; new captive centres keep opening.** Oracle România: 526 layoffs announced June 2026 with 2-month garden leave and 3–12 months' severance, after ~400 in 2025 [S21]. Amazon Iași: 504 positions in Retail Business Services in 2026 (Ziarul de Iași: no IT specialists affected) [S22]. Whitepaper figures (single source, UNVERIFIED individually): Endava −1,239 (2022–24, closed Craiova and Sibiu), Continental/Aumovio −870 (Timișoara ADAS, 2025), UiPath −445 (2024–25; Bucharest QA closed), Microsoft Romania −180 (2025), Bitdefender −150 (2025) [S8]. On the other side, a ZF analysis reported ten international groups announcing technology/service centres in the last year, five with ~600 concrete positions (Müller, Zalando, Engie, Kärcher among them; roles include AI/ML and cybersecurity), mostly in Bucharest, then Cluj and Timișoara [S25]; Equans opened a 150-specialist IT hub in Bucharest (One Cotroceni Park, March 2026) [S25].
   For the owner: newly opened captives hire in waves and in English, and are under-applied relative to the famous names; monitoring ZF/Romania Insider "new hub" announcements is a cheap sourcing channel.

B6. **VERIFIED. Employer-brand preferences of Romanian candidates (relevant for where competition is fiercest).** Catalyst "Cei mai doriți angajatori" 2025 (n=12,161 early-career and professional respondents): Microsoft, Google, Continental, Oracle, ING, Bosch, Amazon, IBM, Banca Transilvania, eMAG top 10; Bitdefender 13, Adobe 16, Endava 22, UiPath 24, Accenture 26, NTT DATA 35, Betfair 46 [S19]; Microsoft ranked first for the sixth consecutive year in May 2026 [S76]. Employee-rated ranking (undelucram, 2025) includes Zitec (19), msg systems (25), ING Hubs (26), SAP Romania (27), Infineon (29), EveryMatrix (31), Microsoft (36), Siemens (38) [S20].
   For the owner: the most-desired names receive the most graduate applications; the employee-rated list surfaces mid-size product/engineering employers (Zitec, msg, EveryMatrix, Infineon, SAP Romania) where a strong open-source profile stands out more.

---

## C. Channels: which platform is primary, and what each expects

C1. **VERIFIED. eJobs is the largest local board by every published metric; BestJobs second; Hipo is the graduate/young-professional niche; LinkedIn is the professional network with the largest reach.** eJobs: >260,000 jobs and 11M applications in 2025, 305,000 new candidate accounts in 2025, ~5M CVs in database, "over 4 million specialists" reachable [S9][S10][S36]; BestJobs: "over 4.6 million professionals connected", 35,000+ jobs at any time, 3M+ applications in H1 2026 [S11][S59]; Hipo: jobs "exclusively for candidates with higher education", ~1,000 employers, 550,000 monthly visits (Hipo's own claim, UNVERIFIED), and the Angajatori de TOP fairs (180+ companies, 8,000+ jobs per edition) [S42]; LinkedIn: 5.87 million users in Romania in July 2026 (31% of population; 40.9% aged 25–34) [S45] (single data provider, NapoleonCat via LinkedIn's marketing API; UNVERIFIED by the two-source rule).
   For the owner: keep live profiles on all four; eJobs and LinkedIn are mandatory for reach, Hipo is mandatory for the graduate fair mechanism (C4), BestJobs is cheap to maintain via file upload (C3).

C2. **VERIFIED (platform's own help centre). eJobs mechanics.** The eJobs CV is a structured profile, not a file: candidates can fill a Romanian and an English version ("Momentan sunt disponibile doar cele două variante"); on applying, the whole profile including both versions is sent, the more complete version is shown first, and an employer can flag "Completează CV-ul în engleză" [S40]. Profile edits propagate in real time to employers who already received it; the CV can be public (searchable by employers who buy database access) or hidden [S40]. Employers can buy "Integrarea ATS gratuită" and "Aplicare externă opțională" (redirect to their own ATS) plus "până la 10 candidați recomandați AI" in the Business+ packages [S36]. In my 40-ad sample, 8 of 40 IT ads used external apply [S47]. eJobs's own advice: apply within one to two weeks of posting, keep the profile current, and (in "Model CV 2026") use a recent portrait photo with office-casual dress [S51]. The eJobs profile does not display the candidate's age to employers (eJobs staff reply) [S51].
   For the owner: fill BOTH the Romanian and the English eJobs profile to the same completeness (the employer sees both); upload the English master PDF as the attached file; expect that for multinational ads the click will bounce to Workday/SmartRecruiters where the PDF, not the eJobs profile, is what gets parsed.

C3. **VERIFIED (platform's own help centre). BestJobs mechanics.** Upload an existing CV in .pdf or .doc, max 10 MB; the file is parsed automatically into the profile "except personal data"; up to 10 attachments (PDF, DOCX, images) for diplomas/portfolios; an in-platform AI assistant edits content [S41]; since 2026 BestJobs runs "Bestie", an AI agent doing pre-screening, an initial interview and intent-based matching before a recruiter sees the application [S11].
   For the owner: a .docx master is not accepted for the main upload (.doc/.pdf only); use the PDF; assume an AI pre-screen reads it before any human, so the first 5 lines must state role target, stack and location plainly.

C4. **VERIFIED (platform's own pages). Hipo mechanics.** Profile is a four-step form (experience with results/KPIs, studies from university upward, skills with a harmonised language-level scale, target job/city); up to five CVs and five cover letters; PDF export; the "CV-Barcode" is printed once and scanned at each employer stand at Angajatori de TOP, entering the company database in real time [S42]. 2026 editions: Bucharest 27–28 March and 30–31 October (Sala Palatului), Timișoara in parallel; entry is free with the Barcode CV [S42]. Hipo lists Microsoft, Oracle, Deloitte, IBM, KPMG, P&G, Continental, Michelin among recruiting employers [S42].
   For the owner: the 30–31 October 2026 Bucharest fair is the one physical channel where a new graduate meets 100+ employers in two days; prepare the Hipo profile now (it has to exist to print the Barcode), and treat the fair as the way into Accenture/Deloitte/IBM early-career pipelines rather than into product AI teams.

C5. **VERIFIED. LinkedIn mechanics and how recruiters actually source.** Easy Apply accepts Word or PDF and recommends under 2 MB [S43]. Recruiters report that job-board relevance has fallen to under 5–10% of applicants ("acum 4–5 ani… 20–25%… astăzi rar mai treci de 10%") and that companies respond with pre-screening questions, ATS scoring and AI summaries; the advice is "un CV ușor de citit, un profil LinkedIn coerent, experiență relevantă și răspunsuri bune la întrebările de screening" [S6]. For senior and niche roles, referrals and network introductions "carry far more weight than job boards" and cold applications rarely convert [S69]; sustainable pipelines rely on employer branding, university partnerships and referrals [S68]; Romanian hiring "shifted from volume hiring to precision recruitment" (Catalyst, 2026) [S42].
   For the owner: the LinkedIn profile is the document most Romanian recruiters will see first for tech roles; keep the headline bilingual-neutral (English), add the secondary Romanian profile language, and treat GitHub links in the profile as evidence recruiters check.

C6. **VERIFIED. Salary transparency differs by channel.** ~40% of eJobs ads showed a salary in 2025 (102,000 ads) ahead of the EU pay-transparency directive [S9], but only 1% of tech postings in the getuhired dataset disclosed a range [S1]; salary is discussed early in Romanian processes (screening call or first interview) [S70].
   For the owner: prepare a number before the first call; benchmarks in H.

---

## D. Do Romanian employers use ATS at the same rate as US employers?

D1. **UNVERIFIED — no Romanian adoption survey exists.** Two searches for a Romanian ATS-adoption percentage returned only global figures (75% of recruiters / 98% of Fortune 500) and vendor pages; no ANIS, HR-barometer or platform survey gives a national rate.

D2. **VERIFIED. What can be said instead.** (i) Every multinational and large outsourcer checked runs a global ATS (B4). (ii) The two dominant local boards have become the de-facto ATS layer for Romanian SMEs: eJobs sells ATS integration and external-apply redirection and AI candidate recommendation to employers [S36]; BestJobs runs AI pre-screening [S11]; Romanian ATS vendors (Mingle, Recrutio) explicitly target SMEs that otherwise manage applications inside eJobs/BestJobs/Hipo inboxes [S38]. (iii) Recruiters describe ATS, scoring and AI summaries as the response to application volume [S6]; a 2026 recruitment-agency guide describes "AI-based applicant tracking systems" as common [S39] (marketing source).
   INFERRED: the functional answer is "yes for anyone with an HR department or a foreign parent; for Romanian SMEs the job board's own inbox plus its AI screening is the ATS". Parsing risk therefore exists on every channel, including the local ones.
   For the owner: build the master CV for machine parsing first and human reading second; no tables, no two-column layouts, no photo inside the parsed PDF used for ATS portals (a separate "traditional Romanian" variant can carry a photo, see G).

---

## E. Language: when Romanian is required and when English is the default

E1. **VERIFIED. English is required in the plurality of all Romanian job ads and is "implicit" for white-collar roles.** eJobs, Jan–May 2025: of 112,000 jobs, 64,000 (~57%) stated a foreign-language requirement; 48,000 required English, 8,100 German, 3,400 French; Roxana Drăghici (eJobs): "in the case of white-collar jobs… English is implicit" [S46].

E2. **VERIFIED (own observation, 2026-09-23). Live IT ads on eJobs are mostly written in English, including by Romanian SMEs.** Of the first 40 "IT Software" listings (alphabetical slice, not random), 24 were English-dominant and 16 Romanian-dominant; six of the 16 Romanian ones are eJobs Group's own "free IT course" ads, not jobs, and seven ads had near-empty descriptions. Among the 27 substantive job ads, 20 (74%) were in English. Romanian-language ads came from in-house IT at non-tech Romanian companies and state-owned entities (City Grill Group, Teletrans SA, Integrator Soft), a field-technician role (Orange), a Sibiu support role (Stefanini, bilingual) and one of two ads from a small consultancy (Accelera); English ads came from outsourcers and consultancies large and small (ALTEN, Optima Solutions, TR IT Team, Zynk, HQ-Solutions, Green Gate, ADP, cbs, JustRocket, GoDaddy, ManpowerGroup) [S47]. Practitioner corroboration: "Este o modă ca anunțul să fie în engleză, sunt foarte puține anunțuri de job în limba română, chiar dacă jobul este în România" (thread, 2020) [S48]; 2026 guides state tech interviews are "almost always conducted in English" (SEO source, [S66]) and that English is "excellent" across the Romanian engineering workforce [S68]; EF EPI 2025 rank #11 for Romania (single source, [S67]).
   For the owner: for developer/AI roles the English CV is the default artifact at multinationals, outsourcers and most tech SMEs; a Romanian CV is needed for (a) public-sector and state-owned employers, (b) in-house IT at Romanian non-tech companies, (c) academic dossiers where the form is Romanian, and (d) any ad written in Romanian (send the CV in the language of the ad — the consistent practitioner rule [S48]).

E3. **CONTESTED (see I). Whether multinationals prefer the English CV.** One 2026 practitioner argues most multinationals "recruit locally in Romanian and translate internally", and that a flawed English CV is worse than a solid Romanian one [S48]; others (and the observed English-only portals in B4, and eJobs's "Completează CV-ul în engleză" employer flag [S40]) point the other way.
   For the owner: keep both versions at equal quality; when unsure, English for tech, Romanian for everything Romanian-facing; never a literal translation of one into the other (both [S48] and eJobs's own 2006 guide warn against calques).

E4. **VERIFIED. Academic track (FMI UB) language rules.** FMI's English-taught master programmes (Artificial Intelligence, Data Science, Natural Language Processing, Security and Applied Logic, Advanced Studies in Mathematics) require a B2+ certificate from a Ministry-recognised body (bac certificates not accepted), or a degree taught in English, or two passed semesters of English at licence level; UB graduates can use the UB language certificate; admission is dossier + online oral exam [S49]. The Informatics Doctoral School (SDI) admitted in July 2026 with 2 funded places with scholarship, 1 priority place, 5 part-time funded and 10 fee-paying; registration by e-mail with a downloadable form and a 300 RON fee; "conform Metodologiei UB, concursul se desfășoară fizic" [S49].
   For the owner: as a UB licence graduate, secure the UB English-competence certificate (or use the two-semesters rule) before the next FMI master cycle; the SDI has very few funded places (3 with scholarship in 2026), so a doctoral application is realistically a 2027 target that needs a supervisor contact and a publication record (ORCID currently empty).

---

## F. What a Romanian CV conventionally contains that a US resume does not (and vice versa)

F1. **VERIFIED. The Europass legacy explains the Romanian "personal details" block.** The Europass CV template carries optional fields for photograph, date of birth, nationality (and signature) [S50]; the Romanian national Europass centre's instructions tell candidates to "includeți o adresă de e-mail și o fotografie" [S50]. eJobs's own (2006) guide to the English CV told Romanians to put name, address, phone, e-mail, date of birth, marital status and nationality at the top [S51]; eJobs's Model CV 2026 still has a photo section and advises a recent portrait in office-casual dress [S51]. Romanian-language guides from 2025–2026 describe the Romanian CV as 1–2 pages, reverse-chronological, with photo "usually expected but not mandatory", languages with CEFR levels, and sometimes driving licence, hobbies and "references on request" [S48 Jobseeker][S63][S65].
   VERIFIED (US side, for contrast, from the same Romanian sources): US resumes omit photo, date of birth, nationality and marital status, run one page, and lead with quantified achievements [S48][S51].
   For the owner: the master document should follow the US/ATS structure (no photo, no DOB, no nationality, no marital status, no address beyond city, quantified bullets) because that is what every verified multinational portal and the eJobs profile parser want; Romanian-specific additions that cost nothing and are expected locally are CEFR language levels (Romanian native, English C1/C2 with a certificate if available), a driving licence line only if relevant, and a short "Despre mine/Profile" paragraph.

F2. **VERIFIED. Europass itself is now a segment-specific format.** Multiple Romanian career sites say private-sector recruiters skip or dislike Europass and prefer a concise custom CV, while Europass is still expected when an ad or a public-sector/EU-funded/academic dossier explicitly asks for "CV format Europass" [S64][S48 Jobseeker][S51 eJobs Europass tag]. Hipo's recruiter-authored guide: "e greu să reții un CV din 200 dacă toate sunt în exact același format (ex: CV European)" [S42].
   For the owner: keep a Europass export ready (europass.europa.eu can generate one from a profile in minutes) for university competitions, EU-funded projects and any public body; never send it to a tech employer unless asked.

F3. **INFERRED from B4, C2–C4, F1. Romanian employers vs multinationals hiring into Romania — where the expectations diverge.**
| Dimension | Romanian employer (SME, in-house IT, public/academic) | Multinational / large outsourcer hiring into Romania |
|---|---|---|
| Intake | eJobs/BestJobs inbox, e-mail, Hipo fair; sometimes Europass requested | Own ATS (Workday, Greenhouse, SmartRecruiters, Ashby, proprietary); job-board ads redirect there |
| Language | Romanian ad → Romanian CV; many still write ads in English | English ad, English form, English interviews; Romanian not required for tech roles |
| Photo | Tolerated to expected (eJobs, undelucram guidance) | No field for it; EEO statements (e.g. Adobe) list age/appearance as protected; safest to omit |
| DOB / age | Common in Europass-style CVs; eJobs hides age; 1 in 3 recruiters admit age bias (2023) | Not requested; structured forms ask only what is needed |
| Length | 1–2 pages accepted | 1–2 pages, parsed into fields |
| Personal data | CNP/ID sometimes requested only at contract stage (Continental lists CNP as a recruitment-stage category) | CNP/ID at onboarding, not with the CV |
| Salary talk | Early, often screening call | Early screening question in most processes |
| Sourcing | Job boards, referrals, fairs | LinkedIn sourcing, referrals, employer brand, university partnerships |
   For the owner: maintain one master (English, ATS-safe, no personal data) and derive two variants: RO-traditional (Romanian, optional photo, Europass-exportable) and RO-academic (Romanian or English per call, with publications/ORCID once populated).

---

## G. Photo, date of birth and personal data in practice, and the GDPR angle

G1. **VERIFIED. The law limits what an employer may ask, but does not ban photo or DOB on a CV.** Labour Code art. 29(3): information requested from a candidate "nu pot avea un alt scop decât acela de a aprecia capacitatea de a ocupa postul respectiv, precum şi aptitudinile profesionale" [S55]. Law 190/2018 art. 4: processing a national identification number (CNP, ID series/number, passport, driving-licence number) on the basis of legitimate interest is allowed only with data-minimisation and security safeguards [S56]; the ANSPDCP's 2019 report stressed that recruitment processing must be limited to data necessary for recruitment and kept only as long as necessary, with information, objection, erasure and consent-withdrawal rights [S57]; practitioners advise employers to inform candidates and to avoid resting on "legitimate interest" alone [S57]. OG 137/2000 prohibits age, gender, ethnicity and similar criteria in hiring; CNCD handles complaints within one year and can fine (up to 200,000 lei cited), with a partial reversal of the burden of proof [S58].
   For the owner: nothing obliges a photo, DOB, nationality, marital status or CNP on a CV; a request for CNP before an offer is a red flag under Law 190/2018; age-based rejection is actionable but hard to prove.

G2. **VERIFIED (employer and DPA primary documents). What organisations say they collect at recruitment stage.** Continental România's candidate notice lists, as recruitment-stage categories, standard data "ex. nume, prenume, adresa de domiciliu, data nașterii", national identification numbers "ex. seria și numărul actului de identitate, CNP", platform usage data, assessment results, education/work history, contact data, and "Fotografii, înregistrări video și audio (ex. fotografie curriculum vitae)"; candidate data and profile are deleted automatically six months after the recruiter closes the evaluation; legal bases cited are GDPR and Law 190/2018 [S53]. The ANSPDCP's own notice for its hiring competitions lists CNP, ID series, birth date and place, citizenship, marital status, criminal record, health certificate and "imaginea" as collected, retained 10 years if not hired (public-sector contest rules) [S54].
   INFERRED: a CV photo is treated by a major multinational as ordinary candidate data (collected if supplied, not required); public-sector competitions collect far more personal data by law than private employers do.
   For the owner: expect six-month retention at multinationals and long archiving in public competitions; keep the personal-data footprint in the CV minimal because whatever is in it is what gets stored.

G3. **VERIFIED. Age bias is real and measured; platforms have reacted.** BestJobs survey (Jan–Feb 2023): 80% of candidates over 45 perceive recruiter reticence, 1 in 3 recruiters admit having refused a candidate because of age, 15% say age matters and 57% "depends on the job"; recruiters look mainly at experience and studies (>85%) and location [S59]. eJobs states that candidate age is not displayed in the eJobs CV [S51]. ANSPDCP has fined a company (three fines totalling 34,839 lei) for a recruitment e-mail sent to the wrong person that disclosed a candidate's data [S57].
   For the owner: at 30-something (INFERRED from a 2025 BSc), age is not a disadvantage in Romania, but leaving DOB off costs nothing and matches both eJobs's design and multinational norms.

G4. **CONTESTED (see I). Whether to include a photo.** Pro-photo: eJobs Model CV 2026 [S51], undelucram "7 greșeli legate de poza din CV" [S52], the national Europass centre [S50], Follow Me/Jobseeker/model-cv.ro guides ("poză profesională obligatorie la majoritatea joburilor", SEO) [S48][S65]. Anti-/neutral: Lexis.ro (omit marital status, CNP, photo "în multe cazuri") [S48]; taurusid (omit for multinationals with diversity policies; "some ATS can ignore" images) [S64]; reader pushback on eJobs's own article citing ethnic discrimination [S51]. No Romanian survey quantifying recruiter preference for photos was found; the "72% of recruiters consider a photo important (BestJobs)" and "over 60% of private-sector recruiters prefer a concise CV over Europass (eJobs)" figures appear only on one SEO page and could not be traced to BestJobs or eJobs [S64] — UNVERIFIED.
   For the owner: omit the photo from the master and from anything that goes through a multinational ATS; include a plain portrait only in the RO-traditional variant and on the eJobs/LinkedIn profiles, where a photo is the platform norm.

---

## H. The junior/early-career segment, specifically

H1. **VERIFIED. Juniors are the segment being squeezed, but not closed.** 31% of ANIS members reduced junior roles in 2025 [S14]; only 18% of tech postings target entry level and 1% internships [S1]; Brainspotting 2025: junior average pay fell to ~967 EUR/month net (from 1,409 in 2024), 55% of IT professionals took part in no recruitment process in 2024, only 8% work via PFA/SRL [S62]; an HR consultant told Ziare.com in April 2026 that IT "nu mai angajează entry-level" and that first-job salaries are 3,500–5,000 RON net [S60]; a training-provider founder said in February 2026 that companies "continuă să angajeze juniori, însă într-un ritm mai lent", prioritising practical delivery, and that manual QA/support/HTML-only roles lose ground while AI, data, cloud and security gain [S61]; junior IT pay guidance for 2026: ~4,000–6,000 RON net for simple entry roles, 5,000–8,000 in mid-size or demanding companies [S63]. Early-career AI roles do exist at Accenture Bucharest (posted 2026-09-15) [S29]; Hipo listed 114 "Junior IT" jobs at the time of search (UNVERIFIED snapshot).
   For the owner: (i) the 68-repo portfolio and unpublished research are the way around the "no juniors" filter because employers say they now buy demonstrated delivery, not potential; (ii) anchor salary expectations at 5,000–8,000 RON net for a first AI/software role in Bucharest and do not quote the IT average (8,000) as a floor; (iii) the Hipo October fair and the Accenture/Deloitte/IBM early-career tracks are the realistic mass-entry doors, while UiPath/Adobe/Bitdefender/Druid are the targeted, referral-assisted doors.

H2. **INFERRED. Gap-closing work that takes weeks to months and is rewarded by this market.** Applied AI (34% of employers' top want [S3]) with cloud deployment (Azure/AWS in the top-3 skills [S1]); at least one peer-reviewed or preprint publication so ORCID is not empty (needed for the MSc/PhD track and a differentiator against other juniors); a Romanian-language CV and eJobs profile of equal quality to the English one; a UB English-competence certificate for the FMI English masters [S49].

---

## I. Contested, or widely repeated but unevidenced

I1. **How many IT employees Romania has.** ANIS 195,929 (2024) [S13]; Termene 170,201 (2023, CAEN 58.29/62/63 employers) [S15]; Stochiță 145,800 peak in 2023 [S7]; whitepaper 200,629 (2022) → 146,000 (2024) [S8]; "207,800 ICT specialists" and "250,000 tech specialists" in vendor guides [S67][S71]. The definitions differ (ICT occupation vs IT-sector employer vs tax-exemption headcount); do not cite any single number without its definition.

I2. **Whether the sector is shrinking or growing in 2026.** Experis Q3 2026 −11% hiring intention [S3] and layoff reports [S8][S21][S22] vs getuhired's weekly posting volume "moved from 738 to 743… indicating growing demand" [S1], ZF's +8.2% turnover [S12] and eJobs's record applications [S5]. Both are true of different things (intentions and headcount vs postings and revenue).

I3. **Amazon Iași: were IT jobs cut?** Whitepaper counts the 500 as developer jobs "relocated to India" [S8]; Ziarul de Iași reports the cut was in Retail Business Services with "niciun specialist IT vizat" [S22].

I4. **Photo on the CV** (G4): platform and national-Europass guidance say include; multinational norms and several Romanian guides say omit; the recruiter-preference percentages circulating online are untraceable.

I5. **CV language at multinationals** (E3): "recruit in Romanian and translate internally" [S48 Georgescu] vs English-only portals and the eJobs "Completează CV-ul în engleză" flag [S40][B4].

I6. **"IT no longer hires entry-level"** [S60] vs 18% of postings entry-level [S1], "slower pace" [S61] and early-career AI postings [S29]. The strong form is an overstatement.

I7. **2025 startup funding total.** How to Web: EUR 103M over 40 deals, −20% [S24]; The Recursive's list is led by Dexory's USD 165M Series C (UK-headquartered, Romanian founders), which alone exceeds the How to Web total [S24]. Definitional (where the company is domiciled).

I8. **Cluj as "the densest AI community".** Asserted by recruitment marketing [S67] and consistent with ZF's "only pole growing in headcount" [S12], but no AI-specific headcount by city exists.

I9. **ATS adoption rate in Romania** (D1): no survey; every rate quoted online is global.

I10. **Europass "not accepted" in Romania.** Repeated by CV-builder sites; the evidence is that it is disliked by private recruiters and required by some public/academic dossiers, i.e. segment-specific, not "not accepted".

---

## J. What this means for the owner — prioritised actions

1. **Build the master as an English, ATS-safe, single-column PDF with no photo, no DOB, no nationality/marital status/CNP, city-only address, CEFR language lines, conventional section headings, Projects and Publications sections.** This single artifact is what Workday (Accenture, Adobe), Greenhouse (Bitdefender), SmartRecruiters (Endava, Deloitte, Bosch, Ubisoft), Ashby (UiPath), proprietary portals (Microsoft, Amazon, Google, Oracle, EPAM, Luxoft), LinkedIn Easy Apply (Word/PDF <2 MB) and BestJobs (.pdf/.doc ≤10 MB) all accept. [B4, C3, C5, F1, G]
2. **Derive a Romanian variant of identical content** (not a translation of phrasing) for Romanian-language ads, public/state employers, in-house IT at non-tech companies, and academic dossiers; keep a Europass export ready for any dossier that asks for it. [E2, F2]
3. **Fill the eJobs profile in both Romanian and English to equal completeness** (the employer receives both), set it public, attach the English PDF, and re-apply within 1–2 weeks of posting; expect ~89 applicants per IT ad. [C2, A1]
4. **Create the Hipo profile now and attend Angajatori de TOP București on 30–31 October 2026 (Sala Palatului) with the CV-Barcode**; this is the mass-entry channel to Accenture/Deloitte/IBM/Microsoft/Oracle early-career pipelines. [C4]
5. **Target list, tier 1 (AI/agent-adjacent, Bucharest, own portals):** UiPath (Ashby), Adobe Firefly/agentic teams (Workday), Bitdefender ML platform (Greenhouse), Druid AI, Accenture Early Careers AI/ML, Thales AI/ML, Siemens Energy applied-AI, Amazon Bucharest (Alexa/AWS), Google Bucharest, Microsoft RDC. **Tier 2 (volume, English, Bucharest):** Luxoft, NTT DATA, Endava, EPAM, GlobalLogic, Capgemini, ALTEN, HCLTech, Inetum, ING Hubs, Deutsche Bank Technology Centre, LSEG, Worldline, Marsh, eMAG. **Tier 3:** newly announced captives (Equans, Müller, Zalando, Engie, Kärcher) and employee-rated mid-size product firms (Zitec, msg systems, EveryMatrix, Infineon, SAP Romania). [B2, B3, B5, B6]
6. **Script alerts** on the public Ashby and Greenhouse APIs (UiPath, Bitdefender) and on LinkedIn/eJobs saved searches for "Bucharest" + "machine learning|applied scientist|agent|LLM"; these boards expose JSON without scraping. [B4]
7. **Salary posture:** first AI/software role 5,000–8,000 RON net in Bucharest; IT average is 8,000 net; candidates asking +50% over offers are the norm and lose; salary is asked at the screening call. [A2, C6, H1]
8. **Personal-data hygiene:** never supply CNP/ID before an offer; expect 6-month retention at multinationals; a photo is optional everywhere and absent from every verified multinational portal; age is hidden by eJobs; age/gender criteria in ads are illegal (OG 137/2000, CNCD). [G1–G4]
9. **Academic track:** obtain the UB English-competence certificate (or document two passed English semesters) before the next FMI master cycle; for the Informatics Doctoral School (3 scholarship places in 2026), line up a supervisor and at least one publication so the CV's Publications section and ORCID are not empty. [E4, H2]
10. **Signals to re-check quarterly:** Experis Tech Talent Outlook (next: Q4 2026), eJobs Review & Trends 2027 (January), BestJobs half-year report (June/December), ANIS Sentiment Survey (October), ZF's IT balance-sheet map (August), and the "new hub" announcements in ZF/Romania Insider/undelucram. [A, B5]

---

## Appendix 1 — eJobs live-ad language sample (2026-09-23)

Method: first 40 listing IDs on https://www.ejobs.ro/locuri-de-munca/it-software (alphabetical slug order, so not a random sample), descriptions pulled from `api.ejobs.ro/jobs/{id}` (`details` field), classified by counts of Romanian vs English function words. Result: 24 EN / 16 RO; excluding six eJobs Group course ads and seven near-empty descriptions, 20 of 27 substantive ads (74%) were English. External-apply redirects: 8/40. Full rows in `ejobs_it_language_sample.json` (same folder). Limitation: one page, one category, one day; treat as indicative, corroborated by [S46][S48].

## Appendix 2 — ATS probe protocol

For each employer: (1) fetch careers page HTML and grep for vendor hostnames; (2) probe vendor-hosted board URLs; (3) because SmartRecruiters, Recruitee and Ashby web pages return HTTP 200 for nonexistent slugs (control: `XyzNonexistentCo9981`), confirm through vendor APIs that 404 or return zero postings for unknown companies: `api.smartrecruiters.com/v1/companies/{slug}/postings`, `{slug}.recruitee.com/api/offers/`, `api.ashbyhq.com/posting-api/job-board/{slug}`, `boards-api.greenhouse.io/v1/boards/{token}/jobs`. Only API-confirmed or fingerprint-confirmed attributions are reported as VERIFIED in B4.
