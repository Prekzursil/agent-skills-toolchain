---
title: (R)-baclofen / arbaclofen ToolUniverse compound profile
type: report
permalink: main/phenibut/compounds/r-baclofen-arbaclofen-tool-universe-compound-profile
tags:
- phenibut
- arbaclofen
- GABA-B
- ADMET
- reference-compound
---

# (R)-baclofen / arbaclofen — ToolUniverse REAL-data profile

Reference eutomer for phenibut program (F: R-phenibut is GABA-B-active enantiomer; baclofen is the rigid chlorophenyl-GABA analog). Pulled 2026-06.

## Identity
- PubChem CID 44602; ChEMBL CHEMBL301742; DrugBank DB08891; GtoPdb ligand 1064 ((-)-baclofen); research code STX-209/STX209; UNII via FDAGSRS not pulled.
- IUPAC (3R)-4-amino-3-(4-chlorophenyl)butanoic acid. C10H12ClNO2, MW 213.66.
- Isomeric SMILES NC[C@H](CC(=O)O)c1ccc(Cl)cc1; InChIKey KPYSYYIEGFHWSV-QMMMGPOBSA-N.
- R-(-)-baclofen = D-baclofen = arbaclofen, the EUTOMER (antispastic-active isomer). Note phenibut's R is also GABA-B-active enantiomer — same R-eutomer pattern.

## Descriptors (PubChem/ChEMBL)
- XLogP -1 / alogp 1.86 (disagree); TPSA 63.3; HBD 2; HBA 2-3; RotB 4; Ro5 violations 0; QED 0.80; aromatic rings 1.
- max_phase 3 (clinical, NOT approved as single agent); chirality=single; USAN 2010.

## GABA-B affinity (GtoPdb interactions, ligand 1064, rat)
- GABA-B1 subunit: agonist (full), pIC50 4.4-4.6 (~25-40 uM) — binding subunit alone.
- GABA-B receptor (functional/heteromer): full agonist, pIC50 8.5 (~3 nM). Matches DrugBank R-baclofen ~3 nM anchor. The B1-alone vs functional-heteromer gap (uM vs nM) is mechanistically important — affinity at isolated B1 is weak; potency emerges at assembled B1/B2 heteromer.
- ChEMBL mechanism: GABA-B receptor AGONIST (target CHEMBL2111463), ref PMID 24272415.

## ADMET-AI (24+ endpoints, SMILES-based)
- BBB_Martins 0.753 (53rd pct) — moderate CNS penetrance, consistent with active CNS drug.
- Bioavailability_Ma 0.852; HIA_Hou 0.935; Caco2_Wang -5.07; PAMPA 0.473; Pgp_Broccatelli 0.014 (NOT Pgp substrate).
- Clearance_Hepatocyte 1.81 (low, 16th pct); Half_Life_Obach 6.65h; VDss_Lombardo -0.047 (low Vd, 35th pct); PPBR 55.9% bound.
- Solubility_AqSolDB -1.65 (good, 75th pct); Lipophilicity_AZ -0.44 (low).
- Tox: AMES 0.069 (neg); hERG 0.148 (low); DILI 0.228; ClinTox 0.150; LD50_Zhu 2.35; Carcinogen 0.345. Stress-response (SR-ARE/ATAD5/HSE/MMP/p53) all <0.06 — clean.

## PK (DrugBank, measured)
- >80-88% renally eliminated UNCHANGED; <1% fecal. RENAL clearance dominant (relevant to phenibut PK hepatic-vs-renal split question — baclofen analog is renal).
- NOT a substrate of CYP1A2/2C19/2D6/2E1/3A4 (prodrug arbaclofen placarbil data) -> minimal CYP-mediated DDI.
- Absorbed throughout intestine incl colon (vs racemic baclofen upper-SI only) via MCT1 (monocarboxylate transporter 1) -> enabled sustained-release prodrug. Half-life ~1.6-3.4h (animal IV).

## Clinical/FAERS
- FAERS indications: multiple sclerosis, muscle spasticity (on-label spasticity); STX-209 reports tied to ASD trials. Drug-characterization: Suspect 5 / Concomitant 4 (small N).
- Phase-II autism RCT (AIMS-2-CT1, EClinicalMedicine 2026, PMID 41631164): missed primary (Vineland socialization) but secondaries (SRS, AIM, ABC, QoL) favored arbaclofen; sleep AEs higher. Arbaclofen = GABA-B agonist probe for autism E/I imbalance.

## DDI (mechanism-typed only)
- PD-additivity: CNS depression with other GABA-B agonists / sedatives (additive, not CYP).
- Transporter: intestinal absorption via MCT1 (substrate) — theoretical MCT1 competition.
- CYP: negligible (not a substrate of major CYPs) -> low metabolic DDI liability.

## NEW angles for phenibut program
1. GABA-B B1-subunit-alone affinity is uM (pIC50 4.4-4.6) but functional heteromer is nM (pIC50 8.5): the docking work targeting GABA-B should validate against the HETEROMER potency, not isolated B1 — explains why phenibut B1 docking (~92 uM) looks weak but could still be functionally meaningful.
2. Baclofen eutomer is RENALLY cleared & non-CYP — supports renal-dominant hypothesis for phenibut PK (the chlorophenyl-GABA scaffold is not a CYP substrate).
3. MCT1 as the intestinal uptake transporter for the GABA-analog scaffold — candidate shared transporter for phenibut absorption (testable angle).
4. Arbaclofen ADMET is "clean" (low hERG, neg AMES, clean stress-response) — gives a benchmark ADMET vector to compare phenibut's ADMET-AI 104-endpoint profile against the proven-safe R-eutomer congener.