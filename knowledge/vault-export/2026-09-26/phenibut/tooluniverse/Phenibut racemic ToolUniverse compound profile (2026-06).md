---
title: Phenibut racemic ToolUniverse compound profile (2026-06)
type: report
permalink: main/phenibut/tooluniverse/phenibut-racemic-tool-universe-compound-profile-2026-06
tags:
- phenibut
- tooluniverse
- admet
- chembl
- gaba-b
- faers
---

# Phenibut (racemic) — ToolUniverse EXECUTE-MAXIMAL pull, 2026-06-22

Identifiers: CID 14113; InChIKey DAFOCGYVTAOKAJ-UHFFFAOYSA-N; C10H13NO2; MW 179.22; XLogP -1.6 (PubChem) / ADMET-AI logP 1.20; TPSA 63.3; HBD 2 HBA 2/3; 1 stereocenter; CAS 1078-21-3. ATC N06BX22. UNII T2M58D6LA8. ChEMBL CHEMBL315818, DrugBank DB13455, DrugCentral 4863, ChEBI 136039.

## CORRECTION to prior grounding
Prior note said phenibut "ABSENT from ChEMBL/BindingDB/GtoPdb". REFINED: phenibut IS registered in ChEMBL (CHEMBL315818) with max_phase -1.0, therapeutic_flag false, mechanisms=[] (no curated MoA). It is absent of *bona-fide affinity data in GtoPdb/Pharos* (phenibut NOT in GABBR1 Pharos ligand list of 8). So: registered structure, no curated MoA, but ONE real measured affinity exists in ChEMBL (below).

## NEW: experimental GABA-B Ki
ChEMBL activity record: GABA-B receptor **Ki = 177,000 nM = 177 uM** ([3H]CGP54626 displacement, radioligand binding). Independent experimental anchor; prior grounding had GABA-B "~92 uM" docking-derived. Racemic value 177 uM is the same order; R-enantiomer would be ~2x more potent.

## Monoamine targets = INACTIVE (settles dopamine puzzle direction)
All DAT/NET/SERT/D1/D3/5HT1A/5HT2B/MAOA/alpha2A/mu-opioid records are AC50 > 30,000 nM single-point screening (NIBR selectivity panel) = inactive. Supports: NO direct monoamine transporter binding -> dopamine effect must be indirect (GABA-B-mediated VTA disinhibition), consistent with validated hypothesis B. The 31 ChEMBL "targets" are screening-panel records, NOT real polypharmacology.

## ADMET-AI
BBB_Martins 0.732 (penetrant) BUT Caco2 -5.18 + PAMPA 0.324 (low passive permeability) + Pgp non-substrate (0.004) — polar zwitterion, slow/poor passive CNS entry. CYP inhibition ALL <0.03 (1A2/2C19/2C9/2D6/3A4) -> not a CYP inhibitor; minimal hepatic metabolism (supports renal-clearance side of PK split). Tox: AMES 0.038 (non-mutagenic), hERG 0.054 (low cardiac), DILI 0.126 (low hepatotox), LD50_Zhu 2.32. Clearance/half-life/VDss percentiles all low. HIA 0.948, Bioavailability_Ma 0.841, QED 0.73, 0 Lipinski violations.

## FAERS (openFDA, last_updated 2026-04-28)
Top reactions: DRUG ABUSE 14, DRUG INTERACTION 14, INTENTIONAL PRODUCT MISUSE 9, WITHDRAWAL SYNDROME 4, DRUG DEPENDENCE 3, SOMNOLENCE/SEDATION. Characterization: Suspect 49, Concomitant 18, Interacting 12 (DDI signal). Confirms dependence/withdrawal profile (question E) and PD-additivity DDI risk with CNS depressants (opioids -> coma/resp depression per Bonnet 2024).

## NEW literature angle (a2d question F/a2d)
Bonnet et al. 2024 (Dtsch Arztebl Int, PMC11539871) explicitly frames phenibut as a gabapentinoid inhibiting alpha2-delta subunits of presynaptic voltage-gated Ca channels (like gabapentin/pregabalin) — independent support for the a2d binding hypothesis. Afolabi 2026 (Curr Neuropharmacol) novel GABA-B modulator vs phenibut (docking dGbind phenibut -8.0 kcal/mol).
