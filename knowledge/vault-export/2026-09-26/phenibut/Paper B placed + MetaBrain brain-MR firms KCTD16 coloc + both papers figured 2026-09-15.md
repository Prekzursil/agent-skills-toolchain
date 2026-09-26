---
title: Paper B placed + MetaBrain brain-MR firms KCTD16 coloc + both papers figured
  2026-09-15
type: note
permalink: main/phenibut/paper-b-placed-meta-brain-brain-mr-firms-kctd16-coloc-both-papers-figured-2026-09-15
tags:
- phenibut
- paper-b
- metabrain
- mendelian-randomization
- figures
- kctd16
---

# Paper B placed + MetaBrain brain-MR + both papers figured (15.09, session 3fb11978)

- [fact] Paper B draft placed: `docs/PAPER_B_DRAFT_2026-09-14.md` (mechanism/depression paper; GABA-B downregulation axis). Built e2e via ultracode workflow (ground -> firm -> draft -> audit) + two targeted revisions.
- [decision] **KEY NEW RESULT — matched brain-tissue MR firms the KCTD16 coloc.** User said "add the instruments if missing"; a follow-up agent found the missing brain instrument in **MetaBrain (de Klein 2023, Nat Genet)** via its MOLGENIS cis-eQTL API: Cortex-EUR **rs171201** (5:144466903, F=53) is present in FinnGen R12; Wald **OR 1.197 (1.109-1.293), p=4.5e-6** (F5_MOOD); **higher cortical KCTD16 -> higher mood risk.** Converts the PP.H4=0.948 coloc into a directional causal estimate (firms the DIRECTION, not the coloc VALUE). Independently recomputed by the agent AND the Wald arithmetic re-checked by me. Receipt: `compute/depression_firm_2026-09-14/mr_instruments/metabrain/` (RESULT.md, 31_final_brain_mr).
- [fact] Honest caveats in the paper: single cis-instrument Wald (re-expresses the colocalized locus, not fully independent of coloc; no Egger/HEIDI); provenance ~80-90% it is the coloc's dataset; KCTD12 brain instruments (MetaBrain, F=18-41) ABSENT from FinnGen analyzed set (true QC absence, control-validated) so KCTD12 brain MR not computable; KCTD12 blood proxies suggestive-PROTECTIVE = OPPOSITE direction to KCTD16; mapping "higher KCTD16 -> risk" onto the downregulation axis is an OPEN HYPOTHESIS.
- [fact] Non-brain KCTD16 (earlier partial MR): GTEx Testis 0.921 protective / Lung 1.135 risk (tissue-discordant) / brain ACC rs457266 untestable-absent — resolved toward RISK by the cortex instrument.
- [fact] **Data-integrity correction:** my workflow prompt gave the WRONG KCTD12 Ensembl ID (`ENSG00000178761` = FAM219B, chr15); correct KCTD12 = `ENSG00000178695` (chr13). Caught by the MR agent, verified 2 ways (Ensembl REST + mygene.info), did NOT reach the manuscript. (Fed to /feedback.)
- [fact] FAERS firming (openFDA, live): baclofen Drug-withdrawal-syndrome ROR 6.19, Depression 2.64 (robust, Evans+); Drug dependence 0.70 INVERSE; phenibut concordant direction at 2-5 reports (small-N, flagged); fasoracetam ZERO reports (absence of data). Receipt: `.../faers/`.
- [fact] Coloc provenance corrected in-draft: BIOMNI_CAUSAL_MR.md contains NO colocalization (pure MR); both 0.948 and 0.011 are transcribed-externals, flagged provenance-pending.
- [decision] **Both papers now have figures + polished self-contained HTML** (user asked: graphs, tables, aesthetically nice, molecule visuals). Paper 1 (7 figs): DDG forest, R->S seeds vs +1.42 floor, splice-health, GABA-B 4MS4 + alpha2delta 8IF3 (Schrodinger pymol_render), R/S enantiomers + H->Cl/GPN transformations (PubChem). Paper B (4 figs): MR forest, FAERS forest, evidence-tier map, ligand panel. Rendered with matplotlib + Schrodinger `pymol_render` (headless, no job server) + PubChem PNG depictions. HTML: `docs/PAPER_1_2026-09-14.html`, `docs/PAPER_B_2026-09-14.html` (figures base64-embedded, styled tables). Figure PNGs under `docs/figures/paper1|paperB`.
- [fact] Tooling reachability this session: openFDA, GTEx v2, eQTLGen, FinnGen R12 pheweb, MetaBrain MOLGENIS, Ensembl REST, mygene.info, PubChem, RCSB PDB all reachable; IEU OpenGWAS SSL cert EXPIRED, GWAS-Catalog sumstats API + eQTL Catalogue API both 410-Gone. Schrodinger 2026-2 suite pymol_render works headless (license valid, job server can stay stopped). See [[ATM splice 10-11 falsifier — direct measurement REFUTES broken-splice autopsy 2026-09-14]] and [[Paper 1 draft assembled + adversarially audited 2026-09-14]].
