# Software-engineering resume format conventions in 2026: what is verified, what is vendor-documented, what is folklore

Research date: 2026-09-23. Prepared for: Andrei Mihai Visalon (BSc Computer Science, University of Bucharest, 2022-2025; Romania; GitHub `Prekzursil`, 68 public repos; ORCID with zero registered works; no existing resume file). Question answered: the actual, currently-true conventions for a software engineering resume in 2026 (length, format, file type, section order) and what genuinely breaks applicant tracking systems, with the widely-repeated claims tested one by one.

## 0. Evidence labels used throughout

- **VERIFIED-PRIMARY**: the vendor's own documentation, a primary research report read directly, or raw data with a published method.
- **VERIFIED-SECONDARY**: an independent measurement with a published, reproducible method (usually a resume-tool company testing layouts against real parsers). Commercial interest is noted; the method is what earns the grade.
- **ASSERTED**: stated without evidence (marketing pages, listicles, anonymous anecdotes). Counted, not trusted.
- **INFERRED**: my inference from the evidence; labeled as such every time.
- Confidence bands (Sherman-Kent style): *almost certain* 90-99%, *highly likely* 80-90%, *likely* 55-80%, *uncertain* 30-55%, *speculative* <30%.

Method note: the session's WebSearch budget was exhausted before this task started and the `search-hub` Tavily/Exa/Firecrawl keys were rejected; the claude.ai-hosted Tavily and Exa connectors, WebFetch, direct PDF text extraction (pypdf), and the Scholar Gateway academic index were used instead. Firecrawl (claude.ai) had no credits. Three targets could not be fetched by any route: Lever's exact file-type list (page returns 401/failed fetch), Google's careers page body (JS-rendered; the Google recruiters' video transcript was used instead), and the full text of an r/resumes practitioner thread (only comment fragments were retrievable). Everything below that depends on those is marked accordingly.

---

## 1. Who parses your resume in 2026: the ATS landscape

### 1.1 Market share depends entirely on what you measure (VERIFIED-PRIMARY for each dataset; the disagreement itself is the finding)

| Dataset | Method | Leader(s) | Source |
|---|---|---|---|
| Jobscan 2026 ATS Usage Report | Manual review of all 500 Fortune 500 career sites after the June 3, 2026 list release, plus 1M+ scans across 13,130 companies since 2016 | Fortune 500: 97.4% (487/500) use a detectable ATS; **Workday >40%**, SAP SuccessFactors 12% (combined 52.4%). Across the broader 13,130-company set: **Greenhouse 19.0%, Workday 17.5%, Lever 15.6%, iCIMS 14.4%** | https://www.jobscan.co/blog/fortune-500-use-applicant-tracking-systems/ |
| Apps Run The World (2024 revenue) | Vendor revenue estimates | Market $2.5B (+12.3%); top 10 vendors only 51.1% combined; **iCIMS 10.7%** first, then Oracle, Workday, Greenhouse, Lever, SmartRecruiters, ADP, Dayforce, SAP SuccessFactors, Bullhorn | https://www.appsruntheworld.com/top-10-hcm-software-vendors-in-applicant-tracking-market-segment |
| Pin 2026 ATS Market Share Report | Live ATS integrations of 600+ recruiting teams connected to Pin (June 2026), "not survey answers" | 23 distinct systems; no platform above one in six; two agency CRMs 29.5% combined, **Ashby 15.6%**, Crelate 13.6%, Bullhorn 6.0%, Greenhouse 5.2% (sample skews to agencies and startups) | https://www.pin.com/blog/ats-market-share-report |

Reading for this owner (INFERRED, *highly likely*): the systems he will actually meet as a new-grad software engineer applying to tech employers are Greenhouse, Lever and Ashby (startups and scale-ups; identifiable from apply URLs `boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`), and Workday, SAP SuccessFactors/SmartRecruiters and iCIMS at large enterprises (`myworkdayjobs.com`, `sapsf.com`/`successfactors.com`, `icims.com`). The URL-to-vendor mapping is ASSERTED in several secondary guides but is trivially checkable and consistent with the vendors' own domains.

