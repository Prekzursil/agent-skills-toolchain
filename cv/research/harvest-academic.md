# Academic and research position — harvest (2026-09-23)

Owner: Andrei Mihai Visalon. ORCID 0009-0001-8776-8498. University of Bucharest.
Every claim below is tagged VERIFIED (checked against a named source this session), INFERRED (my reading of verified facts), or UNVERIFIED (asserted somewhere but not confirmable).

Sources used: pub.orcid.org API (record, /works, /educations), OpenAlex API, Crossref REST, DataCite REST, Zenodo REST, arXiv API, Europe PMC REST, Semantic Scholar API, Google Scholar (web), GitHub REST API (repos, commits, trees, search, raw files), Codabench API, IberLEF 2026 site, LinguistList, CEUR-WS index, medRxiv/bioRxiv APIs, the vault at D:\basic-memory (read-only), the auto-memory dir C:\Users\prekzursil\.claude\projects\C--Users-prekzursil\memory\, and a narrowly scoped search of the owner's own Gmail for ORCID/Zenodo/Kaggle/IberLEF notifications (only the owner's own service notifications were used; unrelated third-party mail present in that inbox was ignored and is not reported).

Local working directories that the vault references (D:\Research\projects\phenibut\..., C:\Users\Prekzursil\Downloads\bionlp\) do NOT exist on this restored machine. No manuscript file (PAPER_1_DRAFT, PAPER_B_DRAFT, main.tex) is on disk here. Everything about draft contents comes from vault notes; everything about published output comes from public registries.

---

## 1. Verification ledger

