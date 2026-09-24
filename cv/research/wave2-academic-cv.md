# Wave 2 — The academic CV track (MSc / PhD applications with zero registered publications)

Date: 2026-09-23. Owner: Andrei Mihai Visalon (BSc CS, Univ. of Bucharest FMI, 2022–2025; ORCID 0009-0001-8776-8498 with zero works; unpublished phenibut pharmacology manuscript, FAERS pharmacovigilance analysis, and an IberLEF 2026 shared-task entry "grace-iberlef-2026").

Labels: **VERIFIED** = read directly in ≥2 independent sources (or one primary regulation + one corroborating source). **INFERRED** = my synthesis from verified facts. **UNVERIFIED** = fewer than two independent sources. Confidence bands follow the WEP scale (high ≈ 90%+, likely ≈ 55–80%, uncertain ≈ 30–55%, speculative < 30%).

Method note: WebSearch + WebFetch, plus the claude.ai-hosted Exa and Tavily connectors (each worked once). The `search-hub` MCP (tavily/exa/firecrawl) returned HTTP 401 all session — connection/auth failure, not absence of capability. PDFs that WebFetch could not parse (Harchol-Balter, UB regulations, UB FMI master methodology, CNATDCU criteria, Cambridge/Imperial CV guides, the "Demystifying CS PhD Admissions" book) were downloaded and text-extracted locally with pypdf; extracted texts are in `scratchpad/w2acv/`. Pages that refused (Oxford Careers 403, academicpositions.com 403, UniMelb 403, APA Style blog returned empty, old.fmi.unibuc.ro connection refused, acs.pub.ro TLS error, GitHub API rate-limited) are noted where a claim leans on them.

---

## 0. The one-paragraph answer

An academic CV is a factual, education-first, unbounded-length record whose job is to document research evidence; an engineering résumé is a 1–2-page persuasion document. But for this owner the more important finding is that **"the academic CV" is not one document — three of his four target processes do not even ask for a CV in the US sense**:

1. **Romanian MSc admission (UB FMI 2026)** is an administrative dossier + oral exam. There is *no CV and no letter of intent* in the dossier; what counts is a signed **list of extracurricular professional achievements with proof**, each worth +0.25 on top of the bachelor's average (published articles, conference communications, research internships, contest results, competitive scholarships) and a 12-minute-style **oral presentation on a subject of the candidate's choosing**. UBB instead wants a *2-page Europass CV + 2-page career plan* graded pass/fail. (VERIFIED, primary regulations.)
2. **Romanian PhD admission** legally requires a **master's degree and 300 ECTS** — he cannot apply until he finishes an MSc. The UB dossier asks for a **"memoriu de activitate științifică" (scientific activity report), a list of published papers, a written research-topic proposal aligned with a supervisor's advertised position, and a bibliography** — again, no CV as such; the Informatics school admits by **oral exam**. (VERIFIED, primary.)
3. **EU PhD positions (NL/DE/CH/Nordics)** are advertised *jobs*: CV + cover letter (+ often a proposal) to a specific supervisor/project; candidates are employees; a master's is assumed. (VERIFIED.)
4. **Competitive international (US-style) PhD** is a department admission judged on research evidence, letters, and statement of purpose; publications are explicitly *not required*, and an MS is not required in the US. (VERIFIED, faculty sources 2014–2026.)

So the "system" he is building needs one **master academic record** (long-form, factual) from which four renderings are generated: (a) a Romanian dossier evidence list + proofs, (b) a Europass 2-page CV, (c) an international academic CV (2–3 pages) + SOP, (d) an EU-job CV + cover letter. Details, evidence, and what to do about each follow.

---

## 1. Academic CV vs engineering résumé — structure, length, tone, section order

**Claim 1.1 (VERIFIED, high; 6 sources).** An academic CV leads with **Education**, then research experience, publications/presentations, honors, teaching/service, and skills; it has *no objective/professional summary*, no fixed length, and is reverse-chronological within sections. A résumé leads with a summary and is 1–2 pages.
- Pitt Career Central: a graduate-school CV "begins with your educational history and delves into academic achievements, including any research, publications, and detailed descriptions of academic projects"; sections listed: Education, Summary, Research, Publications, Presentations, Professional/Work Experience, Community/Academic Service, Honors & Awards; font ≥ 10–12 pt, margins ≥ 0.5–1 in. https://careercentral.pitt.edu/resources/writing-an-effective-cv-for-your-graduate-school-application-and-how-this-differs-from-a-resume/
- Cornell Graduate School: résumé = "one or two page summaries"; CV "can vary from two pages to several pages"; "the order of topics in a CV format is flexible" — arrange to highlight strengths; consult faculty in your field. https://gradschool.cornell.edu/career-and-professional-development/pathways-to-success/prepare-for-your-career/take-action/resumes-and-cvs/
- Cambridge Careers Service (PhD/postdoc CV book, p.20 table): Academic CV "Length: No limit"; Industry R&D CV "2 pages with possible appendix of publications"; Non-research CV "2 pages maximum. This is non-negotiable." https://www.careers.cam.ac.uk/files/phdpostdoccvbook.pdf
- Imperial College tipsheet (v2019): a CV "is a factual marketing document"; for postdoc/fellowship applications "a maximum of two to three pages, with your publications and conference proceedings included at the end like an appendix"; list qualifications reverse-chronologically; "It is rarely necessary to include school qualifications." https://www.imperial.ac.uk/media/imperial-college/administration-and-support-services/staff-development/public/postdocs/tipsheets/Academic-CVs-v2019.pdf
- UNC TIBBS "CV Dos and Don'ts": no objective statements, no personal information (pictures, family status, birth date), no pre-college activities, no undefined abbreviations, no free-standing "skills/techniques" section (put techniques inside research descriptions); dates on the right; PDF; reverse chronological. https://tibbs.unc.edu/cv-dos-and-donts/
- Nature careers "38 tips on writing an academic CV" (2011): put the most important information in the first half of page 1; avoid "I'm a passionate, hard-working individual"; you may "include papers that aren't published yet if you indicate what stage they are at". https://blogs.nature.com/naturejobs/2011/09/27/38-tips-on-writing-an-academic-cv/

**Claim 1.2 (VERIFIED, high; 3 sources).** For a graduate-school applicant the practical length is **2–3 pages**, not the "unbounded" faculty CV. Pitt: "2 to 3 page version emphasizing research experience and undergraduate honors" (via search summary of Pitt/UCSD pages); Imperial: 2–3 pages for postdoc/fellowship; Cambridge: no limit but examples for early-career are 2–4 pages.

