# Conflict resolution: Andrei-Mihai Visalon (public-source check)

Date of check: 2026-09-23. All statements are labelled VERIFIED (with source), INFERRED, or COULD NOT DETERMINE.
No logins, no contact with any person or organisation. Fetched content was treated as data only.

Tooling note: the session's WebSearch budget was exhausted before this task started and the search-hub Tavily/Exa
keys were rejected, so the work ran on the claude.ai Tavily/Exa connectors, direct WebFetch/curl, Google DNS-over-HTTPS,
Wayback (availability API + direct capture fetch; the CDX index was returning "Temporarily Offline" 503s all session,
so the list of captures below is not exhaustive) and a Playwright browser for pbinfo.ro, which sits behind a JavaScript
proof-of-work page that a real browser passes automatically (its bot check is disabled in the page's own script:
`if (false && bot)`). No login was used anywhere.

---

## Conflict 2 (lead): the pbinfo.ro ranking

### Bottom line
The CV's March 2023 claim ("ranked 2nd all time solved problems (currently)") is not only plausible, it is now
understated. Today he is **first** on pbinfo.ro's public all-time Top 100 by problems solved, and the two archived
captures that bracket March 2023 show him at #3 (Dec 2022) and #2 (Jun 2023).

### Evidence timeline

| Date | Rank | Problems solved | Next competitors | Source | Label |
|---|---|---|---|---|---|
| 2022-12-06 | #3 | 3,516 | #1 TREYWAY 3,569; #2 oaspru 3,536 | Wayback capture `web.archive.org/web/20221206094954/https://www.pbinfo.ro/top100` (fetched raw with `id_` and parsed) | VERIFIED |
| 2023-02-03 | (profile only) | 3,573 | n/a | Wayback capture `web.archive.org/web/20230203092508/https://www.pbinfo.ro/profil/Prekzursil`: "3573 probleme rezolvate, 10997 surse trimise, 4881 soluții corecte, 36.88 succes (%)", 5 articles, contact prekzursil@yahoo.com | VERIFIED |
| 2023-03 (CV date) | claimed #2 | n/a | n/a | No capture found for March 2023 | COULD NOT DETERMINE directly; consistent with the captures on both sides (INFERRED) |
| 2023-06-06 | #2 | 3,733 | #1 TREYWAY 3,738 (5 ahead); #3 oaspru 3,728 | Wayback capture `web.archive.org/web/20230606053414/https://www.pbinfo.ro/top100` | VERIFIED |
| 2026-09-23 (live) | **#1** | **4,244** | #2 Adrian Negreanu-Maior 4,191; #3 Lucia Negreanu-Maior 4,190; #4 Peter Tobias 4,167; #5 Aspru Octavian 4,025; #100: 2,328 | Live page `https://www.pbinfo.ro/top100` read in Playwright (no login) and independently via Tavily's extractor (also no login); both show row 1 = "Andrei Visalon (Prekzursil) | Valcea | 4244" | VERIFIED |

Live profile `https://www.pbinfo.ro/profil/Prekzursil` (2026-09-23): "4244 probleme rezolvate, 14228 surse trimise,
6134 soluții corecte, 34.40 succes (%)", 6 articles, activity journal through 21 Sep 2026. VERIFIED.
Privacy note: the profile publicly displays his personal Gmail address as the contact; he may want to change that.

### What the metric is (decides the honest wording)
- Column header on the Top 100 is "Probleme rezolvate". pbinfo's own help page "Despre rata de succes"
  (`https://www.pbinfo.ro/ajutor/40/despre-rata-de-succes`, S. Candale, 13 Dec 2023) defines the count as
  "numărul de probleme rezolvate (cu 100 de puncte)", i.e. **distinct problems solved with a full 100-point score**.
  It is not points, not submissions, not a rating. VERIFIED.
- The same page notes the known weakness of the ecosystem: some users create multiple accounts to inflate success
  rate. Nothing found suggesting that about him; his account dates back at least to 2019 (infoarena submissions
  under "Andrei Visalon Prekzursil" from May/June 2019; GitHub account created 2019-08-28). VERIFIED.
- The page footer says "Clasamentul se actualizează periodic" (ranking updated periodically, not real time). VERIFIED.

### Reachability
- The Top 100 (national and per-county, e.g. `/top100/valcea`) and the profile are public, no login required.
  Read from a fresh Playwright browser and from a third-party extractor. VERIFIED.
