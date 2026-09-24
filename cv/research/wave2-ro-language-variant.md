# Wave 2 — The Romanian-language document question

Owner: Andrei Mihai Visalon (University of Bucharest, FMI, BSc CS 2022–2025; GitHub Prekzursil; ORCID 0009-0001-8776-8498).
Question: does he need a Romanian-language CV at all for the Romanian market, when is each language used, Romanian terminology, diacritics/name policy, Europass status in 2026, and the language/format of Romanian MSc/PhD dossiers (University of Bucharest specifically).
Date of research: 2026-09-23. Method: WebSearch, WebFetch, Tavily, Exa (search-hub MCP was down; claude.ai Tavily/Exa worked), plus local text extraction (pypdf) of 12 primary PDFs and visual reading of a scanned regulation. Extracted texts are saved next to this file as `pdftext_*.txt`.

Legend: **VERIFIED** = read in a primary or two independent sources. **INFERRED** = my reasoning on top of verified facts. **UNVERIFIED** = fewer than two independent sources, or a claim I could not check.

---

## 0. Bottom line for this owner

1. **He does not need a Romanian CV for the private-sector software/AI job hunt.** Every practitioner source (10+, 2023–2026) converges on one rule: write the CV in the language of the job ad; Romanian IT and multinational ads are overwhelmingly in English, and an English CV is never wrong for IT. Romanian is expected only by small local firms, the public sector, and traditional industries. (VERIFIED as practitioner consensus; no quantitative survey exists, see §10.)
2. **He does need Romanian-language documents for three specific contexts, and none of them is "a translated resume":**
   - **Public-sector and university employment competitions** legally require a *Europass-model* CV ("curriculum vitae, model comun european") — HG 1336/2022 art. 35(1)(i), HG 611/2008 art. 49(1)(b), and university hiring methodologies (UB 2025, UBB 2025). This is the only place in Romania where Europass is still genuinely mandatory. (VERIFIED, primary texts.)
   - **UB doctoral admission (incl. the FMI Computer Science Doctoral School)** requires **no CV at all**. The dossier is a fixed Romanian-language set: *memoriu de activitate științifică*, *lista lucrărilor publicate*, a research-topic proposal with bibliography, a 10-topic exam list, a **B2 language certificate for every candidate**, plus identity/diploma copies. (VERIFIED, UB regulation 2025+2026 art. 14 and FMI SDI 2026 regulation art. 10 — read page by page.)
   - **UB / FMI master's admission** requires **no CV either**: a signed *lista performanțelor extracurriculare* with proofs, a two-page summary of the bachelor thesis, diplomas, and — only for English-taught programs — a B2 English certificate (baccalaureate certificates are not accepted). (VERIFIED, UB regulation 2026 art. 6 and FMI methodology 2025 §VI.1.)
3. **Research grants (UEFISCDI PN-IV) are in English**, with their own 4-page "CV and track record" template (not Europass). (VERIFIED.)
4. **Name policy:** his surname and given names carry no diacritics in any profile he controls (GitHub, ORCID, email, LinkedIn slug). The only open question is what the identity card prints (whether "VISALON" or "VIȘALON", and whether "ANDREI-MIHAI" is hyphenated). He must read his CI once and record the legal form; the CV system then uses the legal form only on documents that must match identity documents, ASCII everywhere else. **His ORCID currently reads "Andrei Visalon" (no "Mihai")** — inconsistent with GitHub/LinkedIn and fixable today. (VERIFIED via ORCID public API.)
5. **System design consequence:** keep the master in English; add a *Romanian variant layer* (headings, contractual job titles, COR codes, correct comma-below diacritics) that can emit (a) a Europass-model RO CV for state/university competitions, (b) the UB doctoral *memoriu* + publication list, (c) the FMI master *listă de performanțe*, and (d) a 4-page English academic CV for UEFISCDI. See §9.

---

## 1. Private-sector employers: Romanian vs English CV in 2026

### 1.1 Evidence (practitioner and recruiter accounts)

| # | Source (date) | Type | What it says |
|---|---|---|---|
| 1 | Irina Filip, recruiter, LinkedIn post (2025-06-02) https://ro.linkedin.com/posts/irinacfilip_nu-%C8%99tii-%C3%AEn-ce-limb%C4%83-s%C4%83-trimi%C8%9Bi-cv-ul-activity-7335198550118518785-GC5a | recruiter | "Este de preferat să ai o variantă în limba română și una în limba engleză. În cazul în care aplici la o multinațională, bineînțeles, varianta în engleză este de preferat." For smaller/Romanian firms: if the ad asks for advanced English or the role involves frequent English, send English. "Alegerea limbii în care îți trimiți CV-ul spune ceva despre tine." |
| 2 | Andreea Nicolae, recruiter, LinkedIn post (2025-01-15) https://ro.linkedin.com/posts/andreea-georgiana-nicolae_trimit-cv-ul-in-romana-sau-in-engleza-in-activity-7285185188634976256-4Wvq | recruiter (dissenting) | "In cazul in care anuntul nu specifica distinct ca CV-ul trebuie trimis intr-o alta limba, trimite-l linistit in romana … Chiar si atunci cand in anunt scrie ca trebuie sa stii engleza." Comments under the post push back: "dacă anunțul este în engleza, este de la sine înțeles ca și CV-ul trebuie sa fie în engleza." |
| 3 | r/programare thread "CV în română sau engleză" https://www.reddit.com/r/programare/comments/zzu57m/cv_in_romana_sau_engleza | developers | "Depinde cum e scris anunțul de angajare. Dacă e în română, trimiți CV-ul în română, deși cred că cu cel în engleză n-ai cum să dai greș." |
| 4 | Job'Or / verandamall model CV 2025 https://verandamall.ro/jobs/resurse/model-cv/ | job-board guide | "Scrie CV-ul în limba în care a fost redactat anunțul de job. … dacă CV-ul va fi în limba română, evită să folosești termeni în engleză pentru care avem echivalent în DEX – pe scurt, folosește o singură limbă. Cât despre diacritice, nu există o regulă…" |
| 5 | Lexis (2025-07-25) https://www.lexis.ro/cv-in-engleza | language school | "Chiar și în România, multe companii multinaționale, start-up-uri tech sau organizații din domenii precum IT, financiar, marketing sau consultanță preferă CV-uri redactate în limba engleză." |
| 6 | ResumeFlex "Professional CV Guide for Romania" (2025-04-30) https://resumeflex.com/how-to-write-a-professional-cv-for-romania-job-market/ | resume-service (marketing) | "Opt for English in multinationals … or IT roles where teams collaborate globally. Use Romanian for local companies, public sector roles, or traditional industries." |
| 7 | Jobera Romania CV guide (2023-04-17) https://jobera.com/resources/romania-cv-writing-guide/ | aggregator | Romanian or English both accepted; be consistent within one document. |
| 8 | Resumly Romania page (undated, 2025–26 content) https://www.resumly.ai/ai-resume-builder-romania | resume-service | "Match the language of the job ad … public-sector [ads are in] Romanian, while IT, B[PO] and multinational positions are frequently advertised and conducted in English … prepare a Romanian and an English version." |
| 9 | taurusid (2026-09-14) https://taurusid.com/articles/how-to-write-a-cv-for-jobs-in-romania-format-photo-rules-employer-expectations | resume-service | Modern 1–2 page CV is the norm in tech/multinationals; Europass only when requested. |
| 10 | avocatnet.ro (2026-05-26) https://www.avocatnet.ro/articol_71956/... | legal press | Confirms the practice: publishing job ads "exclusiv în limbi străine" has become "aproape o normă, în special în corporații și în sectorul IT" (and argues Law 500/2004 requires a Romanian translation of such ads). |
| 11 | Lina Nareikienė, recruiter, LinkedIn (2026-08-10) https://www.linkedin.com/posts/lina-nareikiene_possibly-an-unpopular-recruitment-opinion-activity-7492489758103797760-vf84 | recruiter (Lithuania, international hiring) | "if the job ad is in English, sending your CV in your native language is… a strange choice" — same rule from outside Romania. |
| 12 | centruldebusiness.ro (2026-08-30) https://centruldebusiness.ro/cum-adaptezi-cv-ul-pentru-fiecare-domeniu-it-vs-hr-vs-vanzari/ | HR blog | Recommends a private "master" document and per-domain variants; for IT: specify stack in the title ("Backend Developer (Java, Spring)"), GitHub link near the top. |

