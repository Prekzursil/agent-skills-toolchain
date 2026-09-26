---
title: TAAR1 ToolUniverse data (phenibut DA-puzzle adjunct)
type: report
permalink: main/phenibut/targets/taar1-tool-universe-data-phenibut-da-puzzle-adjunct
tags:
- phenibut
- TAAR1
- trace-amine
- GABA-B
- dopamine
- tooluniverse
---

# TAAR1 (Trace Amine-Associated Receptor 1) — ToolUniverse pull 2026-06

IDs: UniProt Q96RJ0 | gene TAAR1 (syn TA1/TAR1/TRAR1) | Ensembl ENSG00000146399 | HGNC 17734 | ChEMBL CHEMBL5857 | 339 aa Gs-coupled class-A GPCR.

## Affinity (REAL measured)
- ChEMBL functional EC50 (human TAAR1): beta-PEA/phenethylamine (CHEMBL610) **129 nM**; dextroamphetamine (CHEMBL612) 935 nM; levamfetamine 920 nM; phentermine 5470 nM. Full agonist SAR series present.
- GtoPdb curated (pEC50/pKi): beta-PEA pEC50 6.2-7.4; **3-iodothyronamine/T1AM pEC50 6.5-7.9** (most potent endogenous); tyramine 5.8-7.2; octopamine 4.8-5.9; RO5166017 pKi 7.5-8.7; **ulotaront (SEP-363856) pIC50 6.8** (clinical TAAR1 agonist antipsychotic); ralmitaront pEC50 7.2; **EPPTB pKi up to 9.0** (antagonist/inverse agonist).
- BindingDB: ZERO affinities for Q96RJ0. Phenibut ABSENT (consistent with corpus: phenibut not in ChEMBL/BindingDB/GtoPdb).

## Structure
- 19 PDB cryo-EM structures (all 2023-2024). Landmarks: **8W87** METH-TAAR1 2.8A (Nature 2023, PMID 37935377); **8JLN** T1AM-hTAAR1-Gs 3.24A (Nature 2023, PMID 37935376); **8UHB** Ro5256390-hTA1-Gs 3.35A (Nat Commun 2024, PMID 38168118).
- 3D Beacons: 22 models (17 PDBe exp, AlphaFold DB 1, SWISS-MODEL 1, 2 PED ensembles).

## Expression
- GTEx v8: median TPM ~0 across ALL 54 tissues (max Kidney_Medulla 0.021). TAAR1 is bulk-undetectable — low-abundance, ER-retained intracellular GPCR. Pathway: Reactome R-HSA-375280 (Amine ligand-binding receptors), R-HSA-418555 (G alpha(s) signalling). GO: trace-amine receptor activity, adenylate-cyclase activating + inhibiting GPCR signalling.

## NEW ANGLE — links TAAR1 to program Q-B (DA puzzle) and Q-G (GABA-B tolerance machinery)
- **PMID 15644497 (Federici 2005, Mol Pharmacol)**: trace amines (beta-PEA, tyramine) DEPRESS the GABA-B slow IPSP / baclofen outward current in midbrain DA neurons by activating G-proteins that interfere with GABA-B<->**Gbetagamma-gated GIRK** coupling. This is a direct molecular bridge to the program's GABA-B disinhibition model AND the KCTD12/16 Gbetagamma-scavenging tolerance node (Q-G).
- **PMID 28963038 (Vega-Quiroga 2018)**: lateral-septum GABAergic disinhibition of antero-ventral VTA DA neurons via GABA-A alpha1 — independent mechanistic support for tonic VTA disinhibition (Q-B).
- Hypothesis worth testing: phenibut's prosocial/articulation acute profile could intersect trace-amine/TAAR1 tone; but phenibut is NOT a measured TAAR1 ligand (absent from all bioactivity DBs) — TAAR1 belongs to the DA-puzzle context (PEA's true high-affinity target is TAAR1 @129nM, NOT direct DA release — reinforces the already-REFUTED PEA->DA-release claim).

## Tool notes
- ChEMBL target.json pref_name__icontains=TAAR1 -> HTTP 500 (EBI); fallback target_components__accession=Q96RJ0 works.
- Pharos_get_target_expression needs `gene`/`uniprot` (not `target`); returned same GTEx ~0.
- HPA_get_rna_expression_by_source needs gene_name+source_type+source_name (3 required).
