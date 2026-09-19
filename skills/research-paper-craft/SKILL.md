---
name: research-paper-craft
description: "Use when writing, structuring, or revising a state-of-the-art scientific research paper, review, preprint, or thesis chapter and you want it to read well and land. Covers paper architecture, the narrative spine, title and abstract, figures as the paper UI, reproducible methods, single-author voice, reporting standards by identifier, anti-AI-prose discipline, and a mechanical pre-submission acceptance gate."
metadata:
  type: skill
  origin: fork-2026-06-30-RESEARCH_PHENIBUT
  revised: 2026-09-15
---

# research-paper-craft — writing a SOTA scientific paper

**A paper is a UI for an idea.** Almost no one reads it linearly. A reader skims **title → abstract → figures → conclusions**, then decides whether to read the body. So the paper must work at every altitude — the title alone, the abstract alone, the figures alone — and reward whoever goes deeper. Optimize for the skim *and* the deep read.

## The two-move process (do these in order)

1. **Outline first (Whitesides' method).** Before any prose, write the outline as the **figures and tables in final order, each with a one-sentence claim**. The paper IS that figure sequence plus the argument connecting them. If the outline doesn't tell a story, prose won't save it. (Whitesides, *Adv. Mater.* 2004, DOI 10.1002/adma.200400767.)
2. **Write backwards.** Take-home messages (1–3 novel claims) → **Results** around the figures → **Methods** → **Discussion** → **Introduction** (the funnel to your gap) → **Abstract** → **Title** last. You cannot write a tight intro or abstract until you know exactly what you are claiming.

## The narrative spine

Every strong paper is **one story**: broad context → the specific **GAP** → your question → your answer → the **so-what**. Write the one-sentence version first: *"This work shows that X, which matters because Y."* If you can't, you're not ready to write.

**OCAR width-match test** (Schimel, *Writing Science*, 2012): the Opening and the Resolution must be the **same width**. An opening that promises "how do drugs work" and a resolution that delivers "one sign on one edge" is a broken paper. Narrow the opening or widen the result — do not let them disagree.

**Stress position** (Gopen & Swan, *Am. Sci.* 78:550, 1990): readers emphasise what lands at the **end** of a sentence. End on the result, not on a trailing caveat. Context goes at the start.

**One paragraph = one point**, stated in the first sentence (Mensh & Kording, *PLoS Comput Biol* 13:e1005619, DOI 10.1371/journal.pcbi.1005619).

## Voice and person — decide once, apply program-wide

- **Single author → "I". Never "we".** The "royal we" from a lone author reads as false modesty and reviewers notice. The **ACS Style Guide** (chemistry's own authority) recommends first person + active voice; **APA 7th** says a sole author uses "I".
- **"I" is for authorial acts** — choices, judgements, retractions, refusals ("I withdraw that attribution", "I do not average the seeds"). Routine method description stays impersonal/passive. A mechanical find-replace of we→I is as bad as the "we".
- **Blanket impersonality is not the safe default** — it is *more conservative than the field's own style guide advises*. Use it for methods, not for judgement.
- **Every paper in a program must use the same voice.** A two-paper program where one is impersonal and one says "we" is an internal contradiction.
- **Never refer to yourself in the third person.** "the author's knowledge", "this program recorded it as", "the dossier asserts", "an earlier reading supported" — each frames your own work as somebody else's, and a reader cannot tell whether you did it or are reporting on a group you belong to. It also lets a retraction dodge its owner: *"an earlier reading supported X"* quietly disowns the reading, where *"my earlier reading supported X"* takes it. Use **I/my** for what you did or judged, **"this work"** for the body of work, impersonal for the artifact. "available from the author on request" → "available on request".
- **The one legitimate third person is other people.** "the authors nominate…" (their paper) must survive any such pass. A blanket find-replace corrupts those, so audit each hit — in a real pass over two manuscripts, 28 of 30 hits were self-reference and 2 were other authors.
- Gate: `grep -nE "\b(we|our|ours|us)\b"` → **zero hits** in a single-author paper; and `grep -niE "the author|this program|the dossier|the parent synthesis"` → zero *self-referential* hits.

## Reporting standards — cite by name AND identifier

Find the standard for your design and name it in the text. Know the difference between an **EQUATOR-registered / journal-mandated** standard and a **community best-practices consensus** — claiming a standard doesn't exist when a citable consensus does is a factual error a reviewer will catch.

| Design | Standard | Identifier |
|---|---|---|
| Randomized trial | CONSORT | equator-network.org |
| Observational | STROBE | equator-network.org |
| **Mendelian randomization** | **STROBE-MR** (20 items + 30 subitems) | PMID 34698778; E&E PMID 34702754 |
| **Pharmacovigilance disproportionality** | **READUS-PV** Statement + E&E | DOI 10.1007/s40264-024-01421-9; E&E PMID 38713347 |
| Systematic review | PRISMA | equator-network.org |
| Animal work | ARRIVE | equator-network.org |
| **Alchemical free energy / RBFE** | **Mey et al., LiveCoMS 2(1):18378 (2020)** — has an explicit **checklist in §12** | DOI 10.33011/livecoms.2.1.18378 |
| **MD foundations** | **Braun et al., LiveCoMS 1(1):5957 (2019)** | DOI 10.33011/livecoms.1.1.5957 |
| Data | **FAIR principles** | DOI 10.1038/sdata.2016.18 |

**Never write "no standard exists" without checking.** For alchemical RBFE specifically: there is no EQUATOR-mandated checklist, *but* Mey et al. 2020 is a peer-reviewed, citable consensus with a checklist covering replicates, estimator uncertainty, phase-space overlap, cycle closure, hysteresis, and force-field/protonation/water-model disclosure. Framing it as "no mandated checklist, but a community consensus exists and this work conforms to it" converts a false void into a conformance claim — a net strengthening.

**Data availability:** deposit raw data + code with a **DOI** (Zenodo/OSF). Local filesystem paths in a manuscript are not data availability.

## Per-section playbook

- **Title** — specific, keyword-rich, jargon-free; state the *finding*. Keep under ~15 words. A 40-word title packing three results is a title that packs none.
- **Abstract** — the most-read part after the title. Front-load the result. Journals commonly cap ~250–300 words; preprint servers accept the long structured form, so prepare **both**.
- **Graphical abstract** — worth building; conclusion statement at the top, 1–3 key results as simple visuals, self-contained.
- **Introduction** — funnel: broad importance → what's known → **the gap** → your question → one line of what you did. End on the gap.
- **Methods** — the reproducibility contract. Enough that a competent peer could replicate it; cite the reporting guideline and every piece of software/force field with a real reference.
- **Results** — figures carry it; text narrates them in outline order, one message per figure. Report, don't interpret. Effect sizes + uncertainty, not bare p-values.
- **Discussion** — the so-what: meaning, fit with prior work, mechanism, **honest limitations**, concrete future work.
- **Limitations** — see the hard rule below.
- **References** — the recent frontier + foundational anchors; cite what you actually used.

## Limitations must be scientific or scope — never logistical

This is a hard rule. A limitations section says what the *science* cannot support, or what was deliberately out of scope. It never says why you personally couldn't do something.

- **Banned:** "unavailable", "insufficient compute", "ran out of", "budget", "quota", "no GPU", "blocked on", "the earlier attempt failed", HTTP status codes, tool/installation problems, session or workflow narration.
- **Correct:** "The electronic origin of the enantioselectivity is not addressed here; resolving it requires a QM/MM treatment, which is left for separate work."
- **Also correct:** "No SNP-level outcome summary statistics are held locally, so the outcome leg is drawn from the public FinnGen R12 endpoints."

The test: would this sentence still be true and relevant if a different lab with different resources wrote the paper? If not, it is a process log, not a limitation. Delete it.

## Anti-AI-prose pass

Kobak et al. measured excess vocabulary across 14M+ abstracts and found LLM-era spikes in a specific lexicon (*Science Advances* 2025, DOI 10.1126/sciadv.adt3813).

- **Lexical grep-and-cut:** `delve, underscore, pivotal, intricate, showcase, boast, realm, notably, comprehensive, multifaceted, testament to, seamless, crucial, it is worth noting, it is important to note, furthermore, moreover`.
- **Repetition is itself a tell.** A fixed caveat sentence repeated verbatim 10× reads as generated text and dilutes a genuinely important point. State it once in full at first use, then refer back ("…the single-instrument caveat of §3.2"). Same for a repeated thesis phrase: say it in the intro and the conclusion, not four times.
- **Vary sentence length.** Break anything over ~40 words. Uniform rhythm is a tell.
- **Cut self-labelling.** "honest", "rigorous", "careful", "thorough" — naming a virtue is weaker than demonstrating it, and repeating it reads as protesting too much. If the error bars are lower bounds and you say so, that *is* the honesty; delete the adjective.
- **Thin probability parentheticals.** Calibrated confidence bands are a genuine strength on load-bearing claims. Per-sentence density reads as hedging. Keep them on the headline claims only.

## Figures — the paper's UI

- Each figure makes **ONE** point, has a **self-contained caption**, and is legible at thumbnail size.
- **Palette: Okabe–Ito colour-universal set** — `#E69F00 #56B4E9 #009E73 #F0E442 #0072B2 #D55E00 #CC79A7 #000000` (Wong, *Nat Methods* 8:441, 2011, DOI 10.1038/nmeth.1618). Check green/cyan pairs under deuteranopia.
- **Specs** (Nature figure guide as a defensible default): fonts **5–7 pt at final size**; single column **89 mm**, double **183 mm**; height ≤ **170 mm**; **≥300 dpi** vector, 600 dpi raster.
- **Don't trust the defaults** — set colours and fonts explicitly (Rougier et al., DOI 10.1371/journal.pcbi.1003833).
- **Figures go inline at their anchor, not in a dump at the end.** Number them in the order they are first referenced and keep in-text references synchronised.
- **Out-of-bounds QA is a real defect class — check every figure, not just the first.** Recurring failures worth an explicit pass: annotation text overlapping data or the footer; a text box drawn above `ylim` so it clips the title; a label jammed against the right edge (convert to a legend entry); a bold title overflowing its box; multi-column layouts with horizontal text collision (restructure as stacked full-width bands with explicit wrapping); tick-label collision on log axes (set explicit locators). For an animation, check **every frame**, not frame 0.

## Never fabricate a citation

A visible `[TK — unresolved]` placeholder is **strictly better** than an invented reference. Every citation must be verified against a real record (PubMed, DOI resolver, CrossRef, the PDB) before it enters the manuscript. A fabricated reference on a preprint under a real name is research misconduct, not a formatting slip. Resolve truncated accessions — a dangling 3-character "PDB ID" is a hole a reviewer will find.

**Verifying the identifier is only half the check. Three failure modes survive a correct PMID:**

1. **Identifier right, attribution wrong.** The paper exists, is correctly cited, and *does not contain the claim*. Found in practice: a claim graded "Established" on a review whose abstract never mentions the measurement attributed to it. Read the abstract — at minimum — for every load-bearing claim, not just the reference list. If the claim plausibly sits in a primary study cited *inside* that review, an untraced chain is not a citation: downgrade it.
2. **Right phenomenon, wrong population.** A verified primary source establishes the effect in a *different* group than the one you claim it in — blunted growth-hormone response to baclofen is documented in alcohol dependence, and citing it for major depression is unsupported even though the paper and the phenomenon are both real. Check the population, the species, and the measure. A mouse study does not support a claim about rats; a biosynthesis measure does not support a claim about tissue content.
3. **Wrong article type.** "A review of X" that is in fact original research (or the reverse) changes what the citation can carry. Confirm the type, not just the title.

**Record graded status, not a binary.** "confirmed" / "identifier confirmed, attribution not" / "located, numeral unverified" / "not located" are four different states and collapsing them to "cited" is how a wrong claim survives. When a source genuinely cannot be found, say so in the manuscript and **do not substitute a plausible near-miss** — a same-surname paper on an adjacent topic is not the citation.

## The mechanical acceptance gate (run before every submission)

Prose review is necessary but not sufficient. Write a lint script and make passing it the definition of done — and re-run it after *every* edit, including edits made by someone else.

```
VOICE      no \b(we|our|ours|us)\b in a single-author paper
PROCESS    no 404 / "SSL expired" / quota / "not runnable" / "blocked on" / scratch / tooling narration
           ^ anchor these as PHRASES. A bare "ssl" substring matches "gro-ssl-y"; a bare "session"
             matches "possession". A lint that flags ordinary English gets muted, and a muted lint
             is worse than none.
EXCUSE     no unavailable / insufficient / "ran out of" / budget / "no GPU"
AI-TELL    no delve / underscore / pivotal / multifaceted / "it is worth noting" / furthermore, / moreover,
REQUIRED   author block present; any mandated safety/scope box present verbatim
FIGURES    all referenced files exist; captions numbered sequentially; none duplicated; no trailing gallery
PATHS      no absolute local filesystem paths
TK         count must be zero before upload
UNICODE    normalise U+2011 non-breaking hyphens, U+00A0, zero-width chars; consistent minus/times
```

**Number-integrity check — the highest-severity defect class.** After any rewrite, restructure, or delegated edit, mechanically verify that **every** number still matches the single source of truth: extract the canonical values (free energies, error bars, per-leg values, ORs, CIs, p-values, accessions, PMIDs, counts) and assert each is present in the manuscript. Normalise Unicode minus, en/em dashes and non-breaking spaces before matching or you will get false failures. A prose edit that silently alters a value is far worse than one that reads awkwardly.

**Do not accept a self-certification.** A writer — human or agent — reporting "all gates pass" is a claim, not evidence. Run the gate yourself against the file bytes. Re-run it after every subsequent change; a gate result goes stale the moment the file does.

**Audit the gate for fail-open.** Every check must feed the exit status. A real gate printed `PASS` for weeks while *also* printing `required '<author name>': *** MISSING`, because only one of its five checks fed the return value — the rest printed and were discarded. **A gate that cannot fail measures nothing.** Test it deliberately: break something the gate is supposed to catch and confirm it goes red. An untested gate is a decoration.

## Verify the BUILT artifact, not only the manuscript

**A build that exits 0 has proved the compiler ran, not that the artifact is correct.** The gate above reads markdown. Readers, search engines and screen readers read the PDF, and defects live in the gap. Two that shipped through a fully green build:

- **Corrupt text layer.** A font's f-ligature glyphs (fi, fl, ff, ffi) carried a broken ToUnicode map, so extraction returned U+03D0 instead of letters — 411 corrupted word instances across 66 pages of two manuscripts, including *confirmed*, *significant*, *verified*, *affinity*, *first*. **The printed page looked perfect.** What broke was everything downstream: in-reader search, copy-paste, screen readers, and preprint-server / Scholar indexing. Searching the PDF for "confirmed" returned nothing. Fix with `-V mainfontoptions="Ligatures=NoCommon"` (fontspec), which stops the glyph being substituted rather than trusting its Unicode map.
- **Columns printed on top of each other.** Pandoc sizes pipe-table columns from the **relative dash counts in the separator row**. A starved first column cannot break an unhyphenatable surname, so the word overprinted its neighbour. **Text extraction does not reveal this** — the layer stores the words separately and in the right order. Only glyph geometry shows it. Fix by rebalancing the separator dashes, *not* by shortening cells; the victims were short pre-existing rows.

**Three checks to automate** (PyMuPDF for geometry — self-contained, no poppler — plus pypdf for text):

```
TEXT LAYER   no suspect codepoints in extracted text (U+03D0, U+FFFD, private-use F000–F002)
OVERPRINT    no two words on one rendered line whose x-ranges intersect by > ~0.8 pt
             (below that is ordinary kerning / italic side-bearing)
CONTROLS     a list of words that MUST be findable — an all-clear on TEXT LAYER means nothing
             if the layer is empty. Normalise U+2010–2014 first: LaTeX emits U+2011 inside
             compounds, so searching "fixed-charge" scores 0 on a document containing it 11×.
```

Also **render pages to images and look at them** for any new table, figure or template change. Tables with paragraph-length cells are a layout smell regardless — long justification belongs in prose beneath the table, where it can also be read.

## Preprint mechanics — match the server

- **ChemRxiv** (chemistry): PDF or .docx main file; figures ≥300 dpi; supplementary of *any* format **including audio/video**, so animated figures are acceptable as SI; CC licence menu.
- **medRxiv** (human-health epidemiology, clinical): figures TIFF/EPS/JPEG; PDF ≤40 MB; SI uploaded separately; requires competing-interests and funding statements plus reporting-guideline adherence.
- **bioRxiv's Clinical Trials and Epidemiology categories are CLOSED to new submissions** — human-health epidemiology routes to medRxiv, and a misrouted submission is screened out or transferred. (bioRxiv/medRxiv FAQ.)
- **Animations:** the manuscript PDF cannot show motion. Always produce a **static fallback figure for inline use** and treat the animation as SI. Motion must encode information — decorative animation is worse than a good static figure.

## The reviewer / editor lens

- Write for the **skeptical reviewer**: pre-empt the obvious objections (controls, confounds, alternative explanations) inside the paper.
- **Run an actual adversarial review before submitting** — ideally a fresh reader with no stake, instructed to find reasons to reject. Distinguish findings that are *writing* problems from findings that are *evidence* problems; polish cannot fix the latter, and pretending otherwise is how papers get rejected.
- **Disclose the evidence that cuts against you, prominently.** A result that contradicts your own thesis, stated plainly in the abstract and discussion with its qualifiers, is far stronger than the same result discovered by a referee. Give it a headed paragraph, propagate it to the limitations and the falsifiable-tests list.
- **Name falsifiers.** For every hypothesis-grade claim, state what observation would kill it.
- **Journal fit** before writing; **cover letter** = one paragraph (the finding, why this journal, why now); **rebuttal** = thank, address every point, concede what's fair, push back with evidence, cite line numbers.

## Workflow checklist

1. One-sentence claim + target venue chosen (check the server's category rules).
2. Figure-sequence outline (Whitesides) — does it tell the story?
3. Draft backwards (Results → … → Title).
4. Voice decision applied program-wide (single author → "I").
5. Figures-first polish: one point each, thumbnail-legible, Okabe–Ito, out-of-bounds pass on every panel.
6. Reproducibility pass: methods + data/code with a DOI + the right reporting guideline, cited by identifier.
7. Limitations pass: scientific/scope only, zero logistical language.
8. Anti-AI-prose pass: lexicon grep, de-duplicate repeated caveats, vary sentence length, cut self-labelling.
9. Citation pass: every reference verified; zero TK.
10. **Mechanical gate + number-integrity check against the SSOT** — and confirm the gate can actually fail.
10b. **Built-artifact pass:** PDF text layer clean, no column overprinting, positive controls findable, pages eyeballed.
11. Adversarial review; separate writing problems from evidence problems.
12. Abstract + title last; prepare both the long preprint form and the ≤250-word journal form.

## Sources

- Whitesides, *Writing a Paper*, Adv. Mater. 16:1375 (2004) — DOI 10.1002/adma.200400767
- Mensh & Kording, *Ten simple rules for structuring papers*, PLoS Comput Biol 13:e1005619 (2017) — DOI 10.1371/journal.pcbi.1005619
- Gopen & Swan, *The Science of Scientific Writing*, Am. Sci. 78:550 (1990)
- Schimel, *Writing Science* (Oxford UP, 2012) — OCAR
- Mey et al., *Best Practices for Alchemical Free Energy Calculations*, LiveCoMS 2(1):18378 (2020) — DOI 10.33011/livecoms.2.1.18378 (checklist in §12)
- Braun et al., *Best Practices for Foundations in Molecular Simulations*, LiveCoMS 1(1):5957 (2019) — DOI 10.33011/livecoms.1.1.5957
- Skrivankova et al., STROBE-MR, JAMA 326:1614 (2021) — PMID 34698778; E&E PMID 34702754
- READUS-PV Statement — DOI 10.1007/s40264-024-01421-9; E&E PMID 38713347
- Wilkinson et al., FAIR principles, Sci Data 3:160018 (2016) — DOI 10.1038/sdata.2016.18
- Wong, *Points of View: Color blindness*, Nat Methods 8:441 (2011) — DOI 10.1038/nmeth.1618
- Rougier, Droettboom & Bourne, *Ten Simple Rules for Better Figures*, PLoS Comput Biol (2014) — DOI 10.1371/journal.pcbi.1003833
- Kobak et al., *Delving into LLM-assisted writing: excess vocabulary*, Science Advances (2025) — DOI 10.1126/sciadv.adt3813
- ACS Style Guide (first person + active voice); APA 7th (sole author → "I")
- ChemRxiv Submission Guide; bioRxiv FAQ; medRxiv FAQ