**Claim 1.3 (INFERRED from 1.1–1.2, likely).** Tone: the CV is *inventory*, the statement/cover letter is *argument*. Adjectives and self-description belong in the SOP/cover letter (UNC TIBBS: manuscripts in preparation "should undeniably be mentioned in your cover letter"; Nature: no self-praise on the CV).

**What it means for the owner.** His master academic record should be education-first (BSc 2022–2025, thesis title, supervisor, grade if strong), then *Research & technical projects* (the phenibut manuscript, FAERS analysis, IberLEF entry, and self-built research tooling written as research entries: question, method, result, artifact), then *Manuscripts & shared-task papers* (status-labelled, see §3), *Presentations*, *Open-source software* (with DOIs once minted, see §4), *Honors*, *Skills* (short, inside research descriptions where possible). No summary paragraph, no photo, no birth date **in the international rendering**; the Europass rendering follows Europass conventions (§7). Target 2–3 pages for any application; the master record itself can be as long as needed.

---

## 2. What a CS MSc/PhD applicant with zero publications is expected to show instead

**Claim 2.1 (VERIFIED, high; 7 faculty/department sources).** Publications are *not required*; committees look for **evidence of research readiness**: what you did with the opportunities you had, letters from people who supervised research-like work, and a statement that names a specific research direction and what you have done in it.
- JHU CS PhD FAQ: "While many of our applicants have publications demonstrating their research experience, we care more about what you did with the opportunities you were given"; they accept "many students without prior publications" and reject "others with multiple publications". https://www.cs.jhu.edu/academic-programs/graduate-studies/phd-program/phd-admissions-faqs/
- Harchol-Balter (CMU, "Applying to Ph.D. Programs in Computer Science", last updated 2014, still the canonical guide): application parts are transcript, GRE/TOEFL, personal statement, "Previous research experience (possibly in industry)", letters, awards; "research is what matters, not grades. A GPA of 4.0 alone with no research experience will not get you into any top CS program"; ways to get research experience include REUs, a job where "sometimes you can do research on the job. I did this", an M.S. project, and "You can work alone or with a friend. Ask professors in your classes to tell you about interesting open problems"; warning for international applicants: publications in venues "which we are not familiar with and have no access to" get discounted — "Publish in internationally recognized conferences" and "Create a web site that has links to all of your papers in English". https://www.cs.cmu.edu/~harchol/gradschooltalk.pdf
- ThanhVu Nguyen (GMU), *Demystifying PhD Admissions in Computer Science* (PDF dated 2026-09-04): "Publications are never required for PhD application. However, given the competitiveness of CS admission, they can significantly strengthen your application"; §2.2.2 "Many students do not have the opportunity to publish papers. Thus, other writings, even those under submission or even rejected, would still help. Be sure to upload these with your application ... Adcom members can quickly skim over the paper and determine its quality"; "local conferences and non-English journals or conferences do not carry as much weight"; adcom reading: "I look through the CV for research experience, publications, serious projects, and unusual achievements." https://roars.dev/phd-cs-us/demystify.pdf (source: https://github.com/dynaroars/phd-cs-us)
- William J. Bowman (UBC adcom, 2020): first filter is the statement — "Do you clearly and concisely express interest in some research area? Do you seem to have any clue what that research area involves?"; "I've seen undergrads with multiple publications 'get rejected' over students with none"; "Do you have software engineering experience? This is pretty valuable for some research areas, so I like to see date ranges for all industry work in your resume"; research experience "is kind of rare for undergrads". https://williamjbowman.com/blog/2020/02/08/one-inside-perspective-on-the-graduate-student-application-process/
- Dave Andersen (CMU adcom chair, 2015): systems faculty "valued examples of students being able to manage large systems and complexity. Large programming experience / projects outside of class, whether that be on their own, through a startup, internship, or through research"; theory faculty valued publications as "great, but not mandatory"; the SoP "was a chance for applicants to talk about the projects they'd done outside of class". https://da-data.blogspot.com/2015/03/reflecting-on-cs-graduate-admissions.html
- Bill Gasarch (UMD, 2026-09-20): on committees he looks at transcript (minor), letters about STEM work, "Papers they've written whether or not they have been published", and a statement saying why a PhD, what interests, why qualified. https://blog.computationalcomplexity.org/2026/09/i-dont-care-about-majors-minors-or.html
- mycsphd.org (faculty-written reading protocol): "Skim resume for publications, interesting (i.e., non-internship) work experience, and anything unusual (5–20 seconds)"; letters and SOP get ~1 minute each on first pass. https://mycsphd.org/_pages/phd-admissions.html

**Claim 2.2 (VERIFIED, high; 3 sources).** Letters are the decisive input, and letters only work if a researcher supervised something. Harchol-Balter: professors' letters count most, then research scientists'; Kuper (2016): "letters of recommendation are the most important part of your application, and the best letters come from people who (a) know you well and (b) are well-known in the research community ... It is great – really great – to work through SICP or do compiler hacking on your own. But to get into grad school, you need recommendations, and for that, you need to find your people." https://decomposition.al/blog/2016/07/28/getting-into-a-phd-program-without-previous-research-experience/ ; Bowman: many letters are useless ("they did well in my class"), he looks for "faculty with whom the applicant worked closely as an RA or TA".

**Claim 2.3 (VERIFIED, likely; 2 sources).** An MS is *not* required for US CS PhD admission, but is commonly required elsewhere. Nguyen §1.2.4: "No, while other countries often encourage or even require an MS for PhD students in CS, it is common in the US to directly apply for a PhD program after a 4-year undergraduate program"; Eurydice/UB regulation confirm the Romanian requirement (§6).

**What it means for the owner.** With zero publications his international PhD file must carry (i) *writing samples* — the phenibut manuscript and the IberLEF system paper uploaded as PDFs even if unpublished/rejected (Nguyen), (ii) a statement that names one research direction (e.g., NLP for clinical/pharmacological text, or pharmacovigilance signal detection) and narrates what he has already done in it, and (iii) **at least two letters from people who supervised research-like work** — this is his largest gap: independent work produces artifacts but not letters. Concrete gap-closers with weeks-to-months horizons: get the phenibut/FAERS work co-supervised or reviewed by a faculty member (FMI, UMF Carol Davila pharmacology, or a UB doctoral supervisor whose advertised topic matches — see §6.3); present at FMI's "Comunicări științifice studențești" session (this also earns +0.25 in the UB master dossier, §5); ask a shared-task organizer or co-author to write about his IberLEF contribution. Also build the "simple website with your name, research interests, publications, and projects" Nguyen and Harchol-Balter both recommend (GitHub Pages suffices).

---

## 3. Listing unpublished work-in-progress, submitted manuscripts, preprints, and shared-task papers without overstating