**VERIFIED (12 sources, consensus):** the language of the CV follows the language of the ad; English is the safe default for IT/multinationals; Romanian for local SMEs/public sector. **UNVERIFIED:** no quantitative data on the share of Romanian IT ads posted in English was found (eJobs/BestJobs publish no such statistic; a taurusid claim of "over 60% of private-sector recruiters prefer a concise CV over Europass, according to eJobs" is unsourced).

**What it means for the owner:** the English master CV is the primary job-hunt artifact. A Romanian variant is a secondary output generated per application when (a) the ad is in Romanian, (b) the employer is a Romanian SME or state entity, or (c) a Romanian document is explicitly requested. Never mix languages inside one document; do not translate technical stack names.

### 1.2 Bilingual / dual-version practice

Recommended by Filip (2025), Resumly, taurusid, FreeCV (2026), cvhub.ro (2026-07: "Poți păstra un profil principal cu toate informațiile și genera versiuni diferite pentru procese diferite"), and the eJobs/Hipo ecosystem (eJobs profiles exist in RO and EN). Two *separate* single-language files, not one bilingual file. **VERIFIED (≥6 sources).**

**For the owner:** generate `CV_EN_Visalon_Andrei-Mihai.pdf` and `CV_RO_…pdf` from the same structured source; file naming with role/domain suffix is common Romanian practice (centruldebusiness.ro).

### 1.3 Legal backdrop (why Romanian paperwork exists even in English-speaking teams)

- **Law 500/2004** art. 1(2): "Orice text scris sau vorbit în limba străină, indiferent de dimensiuni, având caracter de interes public, trebuie să fie însoţit de traducerea sau adaptarea în limba română." (lege-online.ro snippet + avocatnet 2026). avocatnet argues a public job ad is such a text; that interpretation is a single legal-press source → **UNVERIFIED as applied to job ads**. It does not touch the CV.
- **Codul muncii art. 16(1):** the individual employment contract is concluded "în formă scrisă, în limba română" (codulmuncii.eu; lege5). **Art. 17(3) d):** the contract must state "funcţia/ocupaţia conform specificaţiei Clasificării ocupaţiilor din România" (COR). **VERIFIED (2 sources).**

**For the owner (work-history extraction):** every Romanian employment he had produced Romanian-language documents — the CIM, *adeverințe de vechime*, REVISAL extract (obtainable from ITM), fișa postului — each carrying a **COR title** that may differ from the English title used at work (e.g., contract says "Programator (251202)" while the team called him "Backend Engineer"). Freelance work produced *contracte de prestări servicii* or PFA invoices. These are the primary evidence for the undocumented history; the master document should store both the contractual Romanian title and the market English title per role.

---

## 2. Europass in Romania, 2026: where it is genuinely mandatory

### 2.1 Public sector — mandatory by regulation (VERIFIED, primary texts)

