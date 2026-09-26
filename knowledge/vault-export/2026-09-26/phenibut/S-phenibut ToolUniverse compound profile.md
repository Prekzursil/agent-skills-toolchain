---
title: S-phenibut ToolUniverse compound profile
type: report
permalink: main/phenibut/s-phenibut-tool-universe-compound-profile
tags:
- phenibut
- S-phenibut
- ADMET
- tooluniverse
- enantiomer
---

# S-phenibut ToolUniverse compound profile (2026-06-22)

EXECUTE-MAXIMAL ToolUniverse pull on S-phenibut (the GABA-B-INACTIVE enantiomer; R is active per program anchor F).

## Identity (PubChem, verbatim)
- CID **685623**; IUPAC **(3S)-4-amino-3-phenylbutanoic acid**
- SMILES `C1=CC=C(C=C1)[C@H](CC(=O)O)CN`; InChIKey **DAFOCGYVTAOKAJ-SECBINFHSA-N**
- Formula C10H13NO2; MW 179.22; XLogP -1.6; TPSA 63.3; HBD 2; HBA 3; RotB 4
- Racemate phenibut = CID 14113; DrugBank only has RACEMIC Phenibut DB13455 (UNII T2M58D6LA8), no enantiomer split.

## ADMET-AI (measured)
- BBB_Martins 0.750 (53.0 pct) -> BBB-permeant predicted
- AMES 0.066; hERG 0.063; DILI 0.144; ClinTox 0.101; Carcinogen 0.315; LD50_Zhu 2.216; Skin_Reaction 0.566. Clean tox profile.

## SwissADME (measured)
- GI absorption High; **BBB permeant Yes**; Pgp substrate No; all CYP1A2/2C19/2C9/2D6/3A4 inhibition = n/d (not an inhibitor)
- Consensus logP 0.56; ESOL "Very soluble"; Lipinski 0 viol; bioavailability 0.55; PAINS 0; Brenk 0; SA score 1.59
- log Kp -8.52

## Binding / targets
- BindingDB targets_by_compound @0.85 sim: **EMPTY** (phenibut/enantiomers absent from binding DBs — confirms program anchor)
- No ChEMBL/GtoPdb entry surfaced for the S-enantiomer.

## Key NEW angle
- OpenAlex W4392912877 (Mohanlal et al. 2024, Chem Asian J, doi 10.1002/asia.202400064): Rosetta docking + GROMACS MMPB(GB)SA on human GABA-B1 ECD shows R-enantiomers of GABA analogs bind better than R-baclofen AND R-phenibut; provides an independent in silico GABA-B1 stereoselectivity benchmark for our +6.09 docking / -2.61 ATM work. Direct external corroboration that S is the weak binder.

## FAERS (racemate "phenibut")
- Top reactions: DRUG ABUSE 14, DRUG INTERACTION 14, INTENTIONAL PRODUCT MISUSE 9, MULTIPLE ORGAN DYSFUNCTION 9, UNRESPONSIVE TO STIMULI 9, LOSS OF CONSCIOUSNESS 7. Enantiomer-agnostic (no S-specific reports).

## DDI mechanism typing
- S-phenibut: NOT a CYP inhibitor (all n/d), NOT a Pgp substrate -> no CYP/transporter-mediated DDI predicted. Any phenibut DDI is **PD CNS-depressant additivity** (FAERS DRUG INTERACTION signal consistent), not metabolic.

## Tool failures (record-once)
- mcp__rdkit__compute_descriptors not reachable via ToolUniverse execute_tool (separate MCP). FDA_get_pharmacokinetics(phenibut) NOT_FOUND (not FDA-approved). No retry-loop used.
