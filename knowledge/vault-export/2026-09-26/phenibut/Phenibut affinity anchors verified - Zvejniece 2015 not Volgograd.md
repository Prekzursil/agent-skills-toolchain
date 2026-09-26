---
title: Phenibut affinity anchors verified - Zvejniece 2015 not Volgograd
type: note
permalink: main/phenibut/phenibut-affinity-anchors-verified-zvejniece-2015-not-volgograd
---

# Phenibut affinity anchors — adversarial verification (2026-06-25)

Claim verified: "R-phenibut a2d 23uM / GABA-B 92uM (corpus-only — find DB support or flag)".

## Verdict: SUPPORT (values correctly sourced) but LOW robustness (single lab/study)

Both anchors trace to ONE primary paper:
- **Zvejniece L, Vavers E, Svalbe B, Veinberg G, ..., Dambrova M. 2015. Pharmacol Biochem Behav 137:23-29. PMID 26234470. DOI 10.1016/j.pbb.2015.07.014.**
- Abstract verbatim: "Kis for R-phenibut, S-phenibut, baclofen and GBP were 23, 39, 156 and 0.05 uM" (a2d, radiolabelled gabapentin displacement, rat brain membranes).
- Companion GABA-B value: R-phenibut Ki 92+-3 uM, racemate 177+-2 uM, baclofen 6.0+-1 uM, S inactive ([3H]CGP54626).

## DB provenance (corrects grounding's "phenibut ABSENT from ChEMBL")
- ChEMBL HAS phenibut: CHEMBL315818 (racemic), CHEMBL53073 (R-enantiomer, SMILES NC[C@H](CC(=O)O)c1ccccc1).
- **GABA-B 92uM IS in ChEMBL**: CHEMBL53073 Ki=92000nM, human GABA-B (CHEMBL2111463), standard_flag=1, pchembl 4.04, curated from doc CHEMBL3600369.
  - CHEMBL3600369 = Brown KM et al. 2015 J Med Chem (PMID 25856547) — a REVIEW that cites Zvejniece primary data. NOT a metadata artifact; it's a real secondary source pointing to same single measurement.
- Racemate GABA-B 177uM also in ChEMBL (CHEMBL315818). Plus 1991/2001 J Med Chem IC50>100uM [3H]baclofen records (R-phenibut).
- **a2d 23uM is ABSENT from ChEMBL** (checked: neither molecule has any a2d/CACNA2D1 record; 2023 selectivity panel CHEMBL5291721 tested ~30 targets all AC50>30uM, a2d NOT among them). But it IS real published primary lit.

## Risk-of-bias (the REAL concentration is Riga, not Volgograd)
- Both anchors = single study, single lab (Latvian Inst Organic Synthesis, Riga: Zvejniece/Vavers/Dambrova cluster), in vitro radioligand, no independent replication.
- This is the dominant RoB, NOT Tyurenkov/Volgograd. The grounding's author-cluster-concentration worry is correctly relocated to the Riga gabapentinoid group.
- baclofen GABA-B 6uM here is far weaker than DB ~3nM(R)/220nM(racemic) anchors — radioligand-assay-dependent; cross-study Ki comparisons need caution.

## "corpus-only" self-label = partially REFUTED
- GABA-B 92uM: direct ChEMBL DB support exists.
- a2d 23uM: absent from ChEMBL but verifiable in indexed primary literature (PMID 26234470). "Verify-able", not "unverifiable corpus-only".
