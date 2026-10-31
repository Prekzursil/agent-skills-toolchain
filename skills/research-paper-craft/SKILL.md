---
name: research-paper-craft
description: Use when writing, structuring, or revising a state-of-the-art scientific
  research paper, review, preprint, or thesis chapter and you want it to read well
  and land. Covers the craft of paper architecture, the narrative spine, the title
  and abstract, figures as the paper UI, reproducible methods.
metadata:
  type: skill
  origin: fork-2026-06-30-RESEARCH_PHENIBUT
permalink: dqverify-repo-20261013/skills/research-paper-craft/skill
---

# research-paper-craft — writing a SOTA scientific paper

**A paper is a UI for an idea.** Almost no one reads it linearly. A reader skims **title → abstract → figures → conclusions**, then decides whether to read the body. So the paper must work at every altitude — the title alone, the abstract alone, the figures alone — and reward whoever goes deeper. Optimize for the skim *and* the deep read. (Readers gauge relevance from title+abstract and skim figures before committing — Royal Society 2024; Editage.)

## The two-move process (do these in order)

1. **Outline first (Whitesides' method).** Before any prose, write the outline as the **figures and tables in final order, each with a one-sentence claim**. The paper IS that figure sequence plus the argument connecting them. If the outline doesn't tell a story, prose won't save it. (Whitesides, *Adv. Mater.* 2004.)
2. **Write backwards.** Decide the **take-home messages** (the 1–3 novel claims) → write **Results** around the figures → **Methods** → sharpen **Discussion** → **Introduction** (the funnel down to your gap) → **Abstract** → **Title** last. You cannot write a tight intro or abstract until you know exactly what you are claiming. (the "writing backwards" strategy, *Mar. Life Sci. Technol.* 2021 / PMC10077155.)

## The narrative spine

Every strong paper is **one story**: broad context → the specific **GAP** (the tension) → your question → your answer → the **so-what**. The gap is the hook — name what is missing, wrong, or unknown, and make the reader *feel* it before you resolve it. Beginning–middle–end; problem-posed-then-solved. Narrative-style papers measurably engage readers more (PMC10491847). Write the one-sentence version first: *"We show that X, which matters because Y."* If you can't, you're not ready to write.

## Per-section playbook

- **Title** — specific, keyword-rich, jargon-free; state the *finding* or the *contribution*, not just the topic. It is the single most-seen line; it drives discovery and the skim decision.
- **Abstract** — the most-read part after the title. One tight paragraph (or structured: background / methods / results / conclusion) that tells the whole story standalone. Front-load the result. Seed the keywords a searcher would use (visibility = citations; Royal Society 2024).
- **Graphical abstract** — worth building: papers with one get ~3× views and ~8× social engagement (Springer Nature; Editage). Conclusion statement at the top, then 1–3 key results as simple visuals. Make it self-contained.
- **Introduction** — a funnel: broad importance → what's known → **the gap** → your question/hypothesis → (one line) what you did. End on the gap; that's the tension the rest resolves.
- **Methods** — the reproducibility contract. 91% of scientists tie detailed methods to reproducibility (PMC8276979). Enough that a competent peer could replicate it; cite the reporting guideline (below). Share data + code.
- **Results** — the figures carry it; the text *narrates* them in the outline order, one message per figure. Report, don't interpret (that's Discussion). State effect sizes + uncertainty, not just p-values.
- **Figures & tables (the paper's UI)** — each figure makes ONE point, has a self-contained caption, and is legible at thumbnail size. Visual hierarchy: the eye should land on the message first. Use colorblind-safe palettes and direct labels over legends (accessibility — ACS Chem. Health Saf. 2024). A reader who only looks at your figures should still get the story.
- **Discussion** — the so-what: what the results mean, how they fit/extend prior work, the mechanism, the **honest limitations**, and the concrete future work. Don't restate Results; interpret them.
- **References** — the recent frontier + the foundational anchors; cite what you actually used; avoid padding.

## The engagement / keeping-interesting layer

- **Clarity is the engagement.** Scientific writing has measurably *declined* in readability over decades (PMC/biorxiv) — counter it: active voice, one idea per sentence, short paragraphs, define-then-use. The clearest paper in a field wins disproportionate attention.
- **Stakes + tension.** Tell the reader why it matters early and keep a thread of "and therefore…" Don't bury the lede; don't hedge the contribution.
- **Discoverability is part of the craft** — title keywords, abstract keywords, a graphical abstract, a plain-language summary, and a thread/post on publication. The paper that isn't found isn't read.

## The reviewer / editor lens

- Write for the **skeptical reviewer**: pre-empt the obvious objections (controls, confounds, alternative explanations) inside the paper.
- **Journal fit** before writing: match scope, length, and audience; read the author guidelines + a few recent papers in the target venue.
- **Cover letter**: 1 paragraph — the finding, why it fits this journal, why it matters now.
- **Rebuttal**: thank, then address every point; concede what's fair, push back with evidence where you disagree, mark each change with the line number. Tone = collaborative, not defensive.

## Modern SOTA (2024-era)

- **Preprint** (bioRxiv/arXiv/etc.) for speed + feedback + a citable DOI before review.
- **Open science**: deposit data + code (Zenodo/OSF/GitHub) with a license; it raises trust and citations.
- **Reporting guidelines** — use the one for your design: PRISMA (systematic reviews), CONSORT (RCTs), ARRIVE (animal), STROBE (observational), STARD (diagnostic). They're a built-in completeness checklist.
- **Registered reports** when the question (not the result) is the contribution — peer review of the protocol pre-results kills publication bias.

## Workflow checklist

1. One-sentence claim + target journal chosen.
2. Figure-sequence outline (Whitesides) — does it tell the story?
3. Draft backwards (Results→…→Title).
4. Figures-first polish (each = one point, thumbnail-legible, colorblind-safe).
5. Clarity pass (read aloud; cut 10% of words; active voice).
6. Reproducibility pass (methods + data/code + the right reporting guideline).
7. Skeptic pass (what would Reviewer 2 attack?).
8. Abstract + title + graphical abstract last; keyword-optimize.
9. Internal/colleague review → preprint → submit → rebuild for rebuttal.

## Sources
- Whitesides, *Writing a Paper*, Adv. Mater. 2004 — researchgate.net/publication/227993468
- Writing backwards / scientific story — ncbi.nlm.nih.gov/pmc/articles/PMC10077155
- Title, abstract, keywords for visibility — royalsocietypublishing.org/doi/10.1098/rspb.2024.1222 ; pmc.ncbi.nlm.nih.gov/articles/PMC11288685
- Graphical abstracts (engagement) — editage.com/insights/research-at-a-glance-the-power-of-graphical-abstracts
- Reproducibility attitudes — ncbi.nlm.nih.gov/pmc/articles/PMC8276979
- Narrative-style papers — ncbi.nlm.nih.gov/pmc/articles/PMC10491847
- Figure accessibility — pubs.acs.org/doi/10.1021/acs.chas.4c00141