**Claim 3.1 (VERIFIED, high; 5 sources).** Convention: keep **peer-reviewed publications**, **manuscripts submitted / under review**, and **manuscripts in preparation** in *separate, labelled subsections*; state the *stage* honestly; never name the target journal for an in-prep manuscript; early-career applicants *should* list real in-prep work, senior people should not.
- Brian McGill, Dynamic Ecology (2025-03-25): graduate students and postdocs should include real in-prep work and add specificity — "results completed, manuscript partially drafted"; pre-tenure faculty list *submitted* work; tenured faculty only published/accepted, else it "looks a little like you're trying to pad your record"; commenter Bethann Garramon Merkle uses "Publications in Process" for submitted/in-review work. https://dynamicecology.wordpress.com/2025/03/25/should-i-include-in-prep-on-my-cv/
- Jeremy Fox, Dynamic Ecology (2024-05-15): list preprints "in the same way that you would list a complete draft ms"; unsubmitted preprint → same subsection as other unpublished manuscripts ("ms in prep – draft available upon request"); submitted preprint → the under-review section; a DOI "doesn't elevate a preprint's evaluation status"; "Search committees don't give you any 'partial credit' for papers that haven't yet gotten all the way through peer review" — preprints show trajectory, not achievement. https://dynamicecology.wordpress.com/2024/05/15/how-and-why-to-list-preprints-on-your-cv-as-a-faculty-job-applicant/
- UNC TIBBS: include "submitted, in review, or in press manuscripts in the publications section"; do not write "Manuscript in preparation for Nature submission". https://tibbs.unc.edu/cv-dos-and-donts/
- Cambridge CV book example (p. ~30): "Manuscript in preparation, expected submission October 2014" and "Manuscript prepared and under review by co-authors, expected submission September 2014" — i.e., a stage + expected date. https://www.careers.cam.ac.uk/files/phdpostdoccvbook.pdf
- Nature 38 tips: "include papers that aren't published yet if you indicate what stage they are at".

**Claim 3.2 (VERIFIED, high; 2 library guides quoting APA 7 §10.8).** The standard status descriptors are bracketed: **[Unpublished manuscript]**, **[Manuscript in preparation]**, **[Manuscript submitted for publication]**, followed by department and institution; the year is the year the manuscript was written, and the journal to which it was submitted is *not* named. Augusta University APA 7 guide: templates "Author, A. A. (Year). *Title* [Manuscript submitted for publication]. Name of Department, Name of Institution." https://guides.augusta.edu/c.php?g=984317&p=7469608 ; Navitas/ACAP guide lists the same three descriptors and "Always use a DOI if the resource has one". https://libguides.navitas.com/apa7/unpublished (The "do not name the journal / use year written" rule appears in the UniMelb guide and APA's own page per search snippets; direct fetch was blocked — treat that sub-rule as VERIFIED-by-snippet, likely.)

**Claim 3.3 (VERIFIED, high; 4 sources).** A shared-task **system description paper** is a real, citable publication once it is in the proceedings — but a lightly-reviewed workshop-tier one, and it should be labelled as such.
- CEUR-WS rules: "Proceedings papers must be *peer-reviewed* by a program committee"; CEUR-WS has "no formal relation" with DBLP/Scopus/Google Scholar, which "crawl CEUR-WS.org or DBLP on a regular basis"; cite with "CEUR-WS.org as 'publisher'". https://ceur-ws.org/HOWTOSUBMIT.html
- IberLEF 2025 organisers' duties: "Manage the submission and scientific evaluation of the system description papers ... submitted by the participants"; "The accepted papers will be published in the IberLEF proceedings" (CEUR-WS); "Task Overviews will be published in the SEPLN journal". https://sites.google.com/view/iberlef-2025/calls
- CEUR-WS Vol-4098 (IberLEF 2025): "There were 125 papers submitted for the 14 shared tasks. 123 submissions were accepted" (~98% acceptance) — participation papers are essentially accepted if competent. https://ceur-ws.org/Vol-4098/
- IberLEF 2026 (ACL portal call): proceedings "including the description of the participating systems will be published at CEUR-WS.org"; overviews in the SEPLN journal, September 2026 issue. https://www.aclweb.org/portal/content/iberlef-2026-second-call-task-proposals
- Comparable NLP norm: SemEval system papers are single-blind peer-reviewed and "part of the official SemEval proceedings" (ACL Anthology). https://semeval.github.io/paper-requirements.html
- Romanian evaluative frame (CNATDCU Informatics criteria, 2016, still the reference list logic): forums are ranked A*, A, B, C, D; "categoria D include conferințele ... indexate SCOPUS, IEEE, ACM, SPRINGER, DBLP ... (nu și forumuri ... care au fost indexate numai CoRR abs/arXiv)"; "Workshop-urile asociate conferințelor care publică în volume distincte se evaluează ca forumuri independente". https://www.edu.ro/sites/default/files/Comisia%202%20Informatica_Criterii-minimale-Info-oct2016.pdf — i.e., a CEUR-WS (DBLP-indexed) paper is a recognised, low-tier venue in Romanian scoring; an arXiv-only preprint counts for nothing there.

**Claim 3.4 (INFERRED, likely).** Recommended rendering for the owner's three items, until their status changes:

```
MANUSCRIPTS AND SHARED-TASK PAPERS
Peer-reviewed
  (none yet)
Shared-task / workshop papers
  Visalon, A. M. (2026). <System name>: <approach> for <task> at IberLEF 2026
    [System description paper, submitted to the IberLEF 2026 proceedings, CEUR-WS.org;
    team rank k/N on <metric>]. Iberian Languages Evaluation Forum @ SEPLN 2026, León.
    -> once published: cite as a CEUR-WS proceedings paper with volume, pages, URL.
Manuscripts in preparation
  Visalon, A. M. (2026). <Phenibut title> [Manuscript in preparation; analysis complete,
    full draft, target submission <month>]. Faculty of Mathematics and Computer Science,
    University of Bucharest.   (No journal name here.)
  Visalon, A. M. (2026). <FAERS title> [Manuscript in preparation; disproportionality
    analysis complete, draft in progress]. <affiliation>.
```
Rules encoded: separate subsections (McGill, UNC); stage + expected date (Cambridge); no target journal (UNC, APA); a preprint, once posted, moves to "Preprints (not peer-reviewed)" with DOI (Fox, Navitas); the shared-task paper is never called a "journal article" and carries the CEUR-WS venue name so a Romanian reader can classify it (CNATDCU).

**What it means for the owner.** Posting the phenibut manuscript to a preprint server *before* it is accepted gives a DOI, a citable object for ORCID (§4), and something committees can read — but no evaluative credit (Fox); Romanian scoring gives arXiv-only zero (CNATDCU). So preprint for *visibility and ORCID population*, not for credit; the credit comes from the eventual peer-reviewed version and from the CEUR-WS system paper. Do not inflate: the phrase to avoid is any version of "publications: 3".