- Caveat for anyone checking by hand: the site shows a "Verificare" proof-of-work interstitial for a second or two;
  plain `curl`/WebFetch see only that interstitial. A normal browser gets through.

### How big is the pool
- pbinfo does not publish a live user count on any page found. COULD NOT DETERMINE (current figure).
- The only published statistics found are in a school promotional PDF by the site's author
  (`https://webserv.lgrcat.ro/ci/Excelenta/PBINFO.pdf`, undated, from the era when the site had "peste 1200 de probleme"):
  "peste 14000 de utilizatori, din care 6000 de elevi, 200 de profesori; 695000 de soluții; 350 de clase". VERIFIED (dated).
  Problem IDs now run to about 5,027 (homepage "latest problems" links), so that brochure is years old and the user
  base is certainly larger today. INFERRED.
- Independent framing: the platform is described by teachers as the standard classroom judge in Romanian high-school
  informatics ("platformă arhicunoscută în rândul profesorilor de informatică", InfoAs / YouTube presentation) and the
  site's creator is Silviu Candale, informatics teacher at Colegiul Național Liviu Rebreanu, Bistrița. VERIFIED.
- Depth of the leaderboard: 100th place has 2,328 solved; he has 4,244 of roughly 5,000 problems on the site
  (about 84%; INFERRED from the max problem id).

### Bonus, verifiable: he is also a problem author on pbinfo
- His article "Problemele Propuse - Prekzursil & Co" (`https://www.pbinfo.ro/articole/31291/...`, 26 Nov 2023,
  4.79K views) lists **88 attached problems** (#2913 Proth Number ... #2693 VocSortDesc), spanning grades 9-11,
  difficulties easy to "concurs". VERIFIED (live page).
- Spot-check of problem #2913: "Postată de: Andrei Visalon (Prekzursil)"; "Autor: Mirela Mlisan, Andrei Visalon".
  So at least some are co-authored. VERIFIED for #2913; authorship split across all 88 not checked (COULD NOT DETERMINE
  sole- vs co-authored count; he can state it).
- He has 6 published articles on pbinfo (BigInt class, Map/hash table, STL list/vector, etc., 2022-2024). VERIFIED.
- solinfo.ro (third-party solutions site) also references "@prekzursil". VERIFIED.

### Safe resume wording (choose one)
1. "Ranked #1 all-time on pbinfo.ro (Romania's main high-school competitive-programming judge) by problems solved:
   4,244 problems solved with full score, as of Sep 2026; top 3 since 2022." (every number above is checkable at
   pbinfo.ro/top100 and pbinfo.ro/profil/Prekzursil)
2. "Author/co-author of 88 problems published on pbinfo.ro; 6 technical articles."
- Do not write "2nd" any more; do not write "all-time solved problems" without the "with full score" qualifier if the
  reader might check the profile and see 6,134 correct solutions vs 4,244 problems.
- Because the board is periodic and #2 is 53 problems behind, date-stamp the rank ("as of ...").

### If a reviewer wants more than the public pages
Nothing else is needed for a third party to verify: the URL of the leaderboard and of the profile suffice.
For the historical "2nd in March 2023" claim specifically, only a dated screenshot from him would settle the exact
month; the public record settles "#3 in Dec 2022, #2 by Jun 2023, #1 now".

---

## Conflict 3: the employer "Dinu Plast"

### The company exists; it is in Râmnicu Vâlcea, not Bucharest
- Registered name **DINUPLAST SRL** (directories also print "Dinu Plast SRL" / "DINU PLAST S.R.L."; same fiscal code).
  CUI/CIF 16367462 (RO16367462), Trade Register J2004000404389 (EUID ROONRC.J2004000404389), founded 26 April 2004,
  status "în funcțiune", VAT payer, no ANAF debts, share capital 120,000 RON. Registered office: Str. Matei Basarab
  nr. 14, Bl. 119, Sc. A, Et. 1, Ap. 5, Râmnicu Vâlcea, jud. Vâlcea. Working point / warehouse: Str. Stolniceni nr. 205
  (by the Oltchim footbridge), Râmnicu Vâlcea; landline +40 350 800 646. Sole associate and administrator with initials
  "P.C." / surname beginning "POP..." (paywalled). VERIFIED: termene.ro, risco.ro, totalfirme.ro, listafirme.ro,
  targetare.ro, infocompanies.com, romaniayp.com, Kompass, and a 2010s AJOFM vacancy list in Adevărul (address Stolniceni 205).