- **HG 1336/2022** (framework regulation for contractual staff in the budgetary sector), **art. 35(1):** "Pentru înscrierea la concurs candidaţii vor prezenta un dosar care va conţine următoarele documente: a) formular de înscriere la concurs … i) curriculum vitae, model comun european." (text extracted from the official PDF, https://www.rauflorin.ro/legislatie/new/2022/HG_1336.2022.pdf; also https://legislatie.just.ro/public/DetaliiDocument/261250).
- **HG 611/2008** (civil-servant career norms), **art. 49(1)** as amended by **HG 761/2017:** "a) formularul de înscriere prevăzut în anexa nr. 3; b) curriculum vitae, modelul comun european; c) copia actului de identitate…" (https://www.universuljuridic.ro/hg-611-2008-…-modificari-hg-761-2017/3/). Note: lege5/legeaz free pages show only the 2008 original without item b).
- **Practice 2025:** a February 2025 contractual-post announcement lists "curriculum vitae, model comun european" (https://liceul-vidra.ro/2025/02/anunt-concurs-pentru-post-contractual-conform-h-g-1336-2022/); MAI recruitment hub announcements do the same (https://hub.mai.gov.ro/recrutarecandidat/anunt/view?id=6439).
- **ANOFM** (public employment agency) still points to "Curriculum vitae, întocmit conform modelului comun aprobat prin Hotărârea Guvernului nr. 1021/2004 pentru aprobarea modelului comun european de curriculum vitae" (https://www.anofm.ro/cv-europass).
- Romania's National Europass Centre frames the CV as the "format comun la nivel european, în situația scoaterii la concurs a unor posturi" (https://mobility.europass-ro.ro/eu_si_europass/documente_utile/).
- ANFP national competition for civil servants (2025–2026): the candidate guide PDF is image-only; the document list could not be extracted → whether the *national* stage asks for a CV is **UNVERIFIED** (the position-level competitions under HG 611/2008 do).

**For the owner:** any application to a ministry, agency, state research institute, public hospital IT department, or a university's administrative/contractual post requires a Europass-model CV in Romanian. "Model comun european" is a legal term; use the official editor output (europass.europa.eu, RO interface) or a faithful reproduction of its section structure, not a "Europass-inspired" modern layout.

### 2.2 Academic hiring — Europass mandated by university methodologies (VERIFIED, 2 primary texts)

- **University of Bucharest**, Metodologia pentru ocuparea prin concurs a posturilor didactice vacante (FAA, 2025), art. 8(1): "c) curriculum vitae al candidatului (model Europass); d) lista de lucrări ale candidatului…"; art. 9 prescribes CV contents (studies and diplomas; professional/teaching experience; projects led as director with funding source and amount; awards; other relevant elements). Item g): "rezumatul, în limba română și într-o limbă de circulaţie internaţională, al tezei de doctorat … pe cel mult o pagină pentru fiecare limbă." (https://unibuc.ro/wp-content/uploads/2025/04/Metodologie-concursuri-didactice-FAA-2025.pdf)
- **UBB Cluj**, methodology 10.03.2025: "3. Curriculum vitae al candidatului – model Europass (în original, asumat prin semnătură). Curriculum vitae al candidatului în format electronic, de tip PDF, fără semnătură, care la rubrica "Date personale" să cuprindă doar numele, prenumele candidatului și, opțional, adresa de e-mail." — the electronic copy is published online, hence the personal-data stripping. (https://www.ubbcluj.ro/ro/infoubb/posturi_vacante/files/legislatie/Metodologie_concurs_ocupare_posturi_didactice_cercetare_10_03_2025.pdf)

**For the owner:** if he ever competes for *asistent universitar* / research positions, a signed Romanian Europass CV plus a separate publication list is required; a second, anonymised PDF copy (name + optional email only) is published by the university.

### 2.3 Research grants — NOT Europass; English (VERIFIED, primary text)

UEFISCDI TE 2026 information package (PN-IV-RU-SC-TE-2026-2, https://uefiscdi.gov.ro/resource-832286-Pachet-informatii-TE-2026_aprobat.pdf):
- "Cererea de finanțare (conform Anexei 3) se scrie în limba engleză, cu excepţia proiectelor din domenii cu specific românesc (conform Anexei 1), unde se permite redactarea în limba română."
- "Anexa 3.1 - CV and track record template (max. 4 pages)"; "The document, including CV, is in A4 format, uses Times New Roman font, 11-point font size, 1.15 line spacing and 2 cm margins. Any modification to these parameters is forbidden."
- Template fields: "Name, Surname / Date of birth / Gender / Nationality / Researcher unique identifier(s) (ORCID, Researcher ID etc.)", education, positions, "Track record: A list of maximum ten most important scientific outputs", "Narrative CV: A narrative summarizing which work has had the greatest importance and impact."
- Submission via https://uefiscdi-direct.ro/ as text PDF. Same pattern for PD 2026 (postdoctoral) per UBB/GRANTPRESS announcements.

**For the owner:** a future academic CV variant must be an English 4-page document with ORCID, a 10-item track record and a narrative section — i.e., the master should already store a "narrative CV" paragraph and a ranked outputs list. Not applicable until he holds a PhD (TE/PD eligibility), but PhD-student calls and institutional calls reuse the same template family.

### 2.4 Private sector — Europass is a negative or neutral signal (VERIFIED as consensus, 9 sources)

cvhub.ro (2026-07-13): "CV-ul Europass este obligatoriu în România? Nu pentru toate candidaturile. Devine obligatoriu doar când angajatorul, instituția sau programul îl solicită explicit." · Ioana M., recruiter, LinkedIn (2026-04-23): "De ce CV-ul Europass sau template-urile standard (eJobs) NU mai funcționează în 2026" · taurusid (2026-09): "Use Europass only when explicitly requested" · cvmaker.ro: "În general, nu este larg acceptat în România" · resumelio (2025-07), interactive-cv (2026-09), romanianpost (2026-08), Resumly, FreeCV (2026-05: "standardul implicit … mai ales la instituțiile de stat, în administrație și la pozițiile entry-level").

**For the owner:** never send Europass to a software company. Keep it as a generated output for §2.1–2.2 only.

### 2.5 Doctoral admissions — NOT Europass, and at UB not even a CV (VERIFIED)

- **UB regulation 2025 and 2026, art. 14(1):** full list is a)–n): fişă de înscriere; act de identitate; certificat de naştere; certificat de căsătorie/schimbare de nume (dacă e cazul); diploma de bacalaureat; diploma de licenţă + foaie matricolă/supliment; diploma de masterat + supliment (sau adeverinţă pentru absolvenţii anului curent); **"h) memoriu de activitate ştiintifică; i) lista cu titlurile lucrărilor ştiinţifice publicate; j) propunerea unei teme (în scris) în concordanţă cu temele de cercetare aferente pozițiilor vacante … cu justificarea importanţei acesteia; k) o listă bibliografică cuprinzătoare pentru tema propusă…; l) certificat de competenţă lingvistică, copie nelegalizată (conform anexei…); m) declarație pe propria răspundere…; n) chitanţa…"** No "curriculum vitae"/"CV"/"Europass" anywhere in either year's text (grep confirmed). (https://doctorat.unibuc.ro/wp-content/uploads/2026/01/Regulamentul_admitere_Doctorat_UB_2026_Aprobat_Senat-2025-12-17_site.pdf and the 2025 file.)
- **Other universities:** UPB 2025–2026 doctoral methodology requires "b) Curriculum vitae. c) Lista de lucrări publicate." (no format); UAIC Law: "Curriculum Vitae semnat" (no format). So the often-repeated "PhD admission needs a Europass CV" is **not supported** at UB, UPB or UAIC. UMFCD could not be checked (list in a PDF not fetched).

---

## 3. Academic dossiers at the University of Bucharest — language and format

### 3.1 FMI Computer Science Doctoral School (Școala Doctorală de Informatică), regulation 2026–2027 (scanned PDF read page by page; VERIFIED)

- Art. 2(1): admission follows Law 199/2023, OME 3020/2024, OME 3693/2024, the UB doctoral admission regulation (Senate 22 Jan 2025) and this regulation.
- Art. 9(1): "Înscrierile la concursul de admitere se fac în sistem online, fie prin platformă online, fie prin trimiterea prin e-mail către secretariatul Ș.D.I." (platform: https://admitere.fmi.unibuc.ro/).
- Art. 10(1): a supervisor's agreement is mandatory, obtainable before (recommended) or after the colloquium; candidates without any supervisor's agreement "vor fi respinși, indiferent de rezultatul obținut". 10(2): "Candidatul va întocmi in mod obligatoriu … o listă cu 10 subiecte propuse pentru examinare."
- Art. 10(3), documents (a)–(n): identical to UB art. 14(1), with "(h) memoriu de activitate științifică (dacă există); (i) lista cu titlurile lucrărilor științifice publicate (dacă există); (j) propunerea unei teme de cercetare (în scris) … cu justificarea importanței acesteia, și lista bibliografică aferentă; (k) o listă cu 10 subiecte pentru examinare și bibliografia aferentă; (l) certificat de competență lingvistică, copie nelegalizată…". **No CV.**
- Art. 13(2): "Concursul de admitere la doctorat are loc în format fizic la Facultatea de Matematică și Informatică, în prezența conducătorului de doctorat vizat…"; 13(4): "constă dintr-o probă orală. Fiecare candidat va prezenta pe scurt tema de cercetare propusă și va fi examinat din lista de 10 subiecte"; 13(8) tie-breakers: licence GPA, CNATDCU-scored publications, baccalaureate GPA. Art. 14(1): minimum mark 7.
- Calendar 2026 (web page): înscrieri 1–12 July 2026, concurs 15 July 2026, results 31 July, enrolment 23–24 September. (https://fmi.unibuc.ro/anunturi-doctorat/anunturi-sdi/admitere-doctorat-2026-scoala-doctorala-de-informatica/)
- Language of the colloquium is not stated in the regulation (the document is entirely in Romanian). **UNVERIFIED** whether an English colloquium is possible; Law 199/2023 art. 64 allows doctorates "în limba română, într-o limbă a minorităţilor naţionale sau într-o limbă de circulaţie internaţională, conform contractului de studii doctorale" (lege5, VERIFIED), so the language is a matter of the doctoral contract with the supervisor.

**Language certificate (applies to every candidate, art. 14(1)(l)) — accepted types, UB annex (VERIFIED):** minimum B2; (1) certificate from FLLS–Departamentul de Limbi Moderne (UB); (2) certificates from Consorțiul Universitaria universities and Transilvania Brașov; (3) diplomas of foreign-language programs of UB, POLITEHNICA București and Universitaria universities; (4) international tests (TOEFL, DELF, Goethe, Cambridge…); (5) foreign cultural institutes (British Council, Institut Français, Cervantes…); (6) documents proving ≥6 months of study abroad; (7) bilingual-high-school baccalaureate with the international-language mention; (8) "Diplome şi certificate eliberate de alte universităţi şi organisme" — the last needs testing at UB's Centrul de Limbi Străine "Ariel".

**For the owner:** (i) the "academic CV" for a UB PhD is a **Romanian *memoriu de activitate științifică*** (narrative record: studies, research, publications, projects, software) plus a **publication list**; build these as first-class outputs of the system, in Romanian, no Europass; (ii) the real gate is a supervisor's agreement and the topic proposal — the CV system should feed a one-page Romanian research-profile summary for supervisor outreach; (iii) **gap with lead time:** obtain a B2+ English certificate accepted by UB (Cambridge/IELTS/TOEFL or the UB FLLS certificate) or check whether his FMI bachelor's diploma supplement qualifies under item (3)/(8) — otherwise a test at CLS "Ariel"; (iv) his three in-flight manuscripts only count in "lista lucrărilor" once published/accepted — the memoriu can still describe them as work in progress.

### 3.2 UB and FMI master's admission (VERIFIED)

- **UB Regulament admitere MASTERAT 2026 (Senate 21.01.2026), art. 6(1):** documents a)–n): fişă-tip de înscriere; diplomă de licenţă/adeverinţă; 3 fotografii tip C.I.; diplomă de bacalaureat; certificat de naştere; adeverinţă medicală-tip; C.I./paşaport; dovada taxei; minority recommendation (if applicable); social-protection/disability proofs (if applicable); recognition of foreign studies (if applicable); fee-exemption proofs; written consent to recording for online exams. **No CV.** (https://admitere.unibuc.ro/wp-content/uploads/2026/01/Regulament-admitere-MASTERAT_2026.pdf)
- **Same regulation, art. 4(3):** "Pentru studiile universitare de masterat organizate într-o limbă străină, admiterea are loc în limba de predare a programului de studii universitare. Facultățile pot stabili în metodologia proprie modul în care candidatul poate dovedi competențele lingvistice." → for FMI's English-taught programs the admission (oral exam) is held in English. 4(4)–(5): Romanian-language proof is required only from foreign citizens; Romanian citizens who studied in another language prove Romanian with the baccalaureate/licence diploma.
- **FMI Metodologia admitere master 2025 (51 pp., Google Drive link from the FMI page), §VI.1 "Actele necesare la înscriere":** a) fişă-tip (generated by the app); b) diploma/adeverinţa de licenţă with GPA and licence-exam mark; c) diploma de bacalaureat; **d) "Un rezumat de două pagini al lucrării de licență – semnat de candidat"; e) "Lista cu performanțele extracurriculare ale candidatului, prevăzute în criteriile de evaluare la proba de dosar – semnată de candidat"; f) diplomas/certificates proving those performances;** g) certificat de naștere; h) adeverință medicală; i) C.I.; j) fee proof; **k) "Numai candidații care se înscriu la un program în limba engleză: certificat de competență lingvistică pentru limba engleză (minim B2) … (certificatele de competențe lingvistice obținute la bacalaureat NU sunt acceptate…)"**; l) consent to oral-exam recording. **No CV.**
- **§IX.1 scoring of the dossier:** licence GPA (without the licence-exam mark) + 0.25 points per extracurricular professional achievement in Mathematics/Informatics/CTI, max 3 per criterion, capped at 10. Criteria: student competitions; communications at scientific sessions/conferences; **published scientific articles**; problems selected for school competitions; research internships; internships abroad; performance/excellence scholarships; professional distinctions; other student performances. "Nu vor fi luate în considerare decât acele activități pentru care candidații prezintă dovezi la înscriere."
- **Weights (UB "Modalități de admitere 2025", FMI rows):** all FMI programs "40% proba de dosar + 60% proba orală". §VIII.2: oral exam online (Google Meet/MS Teams), recorded; candidates whose bachelor thesis is outside Mathematics/Informatics are examined from a 4-subject list.
- **Programs and language (FMI 2025):** Informatică IF — Baze de date şi tehnologii software, Inginerie software, Sisteme distribuite (Romanian); **Artificial Intelligence, Data Science, Natural Language Processing, Security and Applied Logic (English)**; Matematică — Advanced Studies in Mathematics (English), Matematică didactică, Probabilități și statistică în finanțe și științe (Romanian).
- The FMI page also lists an exemption from the B2 certificate for graduates of English-taught bachelor/master programs or those who passed at least two semesters of English courses during the bachelor's (web page wording; not found in the PDF text → **UNVERIFIED wording**, check the current page).