---

## 4. ORCID iD with zero works — helps, hurts, and what to register

**Claim 4.1 (VERIFIED, high; 3 sources).** ORCID records can hold far more than journal articles; the supported work types include **Software**, **Preprint**, **Conference paper / poster / presentation / output**, **Dataset**, **Research tool**, **Working paper**, **Report**, **Blog post**, **Other academic publication**, plus education and employment affiliations. ORCID FAQ "What work types does ORCID support?" defines Software as "A computer program in source code (text) or compiled form" and Preprint as "a scientific manuscript without peer-review ... typically submitted to a public server/repository by the author". https://info.orcid.org/ufaqs/what-work-types-does-orcid-support/ ; Indiana University graduate-student guide: "ORCID profiles support a wide variety of output, from poster projects to student papers to video exhibits, conference papers, blog posts, websites", and put the iD in "email signatures, online profiles, employment applications, manuscript submissions, scholarship applications, grant applications, and conference presentations". https://iu.libguides.com/orcid/graduate-students

**Claim 4.2 (VERIFIED, high; 3 sources).** Software releases on GitHub can be given DOIs through Zenodo's GitHub integration (one DOI per release plus a concept DOI), and DataCite's **ORCID auto-update** will push new DOIs to his ORCID record automatically — *only if* (a) he enables auto-update in DataCite Profiles and (b) his ORCID iD is in the DOI's creators metadata; it is **not retroactive** ("only triggers for findable DOIs registered or updated after the user enables auto-update"). Zenodo: "Linking your GitHub account enables you to automatically archive your repositories on GitHub via our GitHub integration". https://help.zenodo.org/docs/profile/linking-accounts/ ; DataCite: https://support.datacite.org/docs/datacite-and-orcid ; DataCite troubleshooting notes Zenodo/Figshare version DOIs — DataCite pushes the original DOI, not each version. https://support.datacite.org/docs/orcid-auto-update-not-working ; ORCID auto-update FAQ: https://info.orcid.org/ufaqs/what-is-orcid-auto-update-orcid-auto-update-enables-authors-to-have-their-orcid-records-automatically-updated-it-works-like-this/

**Claim 4.3 (UNVERIFIED — INFERRED, likely).** No source I could read says an empty ORCID record *hurts*; library guides uniformly advise registering early and populating it. The credible inference: an iD in the CV header is neutral-to-positive; a reviewer who clicks through to an empty record learns nothing, which is a missed opportunity rather than a penalty. The only way it *could* hurt is if the CV claims outputs the record contradicts (e.g., "publications" on the CV, none on ORCID).