- Activity: main CAEN 4644 "Comerț cu ridicata al produselor din ceramică, sticlărie și produse de întreținere"
  (wholesale of china, glassware and cleaning products). Directory description: "Articole de uz casnic din materiale
  plastice. Comerț en-gros al materialelor plastice. Depozit de materiale plastice. Distribuție de produse diverse."
  So "wholesale plastics / household-goods distributor" is a fair description. VERIFIED.
- Size (risco.ro / totalfirme.ro, ANAF balance sheets): employees 7 (2021), 6 (2022), 7 (2023), 8 (2024), 7 (2025);
  turnover RON 6.41M (2021), 6.26M (2022), 6.12M (2023), 6.91M (2024), 5.24M (2025); net profit RON 0.27-0.64M/yr.
  A small but stable family-scale wholesaler, 22 years old. VERIFIED.
- Location conflict resolved: the company is in Râmnicu Vâlcea. The CV that says Bucharest is wrong about the company's
  location (it could only be right about where he sat while working remotely). VERIFIED (registry) / INFERRED (remote).

### His link to the company
- A Facebook video titled "O scurta prezentare a firmei Dinu Plast." posted by "Andrei Visalon" (handle prekzursiltm),
  located "in Râmnicu Vâlcea, Romania", exists (title and poster seen in the search index; the page itself is
  login-walled, so its date and content were not read). VERIFIED (existence) / COULD NOT DETERMINE (date, content).
- Employment dates (May 2021 to Jul 2022 vs Jun 2023) and role (employee vs freelancer): no public record either way.
  COULD NOT DETERMINE. What settles it: his contract or "adeverință" / invoices, or the dated Facebook post.