| # | Check | Method / source | Result | Tag |
|---|-------|-----------------|--------|-----|
| 1 | ORCID record contents | GET https://pub.orcid.org/v3.0/0009-0001-8776-8498/record | Names Andrei / Visalon; country RO; public verified email andrei-mihai.visalon@s.unibuc.ro; researcher URLs = LinkedIn (linkedin.com/in/andrei-mihai-visalon-03141b170) + GitHub (github.com/Prekzursil); employment none; funding none; peer review none; keywords none; record created 2025-08-14; last modified 2026-07-21 | VERIFIED |
| 2 | ORCID works | GET .../works | activities:works element EMPTY = zero works | VERIFIED |
| 3 | ORCID education | GET .../educations | University of Bucharest, Bucharest RO, dept "Computer Science", role "Bachelor's in Computer Science", 2022-10-01 to 2025-06-04; source = "Andrei Visalon" (record holder, self-asserted, NOT institution-asserted); put-code 36830605; created and last-modified 2026-05-31T09:22:00Z; visibility public | VERIFIED |
| 4 | ORCID timeline (owner's own notification mail) | Gmail, sender notify/verify.orcid.org | Welcome/creation 2025-08-14; "Add Research Outputs" reminders 2025-08-21, 2025-09-11, 2025-11-12; password reset 2025-12-11; email-change (institutional address added) 2026-05-31; NEW 2026-09-23 10:32 UTC: Crossref auto-update permission request pending in the ORCID inbox for DOI 10.26434/chemrxiv.15009306/v1 ("Grant permissions" not yet actioned) | VERIFIED |
| 5 | OpenAlex author | filter orcid:0009-0001-8776-8498 | TWO author records carry the ORCID: A5151992415 (created 2026-09-18) and A5152109704 (created 2026-09-19), both "Andrei Mihai Visalon", affiliation University of Bucharest (I141595442, ROR 02x2v6p15) 2026, works 2 each (4 total, all Zenodo dataset DOIs), 0 citations, h-index 0. Author record is SPLIT (OpenAlex artefact) | VERIFIED |
| 6 | OpenAlex works | filter author.id | W7213502136 (10.5281/zenodo.22819600), W7213529252 (…22819601), W7213610604 (…22836690), W7213610871 (…22836832); all type dataset, OA green, cc-by, raw affiliation "University of Bucharest, Faculty of Mathematics and Informatics", corresponding=true | VERIFIED |
| 7 | Crossref author search "Visalon" | crossref search_works query_author | 9 items; 8 are by Ioana / Ioana Octavia Visalon (theatre & voice studies, "Dunarea de Jos" Univ. Galati; DOIs 10.35219/cercetarte.*, 10.37130/*) = a DIFFERENT PERSON, never conflate; 1 is his: 10.26434/chemrxiv.15009306/v1 (posted-content) | VERIFIED |
| 8 | Crossref record of the preprint | GET https://api.crossref.org/works/10.26434/chemrxiv.15009306/v1 | Title "Computational corroboration, at the sign level, that R-phenibut is the GABA-B eutomer: a two-sided alchemical transfer free-energy validation"; sole author Andrei Mihai Visalon, ORCID 0009-0001-8776-8498, affiliation "Faculty of Mathematics and Computer Science, University of Bucharest, Bucharest, Romania"; subtype preprint; posted 2026-09-22; created/deposited 2026-09-23T05:39:42Z; indexed 2026-09-23T06:09:27Z; publisher American Chemical Society (ChemRxiv / Cambridge Open Engage); no license field; no relation (no journal VOR); full-text URL https://chemrxiv.org/doi/full/10.26434/chemrxiv.15009306/v1, PDF …/doi/pdf/… | VERIFIED |
| 9 | ChemRxiv landing page | chemrxiv.org (WebFetch + UA request + public API) | HTTP 403 (Cloudflare) on every route; license, categories, view/download counts NOT retrievable this session | UNVERIFIED (blocked) |
| 10 | Zenodo deposit | GET zenodo.org/api/records/22836832 and /22819601; DataCite query creators.name:*Visalon* | Concept DOI 10.5281/zenodo.22819600 (created 2026-09-17); v1 10.5281/zenodo.22819601 (2026-09-17T21:18:47Z, phenibut_deposit_2026-09-17.zip 21.9 MB); v2 10.5281/zenodo.22836690 (2026-09-18); v3 10.5281/zenodo.22836832 (2026-09-18T19:25:18Z, phenibut_deposit_2026-09-18_v3.zip 35.5 MB, MD5 3501eeacf141c955eb9626a4135f72e4); CC-BY-4.0, open; creator "Visalon, Andrei Mihai", affiliation "University of Bucharest, Faculty of Mathematics and Informatics", ORCID; resource type Dataset; keywords: alchemical free energy, relative binding free energy, Alchemical Transfer Method, GABA-B receptor, phenibut, enantioselectivity, eutomer, KCTD16, KCTD12, Mendelian randomization, colocalization, FAERS, pharmacovigilance, reproducibility, negative result; v3 stats 11 views / 2 downloads; DataCite total = 4 DOIs, all his | VERIFIED |
| 11 | Zenodo description (v1, verbatim gist) | same | "Supporting data and code for two manuscripts by Andrei Mihai Visalon (University of Bucharest)." Paper A: ATM free energies for phenibut enantiomers at GABA-B across three independent seeds, R-phenibut = eutomer, magnitude not claimed; same protocol applied to alpha2delta-1 where it fails, with full reporting. Paper B: KCTD16 Mendelian randomization significant in FinnGen but "does not replicate outside Finland", plus bias-aware FAERS disproportionality. Archive re-derives free energies via scripts/verify_deposit_selfsufficient.py to within 0.0004 kcal/mol. Manuscript status (submitted/accepted) NOT stated | VERIFIED |
| 12 | arXiv | au:Visalon | 0 results | VERIFIED |
| 13 | Europe PMC | AUTH:"Visalon" | hitCount 0 (note: ChemRxiv item posted 2026-09-22 is not yet ingested; lag expected) | VERIFIED |
| 14 | Semantic Scholar | author search "Visalon" | only "I. Visalon" (9 papers, theatre studies); no Andrei | VERIFIED |
| 15 | DBLP | author search API | no hit (site fronted by Anubis anti-bot; API returned nothing relevant) | VERIFIED (weak) |
| 16 | Google Scholar | scholar?q="Visalon"+phenibut | "did not match any articles" (0); author-profile search requires Google login | VERIFIED (0 as of today) |
| 17 | medRxiv / bioRxiv | details API 2026-09-15..23 (medRxiv, page 1 of 483) and 2026-09-21..23 (bioRxiv, page 1 of 720) | no Visalon / phenibut / KCTD / FAERS item on the fetched pages; coverage PARTIAL | VERIFIED (partial) |
| 18 | GitHub account repos matching research terms | search API user:Prekzursil phenibut / faers | 0 and 0 (no public phenibut code repo; code lives only in the Zenodo archive) | VERIFIED |
| 19 | GitHub grace repo | GET repos/Prekzursil/grace-iberlef-2026 (+ commits, tree, raw README/report) | public; created 2026-06-07T04:56:25Z; updated 2026-07-05; pushed 2026-08-02T05:32:44Z; default branch master; Python; 21,194 KB; 0 stars/forks; no license; description "GRACE @ IberLEF 2026 — Spanish clinical argument mining (Track 1: evidence component detection). 27-cell transformer sweep on Modal + softmax-probability ensemble + report deliverables."; 16 commits 2026-04-10 → 2026-07-05 (author "Prekzursil" in Apr/Jun, "Andrei Mihai Visalon" from 2026-06-27; 4 dependabot). Tree (truncated at ~850 entries) contains FINAL/report/{GRACE_Track1_Report.pdf, .docx, GRACE_Track1_IberLEF2026.pptx, README.md, report_data.json, figures/ (13 PNG), slides_png/ (28)}, FINAL/ensemble_results.json, FINAL/modal_results_summary.json, FINAL/report_out/GRACE_track1_submission.json, FINAL/modal_out/. NO paper source: FINAL/paper/main.tex → 404. README, report README and report_data.json carry NO author, team, affiliation, official test score or rank | VERIFIED |
| 20 | GRACE report content | DOCX text extracted locally (scratchpad GRACE_Track1_Report.txt) | Title "Argument Mining in Spanish Clinical Trials — A 27-Run Transformer Benchmark and Ensemble for Evidence Component Detection"; 9 backbones × 3 seeds = 27 runs, Modal A10G bf16; best single mDeBERTa-v3-base 0.705±0.028 dev strict macro-F1; all-9 softmax-mean ensemble 0.7434 (official scorer), top-3 0.7416, greedy 0.7426; blind submission 2,474 abstracts → 11,752 components (Premise 7,872 / Claim 3,717 / MajorClaim 163), 0 offset mismatches; MajorClaim ceiling 0.24–0.43 per model; corpus 350 train / 50 dev docs. No author line, no official test number, no rank | VERIFIED |
| 21 | GRACE task facts | LinguistList 37.884; sites.google.com/view/iberlef-2026 (home, tasks); Codabench API /api/competitions/13280/ | First edition, Spanish clinical argument mining; Track 1 RCT abstracts (components Premise/Claim/MajorClaim + Support/Attack/Partial-Attack relations), Track 2 MIR exam cases; organizers Iker de la Iglesia, Aitziber Atutxa, Ander Barrena, Koldo Gojenola, Raquel Martínez, Soto Montalvo, Miguel Ángel Rodríguez, Sofía Zakhir Puig, Vanesa Gómez Martínez (HiTZ/UPV-EHU et al.); dates: train/dev 2026-03-18, test 2026-04-22, result submission deadline 2026-05-03, results published 2026-05-08, system paper 2026-05-24, acceptance 2026-06-17 (IberLEF-wide 06-19), camera-ready 2026-07-03, workshop 2026-09-22 at SEPLN 2026, León; site grace2026.hitz.eus 301→Codabench 13280 (created 2026-01-28 by idelaiglesia004, published=true); IberLEF 2026 has 18 tasks; proceedings at CEUR-WS.org, task overviews in SEPLN journal PLN no. 77 (Sept 2026) | VERIFIED |
| 22 | GRACE official results / leaderboard | Codabench /api/competitions/13280/results/ → 403; /api/leaderboards/?competition=13280 → 200 with EMPTY list; competition page is a JS shell; forum API 404 | Public leaderboard NOT retrievable | UNVERIFIED (login-gated) |
| 23 | IberLEF 2026 proceedings | ceur-ws.org index (latest Vol-4270, 22-Sep-2026); web search | No "IberLEF 2026" CEUR volume published as of 2026-09-23; IberLEF program page references a Google-Drive "IberLEF 2026 Detailed Program.docx" with no fetchable link; SEPLN journal site journal.sepln.org fails TLS (cert for gitlab.ujaen.es) | VERIFIED (absence as of today) |
| 24 | Organizer / Codabench correspondence | Gmail search (from:codabench.org, ehu.eus, hitz.eus, sepln.org, subject:GRACE/IberLEF) | none in this Gmail account (registration may be under the s.unibuc.ro address, which is not this mailbox) | VERIFIED absence in THIS mailbox only |
| 25 | Kaggle runs for GRACE | Gmail (kaggle-noreply) | "Your notebook finished" for GRACE T1 kernels 2026-06-06/07 (mrbert-biomed s42, mdb s42, mrb s100) = corroborates the June sweep timing | VERIFIED |
| 26 | Kaggle dataset alexcristea72/iberlef-grace | web | 404 (private/removed). Possible collaborator; unverified | UNVERIFIED |
| 27 | Zenodo account | Gmail (noreply@zenodo.org, GitHub OAuth notice) | Zenodo account created / GitHub↔Zenodo OAuth authorized 2026-06-06 (no GRACE Zenodo record was ever created) | VERIFIED |
| 28 | Bachelor's-degree project repo | GET repos/Prekzursil/Personal-Finance-Management + raw README | "Android application for personal finance management, developed as a Bachelor's Degree project, written it Kotlin And Java for Android"; app name Thrifty; created 2025-05-26; pushed 2026-08-21; Java; 1 star; README: "originally developed as a Bachelor's degree project"; Firebase Auth/Analytics, ML Kit OCR, SQLite, MPAndroidChart, CameraX, Glide, Google Drive backup, EN/RO; no university/supervisor/year named | VERIFIED |
| 29 | Institutional email control | ORCID (verified public email), GitHub notice 2026-09-04 "andrei-mihai.visalon@s.unibuc.ro was added to your account" | He controls a University of Bucharest student-domain address | VERIFIED |
| 30 | LinkedIn | linkedin.com/in/andrei-mihai-visalon-03141b170 | HTTP 999 (blocked); not checked | UNVERIFIED |
| 31 | Awards / thesis / diploma in vault | grep award|prize|scholarship|thesis|licență|diploma|bachelor | nothing relevant (only unrelated matches) | VERIFIED absence in vault |

---

## 2. Public research record — what exists under his name today

1. PREPRINT (public, citable, not peer-reviewed)
   Visalon, A. M. (2026). Computational corroboration, at the sign level, that R-phenibut is the GABA-B eutomer: a two-sided alchemical transfer free-energy validation. ChemRxiv (preprint, v1, posted 22 Sep 2026). https://doi.org/10.26434/chemrxiv.15009306/v1
   Abstract (verbatim from Crossref, abridged only by removing nothing): ATM in AToM-OpenMM at the 4MS4 Venus-flytrap orthosteric site; 22-state λ-ladder with replica exchange, autocorrelation-corrected UWHAM; validation edge R-phenibut → arbaclofen (H→Cl) ΔΔG = −1.890 ± 0.368 kcal/mol vs measured ≈ −1.6 to −2.0; three independent R→S seeds +1.673±0.321, +0.633±0.302, +0.783±0.304 (all positive → R is eutomer; claim is the sign, not the magnitude); between-seed SD 0.562; experimental floor ΔΔG ≥ +1.42 under-predicted; zero completed λ round trips → statistical-only lower-bound errors; at α2δ-1 the H→Cl edge is wrong-signed (−0.805 ± 0.303 vs +1.13) and a gabapentin → pregabalin control lands at +12.846 ± 0.449 vs ≈ −0.21 — failure mechanism unresolved, no α2δ-1 number claimed as biology. "The contribution is the pairing: a licensed regime and a documented-failure regime, each reported with its full uncertainty."
   Indexing status today: Crossref yes (deposited 2026-09-23 05:39 UTC); ORCID no (Crossref permission request pending in his inbox); OpenAlex/Europe PMC/Scholar not yet.

2. DATASET / CODE DEPOSIT (public, citable)
   Visalon, A. M. (2026). Data and code for two studies of the phenibut GABA-B axis: alchemical transfer free energies, and KCTD-subunit genetics with FAERS pharmacovigilance (v3) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.22836832 (concept DOI https://doi.org/10.5281/zenodo.22819600). CC BY 4.0. 35.5 MB. Includes a self-sufficiency verifier that re-derives the published free energies.

3. BACHELOR'S-DEGREE PROJECT (public code, not a publication)
   Thrifty — Android personal-finance app (Java/Kotlin; Firebase, ML Kit OCR, SQLite, CameraX, Google Drive backup; EN/RO). github.com/Prekzursil/Personal-Finance-Management (created 2025-05-26).

4. SHARED-TASK PARTICIPATION ARTEFACTS (public code + technical report, not a publication)
   GRACE @ IberLEF 2026, Track 1 — github.com/Prekzursil/grace-iberlef-2026 (see §3).

Nothing else: no journal article, no conference paper, no arXiv item, no CEUR working notes, no thesis deposit, no Google Scholar profile.

---

## 3. GRACE @ IberLEF 2026 — real status

Timeline reconstructed (VERIFIED items from GitHub commits, Gmail service notifications and vault notes dated at the time; INFERRED items marked):
- 2026-04-10: commits "implement Phases 1-7 scaffolding", "complete 27-experiment GPU sweep on H100" (token-level BIO tagger; vault: BETO 20-ep champion dev S1-F1 0.4037; 13 experiments on H100/A100 ≈ $10; "Deadline: submission 2026-05-03, paper 2026-05-24" listed as future next steps). Azure GPU quota dead-end; RunPod/Kaggle used.
- 2026-04-10 → 2026-06-06: no vault note, no commit. The official result-submission deadline (2026-05-03), results publication (05-08) and system-paper deadline (05-24) fall in this silent window.
- 2026-06-06/07: Kaggle then Modal sentence-level 4-class pipeline, 9 models × 3 seeds, all-9 ensemble dev 0.7434 with the official scorer, blind submission JSON written; repo created public 2026-06-07 (commit "add Modal 27-cell sweep, ensemble, and Track-1 report deliverables"); report DOCX/PDF + 28-slide PPTX built "for a presentation head-to-head". Vault text: "all9 0.7434 (SUBMITTED, zero-peek)".
- 2026-06-08: vault "grace_paper_rewrite": the existing main.pdf "describes a system that DOES NOT EXIST in the code/data" (geometric 4-model ensemble, dev F1 0.8193, etc.) — flagged as fabricated; user chose to rewrite the paper to the real system; .tex reconstructed in CEUR ceurart format with 13 real references; "Official TEST 36.83 (Subtask-1) is NOT in any repo file — only in main.pdf + external leaderboard"; "PDF claims 4th overall / 2nd Subtask-1" flagged "for user to confirm vs official site"; "Still TODO for user: real author names (placeholders in main.tex ~L24-26)". The other-team standings table was dropped.
- 2026-06-27 → 2026-07-05: CI/CodeQL/dependabot housekeeping commits only. Last push 2026-08-02.
- No vault note, commit, or mail evidences: a system-description paper submitted (05-24), an acceptance (06-17/19), a camera-ready (07-03), or workshop attendance (09-22, León).

Status verdict:
- Work done: YES, substantial and public (reproducible 27-run benchmark, ensemble, blind-test submission file, technical report, slides). VERIFIED.
- Official evaluation: a blind-test submission file exists (VERIFIED). Whether it was scored in the OFFICIAL phase is UNVERIFIED: the only claimed official number (Subtask-1 test 36.83, "4th overall / 2nd Subtask-1") comes from a PDF the owner's own notes flag as fabricated, is absent from every repo artefact, and the strong all-9 system was produced five weeks after the results deadline. INFERRED (≈60-70%): the June all-9 submission went to a post-evaluation/open phase, and any official-phase entry was the weaker April system (dev ≈0.40, consistent with a ≈0.37 test score). Codabench results are login-gated; confirm by logging into the Codabench account and reading "My submissions" per phase, and by checking the mailbox used for Codabench registration for the 2026-06-17/19 notification.
- Published working notes: NO evidence (no CEUR IberLEF 2026 volume exists yet as of Vol-4270 dated 2026-09-22; the June .tex had placeholder authors). Re-check CEUR-WS in 2-6 weeks; if a paper under his name appears there, it becomes a citable line.
- Resume framing that is true today: "Participant, GRACE @ IberLEF 2026 shared task (Spanish clinical argument mining, Track 1): built and open-sourced a 27-run multilingual/clinical transformer benchmark and probability-averaging ensemble (dev strict macro-F1 0.743 vs 0.705 best single model) with a validated blind-test submission." Do NOT put a rank or an official score on the resume until confirmed.

---

## 4. Paper A — phenibut GABA-B enantioselectivity (ATM RBFE)

Vault chronology (VERIFIED as dated notes): P1 locked 2026-08-19 (A1 draft docs/paper/A1_GABAB_ATM_RBFE_2026-08-19.md); extensive post-UWHAM grill converged 2026-08-26 (G-1…G-18; at that time "No ChemRxiv freeze until a QM/MM number exists" — evidently relaxed later, the posted title is the no-QM-clause option); competitor scan 2026-08-25 "not scooped" (no phenibut R/S FEP/ATM 2024-2026) but Shityakov/Skorb 2026 computational GABA-B/phenibut line exists so "first computational treatment" is not claimable; Paper A skeleton 2026-09-13; draft assembled + 3-lens adversarial audit 2026-09-14 (docs/PAPER_1_DRAFT_2026-09-14.md ≈48.6 KB; 7 figures; self-contained HTML; seeds reported as co-equal rows, no averaging; "clears the bound" retracted; SI "not for human use" box); compute audit 2026-09-15 (every ΔΔG traced to primary logs); Zenodo deposit v1-v3 2026-09-17/18; ChemRxiv posted 2026-09-22; DOI live 2026-09-23.
STATUS: PREPRINT PUBLISHED (ChemRxiv v1). Not peer-reviewed. No journal submission found (vault: none; Gmail: no editorial/manuscript mail). Target journal unknown. Sole author. Data deposit public.
Resume: citable as a preprint line (label it "preprint").

## 5. Paper B — KCTD16/KCTD12 genetics (MR + colocalization) with FAERS

Vault (VERIFIED as notes): draft placed 2026-09-14 (docs/PAPER_B_DRAFT_2026-09-14.md; "mechanism/depression paper; GABA-B downregulation axis"); key result MetaBrain cortex cis-eQTL instrument KCTD16 rs171201 (F=53) → FinnGen R12 F5_MOOD Wald OR 1.197 (1.109–1.293), p=4.5e-6; coloc PP.H4=0.948 is a transcribed external, provenance-pending; KCTD12 brain MR not computable (instruments absent from FinnGen set); cis-MR v2 (2026-07-10) 0/36 cells causal = honest negative; 4 figures; 2026-09-15 compute audit found two finalization-day computations excluded and "affirmatively DENIED" in the text (integrity fix required before any posting); 2026-09-15 FAERS v2 changed conclusions (see §6). Zenodo description calls the KCTD16 MR "significant in FinnGen" but "does not replicate outside Finland".
STATUS: DRAFTED, under revision. NOT preprinted (no Crossref/DataCite/medRxiv/bioRxiv record), NOT submitted. Its data are inside the public Zenodo deposit. Not on this machine.
Resume: NOT citable. At most "manuscript in preparation" if the resume style allows it; otherwise omit.

## 6. FAERS pharmacovigilance analysis

VERIFIED as vault notes (auto-memory project_faers_v2_dedup_2026-09-15 + Paper B note): two distinct openFDA runs — Run 1 (locked 2026-09-14, N=20,692,690; baclofen/phenibut/fasoracetam × 6 withdrawal/depression PTs; phenibut N=49, baclofen 90,227, fasoracetam 0) feeding Paper B §3.1/Table 2/SI-1; Run 2 (2026-06-25 via ToolUniverse, N=20,328,571; loss-of-consciousness table: phenibut a=7/n=49 PRR 23.3, ROR 27.0 [12.1–60.0]; baclofen 2.4, pregabalin 2.5, gabapentin 1.7; phenibut "Drug interaction" ROR 48.0) in docs/FAERS_DISPROPORTIONALITY.md. v2 (2026-09-15, 48 keyless calls): drug-role (suspect-only) restriction collapses baclofen Depression ROR 2.64 → 1.31, bracket [0.96,1.50] (non-signal proven via a receivedate-partitioned census of 78,592/90,232 = 87.1% of baclofen reports and a monotone ROR bound); withdrawal axis strengthens (DWS 6.19 → 20.70 at 83% suspect); MedDRA version populated per record, range 17.0–26.0 (SI-1 wording corrected); duplicates negligible; LOC reproduced (phenibut PRR 23.36 / ROR 27.09 [12.17–60.30]).
STATUS: a component of Paper B (drafted); receipts deposited in Zenodo (title includes "FAERS pharmacovigilance"). Not a standalone paper; not published.
Resume: usable only as a skills/methods line (openFDA disproportionality, PRR/ROR, drug-role restriction, census bounding), not as a publication.

## 7. Education — University of Bucharest, BSc Computer Science, 2022–2025

VERIFIED: self-asserted on ORCID (entered 2026-05-31; dates 2022-10-01 → 2025-06-04; dept "Computer Science"; degree "Bachelor's in Computer Science"); institutional address andrei-mihai.visalon@s.unibuc.ro verified on ORCID and added to GitHub 2026-09-04 (proves control of a UB student-domain mailbox); Bachelor's-degree project repo created 2025-05-26 (timing consistent with a June 2025 defence); affiliation self-asserted on ChemRxiv and Zenodo.
NOT VERIFIED: the diploma itself (graduation, grade, thesis title, supervisor). Nothing on this machine or in the vault documents the licență. No public registry exists to check. Treat as "yes-on-request" (diploma scan).
Consistency note for the resume: three different faculty strings are in circulation — ORCID "Computer Science" (department), ChemRxiv "Faculty of Mathematics and Computer Science" (the university's official English name per the owner's own 2026-09-15 note), Zenodo "Faculty of Mathematics and Informatics" (the form that note calls a mistranslation). Use "Faculty of Mathematics and Computer Science" everywhere and fix the Zenodo affiliation on the next version.

## 8. ORCID with zero works — helps or hurts, and what to do

Plain answer: by itself an empty ORCID neither helps nor hurts; reviewers read ORCID as an identifier, and empty records are the norm at BSc level. Putting the iD on a resume while it is empty is mildly negative only because a reader who clicks finds nothing to corroborate the research lines. Putting it on once it lists the preprint + the dataset is a net positive: it makes the two resume lines one-click verifiable and disambiguates him from the unrelated Ioana Visalon who dominates "Visalon" author searches.

Register the existing output: YES, today, it takes minutes —
1. ORCID inbox → the Crossref request dated 2026-09-23 10:32 UTC → "Grant permissions" (adds 10.26434/chemrxiv.15009306/v1 and future Crossref DOIs automatically).
2. ORCID → Works → Search & link → DataCite → add 10.5281/zenodo.22819600 (concept) — or enable the DataCite auto-update so the versioned DOIs follow.
3. Add the GRACE repo only if/when a CEUR working-notes paper exists; do not add the technical report as a "work".
4. Optionally mark the education entry with the faculty name and keep dept/faculty consistent (see §7).
Effect: ORCID shows 2 works; OpenAlex will merge its split author records over time because both point at the same ORCID.

---

## 9. Resume-ready lines (only what is true today)

- Preprint: Visalon, A. M. (2026). Computational corroboration, at the sign level, that R-phenibut is the GABA-B eutomer: a two-sided alchemical transfer free-energy validation. ChemRxiv. doi:10.26434/chemrxiv.15009306/v1 (preprint, sole author).
- Data deposit: Visalon, A. M. (2026). Data and code for two studies of the phenibut GABA-B axis… Zenodo. doi:10.5281/zenodo.22819600 (CC BY 4.0; self-verifying archive).
- Shared task: GRACE @ IberLEF 2026 (Spanish clinical argument mining, Track 1) — 27-run transformer benchmark + softmax-averaging ensemble, dev strict macro-F1 0.743 (best single 0.705), blind-test submission; code and report public at github.com/Prekzursil/grace-iberlef-2026. (No rank/score until confirmed.)
- Education: BSc Computer Science, University of Bucharest, Faculty of Mathematics and Computer Science, Oct 2022 – Jun 2025 (Bachelor's project: Thrifty, Android personal-finance app).
- Methods/skills (evidenced by the above): alchemical relative binding free energies (ATM / AToM-OpenMM, UWHAM, replica exchange; FEP+ cross-checks; Schrödinger suite), reproducible-research packaging (Zenodo self-verification script), pharmacovigilance disproportionality on openFDA FAERS (PRR/ROR, suspect-role restriction, partition census bounds), Mendelian randomization / colocalization workflows (FinnGen R12, GTEx, eQTLGen, MetaBrain), Spanish clinical NLP (mDeBERTa-v3, RigoBERTa-Clinical, bsc-bio-ehr-es, XLM-R; weighted CE, two-stage refit, ensembling), GPU orchestration on Modal / Kaggle / RunPod / Scaleway, Databricks SQL.
- ORCID 0009-0001-8776-8498 — list after the two works are attached.

## 10. Gaps (what a resume would want that these sources cannot supply)

1. Official GRACE outcome: no public leaderboard; the 36.83 / "4th overall, 2nd Subtask-1" claim is unverified and originates in a document the owner's notes call fabricated. Needs the Codabench account or the registration mailbox.
2. Whether a GRACE system-description paper was submitted/accepted/presented; CEUR IberLEF 2026 volume not yet published (check ceur-ws.org after ~Oct 2026); SEPLN PLN no. 77 overview (participant list) not fetchable (TLS error).
3. Diploma / graduation confirmation, thesis title, grade, supervisor for the BSc.
4. Target journal and submission dates for Paper A; whether Paper B will be posted; the manuscripts themselves are not on this machine.
5. ChemRxiv license, categories and metrics (page blocked); no Google Scholar profile; OpenAlex author record split (two IDs).
6. Co-authors/teammates on GRACE (Kaggle dataset owner "alexcristea72" hints at a collaborator; unverified) — the resume must not claim "solo" or "team" without checking.
7. Any awards, scholarships, talks, teaching, or conference attendance — none found anywhere.
8. LinkedIn profile contents (blocked).

## 11. Method notes / caveats

- WebFetch results are model summaries of pages; every load-bearing number above was cross-checked against at least one machine-readable source (Crossref JSON, Zenodo/DataCite JSON, OpenAlex JSON, GitHub JSON, or locally extracted DOCX text).
- Gmail was used only for the owner's own service notifications (ORCID, Zenodo, GitHub, Kaggle) and to test for organizer mail; no message bodies other than the ORCID notification were read, and third-party mail present in the inbox was ignored.
- Vault dates are note mtimes/valid_as_of values; the vault's newest phenibut note is 2026-09-20, i.e. it predates the ChemRxiv posting, so the decision to post is documented only by the public record.
- Local files fetched this session sit in the scratchpad: GRACE_Track1_Report.pdf/.docx/.txt (from the public repo).