**For the owner:** for an FMI MSc the CV is irrelevant; what scores is (a) licence GPA and (b) a **signed Romanian list of extracurricular achievements with proofs** — the CV system should emit exactly that list (competitions, conference talks, published articles, research internships, scholarships) as a Romanian document with an attachments index. The English-taught AI/Data Science/NLP tracks need a B2 certificate (not the baccalaureate one) unless the exemption applies — check his diploma supplement for two semesters of "Limba engleză" now, because certificates take weeks. Admission for English-taught programs is conducted in English (UB art. 4(3)).

### 3.3 Language of Romanian academic dossiers, generally

- Forms and platforms (admitere.unibuc.ro, admitere.fmi.unibuc.ro, uefiscdi-direct.ro) are Romanian-language systems; UB doctoral art. 16 / FMI SDI art. 12 require legalised translations only for non-EU recognition attestations. Domestic candidates submit Romanian documents; the memoriu/proposal are written in Romanian by default. **INFERRED** for the memoriu language (the regulation does not state it; the dossier and colloquium are Romanian-language by context).
- Thesis language: Law 199/2023 art. 64 (VERIFIED) allows an international language per the doctoral contract; secondary sources say theses are "de regulă în limba română" with exceptions (cotutelă, research abroad) — article number **UNVERIFIED**.