Consolidation that changed the picture in the last 18 months (ASSERTED by trade sources, consistent across three of them; not independently verified here): SAP acquired SmartRecruiters (September 2025; confirmed by SAP's own Romanian product page positioning "SmartRecruiters pentru SAP SuccessFactors"), Workday absorbed HiredScore (2024) and Paradox (October 2025), iCIMS bought Apli. Greenhouse and Ashby both shipped MCP servers in May 2026 so external agents can query pipeline data.

Romania specifically (VERIFIED-PRIMARY for vendor pages, INFERRED for the conclusion): local job boards (eJobs, BestJobs, Hipo, OLX, LinkedIn) still front most Romanian applications; a local ATS vendor (Mingle) positions Greenhouse and Workable as the tools of multinationals with SAP SuccessFactors/Workday HRIS back-ends; eJobs lists SmartRecruiters, Bullhorn, Zoho and Phoenix ATS among its integrations. So a Romanian applicant to a Bucharest office of a multinational will most often land in SuccessFactors/SmartRecruiters, Workday or Greenhouse; an applicant to a US/UK-headquartered startup lands in Greenhouse/Lever/Ashby.

A note on a number you will see repeated: Huntr's 2026 article states "Greenhouse holds 30.6% market share; Workday is second at 19.6%" with no source. It conflicts with both Jobscan datasets. Treat as ASSERTED.

---

## 2. What the dominant vendors' own documentation says about accepted formats and parsing

| Vendor | Accepted candidate upload formats | Size limits | What the vendor says about parsing | Auto-reject by resume content? |
|---|---|---|---|---|
| **Greenhouse** (VERIFIED-PRIMARY) | `.doc .docx .pdf .rtf .txt` | Upload up to 100 MB; **parser will not parse files over 2.5 MB** | Publishes an explicit parse-failure list (see 2.1). Failed parse = resume still attached, recruiter enters fields by hand. Does not load externally linked images. Full parsing in 28 languages incl. Romanian. | No. Talent Matching FAQ: "does not automatically disposition any candidates nor does it make any hiring decisions"; "does not auto-reject or auto-advance any candidate, including candidates in lower match categories or those labeled 'Needs manual review'". Candidate AI opt-out exists. Auto-reject rules exist only on application-form answers. |
| **Lever** (VERIFIED-PRIMARY, list itself not retrieved) | Text-based document files; "Lever cannot parse information from image files (like JPG or PNG)"; test: if you cannot highlight the text, it is likely not parseable | not stated on the page retrieved | Parser extracts name, organization, contact details, work history into the profile; listed failure causes are import-path issues (email/Chrome extension/API), not layout. Exact file-type list could not be retrieved (page blocked); secondary sources say PDF/DOC/DOCX/RTF/TXT (ASSERTED). | Not documented as a feature; secondary sources describe a "Talent Fit" badge that labels top matches without marking others unqualified (ASSERTED). |
| **Workday** (VERIFIED-PRIMARY via HiredScore documentation; per-tenant lists are employer-configured) | HiredScore "supports these file types for resume attachments: DOC, DOCX, PDF, RTF, and TXT"; a university tenant FAQ lists `.pdf .doc .xls .mp4 .png .jpg .ppt` as uploadable; two public-sector tenants publish a 5 MB cap (secondary) | commonly 5 MB per file (employer-set) | HiredScore assigns grades A-D by how well the parsed resume matches the job description; **no grade is assigned when the resume is missing, in an unsupported format, or the requisition has no job description or is a campus/graduate requisition**. Recruiters can also keyword-search the original resume. Workday's own parsing docs are behind a customer login; a secondary review (atsgrader) reports they say results vary with format and word order and advise against image-based styles (ASSERTED, not seen). | Not by resume content; questionnaire (knockout) answers can be configured to disqualify. HiredScore grades sort the queue; a "D" is not a rejection but may never be read if enough "A"s exist. |
| **Oracle Taleo Enterprise** (VERIFIED-PRIMARY) | `.doc .docx .txt .rtf .pdf .htm .html .wpd .odt` (attachments); one parsing path documents a 100 KB cap and adds `.xls .xlsx`; Taleo Business Edition 24A now accepts `PNG` and `JPEG` resumes | 100 KB in that one path (hedged: exact scope of the cap not confirmed) | Legacy system; the folklore about PDFs and columns largely originates here | Prescreening/disqualification questions can auto-reject (documented Taleo capability). |
| **SAP SuccessFactors / SmartRecruiters** (mixed) | SmartRecruiters glossary: submit `.docx` "for maximum parsing compatibility", or a PDF exported from a word processor, "do not scan the pdf as an image" | not stated | SmartRecruiters' 2020 candidate privacy policy names **Textkernel** as the parser. Its glossary advises: "Avoid headers and footers", "Avoid tables and columns", "Do not feel that you are limited to one page" (vendor advice, ASSERTED not measured). Textkernel (engine also reported behind SuccessFactors and iCIMS by a secondary test) states it handles pdf, docx, doc, html, odt, txt plus OCR for scans, 70+ formats, 25-29 languages, and "both single and multi-column resumes". | Screening questions configurable (secondary). |
| **iCIMS** (VERIFIED-PRIMARY for the statement; file list ASSERTED) | Secondary sources: DOCX, PDF (text), RTF, TXT, HTML, ODT | employer-configurable | iCIMS glossary: "most ATS vendors have fixed these tricks and read PDFs and other file types accurately... They also allow for more formatting variations, including colored fonts and pictures. That said... it's still best to advise candidates to keep the format of their resumes simple." | Secondary sources: AI is advisory. |
| **Ashby** (VERIFIED-PRIMARY for AI review; file list ASSERTED) | Secondary: `.pdf .docx .doc .txt .rtf` | not found | "Enhanced resume parsing" option extends languages and "improves parsing for resumes with more complex layouts or formatting". AI-Assisted Application Review evaluates each employer-defined criterion as Meets / Does not meet / Undecided with citations to resume sentences; if the resume is unreadable the criteria are marked skipped. Bias audit (Aug 2024): "does not aggregate individual applicant-criteria outcomes into applicant-level scores for rank-ordering". Note: by 2026 the docs also offer an "AI Job Criteria Met Percentage" column that recruiters can sort by, so de facto ranking is available. | No auto-reject on resume content documented; auto-reject question rules exist. |
| **Workable** (VERIFIED-PRIMARY) | `.pdf .doc .docx .rtf .html .odt` | 5 MB | - | - |
| Parsing engines behind ATSs (VERIFIED-PRIMARY specs) | **Daxtra**: doc/docx/xls/xlsx/ppt/txt/pages/pdf "including graphical document"/html/rtf/odt/mht/eml/msg/xps/vcf/jpg/png (OCR)/zip; **RChilli**: doc/docx/pdf/rtf/txt/html/htm/odt/docm/dotm/dot/dotx/mht/png/jpeg; **Sovren** (now Textkernel): 60+ formats; **Affinda** handbook: table-like "group" fields "are tricky for the model—especially if the document doesn't visually show a clear grouping" | - | - | - |

### 2.1 Greenhouse's published parse-failure list (VERIFIED-PRIMARY; the single most useful vendor document found)

From "Unsuccessful resume parse" (support.greenhouse.io, article 200989175): a resume may fail or partially fail to parse when it is larger than 2.5 MB, contains placeholder ("fake") data, or has these formatting issues:

- spaces between letters (letter-spaced text);
- graphics, photos, or word art;
- uploaded as an image rather than a document;
- "Complex resumes with tables, headers, and footers";
- "Resumes with the name and contact information in the header, footer, or text box";
- "Resumes that have a columned layout";
- no clear sections / differing formats between sections;
- company names without identifying words such as Inc., Co., LTD, LLC;
- incomplete job titles ("Sr. Account Exec" instead of "Senior Account Executive").

Consequence stated by Greenhouse: the resume is attached to the candidate and the recruiter fills in fields manually. It is a data-quality failure, not a rejection.

### 2.2 What the vendors say about automatic rejection (VERIFIED-PRIMARY where quoted)

- Greenhouse: assistive only; humans decide (Talent Matching FAQ; Real Talent page: "Talent matching never advances or rejects candidates for you").
- Ashby: per-criterion evidence with citations; product principle that AI does not decide; unreadable resume = skipped criteria, not rejection.
- Workday HiredScore: grades and sorts; no grade without a parseable, supported-format resume.
- Lever: parsing populates fields; no automated disposition documented.
- Taleo and Workday questionnaires: configured knockout answers can disqualify.

Practitioner corroboration (VERIFIED-SECONDARY, small samples): Enhancv's interviews with 25 US recruiters across nine ATSs (Sept-Oct 2025): 23/25 (92%) said their ATS does not auto-reject for formatting, content or design; only 2/25 had any content-based auto-reject configured (Bullhorn, BambooHR, match/experience thresholds); knockout questions are used by everyone who has them; 44% have an AI fit score, 8% use it as a hard cutoff. Resume Genius's 2026 survey of 1,000 US hiring managers (Pollfish RDE): 71% say their company uses an ATS; 49% "personally review resumes and use ATS to flag, rank, or organize them"; 37% "let the ATS screen out applications based on criteria they set" (self-report; "criteria" here means requirements, not formatting).

Harvard Business School / Accenture, *Hidden Workers: Untapped Talent* (Sept 2021; 2,275 executives, at least 750 each in the US, UK and Germany; 8,000+ workers) (VERIFIED-PRIMARY, read from the PDF): "more than 90% of employers in our survey use their RMS to initially filter or rank potential middle-skills (94%) and high-skills (92%) candidates"; "Almost half the companies surveyed weeded out resumes that present such a 'work gap'. If an applicant's work history has a gap of more than six months, the resume is automatically screened out"; 88% of employers agree qualified high-skills candidates are vetted out because they do not match the exact job-description criteria (94% for middle-skills). This is the strongest evidence that automated exclusion is real, and it attributes it to recruiter-configured criteria (degree proxies, gaps, exact skills), never to layout or file type.

---

## 3. The six widely-repeated claims, tested

### 3.1 "Two-column layouts break ATS parsing"

**Measured** (four independent tests with published methods, all 2026):

1. Resumap on dev.to (July 28, 2026): one synthetic backend-engineer resume rendered through 36 templates, imported into Zoho Recruit, Workable, Manatal and the Textkernel engine, diffed field by field; the text layer of every PDF was verified locally first. Email and phone parsed 36/36 on every parser. Textkernel kept all 10 job-critical skills 36/36 but mis-segmented work history on 5 templates and lost location on 5; Workable segmented jobs 36/36 but garbled one degree glyph; Zoho lost "React" on 8 templates. "Several of the two-column layouts scored 22/22 on Zoho and 3/3 positions on Textkernel. Several one-column layouts didn't. The column count didn't predict the outcome; the emission order did." Diagnosis: a PDF is a sequence of positioned text runs; if the generator emits the sidebar interleaved with the main column, segmentation fails; if it emits column by column, two columns parse like one. Suggested check: `pdftotext -layout resume.pdf - | head -40`. (VERIFIED-SECONDARY; data and corpus published.)
2. Enhancv (Aug-Sept 2026): 3 resumes x 17 templates x 7 extractors (pdftotext -layout, PyMuPDF sorted, pdftotext default, pdfminer.six, pdftotext -raw, PyMuPDF unsorted, pypdf) = 357 runs scored against the source data. Word recovery differed by under half a percentage point between one and two columns; email, location, phone and portfolio link came through in all 357 runs. Under the worst extractor family (geometry-sorted, reads straight across the page) sections stayed intact only 35% of the time with two columns vs 60% with one (a 24-point drop); under reading-order or content-stream extractors the drop was about one point. Only one template (contact details in a narrow side column) ever lost the candidate's name. When the damaged text was then read by an LLM (Claude Haiku 4.5, DeepSeek-V3.1, Qwen3-32B, GPT-OSS 120B), the structural loss shrank to about 3 points, except employer names (100% -> 83%) because interleaving separates title from company. Enhancv sells two-column templates (two-thirds of its downloads), so its incentive runs toward "columns are fine"; the method is nonetheless the largest and most transparent found. (VERIFIED-SECONDARY.)
3. ATSVerification (June 30, 2026): one finance resume, six layouts, pdf.js (pdf-parse) extraction plus structural detectors. Two-column-with-sidebar was the only variant to draw a critical flag (reading-order scramble; score 100 -> 85); all names, emails, dates and skills still extracted in every variant. (VERIFIED-SECONDARY; explicitly not a login to Workday or Greenhouse.)
4. MyResumeKit (Aug 2, 2026, updated Aug 27): 13 templates through mupdf and pdf-parse. The asymmetric two-column LaTeX template (Deedy-Resume) was the best-scoring third-party template with full field recovery on both engines, "proof that 'two-column' alone does not doom a resume to parsing badly". (VERIFIED-SECONDARY; harness committed to their repo.)

Supporting but weaker: Enhancv's earlier test inside a major job board's employer dashboard (two-column and icon-heavy resumes parsed with 100% field extraction; identical results to a plain control) (VERIFIED-SECONDARY, single board, date unknown); UnchartedCareer's July 2026 extractor test reports two columns lost 1.4% of field reads but three columns lost 14.6% (method details not fully retrieved; VERIFIED-SECONDARY with reservations).

**Contradicting claims** (all ASSERTED or methodologically opaque): "two-column layouts failed in 7 out of 8 systems" (QuickCV; "demo environments, sandbox tools, and publicly available parsing APIs", no data published); "we uploaded 1,000 anonymized two-column resumes to Workday, Greenhouse, Lever, iCIMS, Taleo and SmartRecruiters... Workday failed 94%" (ResumeBold; uploading a thousand resumes into six enterprise tenants is not described and is not plausible without employer accounts; treat as unverified); one blogger says Greenhouse interleaves columns while another says Greenhouse and Lever parse two columns correctly and Workday/Taleo/iCIMS/SuccessFactors do not (Jobloo vs AI Applyd; they contradict each other). These are the sources most people quote.

**Vendor-documented**: Greenhouse lists "columned layout" among parse-failure causes; SmartRecruiters says avoid columns; Textkernel says it handles multi-column; Ashby's enhanced parsing exists precisely because complex layouts are harder. **Human side**: Ladders' 2018 eye-tracking report (see 3.6) says resumes with multiple columns fared worse with recruiters; the 2012 report found recruiters' gaze trace "erratic" on poorly organized layouts.

**Verdict** (*highly likely*): the claim is half-true and mis-diagnosed. Two columns do not make a resume unreadable or rejected; they create a reading-order risk whose size depends on (a) how the PDF generator emitted the text stream and (b) which extractor the ATS uses, neither of which the applicant can see. What degrades is work-history segmentation and employer attribution, i.e. searchability and auto-filled fields, not contact details. In Greenhouse, Lever and Ashby the recruiter is shown the original PDF anyway (Ashby's docs show the resume file in Application Review; a Greenhouse-using recruiter quoted by Enhancv says he opens the file whenever the parse looks wrong). Single column is nonetheless the dominant strategy because it costs nothing and also wins with human readers.

**For this owner**: use one column. Before every upload, run `pdftotext -layout` (or copy-paste into Notepad) and confirm it reads top to bottom in order.

### 3.2 "PDFs are rejected by ATSs"

**Vendor-documented** (VERIFIED-PRIMARY): PDF is an accepted upload at Greenhouse, Lever (any text-based file), Workday/HiredScore, Oracle Taleo, SmartRecruiters (with a preference for `.docx`), Workable, and in the Textkernel, Daxtra, RChilli and Sovren engines. No dominant vendor documents rejecting PDF.

**Measured**: ResumeAtlas produced 35 single-column templates as both PDF and Word and parsed both with its own analyzer: 35/35 pairs reached the same verdict, same sections, same contact fields, median score 88 vs 88 (own parser, single-column only; VERIFIED-SECONDARY, weak generality). UnchartedCareer's extractor test found PDFs lost 19.9% of field reads overall vs 0% for Word, but "almost all of the PDF loss came from the hard layouts... a clean single-column text-based PDF lost nothing" (VERIFIED-SECONDARY with reservations). Resume Genius's 1,000-hiring-manager survey: 53% call text-based PDFs compatible with their systems, 43% Word, 34% lightly designed PDFs, 13% design-heavy resumes (this measures manager belief, not parser behavior).

**What actually fails**: image-only or scanned PDFs (Lever: cannot parse; Greenhouse: "uploaded as an image"; Textkernel and Daxtra treat OCR as an add-on that the ATS may not have licensed); letter-spaced headings (MyResumeKit found two of its own paid templates scoring 45/100 because `letterSpacing: 1.5` made "EXPERIENCE" extract as "E X P E R I E N C E"; fixed by reducing tracking to 0.8); fonts whose glyphs map to wrong Unicode (UnchartedCareer: 20.8% loss with an unusual embedded font; also asserted by two other sources); oversized files (Greenhouse's 2.5 MB parse limit; typical Workday 5 MB caps). The claim that Canva/InDesign/Figma exports "store text as vector paths" is ASSERTED by one marketing page and not verified; the actionable version is simply "check that text is selectable".

**The DOCX-for-Workday folklore**: several guides and Reddit posts say `.docx` autofills more reliably in older Workday tenants. This is ASSERTED (no test found); Workday's HiredScore documentation accepts both. A `.docx` twin costs nothing to keep.

**Verdict** (*almost certain*): folklore inherited from the Taleo era. A text-based PDF exported from Word, Google Docs or LaTeX is accepted and parsed everywhere that matters in 2026.

**For this owner**: default to a text-based PDF under 1 MB (far below Greenhouse's 2.5 MB parse limit and Workday's usual 5 MB cap); keep an identical `.docx` for portals that ask; never a scan or image; confirm text is selectable.

### 3.3 "Headers and footers are dropped"

**Vendor-documented** (VERIFIED-PRIMARY): Greenhouse names "name and contact information in the header, footer, or text box" and "complex resumes with tables, headers, and footers" as parse-failure causes; SmartRecruiters' glossary says "Avoid headers and footers". These are the only two dominant vendors that mention it; both state it as advice, neither publishes a measurement.

**Mechanism** (VERIFIED-PRIMARY for the library behavior, INFERRED for the consequence): in a `.docx`, header and footer text lives in separate XML parts linked to a section, not in the document body (python-docx documentation: headers are section-level "story" containers edited separately from `Document`). Extractors differ: Apache Tika includes headers by default (users file tickets asking how to skip them, e.g. TIKA-2362, 2019), while body-only extraction paths omit them (the docx2python library exists to recover "headers, footers, footnotes" that plain extraction misses). A PDF has no header concept: the text is on the page and extracts, but it repeats once per page. ATSVerification measured exactly that: contact placed in a running header was extracted three times; its further claim that "some ATS engines deliberately skip header and footer regions as boilerplate" is ASSERTED. UnchartedCareer's extractor test reports contact-in-header and contact-in-footer each lost 25% of field reads (VERIFIED-SECONDARY with reservations).

**Verdict** (*highly likely*): real for Word headers/footers in some pipelines, a minor duplication issue for PDFs, and in every case a risk that is free to eliminate.

**For this owner**: put name, city, email, phone, GitHub and LinkedIn as ordinary body text at the top of page one. No Word header/footer, no text box, no repeated page header.

### 3.4 "Icons and graphics destroy parsing"

**Vendor-documented** (VERIFIED-PRIMARY): Greenhouse lists "graphics, photos, or word art" and image uploads as failure causes and will not parse files over 2.5 MB (images are what push a resume over it); Lever cannot parse image files; Textkernel/Daxtra parse images only through OCR add-ons; iCIMS says modern systems tolerate pictures and colored fonts but still recommends simple formatting.

**Measured**: MyResumeKit's 13-template test (VERIFIED-SECONDARY): the icon- and progress-bar-heavy infographic template was the worst of all 13 (37/40 on the two engines); the sidebar-with-photo-and-contact-icons template failed to recover the email address on both engines; the full-width graphical photo header template lost the phone number and recovered zero experience entries on both engines. Enhancv's job-board dashboard test found icons for LinkedIn and GitHub in a stylized header did not stop contact extraction. An anonymous r/resumes poster who says they parse resumes professionally reports that typed pipes and hyphens extract fine but a thin line drawn as a shape "extracts as nothing, so the words on either side glue together" (ASSERTED; only comment fragments retrievable). A German recruiting-firm director quoted by Enhancv: "What actually breaks machines today is text trapped in images, icons used instead of headings, and contact details hidden in the header" (ASSERTED, practitioner).

**Human side**: Ladders 2012 found recruiters "fixated for an average 19% of the total time spent on profile pictures" and that visual elements "reduced recruiters' analytical capability"; Resume Genius 2026: 62% of hiring managers say "overly designed resumes with lots of color or visual elements hurt their perception"; Gergely Orosz (Uber/Skyscanner hiring manager) advises no photo to avoid bias.

**Verdict** (*highly likely*): "destroy" is folklore; the true mechanism is narrower. An icon that *replaces* a word (an envelope glyph instead of "Email", a GitHub glyph instead of the URL label) removes that label from the text; skill bars and charts carry no text at all; large images inflate file size past parse limits; a photo adds bias risk and, per Greenhouse, can contribute to parse failure. Decorative icons next to real text usually cost nothing on modern extractors, but they buy nothing either.

**For this owner**: no icons, no skill bars, no charts, no photo in the default (US/UK/tech) version; write "GitHub: github.com/Prekzursil" and "LinkedIn: linkedin.com/in/andrei-mihai-visalon-03141b170" as plain text. (Photo for the Romanian local market is discussed in section 6.)

### 3.5 "Tables scramble the parse"

**Vendor-documented** (VERIFIED-PRIMARY): Greenhouse: "Complex resumes with tables"; SmartRecruiters: "Avoid tables and columns"; Affinda (a parsing vendor): tabular group fields "are tricky for the model" and "often need custom configuration". A secondary research note claims Lever's table parsing is "inconsistent... depending on how the table was constructed" (ASSERTED).

**Measured**: ATSVerification's skills-as-a-table/grid variant parsed 100/100 with no flags under pdf.js; UnchartedCareer reports work history "crammed into a bordered table" lost 12.5% of field reads. The Resumap test's diagnosis applies directly: in a PDF a table is just positioned text, so a two-column layout table has the same reading-order risk as columns; in a `.docx`, tables extract cell by cell in row order, so anything laid out as side-by-side cells interleaves. Drawn borders are shapes and vanish (r/resumes fragment). The classic Workday complaint, dates in a right-hand table column landing on the wrong job, is ASSERTED by a Workday-troubleshooting page but is exactly what row-major extraction predicts.

**Verdict** (*likely*): layout tables (used to position columns, or to put dates beside titles) carry the same risk as columns; a simple one-row skills grid with real text usually parses fine; the safe form costs nothing.

**For this owner**: no tables at all. Each role or project: title line, then organization and dates on the same or next line, then bullets. Skills as plain lines separated by commas or typed pipes.

### 3.6 "Recruiters spend six seconds on a resume"

**Origin, read from the primary documents** (VERIFIED-PRIMARY):

- 2012: Ladders' summary "Keeping an eye on recruiter behavior" (footnoted to an internal report: *Eye Tracking Online Metacognition: Cognitive Complexity and Recruiter Decision Making*, Will Evans, Head of User Experience Design, TheLadders, 2012). "Thirty professional recruiters took part in the study during a 10-week period." The study's stated purposes were to test whether professionally rewritten resumes (Ladders sold rewrites) were processed differently, to check recruiters' self-reports that they spend "as much as 4 to 5 minutes per resume", and to compare Ladders' profiles with LinkedIn's. It found "recruiters spend only 6 seconds reviewing an individual resume" for the initial fit/no-fit decision, that almost 80% of that time went to six data points (name, current title/company, current position dates, previous title/company, previous dates, education), and it closed with "Key recommendations: Turn to a professional for resume rewrites... it makes sense to follow the style found on TheLadders.com."
- 2018 update (Ladders PDF, methodology paragraph): a two-stage design, a timed stage where recruiters "who were not aware they were being timed" reviewed a stack, and a lab eye-tracking stage; average initial screen "7.4 seconds"; the number of recruiters is not disclosed. It attributes the 2012 figure partly to recession-era application volume. Layout findings reported by HR Dive: simple layouts with clear section headings, E/F reading pattern, bold titles and bullets did well; cluttered layouts, no white space, multiple columns, long sentences and missing headers did poorly.

**Independent status**: never peer-reviewed; the eye-tracking hardware, the resumes, the job specs and the 2018 sample size are not published; the sponsor sold the recommended remedy. Practitioner critiques on those exact grounds: Distinct Recruitment ("The 6-second CV: Recruitment's biggest myth"), Spectacle Talent Partners, Quantum Tech Resumes, and a recruiter's LinkedIn essay. No peer-reviewed replication of a 6-7 second screen was found in the academic index searched; the closest academic eye-tracking work (Lahey & Oxley 2021, *Journal of Policy Analysis and Management*, 152 student participants, not recruiters) reports top-to-bottom viewing patterns and studies discrimination, not seconds per resume.

**Other measurements point elsewhere**: ResumeGo's 2018 simulation (482 recruiters, hiring managers, HR professionals and executives, Oct 15-Nov 2, 2018) recorded 2 minutes 24 seconds per one-page resume and 4 minutes 5 seconds per two-page resume (a different task: a deliberate shortlist, not a first glance); Novoresume's 2026 HR survey: 74% "skim a resume in 20 seconds or less" (self-report); Enhancv's 25 recruiters: "minutes—sometimes seconds".

**Verdict** (*highly likely*): the specific number is measured once, by a vendor, with n=30 in 2012 and an undisclosed n in 2018, and has not been independently replicated; it is a marketing statistic that hardened into a rule. The qualitative finding that survived every source, including the human-side data in every survey above, is robust: the first pass is fast and reads the top-left, the headings, titles, organizations, dates and education. Design for that pass without treating "six seconds" as a measured constraint.

**For this owner**: the six data points recruiters were measured looking at map onto: name; the target title (e.g. "Software Engineer" or "Junior Backend Engineer"); University of Bucharest, BSc Computer Science, 2022-2025; the most recent role or project with dates; skills. All of these belong in the top third of page one.

### 3.7 Related claims worth settling

- **"75% of resumes are never seen by a human / are rejected by the ATS."** Traced by HiringThing and a recruiter who investigated it to a defunct vendor's marketing claim; no dataset exists. The number usually cited as support is HBS's 88%, which is executives *agreeing* that qualified candidates get vetted out by rigid criteria, not a rejection rate, and HBS blames configured filters (degree proxies, exact skills, gaps), not parsing. (VERIFIED-PRIMARY for HBS; the 75% is ASSERTED.)
- **"There is an ATS score you must pass."** No vendor publishes a universal percentage; Greenhouse uses five qualitative tiers, Workday HiredScore letter grades, Ashby per-criterion outcomes plus an optional criteria-met percentage. Third-party "ATS score" tools score against their own rules; an ex-Google recruiter (Farah Sharghi, 2025) and Huntr's 2026 write-up both say no employer sees those numbers. (VERIFIED-PRIMARY for vendor mechanisms.)
- **"Hide keywords in white text."** Parsed text ignores color; recruiters see the block in the extracted text and Greenhouse has fake-data detection; every practitioner source calls it self-sabotage. (ASSERTED by multiple independent practitioners; mechanism VERIFIED.)
- **"Creative section headings break parsing."** ATSVerification flagged missing standard headings; UnchartedCareer found renamed headings cost nothing; Greenhouse lists "no clear sections". Mixed evidence; standard headings are free. (Contested.)
- **"Keyword stuffing raises your rank."** Skills extraction is "bag-of-words-ish" (Resumap), so presence matters, but repetition adds nothing in embedding or LLM scoring layers and recruiters read it as spam (Greenhouse's Talent Matching highlights exact and semantically similar matches; Workday Skills Cloud normalizes synonyms). Use each exact term from the posting once in a skills line and once in context.

---

## 4. Length

Evidence, in descending order of strength:

- ResumeGo 2018 simulated screening (VERIFIED-PRIMARY page; commercial author): of 7,712 resume selections, 5,375 were two-page, i.e. reviewers were 2.3x as likely to pick two-page over one-page overall; 1.4x for entry-level, 2.6x mid-level, 2.9x managerial; two-page resumes scored 8.6 vs 7.1. Important confound: the two-page resumes contained 700-850 words vs 350-500, so the study cannot separate "more pages" from "more substance".
- Resume Genius 2026 (n=1,000 US hiring managers): 43% "won't read resumes longer than two pages", 57% "will read beyond two pages when the information is relevant"; "resume too long or dense" is a rejection trigger for 20%.
- Novoresume 2026 HR survey: 68.5% prefer two pages, 21.7% one page; but "resumes that are too long" was a recurring pet peeve (sample size not retrieved).
- Enhancv's 25 recruiters: 64% volunteered "one to two pages maximum".
- Google technical recruiters (Life at Google video "Create Your Resume for Google"): "keep your resume to one page for business and internship roles and no longer than two pages for engineering roles" (VERIFIED-PRIMARY transcript).
- Gergely Orosz (hiring manager at Uber/Skyscanner, interviewed two dozen big-tech recruiters for *The Tech Resume Inside Out*): "in most of the US, a one-page resume is the norm for developers with less than a few years' experience... In most of Europe, resumes of two pages are common, and some hiring managers actually prefer to read longer resumes for senior people."
- New-grad-specific guides (techinterview.org, April 2026; InterviewChamp, May 2026): one page for anyone under about three years of experience; recruiters they interviewed read a second page as a failure to edit (ASSERTED by the authors on recruiters' behalf).
- Romania: eJobs' own model-CV guidance: "Păstrează CV-ul în 1-2 pagini" (keep the CV to 1-2 pages) and keep a detailed version to send on request; CVmaker.ro: one page for recent graduates and entry-level, two for experienced specialists.
- No dominant vendor documents a page cap; claims that Taleo truncates at ~2 pages and iCIMS at ~3 pages of extracted text come from one marketing page (ASSERTED).

**Verdict** (*highly likely*): for a 2025 graduate with no full-time experience, one full page is the convention in US/UK tech hiring and what Google's and big-tech recruiters state; a well-filled second page is not penalized by most hiring managers and is normal in Europe; a page and a half is the one length every source dislikes. The "two pages beat one" data comes from candidates with more content to show.

**For this owner**: build a dense single page (Education, Skills, 1-3 experiences if any, 3-5 best projects from the 68 repos). Allow a second page only when internships or shipped projects genuinely fill it; never leave a page half empty. Keep a longer "master" version for tailoring.

---

## 5. Section order and content for a 2025 CS graduate

Sources agree on the principle "strongest signal first":

- Google recruiters: list programming languages at the top; include a GitHub profile or prominent open-source work; use clearly delineated sections; experience takes the bulk; then personal or class projects; then leadership and awards; reverse chronological with month-year dates; bullets in "Accomplished [X] as measured by [Y] by doing [Z]" form; read the job description and bold matching keywords.
- Orosz (new grads and bootcamp grads, in order of what hiring managers care about): real-world experience including internships; contributions to real-world projects (open source); education details; standout projects; tutoring and leadership. Have a "languages and technologies" section on page one; weave technologies into bullets; keep the template top-to-bottom, similar to LinkedIn's; no photo; drop personal details.
- techinterview.org (2026): education leads only while it is the strongest signal (GPA 3.5+, named relevant courses, thesis); once there is a recognizable internship, experience leads; projects can substitute for internships if they show depth or adoption; cut objective statements, high-school data, generic class projects. IGotAnOffer (2024): "if you've just graduated... Google recommends starting with your education section". CS Dojo (Google engineer): "list whichever one's more impressive/relevant".
- Resume Genius 2026: 85% of hiring managers expect a skills section; 90% say a clear summary helps them evaluate faster; 56% say skills-heavy resumes that downplay work history are harder to evaluate.

**Recommended structure for this owner** (INFERRED from the above; *likely* the best default):

1. Header (body text): Andrei Mihai Visalon; Bucharest, Romania; one email (the institutional `@s.unibuc.ro` address signals current affiliation but will expire, so prefer the personal Gmail or list both); phone with +40; LinkedIn URL; GitHub URL. Omit ORCID on an engineering resume while it lists zero works; add it only on academic/research applications.
2. Optional 2-3 line summary naming the target role and the two or three strongest technical facts (skip a generic objective).
3. Education: Universitatea din București, Faculty of Mathematics and Informatics, BSc Computer Science, 2022-2025; thesis title; 4-6 named relevant courses (Operating Systems, Algorithms, Databases, Distributed Systems, ML, etc.); GPA only if strong on the 10-point scale and explained ("9.1/10").
4. Skills: languages, frameworks, tools, cloud, grouped on three or four plain lines, using the posting's exact terms.
5. Experience: internships, freelance, research assistantships, if any; 3-5 bullets each with a metric.
6. Projects: 3-5 of the 68 repositories with a one-line description, stack, and a measured outcome (users, stars, latency, coverage, data volume), each with a plain-text link. Prefer depth and adoption over count.
7. Optional: competitions, hackathons, open-source contributions, publications, leadership.

Use the headings **Education, Experience, Projects, Skills** verbatim (every parser and every source recognizes them). Reverse chronological within sections; dates as "Oct 2022 – Jul 2025" consistently.

---

## 6. Regional layer: Romania and the EU

- **Photo**: eJobs (the largest Romanian job board) advises a recent portrait in office-casual clothing on a neutral background for its CV model (VERIFIED-PRIMARY); Resumly's Romania page and VisualCV say a photo is common and accepted but never mandatory, and that multinationals increasingly prefer none (ASSERTED, consistent); a EURES-derived country table says a photo is "not necessary, unless the employer mentions it" for Romania (dated); US/UK tech guidance (Orosz; Google recruiters' format advice) is no photo; Resume Genius's US managers split 55/45. Verdict (*likely*): keep the default version photo-free for any ATS-fronted or non-Romanian employer; a second, photo-bearing variant is acceptable for Romanian local employers who expect one, and is a choice, not a requirement.
- **Personal data**: omit CNP, ID/passport numbers, full street address, date of birth, marital status, religion (Resumly's Romania guidance; also data minimization under GDPR, INFERRED). Age and gender are exactly the "irrelevant data" the 2012 eye-tracking report said biased reviewers.
- **Europass**: recognized and sometimes required in Romanian public-sector, academic and EU-funded roles; not preferred for IT and multinationals (Resumly; Enhancv 2026; the EURES table). Keep one on file; do not lead with it.
- **Language and dates**: English for IT, BPO and multinationals, Romanian for public-sector employers (Resumly; Academia Programatorilor); Romanian convention is DD.MM.YYYY, but month-year in English is fine and safer for parsers.
- **Paper size**: A4 for European applications, US Letter for US ones (ASSERTED convention; harmless to keep two exports).
- **EU AI Act** (VERIFIED-PRIMARY, European Commission page and Regulation (EU) 2026/1744): AI "for recruitment or selection... to analyse and filter job applications, and evaluate candidates" is Annex III high-risk. The Digital Omnibus (published OJ 24 July 2026, in force 27 July 2026) moved the stand-alone high-risk obligations to **2 December 2027** (Annex I embedded systems to 2 August 2028); Article 50 transparency obligations applied on schedule from **2 August 2026**. Deployers who are employers must inform candidates that a high-risk AI system is used; the Act applies extraterritorially when the affected person is in the EU. Pure field extraction (parsing) is generally outside the high-risk line; match scores and ranking are inside it (Praxikon's reading of the May 2026 Commission draft guidelines). Practical effect for a Romanian applicant: expect AI disclosures on job posts, and note that Greenhouse already lets candidates opt out of AI processing per application (opted-out candidates are labeled "Needs manual review" and are never auto-rejected).
- **Mobley v. Workday** (N.D. Cal., No. 23-cv-00770; VERIFIED-SECONDARY via law-firm and legal-press coverage): the first vendor-targeted AI-screening suit; a nationwide ADEA collective of applicants 40+ was preliminarily certified in May 2025 (HiredScore-screened applicants included); on 22 June 2026 the court largely denied Workday's motion to dismiss the Third Amended Complaint; class-certification hearing set for 9 March 2027; no finding of discrimination to date. Relevance: it documents that Workday tenants using HiredScore score, rank and screen resumes before a human looks, and that "proxy" features such as employment gaps are the contested mechanism, echoing HBS's gap-filter finding.

---

## 7. Consolidated: what genuinely breaks parsing in 2026 versus what is folklore

| Item | Status | Evidence grade |
|---|---|---|
| Resume saved as an image / scanned PDF | Breaks parsing everywhere without OCR; Greenhouse, Lever say so | VERIFIED-PRIMARY |
| File over the parser cap (Greenhouse 2.5 MB; typical Workday 5 MB) | Uploads but is never parsed | VERIFIED-PRIMARY |
| Contact details only in a Word header/footer or text box | Named by Greenhouse and SmartRecruiters; extractor-dependent for DOCX; duplication for PDF | VERIFIED-PRIMARY (advice) + mechanism |
| Letter-spaced or outlined headings, fonts with bad Unicode mapping | Section detection fails; measured 45/100 vs 89/100 | VERIFIED-SECONDARY |
| Sidebar/two-column with interleaved text stream | Scrambles reading order, segmentation and employer attribution; not contact details | VERIFIED-SECONDARY (4 tests) |
| Layout tables, dates in a side column | Same reading-order risk; row-major extraction in DOCX | VERIFIED-PRIMARY (advice) + mechanism |
| Icons replacing labels, skill bars, charts, drawn lines | The replaced text simply does not exist | VERIFIED-SECONDARY + practitioner |
| Non-standard section headings | Mixed results; standard headings are free | Contested |
| Photo | Parse risk per Greenhouse; bias risk per recruiters; local convention in Romania | Mixed |
| Two columns with a clean column-by-column text stream | Parses like one column on most extractors | VERIFIED-SECONDARY |
| PDF file type | Accepted everywhere; not a failure cause | VERIFIED-PRIMARY |
| Em dashes, curly quotes, simple skills grids | Did not break | VERIFIED-SECONDARY (single test) |
| "Six-second scan" as a hard constraint | Single vendor study, n=30, unreplicated | Folklore-grade number, valid qualitative lesson |
| "75% auto-rejected by ATS" | No source; HBS says >90% filter/rank on configured criteria, ~half auto-screen 6-month gaps | Folklore; the real filter is knockout questions and requirements |

---

## 8. Pre-submit checklist for this owner (concrete, ordered)

1. One column; A4 export for EU/Romania, Letter export for US; 10.5-11 pt body in a standard font (Calibri, Arial, Georgia, or a LaTeX default); margins 0.5-0.75 in; no letter-spacing on headings.
2. Name and contact as body text on line one; no header/footer, no text box, no icons, no photo in the default version.
3. Headings exactly: Education, Experience, Projects, Skills (plus an optional Summary). Reverse chronological. Dates "Mon YYYY – Mon YYYY", consistent everywhere.
4. Full organization names ("Universitatea din București" / "University of Bucharest"; company names with their legal suffix where natural, e.g. "S.R.L." or "Inc.", since Greenhouse's parser looks for such markers) and full job titles.
5. Every project or role bullet in "did X, measured by Y, by doing Z" form with a number; the posting's exact technology names appear once in Skills and once in context.
6. Export a text-based PDF from Word, Google Docs or LaTeX; check that text is selectable; run `pdftotext -layout` and confirm top-to-bottom order; keep the file well under 1 MB; keep a `.docx` twin.
7. File name `Andrei-Mihai-Visalon-CV.pdf` (or `-Resume` for US postings); harmless convention, occasionally requested.
8. In every application, answer knockout questions accurately (work authorization: EU citizen for EU roles; for US or UK roles the sponsorship question is the real automated filter); after Workday's "Autofill with Resume", review every pre-filled field before submitting, because the parse is a draft and the record cannot be edited afterward.
9. Tailor per posting from a master file; put the most role-relevant project first.
10. Do not pay for or chase an "ATS score"; no employer sees it.

---

## 9. Source register (with grade and what each was used for)

Vendor documentation (VERIFIED-PRIMARY):
- Greenhouse Support, "Supported formats for resumes, cover letters and other candidate uploads" (article 360052218132) — formats, 100 MB, external images.
- Greenhouse Support, "Unsuccessful resume parse" (article 200989175) — 2.5 MB parse limit, formatting failure list, failed-parse behavior.
- Greenhouse Support, "Talent Matching FAQ" (article 41131886674075) and "Talent Matching setup" (article 48563080657435); greenhouse.com "Real Talent" — no auto-reject, candidate AI opt-out.
- Greenhouse Support, "Resume parsing with non-English languages" (article 205019689) — Romanian supported.
- Lever Help Center, "Understanding resume parsing" (article 20087345054749, updated July 23, 2025) — image files unparseable, highlight test (file list not retrievable).
- Workday HiredScore documentation PDF (doc.workday.com) — grades A-D, supported formats DOC/DOCX/PDF/RTF/TXT, no-grade conditions.
- Oracle Help Center, Taleo Enterprise 21B "Candidate Management"; Taleo Business Edition 24A "Resumes in Image Formats".
- SmartRecruiters glossary "Resume parsing"; SmartRecruiters Candidate Privacy Policy (27 March 2020) naming Textkernel.
- Textkernel product and developer pages (parser formats, multi-column, OCR, languages).
- iCIMS glossary "Your complete guide to applicant tracking systems".
- Ashby Knowledge Base: "AI-Assisted Application Review", "AI features in Ashby" (enhanced resume parsing), "Application Review"; Ashby product update (Sept 10, 2024); Ashby Bias Audit (Aug 2024).
- Workable Help, "What types of files can be uploaded on the application form?".
- Daxtra Parser (CVX) Technical Specifications; RChilli Resume Parser docs; Sovren technical specs; Affinda schema-design handbook.
- Jobs.wisc.edu Workday FAQ (tenant upload formats).
- python-docx documentation, "Working with Headers and Footers"; Apache Tika JIRA TIKA-2362.

Primary research reports (VERIFIED-PRIMARY):
- Fuller, Raman, Sage-Gavin, Hines et al., *Hidden Workers: Untapped Talent*, HBS Project on Managing the Future of Work and Accenture, Sept 2021 (PDF read directly).
- Ladders, "Keeping an eye on recruiter behavior" (2012 summary, PDF read directly) and *Eye-Tracking Study 2018* (PDF methodology paragraph; PR Newswire release Nov 6, 2018; HR Dive summary Nov 8, 2018).
- ResumeGo, "Settling the Debate: One or Two Page Resumes" (2018).
- Resume Genius, *2026 Hiring Insights Report* (1,000 US hiring managers, Pollfish).
- European Commission, "AI Act | Shaping Europe's digital future" (timeline incl. 2 Dec 2027); Jobiqo on Regulation (EU) 2026/1744; Eversheds Sutherland (Mar 9, 2026); Praxikon (Apr 22, 2026); Mickai (Jul 21, 2026); Confir.
- Jobscan, *2026 ATS Usage Report*; Apps Run The World, Top 10 ATS vendors 2024; Pin, *2026 ATS Market Share Report*.
- Google, "Create Your Resume for Google: Tips and Advice" (Life at Google, YouTube; transcript via Exa).

Independent measurements with published methods (VERIFIED-SECONDARY; all authored by resume-tool companies):
- Resumap, "We ran the same resume through 4 real ATS parsers in 36 layouts" (dev.to, Jul 28, 2026).
- Enhancv, "What Happens to a Two-Column Resume When a Machine Reads It" (Aug 24 / Sept 16, 2026; 357 runs) and "Does ATS Parse Creative Resumes in the World's Biggest Job Board?".
- ATSVerification, "ATS Parsing Benchmark 2026" (Jun 30, 2026).
- MyResumeKit, "We Tested 13 Resume Templates Through Real ATS Parsers" (Aug 2 / Aug 27, 2026).
- ResumeAtlas, "Can an ATS Read a Two-Column Resume?" (213 resumes, 35 PDF/DOCX pairs, Sept 2026; own analyzer).
- UnchartedCareer, "How an ATS actually reads your resume" (Jul 4, 2026; extractor test, method partially retrieved).
- Enhancv, "Does the ATS Reject Your Resume? 25 Recruiters Explain" (Nov 3, 2025).

Practitioner accounts (graded individually in text): Gergely Orosz (Stack Overflow blog Nov 25, 2020; dev.to Dec 1, 2020; thetechresume.com); Farah Sharghi, ex-Google recruiter (video, Jun 25, 2025); Huntr with Amazon recruiter Kristen Fife (Apr 13, 2026); HiringThing; Distinct Recruitment; Spectacle Talent Partners; Quantum Tech Resumes; WunderJob (Apr 21, 2026); r/resumes thread fragments (2026); techinterview.org (Apr 26, 2026); InterviewChamp (May 19, 2026); IGotAnOffer (Dec 9, 2024); CS Dojo (2018); Novoresume/Andrei Kurtuy (LinkedIn, 2026).

Romania: eJobs "Model CV 2026" (cariera.ejobs.ro/model-cv); Resumly "AI Resume Builder for Romania"; Academia Programatorilor "Cum să pregătești un CV perfect pentru interviuri IT... 2026"; CVmaker.ro; Jobseeker.com/ro; studentnews.eu EURES-derived country table; Mingle blog (Jun 2026); SAP Romania SmartRecruiters page; eJobs integrations page.

Legal: Duane Morris (Jun 24, 2026), Mondaq (Jul 9, 2026), Law360 (Sep 15, 2026), Lawyer Monthly (Sep 21, 2026), FindLaw (Jul 12, 2024 order) on Mobley v. Workday.

Academic (Scholar Gateway, Wiley corpus): Lahey & Oxley 2021 (DOI 10.1002/pam.22281); Sachs, Homan & Lancee 2024 (DOI 10.1111/jasp.13047); Derous, Ryan & Nguyen 2011 (DOI 10.1002/job.769); Dutta & Naveen 2025 (DOI 10.1002/hrm.70018). None reports a seconds-per-resume screening time; none replicates Ladders.

Marketing pages cited only as examples of the folklore or as ASSERTED claims: QuickResumeAI, Jobaholic, ResumeOptimizerPro, ResumeAdapter, iReformat, Resumly (ATS guides), Scale.jobs, Jobloo, QuickCV, AI Applyd, ResumeBold, CVder, HireFlow, NeuraCV, JobWizard, CVPilot, CVboosta, StylingCV, ResuAI, ATSGrader, Hirecarta, HeroHunt, sunnypatell/ats-screener research notes.

---

## 10. Limitations

- No test in this evidence base logs into a production Workday, Greenhouse, Lever or Ashby tenant and publishes the field-level diff; the four transparent tests used Zoho, Workable, Manatal, Textkernel, open-source extractors, or the authors' own pipelines. Claims about a specific ATS's parser therefore rest on vendor docs plus mechanism, not on direct measurement.
- Every layout experiment was run by a company that sells resume tooling; their incentives differ (Enhancv sells two-column templates; ATSVerification and MyResumeKit sell checkers) and the conclusions partially offset each other, which is why the synthesis leans on where they agree.
- Lever's exact accepted-format list, Workday's own parsing help text and the full r/resumes thread could not be retrieved.
- Romanian-market conventions rest on job-board and vendor pages, not on a survey of Romanian recruiters.
