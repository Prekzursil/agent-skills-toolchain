---
title: CACNA2D1 alpha2-delta-1 ToolUniverse target dossier
type: report
permalink: main/phenibut/cacna2-d1-alpha2-delta-1-tool-universe-target-dossier
tags:
- phenibut
- cacna2d1
- alpha2delta
- gabapentinoid
- tooluniverse
- target
---

# CACNA2D1 (alpha2-delta-1) target dossier — ToolUniverse pull 2026-06-22

Phenibut question F/a2d branch. Real data from ToolUniverse modules.

## Identity / structure
- UniProt **P54289** (CA2D1_HUMAN), 1103 aa. Entrez 781. Ensembl ENSG00000153956. chr7:81,946,444-82,443,970 (strand -1).
- Pharos TDL **Tclin**, family IC (ion channel), novelty 0.017 (well-studied). 66 pubs.
- AlphaFold AF-P54289-F1, avg pLDDT **86.56**, monomer, full coverage.
- 25 PDB structures incl **8IF3/8IF4** (already in FEP program), 7MIX/7UHF/8E59 (Cav complexes). Domain basis: two dCache_1 (double cache) domains + VWA domain; gabapentinoid/amino-acid pocket in cache domains (universal AA-binding pocket present in a2d-1 and a2d-2 only; a2d-3/-4 lack it due to bulky Trp/Phe). [Page/Dolphin 2023, PMID 36735378]

## Affinity (THE experimental anchor — Zvejniece 2015, PMID 26234470)
Radiolabeled-gabapentin displacement, rat brain membranes, Ki at a2d-1 VDCC:
- **R-phenibut Ki = 23 uM** (4x higher affinity at a2d than its GABA-B Ki ~92 uM)
- S-phenibut 39 uM; baclofen 156 uM; **gabapentin 0.05 uM (50 nM)**.
- R-phenibut anti-nociceptive (formalin, CCI) NOT blocked by GABA-B antagonist CGP35348 -> a2d-mediated, gabapentin-like. Confirms a2d as a real second phenibut target, distinct from GABA-B.
- DrugCentral: gabapentin MoA target = CACNA2D1 (P54289), action MODULATOR, is_moa=true (+ CACNA2D2). Validates target annotation.
- Pharos: 210 ligands / 4 approved drugs; top tool ligands = pyrazolo[4,3-d]pyridazines, pActivity 7.5-9 (IC50 ~1-30 nM).
- BindingDB: empty for P54289 (phenibut/gabapentinoid binding data absent there — consistent with corpus note that phenibut is absent from ChEMBL/BindingDB/GtoPdb).

## Expression (GTEx via Pharos)
Highest: skeletal muscle 38 TPM, artery/aorta ~14-18, brain frontal cortex BA9 18.9, hypothalamus 15.7, cerebellar hemisphere 15.9, adipose 12.4. Broad brain expression. Near-zero whole blood (0.026). HPA tissue-specific: skeletal muscle 72.5, tongue 70.5 nTPM.

## Pathway / disease
- Reactome: R-HSA-9856532 (Mechanical load PIEZO1/integrins in osteocytes) — sparse curation.
- STRING DISEASES: Brugada syndrome (DOID:0050451), Short QT (DOID:0050793), heart conduction disease — cardiac channelopathy. CACNA2D1-4 family broadly linked to epilepsy, autism, bipolar, schizophrenia, depression (Ablinger 2020).
- GO BP: calcium transport, ion transport. Regulates Ca-current density + activation/inactivation kinetics; excitation-contraction coupling.

## Safety / DDI (mechanism-typed, NO regimen)
- FAERS pregabalin (class-mate) top signals: somnolence, dizziness, fall, depressed consciousness, coma, drug abuse/dependence, completed suicide. => documented PD class effect: **additive CNS depression** when combined with other CNS depressants (opioids, alcohol, benzos). This is the mechanism-typed DDI relevant to phenibut (also a CNS depressant via GABA-B): PD-additive sedation/respiratory depression, NOT a CYP/transporter interaction (gabapentinoids are renally cleared, minimal CYP).

## Tools down this run (recorded, not retried)
- ChEMBL_search_targets: HTTP 500 then ReadTimeout (EBI ChEMBL flaky). Used Pharos/DrugCentral/OpenTargets as fallback.
- OpenTargets_get_associated_diseases_by_target: not in loaded set (used STRING DISEASES + target_info instead).

## NEW angles
1. a2d Ki 23 uM vs GABA-B 92 uM => at a2d, R-phenibut is ~4x MORE potent than at GABA-B. The program treats GABA-B as primary, but the anti-nociceptive/anti-allodynic arm is a2d-mediated and GABA-B-independent (CGP35348 null). a2d may dominate the analgesic/anti-allodynic phenotype.
2. 8IF3 already mapped; the dCache_1 universal AA-binding pocket (not VWA) is the gabapentinoid site — re-dock R-phenibut into the cache pocket, not the VWA, for the connected-map FEP re-run.
3. a2d-3/-4 selectivity filter (bulky Trp/Phe occlude pocket) gives a clean negative-control series for R-phenibut docking specificity.