---

## 4. Romanian terminology

### 4.1 Section headings

**Official Europass RO template labels (2013–2017 template, "Instrucţiuni pentru completarea CV-ului Europass", https://www.dataprotection.ro/servlet/ViewDocument?id=2132; VERIFIED from extracted text):**
INFORMAŢII PERSONALE · LOCUL DE MUNCĂ PENTRU CARE SE CANDIDEAZĂ / LOCUL DE MUNCĂ / POZIŢIA / STUDIILE PENTRU CARE SE CANDIDEAZĂ · EXPERIENŢA PROFESIONALĂ · EDUCAŢIE ŞI FORMARE · COMPETENŢE PERSONALE (Limba(i) maternă(e); Alte limbi străine cunoscute with CEFR grid Înţelegere / Vorbire / Scriere; Competenţe de comunicare; Competenţe organizaţionale/manageriale; Competenţe dobândite la locul de muncă; Competenţă digitală; Alte competenţe; Permis de conducere) · INFORMAŢII SUPLIMENTARE (Publicaţii, Prezentări, Proiecte, Conferinţe, Seminarii, Distincţii, Afilieri, Referinţe) · ANEXE.
**Glyph warning (measured):** that official PDF is typeset with **cedilla** glyphs — 390 occurrences of ş/Ş/ţ/Ţ vs 25 comma-below ș/ț. Copy-pasting its headings propagates the wrong characters (see §5.1). Type the headings yourself with comma-below: *Informații personale, Experiența profesională, Educație și formare, Competențe personale, Competențe digitale, Informații suplimentare, Publicații, Prezentări, Proiecte, Conferințe, Distincții, Afilieri, Referințe, Anexe*.

**Modern (non-Europass) Romanian headings recommended by ATS-oriented Romanian guides (hipo.ro, 8ore.ro, undelucram.ro; VERIFIED, 3 sources):** Date de contact · Profil profesional (or Profilul candidatului / Rezumat / Despre mine) · Experiență profesională · Educație (Studii) · Competențe (Competențe tehnice / Abilități) · Limbi străine (with CEFR level, e.g. "Limba engleză – nivel C1") · Certificări · Proiecte · Publicații · Premii și distincții · Voluntariat · Cunoștințe IT (older Hipo wording). 8ore.ro: "Folosește titluri standard pentru secțiuni … Profil profesional; Experiență profesională; Educație; Competențe; Limbi străine; Certificări" and avoid creative labels ("Povestea mea").

Other useful RO terms: *scrisoare de intenție* (cover letter), *adeverință de vechime* (employment certificate), *fișa postului* (job description), *stagiu de practică* (internship), *practică de vară*, *colaborator / freelancer / PFA (persoană fizică autorizată)*, *contract de prestări servicii*, *drepturi de autor* (copyright-based contract), *lucrare de licență* (bachelor thesis), *foaie matricolă / supliment la diplomă* (transcript), *media generală*, *memoriu de activitate științifică*, *lista lucrărilor*, *conducător de doctorat*, *școală doctorală*.

### 4.2 Technical job titles — COR (Clasificarea Ocupațiilor din România) group 2512 "Proiectanți de software" (VERIFIED, rubinian.com COR 2026; corroborated by codcor.ro, legislatiamuncii.manager.ro)

251201 Analist · 251202 Programator · 251203 Inginer de sistem în informatică · 251204 Programator de sistem informatic · 251205 Inginer de sistem software · 251206 Manager proiect informatic · 251207 Inginer de dezvoltare a produselor software · 251208 Inginer în realizarea, întreținerea și dezvoltarea aplicațiilor web · 251209 Inginer în domeniul tehnologiilor cloud · 251210 Dezvoltator în domeniul tehnologiei blockchain · 251211 Dezvoltator interfață cu utilizatorul · 251212 Inginer de date complexe (big data).
(Related: 2511 Analiști de sistem; 2513 Web and multimedia developers; 2519 other software specialists; 2521 Proiectanți de baze de date — codes not pulled.) Whether COR 2025–2026 contains an AI/ML-specific occupation is **UNVERIFIED** (not checked).

Market usage: Romanian tech CVs and ads use English titles ("Software Engineer", "Machine Learning Engineer", "Backend Developer (Java, Spring)") even in Romanian-language documents; Romanian guides advise specifying the stack in the title (centruldebusiness.ro 2026; developmentfactory.ro "Programator vs inginer software vs dezvoltator software"). Natural Romanian renderings when a Romanian title is wanted: *inginer software*, *dezvoltator software*, *programator*, *inginer de învățare automată* (rare; "ML Engineer" is used as-is), *cercetător / asistent de cercetare în informatică*, *inginer de date*, *arhitect software*.

**For the owner:** in the Romanian variant, render each role as "English market title (Romanian COR title, cod COR)" only where the document is for a state/university reader; for Romanian SMEs use the English title with a short Romanian gloss; for the master record, capture the COR code from each contract because Romanian *adeverințe* and REVISAL extracts will state it.

---

## 5. Name, diacritics and identity consistency

### 5.1 Orthography (VERIFIED: secarica.ro; Romanian Academy 2003; standards SR 13411:1999, ISO/IEC 8859-16)

Correct Romanian uses **comma below**: Ș U+0218 / ș U+0219, Ț U+021A / ț U+021B. The cedilla forms Ş U+015E / ş U+015F / Ţ U+0162 / ţ U+0163 are a legacy of ISO 8859-2 / Windows CP1250; the Academy stated in 2003 that "reprezentarea grafică a caracterelor Ș/ș și Ț/ț se face prin adăugarea virgulei sub caracterele S/s și T/t". Practical rule: UTF-8, comma-below code points, and a font that has the glyphs (Noto Sans, Arial/Calibri modern versions). ATS guides: modern parsers accept diacritics when the PDF uses standard fonts (8ore.ro; nobsresume; Job'Or: "nu există o regulă"). **VERIFIED (4 sources) — "likely" for ATS behaviour.**

### 5.2 What Romanian identity documents print

- Visual zone of the CI: "La partea de date personale se folosesc diacritice" (ro.wikipedia, single source → **UNVERIFIED for the current card model**; ICAO 9303 confirms only that the VIZ *may* carry diacritics).
- MRZ: "Aici nu se folosesc diacritice pentru a nu crea probleme la recunoașterea automată" (Wikipedia) and ICAO Doc 9303 Part 3: "Diacritical marks are not permitted in the MRZ … transliterate national characters using only the allowed OCR-B characters" → names appear as VISALON<<ANDREI<MIHAI in the MRZ regardless. **VERIFIED (2 sources).**
- CEI (electronic ID, national roll-out 20 March 2025 → all counties by 12 June 2025; free until 30 June 2026): printed data "nume, prenume, cetățenie, data nașterii, sex, imaginea facială, CNP, semnătura olografă" (MAI communiqué 13.03.2025). Diacritics handling not stated. Mismatches between birth certificate and CI spellings do occur and cause trouble at renewal (avocatnet forum thread "Certificat naștere și buletin cu diacritice diferite").

### 5.3 Compound given names and the hyphen

HG 64/2011 methodology (civil status), art. 24: "dacă numele de familie ori prenumele este compus din două sau mai multe cuvinte, acestea se scriu fără a se despărţi prin cratimă" (lege5; emaramures.ro reported it as a change: "nu se mai despart prin cratimă"). **VERIFIED.** The owner was born in 1993, before this rule; whether his birth record and CI print "ANDREI-MIHAI" (old hyphenated practice) or "ANDREI MIHAI" is **UNVERIFIED** — his UB email `andrei-mihai.visalon@s.unibuc.ro` and LinkedIn slug contain a hyphen, but email/URL conventions hyphenate anyway, so they are not evidence (**INFERRED**).

### 5.4 His current profile state (VERIFIED, ORCID public API on 2026-09-23)

ORCID 0009-0001-8776-8498: given-names "Andrei", family-name "Visalon", credit-name empty, "Also known as" empty, public email andrei-mihai.visalon@s.unibuc.ro, researcher URLs LinkedIn + GitHub, zero works. GitHub shows "Andrei Mihai Visalon" (owner-verified); LinkedIn slug andrei-mihai-visalon-03141b170. → ORCID drops "Mihai" and is the odd one out.

ORCID guidance (support.orcid.org "Add and edit your name"): the *Also known as* field is for "an abbreviated first name, variants including middle name(s), former or alternate name(s), or name(s) in a different character set"; for special characters ORCID recommends entering the name without them and notes search ignores diacritics. **VERIFIED.**

### 5.5 Decision rule for the owner (INFERRED from the verified facts above)

1. Read the CI visual zone once. Record the **legal form** in the master document: surname exactly as printed (VISALON or VIȘALON), given names exactly as printed (ANDREI-MIHAI vs ANDREI MIHAI).
2. **Legal-form documents** (Europass CV for state/university competitions, UB doctoral/master dossiers, notarised anything, grant applications): use the legal form, with correct comma-below glyphs if a diacritic exists.
3. **Everything web-facing and English** (GitHub, LinkedIn, ORCID published name, papers' bylines, English CV): ASCII "Andrei Mihai Visalon" (or "Andrei-Mihai Visalon" if the CI hyphenates — pick one and keep it identical across GitHub, LinkedIn, ORCID and the phenibut/FAERS/IberLEF bylines; the shared-task and journal bylines are the ones that will index forever).
4. **Fix ORCID now:** given names → "Andrei Mihai" (or "Andrei-Mihai"), add *Also known as* = "Andrei Mihai Visalon", "Andrei-Mihai Visalon", "A. M. Visalon", and the diacritic form only if the CI has one. Add "Mihai" before the first paper is submitted so the ORCID matches the byline.
5. Keep the ASCII surname on every English surface even if the CI has ș: ORCID/Crossref/GitHub search treat them as equivalent, and the MRZ, email and URL forms are ASCII anyway.

---

## 6. Photo, birth date and personal data in the Romanian variant (adjacent, for completeness)

Romanian sources disagree: ResumeFlex/taurusid/link-academy say a photo and date of birth are "standard" in Romanian CVs; hipo.ro says opinions are split and most recruiters consider the photo unnecessary; cvmaker.ro says Romanian employers "nu sunt obișnuiți cu fotografii în CV" (wrong for Europass practice); Resumly advises omitting CNP, ID number, marital status. Hipo's Europass article notes sex and nationality should be dropped "conform prevederilor legale actuale". **Contested** — see §10. The UBB rule (published CV copy with name + optional email only) shows the direction: minimise personal data on any copy that will be published.

---

## 7. What the private-sector Romanian variant should contain (INFERRED synthesis)

- Same content as the English master, one language throughout, technical terms and stack names untranslated, English job titles kept (optionally glossed).
- Romanian headings from §4.1 (modern set), CEFR levels for languages ("Engleză – C1", "Română – limba maternă", "Spaniolă – B?" if he claims it from the IberLEF work).
- 1–2 pages; PDF; comma-below diacritics; filename `CV_RO_<Nume>_<Prenume>.pdf`.
- No Europass layout, no photo unless the ad/company culture asks, no CNP/address.

---

## 8. Recommended system architecture for the three purposes

1. **Master (English, structured data):** per role store `title_en`, `title_ro_contract` (from CIM/adeverință), `cor_code`, employer, dates, evidence document; per output store `type` (paper/software/talk), status (in progress / submitted / accepted / published), and a Romanian title/summary.
2. **Renderers:**
   - `EN modern` (default job hunt).
   - `RO modern` (Romanian ads / SMEs).
   - `RO Europass` (state and university competitions) — generated through the official Europass editor or a faithful section-for-section reproduction; keep a signed-PDF and an anonymised-PDF variant (UBB pattern).
   - `RO memoriu de activitate științifică` + `RO lista lucrărilor` (UB doctoral admission).
   - `RO lista performanțelor extracurriculare` + attachments index (FMI master's).
   - `EN academic 4-page (UEFISCDI CV & track record)` with ORCID, 10-item track record, narrative CV.
3. **Identity block:** legal name form, ASCII display form, ORCID, GitHub, LinkedIn, institutional email; one source of truth so every renderer prints the same thing.
4. **Gap-closing items with lead time:** B2+ English certificate accepted by UB (§3.1) or proof of exemption; publication of the three manuscripts (needed for both the master dossier points and the doctoral *lista lucrărilor*); ORCID completion; Romanian employment evidence (adeverințe/REVISAL) to reconstruct the undocumented work history.

---

## 9. Claims index (label, sources, action)

| # | Claim | Label | Sources (n) | Owner action |
|---|---|---|---|---|
| 1 | Private IT/multinational employers expect the CV in the language of the ad; English is the safe default in IT | VERIFIED consensus | 12 | English master is primary; RO variant on demand |
| 2 | Two single-language versions (RO+EN) is normal; never mix languages | VERIFIED | 6 | Generate both from one source |
| 3 | Europass ("model comun european") CV is legally mandated for public-sector competitions (HG 1336/2022 art. 35(1)(i); HG 611/2008 art. 49(1)(b)) | VERIFIED primary | 6 | Keep a RO Europass renderer |
| 4 | University teaching/research competitions require a Europass-model CV (UB 2025, UBB 2025) | VERIFIED primary | 3 | Same renderer + signed and anonymised copies |
| 5 | UEFISCDI grant CV = English 4-page "CV and track record" template, not Europass | VERIFIED primary | 5 | Maintain EN academic variant with ORCID/narrative |
| 6 | Europass is unnecessary/negative in the private sector; use only when named | VERIFIED consensus | 9 | Never send it to software companies |
| 7 | UB doctoral admission requires no CV; requires memoriu, publication list, topic proposal, 10-topic list, B2 language certificate | VERIFIED primary | 4 | Build RO memoriu + list; get certificate |
| 8 | FMI SDI admission = oral colloquium in person at FMI, supervisor agreement mandatory; regulation and dossier in Romanian | VERIFIED primary | 2 | Supervisor outreach summary; RO proposal |
| 9 | UB/FMI master's admission requires no CV; signed extracurricular list + proofs; 40% dossier + 60% oral; B2 only for English-taught programs; admission in the language of instruction | VERIFIED primary | 4 | Emit the RO list with proofs; check B2/exemption |
| 10 | Doctorate may be conducted in an international language per the doctoral contract (Law 199/2023 art. 64) | VERIFIED | 2 | Language of the PhD is negotiable, dossier is not |
| 11 | Employment contracts are in Romanian with COR job titles; job ads in foreign languages need a Romanian version under Law 500/2004 (interpretation) | VERIFIED (contracts) / UNVERIFIED (ads interpretation) | 4 | Use CIM/adeverințe/REVISAL to reconstruct work history; store COR titles |
| 12 | Romanian headings: Europass official set vs modern ATS set; official Europass RO PDF uses cedilla glyphs | VERIFIED (glyph count measured) | 5 | Type headings with comma-below; two heading sets in the renderer |
| 13 | COR 2512 titles 251201–251212 as listed; market uses English titles | VERIFIED | 5 | Dual-title fields |
| 14 | Comma-below is the correct orthography; MRZ never carries diacritics; VIZ may | VERIFIED / partly UNVERIFIED | 5 | Use U+0219/U+021B; ASCII on web surfaces |
| 15 | Compound given names are written without hyphen since HG 64/2011; his 1993 record may be hyphenated | VERIFIED rule / UNVERIFIED for him | 3 | Read the CI; fix one display form |
| 16 | ORCID shows "Andrei Visalon" only; GitHub/LinkedIn carry "Andrei Mihai" | VERIFIED | 2 | Add "Mihai" + Also-known-as variants now |
| 17 | Modern ATS handle diacritics if fonts/PDF are standard; no Romanian rule requires or forbids them | likely | 4 | Keep diacritics in RO variant, test PDF text layer |

---

## 10. Contested or widely repeated but unevidenced

1. "Europass is the expected standard in Romania" (FreeCV 2026, older guides) vs "Europass is outdated/not accepted" (cvmaker, Ioana M. 2026, resumelio). Resolution: both are true in different sectors — mandatory in state/university competitions, counter-productive in private tech.
2. "Send the CV in Romanian even when the ad demands English" (Andreea Nicolae, 2025) vs "match the ad; English for IT" (Filip 2025, r/programare, Job'Or, Nareikienė 2026). Majority: match the ad.
3. "Over 60% of private-sector recruiters prefer a concise CV over Europass, according to eJobs data" (taurusid 2026) — no eJobs publication found; UNVERIFIED statistic.
4. "Romanian doctoral admissions require a Europass CV" (AI-generated search summaries) — refuted for UB (no CV), UPB and UAIC (plain CV, no format); other universities not checked.
5. Whether Law 500/2004 obliges employers to publish a Romanian version of job ads — avocatnet's interpretation, single source.
6. Whether the current CI/CEI prints diacritics in the visual zone — Wikipedia only; MAI's CEI communiqué does not say.
7. Photo and date of birth "standard" in Romanian CVs (ResumeFlex, taurusid, link-academy) vs "split/unnecessary" (hipo, cvmaker) — genuinely contested; Europass practice includes them, modern private-sector practice increasingly omits them.
8. Thesis "de regulă în limba română" — reported by search summaries of Law 199/2023; article not verified.
9. Language of the FMI doctoral colloquium and of the FMI master's B2-exemption wording — not stated in the regulations I read.
10. Whether COR 2025–2026 includes an AI/ML-specific occupation — not checked.

---

## 11. Sources (all accessed 2026-09-23)

Primary / regulatory
- HG 1336/2022 (PDF): https://www.rauflorin.ro/legislatie/new/2022/HG_1336.2022.pdf ; portal: https://legislatie.just.ro/public/DetaliiDocument/261250
- HG 611/2008 art. 49 as amended by HG 761/2017: https://www.universuljuridic.ro/hg-611-2008-pentru-aprobarea-normelor-privind-organizarea-si-dezvoltarea-carierei-functionarilor-publici-modificari-hg-761-2017/3/ ; base text: https://lege5.ro/gratuit/geytgnrrgy/art-49-dosarul-de-concurs-hotarare-611-2008?dp=gm3temztgyzti
- ANOFM CV Europass: https://www.anofm.ro/cv-europass
- 2025 announcement under HG 1336/2022: https://liceul-vidra.ro/2025/02/anunt-concurs-pentru-post-contractual-conform-h-g-1336-2022/
- UB teaching-position methodology 2025 (FAA): https://unibuc.ro/wp-content/uploads/2025/04/Metodologie-concursuri-didactice-FAA-2025.pdf
- UBB methodology 10.03.2025: https://www.ubbcluj.ro/ro/infoubb/posturi_vacante/files/legislatie/Metodologie_concurs_ocupare_posturi_didactice_cercetare_10_03_2025.pdf
- UEFISCDI TE 2026 package: https://uefiscdi.gov.ro/resource-832286-Pachet-informatii-TE-2026_aprobat.pdf ; call page: https://uefiscdi.gov.ro/proiecte-de-cercetare-pentru-stimularea-tinerelor-echipe-independente-te
- UB doctoral admission regulation 2026: https://doctorat.unibuc.ro/wp-content/uploads/2026/01/Regulamentul_admitere_Doctorat_UB_2026_Aprobat_Senat-2025-12-17_site.pdf ; 2025: https://doctorat.unibuc.ro/wp-content/uploads/2025/01/Regulamentul_admitere_Doctorat_UB_2025_Aprobat_Senat.pdf ; page: https://doctorat.unibuc.ro/admitere/
- FMI Școala Doctorală de Informatică 2026 page + scanned regulation (Google Drive id 1WLoRqwwKOrMM4fEfE4KhTvBYpRVkv-3c): https://fmi.unibuc.ro/anunturi-doctorat/anunturi-sdi/admitere-doctorat-2026-scoala-doctorala-de-informatica/ ; 2025: https://fmi.unibuc.ro/anunturi-doctorat/anunturi-sdi/admitere-doctorat-2025-scoala-doctorala-de-informatica/
- UB master regulation 2026: https://admitere.unibuc.ro/wp-content/uploads/2026/01/Regulament-admitere-MASTERAT_2026.pdf ; admission modes 2025: https://admitere.unibuc.ro/wp-content/uploads/2025/01/Modalitati_admitere-2025_Masterat.pdf
- FMI master admission 2025 page: https://fmi.unibuc.ro/admitere-master-2025/ ; methodology PDF (Google Drive id 13yDB0aYGqjVDZqZnPe2uPlPlDu1np5ay)
- UPB doctoral methodology 2025–2026: https://upb.ro/wp-content/uploads/2025/02/Metodologie-admitere-doctorat-2025-2026_.pdf ; UAIC Law doctoral documents: https://laws.uaic.ro/ro/admitere/admitere-studii-de-doctorat/documente-necesare-doctorat
- Law 199/2023 (doctoral chapter): https://lege5.ro/Gratuit/geztqmjwgq4ts/studii-universitare-de-doctorat-lege-199-2023?dp=guzteobxge3tani
- Law 500/2004: https://www.lege-online.ro/lr-LEGE-500-2004-(56721).html (snippet) ; commentary https://www.avocatnet.ro/articol_71956/Utilizarea-limbii-romane-in-anun%C8%9Burile-de-angajare-este-o-obliga%C8%9Bie-precontractual%C4%83-care-ne-protejeaz%C4%83-de-fraudele-online.html
- Codul muncii art. 16: https://www.codulmuncii.eu/titlu-2/capitol-1/articol-16.html ; art. 17: https://lege5.ro/Gratuit/gi2tknjxgq/art-17-incheierea-contractului-individual-de-munca-codul-muncii?dp=gu3dmmjxhe3ti
- HG 64/2011 civil-status methodology art. 24: https://lege5.ro/gratuit/gi2tinzvgq/art-24-inregistrarea-actelor-de-stare-civila-metodologie?dp=gu3demjvhe4tc ; https://www.emaramures.ro/acte-starea-civila-numele-si-prenumele-compuse-nu-se-mai-despart-prin-cratima-in-actele-de-nastere-si-casatorie/
- COR 2512: https://rubinian.com/cor_5_ocupatia.php?id=2512 ; https://codcor.ro/2512-proiectanti-de-software
- Europass RO instructions (official PDF): https://www.dataprotection.ro/servlet/ViewDocument?id=2132 ; Europass RO portal: https://europass.europa.eu/ro/create-europass-cv ; National Europass Centre: https://www.europass-ro.ro/ , https://mobility.europass-ro.ro/eu_si_europass/documente_utile/
- ICAO Doc 9303 Part 3: https://www.icao.int/sites/default/files/publications/DocSeries/9303_p3_cons_en.pdf
- Romanian ID card (diacritics, MRZ, CEI dates): https://ro.wikipedia.org/wiki/Carte_de_identitate_rom%C3%A2neasc%C4%83 ; MAI CEI communiqué 13.03.2025: https://www.mai.gov.ro/noua-carte-electronica-de-identitate-devine-disponibila-in-romania-... ; CEI portal: https://carteadeidentitate.gov.ro/despre
- Diacritics standards: https://www.secarica.ro/ro/rou/s-uri-si-t-uri
- ORCID record (public API v3.0 /person): https://orcid.org/0009-0001-8776-8498 ; ORCID name guidance: https://support.orcid.org/hc/en-us/articles/360006973853-Add-and-edit-your-name-on-your-ORCID-record

Practitioner / secondary
- https://ro.linkedin.com/posts/irinacfilip_nu-%C8%99tii-%C3%AEn-ce-limb%C4%83-s%C4%83-trimi%C8%9Bi-cv-ul-activity-7335198550118518785-GC5a (2025-06)
- https://ro.linkedin.com/posts/andreea-georgiana-nicolae_trimit-cv-ul-in-romana-sau-in-engleza-in-activity-7285185188634976256-4Wvq (2025-01)
- https://ro.linkedin.com/posts/ioana-m-a20827182_humanresources-recruiterlife-talentacquisition-activity-7453053872182468608-pwPq (2026-04)
- https://www.linkedin.com/posts/lina-nareikiene_possibly-an-unpopular-recruitment-opinion-activity-7492489758103797760-vf84 (2026-08)
- https://www.reddit.com/r/programare/comments/zzu57m/cv_in_romana_sau_engleza
- https://cvhub.ro/blog/cv-europass-sau-cv-modern (2026-07) · https://taurusid.com/articles/how-to-write-a-cv-for-jobs-in-romania-format-photo-rules-employer-expectations (2026-09) · https://freecv.org/ro/model-cv (2026-05) · https://romanianpost.ro/diferenta-dintre-cv-ul-clasic-si-cv-ul-europass-explicata-simplu/ (2026-08) · https://www.interactive-cv.com/en/blog/europass-cv-vs-standard-cv (2026-09) · https://resumelio.com/blog/europass-vs-custom-cv-2025 · https://www.cvmaker.ro/blog/cv/ce-este-un-cv-europass-si-cum-il-creez · https://www.resumly.ai/ai-resume-builder-romania
- https://resumeflex.com/how-to-write-a-professional-cv-for-romania-job-market/ (2025-04) · https://jobera.com/resources/romania-cv-writing-guide/ (2023) · https://www.lexis.ro/cv-in-engleza (2025-07) · https://verandamall.ro/jobs/resurse/model-cv/ (2025) · https://www.link-academy.com/cum-sa-scrieti-un-cv-in-engleza-si-germana · https://www.jobseeker.com/ro/cv/articole/cv-in-engleza · https://www.cvwizard.com/ro/articol/cv-in-engleza
- https://www.hipo.ro/locuri-de-munca/vizualizareArticol/2301/CV-cum-se-completeaza-corect-fiecare-camp-din-Curriculum-Vitae · https://www.hipo.ro/locuri-de-munca/vizualizareArticol/2298/CV-Europass-ce-este-si-cum-se-completeaza · https://8ore.ro/blog/cv-pentru-ats-cum-il-faci-sa-treaca-de-filtrul-automat-cu-exemple-rapide-68 · https://www.undelucram.ro/ro/cumlucram/cv-respins-da-vina-pe-ai-2294 · https://nobsresume.com/resume-builder/romanian · https://centruldebusiness.ro/cum-adaptezi-cv-ul-pentru-fiecare-domeniu-it-vs-hr-vs-vanzari/ (2026-08) · https://developmentfactory.ro/blog/programator-vs-inginer-software-vs-dezvoltator-software
- https://www.avocatnet.ro/forum/discutie_305239/CERTIFICAT-NASTERE-SI-BULETIN-CU-DIACRITICE-DIFERITE.html