### The website
- No web address is listed for the company in any directory ("Adresa web: Nespecificată" on infocompanies). VERIFIED.
- `dinuplast.ro`, `dinu-plast.ro`, `dinuplast.com` do not exist in DNS (Google DoH: NXDOMAIN for all three). VERIFIED.
  (The sandbox's own resolver sinkholes everything to 10.186.0.1, so the earlier nslookup was meaningless.)
- Wayback has no captures for dinuplast.ro or dinu-plast.ro (availability API: empty). VERIFIED.
- None of his 68 public GitHub repositories relates to Dinu Plast or to a 2021-2023 company website; the earliest
  repository is from Nov 2023. VERIFIED (GitHub API listing).
- Conclusion: the site he built is not findable and may never have been on a public domain (an intranet/LAN site or a
  hosting that has since lapsed are both consistent with the evidence). COULD NOT DETERMINE. What settles it: the domain
  or URL it ran on, hosting/registrar records, the source, or screenshots; the "ledger/management software" work
  (customising/networking an accounting package) is by nature not publicly visible.

### Safe resume wording
"Dinuplast SRL (trading as Dinu Plast), Râmnicu Vâlcea, Romania: wholesale distributor of household plastics, glassware
and cleaning products (7-8 staff, approx. RON 6M turnover)". Use Râmnicu Vâlcea; drop Bucharest. Describe the website
as an internal/company site unless he can produce a URL; describe the software work as configuration/networking of the
firm's accounting and stock-management software, which needs no external proof but should not be dressed up.

---

## Conflict 4: name form and identity consistency

### What Romanian law says about hyphens
- Current law: Legea 119/1996 privind actele de stare civilă, art. 66 (2): "Numele de familie sau prenumele formate din
  două sau mai multe cuvinte se scriu cu cratimă." (compound family names or given names are written with a hyphen).
  VERIFIED from two independent copies of the consolidated text (edirect.e-guvernare.ro upload of Legea 119; ILGA-Europe
  PDF of the republished law).
- This is the post-2012 rule. Legea 61/2012 (M.Of. 255 of 17 Apr 2012), approving OUG 80/2011, introduced "names or given
  names formed from two or more words are written with a hyphen" and reversed the earlier rule. Before that, the
  civil-status methodology (HG 64/2011, art. 24 a) said compound names "se scriu fără a se despărți prin cratimă"
  (without hyphen). VERIFIED (juridice.ro, 20 Apr 2012; notari.pro / lege5.ro text of HG 64/2011 art. 24).
- The Romanian consulate in Bonn states the practical meaning: "Numele de familie și prenumele formate din mai multe nume
  se scriu cu cratimă. Cratima nu este decât un element de legătură." (the hyphen is only a connector). VERIFIED as a
  search-index snippet of bonn.mae.ro/node/450; the page itself refused the connection.
- Consequence for him (born 2002): his birth certificate was issued under the no-hyphen regime, so it may read
  "ANDREI MIHAI"; any identity card or passport issued after April 2012 (his first CI, at 14, in 2016) would carry
  "ANDREI-MIHAI". Legally these are the same single compound given name. INFERRED. What settles it: the name line on his
  current CI and on his bachelor's diploma.
- Orthography (DOOM, Academia Română): compound personal names "se întâlnesc scrise fie cu cratimă" or without; the
  Academy is permissive, the civil-status law is what fixes the official form. VERIFIED (doom.lingv.ro snippet).

### Diacritics on "Visalon"
- No public record shows a diacritic form. The Wikipedia list of Romanian surnames (letter V) lists "Visalon"
  separately from "Vișan"; Namespedia derives it from the biblical Avesalom (Absalom), with a plain s; other public
  bearers (Ioana Visalon, actress, IMDb; Dan Visalon, UPET; "Visalon G. Mirela", MDLPA declaration) are all written
  without diacritics, as is his own institutional email, ORCID, GitHub and pbinfo. VERIFIED (absence in all sources checked).
  The surname is rare (Namespedia: about 103 occurrences across 2 countries), which helps disambiguation.

### Where each form currently appears (VERIFIED)
- "Andrei-Mihai Visalon": both CVs; institutional email local-part `andrei-mihai.visalon@s.unibuc.ro`; LinkedIn headline.
- "Andrei Mihai Visalon": GitHub name field; skills.rest mirror.
- "Andrei Visalon": ORCID (given "Andrei", family "Visalon", no other names); pbinfo display name; infoarena; Hugging Face;
  Facebook poster name.
- His yahoo handle, per the Feb 2023 archived pbinfo profile, was prekzursil@yahoo.com (not a_visalon).

### Recommendation: standardise on the hyphenated "Andrei-Mihai Visalon"
Apply it to the resume, ORCID (given names "Andrei-Mihai", family name "Visalon"), LinkedIn (already), GitHub (change
the display name), and every future byline, always with the ORCID iD 0009-0001-8776-8498 on papers. Reasons:
1. It is the official form under the law in force and is the form the University of Bucharest itself uses for him;
   master's and doctoral paperwork at UB will carry that name, and doctoral files are checked against diplomas and birth
   certificate, so bylines that match the diploma name avoid friction. VERIFIED (law, email) / INFERRED (paperwork).
2. For author indexing (Crossref, Scopus, Web of Science, OpenAlex, Google Scholar), the hyphen marks "Mihai" as part of
   the given name, yielding "Visalon, A.-M." consistently. The unhyphenated "Andrei Mihai Visalon" is at risk of being
   parsed as given name "Andrei" + surname "Mihai Visalon", or of "Mihai" being dropped as a middle name in one venue and
   kept in another, which splits author profiles. INFERRED (standard indexer behaviour), not tested against a live record.
3. "Andrei Visalon" alone is the weakest choice: it is neither the legal form nor the email form, and it discards the
   token that distinguishes him from any other A. Visalon.
4. Consistency matters more than which form: once the first paper is out, changing the string later creates duplicate
   author records. Add the other two forms to ORCID's "Also known as" so that existing pbinfo/GitHub traces still link.

---

## Follow-up 1: how ORCID education affiliations work (and what a reviewer sees)

- His record (public API `pub.orcid.org/v3.0/0009-0001-8776-8498/record`, read 2026-09-23): one education entry,
  "University of Bucharest, Computer Science, Bachelor's in Computer Science, 2022-10-01 to 2025-06-04", **source =
  the record holder** (self-asserted); email `andrei-mihai.visalon@s.unibuc.ro` verified and public; no employment,
  no works; links to LinkedIn and GitHub; created 2025-08-14, last modified 2026-07-21. VERIFIED.
- Multiple education entries are allowed; the Education section "records the educational institution(s)" and the record
  summary shows the three most recent education items. VERIFIED (info.orcid.org integration guide; record-summaries doc).
- Self-asserted vs validated: items added by the researcher show the researcher's own name as "Source" with a blue
  person icon; items added by an ORCID member organisation through the member API or Affiliation Manager show the
  organisation as Source with a green check mark ("Trust Marker"). Record summaries count "validated" and "self-asserted"
  items separately. ORCID's own words: validated items "were independently verified at the source"; self-asserted data
  "remain an important part of the scholarly record" but Trust Markers make data "far more ... credible".
  VERIFIED (info.orcid.org: "Interpreting the trustworthiness of an ORCID record"; "ORCID Record Summaries - Trust
  Markers"; "The Trust Marker Advantage"; iD & Me webinar summary).
- Reality check on weight: ORCID reports that only about 2% of iDs have an organisation-asserted affiliation and that
  the vast majority of affiliation data is self-asserted, so a self-asserted education entry is normal and not a red
  flag. VERIFIED (info.orcid.org, "A Closer Look at ORCID's Affinity for Affiliations").
- The one trust marker he already has: a verified institutional email domain counts as a Trust Marker even when the
  institution has not written to the record. VERIFIED (ORCID webinar summary).
- What to change: edit the existing entry to "Universitatea Titu Maiorescu, Bucharest, Bachelor's in Computer Science,
  2022-10 to 2025-06"; add "University of Bucharest, Faculty of Mathematics and Computer Science, Master's ..., 2025-10 to
  present"; optionally add UBB 2021-09 to 2022-07 with no degree (ORCID allows education without a qualification), or omit
  it. Whether UB or UTM are ORCID members able to validate via Affiliation Manager: COULD NOT DETERMINE.

---

## Follow-up 2: does private vs state university weigh with Romanian employers or doctoral committees?

### Titu Maiorescu's standing (relevant context)
- Private university established 1991 (court decision 59/1991), accredited by Legea 239/2002 as "persoană juridică de
  drept privat și de utilitate publică, parte a Sistemului Național de Învățământ". Institutional ARACIS rating "Grad de
  încredere ridicat" (the highest rating) in 2016/2017 and again for 2023-2028; three ARACIS-accredited doctoral schools;
  the Informatică master's domain was under ARACIS re-accreditation evaluation in May 2026. VERIFIED (ARACIS reports
  EI2462 and EM4076; utm.ro). Faculty of Informatics offers Informatică (full-time and distance) and an English-language
  Artificial Intelligence bachelor's. VERIFIED (utm.ro).

### Employers: evidence found (all dated)
- Evenimentul Zilei, 25 Jun 2009: HR specialist Mihaela Forgaciu (HR România board): "există o tendință, nedeclarată, de a
  acorda mai mult credit absolvenților instituțiilor de stat ... Este o chestiune de încredere, greu de zdruncinat."
- Ziarul Financiar, 15 Jul 2009: recruiter Iuliana Badea (Lugera & Makler): "Angajatorii privați nu mai fac diferențe între
  candidații care au absolvit studiile superioare la stat sau la universități private", describing the state-vs-private
  prejudice as something from "five or six years ago".
- ziare.com, 4 Dec 2009 (research project "Adaptarea activă a educației universitare la cerințele pieței muncii",
  Mihai Păunescu): employers "preferă absolvenți de universități de stat" and want work experience; qualitative, no figure.
- HotNews, 18 Jan 2011, on the UECNCFPA study "Absolvenții recenți de învățământ superior și integrarea lor pe piața
  muncii" (2004-2009; 4,000 employers, 5,500 graduates, 120 recruiters): "80% dintre angajatori declară că nu au nicio
  preferință legată de facultatea sau universitatea din care provine studentul". A ResearchGate snippet of the same study
  reads "96% preferă absolvenții facultăților de stat"; its context could not be read (page not fetchable) and it
  conflicts with the 80% figure, so it is reported here as unverified.
- BestJobs survey of 100 companies (Jurnalul, c. 2010): 25% avoid no university; 46% named Spiru Haret specifically as one
  they avoid (that case is about a diploma scandal, not private universities in general).
- IT specifically: Codecool (2020s) interviews with 47 Romanian IT leaders: more than half no longer treat a bachelor's
  diploma as a hiring necessity. WEF Future of Jobs 2023 via Ziare.com: under 30% of Romanian companies emphasise a
  degree at hiring.
- All labelled VERIFIED as quotations from those articles. Nothing from 2015 onward that measures a state/private
  preference was found.
- Conclusion for hiring: there is dated (2009-2011) evidence of a mild, informal, contested preference for state
  graduates among some employers, and no recent evidence that the distinction matters, least of all in IT, where
  portfolios and experience dominate. Current general practice: COULD NOT DETERMINE beyond that.

### Doctoral admissions
- University of Bucharest, Școala Doctorală de Informatică, admission 2026 page: eligibility is being a master's
  graduate (or pre-Bologna long-cycle graduate, or holder of a foreign degree recognised by CNRED); no criterion refers
  to whether earlier degrees came from a state or private university. UB's Psychology doctoral school scores the written
  test and the research project, with tie-breaks on master's average, bachelor's average and indexed publications, again
  with no institution-type criterion. VERIFIED (fmi.unibuc.ro SDI admission page; doctorat.unibuc.ro/psihologie/admitere).
- Informal weighting by a committee: COULD NOT DETERMINE; no source found. Practically, his doctoral file will lead with
  a UB master's, and the bachelor's institution is then secondary. INFERRED.
- Resume framing option if he wants to pre-empt the question: "Titu Maiorescu University (accredited private university,
  Bucharest; ARACIS 'high confidence' institutional rating)", which is factual and checkable.