**What it means for the owner (concrete plan, ~2–4 hours plus per-release upkeep).**
1. Fill ORCID **Education** (BSc CS, UB FMI, 2022–2025) and **Employment** (once the undocumented jobs/freelance are reconstructed by the other wave) — these render even with zero works.
2. Link ORCID ↔ Zenodo ↔ GitHub; enable **DataCite ORCID auto-update first**, then cut tagged releases for the 3–6 repos he would show a committee (the research tooling first: FAERS pipeline, IberLEF system code, MCP/agent infrastructure with a research use). Add a `CITATION.cff` with his ORCID so the DOI metadata carries the iD (pyOpenSci guidance: https://www.pyopensci.org/lessons/package-share-code/publish-share-code/cite-code.html). Each release becomes a **Software** work on ORCID automatically.
3. When the phenibut manuscript is preprinted (DOI from the server), it appears as **Preprint**; when the IberLEF paper is in CEUR-WS, add it as **Conference paper** (CEUR-WS papers are DBLP-indexed; ORCID's DBLP/Crossref search-and-link tools may pick it up, otherwise add manually with the CEUR URL).
4. Put `ORCID: 0009-0001-8776-8498` in the CV header of *every* rendering (IU guide), and keep the CV's publication count and the ORCID record consistent (Claim 4.3).

---

## 5. Independent open-source work and self-built research tooling vs formal research assistantships

**Claim 5.1 (VERIFIED, high; 5 faculty sources).** Committees do credit substantial self-directed technical work — *as a stand-out signal and as raw material for the statement* — but they discount it relative to supervised research in two specific ways: it rarely produces the letters that decide admissions, and "software development" is not "research experience".
- Nguyen (2026) §2.6.4: "Many CS students also use GitHub to host their projects and demonstrate their involvement in open-source projects ... Having popular projects or active contributions can help you stand out, especially if you do not have much research experience"; §3.3.3: mention "your personal GitHub project with hundreds or thousands of stars or your regular contributions to well-known open-source projects"; Appendix D.2 "Open Source Contributions": contributing to research labs' open-source projects lets students "gain practical research experience ... you might be able to get a LOR from the project maintainer". But §2.2.3: "working at a FAANG company as a software engineer does not count as research experience ... software development, even at a top company, does not demonstrate your research ability and potential for a PhD program"; a LOR for non-research work "might not count much". https://roars.dev/phd-cs-us/demystify.pdf
- Andersen (CMU): systems faculty explicitly valued "large programming experience / projects outside of class, whether that be on their own, through a startup, internship, or through research"; "Sometimes the experience won over" poor grades. https://da-data.blogspot.com/2015/03/reflecting-on-cs-graduate-admissions.html
- Bowman (UBC): software engineering experience "is pretty valuable for some research areas" — but the filter is whether the statement shows a research question and knowledge of the area. https://williamjbowman.com/blog/2020/02/08/one-inside-perspective-on-the-graduate-student-application-process/
- Kuper: solo hacking is "really great" but yields no letters; find the researchers who work on the thing you can't stop thinking about. https://decomposition.al/blog/2016/07/28/getting-into-a-phd-program-without-previous-research-experience/
- Harchol-Balter: research "possibly in industry" counts; working "alone or with a friend" on open problems suggested by professors is a listed route to research experience — the professor's involvement is what turns it into a letter. https://www.cs.cmu.edu/~harchol/gradschooltalk.pdf
- GradPilot (2026-09-16), on GitHub links in CS statements: links are "optional supporting evidence unless the application specifically makes it a required component"; "A repository can support your account; it should not carry the explanation"; some programs (Utah, Kentucky) explicitly invite links, others prohibit supplemental material — "follow the destination the program identifies". https://gradpilot.com/news/cs-sop-github-project-links

**Claim 5.2 (VERIFIED, likely; 2 sources).** Consultant and Q&A sources (lower grade) agree: "A computer science applicant with no formal lab experience but several substantial machine learning projects may still appear highly competitive if the work demonstrates intellectual depth and clear research direction" (Admit Lab, former professor; https://admit-lab.com/blog/phd-without-research-experience/); Quora threads frame the counter-view that "programming is not science" (https://www.quora.com/How-beneficial-are-open-source-contributions-for-graduate-admissions-in-computer-science...). Treat as corroboration, not evidence.

**Claim 5.3 (INFERRED, likely).** The conversion rule that makes independent tooling count: each project must be written as a **research entry** (question → method → measured result → limitation → artifact with DOI), not as a product bullet; and at least one must acquire a *researcher witness* (co-author, reviewer, supervisor, shared-task organiser) who can write about it.

**What it means for the owner.** His 68 repos are a liability only if presented as a wall of products; presented as 3–5 research-instrument entries (e.g., "FAERS disproportionality pipeline: PRR/ROR with 2-run reconciliation over 20M reports; result X; limitation Y; Zenodo DOI") they are exactly what the systems/NLP faculty above say they want. The agent-infrastructure/MCP work is *engineering*; keep it to one line in the academic rendering unless it served a research question. The gap to close is witnesses: the IberLEF task gives a natural one (organisers/co-participants); the phenibut/FAERS work needs a pharmacology or biostatistics faculty reader; a UB doctoral supervisor with a matching advertised topic (e.g., Liviu P. Dinu's NLP topic list, §6.3) is the highest-value target because it doubles as the future PhD route.

---

## 6. Romania — MSc admission (administrative dossier) vs PhD admission (regulated concurs) — and how both differ from an international PhD pitch

### 6.1 Romanian MSc admission is a dossier + oral exam, and no CV is requested at UB FMI

**Claim 6.1.1 (VERIFIED, high; primary regulation + admission page).** University of Bucharest FMI, *Metodologia ... ADMITERE 2026 la studii universitare de MASTER* (linked from https://fmi.unibuc.ro/admitere-master-2026/ ; PDF https://drive.google.com/file/d/1SP-yB7SsO0y7ZAywOIi0uGj-45VgDVe6/view):
- Two tests. **Proba 1 (proba de dosar)**: "analiza rezultatelor obținute de candidat pe parcursul programului de licență": the bachelor's general average (excluding the licence exam) **+0.25 points per extracurricular professional achievement** in Mathematics/Informatics/CTI, capped at 10, max 3 achievements per criterion, only with proof ("diplome, adeverințe, certificate, confirmări"). Counted: a) national/international student contests (team contests excluded except ICPC regional/final); **b) "Comunicări prezentate la sesiuni sau conferințe științifice naționale sau internaționale"; c) "Articole științifice publicate"**; d) problems proposed for school olympiads; **e) "Stagii de cercetare într-o instituție de profil, din țară sau din străinătate"**; f) internships abroad; g) competitive performance/excellence scholarships; h) professional distinctions; i) other student performances. **Not counted: "calitatea de angajat al unei firme, participarea la hackathon-uri, voluntariate, cursuri, specializări (chiar dacă sunt în domeniu)".**
- **Proba 2 (proba orală)**: for Informatics masters, candidates "vor susține o prezentare orală pe baza unui subiect propus de ei (lucrarea de licență, un proiect, un referat etc.) și vor răspunde la întrebările comisiei", graded on difficulty of the notions, mastery, relevance/option, clarity.
- Dossier (VI.1): registration form, bachelor diploma/supplement, baccalaureate, **the bachelor thesis (signed)**, **the signed list of extracurricular achievements + proofs**, birth certificate, medical certificate, ID, fee receipt, **B2 English certificate for English-taught programmes** (baccalaureate language certificates *not* accepted), consent to recording of the oral. **No CV, no letter of intent, no publication list beyond the achievements list.**
- Admission *without exam* for candidates in the top 5% of their bachelor cohort by graduation average (ranked by the dossier grade; admitted with average 10).
- Programmes 2026 (CS domain): Artificial Intelligence (EN), Data Science (EN), Natural Language Processing (EN), Security and Applied Logic (EN), Inginerie Software, Sisteme Distribuite, Baze de Date și Tehnologii Software. Sessions: July (registration 1–14 July 2026) and September (1–13 Sept 2026). https://fmi.unibuc.ro/admitere-master-2026/

**Claim 6.1.2 (VERIFIED, high; UBB regulations + document list).** Babeș-Bolyai FMI 2026: admission average = **75% overall study average + 25% bachelor's exam grade** (in-field candidates); a mandatory **portfolio = Europass CV (PDF, max 2 pages) + "Professional and Scientific Career Development Plan" (max 2 pages)**, evaluated **ADMITTED/REJECTED**, not scored; minimum 6.0; no interview/written test for in-field candidates; research/publications not a ranking criterion. https://www.cs.ubbcluj.ro/admission/masters-programmes/masters-admissions-regulations/ ; https://www.cs.ubbcluj.ro/admission/masters-programmes/documents-required-in-the-master-studies-registration-process/

**Claim 6.1.3 (VERIFIED, likely; UPB central page).** Politehnica București master dossier (July/Sept 2026): diploma/certificate, birth certificate, ID, enrolment form, fee, declaration on prior funded place, language proof for foreign-language programmes; **no CV, letter of intent, or publication list mentioned**; regulation PDF linked. https://upb.ro/admitere/admitere-masterat/ (faculty page acs.pub.ro could not be fetched — TLS error.)

**What it means for the owner.** For UB FMI (the natural target: AI / NLP / Data Science in English, 2 years, gating step for any Romanian or most EU PhDs):
- The document that matters is not a CV but the **signed achievements list with proofs**. Every +0.25 is real: a published scientific article (the CEUR-WS system paper, once out, plausibly qualifies as "articol științific publicat" — ask the secretariat in writing before the session), a *presented* communication at a scientific session (FMI's student sessions or any conference — this is the cheapest verifiable point), a documented research internship, a competitive scholarship. Employment, hackathons, volunteering, courses are explicitly worth zero — so his freelance/engineering history buys nothing here.
- Proba 2 lets him present *any* subject: the IberLEF system or the FAERS analysis is a far stronger oral than a bachelor thesis retelling; graded on difficulty and mastery.
- Check whether his bachelor average puts him in the top 5% of his cohort — if so he is admitted without exam. He must obtain a B2 English certificate from a Ministry-approved issuer (or use the "two semesters of English during the bachelor" route stated on the page) for the English-taught tracks.
- For UBB or any institution with a "portfolio", he needs a **2-page Europass CV** and a **2-page career plan** ready; both are pass/fail.

### 6.2 Romanian PhD admission requires a master's, and its dossier is a research file, not a CV

**Claim 6.2.1 (VERIFIED, high; 2 primary sources).** A master's degree and **300 ECTS (bachelor + master)** are mandatory. UB *Regulation on the organisation and conduct of the admission contest for doctoral studies 2026* (Senate 17.12.2025), Art. 12: candidates must be "graduates with a master's degree or a diploma equivalent to it" with "at least 300 transferable credits"; Eurydice Romania: "absolvenții cu diplomă de master sau echivalentă acesteia", 300 ECTS cumulative; legal basis Law 199/2023, HG 681/2011, OME 3020/2024 and OME 3693/2024. https://doctorat.unibuc.ro/wp-content/uploads/2026/06/REGULATION-ON-THE-ORGANISATION-AND-CONDUCT-OF-THE-ADMISSION-CONTEST.pdf ; https://eurydice.eacea.ec.europa.eu/ro/eurypedia/romania/ciclul-iii-studii-universitare-de-doctorat

**Claim 6.2.2 (VERIFIED, high; primary RO + EN texts).** UB doctoral dossier, Art. 14(1): ... g) master's diploma; **h) "memoriu de activitate ştiintifică"** (scientific activity report); **i) "lista cu titlurile lucrărilor ştiinţifice publicate"**; **j) "propunerea unei teme (în scris) în concordanţă cu temele de cercetare aferente pozițiilor vacante de student-doctorand scoase la concurs de către conducătorul de doctorat, cu justificarea importanţei acesteia"**; **k) "o listă bibliografică cuprinzătoare pentru tema propusă"**; l) language certificate; m) declaration; n) fee. **No CV appears in UB's list.** Doctoral schools must publish "at least 3 criteria for separating the candidates" and evaluate "the previous scientific experience reflected in studies, presentations at conferences, scientific publications, etc."; ranking by average, **minimum 7**. https://doctorat.unibuc.ro/wp-content/uploads/2026/01/Regulamentul_admitere_Doctorat_UB_2026_Aprobat_Senat-2025-12-17_site.pdf

**Claim 6.2.3 (VERIFIED, high; SDI pages 2025–2026 + UB table).** Școala Doctorală de Informatică (UB): admission is an **"Examen oral"** (UB per-school table, Senate 21.01.2026, https://doctorat.unibuc.ro/wp-content/uploads/2026/01/DOCTORAT_Admitere-2026-Propunere_Locuri_Examen-Facult_SD_Site.pdf); July 2026: registration 1–12 July, exam 15 July 2026, results by 31 July; candidates scheduled in **12-minute slots**; places: 2 full-time budget with scholarship + 1 priority + 5 part-time budget without scholarship + 10 fee-paying (+ non-EU); fee 300 lei; must be a master's graduate. https://fmi.unibuc.ro/anunturi-doctorat/anunturi-sdi/admitere-doctorat-2026-scoala-doctorala-de-informatica/ ; 2025 page shows the same format (14 July 2025, 12-min slots). https://fmi.unibuc.ro/anunturi-doctorat/anunturi-sdi/admitere-doctorat-2025-scoala-doctorala-de-informatica/
- The SDI page links a **supervisor topic list with reading lists** (Google Doc): e.g., "Liviu P Dinu: 'Modele computaționale pentru predicția personalizată a procesării limbajului'" with six 2024–2025 references (ScanDL 2.0, EyeFormer, LEMI Romanian readability, Romanian mouse-tracking reading data); Alex Popa (fuzzy combinatorial optimisation, graph labelings); Sorin Stupariu (3D point-cloud classification; vision-and-language); Ruxandra Olimid (side-channel attacks on post-quantum implementations). https://docs.google.com/document/d/1SmusTy7muRsc1iQCEpNpSRzOZpljlvga/ (INFERRED, likely: the oral exam is a discussion of the candidate's written topic proposal against the supervisor's announced topic and bibliography — consistent with Art. 14 j–k and the 12-minute schedule; the SDI's own scoring criteria were not found online — the old FMI page refused connections.)

**Claim 6.2.4 (VERIFIED, high; 3 institutions).** Other Romanian doctoral schools *do* require a CV, usually **Europass**, plus a list of works: UMF Cluj — "Curriculum Vitae (model Europass)" with "activitatea științifică cu precizarea domeniilor de interes" and "Lista cu titlurile lucrărilor științifice elaborate" (published in extenso, conference abstracts, monographs, corresponding-author role); https://umfcluj.ro/programe-studii/doctorat/admitere/acte-necesare-inscrierii/ ; Univ. of Craiova (2019 doc): "Curriculum vitae; Listă de lucrări ştiinţifice publicate sau comunicate"; https://efs.ucv.ro/pdf/studii_doctorale/informatii_concurs_admitere.pdf ; UBB (master) — Europass. Search-level (unfetched) hits from USAMV/UGAL/ASE describe "CV Europass semnat pe fiecare pagină" — plausible, UNVERIFIED individually.

**What it means for the owner.** (1) A Romanian PhD is **not available to him until ~2028** (after a 2-year MSc); the timeline is MSc 2026–2028 → PhD concurs July/Sept 2028. (2) The documents to prepare are a **"memoriu de activitate științifică"** (a narrative research report — closer to a research statement than a CV), a **list of published works** (which may legitimately be short: the CEUR-WS paper + any peer-reviewed article by then; unpublished items go in the memoriu, not the list), a **written topic proposal matched to a specific supervisor's advertised position**, and a **bibliography**. (3) The supervisor is chosen *before* the exam — so the MSc years should be used to work with the intended supervisor (Dinu's NLP group is the obvious fit for a Spanish clinical argument-mining participant). (4) Keep a Europass CV current anyway: many Romanian IOSUDs require it, and UB might add it.

### 6.3 EU PhD positions are jobs; US-style PhD admission is a department pitch

**Claim 6.3.1 (VERIFIED, high; 5 sources).** In NL/DE/CH/Nordics a PhD is an **advertised, salaried position** applied to with **CV + cover/motivation letter (+ research proposal where asked)** addressed to a specific project/supervisor; candidates are employees under collective agreements.
- Utrecht University: "As an employee PhD candidate, you fall under the Collective Labour Agreement of Dutch Universities"; separate P0–P3 salary scale. https://www.uu.nl/en/organisation/phd-programmes/phd-in-utrecht/salary-and-labour-market ; Universiteiten van Nederland CAO 2025–2026 (teaching capped at 20% for PhD candidates). https://www.universiteitenvannederland.nl/en/collective-labour-agreement-of-dutch-universities ; Radboud terms of employment for PhD candidates. https://www.ru.nl/en/staff/services/employment-conditions/cla/terms-of-employment-for-phd-candidates
- European Commission (2021/2022): typical documents "official copy of the previous diploma(s), curriculum vitae (CV), research proposal for your PhD, motivation letter, references and/or recommendation letters"; finding a supervisor first is "either compulsory or advisable"; EURAXESS lists positions. https://education.ec.europa.eu/news/how-to-apply-for-doctoral-studies-in-europe
- ETH Zurich doctorate registration: final Bachelor's *and Master's* transcripts and diploma, two recommendation letters, a CV with "full and continuous history (no biographical gaps)", and the professor's **signed supervision confirmation** uploaded with the registration — the professor accepts you first. https://ethz.ch/en/doctorate/registration-admission/erforderliche-anmeldeunterlagen.html
- academicpositions.com (fetched via Tavily excerpt; direct fetch 403): "Students apply for specific vacant doctoral projects that are usually tied to a professor's research. As part of their application, they must create a research proposal"; "In several European countries, PhD students are seen as employees and have work contracts"; US candidates "apply to a department's PhD program, rather than a specific PhD project". https://academicpositions.com/career-advice/phd-in-europe-or-the-us ; ProFellow: "European PhDs are typically advertised as specific funded research projects ... In the U.S., students commonly apply to a department". https://www.profellow.com/tips/u-s-vs-europe-how-graduate-schools-differ

**Claim 6.3.2 (VERIFIED, high; 2 institutions).** EU MSc admission is likewise a fixed document set with a *tabular* CV and no research expectation: ETH Master's general documents — the CV "must contain a full and continuous history (no biographical gaps) of your education and work experiences ... Start with high school ... (tabular resume)", in the programme's language of instruction. https://ethz.ch/en/studies/master/application/international-bachelor/application-documents/general-documents.html ; TUM Master Informatics — "statement of reasons" (max 2 pages), CV, "a scientific essay of approx. 1,000 words on a specified topic", curriculum analysis, two-stage aptitude assessment with a 90-minute written test; no mention of research, publications or projects as criteria. https://www.cit.tum.de/en/cit/studies/degree-programs/master-informatics/

**What it means for the owner (the "not the same document" point, made concrete).**

| Process | What is actually read | Document he must produce | Where his research artefacts count |
|---|---|---|---|
| UB FMI MSc (RO) | bachelor average + proof-backed achievements list; 12-min oral | signed achievements list + proofs; thesis PDF; oral deck | +0.25 each: presented communications, published articles, research internships |
| UBB MSc (RO) | 75/25 grade formula; pass/fail portfolio | Europass CV ≤2 p + career plan ≤2 p | not scored |
| ETH/TUM MSc (EU) | grades/curriculum fit; motivation; essay/test | gap-free tabular CV; 2-page statement; 1,000-word essay | motivation letter only |
| UB SDI PhD (RO, ≥2028) | 12-min oral on a supervisor-aligned topic; min 7 | memoriu de activitate științifică; list of published works; topic proposal; bibliography | list of works + memoriu |
| EU PhD vacancy | fit to the advertised project; supervisor's judgement | 2-page CV + tailored cover letter (+ proposal); 2 referees | CV research entries; letters |
| US-style PhD | letters; SOP; research evidence; writing samples | 2–3-page academic CV; SOP; uploaded papers; 3 letters | everything, if narrated as research |

---

## 7. Europass and the personal-data convention clash

**Claim 7.1 (VERIFIED, high; 3 sources).** Europass is the CV format Romanian public institutions name when they ask for one (UBB master portfolio; UMF Cluj doctorate; Craiova asks for a CV without naming the model); Europass describes itself as "one of the best-known CV formats in Europe ... familiar to employers and education institutions", free, 31 languages, and suggests adding "a professional photograph". https://europass.europa.eu/en/create-europass-cv

**Claim 7.2 (CONTESTED, see §9).** US/UK academic-CV guidance forbids photos, birth dates and marital status (UNC TIBBS); Europass and Romanian registration forms routinely carry them (the UB doctoral registration form asks for date of birth, marital status, citizenship, ethnicity, CNP). Not a contradiction to resolve but a rendering rule: personal data only in the Romanian/Europass rendering.

**What it means for the owner.** The master record should hold the personal-data fields once, tagged "RO/Europass only"; the international rendering strips them. Keep the Europass export within 2 pages (UBB limit) so it is reusable as-is.

---

## 8. Gap-closing programme (weeks to months, no deadline — matches the owner's decision #4)

Ordered by leverage per the evidence above; each item names the claim it serves.

1. **Get a researcher witness on the existing work** (Claims 2.2, 5.3). Approach one UB FMI faculty member whose SDI topic list matches (NLP: Dinu) and one pharmacology/biostatistics reader for the phenibut/FAERS manuscripts. Ask for critique, not a favour; a co-authorship or a documented "stagiu de cercetare" is the ideal outcome (+0.25 in the UB master dossier and a letter later).
2. **Present something** at FMI's "Comunicări științifice studențești" or a national student/young-researcher session before the July 2026 or September 2026 master session (Claim 6.1.1 b) — a proof-backed +0.25 and the first line in "Presentations".
3. **Finish and submit the IberLEF 2026 system description paper** to the CEUR-WS proceedings (Claim 3.3); acceptance is near-certain if competent (123/125 in 2025); this becomes his first indexed publication (DBLP; Romanian category-D forum) and the strongest single line in the list of works.
4. **Preprint the phenibut manuscript** once a faculty reader has seen it (Claim 3.1/3.4): DOI → ORCID "Preprint"; label "[Preprint, not peer-reviewed]" on the CV; then submit to a journal and relabel "[Manuscript submitted for publication]" without naming the journal.
5. **Mint DOIs for 3–5 research repos** via Zenodo with ORCID in `CITATION.cff`, after enabling DataCite auto-update (Claim 4.2). Rewrite each README's top as a research entry (question/method/result/limitation).
6. **Populate ORCID** education/employment now (Claim 4.1); put the iD on every rendering.
7. **Build the one-page academic site** (GitHub Pages) with name, research interests, the three manuscripts/papers with status labels, the DOI'd software, and the CV PDFs (Claims 2.1 Harchol-Balter, 5.1 Nguyen).
8. **Assemble the UB FMI master dossier pack**: achievements list template + proofs folder; B2 English certificate or the two-semester-English evidence; a 10-minute oral deck on the IberLEF or FAERS work; check the top-5% exemption with the FMI secretariat.
9. **Draft the three narrative documents** from one source: (a) US-style SOP (research direction + what he did), (b) EU cover letter template keyed to a vacancy ("they want X, I have Y"), (c) the Romanian "memoriu de activitate științifică" outline for 2028.
10. **Maintain**: on each new artefact, update the master record first, then regenerate Europass, international CV, and the achievements list — never edit a rendering directly.

---

## 9. Contested or widely repeated but unevidenced

- **"An empty ORCID looks bad."** No fetched source says so; guides only say "register early and use it". Treat as unevidenced (Claim 4.3).
- **"Preprints count as publications."** Fox (2024): explicitly no "partial credit" from hiring committees; Romanian CNATDCU: arXiv-only forums excluded from scoring; Nguyen (2026): unpublished/rejected writing still *helps* committees judge quality. Position: preprints help *evaluation of your ability*, not *credit*.
- **"Open-source work substitutes for research experience."** Faculty sources split by area: systems/NLP-adjacent faculty (Andersen, Nguyen, Bowman) credit large self-directed projects and GitHub activity; Nguyen and Kuper also say software development is not research and self-directed work yields no letters. Both are true; the resolution is framing + witness (Claim 5.3).
- **"Whether a CEUR-WS system paper is a 'published scientific article' for UB FMI's +0.25."** The methodology says "Articole științifice publicate" without defining venue tier; CEUR-WS is DBLP/Scopus-crawled and CNATDCU category D at best. Likely yes, but the admissions committee decides case-by-case — confirm in writing.
- **"Romanian doctoral dossiers require a Europass CV signed on every page."** True at some institutions (UMF Cluj Europass; search hits for USAMV/UGAL/ASE mention signed pages) but **UB's 2026 regulation lists no CV at all** — the requirement is institution-specific.
- **Personal data (photo, DOB, marital status) on the CV**: forbidden by US/UK academic guidance, routine in Europass/Romanian forms. Rendering rule, not a fact dispute.
- **Length**: "no limit" (Cambridge/Cornell/Nature) vs "2–3 pages" (Imperial/Pitt for early career). Consistent once career stage is held fixed: early-career applicant CVs are 2–3 pages.
- **US "no MS needed" vs Europe/Romania "MS required"**: both verified; they describe different systems (Nguyen §1.2.4; UB Art. 12; Eurydice).
- Older canonical sources (Harchol-Balter 2014, Andersen 2015, Kuper 2016, Bowman 2020) vs the 2025–2026 preference: every load-bearing point from them is corroborated by a 2025–2026 source (Nguyen 2026-09-04, Gasarch 2026-09-20, GradPilot 2026-09-16, McGill 2025-03-25, UB/UBB/TUM/ETH 2026 pages).

---

## 10. Source register (grade: P = primary regulation/institution; F = faculty/committee-member account; G = university careers/library guide; S = secondary/consultant/SEO; X = could not fetch, used via snippet)

| # | Source | Grade | Used for |
|---|---|---|---|
| 1 | UB FMI Metodologia admitere master 2026 (PDF via Drive) | P | §6.1 |
| 2 | UB FMI admitere-master-2026 page | P | §6.1 |
| 3 | UBB FMI master admission regulations 2026 | P | §6.1 |
| 4 | UBB FMI documents required (master 2026) | P | §6.1, §7 |
| 5 | UPB admitere masterat 2026 | P | §6.1 |
| 6 | UB Regulament admitere doctorat 2026 (RO) | P | §6.2 |
| 7 | UB Regulation ... admission contest doctoral 2026 (EN) | P | §6.2 |
| 8 | UB per-doctoral-school places & exam type 2026 | P | §6.2 |
| 9 | UB FMI SDI admitere doctorat 2026 page (+2025) | P | §6.2 |
| 10 | SDI supervisor topic list (Google Doc) | P | §6.2 |
| 11 | Eurydice Romania, ciclul III | P | §6.2 |
| 12 | UMF Cluj acte necesare doctorat | P | §6.2, §7 |
| 13 | Univ. Craiova informatii concurs admitere doctorat (2019) | P | §6.2 |
| 14 | CNATDCU Informatică criterii minimale (2016) | P | §3.3 |
| 15 | ETH Zurich master general documents; doctorate registration documents | P | §6.3 |
| 16 | TUM Master Informatics page | P | §6.3 |
| 17 | Utrecht Univ. PhD salary & labour market; UvN CAO; Radboud terms | P | §6.3 |
| 18 | European Commission, how to apply for doctoral studies in Europe | P | §6.3 |
| 19 | Europass create-CV page | P | §7 |
| 20 | CEUR-WS HOWTOSUBMIT; Vol-4098 index | P | §3.3 |
| 21 | IberLEF 2025 calls page; IberLEF 2026 ACL-portal call | P | §3.3 |
| 22 | SemEval paper requirements | P | §3.3 |
| 23 | ORCID work types FAQ; ORCID auto-update FAQ | P | §4 |
| 24 | DataCite & ORCID docs (+ troubleshooting) | P | §4 |
| 25 | Zenodo linking accounts help | P | §4 |
| 26 | JHU CS PhD admissions FAQ | P | §2 |
| 27 | Harchol-Balter, Applying to Ph.D. Programs in CS (2014) | F | §2, §5 |
| 28 | Nguyen, Demystifying PhD Admissions in CS (2026-09-04) | F | §2, §5 |
| 29 | Bowman, One inside perspective (UBC, 2020) | F | §2, §5 |
| 30 | Andersen, Reflecting on CS graduate admissions (CMU, 2015) | F | §2, §5 |
| 31 | Gasarch, Computational Complexity blog (2026-09-20) | F | §2 |
| 32 | Kuper, Getting into a PhD program without research experience (2016) | F | §2, §5 |
| 33 | mycsphd.org, How does CS PhD admissions work | F | §2 |
| 34 | McGill, Dynamic Ecology (2025-03-25) | F | §3 |
| 35 | Fox, Dynamic Ecology (2024-05-15) | F | §3 |
| 36 | Pitt Career Central; Cornell Grad School; Cambridge CV book; Imperial tipsheet; UNC TIBBS; Nature 38 tips | G | §1, §3 |
| 37 | Augusta Univ. APA 7 guide; Navitas APA 7 guide; UniMelb (X) | G | §3.2 |
| 38 | IU Libraries ORCID for graduate students; pyOpenSci cite-code | G | §4 |
| 39 | GradPilot, GitHub links in CS SOP (2026-09-16) | S | §5 |
| 40 | Admit Lab (Barr); Quora threads; Acatrix 2026 | S | §5 corroboration only |
| 41 | academicpositions.com (X, Tavily excerpt); ProFellow | S | §6.3 |

Local extracted texts: `scratchpad/w2acv/` (harchol.txt, demystify.txt, fmi_master_metodologie.txt, ub_doct_reg_2026_{ro,en}.txt, ub_sd_exam_types_2026.txt, cnatdcu_info_2016.txt, cam_cvbook.txt, imperial_tips.txt, craiova.txt, gdoc_*.txt).