---

## Conflict 1 (closed by the subject) - incidental verification only
- The subject's account (UBB 2021-22 incomplete; UTM bachelor's 2022-25; UB master's from 2025) matches his LinkedIn
  profile as indexed by Exa: "Bachelor's degree, Computer Science, Universitatea Babeș-Bolyai, 2021-2022"; "Bachelor's
  degree, Computer Science, Titu Maiorescu University, 2022-2025"; "Master of Computer Applications - MCA, Computer
  Science, University of Bucharest, 2025-2027". VERIFIED (index copy; LinkedIn itself not fetched). "MCA" is a LinkedIn
  degree-type label; the resume should use the UB programme's real name.
- Public trace of the degree project: GitHub repo "Personal-Finance-Management" ("Android application for personal
  finance management, developed as a Bachelor's Degree project", Kotlin/Java, created 2025-05-26). VERIFIED.
- The ORCID education entry (UB, bachelor's, 2022-2025) is wrong on the institution and must be edited (see Follow-up 1).

---

## Sources (all public, read 2026-09-23)
- pbinfo.ro: /top100 (live, Playwright + Tavily extractor); /profil/Prekzursil (live); /articole/31291/problemele-propuse-prekzursil-co;
  /articole/user/Prekzursil; /probleme/2913/proth-number; /ajutor/40/despre-rata-de-succes; /ajutor/9/cum-devin-rezolvitor
- Wayback: web.archive.org/web/20221206094954/https://www.pbinfo.ro/top100; .../20230606053414/https://www.pbinfo.ro/top100;
  .../20230203092508/https://www.pbinfo.ro/profil/Prekzursil; archive.org/wayback/available for dinuplast.ro, dinu-plast.ro
- webserv.lgrcat.ro/ci/Excelenta/PBINFO.pdf (site statistics brochure); infoarena.ro/utilizator/Prekzursil
- Company: termene.ro/firma/16367462-DINUPLAST-SRL; risco.ro/verifica-firma/dinuplast-cui-16367462; totalfirme.ro/dinuplast-srl-16367462;
  listafirme.ro/dinuplast-srl-16367462; targetare.ro/16367462/dinuplast-srl; infocompanies.com/Dinu-Plast-SRL-Ramnicu-Valcea-93279.htm;
  romaniayp.com/company/145598; kompass (ro287270); adevarul.ro AJOFM vacancy list; dns.google/resolve (NXDOMAIN x3);
  api.github.com/users/Prekzursil and /repos
- Law: edirect.e-guvernare.ro Legea 119/1996 (art. 66); ilga-europe.org PDF of Legea 119/1996; juridice.ro/197415 (Legea 61/2012);
  notari.pro and lege5.ro HG 64/2011 art. 24; bonn.mae.ro/node/450 (snippet); doom.lingv.ro
- Names: ro.wikipedia.org "Listă de nume românești - litera V"; namespedia.com (Visalon); imdb.com/name/nm8895849; upet.ro; mdlpa.ro
- ORCID: pub.orcid.org/v3.0/0009-0001-8776-8498/record; info.orcid.org (trust markers, record summaries, affinity for affiliations,
  integration guide); support.orcid.org record summaries article
- Universities: aracis.ro EI2462 and EM4076 reports; utm.ro; fmi.unibuc.ro SDI admission 2026; doctorat.unibuc.ro
- Press on private/state: evz.ro (25 Jun 2009); zf.ro (15 Jul 2009); ziare.com (4 Dec 2009); hotnews.ro (18 Jan 2011);
  jurnalul.ro BestJobs survey; codecool.com; ziare.com WEF 2023 piece
